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
    
    def __init__(self, fast_mode: bool = False):
        """Initialize DBLP client with optional fast mode
        
        Args:
            fast_mode: If True, use only the most effective search strategy for better performance
        """
        self.base_url = "https://dblp.org/search/publ/api"
        self.timeout = 15  # Reduced from 30 to 15 seconds
        self.max_retries = 2  # Add retry limit
        self.retry_delay = 1  # Delay between retries
        self.fast_mode = fast_mode  # Performance optimization flag
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
        Search DBLP for papers using optimized search strategies
        
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

        # Optimized search with fewer, more effective strategies
        search_strategies = self._generate_optimized_search_strategies(title, authors, year, venue)
        
        for strategy_name, query in search_strategies:
            logger.debug(f"DBLP strategy '{strategy_name}': {query}")
            
            params = {
                'q': query,
                'format': 'json',
                'h': min(limit, 100)  # DBLP max is 100
            }
            
            results = self._execute_search(query, params)
            if results:
                logger.debug(f"DBLP strategy '{strategy_name}' found {len(results)} results")
                return results
            else:
                logger.debug(f"DBLP strategy '{strategy_name}' found 0 results")
        
        logger.debug("All DBLP search strategies exhausted, returning empty results")
        return []

    def _generate_optimized_search_strategies(self, title: str, authors: List[str], year: int, venue: str) -> List[tuple]:
        """Generate optimized search strategies for DBLP with minimal API calls"""
        strategies = []
        
        if not title:
            return strategies
        
        # Clean and prepare title variations
        title_clean = self._clean_title_for_search(title)
        title_keywords = self._extract_title_keywords(title_clean)
        
        if self.fast_mode:
            # Fast mode: Only use the single most effective strategy
            if authors and year and title_keywords:
                main_author_last = self._extract_last_name(authors[0])
                if main_author_last:
                    # Use keywords for better flexibility while keeping precision
                    keywords_query = f'{" ".join(title_keywords)} {main_author_last} {year}'
                    strategies.append(("keywords_author_year", keywords_query))
                    return strategies
            
            # Fallback for fast mode when author/year not available
            if year and title_keywords:
                # Use keywords + year for better results than exact title
                strategies.append(("keywords_year", f'{" ".join(title_keywords)} {year}'))
            elif year:
                strategies.append(("exact_title_year", f'"{title_clean}" {year}'))
            else:
                strategies.append(("exact_title_only", f'"{title_clean}"'))
            return strategies
        
        # Normal mode: Use only 2 most effective strategies for optimal performance
        
        # Strategy 1: Keywords + author + year (most comprehensive and flexible)
        if authors and year and title_keywords:
            main_author_last = self._extract_last_name(authors[0])
            if main_author_last:
                keywords_query = f'{" ".join(title_keywords)} {main_author_last} {year}'
                strategies.append(("keywords_author_year", keywords_query))
        
        # Strategy 2: Fallback - exact title + year (good precision)
        if year:
            strategies.append(("exact_title_year", f'"{title_clean}" {year}'))
        else:
            # If no year, use exact title only as fallback
            strategies.append(("exact_title_only", f'"{title_clean}"'))
        
        return strategies
    
    def _clean_title_for_search(self, title: str) -> str:
        """Clean title for better DBLP search compatibility"""
        import re
        
        # Remove common formatting issues
        title = title.strip()
        
        # Remove excessive punctuation and special characters that confuse DBLP
        title = re.sub(r'[^\w\s\-:]', ' ', title)
        
        # Normalize whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Remove common academic prefixes/suffixes that make queries too specific
        noise_patterns = [
            r'\b(a|an|the)\s+',  # Articles
            r'\s+approach$',     # "approach"
            r'\s+method$',       # "method"
            r'\s+algorithm$',    # "algorithm"
        ]
        
        for pattern in noise_patterns:
            title = re.sub(pattern, ' ', title, flags=re.IGNORECASE)
        
        return re.sub(r'\s+', ' ', title).strip()
    
    def _extract_title_keywords(self, title: str, min_word_length: int = 3) -> List[str]:
        """Extract meaningful keywords from title"""
        import re
        
        # Split into words
        words = title.split()
        
        # Common stop words to ignore
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'among', 'through', 'during', 'before', 'after',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'new', 'novel', 'improved', 'efficient', 'effective', 'approach', 'method'
        }
        
        keywords = []
        for word in words:
            # Preserve hyphens within words (e.g., "zero-correlation", "multi-party")
            # but remove other punctuation
            word_clean = re.sub(r'[^\w\-]', '', word.lower())
            # Remove leading/trailing hyphens but keep internal ones
            word_clean = word_clean.strip('-')
            
            if (len(word_clean) >= min_word_length and 
                word_clean not in stop_words and
                not word_clean.isdigit()):
                keywords.append(word_clean)
        
        # Return top 4-5 keywords to avoid overly complex queries
        return keywords[:5]
    
    def _extract_last_name(self, author: str) -> str:
        """Extract last name from author string"""
        if not author:
            return ""
        
        # Handle various author formats
        parts = author.strip().split()
        if not parts:
            return ""
        
        # Common formats:
        # "John Smith" -> "Smith"
        # "Smith, John" -> "Smith"  
        # "J Smith" -> "Smith"
        # "Smith J" -> "Smith"
        
        if ',' in author:
            # "Smith, John" format
            return parts[0].rstrip(',')
        else:
            # "John Smith" format - return last part
            return parts[-1]
    
    def _execute_search(self, query: str, params: dict) -> List[Dict[str, Any]]:
        """Execute a single DBLP search with the given parameters"""
        try:
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
                        logger.error(f"DBLP query was: {query}")
                        logger.error(f"DBLP URL was: {self.base_url}")
                        return []
                except requests.exceptions.RequestException as e:
                    logger.error(f"DBLP request error: {e}")
                    logger.error(f"DBLP query was: {query}")
                    logger.error(f"DBLP response status: {getattr(response, 'status_code', 'Unknown')}")
                    return []
            
            # Parse response with detailed error reporting
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"DBLP returned invalid JSON: {e}")
                logger.error(f"DBLP response text (first 200 chars): {response.text[:200]}...")
                return []
            
            results = []
            
            # Enhanced response parsing with diagnostics
            if 'result' in data:
                result_data = data['result']
                if 'hits' in result_data:
                    hits = result_data['hits']
                    if isinstance(hits, dict):
                        total_hits = hits.get('@total', 0)
                        logger.debug(f"DBLP reports {total_hits} total hits available")
                        
                        if 'hit' in hits:
                            hit_list = hits['hit']
                            if not isinstance(hit_list, list):
                                hit_list = [hit_list]
                            
                            logger.debug(f"DBLP returned {len(hit_list)} hits to process")
                            
                            for i, hit in enumerate(hit_list):
                                if 'info' in hit:
                                    paper = self._parse_dblp_paper(hit['info'])
                                    if paper:
                                        results.append(paper)
                                    else:
                                        logger.debug(f"DBLP hit {i+1} failed to parse")
                                else:
                                    logger.debug(f"DBLP hit {i+1} missing 'info' field")
                        else:
                            logger.debug("DBLP response has hits but no 'hit' field")
                    else:
                        logger.debug(f"DBLP hits is not a dict: {type(hits)}")
                else:
                    logger.debug("DBLP response missing 'hits' field")
            else:
                logger.debug("DBLP response missing 'result' field")
                logger.debug(f"DBLP response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            if len(results) == 0 and 'result' in data and 'hits' in data['result']:
                # If we got a valid response structure but no results, it's a legitimate "no results"
                total_hits = data['result']['hits'].get('@total', 0) if isinstance(data['result']['hits'], dict) else 0
                if total_hits == 0:
                    logger.debug(f"DBLP legitimately found 0 results for query: {query}")
                else:
                    logger.warning(f"DBLP found {total_hits} hits but failed to parse any results")
            
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