#!/usr/bin/python

import can
import csv
import sys
import getopt


def main(argv):
    # get command line arguments

    inputfile = ""
    outputfile = ""
    try:
        opts, args = getopt.getopt(argv, "hi:o:", ["ifile=", "ofile="])
    except getopt.GetoptError:
        print("blf2asc.py -i <inputfile> -o <outputfile>")
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            print("test.py -i <inputfile> -o <outputfile>")
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg

    print()
    print('Input file:\t', inputfile)
    print('Output file:\t', outputfile)

    # convert the file

    log = can.BLFReader(inputfile)
    log = list(log)

    f = open(outputfile, "w")

    for msg in log:
        msg = str(msg)
        msg = msg[0:30] + msg[30:100].upper() + msg[100:]

        f.write(msg + "\n")

    f.close()

    print()
    print('Done!')


if __name__ == "__main__":
    main(sys.argv[1:])
