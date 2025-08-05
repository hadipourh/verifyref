"""
OpenAlex API client for academic paper verification.

OpenAlex is a fully open catalog of scholarly papers, authors, venues, and institutions.
It's the successor to Microsoft Academic Graph and provides comprehensive, fast, and free access
to scholarly data without rate limits.

OpenAlex API Documentation: https://docs.openalex.org/
"""

import requests
import logging
import time
from typing import Dict, List, Any, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

class OpenAlexClient:
    """Client for OpenAlex API"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize OpenAlex client
        
        Args:
            config: Configuration dictionary
        """
        if config is None:
            config = {}
            
        self.base_url = config.get("base_url", "https://api.openalex.org")
        self.timeout = config.get("timeout", 30)
        self.per_page = min(config.get("per_page", 25), 200)  # Max 200 per OpenAlex docs
        self.mailto = config.get("mailto", "refcheck@example.com")
        
        # Setup session with headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RefCheck/1.0 (mailto:' + self.mailto + ')',
            'Accept': 'application/json'
        })
        
        logger.info(f"OpenAlex client initialized with base URL: {self.base_url}")
    
    def is_available(self) -> bool:
        """
        Check if OpenAlex API is available
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}/works",
                params={'per-page': 1},
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAlex availability check failed: {e}")
            return False
    
    def search_paper(self, title: str = None, authors: List[str] = None, 
                     year: int = None, venue: str = None, doi: str = None,
                     limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for papers using OpenAlex API
        
        Args:
            title: Paper title to search for
            authors: List of author names
            year: Publication year
            venue: Publication venue
            doi: DOI to search for
            limit: Maximum number of results to return
            
        Returns:
            List of paper dictionaries from OpenAlex
        """
        if doi:
            # Direct DOI search
            return self.search_by_doi(doi)
        
        if not title and not authors:
            logger.warning("No title or authors provided for search")
            return []
        
        # Build search query - use simple search for better compatibility
        search_terms = []
        
        if title:
            # Clean and prepare title for search
            clean_title = self._clean_search_term(title)
            if clean_title:
                search_terms.append(clean_title)
        
        if authors:
            # Add author names to search
            for author in authors[:2]:  # Limit to first 2 authors
                clean_author = self._clean_search_term(author)
                if clean_author:
                    search_terms.append(clean_author)
        
        if not search_terms:
            logger.warning("No valid search terms could be constructed")
            return []
        
        # Use simple search query
        search_query = ' '.join(search_terms)
        
        return self._execute_simple_search(search_query, year, venue, limit)
    
    def _execute_simple_search(self, search_query: str, year: int = None, 
                              venue: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Execute simple search query against OpenAlex API"""
        try:
            url = f"{self.base_url}/works"
            
            params = {
                'search': search_query,
                'per-page': min(limit, self.per_page)
            }
            
            # Add year filter if specified
            if year:
                params['filter'] = f'publication_year:{year-1}|{year}|{year+1}'
            
            logger.debug(f"OpenAlex simple search: {search_query}")
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                # Convert to standardized format
                papers = []
                for work in results:
                    paper = self._convert_work_to_paper(work)
                    if paper:
                        papers.append(paper)
                
                logger.info(f"OpenAlex search returned {len(papers)} results")
                return papers
            else:
                logger.warning(f"OpenAlex search failed with status: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error executing OpenAlex search: {e}")
            return []
    
    def search_by_doi(self, doi: str) -> List[Dict[str, Any]]:
        """
        Search for a paper by DOI
        
        Args:
            doi: Digital Object Identifier
            
        Returns:
            List with single paper dictionary or empty list if not found
        """
        if not doi:
            return []
        
        # Clean DOI
        clean_doi = doi.strip()
        if clean_doi.startswith('http'):
            # Extract DOI from URL
            clean_doi = '/'.join(clean_doi.split('/')[-2:])
        
        try:
            filters = [f'doi:{clean_doi}']
            results = self._execute_search(filters, 1)
            return results
            
        except Exception as e:
            logger.error(f"Error searching by DOI {doi}: {e}")
            return []
    
    def _execute_search(self, filters: List[str], limit: int) -> List[Dict[str, Any]]:
        """Execute search query against OpenAlex API"""
        try:
            url = f"{self.base_url}/works"
            
            # For OpenAlex, use search parameter instead of complex filters for better compatibility
            if len(filters) == 1 and 'title.search:' in filters[0]:
                # Simple title search
                search_term = filters[0].replace('title.search:', '').strip()
                params = {
                    'search': search_term,
                    'per-page': min(limit, self.per_page),
                    'select': 'id,doi,title,display_name,publication_year,publication_date,type,cited_by_count,authorships,primary_location,open_access'
                }
            else:
                # Complex filter search
                filter_string = ','.join(filters)
                params = {
                    'filter': filter_string,
                    'per-page': min(limit, self.per_page),
                    'select': 'id,doi,title,display_name,publication_year,publication_date,type,cited_by_count,authorships,primary_location,open_access'
                }
            
            logger.debug(f"OpenAlex search: {url} with params: {params}")
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                # Convert to standardized format
                papers = []
                for work in results:
                    paper = self._convert_work_to_paper(work)
                    if paper:
                        papers.append(paper)
                
                logger.info(f"OpenAlex search returned {len(papers)} results")
                return papers
            else:
                logger.warning(f"OpenAlex search failed with status: {response.status_code}")
                if response.status_code == 403:
                    logger.warning("OpenAlex 403 error - this might be due to rate limiting or request format")
                return []
                
        except Exception as e:
            logger.error(f"Error executing OpenAlex search: {e}")
            return []
    
    def _convert_work_to_paper(self, work: Dict) -> Optional[Dict[str, Any]]:
        """
        Convert OpenAlex work format to standardized paper format
        
        Args:
            work: OpenAlex work dictionary
            
        Returns:
            Standardized paper dictionary
        """
        try:
            # Extract basic information
            paper = {
                'database': 'OpenAlex',
                'id': work.get('id', '').replace('https://openalex.org/', ''),
                'title': work.get('display_name', ''),
                'doi': work.get('doi', '').replace('https://doi.org/', '') if work.get('doi') else None,
                'year': work.get('publication_year'),
                'publication_date': work.get('publication_date'),
                'type': work.get('type', '').replace('https://openalex.org/types/', ''),
                'citation_count': work.get('cited_by_count', 0),
                'url': work.get('id', ''),
                'open_access': work.get('open_access', {})
            }
            
            # Extract authors
            authors = []
            authorships = work.get('authorships', [])
            for authorship in authorships:
                if authorship and isinstance(authorship, dict):
                    author_info = authorship.get('author', {})
                    if author_info and author_info.get('display_name'):
                        authors.append(author_info['display_name'])
            paper['authors'] = authors
            
            # Extract venue information
            primary_location = work.get('primary_location', {})
            if primary_location:
                source = primary_location.get('source', {})
                if source:
                    paper['venue'] = source.get('display_name', '')
                    paper['journal'] = source.get('display_name', '')
                    paper['publisher'] = source.get('host_organization_name', '')
                
                # Check if it's open access
                if primary_location.get('is_oa'):
                    paper['is_open_access'] = True
                    paper['pdf_url'] = primary_location.get('pdf_url')
            
            return paper
            
        except Exception as e:
            logger.warning(f"Error converting OpenAlex work to paper format: {e}")
            return None
    
    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Verify a reference by searching OpenAlex
        
        Args:
            reference: Reference dictionary with title, authors, etc.
            
        Returns:
            List of matching papers from OpenAlex
        """
        title = reference.get('title', '')
        authors = reference.get('authors', [])
        year = reference.get('year')
        venue = reference.get('venue') or reference.get('journal')
        doi = reference.get('doi')
        
        return self.search_paper(
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            doi=doi,
            limit=10
        )
    
    def _clean_search_term(self, term: str) -> str:
        """
        Clean search term for OpenAlex API query
        
        Args:
            term: Raw search term
            
        Returns:
            Cleaned search term
        """
        if not term:
            return ""
        
        # Remove extra whitespace and normalize
        cleaned = ' '.join(term.strip().split())
        
        # Remove problematic characters for search
        # OpenAlex handles most characters well, but these can cause issues
        problematic_chars = ['[', ']', '{', '}', '(', ')', '"', "'"]
        for char in problematic_chars:
            cleaned = cleaned.replace(char, ' ')
        
        # Normalize whitespace again
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def get_paper_details(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific paper
        
        Args:
            paper_id: OpenAlex work ID
            
        Returns:
            Detailed paper information or None
        """
        try:
            # Ensure proper OpenAlex ID format
            if not paper_id.startswith('https://openalex.org/'):
                if not paper_id.startswith('W'):
                    paper_id = 'W' + paper_id
                paper_id = f'https://openalex.org/{paper_id}'
            
            url = f"{self.base_url}/works/{paper_id}"
            
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                work = response.json()
                return self._convert_work_to_paper(work)
            else:
                logger.warning(f"Failed to get OpenAlex paper details for {paper_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting OpenAlex paper details for {paper_id}: {e}")
            return None
