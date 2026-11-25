#!/usr/bin/env python3
"""Entry point: python ppgen.py <command> [--json]. See README.md or `python ppgen.py -h`."""
import sys

from ppgen.cli import main

if __name__ == "__main__":
    sys.exit(main())
