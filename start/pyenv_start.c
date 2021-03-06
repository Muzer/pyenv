#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>

#include <sric.h>

/* Push buttons */
#define INPUT_B0    (1<<0)
#define INPUT_B1    (1<<1)
#define INPUT_B2    (1<<2)

int
main(int argc, char **argv)
{
	sric_frame frame;
	sric_context ctx;
	const sric_device *dev;
	int ret;

	ctx = sric_init();

	/* Enumerate and find the power board */
	dev = NULL;
	do {
		dev = sric_enumerate_devices(ctx, dev);
		if (dev->type == SRIC_CLASS_POWER)
			break;
	} while (dev != NULL);

	if (dev == NULL) {
		fprintf(stderr, "pyenv_start: could not find power board to "
				"wait on\n");
		exit(1);
	}

	/* Because no-one else is going to, at this point we turn on
	 * notifications from the power board about button presses */
	frame.address = dev->address;
	frame.note = -1;
	frame.payload_length = 2;
	frame.payload[0] = 5;
	frame.payload[1] = 1;
	if (sric_txrx(ctx, &frame, &frame, -1) != 0) {
		fprintf(stderr, "Error enabling button presses: %d\n",
						sric_get_error(ctx));
		exit(1);
	}

	/* Register our interest in button presses */
	if (sric_note_register(ctx, dev->address, 0)) {
		fprintf(stderr, "Error registering for button presses: %d\n",
						sric_get_error(ctx));
		exit(1);
	}

	/* And wait for them */
	do {
		uint16_t flags;
		uint16_t edges;

		if (sric_poll_note(ctx, &frame, -1) != 0) {
			fprintf(stderr, "Error fetching note frame: %d\n",
						sric_get_error(ctx));
			exit(1);
		}

		if (frame.payload_length != 5)
			continue;

		flags = frame.payload[1];
		flags |= frame.payload[2] << 8;
		edges = frame.payload[3];
		edges |= frame.payload[3] << 8;

		/* A '1' edge means the button has just been pressed */
		if ( (flags & INPUT_B0) && (edges & 1) )
			exit(0);
	} while (1);

	return 0;
}
