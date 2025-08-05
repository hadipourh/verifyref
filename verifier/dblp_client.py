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

class DBLPClient:
    """
    Client for interacting with DBLP Computer Science Bibliography
    """
    
    def __init__(self):
        """Initialize DBLP client"""
        self.base_url = "https://dblp.org/search/publ/api"
        self.timeout = 15  # Reduced from 30 to 15 seconds
        self.max_retries = 2  # Add retry limit
        self.retry_delay = 1  # Delay between retries
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
        Search DBLP for papers
        
        Args:
            title: Paper title to search for
            authors: List of author names
            year: Publication year
            venue: Publication venue
            limit: Maximum number of results
            
        Returns:
            List of matching papers from DBLP
        """
        if not title and not authors:
            return []
        
        # Build search query - DBLP works better with simpler, focused queries
        query_parts = []
        
        # Priority 1: Title is most important
        if title:
            # Use title as the primary search term
            query_parts.append(f'"{title}"')  # Quote the title for exact phrase matching
        
        # Priority 2: Add main author (first author usually)
        if authors and len(authors) > 0:
            # Only use first author to avoid overly complex queries
            main_author = authors[0]
            # Extract last name if possible for better matching
            author_parts = main_author.split()
            if len(author_parts) > 1:
                query_parts.append(author_parts[-1])  # Last name
            else:
                query_parts.append(main_author)
        
        # Priority 3: Add year if available (DBLP often indexes by year)
        if year:
            query_parts.append(str(year))
        
        # Don't include venue in DBLP queries - it often makes them too restrictive
        # DBLP has its own venue normalization that might not match extracted venue names
        
        query = ' '.join(query_parts)
        
        params = {
            'q': query,
            'format': 'json',
            'h': min(limit, 100)  # DBLP max is 100
        }
        
        try:
            logger.debug(f"Searching DBLP for: {query}")
            
            # Add retry logic with exponential backoff
            for attempt in range(self.max_retries + 1):
                try:
                    response = self.session.get(self.base_url, params=params, timeout=self.timeout)
                    response.raise_for_status()
                    break  # Success, exit retry loop
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if attempt < self.max_retries:
                        wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"DBLP request timeout/error (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"DBLP request failed after {self.max_retries + 1} attempts: {e}")
                        return []
                except requests.exceptions.RequestException as e:
                    logger.error(f"DBLP request error: {e}")
                    return []
            
            data = response.json()
            results = []
            
            if 'result' in data and 'hits' in data['result']:
                hits = data['result']['hits']
                if isinstance(hits, dict) and 'hit' in hits:
                    hit_list = hits['hit']
                    if not isinstance(hit_list, list):
                        hit_list = [hit_list]
                    
                    for hit in hit_list:
                        if 'info' in hit:
                            paper = self._parse_dblp_paper(hit['info'])
                            if paper:
                                results.append(paper)
            
            logger.info(f"DBLP search returned {len(results)} results")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"DBLP search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in DBLP search: {e}")
            return []
    
    def _parse_dblp_paper(self, paper_info: Dict) -> Optional[Dict[str, Any]]:
        """
        Parse DBLP paper information into standard format
        
        Args:
            paper_info: Raw paper info from DBLP API
            
        Returns:
            Standardized paper dictionary or None
        """
        try:
            # Extract title
            title = paper_info.get('title', '')
            if isinstance(title, dict):
                title = title.get('text', '')
            
            # Extract authors
            authors = []
            author_data = paper_info.get('authors', {})
            if author_data:
                author_list = author_data.get('author', [])
                if not isinstance(author_list, list):
                    author_list = [author_list]
                
                for author in author_list:
                    if isinstance(author, dict):
                        author_name = author.get('text', '')
                    else:
                        author_name = str(author)
                    
                    if author_name:
                        authors.append(author_name)
            
            # Extract venue
            venue = paper_info.get('venue', '')
            if isinstance(venue, dict):
                venue = venue.get('text', '')
            
            # Extract year
            year = None
            year_data = paper_info.get('year')
            if year_data:
                try:
                    year = int(year_data)
                except (ValueError, TypeError):
                    pass
            
            # Extract DOI
            doi = paper_info.get('doi', '')
            if isinstance(doi, dict):
                doi = doi.get('text', '')
            
            # Extract URL
            url = paper_info.get('url', '')
            if isinstance(url, dict):
                url = url.get('text', '')
            
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
                'source': 'DBLP',
                'type': paper_info.get('type', ''),
                'key': paper_info.get('key', ''),
                'pages': paper_info.get('pages', ''),
                'volume': paper_info.get('volume', ''),
                'number': paper_info.get('number', ''),
                'series': paper_info.get('series', ''),
                'publisher': paper_info.get('publisher', ''),
                'address': paper_info.get('address', '')
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse DBLP paper: {e}")
            return None
    
    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Verify a reference using DBLP
        
        Args:
            reference: Reference to verify
            
        Returns:
            List of matching papers
        """
        title = reference.get('title', '')
        authors = reference.get('authors', [])
        year = reference.get('year')
        venue = reference.get('venue', '')
        
        return self.search_paper(title=title, authors=authors, year=year, venue=venue)
    
    def is_available(self) -> bool:
        """
        Check if DBLP service is available
        
        Returns:
            True if service is available, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}?q=test&format=json&h=1", timeout=8)  # Reduced timeout
            return response.status_code == 200
        except Exception:
            return False