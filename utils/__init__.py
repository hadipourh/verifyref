# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Hosein Hadipour
"""
Utils package - Helper functions and utilities.

This package provides:
- Text similarity calculations
- Input parsing and detection
- Output formatting and report generation
- Terminal display utilities
"""

from .helpers import (
    normalize_text,
    calculate_text_similarity,
    extract_year_from_text,
    clean_author_name,
)
from .academic_matching import (
    calculate_venue_similarity,
    calculate_author_similarity,
)

__all__ = [
    "normalize_text",
    "calculate_text_similarity",
    "extract_year_from_text",
    "clean_author_name",
    "calculate_venue_similarity",
    "calculate_author_similarity",
]
