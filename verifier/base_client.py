# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Hosein Hadipour
"""
Abstract base class for academic database clients.

This module provides a consistent interface for all database clients,
ensuring they implement the same methods and return standardized results.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import logging
import time

from exceptions import DatabaseConnectionError, DatabaseTimeoutError, RateLimitError


@dataclass
class SearchResult:
    """
    Standardized search result from any academic database.
    
    All database clients should return results in this format
    for consistent processing by the classifier.
    """
    title: str
    authors: List[str]
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    source: str = "unknown"
    raw_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "doi": self.doi,
            "url": self.url,
            "abstract": self.abstract,
            "source": self.source,
            "confidence": self.confidence,
        }


class BaseAcademicClient(ABC):
    """
    Abstract base class for all academic database clients.
    
    Subclasses must implement:
    - search_paper(): Search for papers matching criteria
    - is_available(): Check if service is available
    
    Provides common functionality:
    - Logging setup
    - Rate limiting helpers
    - Retry logic
    - Result standardization
    """
    
    def __init__(
        self,
        name: str,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit_delay: float = 0.5,
    ):
        """
        Initialize the base client.
        
        Args:
            name: Human-readable name of the database
            base_url: Base URL for API requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            rate_limit_delay: Delay between requests in seconds
        """
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        self.logger = logging.getLogger(f"verifyref.{name.lower().replace(' ', '_')}")
        self._last_request_time: float = 0
        self._available: Optional[bool] = None
    
    @abstractmethod
    def search_paper(
        self,
        title: str,
        authors: Optional[List[str]] = None,
        year: Optional[int] = None,
        venue: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for papers matching the given criteria.
        
        Args:
            title: Paper title to search for
            authors: List of author names (optional)
            year: Publication year (optional)
            venue: Publication venue (optional)
            limit: Maximum number of results to return
            
        Returns:
            List of matching papers as dictionaries
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the database service is available.
        
        Returns:
            True if service is available, False otherwise
        """
        pass
    
    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Verify a reference by searching the database.
        
        This is a convenience method that extracts fields from a reference
        dictionary and calls search_paper().
        
        Args:
            reference: Reference dictionary with title, authors, year, venue
            
        Returns:
            List of matching papers from the database
        """
        return self.search_paper(
            title=reference.get("title", ""),
            authors=reference.get("authors", []),
            year=reference.get("year"),
            venue=reference.get("venue"),
        )
    
    def _respect_rate_limit(self) -> None:
        """
        Ensure we don't exceed rate limits by waiting if necessary.
        
        Call this before making any API request.
        """
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            self.logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()
    
    def _handle_response_error(self, status_code: int, response_text: str) -> None:
        """
        Handle HTTP error responses consistently.
        
        Args:
            status_code: HTTP status code
            response_text: Response body text
            
        Raises:
            RateLimitError: If rate limited (429)
            DatabaseConnectionError: For other errors
        """
        if status_code == 429:
            # Try to parse retry-after header
            raise RateLimitError(self.name, retry_after=60)
        elif status_code >= 500:
            raise DatabaseConnectionError(
                self.name, f"Server error (HTTP {status_code}): {response_text[:200]}"
            )
        elif status_code >= 400:
            self.logger.warning(
                f"{self.name} request failed (HTTP {status_code}): {response_text[:200]}"
            )
    
    def _standardize_result(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a raw database result to standardized format.
        
        Override this in subclasses to handle database-specific formats.
        
        Args:
            raw_result: Raw result from database API
            
        Returns:
            Standardized result dictionary
        """
        return {
            "title": raw_result.get("title", ""),
            "authors": raw_result.get("authors", []),
            "year": raw_result.get("year"),
            "venue": raw_result.get("venue"),
            "doi": raw_result.get("doi"),
            "url": raw_result.get("url"),
            "source": self.name.lower(),
            "raw_data": raw_result,
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', base_url='{self.base_url}')"
