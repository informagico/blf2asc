#!/usr/bin/python

import can
import sys
import getopt
import time


PROGRESS_INTERVAL_SECONDS = 0.5


def print_usage():
    print("blf2asc.py -i <inputfile> -o <outputfile> [-c <can_ids>]")
    print("  -c, --can-id  Comma-separated CAN IDs to include, e.g. 123,0x456")


def parse_can_id(value):
    value = value.strip()
    if not value:
        raise ValueError("empty CAN ID")

    if value.lower().startswith("0x"):
        return int(value, 16)

    try:
        return int(value, 16)
    except ValueError:
        return int(value, 0)


def parse_can_id_list(value):
    return set(parse_can_id(item) for item in value.split(","))


def format_relative_timestamp(timestamp, start_timestamp):
    elapsed = max(timestamp - start_timestamp, 0)
    total_seconds = int(elapsed)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    microseconds = int(round((elapsed - total_seconds) * 1000000))

    if microseconds == 1000000:
        seconds += 1
        microseconds = 0
    if seconds == 60:
        minutes += 1
        seconds = 0

    return "{:02d}:{:02d}.{:06d}".format(minutes, seconds, microseconds)


def format_message(msg, start_timestamp):
    timestamp = format_relative_timestamp(msg.timestamp, start_timestamp)
    msg_text = str(msg)
    msg_text = msg_text[msg_text.find("ID:"):]
    msg_text = msg_text.split("    Channel:", 1)[0]
    if msg_text.startswith("ID: "):
        msg_text = msg_text[4:]
    channel = str(msg.channel if msg.channel is not None else "-")

    return "{} CH {}{}".format(timestamp, channel.ljust(3), msg_text.upper())


def print_progress(reader, read_count, written_count, skipped_count, last_progress, force=False):
    now = time.monotonic()
    if not force and now - last_progress < PROGRESS_INTERVAL_SECONDS:
        return last_progress

    file_size = getattr(reader, "file_size", 0) or 0
    try:
        file_position = reader.file.tell()
    except ValueError:
        # BLFReader may close its file after iteration reaches EOF.
        file_position = file_size

    if file_size > 0:
        percent = min(file_position / file_size * 100, 100)
        progress = "Progress: {:6.2f}% | {:,} read | {:,} written | {:,} skipped".format(
            percent, read_count, written_count, skipped_count
        )
    else:
        progress = "Progress: {:,} read | {:,} written | {:,} skipped".format(
            read_count, written_count, skipped_count
        )

    print("\r" + progress, end="", flush=True)
    return now


def main(argv):
    # get command line arguments

    inputfile = ""
    outputfile = ""
    included_ids = set()
    try:
        opts, args = getopt.getopt(
            argv, "hi:o:c:", ["ifile=", "ofile=", "can-id="]
        )
    except getopt.GetoptError:
        print_usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            print_usage()
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
        elif opt in ("-c", "--can-id"):
            try:
                included_ids.update(parse_can_id_list(arg))
            except ValueError as exc:
                print("Invalid CAN ID filter: {}".format(exc))
                sys.exit(2)

    if not inputfile or not outputfile:
        print_usage()
        sys.exit(2)

    print()
    print('Input file:\t', inputfile)
    print('Output file:\t', outputfile)
    if included_ids:
        print(
            "Including CAN IDs:\t",
            ", ".join("0x{:X}".format(can_id) for can_id in sorted(included_ids)),
        )

    # convert the file

    log = can.BLFReader(inputfile)
    read_count = 0
    written_count = 0
    skipped_count = 0
    start_timestamp = None
    last_progress = 0

    try:
        with open(outputfile, "w") as f:
            for msg in log:
                read_count += 1

                if included_ids and msg.arbitration_id not in included_ids:
                    skipped_count += 1
                    last_progress = print_progress(
                        log, read_count, written_count, skipped_count, last_progress
                    )
                    continue

                if start_timestamp is None:
                    start_timestamp = msg.timestamp

                f.write(format_message(msg, start_timestamp) + "\n")
                written_count += 1
                last_progress = print_progress(
                    log, read_count, written_count, skipped_count, last_progress
                )

        print_progress(
            log, read_count, written_count, skipped_count, last_progress, force=True
        )
    finally:
        log.stop()

    print()
    print(
        "Done! Read {:,} messages, wrote {:,}, skipped {:,}.".format(
            read_count, written_count, skipped_count
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:])
