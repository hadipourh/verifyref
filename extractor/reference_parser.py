"""
VerifyRef - High-performance academic reference verification tool
Copyright (C) 2025 Hosein Hadipour <hsn.hadipour@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from difflib import SequenceMatcher

from utils.helpers import normalize_text, extract_year_from_text

logger = logging.getLogger(__name__)

class ReferenceParser:
    """
    Parser for cleaning and normalizing reference data extracted from GROBID
    """
    
    def __init__(self):
        """Initialize the reference parser"""
        self.author_patterns = [
            r'([A-Z][a-z]+,?\s+[A-Z]\.?\s*)+',  # Last, F. or Last F.
            r'([A-Z]\.?\s+[A-Z][a-z]+,?\s*)+',  # F. Last or F Last
        ]
        
        self.venue_patterns = [
            r'in\s+(.+?)(?:\.|,|$)',  # "in Journal Name"
            r'(?:Journal|Proc\.|Proceedings)\s+(.+?)(?:\.|,|$)',  # Journal/Proc patterns
        ]
        
    def parse_references(self, raw_references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse and clean a list of raw references from GROBID
        
        Args:
            raw_references: List of raw reference dictionaries from GROBID
            
        Returns:
            List of cleaned and normalized references
        """
        parsed_references = []
        
        for i, ref in enumerate(raw_references):
            try:
                parsed_ref = self.parse_single_reference(ref, index=i)
                if parsed_ref:
                    parsed_references.append(parsed_ref)
            except Exception as e:
                logger.error(f"Error parsing reference {i}: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(parsed_references)} out of {len(raw_references)} references")
        return parsed_references
    
    def parse_single_reference(self, reference: Dict[str, Any], index: int = 0) -> Optional[Dict[str, Any]]:
        """
        Parse and clean a single reference
        
        Args:
            reference: Raw reference dictionary from GROBID
            index: Reference index for tracking
            
        Returns:
            Cleaned reference dictionary or None if parsing fails
        """
        try:
            parsed = {
                'index': index,
                'original_data': reference.copy(),
                'title': self._clean_title(reference.get('title', '')),
                'authors': self._clean_authors(reference.get('authors', [])),
                'venue': self._extract_best_venue(reference),
                'year': self._extract_year(reference),
                'volume': self._clean_field(reference.get('volume', '')),
                'issue': self._clean_field(reference.get('issue', '')),
                'pages': self._clean_pages(reference.get('pages', '')),
                'doi': self._clean_doi(reference.get('doi', '')),
                'isbn': self._clean_field(reference.get('isbn', '')),
                'url': self._clean_url(reference.get('url', '')),
                'confidence_score': 0.0,
                'parsing_notes': []
            }
            
            # Calculate confidence score based on completeness
            parsed['confidence_score'] = self._calculate_confidence(parsed)
            
            # Add parsing notes
            if not parsed['title']:
                parsed['parsing_notes'].append('No title found')
            if not parsed['authors']:
                parsed['parsing_notes'].append('No authors found')
            if not parsed['year']:
                parsed['parsing_notes'].append('No publication year found')
            
            # Only return references with minimum required fields
            if parsed['title'] and (parsed['authors'] or parsed['venue']):
                return parsed
            else:
                logger.warning(f"Reference {index} lacks minimum required fields")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing reference {index}: {e}")
            return None
    
    def _clean_title(self, title: str) -> str:
        """Clean and normalize title text while preserving important punctuation"""
        if not title:
            return ''
        
        # Remove LaTeX commands and mathematical notation
        title = re.sub(r'\$\\textnormal\\textsc\{([^}]*)\}\$', r'\1', title)  # $\textnormal\textsc{WORD}$ -> WORD
        title = re.sub(r'\$\\textsc\{([^}]*)\}\$', r'\1', title)             # $\textsc{WORD}$ -> WORD
        title = re.sub(r'\$\\textnormal\{([^}]*)\}\$', r'\1', title)         # $\textnormal{WORD}$ -> WORD
        title = re.sub(r'\$\\[a-zA-Z]+\{([^}]*)\}\$', r'\1', title)          # $\textXX{WORD}$ -> WORD
        title = re.sub(r'\$\\[a-zA-Z]+([^$]*)\$', r'\1', title)              # $\textXX...$ -> content
        title = re.sub(r'\$([^$]*)\$', r'\1', title)                         # $...$ -> content
        title = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', title)              # \textsc{WORD} -> WORD
        title = re.sub(r'\\[a-zA-Z]+', '', title)                            # Remove remaining LaTeX commands
        
        # Remove extra whitespace and normalize while preserving hyphens
        title = normalize_text(title, preserve_hyphens=True)
        
        # Remove trailing punctuation that might be artifacts
        title = re.sub(r'[.,:;]+$', '', title)
        
        # Remove common OCR artifacts
        title = re.sub(r'[{}|<>]', '', title)
        
        return title.strip()
    
    def _clean_authors(self, authors: List[str]) -> List[str]:
        """Clean and normalize author names"""
        if not authors:
            return []
        
        cleaned_authors = []
        for author in authors:
            if not author:
                continue
                
            # Remove LaTeX formatting from author names
            author = re.sub(r'\$\\[a-zA-Z]+\{([^}]*)\}\$', r'\1', author)  # $\textsc{WORD}$ -> WORD
            author = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', author)      # \textsc{WORD} -> WORD
            author = re.sub(r'\\[a-zA-Z]+', '', author)                    # Remove remaining LaTeX commands
            
            # Normalize text while preserving hyphens in author names
            author = normalize_text(author, preserve_hyphens=True)
            
            # Remove common artifacts
            author = re.sub(r'[{}|<>]', '', author)
            
            # Handle "et al." cases - but preserve all real authors
            if 'et al' in author.lower():
                cleaned_authors.append('et al.')
                break
            
            # Basic name validation
            if len(author) >= 2 and any(c.isalpha() for c in author):
                cleaned_authors.append(author.strip())
        
        return cleaned_authors
    
    def _clean_venue(self, venue: str) -> str:
        """Clean and normalize venue/journal name while preserving important punctuation"""
        if not venue:
            return ''
        
        # Normalize text while preserving hyphens in venue names
        venue = normalize_text(venue, preserve_hyphens=True)
        
        # Special handling for common academic patterns
        # If we only got "Lecture Notes in Computer Science", try to extract from raw_text
        if venue.lower() == 'lecture notes in computer science':
            # This is a placeholder - we need the full reference context
            return venue
        
        # Prioritize conference/workshop names over series (LNCS, ACM, etc.)
        # Extract primary venue before series information
        venue_parts = re.split(r',\s*', venue)
        if len(venue_parts) > 1:
            # Check if first part looks like a conference
            first_part = venue_parts[0].strip()
            if any(keyword in first_part.lower() for keyword in ['conference', 'workshop', 'symposium', 'congress']):
                venue = first_part
            elif 'lecture notes' in venue.lower() and len(venue_parts) > 1:
                # For LNCS, try to find actual conference name
                for part in venue_parts:
                    part = part.strip()
                    # Look for conference acronyms or explicit conference names
                    if any(keyword in part.lower() for keyword in ['sac', 'asiacrypt', 'crypto', 'eurocrypt', 'conference', 'workshop', 'symposium']):
                        venue = part
                        break
                    # Check if part contains year and conference-like pattern
                    elif re.search(r'\b(20\d{2}|19\d{2})\b', part) and len(part) > 10:
                        venue = part
                        break
        
        # Remove common prefixes/suffixes
        venue = re.sub(r'^(in\s+|proceedings\s+of\s+)', '', venue, flags=re.IGNORECASE)
        venue = re.sub(r'[.,:;]+$', '', venue)
        
        # Remove artifacts
        venue = re.sub(r'[{}|<>]', '', venue)
        
        return venue.strip()
    
    def _extract_best_venue(self, reference: Dict[str, Any]) -> str:
        """Extract the best venue name using both parsed data and raw text"""
        # First try the parsed venue
        parsed_venue = self._clean_venue(reference.get('venue', ''))
        raw_text = reference.get('raw_text', '')
        
        # If we only got generic "Lecture Notes in Computer Science" or similar, 
        # try to extract conference name from raw text
        generic_venues = ['lecture notes in computer science', 'proceedings', 'acm', 'ieee', 'springer']
        
        if (parsed_venue.lower() in generic_venues or 
            any(generic in parsed_venue.lower() for generic in generic_venues)) and raw_text:
            
            # Try to extract conference name from raw text
            extracted_venue = self._extract_venue_from_raw_text(raw_text)
            if extracted_venue:  # Prefer extracted venue over generic ones
                return extracted_venue
        
        return parsed_venue
    
    def _extract_venue_from_raw_text(self, raw_text: str) -> str:
        """Extract venue/conference name from raw reference text"""
        if not raw_text:
            return ''
        
        # Common patterns for conference/journal names in references
        venue_patterns = [
            # "In: Conference Name, Year" pattern
            r'In:\s*([^,]+(?:Conference|Workshop|Symposium|Congress)[^,]*)',
            # "Selected Areas in Cryptography" specific pattern  
            r'Selected\s+Areas\s+in\s+Cryptography[^,]*',
            # "Conference Name, Year" pattern
            r'([A-Z][^,]*(?:Conference|Workshop|Symposium|Congress)[^,]*),\s*\d{4}',
            # Acronym followed by year: "SAC 2012", "CRYPTO 2020", etc.
            r'\b([A-Z]{3,8})\s+(19|20)\d{2}\b',
            # "Advances in Cryptology - CRYPTO" pattern
            r'Advances\s+in\s+Cryptology\s*[-–—]\s*[A-Z]+',
            # Journal patterns
            r'Journal\s+of\s+[^,]+',
            r'IEEE\s+[^,]+',
            r'ACM\s+[^,]+',
        ]
        
        for pattern in venue_patterns:
            matches = re.findall(pattern, raw_text, re.IGNORECASE)
            if matches:
                venue = matches[0] if isinstance(matches[0], str) else matches[0][0]
                venue = venue.strip()
                if len(venue) > 3:  # Reasonable venue name length
                    return venue
        
        return ''
    
    def _extract_year(self, reference: Dict[str, Any]) -> Optional[int]:
        """Extract and validate publication year"""
        # First try the parsed year field
        if reference.get('year'):
            try:
                year = int(reference['year'])
                if 1900 <= year <= 2030:  # Reasonable year range
                    return year
            except (ValueError, TypeError):
                pass
        
        # Try to extract from raw text or other fields
        for field in ['title', 'venue', 'raw_text']:
            if reference.get(field):
                year = extract_year_from_text(reference[field])
                if year:
                    return year
        
        return None
    
    def _clean_pages(self, pages: str) -> str:
        """Clean and normalize page information"""
        if not pages:
            return ''
        
        pages = normalize_text(pages, preserve_hyphens=True)
        
        # Normalize page ranges
        pages = re.sub(r'pp?\.\s*', '', pages, flags=re.IGNORECASE)
        pages = re.sub(r'pages?\s*', '', pages, flags=re.IGNORECASE)
        
        # Normalize separators
        pages = re.sub(r'[-–—]+', '-', pages)
        
        return pages.strip()
    
    def _clean_doi(self, doi: str) -> str:
        """Clean and validate DOI"""
        if not doi:
            return ''
        
        doi = doi.strip()
        
        # Remove URL prefix if present
        doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi)
        
        # Basic DOI format validation
        if re.match(r'10\.\d+/.+', doi):
            return doi
        
        return ''
    
    def _clean_url(self, url: str) -> str:
        """Clean and validate URL"""
        if not url:
            return ''
        
        url = url.strip()
        
        # Basic URL validation
        if re.match(r'https?://.+', url):
            return url
        
        return ''
    
    def _clean_field(self, field: str) -> str:
        """Generic field cleaning"""
        if not field:
            return ''
        
        field = normalize_text(field, preserve_hyphens=True)
        field = re.sub(r'[{}|<>]', '', field)
        
        return field.strip()
    
    def _calculate_confidence(self, parsed_ref: Dict[str, Any]) -> float:
        """
        Calculate confidence score based on reference completeness
        
        Args:
            parsed_ref: Parsed reference dictionary
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.0
        
        # Title (required, high weight)
        if parsed_ref['title']:
            score += 0.4
            if len(parsed_ref['title']) > 10:
                score += 0.1
        
        # Authors (high weight)
        if parsed_ref['authors']:
            score += 0.3
            if len(parsed_ref['authors']) > 1:
                score += 0.1
        
        # Venue (medium weight)
        if parsed_ref['venue']:
            score += 0.2
        
        # Year (medium weight)
        if parsed_ref['year']:
            score += 0.2
        
        # Additional fields (low weight)
        if parsed_ref['doi']:
            score += 0.1
        if parsed_ref['pages']:
            score += 0.05
        if parsed_ref['volume']:
            score += 0.05
        
        return min(1.0, score)  # Cap at 1.0
    
    def merge_similar_references(self, references: List[Dict[str, Any]], 
                               similarity_threshold: float = 0.9) -> List[Dict[str, Any]]:
        """
        Merge references that appear to be duplicates
        
        Args:
            references: List of parsed references
            similarity_threshold: Minimum similarity to consider duplicates
            
        Returns:
            List of references with duplicates merged
        """
        merged_references = []
        processed_indices = set()
        
        for i, ref1 in enumerate(references):
            if i in processed_indices:
                continue
            
            # Find similar references
            similar_refs = [ref1]
            processed_indices.add(i)
            
            for j, ref2 in enumerate(references[i+1:], start=i+1):
                if j in processed_indices:
                    continue
                
                similarity = self._calculate_reference_similarity(ref1, ref2)
                if similarity >= similarity_threshold:
                    similar_refs.append(ref2)
                    processed_indices.add(j)
            
            # Merge similar references
            if len(similar_refs) > 1:
                merged_ref = self._merge_reference_group(similar_refs)
                merged_references.append(merged_ref)
            else:
                merged_references.append(ref1)
        
        logger.info(f"Merged {len(references)} references into {len(merged_references)}")
        return merged_references
    
    def _calculate_reference_similarity(self, ref1: Dict[str, Any], ref2: Dict[str, Any]) -> float:
        """Calculate similarity between two references"""
        title_sim = SequenceMatcher(None, ref1['title'].lower(), ref2['title'].lower()).ratio()
        
        # If titles are very different, probably not the same reference
        if title_sim < 0.6:
            return 0.0
        
        # Compare authors
        author_sim = 0.0
        if ref1['authors'] and ref2['authors']:
            author1_str = ' '.join(ref1['authors']).lower()
            author2_str = ' '.join(ref2['authors']).lower()
            author_sim = SequenceMatcher(None, author1_str, author2_str).ratio()
        
        # Compare years
        year_sim = 1.0 if ref1['year'] == ref2['year'] else 0.0
        
        # Weighted average
        similarity = (title_sim * 0.7 + author_sim * 0.2 + year_sim * 0.1)
        return similarity
    
    def _merge_reference_group(self, references: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge a group of similar references by taking the best data from each"""
        # Start with the reference that has the highest confidence
        base_ref = max(references, key=lambda r: r['confidence_score'])
        merged = base_ref.copy()
        
        # Fill in missing fields from other references
        for ref in references:
            if ref == base_ref:
                continue
            
            for field in ['title', 'venue', 'doi', 'pages', 'volume', 'issue']:
                if not merged[field] and ref[field]:
                    merged[field] = ref[field]
            
            # Merge authors (take the longest list)
            if len(ref['authors']) > len(merged['authors']):
                merged['authors'] = ref['authors']
        
        # Update confidence score
        merged['confidence_score'] = self._calculate_confidence(merged)
        
        return merged