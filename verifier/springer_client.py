#!/usr/bin/env python3
"""
Springer Nature API client for academic paper verification
Supports Meta API for accessing paper metadata and abstracts
"""

import requests
import logging
import time
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
import re

logger = logging.getLogger(__name__)

class SpringerNatureClient:
    """Client for searching Springer Nature database via Meta API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Springer Nature client
        
        Args:
            api_key: Springer Nature API key (REQUIRED - no free tier available)
        """
        self.base_url = "https://api.springernature.com/meta/v2"
        self.api_key = api_key
        
        # Rate limiting: Conservative approach for API compliance
        self.rate_limit_delay = 1.0  # 1 second between requests
        self.last_request_time = 0
        
        self.session = requests.Session()
        
        if not api_key:
            logger.info("Springer Nature API key not provided - this database requires an API key for all requests")
            logger.info("Get your free API key at: https://dev.springernature.com/")
    
    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Make API request with rate limiting and error handling
        
        Args:
            endpoint: API endpoint to call
            params: Query parameters
            
        Returns:
            Response text or None if failed
        """
        if not self.api_key:
            logger.debug("Springer Nature API key required - skipping request")
            return None
        
        self._rate_limit()
        
        # Add API key to parameters
        params['api_key'] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            logger.debug(f"Springer Nature API request: {endpoint} with params: {params}")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            return response.text
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("Springer Nature API authentication failed - check API key")
            elif e.response.status_code == 429:
                logger.warning("Springer Nature API rate limit exceeded")
            else:
                logger.error(f"Springer Nature API HTTP error: {e.response.status_code}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Springer Nature API request failed: {e}")
            return None
    
    def _parse_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response from API"""
        try:
            import json
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Springer Nature API response: {e}")
            return None
    
    def _extract_paper_info(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract paper information from Springer Nature API response
        
        Args:
            record: Single paper record from API response
            
        Returns:
            Standardized paper information dictionary
        """
        try:
            # Extract basic information
            title = record.get('title', '').strip()
            
            # Extract authors
            authors = []
            creator_list = record.get('creators', [])
            if isinstance(creator_list, list):
                for creator in creator_list:
                    if isinstance(creator, dict):
                        name = creator.get('creator', '').strip()
                        if name:
                            authors.append(name)
            
            # Extract year from publication date
            year = None
            pub_date = record.get('publicationDate', '') or record.get('onlineDate', '')
            if pub_date:
                year_match = re.search(r'\b(19|20)\d{2}\b', str(pub_date))
                if year_match:
                    year = int(year_match.group())
            
            # Extract venue/journal
            venue = record.get('publicationName', '').strip()
            
            # Extract DOI
            doi = record.get('doi', '').strip()
            
            # Extract URL
            url = record.get('url', '').strip()
            if not url and doi:
                url = f"https://doi.org/{doi}"
            
            # Extract abstract
            abstract = record.get('abstract', '').strip()
            
            # Extract volume and pages
            volume = record.get('volume', '').strip()
            pages = record.get('startingPage', '').strip()
            if pages and record.get('endingPage'):
                pages += f"-{record.get('endingPage', '').strip()}"
            
            # Extract subject areas
            subjects = []
            subject_list = record.get('subjects', [])
            if isinstance(subject_list, list):
                for subject in subject_list:
                    if isinstance(subject, dict):
                        subj_name = subject.get('subject', '').strip()
                        if subj_name:
                            subjects.append(subj_name)
            
            paper_info = {
                'title': title,
                'authors': authors,
                'year': year,
                'venue': venue,
                'doi': doi,
                'url': url,
                'abstract': abstract,
                'volume': volume,
                'pages': pages,
                'subjects': subjects,
                'source': 'springer_nature',
                'raw_data': record
            }
            
            return paper_info
            
        except Exception as e:
            logger.error(f"Error extracting paper info from Springer Nature record: {e}")
            return {}
    
    def search_by_title_and_authors(self, title: str, authors: List[str] = None, year: int = None) -> List[Dict[str, Any]]:
        """
        Search Springer Nature by title and authors
        
        Args:
            title: Paper title
            authors: List of author names (optional)
            year: Publication year (optional)
            
        Returns:
            List of matching papers
        """
        if not title.strip():
            return []
        
        # Build search query
        query_parts = []
        
        # Add title search
        title_clean = re.sub(r'[^\w\s]', ' ', title.strip())
        title_words = [w for w in title_clean.split() if len(w) > 2]
        if title_words:
            title_query = ' AND '.join(f'title:"{word}"' for word in title_words[:6])  # Limit to 6 words
            query_parts.append(f"({title_query})")
        
        # Add author search if provided
        if authors:
            author_queries = []
            for author in authors[:3]:  # Limit to 3 authors
                author_clean = re.sub(r'[^\w\s]', ' ', author.strip())
                if author_clean:
                    author_queries.append(f'creator:"{author_clean}"')
            if author_queries:
                query_parts.append(f"({' OR '.join(author_queries)})")
        
        # Add year constraint if provided
        if year:
            query_parts.append(f'year:{year}')
        
        if not query_parts:
            return []
        
        query = ' AND '.join(query_parts)
        logger.info(f"Springer Nature search query: {query}")
        
        # API parameters
        params = {
            'q': query,
            'p': 10,  # Max 10 results
            's': 1,   # Start from 1
            'sort': 'relevance'
        }
        
        response_text = self._make_request('json', params)
        if not response_text:
            return []
        
        response_data = self._parse_json_response(response_text)
        if not response_data:
            return []
        
        # Extract papers from response
        papers = []
        records = response_data.get('records', [])
        
        logger.debug(f"Springer Nature returned {len(records)} records")
        
        for record in records:
            paper_info = self._extract_paper_info(record)
            if paper_info.get('title'):
                papers.append(paper_info)
        
        return papers
    
    def search_by_doi(self, doi: str) -> List[Dict[str, Any]]:
        """
        Search Springer Nature by DOI
        
        Args:
            doi: Paper DOI
            
        Returns:
            List of matching papers (usually 0 or 1)
        """
        if not doi.strip():
            return []
        
        # Clean DOI
        doi_clean = doi.strip().lower()
        if doi_clean.startswith('doi:'):
            doi_clean = doi_clean[4:]
        if doi_clean.startswith('http'):
            # Extract DOI from URL
            doi_match = re.search(r'10\.\d+/[^\s]+', doi_clean)
            if doi_match:
                doi_clean = doi_match.group()
            else:
                return []
        
        params = {
            'q': f'doi:"{doi_clean}"',
            'p': 5,
            's': 1
        }
        
        response_text = self._make_request('json', params)
        if not response_text:
            return []
        
        response_data = self._parse_json_response(response_text)
        if not response_data:
            return []
        
        papers = []
        records = response_data.get('records', [])
        
        for record in records:
            paper_info = self._extract_paper_info(record)
            if paper_info.get('title'):
                papers.append(paper_info)
        
        return papers
    
    def search_by_keywords(self, keywords: str, subject_area: str = None) -> List[Dict[str, Any]]:
        """
        Search Springer Nature by keywords
        
        Args:
            keywords: Search keywords
            subject_area: Subject area filter (optional)
            
        Returns:
            List of matching papers
        """
        if not keywords.strip():
            return []
        
        # Build query
        query_parts = [keywords.strip()]
        
        if subject_area:
            query_parts.append(f'subject:"{subject_area}"')
        
        query = ' AND '.join(query_parts)
        
        params = {
            'q': query,
            'p': 10,
            's': 1,
            'sort': 'relevance'
        }
        
        response_text = self._make_request('json', params)
        if not response_text:
            return []
        
        response_data = self._parse_json_response(response_text)
        if not response_data:
            return []
        
        papers = []
        records = response_data.get('records', [])
        
        for record in records:
            paper_info = self._extract_paper_info(record)
            if paper_info.get('title'):
                papers.append(paper_info)
        
        return papers
    
    def search_papers(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main search method that tries multiple search strategies
        
        Args:
            reference: Reference dictionary with title, authors, year, etc.
            
        Returns:
            List of matching papers from Springer Nature
        """
        title = reference.get('title', '').strip()
        authors = reference.get('authors', [])
        year = reference.get('year')
        doi = reference.get('doi', '').strip()
        
        logger.info(f"Searching Springer Nature for: {title[:60]}...")
        
        all_papers = []
        
        # Try DOI search first if available
        if doi:
            logger.debug("Trying Springer Nature DOI search")
            doi_papers = self.search_by_doi(doi)
            all_papers.extend(doi_papers)
            if doi_papers:
                logger.info(f"Found {len(doi_papers)} papers via DOI search")
                return doi_papers  # DOI search is authoritative
        
        # Try title and authors search
        if title:
            logger.debug("Trying Springer Nature title/authors search")
            title_papers = self.search_by_title_and_authors(title, authors, year)
            all_papers.extend(title_papers)
        
        # Remove duplicates by DOI/title
        unique_papers = []
        seen_dois = set()
        seen_titles = set()
        
        for paper in all_papers:
            paper_doi = paper.get('doi', '').lower()
            paper_title = paper.get('title', '').lower().strip()
            
            if paper_doi and paper_doi in seen_dois:
                continue
            if paper_title and paper_title in seen_titles:
                continue
            
            if paper_doi:
                seen_dois.add(paper_doi)
            if paper_title:
                seen_titles.add(paper_title)
            
            unique_papers.append(paper)
        
        logger.info(f"Found {len(unique_papers)} unique papers from Springer Nature")
        return unique_papers
