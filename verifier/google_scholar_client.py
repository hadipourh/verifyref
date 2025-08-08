"""
Google Scholar client with smart fallback strategy and anti-bot protection
Uses scholarly library with comprehensive rate limiting and human-like behavior
"""

import time
import random
import logging
import sys
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import requests
from scholarly import scholarly, ProxyGenerator

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_CONFIG

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class GoogleScholarResult:
    """Represents a single Google Scholar search result"""
    title: str
    authors: List[str]
    year: Optional[int]
    venue: Optional[str]
    url: Optional[str]
    cited_by: Optional[int]
    snippet: Optional[str]
    similarity: float = 0.0

class GoogleScholarRateLimiter:
    """Smart rate limiter with session management and anti-bot protection"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.last_request_time = 0
        self.requests_this_hour = 0
        self.requests_today = 0
        self.requests_this_session = 0
        self.hour_start = time.time()
        self.day_start = time.time()
        self.session_start = time.time()
        self.blocked_until = 0
        self.current_user_agent_index = 0
        
    def wait_if_needed(self) -> bool:
        """
        Wait if rate limiting is needed
        Returns False if we should skip this request (quota exceeded)
        """
        current_time = time.time()
        
        # Check if we're in cooldown period
        if current_time < self.blocked_until:
            logger.warning(f"In cooldown period, skipping request (blocked until {self.blocked_until})")
            return False
        
        # Reset hourly counter
        if current_time - self.hour_start > 3600:
            self.requests_this_hour = 0
            self.hour_start = current_time
            
        # Reset daily counter  
        if current_time - self.day_start > 86400:
            self.requests_today = 0
            self.day_start = current_time
            
        # Check quotas
        if self.requests_this_hour >= self.config.get('max_requests_per_hour', 10):
            logger.warning("Hourly quota exceeded, skipping Google Scholar request")
            return False
            
        if self.requests_today >= self.config.get('max_requests_per_day', 50):
            logger.warning("Daily quota exceeded, skipping Google Scholar request")
            return False
            
        # Session rotation
        if (self.requests_this_session >= self.config.get('max_requests_per_session', 5) or 
            current_time - self.session_start > 1800):  # 30 minutes
            self._rotate_session()
            
        # Calculate delay with randomization
        base_delay = self.config.get('rate_limit_delay', 20.0)
        if self.config.get('randomize_delays', True):
            min_var = self.config.get('min_delay_variance', 0.7)
            max_var = self.config.get('max_delay_variance', 1.3)
            delay = base_delay * random.uniform(min_var, max_var)
        else:
            delay = base_delay
            
        # Wait if needed
        time_since_last = current_time - self.last_request_time
        if time_since_last < delay:
            wait_time = delay - time_since_last
            logger.info(f"Rate limiting: waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)
            
        # Update counters
        self.last_request_time = time.time()
        self.requests_this_hour += 1
        self.requests_today += 1
        self.requests_this_session += 1
        
        return True
        
    def handle_block(self):
        """Handle being blocked by Google Scholar"""
        cooldown = self.config.get('cooldown_after_block', 3600)
        self.blocked_until = time.time() + cooldown
        logger.warning(f"Detected block, entering cooldown for {cooldown} seconds")
        
    def _rotate_session(self):
        """Rotate session and user agent"""
        logger.info("Rotating session for anti-bot protection")
        self.requests_this_session = 0
        self.session_start = time.time()
        
        if self.config.get('rotate_user_agents', True):
            user_agents = self.config.get('user_agents', [])
            if user_agents:
                self.current_user_agent_index = (self.current_user_agent_index + 1) % len(user_agents)
                
    def get_current_user_agent(self) -> str:
        """Get current user agent for rotation"""
        user_agents = self.config.get('user_agents', [])
        if user_agents and self.config.get('rotate_user_agents', True):
            return user_agents[self.current_user_agent_index]
        return "Mozilla/5.0 (compatible; Academic Research Tool)"

class GoogleScholarClient:
    """Google Scholar client with smart fallback and anti-bot protection"""
    
    def __init__(self):
        self.config = DATABASE_CONFIG.get('google_scholar', {})
        self.rate_limiter = GoogleScholarRateLimiter(self.config)
        self.session_configured = False
        
    def is_available(self) -> bool:
        """
        Check if Google Scholar service is available
        
        Returns:
            True if the service is available and enabled
        """
        return self.config.get('enabled', False)
        
    def should_search_google_scholar(self, best_similarity: float, databases_searched: List[str]) -> bool:
        """
        Determine if we should use Google Scholar based on fallback strategy
        
        Args:
            best_similarity: Best similarity score from other databases
            databases_searched: List of databases already searched
            
        Returns:
            True if Google Scholar should be searched
        """
        if not self.config.get('enabled', False):
            return False
            
        # If not in fallback-only mode, always search
        if not self.config.get('fallback_only', True):
            return True
            
        # Check if enough databases were searched
        min_dbs = self.config.get('min_databases_searched', 3)
        if len(databases_searched) < min_dbs:
            logger.debug(f"Not enough databases searched ({len(databases_searched)} < {min_dbs})")
            return False
            
        # Check if similarity threshold is met
        threshold = self.config.get('fallback_threshold', 0.7)
        if best_similarity >= threshold:
            logger.debug(f"Best similarity {best_similarity:.2f} >= threshold {threshold:.2f}, skipping Google Scholar")
            return False
            
        logger.info(f"Triggering Google Scholar fallback: best_similarity={best_similarity:.2f}, dbs_searched={len(databases_searched)}")
        return True
        
    def should_validate_author_manipulation(self, classification: str) -> bool:
        """
        Determine if we should use Google Scholar to validate author manipulation detection
        
        Args:
            classification: The preliminary classification result
            
        Returns:
            True if Google Scholar should validate the author manipulation detection
        """
        if not self.config.get('enabled', False):
            return False
            
        # Always validate author manipulation if Google Scholar is enabled
        if classification == 'author_manipulation':
            logger.info("Triggering Google Scholar validation for author manipulation detection")
            return True
            
        return False
    
    def should_validate_fabrication_suspicion(self, databases_searched: List[str], similarity_score: float) -> bool:
        """
        Determine if we should use Google Scholar to validate suspected fabrication
        when no major databases found the paper
        
        Args:
            databases_searched: List of databases that were searched
            similarity_score: Best similarity score found
            
        Returns:
            True if Google Scholar should validate the fabrication suspicion
        """
        if not self.config.get('enabled', False):
            return False
            
        # Major academic databases
        major_databases = {'openalex', 'semantic_scholar', 'dblp', 'pubmed', 'arxiv', 'iacr'}
        found_in_major_db = any(db in major_databases for db in databases_searched)
        
        # If no major database found the paper AND similarity is low, validate with Google Scholar
        if not found_in_major_db and similarity_score < 0.5:
            logger.info(f"Triggering Google Scholar validation for suspected fabrication: no major DB results, similarity={similarity_score:.2f}")
            return True
            
        return False
    
    def validate_fabrication_suspicion(self, title: str, authors: List[str], year: Optional[int] = None) -> Dict[str, Any]:
        """
        Validate suspected fabrication using Google Scholar
        Search for the exact paper to confirm if it actually exists
        
        Args:
            title: Paper title to search for
            authors: Paper authors to verify
            year: Publication year (optional)
            
        Returns:
            Dict with validation result and evidence
        """
        if not self.is_available():
            return {"validated": False, "reason": "Google Scholar not available"}
            
        # Wait for rate limiting
        if not self.rate_limiter.wait_if_needed():
            return {"validated": False, "reason": "Rate limit exceeded"}
            
        try:
            self._configure_session()
            
            # Search for exact title
            exact_title_query = f'"{title}"'
            logger.info(f"Validating fabrication suspicion with Google Scholar: {exact_title_query}")
            
            search_results = scholarly.search_pubs(exact_title_query)
            found_papers = []
            
            # Look for up to 5 results to see if the paper actually exists
            for i, paper in enumerate(search_results):
                if i >= 5:  # Limit search to avoid excessive API usage
                    break
                    
                try:
                    result = self._parse_paper_result(paper)
                    if result:
                        found_papers.append(result)
                        
                    # Small delay between results
                    if i < 4:
                        time.sleep(random.uniform(1, 2))
                        
                except Exception as e:
                    logger.warning(f"Error parsing fabrication validation result: {e}")
                    continue
            
            # Analyze results to determine if paper exists
            validation_result = self._analyze_fabrication_evidence(title, authors, year, found_papers)
            
            logger.info(f"Fabrication validation result: {validation_result['conclusion']}")
            return validation_result
            
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['blocked', 'captcha', 'robot', 'too many requests']):
                logger.error(f"Google Scholar blocked fabrication validation request: {e}")
                self.rate_limiter.handle_block()
            else:
                logger.error(f"Google Scholar fabrication validation error: {e}")
            
            return {"validated": False, "reason": f"Search error: {e}"}
    
    def _analyze_fabrication_evidence(self, title: str, authors: List[str], year: Optional[int], 
                                     found_papers: List[GoogleScholarResult]) -> Dict[str, Any]:
        """
        Analyze Google Scholar results to determine if suspected fabrication is real or fake
        """
        if not found_papers:
            return {
                "validated": True,  # Confirms fabrication - paper doesn't exist
                "conclusion": "confirmed_fabrication",
                "evidence": "Google Scholar found no papers matching the title",
                "papers_found": 0,
                "confidence": 0.9
            }
        
        # Look for exact or very close matches - MUCH STRICTER CRITERIA
        exact_matches = []
        for paper in found_papers:
            title_similarity = self._calculate_title_similarity(title, paper.title)
            
            if title_similarity > 0.95:  # INCREASED: Much higher threshold for title match
                # Check author similarity with stricter requirements
                author_similarity = self._calculate_author_similarity(authors, paper.authors)
                
                if author_similarity > 0.8:  # INCREASED: Higher threshold for author match
                    # Found a legitimate match - must be very close in both title AND authors
                    return {
                        "validated": False,  # Paper exists - not fabricated
                        "conclusion": "paper_exists",
                        "evidence": f"Found legitimate paper: '{paper.title}' by {', '.join(paper.authors[:3])} (title_sim: {title_similarity:.3f}, author_sim: {author_similarity:.3f})",
                        "papers_found": len(found_papers),
                        "confidence": 0.85
                    }
                elif title_similarity > 0.98:  # Almost identical title but different authors
                    exact_matches.append((paper, title_similarity, author_similarity))
            elif title_similarity > 0.8:  # Medium similarity - might be related paper
                author_similarity = self._calculate_author_similarity(authors, paper.authors)
                if author_similarity > 0.8:  # Authors match but title doesn't - suspicious
                    exact_matches.append((paper, title_similarity, author_similarity))
        
        # If we found high title similarity but different authors, likely author manipulation or fabrication
        if exact_matches:
            best_match, title_sim, author_sim = max(exact_matches, key=lambda x: x[1])
            
            if title_sim > 0.98 and author_sim < 0.5:
                # Almost identical title but very different authors - likely author manipulation
                return {
                    "validated": None,  # Inconclusive - might be author manipulation instead
                    "conclusion": "possible_author_manipulation",
                    "evidence": f"Found very similar title '{best_match.title}' but significantly different authors (title_sim: {title_sim:.3f}, author_sim: {author_sim:.3f})",
                    "papers_found": len(found_papers),
                    "confidence": 0.7
                }
            else:
                # Related but not identical paper found
                return {
                    "validated": True,  # Likely fabricated - no exact match found
                    "conclusion": "related_paper_only",
                    "evidence": f"Found related paper '{best_match.title}' but not exact match (title_sim: {title_sim:.3f}, author_sim: {author_sim:.3f})",
                    "papers_found": len(found_papers),
                    "confidence": 0.8
                }
        
        # Found some papers but no good matches - likely fabricated
        return {
            "validated": True,  # Likely fabricated - no matching paper found
            "conclusion": "likely_fabrication", 
            "evidence": f"Found {len(found_papers)} papers but none match the title/authors sufficiently (best similarity < 0.95)",
            "papers_found": len(found_papers),
            "confidence": 0.85
        }
            
        return False
        
    def _configure_session(self):
        """Configure scholarly session with proxy and user agent"""
        if self.session_configured:
            return
            
        try:
            # Set user agent
            user_agent = self.rate_limiter.get_current_user_agent()
            scholarly.set_timeout(self.config.get('timeout', 45))
            
            # Configure proxy if available
            proxy_url = self.config.get('proxy_url', '')
            if proxy_url:
                logger.info(f"Configuring Google Scholar with proxy: {proxy_url}")
                pg = ProxyGenerator()
                pg.Standalone_Proxy(proxy_url)
                scholarly.set_proxy_generator(pg)
                
            self.session_configured = True
            logger.info("Google Scholar session configured successfully")
            
        except Exception as e:
            logger.warning(f"Failed to configure Google Scholar session: {e}")
            # Continue without proxy
            self.session_configured = True
            
    def search_papers(self, title: str, authors: List[str], year: Optional[int] = None) -> List[GoogleScholarResult]:
        """
        Search Google Scholar for papers
        
        Args:
            title: Paper title to search for
            authors: List of author names
            year: Publication year (optional)
            
        Returns:
            List of GoogleScholarResult objects
        """
        if not self.rate_limiter.wait_if_needed():
            return []
            
        self._configure_session()
        
        try:
            # Construct search query
            query = self._build_search_query(title, authors, year)
            logger.info(f"Searching Google Scholar: {query}")
            
            # Perform search with retry logic
            results = []
            max_results = self.config.get('max_results', 3)
            
            search_results = scholarly.search_pubs(query)
            
            for i, paper in enumerate(search_results):
                if i >= max_results:
                    break
                    
                try:
                    result = self._parse_paper_result(paper)
                    if result:
                        results.append(result)
                        
                    # Small delay between parsing results
                    if i < max_results - 1:
                        time.sleep(random.uniform(1, 3))
                        
                except Exception as e:
                    logger.warning(f"Error parsing Google Scholar result: {e}")
                    continue
                    
            logger.info(f"Found {len(results)} results from Google Scholar")
            return results
            
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['blocked', 'captcha', 'robot', 'too many requests']):
                logger.error(f"Google Scholar blocked request: {e}")
                self.rate_limiter.handle_block()
            else:
                logger.error(f"Google Scholar search error: {e}")
            return []
            
    def _build_search_query(self, title: str, authors: List[str], year: Optional[int] = None) -> str:
        """Build optimized search query for Google Scholar"""
        # Use title as main query
        query_parts = [f'"{title}"']
        
        # Add primary author if available
        if authors:
            primary_author = authors[0].split()[-1]  # Last name
            query_parts.append(f'author:"{primary_author}"')
            
        # Add year if available
        if year:
            query_parts.append(f'"{year}"')
            
        return ' '.join(query_parts)
        
    def _parse_paper_result(self, paper: Dict[str, Any]) -> Optional[GoogleScholarResult]:
        """Parse a single paper result from Google Scholar"""
        try:
            # Extract basic information
            title = paper.get('bib', {}).get('title', '').strip()
            if not title:
                return None
                
            # Parse authors
            authors = []
            author_str = paper.get('bib', {}).get('author', '')
            if author_str:
                # Split by 'and' and clean up
                authors = [author.strip() for author in author_str.split(' and ')]
                
            # Parse year
            year = None
            year_str = paper.get('bib', {}).get('pub_year', '')
            if year_str:
                try:
                    year = int(year_str)
                except (ValueError, TypeError):
                    pass
                    
            # Parse venue
            venue = paper.get('bib', {}).get('venue', '').strip()
            
            # Get URL
            url = paper.get('pub_url', '') or paper.get('eprint_url', '')
            
            # Get citation count
            cited_by = None
            if 'num_citations' in paper:
                try:
                    cited_by = int(paper['num_citations'])
                except (ValueError, TypeError):
                    pass
                    
            # Get snippet
            snippet = paper.get('bib', {}).get('abstract', '').strip()
            if not snippet:
                snippet = title  # Use title as fallback
                
            return GoogleScholarResult(
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                url=url,
                cited_by=cited_by,
                snippet=snippet
            )
            
        except Exception as e:
            logger.warning(f"Error parsing Google Scholar paper: {e}")
            return None
            
    def validate_author_manipulation(self, title: str, authors: List[str], suspected_match_title: str, suspected_match_authors: List[str]) -> Dict[str, Any]:
        """
        Validate author manipulation detection using Google Scholar
        
        Args:
            title: Original reference title
            authors: Original reference authors
            suspected_match_title: Title of the suspected matching paper
            suspected_match_authors: Authors of the suspected matching paper
            
        Returns:
            Dict with validation result and evidence
        """
        if not self.is_available():
            return {"validated": False, "reason": "Google Scholar not available"}
            
        # Wait for rate limiting
        if not self.rate_limiter.wait_if_needed():
            return {"validated": False, "reason": "Rate limit exceeded"}
            
        try:
            self._configure_session()
            
            # Search for exact title to see if multiple papers exist
            exact_title_query = f'"{title}"'
            logger.info(f"Validating author manipulation with Google Scholar: {exact_title_query}")
            
            search_results = scholarly.search_pubs(exact_title_query)
            found_papers = []
            
            # Look for up to 5 results to see if there are legitimate different papers
            for i, paper in enumerate(search_results):
                if i >= 5:  # Limit search to avoid excessive API usage
                    break
                    
                try:
                    result = self._parse_paper_result(paper)
                    if result:
                        found_papers.append(result)
                        
                    # Small delay between results
                    if i < 4:
                        time.sleep(random.uniform(1, 2))
                        
                except Exception as e:
                    logger.warning(f"Error parsing validation result: {e}")
                    continue
            
            # Analyze results to determine if author manipulation is valid
            validation_result = self._analyze_author_manipulation_evidence(
                title, authors, suspected_match_title, suspected_match_authors, found_papers
            )
            
            logger.info(f"Author manipulation validation result: {validation_result['conclusion']}")
            return validation_result
            
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['blocked', 'captcha', 'robot', 'too many requests']):
                logger.error(f"Google Scholar blocked validation request: {e}")
                self.rate_limiter.handle_block()
            else:
                logger.error(f"Google Scholar validation error: {e}")
            
            return {"validated": False, "reason": f"Search error: {e}"}
            
    def _analyze_author_manipulation_evidence(self, original_title: str, original_authors: List[str], 
                                            suspected_title: str, suspected_authors: List[str], 
                                            found_papers: List[GoogleScholarResult]) -> Dict[str, Any]:
        """
        Analyze Google Scholar results to determine if author manipulation detection is correct
        """
        # Look for exact or very close title matches
        exact_matches = []
        similar_matches = []
        
        for paper in found_papers:
            title_similarity = self._calculate_title_similarity(original_title, paper.title)
            
            if title_similarity > 0.95:  # Very high similarity (likely same paper)
                exact_matches.append(paper)
            elif title_similarity > 0.8:  # High similarity (could be related papers)
                similar_matches.append(paper)
        
        # Check if we found the original authors for the same/similar title
        found_original_authors = False
        found_suspected_authors = False
        
        for paper in exact_matches + similar_matches:
            # Check if this paper has the original authors
            author_match_original = self._calculate_author_similarity(original_authors, paper.authors)
            author_match_suspected = self._calculate_author_similarity(suspected_authors, paper.authors)
            
            if author_match_original > 0.7:
                found_original_authors = True
            if author_match_suspected > 0.7:
                found_suspected_authors = True
        
        # Determine conclusion
        if len(exact_matches) >= 2:
            # Multiple papers with very similar titles found
            if found_original_authors and found_suspected_authors:
                return {
                    "validated": False,  # Author manipulation is likely WRONG
                    "conclusion": "legitimate_different_papers",
                    "evidence": "Found multiple legitimate papers with similar titles but different authors",
                    "papers_found": len(exact_matches),
                    "confidence": 0.8
                }
            elif found_suspected_authors and not found_original_authors:
                return {
                    "validated": True,  # Author manipulation is likely CORRECT
                    "conclusion": "confirmed_author_manipulation", 
                    "evidence": "Found the correct paper with different authors than claimed",
                    "papers_found": len(exact_matches),
                    "confidence": 0.85
                }
        
        elif len(exact_matches) == 1:
            # Only one paper found with this title
            paper = exact_matches[0]
            author_match_suspected = self._calculate_author_similarity(suspected_authors, paper.authors)
            
            if author_match_suspected > 0.7:
                return {
                    "validated": True,  # Author manipulation is likely CORRECT
                    "conclusion": "confirmed_author_manipulation",
                    "evidence": "Found single paper with correct authors, different from reference",
                    "papers_found": 1,
                    "confidence": 0.9
                }
        
        # Inconclusive or no strong evidence
        return {
            "validated": None,  # Inconclusive
            "conclusion": "inconclusive",
            "evidence": f"Found {len(found_papers)} papers, but evidence is inconclusive",
            "papers_found": len(found_papers),
            "confidence": 0.3
        }
        
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
        
    def _calculate_author_similarity(self, authors1: List[str], authors2: List[str]) -> float:
        """Calculate similarity between two author lists"""
        if not authors1 or not authors2:
            return 0.0
            
        # Simple approach: check for overlapping last names
        last_names1 = {author.split()[-1].lower() for author in authors1}
        last_names2 = {author.split()[-1].lower() for author in authors2}
        
        if not last_names1 or not last_names2:
            return 0.0
            
        intersection = len(last_names1.intersection(last_names2))
        union = len(last_names1.union(last_names2))
        
        return intersection / union if union > 0 else 0.0

def test_google_scholar_client():
    """Test the Google Scholar client with a simple search"""
    logger.info("Testing Google Scholar client...")
    
    client = GoogleScholarClient()
    
    # Test with a well-known paper
    test_title = "From the gate to the neuromatrix"
    test_authors = ["Ronald Melzack"]
    test_year = 1999
    
    # Simulate that other databases found poor matches
    best_similarity = 0.3  # Low similarity to trigger fallback
    databases_searched = ["openalex", "pubmed", "dblp", "crossref"]  # Enough databases
    
    if client.should_search_google_scholar(best_similarity, databases_searched):
        results = client.search_papers(test_title, test_authors, test_year)
        
        if results:
            print(f"✅ Google Scholar test successful! Found {len(results)} results:")
            for i, result in enumerate(results):
                print(f"  {i+1}. {result.title}")
                print(f"     Authors: {', '.join(result.authors[:2])}{'...' if len(result.authors) > 2 else ''}")
                print(f"     Year: {result.year}, Venue: {result.venue}")
                if result.cited_by:
                    print(f"     Citations: {result.cited_by}")
                print()
        else:
            print("❌ Google Scholar test returned no results")
    else:
        print("ℹ️  Google Scholar test skipped (fallback conditions not met)")

if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(level=logging.INFO)
    test_google_scholar_client()
