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
import xml.etree.ElementTree as ET
import time
import logging
import threading
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
import re

logger = logging.getLogger(__name__)

# Global rate limiting for thread safety across multiple PubMed client instances
_pubmed_rate_limiter = threading.Lock()
_last_pubmed_request = 0

class PubMedClient:
    """Client for searching PubMed/MEDLINE database via Entrez E-utilities API"""
    
    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None):
        """
        Initialize PubMed client
        
        Args:
            api_key: NCBI API key for higher rate limits (optional but recommended)
            email: Contact email (required for NCBI API guidelines)
        """
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.api_key = api_key
        self.email = email or "VerifyRef@example.com"  # Default email
        
        # Rate limiting: 3 req/sec without API key, 10 req/sec with API key
        # Use more conservative delays to avoid hitting rate limits
        self.rate_limit_delay = 0.2 if api_key else 0.5  # More conservative delays
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VerifyRef/1.0 (Academic Reference Verification Tool; mailto:VerifyRef@example.com)',
            'Accept': 'application/xml'
        })
        
        logger.info(f"PubMed client initialized (API key: {'Yes' if api_key else 'No'})")
    
    def is_available(self) -> bool:
        """Check if PubMed service is available"""
        try:
            # Make a simple test query to check availability
            response = self.session.get(
                f"{self.base_url}/einfo.fcgi",
                params={'tool': 'VerifyRef', 'email': self.email},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def _rate_limit(self):
        """Enforce thread-safe rate limiting between requests across all instances"""
        global _pubmed_rate_limiter, _last_pubmed_request
        
        with _pubmed_rate_limiter:
            current_time = time.time()
            time_since_last = current_time - _last_pubmed_request
            
            if time_since_last < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last
                time.sleep(sleep_time)
            
            _last_pubmed_request = time.time()
    
    def _make_request(self, endpoint: str, params: Dict[str, Any], max_retries: int = 3) -> Optional[str]:
        """Make API request with rate limiting, error handling, and retry logic for 429 errors"""
        self._rate_limit()
        
        # Add common parameters
        params.update({
            'tool': 'VerifyRef',
            'email': self.email
        })
        
        if self.api_key:
            params['api_key'] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.debug(f"PubMed API retry attempt {attempt}/{max_retries}")
                
                logger.debug(f"PubMed API request: {endpoint} with params: {params}")
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                return response.text
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429 and attempt < max_retries:
                    # Rate limit exceeded - use exponential backoff
                    wait_time = (2 ** attempt) * self.rate_limit_delay  # 0.5s, 1s, 2s...
                    logger.warning(f"PubMed rate limit exceeded (429), retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.warning(f"PubMed API request failed: {e}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"PubMed API request failed: {e}")
                return None
        
        logger.warning(f"PubMed API request failed after {max_retries + 1} attempts")
        return None
    
    def _search_pubmed(self, query: str, max_results: int = 20) -> List[str]:
        """
        Search PubMed and return list of PMIDs
        
        Args:
            query: Search query in PubMed format
            max_results: Maximum number of results to return
            
        Returns:
            List of PubMed IDs (PMIDs)
        """
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'xml',
            'sort': 'relevance'
        }
        
        response_text = self._make_request('esearch.fcgi', params)
        if not response_text:
            return []
        
        try:
            root = ET.fromstring(response_text)
            id_list = root.find('.//IdList')
            
            if id_list is not None:
                pmids = [id_elem.text for id_elem in id_list.findall('Id')]
                logger.debug(f"Found {len(pmids)} PMIDs for query: {query}")
                return pmids
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse PubMed search response: {e}")
        
        return []
    
    def _fetch_paper_details(self, pmids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch detailed information for given PMIDs
        
        Args:
            pmids: List of PubMed IDs
            
        Returns:
            List of paper details dictionaries
        """
        if not pmids:
            return []
        
        # Fetch details for up to 20 papers at once
        pmid_str = ','.join(pmids[:20])
        
        params = {
            'db': 'pubmed',
            'id': pmid_str,
            'retmode': 'xml',
            'rettype': 'abstract'
        }
        
        response_text = self._make_request('efetch.fcgi', params)
        if not response_text:
            return []
        
        return self._parse_pubmed_xml(response_text)
    
    def _parse_pubmed_xml(self, xml_text: str) -> List[Dict[str, Any]]:
        """Parse PubMed XML response into structured paper data"""
        papers = []
        
        try:
            root = ET.fromstring(xml_text)
            
            for article in root.findall('.//PubmedArticle'):
                paper = self._extract_paper_info(article)
                if paper:
                    papers.append(paper)
                    
        except ET.ParseError as e:
            logger.error(f"Failed to parse PubMed XML: {e}")
        
        return papers
    
    def _extract_paper_info(self, article_elem) -> Optional[Dict[str, Any]]:
        """Extract paper information from PubMed XML article element"""
        try:
            # Get PMID
            pmid_elem = article_elem.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else None
            
            # Get main article element
            article = article_elem.find('.//Article')
            if article is None:
                return None
            
            # Extract title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else ""
            
            # Clean title (remove HTML tags if any)
            title = re.sub(r'<[^>]+>', '', title) if title else ""
            
            # Extract authors
            authors = []
            author_list = article.find('.//AuthorList')
            if author_list is not None:
                for author in author_list.findall('Author'):
                    last_name = author.find('LastName')
                    first_name = author.find('ForeName')
                    
                    if last_name is not None:
                        name = last_name.text
                        if first_name is not None:
                            name = f"{first_name.text} {name}"
                        authors.append(name)
            
            # Extract journal information
            journal_elem = article.find('.//Journal')
            journal_title = ""
            year = None
            volume = ""
            issue = ""
            pages = ""
            
            if journal_elem is not None:
                # Journal title
                journal_title_elem = journal_elem.find('.//Title')
                if journal_title_elem is not None:
                    journal_title = journal_title_elem.text
                
                # Publication date
                pub_date = journal_elem.find('.//PubDate')
                if pub_date is not None:
                    year_elem = pub_date.find('Year')
                    if year_elem is not None:
                        try:
                            year = int(year_elem.text)
                        except ValueError:
                            pass
                
                # Volume and issue
                issue_elem = journal_elem.find('.//JournalIssue')
                if issue_elem is not None:
                    volume_elem = issue_elem.find('Volume')
                    if volume_elem is not None:
                        volume = volume_elem.text
                    
                    issue_num_elem = issue_elem.find('Issue')
                    if issue_num_elem is not None:
                        issue = issue_num_elem.text
            
            # Extract pagination
            pagination_elem = article.find('.//Pagination/MedlinePgn')
            if pagination_elem is not None:
                pages = pagination_elem.text
            
            # Extract DOI
            doi = None
            for id_elem in article.findall('.//ArticleId'):
                if id_elem.get('IdType') == 'doi':
                    doi = id_elem.text
                    break
            
            # Extract abstract
            abstract = ""
            abstract_elem = article.find('.//Abstract/AbstractText')
            if abstract_elem is not None:
                abstract = abstract_elem.text or ""
            
            # Create paper dictionary
            paper = {
                'pmid': pmid,
                'title': title.strip(),
                'authors': authors,
                'journal': journal_title,
                'year': year,
                'volume': volume,
                'issue': issue,
                'pages': pages,
                'doi': doi,
                'abstract': abstract,
                'source': 'PubMed',
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None
            }
            
            logger.debug(f"Extracted PubMed paper: {title[:50]}...")
            return paper
            
        except Exception as e:
            logger.error(f"Error extracting paper info: {e}")
            return None
    
    def search_by_title_and_authors(self, title: str, authors: List[str] = None, year: int = None) -> List[Dict[str, Any]]:
        """
        Search PubMed by title and authors
        
        Args:
            title: Paper title
            authors: List of author names
            year: Publication year
            
        Returns:
            List of matching papers from PubMed
        """
        if not title:
            return []
        
        # Build search query - start simple and get more specific
        query_parts = []
        
        # Add title search - use important keywords
        title_clean = re.sub(r'[^\w\s]', ' ', title)  # Remove special characters
        title_words = title_clean.split()
        if title_words and len(title_words) >= 2:
            # Use the most important words (longer than 3 chars)
            important_words = [word for word in title_words if len(word) > 3][:4]
            if important_words:
                # Search in title and abstract for broader coverage
                title_query = " AND ".join(important_words)
                query_parts.append(f"({title_query})[Title/Abstract]")
        
        # Add first author if available
        if authors and len(authors) > 0:
            first_author = authors[0]
            if first_author:
                name_parts = first_author.split()
                if name_parts:
                    last_name = name_parts[-1]
                    query_parts.append(f"{last_name}[Author]")
        
        # Add year with tolerance
        if year and year > 1900:
            query_parts.append(f"({year-1}:{year+1})[PDAT]")
        
        if not query_parts:
            return []
        
        # Combine query parts
        query = " AND ".join(query_parts)
        
        logger.info(f"PubMed search query: {query}")
        
        # Search PubMed
        pmids = self._search_pubmed(query, max_results=10)
        
        if not pmids:
            # Fallback: try simpler title search
            if title_words and len(title_words) >= 2:
                # Use just the first few important words
                simple_words = [word for word in title_words if len(word) > 4][:3]
                if simple_words:
                    fallback_query = " AND ".join(simple_words)
                    logger.info(f"PubMed fallback query: {fallback_query}")
                    pmids = self._search_pubmed(fallback_query, max_results=5)
        
        if pmids:
            return self._fetch_paper_details(pmids)
        
        return []
    
    def search_by_doi(self, doi: str) -> List[Dict[str, Any]]:
        """
        Search PubMed by DOI
        
        Args:
            doi: Digital Object Identifier
            
        Returns:
            List with the matching paper (if found)
        """
        if not doi:
            return []
        
        # Clean DOI
        doi_clean = doi.strip().replace('https://doi.org/', '').replace('http://dx.doi.org/', '')
        
        query = f"{doi_clean}[DOI]"
        logger.info(f"PubMed DOI search: {query}")
        
        pmids = self._search_pubmed(query, max_results=1)
        
        if pmids:
            return self._fetch_paper_details(pmids)
        
        return []
    
    def search_by_pmid(self, pmid: str) -> List[Dict[str, Any]]:
        """
        Search PubMed by PMID
        
        Args:
            pmid: PubMed ID
            
        Returns:
            List with the matching paper (if found)
        """
        if not pmid:
            return []
        
        logger.info(f"PubMed PMID search: {pmid}")
        return self._fetch_paper_details([pmid])

    def search_papers(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main search method that tries multiple search strategies
        
        Args:
            reference: Reference dictionary with title, authors, year, etc.
            
        Returns:
            List of matching papers from PubMed
        """
        title = reference.get('title', '').strip()
        authors = reference.get('authors', [])
        year = reference.get('year')
        doi = reference.get('doi', '').strip()
        
        logger.info(f"Searching PubMed for: {title[:60]}...")
        
        # Strategy 1: Search by DOI if available
        if doi:
            results = self.search_by_doi(doi)
            if results:
                logger.info(f"Found {len(results)} PubMed results via DOI")
                return results
        
        # Strategy 2: Search by title and authors
        if title:
            results = self.search_by_title_and_authors(title, authors, year)
            if results:
                logger.info(f"Found {len(results)} PubMed results via title/authors")
                return results
        
        logger.info("No PubMed results found")
        return []

    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Verify a reference against PubMed database (alias for search_papers)
        
        Args:
            reference: Reference dictionary with title, authors, year, etc.
            
        Returns:
            List of matching papers from PubMed
        """
        return self.search_papers(reference)