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
from typing import Dict, List, Optional, Any
from urllib.parse import quote

logger = logging.getLogger(__name__)

class CrossRefClient:
    """
    Client for interacting with CrossRef DOI database
    """
    
    def __init__(self, email: str = "your-email@example.com"):
        """
        Initialize CrossRef client
        
        Args:
            email: Contact email for polite access (required by CrossRef)
        """
        self.base_url = "https://api.crossref.org/works"
        self.timeout = 30
        self.email = email
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'RefCheck/1.0 (Academic Reference Verification; mailto:{email})'
        })
    
    def search_paper(self, 
                    title: str = None, 
                    authors: List[str] = None, 
                    year: int = None,
                    venue: str = None,
                    doi: str = None,
                    limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search CrossRef for papers
        
        Args:
            title: Paper title to search for
            authors: List of author names
            year: Publication year
            venue: Publication venue
            doi: DOI to look up directly
            limit: Maximum number of results
            
        Returns:
            List of matching papers from CrossRef
        """
        # If DOI provided, do direct lookup
        if doi:
            return self._lookup_by_doi(doi)
        
        if not title and not authors:
            return []
        
        # Build search query
        query_parts = []
        if title:
            query_parts.append(f'"{title}"')
        if authors:
            # Use first author for better results
            query_parts.append(f'author:"{authors[0]}"')
        
        query = ' '.join(query_parts)
        
        params = {
            'query': query,
            'rows': min(limit, 100),  # CrossRef max is 1000, but we'll be conservative
            'sort': 'relevance',
            'order': 'desc'
        }
        
        # Add filters if provided
        if year:
            params['filter'] = f'from-pub-date:{year},until-pub-date:{year}'
        
        try:
            logger.debug(f"Searching CrossRef for: {query}")
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if 'message' in data and 'items' in data['message']:
                for item in data['message']['items']:
                    paper = self._parse_crossref_paper(item)
                    if paper:
                        results.append(paper)
            
            logger.info(f"CrossRef search returned {len(results)} results")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"CrossRef search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in CrossRef search: {e}")
            return []
    
    def _lookup_by_doi(self, doi: str) -> List[Dict[str, Any]]:
        """
        Look up paper by DOI directly
        
        Args:
            doi: DOI to look up
            
        Returns:
            List containing the paper if found
        """
        try:
            # Clean DOI
            clean_doi = doi.replace('https://doi.org/', '').replace('http://dx.doi.org/', '')
            
            url = f"{self.base_url}/{quote(clean_doi)}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            if 'message' in data:
                paper = self._parse_crossref_paper(data['message'])
                return [paper] if paper else []
            
            return []
            
        except Exception as e:
            logger.warning(f"CrossRef DOI lookup failed for {doi}: {e}")
            return []
    
    def _parse_crossref_paper(self, item: Dict) -> Optional[Dict[str, Any]]:
        """
        Parse CrossRef paper information into standard format
        
        Args:
            item: Raw paper info from CrossRef API
            
        Returns:
            Standardized paper dictionary or None
        """
        try:
            # Extract title
            title = ''
            titles = item.get('title', [])
            if titles and isinstance(titles, list):
                title = titles[0]
            
            # Extract authors
            authors = []
            for author in item.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                if given and family:
                    authors.append(f"{given} {family}")
                elif family:
                    authors.append(family)
                elif given:
                    authors.append(given)
            
            # Extract venue
            venue = ''
            container_titles = item.get('container-title', [])
            if container_titles and isinstance(container_titles, list):
                venue = container_titles[0]
            
            # Extract year
            year = None
            # Try different date fields
            for date_field in ['published-print', 'published-online', 'created']:
                if date_field in item:
                    date_parts = item[date_field].get('date-parts', [])
                    if date_parts and len(date_parts[0]) > 0:
                        try:
                            year = int(date_parts[0][0])
                            break
                        except (ValueError, TypeError, IndexError):
                            continue
            
            # Extract DOI
            doi = item.get('DOI', '')
            
            # Extract URL
            url = item.get('URL', '')
            if not url and doi:
                url = f"https://doi.org/{doi}"
            
            # Extract additional metadata
            publisher = item.get('publisher', '')
            citation_count = item.get('is-referenced-by-count', 0)
            
            # Only return if we have at least a title
            if not title:
                return None
            
            return {
                'title': title,
                'authors': authors,
                'venue': venue,
                'year': year,
                'doi': doi,
                'url': url,
                'publisher': publisher,
                'citation_count': citation_count,
                'source': 'CrossRef',
                'type': item.get('type', ''),
                'subject': item.get('subject', [])
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse CrossRef paper: {e}")
            return None
    
    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Verify a reference using CrossRef
        
        Args:
            reference: Reference to verify
            
        Returns:
            List of matching papers
        """
        title = reference.get('title', '')
        authors = reference.get('authors', [])
        year = reference.get('year')
        venue = reference.get('venue', '')
        doi = reference.get('doi', '')
        
        return self.search_paper(title=title, authors=authors, year=year, venue=venue, doi=doi)
    
    def is_available(self) -> bool:
        """
        Check if CrossRef service is available
        
        Returns:
            True if service is available, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}?query=test&rows=1", timeout=10)
            return response.status_code == 200
        except Exception:
            return False