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


import requests
import time
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from urllib.parse import quote
import re

logger = logging.getLogger(__name__)

class ArXivClient:
    """
    Client for interacting with ArXiv using their official API
    """
    
    def __init__(self):
        """Initialize ArXiv client"""
        self.base_url = "http://export.arxiv.org/api/query"
        self.timeout = 10
        self.max_retries = 2
        self.retry_delay = 1
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RefCheck/1.0 (Academic Reference Verification)'
        })
    
    def search_paper(self, 
                    title: str = None, 
                    authors: List[str] = None, 
                    year: int = None,
                    venue: str = None,
                    limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search ArXiv for papers
        
        Args:
            title: Paper title to search for
            authors: List of author names
            year: Publication year
            venue: Publication venue (not used for ArXiv but kept for compatibility)
            limit: Maximum number of results
            
        Returns:
            List of matching papers from ArXiv
        """
        if not title and not authors:
            return []
        
        # Build ArXiv search query
        query_parts = []
        
        if title:
            # Clean title for ArXiv search
            clean_title = self._clean_title_for_search(title)
            query_parts.append(f'ti:"{clean_title}"')
        
        if authors:
            # Add author searches
            for author in authors[:2]:  # Limit to first 2 authors to avoid overly restrictive queries
                clean_author = self._clean_author_for_search(author)
                if clean_author:
                    query_parts.append(f'au:"{clean_author}"')
        
        if not query_parts:
            return []
        
        # Combine query parts with OR for broader search
        if len(query_parts) > 1:
            search_query = f"({' OR '.join(query_parts)})"
        else:
            search_query = query_parts[0]
        
        params = {
            'search_query': search_query,
            'start': 0,
            'max_results': min(limit, 50),  # ArXiv recommends max 50
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }
        
        try:
            logger.debug(f"Searching ArXiv for: {search_query}")
            
            # Add retry logic
            for attempt in range(self.max_retries + 1):
                try:
                    response = self.session.get(self.base_url, params=params, timeout=self.timeout)
                    response.raise_for_status()
                    break
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if attempt < self.max_retries:
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.warning(f"ArXiv request timeout/error (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"ArXiv request failed after {self.max_retries + 1} attempts: {e}")
                        return []
                except requests.exceptions.RequestException as e:
                    logger.error(f"ArXiv request error: {e}")
                    return []
            
            results = self._parse_arxiv_response(response.text)
            
            # Filter by year if specified
            if year:
                results = [r for r in results if r.get('year') == year]
            
            logger.info(f"ArXiv search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Unexpected error in ArXiv search: {e}")
            return []
    
    def _clean_title_for_search(self, title: str) -> str:
        """Clean title for ArXiv search"""
        # Remove common punctuation that might interfere with search
        clean = re.sub(r'[^\w\s-]', ' ', title)
        # Normalize whitespace
        clean = ' '.join(clean.split())
        return clean.strip()
    
    def _clean_author_for_search(self, author: str) -> str:
        """Clean author name for ArXiv search"""
        # Remove common prefixes/suffixes
        clean = re.sub(r'\b(Dr|Prof|Professor)\b\.?', '', author, flags=re.IGNORECASE)
        # Normalize whitespace
        clean = ' '.join(clean.split())
        return clean.strip()
    
    def _parse_arxiv_response(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Parse ArXiv API XML response
        
        Args:
            xml_content: XML response from ArXiv API
            
        Returns:
            List of parsed paper dictionaries
        """
        results = []
        
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Define namespaces
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            # Find all entry elements
            entries = root.findall('atom:entry', namespaces)
            
            for entry in entries:
                paper = self._parse_arxiv_entry(entry, namespaces)
                if paper:
                    results.append(paper)
            
            return results
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse ArXiv XML response: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing ArXiv response: {e}")
            return []
    
    def _parse_arxiv_entry(self, entry: ET.Element, namespaces: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Parse a single ArXiv entry
        
        Args:
            entry: XML entry element
            namespaces: XML namespaces
            
        Returns:
            Parsed paper dictionary or None
        """
        try:
            # Extract ID and ArXiv identifier
            arxiv_id = entry.find('atom:id', namespaces)
            arxiv_id = arxiv_id.text if arxiv_id is not None else ''
            
            # Extract ArXiv ID from URL
            arxiv_match = re.search(r'arxiv\.org/abs/(.+)', arxiv_id)
            arxiv_paper_id = arxiv_match.group(1) if arxiv_match else ''
            
            # Extract title
            title_elem = entry.find('atom:title', namespaces)
            title = title_elem.text.strip() if title_elem is not None else ''
            
            # Extract authors
            authors = []
            for author_elem in entry.findall('atom:author', namespaces):
                name_elem = author_elem.find('atom:name', namespaces)
                if name_elem is not None:
                    authors.append(name_elem.text.strip())
            
            # Extract publication date
            published_elem = entry.find('atom:published', namespaces)
            published = published_elem.text if published_elem is not None else ''
            
            # Extract year from published date
            year = None
            if published:
                year_match = re.search(r'(\d{4})', published)
                if year_match:
                    year = int(year_match.group(1))
            
            # Extract abstract
            summary_elem = entry.find('atom:summary', namespaces)
            abstract = summary_elem.text.strip() if summary_elem is not None else ''
            
            # Extract categories (subjects)
            categories = []
            for category_elem in entry.findall('atom:category', namespaces):
                term = category_elem.get('term', '')
                if term:
                    categories.append(term)
            
            # Extract DOI if available
            doi = ''
            for link_elem in entry.findall('atom:link', namespaces):
                if link_elem.get('title') == 'doi':
                    doi = link_elem.get('href', '')
                    break
            
            # Extract journal reference if available
            journal_ref = ''
            journal_elem = entry.find('arxiv:journal_ref', namespaces)
            if journal_elem is not None:
                journal_ref = journal_elem.text.strip()
            
            # Only return if we have at least a title
            if not title:
                return None
            
            return {
                'title': title,
                'authors': authors,
                'year': year,
                'venue': 'ArXiv',  # ArXiv is the venue
                'journal': journal_ref if journal_ref else 'ArXiv',
                'abstract': abstract,
                'doi': doi,
                'url': f"https://arxiv.org/abs/{arxiv_paper_id}",
                'source': 'ArXiv',
                'arxiv_id': arxiv_paper_id,
                'categories': categories,
                'published_date': published
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse ArXiv entry: {e}")
            return None
    
    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Verify a reference using ArXiv
        
        Args:
            reference: Reference to verify
            
        Returns:
            List of matching papers
        """
        title = reference.get('title', '')
        authors = reference.get('authors', [])
        year = reference.get('year')
        
        return self.search_paper(title=title, authors=authors, year=year)
    
    def is_available(self) -> bool:
        """
        Check if ArXiv service is available
        
        Returns:
            True if service is available, False otherwise
        """
        try:
            # Simple test query
            params = {
                'search_query': 'ti:"test"',
                'max_results': 1
            }
            response = self.session.get(self.base_url, params=params, timeout=5)
            return response.status_code == 200
        except Exception:
            return False