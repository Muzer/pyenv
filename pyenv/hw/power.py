from jointio import IOPoll
from events import Event
import pysric

CMD_ENABLE_INPUT_NOTES = 5
CMD_PLAY_PIEZO = 6
CMD_SET_LEDS = 7

class Power:
    def __init__(self, dev):
        self.dev = dev

    def beep( self, freq = 1000, dur = 0.1 ):
        "Beep"

        if hasattr( freq, "__iter__" ):
            beeps = freq
        else:
            "It's just a single note"
            beeps = [(freq, dur)]

        if len(beeps) > 10:
            # TODO: Do something better here
            raise "Too many beeps added"

        tx = [ CMD_PLAY_PIEZO, len(beeps) ]
        for f,d  in beeps:
            d = int(1000 * d)

            # Frequency
            tx.append( (f >> 8) & 0xff )
            tx.append( f & 0xff )
            # Duration
            tx.append( (d >> 8) & 0xff )
            tx.append( d & 0xff )

            # Volume (fixed right now)
            tx.append( 5 )

        self.dev.txrx( tx )

ps = pysric.PySric()
power = None

if pysric.SRIC_CLASS_POWER in ps.devices:
    power = Power( ps.devices[pysric.SRIC_CLASS_POWER][0] )
