# Utility functions for starting/stopping sricd
from subprocess import Popen
import os, signal
import time, sys
PID_FILE = "/tmp/sricd.pid"

def kill():
    "Kill sricd"
    print "Killing sricd"
    sys.stdout.flush()

    if os.path.exists(PID_FILE):
        f = open(PID_FILE)
        pid = int( f.read() )
        f.close()

        os.kill( pid, signal.SIGKILL )
    else:
        print "sricd file doesn't exist"

def start(logfile):
    out = open( logfile, "a" )
    print >>out, "-" * 80

    p = Popen( "sricd -p /tmp/sricd.pid -d -u /dev/ttyS1 -v",
               stdin = open("/dev/null", "r"),
               stdout = out, stderr = out, shell = True )
    p.wait()

def restart(logfile):
    kill()
    start(logfile)
