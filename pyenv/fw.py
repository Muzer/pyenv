#!/usr/bin/python
# Routines for invoking flashb and thus updating board firmware.
import json
import subprocess, os.path, re
import sr.motor
from sr.power import Power
import sr.pysric as pysric
import stm32loader
import threading
import time

SRIC_VERSION_BUF_CMD = 0x84

power_vbuf = [ 7, 100, 114, 105, 118, 101, 114, 115, 5, 37,
               251, 84, 30, 144, 8, 102, 108, 97, 115, 104,
               52, 51, 48, 5, 87, 171, 113, 171, 124, 7,
               108, 105, 98, 115, 114, 105, 99, 5, 31, 227,
               112, 155, 220, 1, 46, 5, 230, 243, 165, 7,
               161]

def sric_read_vbuf(dev):
    "Read the versionbuf from dev"
    d = []
    off = 0

    while True:
        "Loop until we've received all the buffer"
        r = dev.txrx( [SRIC_VERSION_BUF_CMD, off & 0xff, (off >> 8) & 0xff] )
        d += r
        if len(r) == 0:
            break
        off += len(r)

    return d

class LockableUnsafeDev(object):
    "Lockable SRIC device that does *not* use a threadlocal connection"
    def __init__(self, dev ):
        # A lock for transactions on this device
        self.dev = dev
        self.lock = threading.Lock()

    def __getattr__(self, name):
        "Provide access to the underlying Sric device"
        return getattr( self.dev, name )

    def txrx( self, *args, **kw ):
        return self.dev.txrx( *args, **kw )

class FwUpdater(object):
    def __init__(self, conf, sricd_restart):
        self.conf = conf
        self.sricd_restart = sricd_restart
        self.splash = None

        self.fwdir = os.path.join( self.conf.prog_dir, "firmware" )
        logpath = os.path.join( self.conf.log_dir, "fw-log.txt" )
        self.fwlog = open( logpath , "at")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceba):
        # Close our stuff
        self.stop_splash()
        self.fwlog.close()

    def start_splash(self):
        if self.splash is not None:
            "Splash is already running"
            return

        self.splash = subprocess.Popen( [ os.path.join( self.conf.bin_dir,
                                                        "fwsplash" ) ],
                                        stdin = subprocess.PIPE )

    def stop_splash(self):
        if self.splash is not None:
            self.splash.kill()
            self.splash.wait()

    def update(self):
        if self.check_power_update():
            self.start_splash()
            self.update_power()
            # The power board's been adjusted, so restart it
            self.sricd_restart()

        # Now bring up the motor rail so we can talk to the motor boards
        p = pysric.PySric()
        dev = LockableUnsafeDev(p.devices[pysric.SRIC_CLASS_POWER][0])
        # Power's constructor brings up the motor rail
        power = Power(dev)

        for mdev in sr.motor.find_devs():
            if self.check_motor_update(mdev.device_node):
                self.start_splash()
                self.update_motor(mdev.device_node)

    def check_power_update(self):
        "Determine if a power board update is necessary using its vbuf"
        p = pysric.PySric()
        vb = sric_read_vbuf( p.devices[ pysric.SRIC_CLASS_POWER ][0] )
        return vb != power_vbuf

    def update_power( self):
        p = subprocess.Popen( [ os.path.join( self.conf.bin_dir, "flashb" ),
                                "-c", os.path.join( self.fwdir, "flashb.config" ),
                                "-n", "power", "-f",
                                os.path.join( self.fwdir, "power-top" ),
                                os.path.join( self.fwdir, "power-bottom" ) ],
                              stdout = self.fwlog, stderr = self.fwlog )

        pulsemsg = "{0}\n".format( json.dumps( { "type": "pulse", "msg": "Updating power board firmware." } ) )

        while p.poll() is None:
            self.splash.stdin.write( pulsemsg )
            self.splash.stdin.flush()
            time.sleep(0.25)
        res = p.wait()

        print >>self.fwlog, "flashb returned %i" % (res),

    def check_motor_update(self, dev_path):
        try:
            motor = sr.motor.Motor(dev_path)
        except sr.motor.IncorrectFirmware:
            "Requires update"
            return True

        motor.close()
        return False

    def update_motor(self, dev_path):
        with sr.motor.Motor(dev_path, check_fwver=False) as motor:
            motor._jump_to_bootloader()

        def prog_cb(mode, prog):
            if mode == "READ":
                msg = "Verifying motor board firmware."
                prog = 0.5 + (prog * 0.5)
            else:
                msg = "Writing motor board firmware."
                prog *= 0.5

            m = { "type": "prog",
                  "fraction": prog,
                  "msg": msg }
            s = "{0}\n".format(json.dumps(m))
            self.splash.stdin.write(s)
            self.splash.stdin.flush()

            print >>self.fwlog, mode, prog

        c = stm32loader.CommandInterface( port=dev_path,
                                          baudrate=115200,
                                          prog_cb = prog_cb )
        c.initChip()
        c.cmdEraseMemory()

        # Write
        d = [ord(x) for x in open(os.path.join( self.fwdir, "mcv4.bin" ), "r").read()]
        c.writeMemory(0x08000000, d)

        # Verify:
        v = c.readMemory(0x08000000, len(d))
        if d != v:
            raise Exception("Firmware verification error :(")

        # Reset/quit bootloader
        c.cmdGo(0x8000000)
