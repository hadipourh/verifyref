# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Hosein Hadipour
"""
Extractor package - Reference parsing and normalization.

This package provides:
- Reference parsing from GROBID XML output
- Text cleaning and normalization
- Author and venue extraction
"""

from .reference_parser import ReferenceParser

__all__ = [
    "ReferenceParser",
]
