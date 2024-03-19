"""Script to test CPU load imposed by a simple disk read operation."""


import re
import sys
import argparse
import subprocess
from os import linesep
from typing import List, Dict


# statistics file path to compute cpu load
STAT_FILE_PATH = "/proc/stat"


def parse_cli() -> argparse.Namespace:
    """Parse arguments from command line.

    Returns:
        argparse.Namespace: namespace of arguments for the script.
    """

    parser = argparse.ArgumentParser(
        prog="disk_cpu_load",
        description=__doc__,
    )

    parser.add_argument(
        "--max-load",
        type=int,
        default=30,
        help="The maximum acceptable CPU load, as a percentage.\
                             Defaults to 30.",
    )
    parser.add_argument(
        "--xfer",
        type=int,
        default=4096,
        help="The amount of data to read from the disk, \
                        in mebibytes. Defaults to 4096 (4 GiB).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="If present, produce more verbose output",
    )
    parser.add_argument(
        "--device-filename",
        type=str,
        default="/dev/sda",
        help='This is the WHOLE-DISK device filename (with or \
            without "/dev/"), e.g. "sda" or "/dev/sda". \
            The script finds a filesystem on that device, \
            mounts it if necessary, and runs the tests on that \
            mounted filesystem. Defaults to /dev/sda.',
    )

    return parser.parse_args()


def compute_cpu_load(
    start_load: List[int], end_load: List[int], verbose_mode: bool
) -> int:
    """Compute's CPU load between two points in time.

    Args:
        start_load (List[int]): CPU statistics from /proc/stat from START point
        end_load (List[int]): CPU statistics from /proc/stat from END point
        verbose_mode (bool): determine if the script ran in verbose mode

    Returns:
        CPU load over the two measurements, as a percentage (0-100)"""
    diff_idle = end_load[3] - start_load[3]
    start_total = sum(start_load)
    end_total = sum(end_load)
    diff_total = end_total - start_total
    diff_used = diff_total - diff_idle

    if verbose_mode:
        print(
            f"Start CPU time = {start_total}",
            f"End CPU time = {end_total}",
            f"CPU time used = {diff_used}",
            f"Total elapsed time = {diff_total}",
            sep=linesep,
        )

    return 0 if not diff_total else diff_used * 100 // diff_total


def get_cpu_load() -> List[int]:
    """Calculate cpu load from statistics and return it."""
    with open(STAT_FILE_PATH) as stat_file:
        match_cpu_stats = re.match("cpu .*", stat_file.read())
        return list(
            map(
                int, filter("".__ne__, match_cpu_stats.group().split(" ")[1:])
            )
        )


def run_check_subprocess(**kwargs: Dict) -> None:
    """Run subprocess and check no errors occured during execution."""
    res_run = None
    try:
        # override check in case given
        kwargs["check"] = True
        res_run = subprocess.run(**kwargs)
    except subprocess.CalledProcessError:
        if res_run:
            sys.exit(res_run.returncode)
        sys.exit(1)


if __name__ == "__main__":
    cli_args = parse_cli()
    print(
        f"Testing CPU load when reading {cli_args.xfer} MiB from "
        f"{cli_args.device_filename}",
        f"Maximum acceptable CPU load is {cli_args.max_load}",
        sep=linesep,
    )

    run_check_subprocess(
        args=[f"blockdev --flushbufs {cli_args.device_filename}"], shell=True
    )
    start_load = get_cpu_load()

    if cli_args.verbose:
        print("Beginning disk read....")

    run_check_subprocess(
        args=[
            "dd",
            f"if={cli_args.device_filename}",
            "of=/dev/null",
            "bs=1048576",
            f"count={cli_args.xfer}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if cli_args.verbose:
        print("Disk read complete!")

    end_load = get_cpu_load()

    cpu_load = compute_cpu_load(start_load, end_load, cli_args.verbose)

    print(f"Detected disk read CPU load is {cpu_load}")
    if cpu_load > cli_args.max_load:
        print("*** DISK CPU LOAD TEST HAS FAILED! ***")
        sys.exit(1)
