#!/usr/bin/env python
"""Thin entry point so `python main.py ...` works as described in the brief."""
import sys

from nse_downloader.cli import main

if __name__ == "__main__":
    sys.exit(main())
