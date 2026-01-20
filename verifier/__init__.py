# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Hosein Hadipour
"""
Verifier package - Academic database clients and reference classification.

This package provides:
- Multi-database verification across academic sources
- Reference classification and fraud detection
- AI-powered verification (optional)
- Base client class for database implementations
"""

from .classifier import ReferenceClassifier, ClassificationResult, VerificationResult
from .multi_database_verifier import MultiDatabaseVerifier
from .base_client import BaseAcademicClient, SearchResult

__all__ = [
    "ReferenceClassifier",
    "ClassificationResult", 
    "VerificationResult",
    "MultiDatabaseVerifier",
    "BaseAcademicClient",
    "SearchResult",
]
