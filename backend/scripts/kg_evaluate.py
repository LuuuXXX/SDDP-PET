#!/usr/bin/env python3
"""Thin wrapper for KG evaluation. Calls sddp.kg.evaluate main().

Per Dev-Phase 0 task 2.9 — this script location is referenced from dod.md D0-6.
"""
from __future__ import annotations
import sys
import os

# Allow running without `pip install -e .`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sddp.kg.evaluate import main

if __name__ == "__main__":
    sys.exit(main())
