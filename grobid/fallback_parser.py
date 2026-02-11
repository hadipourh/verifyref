"""
VerifyRef - High-performance academic reference verification tool
Copyright (C) 2025 Hosein Hadipour <hsn.hadipour@gmail.com>

Fallback PDF reference parser using PyMuPDF when GROBID is unavailable.
This provides graceful degradation with lower accuracy (~75%) compared to GROBID (~95%).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Try to import PyMuPDF, but don't fail if not available
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.debug("PyMuPDF not installed - fallback parser unavailable")


class FallbackReferenceParser:
    """
    Lightweight PDF reference parser using PyMuPDF and regex.
    Used as fallback when GROBID is unavailable.
    
    Accuracy: ~75% (vs GROBID's ~95%)
    Best for: Getting something rather than nothing
    """
    
    def __init__(self):
        self.available = PYMUPDF_AVAILABLE
        
        # Patterns to identify reference sections
        self.ref_section_patterns = [
            r'\bReferences\b',
            r'\bBibliography\b', 
            r'\bWorks\s+Cited\b',
            r'\bLiterature\s+Cited\b',
            r'\bCited\s+References\b',
        ]
        
        # Pattern to match individual references (numbered or bulleted)
        self.ref_entry_pattern = re.compile(
            r'^\s*[\[\(]?\d+[\]\)]?\.?\s+(.+?)(?=^\s*[\[\(]?\d+[\]\)]?\.?\s+|\Z)',
            re.MULTILINE | re.DOTALL
        )
        
        # Author pattern: Last, F. or F. Last or Last F
        self.author_pattern = re.compile(
            r'([A-Z][a-zàáâãäåæçèéêëìíîïñòóôõöøùúûüý\-\']+(?:\s+[A-Z]\.?)+|'
            r'[A-Z]\.\s*[A-Z][a-zàáâãäåæçèéêëìíîïñòóôõöøùúûüý\-\']+)'
        )
        
        # Year pattern - captures full 4-digit year
        self.year_pattern = re.compile(r'\b((?:19|20)\d{2})\b')
        
        # DOI pattern
        self.doi_pattern = re.compile(r'10\.\d{4,}/[^\s\]>]+')
        
        # arXiv pattern
        self.arxiv_pattern = re.compile(r'arXiv[:\s]*(\d{4}\.\d{4,5}(?:v\d+)?)', re.IGNORECASE)
    
    def is_available(self) -> bool:
        """Check if fallback parser can be used"""
        return self.available
    
    def extract_references(self, pdf_path: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract references from PDF using PyMuPDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of parsed references, or None if extraction fails
        """
        if not self.available:
            logger.error("PyMuPDF not installed. Install with: pip install PyMuPDF")
            return None
        
        if not Path(pdf_path).exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None
        
        try:
            # Open PDF
            doc = fitz.open(pdf_path)
            full_text = ""
            
            # Extract text from all pages
            for page in doc:
                full_text += page.get_text() + "\n"
            
            doc.close()
            
            # Find reference section
            ref_text = self._extract_reference_section(full_text)
            if not ref_text:
                logger.warning("Could not locate reference section in PDF")
                return None
            
            # Parse individual references
            references = self._parse_references(ref_text)
            
            if references:
                logger.info(f"[FALLBACK] Extracted {len(references)} references using PyMuPDF")
            
            return references
            
        except Exception as e:
            logger.error(f"Fallback parser failed: {e}")
            return None
    
    def _extract_reference_section(self, text: str) -> Optional[str]:
        """Find and extract the references section from document text"""
        
        # Try each reference section pattern
        for pattern in self.ref_section_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Get everything after "References" heading
                ref_start = match.end()
                ref_text = text[ref_start:]
                
                # Try to find where references end (next major section)
                end_patterns = [
                    r'\n\s*(?:Appendix|Acknowledgment|Supplementary)',
                    r'\n\s*A\.\s+[A-Z]',  # Appendix A.
                ]
                
                for end_pattern in end_patterns:
                    end_match = re.search(end_pattern, ref_text, re.IGNORECASE)
                    if end_match:
                        ref_text = ref_text[:end_match.start()]
                        break
                
                return ref_text.strip()
        
        return None
    
    def _parse_references(self, ref_text: str) -> List[Dict[str, Any]]:
        """Parse individual references from reference section text"""
        references = []
        
        # Split by reference numbers [1], [2], etc. or 1., 2., etc.
        # Pattern matches: [1] or (1) or 1. at start of line
        split_pattern = re.compile(r'\n\s*(?:[\[\(]\d+[\]\)]|\d+\.)\s+')
        
        # First entry might not have number
        entries = split_pattern.split(ref_text)
        
        for entry in entries:
            entry = entry.strip()
            if not entry or len(entry) < 20:  # Skip too short entries
                continue
            
            # Clean up the entry (remove line breaks within entry)
            entry = re.sub(r'\s*\n\s*', ' ', entry)
            entry = re.sub(r'\s+', ' ', entry)
            
            parsed = self._parse_single_reference(entry)
            if parsed:
                references.append(parsed)
        
        return references
    
    def _parse_single_reference(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Parse a single reference entry into structured data"""
        
        if not raw_text or len(raw_text) < 15:
            return None
        
        result = {
            'raw_text': raw_text,
            'title': '',
            'authors': [],
            'venue': '',
            'year': None,
            'volume': '',
            'issue': '',
            'pages': '',
            'doi': '',
            'isbn': '',
            'url': '',
            'confidence_indicators': {'parser': 'fallback_pymupdf'}
        }
        
        # Extract DOI
        doi_match = self.doi_pattern.search(raw_text)
        if doi_match:
            result['doi'] = doi_match.group(0).rstrip('.,;')
        
        # Extract arXiv ID
        arxiv_match = self.arxiv_pattern.search(raw_text)
        if arxiv_match:
            result['url'] = f"https://arxiv.org/abs/{arxiv_match.group(1)}"
        
        # Extract year
        year_matches = self.year_pattern.findall(raw_text)
        if year_matches:
            # Usually the publication year is the first or second year mentioned
            for y in year_matches:
                year = int(y)
                if 1900 <= year <= 2030:
                    result['year'] = year
                    break
        
        # Extract title - usually the longest segment in quotes or after authors
        # Try quoted title first
        quoted = re.search(r'"([^"]{20,})"', raw_text)
        if quoted:
            result['title'] = quoted.group(1).strip()
        else:
            # Title is often after authors (ends with period) and before venue
            # Look for text between first period and common venue indicators
            parts = raw_text.split('.')
            if len(parts) >= 2:
                # Skip author part (first segment), title is usually second
                potential_title = parts[1].strip() if len(parts[1]) > 15 else ''
                if potential_title:
                    result['title'] = potential_title
        
        # If still no title, use first substantial segment
        if not result['title']:
            # Remove author-like prefix and take rest as title
            clean = re.sub(r'^[^.]+\.', '', raw_text).strip()
            if clean:
                # Take up to first venue indicator
                for indicator in [' In ', ' Proc', ' IEEE', ' ACM', ' Springer', ' pages', ', vol']:
                    idx = clean.find(indicator)
                    if idx > 15:
                        result['title'] = clean[:idx].strip().rstrip('.')
                        break
                if not result['title'] and len(clean) > 15:
                    result['title'] = clean[:min(200, len(clean))].strip()
        
        # Extract authors (before the title/first period usually)
        author_section = raw_text.split('.')[0] if '.' in raw_text else raw_text[:100]
        
        # Look for "and" separated names
        if ' and ' in author_section:
            # Split by 'and' and ','
            author_parts = re.split(r',\s*|\s+and\s+', author_section)
            for part in author_parts:
                part = part.strip()
                if len(part) > 2 and len(part) < 50:
                    # Looks like a name
                    if re.search(r'[A-Z]', part):
                        result['authors'].append(part)
        
        # Extract pages
        pages_match = re.search(r'(?:pages?|pp\.?)\s*(\d+[-–]\d+)', raw_text, re.IGNORECASE)
        if pages_match:
            result['pages'] = pages_match.group(1)
        
        return result
    
    def parse_citation_string(self, citation_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single citation string (for --verify mode).
        Uses the same parsing logic as PDF extraction.
        """
        if not citation_text or len(citation_text) < 15:
            return None
        
        return self._parse_single_reference(citation_text.strip())


# Singleton instance
_fallback_parser = None

def get_fallback_parser() -> FallbackReferenceParser:
    """Get or create the fallback parser instance"""
    global _fallback_parser
    if _fallback_parser is None:
        _fallback_parser = FallbackReferenceParser()
    return _fallback_parser
