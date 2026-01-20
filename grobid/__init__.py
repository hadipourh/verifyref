# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Hosein Hadipour
"""
GROBID package - PDF processing and reference extraction.

This package provides:
- GROBID service client for PDF processing
- Reference extraction from academic PDFs
- Citation string parsing
"""

from .client import GrobidClient

__all__ = [
    "GrobidClient",
]
