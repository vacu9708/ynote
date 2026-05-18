#!/usr/bin/env python3
"""Compatibility launcher for running Ynote from the source checkout."""

import sys

from ynote.main import main


if __name__ == '__main__':
    sys.exit(main())
