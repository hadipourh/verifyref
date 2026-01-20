# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Hosein Hadipour
"""
Custom exceptions for VerifyRef.

This module provides a hierarchy of exceptions for better error handling
and more informative error messages throughout the application.
"""


class VerifyRefError(Exception):
    """Base exception for all VerifyRef errors."""
    pass


class ConfigurationError(VerifyRefError):
    """Raised when there's a configuration problem."""
    
    def __init__(self, message: str, config_key: str = None):
        self.config_key = config_key
        if config_key:
            message = f"Configuration error for '{config_key}': {message}"
        super().__init__(message)


class DatabaseError(VerifyRefError):
    """Base exception for database-related errors."""
    
    def __init__(self, database: str, message: str):
        self.database = database
        super().__init__(f"[{database}] {message}")


class DatabaseConnectionError(DatabaseError):
    """Raised when a database connection fails."""
    pass


class DatabaseTimeoutError(DatabaseError):
    """Raised when a database request times out."""
    
    def __init__(self, database: str, timeout: int):
        self.timeout = timeout
        super().__init__(database, f"Request timed out after {timeout} seconds")


class RateLimitError(DatabaseError):
    """Raised when an API rate limit is exceeded."""
    
    def __init__(self, database: str, retry_after: int = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(database, message)


class PDFProcessingError(VerifyRefError):
    """Base exception for PDF processing errors."""
    pass


class PDFNotFoundError(PDFProcessingError):
    """Raised when a PDF file is not found."""
    
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"PDF file not found: {path}")


class PDFExtractionError(PDFProcessingError):
    """Raised when reference extraction from PDF fails."""
    
    def __init__(self, message: str, path: str = None):
        self.path = path
        if path:
            message = f"Failed to extract references from '{path}': {message}"
        super().__init__(message)


class GrobidError(VerifyRefError):
    """Base exception for GROBID-related errors."""
    pass


class GrobidConnectionError(GrobidError):
    """Raised when GROBID service is unavailable."""
    
    def __init__(self, url: str):
        self.url = url
        super().__init__(
            f"Cannot connect to GROBID service at {url}. "
            "Make sure GROBID is running: docker run -d -p 8070:8070 lfoppiano/grobid:0.8.2"
        )


class GrobidProcessingError(GrobidError):
    """Raised when GROBID fails to process a document."""
    
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        if status_code:
            message = f"GROBID processing failed (HTTP {status_code}): {message}"
        super().__init__(message)


class ClassificationError(VerifyRefError):
    """Raised when reference classification fails."""
    pass


class AIVerificationError(VerifyRefError):
    """Base exception for AI verification errors."""
    pass


class AIConnectionError(AIVerificationError):
    """Raised when AI service connection fails."""
    
    def __init__(self, message: str = "Failed to connect to AI service"):
        super().__init__(message)


class AIQuotaExceededError(AIVerificationError):
    """Raised when AI API quota is exceeded."""
    
    def __init__(self):
        super().__init__(
            "OpenAI API quota exceeded. Check your usage at https://platform.openai.com/usage"
        )


class InvalidReferenceError(VerifyRefError):
    """Raised when a reference is invalid or cannot be parsed."""
    
    def __init__(self, message: str, reference_index: int = None):
        self.reference_index = reference_index
        if reference_index is not None:
            message = f"Reference #{reference_index}: {message}"
        super().__init__(message)
