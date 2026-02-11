# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Hosein Hadipour
"""
GROBID package - PDF processing and reference extraction.

This package provides:
- GROBID service client for PDF processing
- Smart client with automatic fallback chain
- Reference extraction from academic PDFs
- Citation string parsing
- Fallback PyMuPDF parser when GROBID unavailable
"""

from .client import GrobidClient, SmartGrobidClient, get_smart_client

__all__ = [
    "GrobidClient",
    "SmartGrobidClient", 
    "get_smart_client",
]
