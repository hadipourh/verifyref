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

from config import SEMANTIC_SCHOLAR_CONFIG

logger = logging.getLogger(__name__)

class SemanticScholarClient:
    """
    Client for interacting with Semantic Scholar API to verify academic references
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Semantic Scholar client
        
        Args:
            api_key: Optional API key for higher rate limits
        """
        self.base_url = SEMANTIC_SCHOLAR_CONFIG["base_url"]
        self.api_key = api_key or SEMANTIC_SCHOLAR_CONFIG["api_key"]
        self.timeout = SEMANTIC_SCHOLAR_CONFIG["timeout"]
        self.max_retries = SEMANTIC_SCHOLAR_CONFIG["max_retries"]
        self.rate_limit_delay = SEMANTIC_SCHOLAR_CONFIG["rate_limit_delay"]
        
        # Setup session with headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RefCheck/1.0 (https://github.com/your-repo/refcheck)'
        })
        
        if self.api_key:
            self.session.headers.update({
                'x-api-key': self.api_key
            })
    
    def is_available(self) -> bool:
        """
        Check if Semantic Scholar service is available
        
        Returns:
            True if service is available, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/paper/search?query=test&limit=1", timeout=10)
            # Consider 200 (OK) and 429 (rate limited) as "available"
            # Rate limiting means the service is working, just busy
            return response.status_code in [200, 429]
        except Exception:
            return False
    
    def search_paper(self, 
                    title: str = None, 
                    authors: List[str] = None, 
                    year: int = None,
                    venue: str = None,
                    limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for papers using Semantic Scholar API
        
        Args:
            title: Paper title to search for
            authors: List of author names
            year: Publication year
            venue: Publication venue
            limit: Maximum number of results to return
            
        Returns:
            List of paper dictionaries from Semantic Scholar
        """
        if not title and not authors:
            logger.warning("No title or authors provided for search")
            return []
        
        # Build search query
        query_parts = []
        
        if title:
            # Clean and quote title for search
            clean_title = self._clean_search_term(title)
            if clean_title:
                query_parts.append(f'title:"{clean_title}"')
        
        if authors:
            # Add author search terms
            for author in authors[:3]:  # Limit to first 3 authors
                clean_author = self._clean_search_term(author)
                if clean_author:
                    query_parts.append(f'author:"{clean_author}"')
        
        if year:
            # Add year constraint with some tolerance
            year_range = f"year:{year-1}-{year+1}"
            query_parts.append(year_range)
        
        if not query_parts:
            logger.warning("No valid search terms could be constructed")
            return []
        
        query = ' '.join(query_parts)
        
        try:
            return self._execute_search(query, limit)
        except Exception as e:
            logger.error(f"Error searching Semantic Scholar: {e}")
            return []
    
    def search_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Search for a paper by DOI
        
        Args:
            doi: Digital Object Identifier
            
        Returns:
            Paper dictionary or None if not found
        """
        if not doi:
            return None
        
        # Clean DOI
        clean_doi = doi.strip()
        if clean_doi.startswith('http'):
            clean_doi = clean_doi.split('/')[-2] + '/' + clean_doi.split('/')[-1]
        
        try:
            url = f"{self.base_url}/paper/DOI:{clean_doi}"
            response = self._make_request(url)
            
            if response and response.status_code == 200:
                return response.json()
            else:
                logger.info(f"Paper not found for DOI: {doi}")
                return None
                
        except Exception as e:
            logger.error(f"Error searching by DOI {doi}: {e}")
            return None
    
    def get_paper_details(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific paper
        
        Args:
            paper_id: Semantic Scholar paper ID
            
        Returns:
            Detailed paper information or None
        """
        try:
            fields = [
                'paperId', 'title', 'authors', 'year', 'venue', 'journal',
                'citationCount', 'referenceCount', 'doi', 'url', 'abstract',
                'publicationDate', 'publicationVenue'
            ]
            
            url = f"{self.base_url}/paper/{paper_id}"
            params = {'fields': ','.join(fields)}
            
            response = self._make_request(url, params)
            
            if response and response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting paper details for {paper_id}: {e}")
            return None
    
    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Verify a reference by searching Semantic Scholar
        
        Args:
            reference: Reference dictionary with title, authors, etc.
            
        Returns:
            List of potential matching papers
        """
        # First try DOI search if available
        if reference.get('doi'):
            doi_result = self.search_by_doi(reference['doi'])
            if doi_result:
                return [doi_result]
        
        # Fall back to general search
        return self.search_paper(
            title=reference.get('title'),
            authors=reference.get('authors'),
            year=reference.get('year'),
            venue=reference.get('venue'),
            limit=5  # Fewer results for verification
        )
    
    def batch_verify_references(self, references: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Verify multiple references with rate limiting
        
        Args:
            references: List of reference dictionaries
            
        Returns:
            List of search results for each reference
        """
        results = []
        
        for i, reference in enumerate(references):
            try:
                # Rate limiting
                if i > 0:
                    time.sleep(self.rate_limit_delay)
                
                search_results = self.verify_reference(reference)
                results.append(search_results)
                
                logger.info(f"Verified reference {i+1}/{len(references)}: {len(search_results)} results")
                
            except Exception as e:
                logger.error(f"Error verifying reference {i+1}: {e}")
                results.append([])  # Empty results for failed searches
        
        return results
    
    def _execute_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Execute search query against Semantic Scholar API"""
        try:
            url = f"{self.base_url}/paper/search"
            params = {
                'query': query,
                'limit': min(limit, 100),  # API limit
                'fields': 'paperId,title,authors,year,venue,citationCount,doi,url'  # Simplified fields list
            }
            
            response = self._make_request(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                papers = data.get('data', [])
                logger.info(f"Search returned {len(papers)} results")
                return papers
            elif response and response.status_code == 429:
                logger.warning("Search failed: Rate limiting persists after retries")
                return []
            elif response:
                logger.warning(f"Search failed with status: {response.status_code}")
                return []
            else:
                logger.warning("Search failed: No response from server")
                return []
                
        except Exception as e:
            logger.error(f"Error executing search: {e}")
            return []
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """
        Make HTTP request with retries and error handling
        
        Args:
            url: Request URL
            params: Query parameters
            
        Returns:
            Response object or None if failed
        """
        max_rate_limit_retries = 5  # Separate limit for rate limiting
        rate_limit_retries = 0
        attempt = 0
        
        while attempt < self.max_retries:
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )
                
                # Handle rate limiting with separate retry counter
                if response.status_code == 429:
                    if rate_limit_retries < max_rate_limit_retries:
                        retry_after = int(response.headers.get('Retry-After', self.rate_limit_delay * 2))
                        logger.warning(f"Rate limited, waiting {retry_after} seconds (rate limit retry {rate_limit_retries + 1}/{max_rate_limit_retries})")
                        time.sleep(retry_after)
                        rate_limit_retries += 1
                        # Don't increment attempt counter for rate limits
                        continue
                    else:
                        logger.warning(f"Exceeded maximum rate limit retries ({max_rate_limit_retries})")
                        return response  # Return 429 response so caller can handle it
                
                # Return response for any other status code
                return response
                
            except requests.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                
            attempt += 1
                
        logger.error(f"All {self.max_retries} request attempts failed")
        return None
    
    def _clean_search_term(self, term: str) -> str:
        """
        Clean search term for API query
        
        Args:
            term: Raw search term
            
        Returns:
            Cleaned search term
        """
        if not term:
            return ''
        
        # Remove special characters that might interfere with search
        import re
        cleaned = re.sub(r'[^\w\s\-\.]', ' ', term)
        
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Truncate if too long
        if len(cleaned) > 200:
            cleaned = cleaned[:200].rsplit(' ', 1)[0]
        
        return cleaned.strip()
    
    def get_api_status(self) -> Dict[str, Any]:
        """
        Check API status and rate limit information
        
        Returns:
            Dictionary with API status information
        """
        try:
            # Make a simple request to check status
            url = f"{self.base_url}/paper/search"
            params = {'query': 'test', 'limit': 1}
            
            response = self._make_request(url, params)
            
            if response:
                status = {
                    'available': response.status_code == 200,
                    'status_code': response.status_code,
                    'has_api_key': bool(self.api_key),
                    'rate_limit_remaining': response.headers.get('X-RateLimit-Remaining'),
                    'rate_limit_reset': response.headers.get('X-RateLimit-Reset')
                }
            else:
                status = {
                    'available': False,
                    'status_code': None,
                    'has_api_key': bool(self.api_key),
                    'error': 'No response from API'
                }
            
            return status
            
        except Exception as e:
            return {
                'available': False,
                'error': str(e),
                'has_api_key': bool(self.api_key)
            }