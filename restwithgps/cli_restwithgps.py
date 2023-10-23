#!/bin/env python3
from __future__ import annotations

import argparse
import signal
import sys
import logging
import os

from . import restwithgps


def get_opt() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Rest with GPS')
    parser.add_argument("--log", dest="loglevel",
                        type=str, metavar="LOG_LEVEL",
                        default=os.environ.get("LOG_LEVEL", "info"))
    parser.add_argument("-s", dest="min_stop",
                        type=int, metavar="STOP_MINUTES",
                        default=5)
    parser.add_argument("filepath", action="store", metavar="fit FILEPATH")

    args = parser.parse_args()

    return args


def sig_handler(signum, frame) -> None:
    sys.stderr.write("Terminated.\n")
    sys.exit(15)


def main() -> int:
    signal.signal(signal.SIGTERM, sig_handler)

    args = get_opt()
    logging.basicConfig(level=getattr(logging, args.loglevel.upper()))

    restwithgps.rest_with_gps(args.filepath, args.min_stop)
    print("Done")

    return 0


if __name__ == "__main__":
    sys.exit(main())
