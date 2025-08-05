"""
VerifyRef - Improved IACR Client with Enhanced Search and Historical Coverage
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
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
import feedparser
import re
import time
from urllib.parse import urljoin, quote_plus
from collections import Counter
import json

logger = logging.getLogger(__name__)

class IACRClient:
    """
    Improved IACR ePrint Archive client with multiple search strategies,
    better parsing, and enhanced historical paper coverage.
    
    Privacy Features:
    - Uses "Do Not Track" (DNT) header
    - Minimal browser fingerprinting 
    - Local-only caching (no persistent storage)
    - Privacy-conscious logging (no search query logging)
    - Only accesses publicly available academic data
    """
    
    def __init__(self):
        """Initialize improved IACR client"""
        self.base_url = "https://eprint.iacr.org"
        self.search_url = "https://eprint.iacr.org/search"
        self.rss_url = "https://eprint.iacr.org/rss/rss.xml"
        self.timeout = 30
        
        # Privacy-conscious session with minimal headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VerifyRef/1.0 (Academic Reference Verification Tool)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',  # Do Not Track
            'Connection': 'keep-alive',
        })
        
        # Multi-level caching
        self._web_cache = {}
        self._web_cache_timestamp = {}
        self._rss_cache = None
        self._rss_cache_timestamp = None
        
        # Cache timeouts (in seconds)
        self.web_cache_timeout = 1800  # 30 minutes
        self.rss_cache_timeout = 3600  # 1 hour
        
        # Respectful search approach - use minimal requests
        self.max_requests_per_search = 3  # Limit total requests per search
        self.request_delay = 2.0  # 2 second delay between requests
        self.request_count = 0  # Track requests made in current search
        
        # Simplified search strategies (less aggressive)
        self.search_strategies = [
            'primary_search',   # Main search only
            'rss_search'        # RSS fallback only
        ]
    
    def search_paper(self, title: str = None, authors: List[str] = None, 
                    year: int = None, venue: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Respectful search with minimal server load
        """
        if not title and not authors:
            return []
        
        # Privacy-conscious logging - avoid logging sensitive search queries
        search_type = "title" if title else "author"
        logger.info(f"Searching IACR database ({search_type} search, {len(authors) if authors else 0} authors)")
        
        all_results = []
        self.request_count = 0  # Reset instance counter
        
        # Generate only the most essential queries (limit to 2-3 max)
        essential_queries = self._generate_essential_queries(title, authors, year)
        
        # Try primary web search first (most important)
        if self.request_count < self.max_requests_per_search and essential_queries:
            try:
                # Use only the best query for web search
                best_query = essential_queries[0]
                web_results = self._search_web_strategy(best_query, 'primary_search', limit)
                all_results.extend(web_results)
                self.request_count += 1
                
                # Respectful delay
                if self.request_count < self.max_requests_per_search:
                    time.sleep(self.request_delay)
                    
            except Exception as e:
                logger.warning(f"Primary search failed: {type(e).__name__}")
        
        # Use RSS as fallback only if web search didn't find enough
        if len(all_results) < limit // 2:  # Only if we found very few results
            try:
                rss_results = self._search_rss_comprehensive(essential_queries, limit)
                all_results.extend(rss_results)
            except Exception as e:
                logger.warning(f"RSS search failed: {type(e).__name__}")
        
        # Remove duplicates and score results
        unique_results = self._deduplicate_results(all_results)
        scored_results = self._score_and_rank_results(unique_results, title, authors, year)
        
        logger.info(f"Found {len(scored_results)} unique papers from IACR (used {self.request_count} requests)")
        return scored_results[:limit]
    
    def _generate_essential_queries(self, title: str = None, authors: List[str] = None, 
                                   year: int = None) -> List[str]:
        """Generate only the most essential search queries to minimize server load"""
        queries = []
        
        if title:
            # Use only the most effective query format
            title_clean = self._clean_search_term(title)
            queries.append(title_clean)  # Simple title search
            
            # Add one additional variant only if title is complex
            if len(title_clean.split()) > 3:
                key_terms = self._extract_key_terms(title)[:3]  # Max 3 key terms
                if key_terms:
                    queries.append(' '.join(key_terms))
        
        if authors and not title:
            # For author-only searches, use the first author's last name
            first_author = authors[0]
            author_clean = self._clean_search_term(first_author)
            name_parts = author_clean.split()
            if len(name_parts) > 1:
                queries.append(name_parts[-1])  # Last name only
            else:
                queries.append(author_clean)
        
        # Limit to maximum 2 queries to be respectful
        return queries[:2]
    
    def _generate_search_queries(self, title: str = None, authors: List[str] = None, 
                                year: int = None) -> List[str]:
        """Generate multiple search query variations"""
        queries = []
        
        if title:
            # Clean title for search
            title_clean = self._clean_search_term(title)
            
            # Basic title search
            queries.append(title_clean)
            
            # Quoted title search
            queries.append(f'"{title_clean}"')
            
            # Key terms from title
            key_terms = self._extract_key_terms(title)
            if len(key_terms) > 1:
                queries.append(' '.join(key_terms))
                queries.append(' OR '.join(key_terms))
            
            # Title with year
            if year:
                queries.append(f"{title_clean} {year}")
                queries.append(f'"{title_clean}" {year}')
        
        if authors:
            for author in authors:
                author_clean = self._clean_search_term(author)
                
                # Author name search
                queries.append(author_clean)
                
                # Author with title keywords
                if title:
                    key_terms = self._extract_key_terms(title)[:3]  # Top 3 terms
                    if key_terms:
                        queries.append(f"{author_clean} {' '.join(key_terms)}")
                
                # Last name only (often more effective)
                name_parts = author_clean.split()
                if len(name_parts) > 1:
                    queries.append(name_parts[-1])  # Last name
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for query in queries:
            if query not in seen and query.strip():
                seen.add(query)
                unique_queries.append(query)
        
        return unique_queries[:10]  # Limit to top 10 queries
    
    def _clean_search_term(self, term: str) -> str:
        """Clean and normalize search terms"""
        if not term:
            return ""
        
        # Remove special characters but keep important ones
        cleaned = re.sub(r'[^\w\s\-\+\.\(\)]', ' ', term)
        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text for search"""
        if not text:
            return []
        
        # Common stop words to exclude
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'via', 'using', 'based', 'new'
        }
        
        # Extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter out stop words and get unique terms
        key_terms = []
        seen = set()
        for word in words:
            if word not in stop_words and word not in seen:
                key_terms.append(word)
                seen.add(word)
        
        return key_terms[:8]  # Return top 8 key terms
    
    def _search_web_strategy(self, query: str, strategy: str, limit: int) -> List[Dict[str, Any]]:
        """Execute specific web search strategy"""
        # Check cache first
        cache_key = f"{strategy}_{query}_{limit}"
        current_time = time.time()
        
        if (cache_key in self._web_cache and 
            cache_key in self._web_cache_timestamp and
            current_time - self._web_cache_timestamp[cache_key] < self.web_cache_timeout):
            return self._web_cache[cache_key]
        
        try:
            # Build search parameters based on strategy
            params = self._build_search_params(query, strategy)
            
            logger.debug(f"IACR {strategy} search initiated")
            response = self.session.get(self.search_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse results with improved methods
            papers = self._parse_search_results_improved(response.text)
            
            # Cache results
            self._web_cache[cache_key] = papers
            self._web_cache_timestamp[cache_key] = current_time
            
            logger.debug(f"IACR {strategy} found {len(papers)} papers")
            return papers
            
        except Exception as e:
            logger.warning(f"IACR {strategy} search failed: {type(e).__name__}")
            return []
    
    def _build_search_params(self, query: str, strategy: str) -> Dict[str, str]:
        """Build search parameters for different strategies"""
        base_params = {'q': query}
        
        if strategy == 'quoted_search':
            # Use exact phrase matching
            base_params['q'] = f'"{query}"'
        elif strategy == 'author_search':
            # Search in author fields specifically
            base_params['author'] = query
        elif strategy == 'year_range_search':
            # Add year constraints if possible
            # IACR search might support year parameters
            pass
        elif strategy == 'category_search':
            # Search within specific categories
            # Could be enhanced with category parameters
            pass
        
        return base_params
    
    def _parse_search_results_improved(self, html_content: str) -> List[Dict[str, Any]]:
        """Improved parsing with better title and author extraction"""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html_content, 'html.parser')
            papers = []
            
            # Look for search result containers
            # IACR typically uses specific patterns for search results
            result_containers = self._find_result_containers(soup)
            
            for container in result_containers:
                paper = self._extract_paper_from_container_improved(container)
                if paper and self._is_valid_paper(paper):
                    papers.append(paper)
            
            # Fallback to link-based extraction if no containers found
            if not papers:
                papers = self._fallback_link_extraction(soup)
            
            logger.debug(f"Improved parsing extracted {len(papers)} papers")
            return papers
            
        except ImportError:
            logger.warning("BeautifulSoup not available, using fallback parsing")
            return self._parse_search_results_regex(html_content)
        except Exception as e:
            logger.warning(f"Improved parsing failed: {e}")
            return self._parse_search_results_regex(html_content)
    
    def _find_result_containers(self, soup) -> List:
        """Find containers that likely contain search results"""
        containers = []
        
        # IACR specific: Look for individual paper entries within the results
        # The structure is typically one big results div with individual paper links
        
        # First, try to find the main results container
        results_container = soup.find('div', class_='results')
        
        if results_container:
            # Parse individual papers from the results container
            # Each paper typically starts with a year/number pattern
            paper_pattern = re.compile(r'/(\d{4}/\d+)')
            
            # Find all paper links
            paper_links = results_container.find_all('a', href=paper_pattern)
            
            # For each paper link, create a container with surrounding context
            for link in paper_links:
                if link.get('href', '').endswith('.pdf'):
                    continue  # Skip PDF links
                
                # Get the text context around this link
                container_text = self._extract_paper_context(link, results_container)
                if container_text:
                    # Create a pseudo-container with the extracted context
                    from bs4 import BeautifulSoup, Tag
                    pseudo_container = Tag(name='div')
                    pseudo_container.append(link)
                    pseudo_container._context_text = container_text
                    containers.append(pseudo_container)
        
        # Fallback to other container patterns
        if not containers:
            selectors = [
                'div.search-result',
                'div.paper-item', 
                'div.eprint-item',
                'div[class*="result"]',
                'div[class*="paper"]',
                'div[class*="entry"]',
                'li.search-result',
                'tr.paper-row'
            ]
            
            for selector in selectors:
                found = soup.select(selector)
                if found:
                    containers.extend(found)
                    break
        
        return containers[:100]  # Limit to prevent excessive processing
    
    def _extract_paper_context(self, paper_link, results_container) -> Optional[str]:
        """Extract text context around a paper link for better parsing"""
        try:
            # Get the full text of the results container
            full_text = results_container.get_text()
            
            # Find the paper ID in the text
            paper_href = paper_link.get('href', '')
            paper_id_match = re.search(r'/(\d{4}/\d+)', paper_href)
            if not paper_id_match:
                return None
            
            paper_id = paper_id_match.group(1)
            
            # Find where this paper appears in the text
            start_pos = full_text.find(paper_id)
            if start_pos == -1:
                return None
            
            # Get text starting from the paper ID
            # Structure is: PAPER_ID\n(PDF)\nLast updated: DATE\n\n\n\nTITLE\nAUTHOR\n\nCATEGORY\n\nABSTRACT
            
            # Find the next paper ID to know where this paper's content ends
            next_paper_pattern = r'\n(\d{4}/\d+)\n'
            text_after = full_text[start_pos:]
            next_paper_match = re.search(next_paper_pattern, text_after[1:])  # Skip current paper ID
            
            if next_paper_match:
                end_pos = start_pos + 1 + next_paper_match.start()
                paper_text = full_text[start_pos:end_pos]
            else:
                # Last paper - take next 1000 characters
                paper_text = text_after[:1000]
            
            # Parse the paper structure
            lines = paper_text.split('\n')
            
            # Skip the first few lines (paper ID, PDF, last updated, empty lines)
            content_start = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.strip() in [paper_id, '(PDF)'] and not line.strip().startswith('Last updated:'):
                    content_start = i
                    break
            
            if content_start < len(lines):
                # Extract title (first non-empty content line)
                title = lines[content_start].strip() if content_start < len(lines) else ""
                
                # Extract author (next non-empty line after title)
                author = ""
                category = ""
                for i in range(content_start + 1, min(content_start + 10, len(lines))):
                    line = lines[i].strip()
                    if line and not author:
                        # Check if this looks like an author name vs category
                        if self._looks_like_author_line(line):
                            author = line
                        elif not category and self._looks_like_category(line):
                            category = line
                            break
                    elif line and author and not category:
                        if self._looks_like_category(line):
                            category = line
                            break
                
                return f"TITLE: {title}\nAUTHOR: {author}\nCATEGORY: {category}"
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to extract paper context: {e}")
            return None
    
    def _looks_like_author_line(self, line: str) -> bool:
        """Check if a line looks like author names"""
        if not line or len(line) < 3:
            return False
        
        # Has proper name capitalization
        has_proper_names = bool(re.search(r'\b[A-Z][a-z]+\b', line))
        
        # Not a known category
        categories = [
            'public-key cryptography', 'symmetric cryptography', 'cryptographic protocols',
            'foundations', 'implementation', 'attacks and cryptanalysis',
            'secret-key cryptography', 'hash functions', 'digital signatures'
        ]
        is_category = any(cat.lower() in line.lower() for cat in categories)
        
        # Not too long (categories tend to be longer descriptions)
        reasonable_length = len(line) <= 100
        
        # Has name patterns (commas, multiple capital letters)
        has_name_patterns = ',' in line or len(re.findall(r'\b[A-Z][a-z]+', line)) >= 2
        
        return has_proper_names and not is_category and reasonable_length and has_name_patterns
    
    def _looks_like_category(self, line: str) -> bool:
        """Check if a line looks like a category"""
        if not line:
            return False
        
        categories = [
            'public-key cryptography', 'symmetric cryptography', 'cryptographic protocols',
            'foundations', 'implementation', 'attacks and cryptanalysis',
            'secret-key cryptography', 'hash functions', 'digital signatures'
        ]
        
        return any(cat.lower() in line.lower() for cat in categories)
    
    def _extract_paper_from_container_improved(self, container) -> Optional[Dict[str, Any]]:
        """Extract paper info from container with improved title/author parsing"""
        try:
            # Find the main paper link
            paper_link = container.find('a', href=re.compile(r'/\d{4}/\d+/?$'))
            if not paper_link:
                return None
            
            href = paper_link.get('href', '')
            
            # Extract paper ID and year
            match = re.search(r'/(\d{4}/\d+)/?$', href)
            if not match:
                return None
            
            paper_id = match.group(1)
            year_match = re.search(r'^(\d{4})/', paper_id)
            year = int(year_match.group(1)) if year_match else None
            
            # Build absolute URL
            url = urljoin(self.base_url, href)
            
            # Extract title and authors using context if available
            title = ""
            authors = []
            category = ""
            
            if hasattr(container, '_context_text') and container._context_text:
                # Parse from extracted context
                context = container._context_text
                lines = context.split('\n')
                for line in lines:
                    if line.startswith('TITLE: '):
                        title = line[7:].strip()  # Remove "TITLE: " prefix
                    elif line.startswith('AUTHOR: '):
                        author_text = line[8:].strip()  # Remove "AUTHOR: " prefix
                        if author_text:
                            authors = self._parse_author_text(author_text)
                    elif line.startswith('CATEGORY: '):
                        category = line[10:].strip()  # Remove "CATEGORY: " prefix
            
            # Fallback to traditional extraction if context parsing failed
            if not title:
                title = self._extract_title_improved(container, paper_link)
            if not authors:
                authors = self._extract_authors_improved(container)
            
            if not title or len(title) < 5:
                return None
            
            # Extract additional metadata
            if not category:
                category = self._extract_category(container)
            description = self._extract_description(container)
            
            return {
                'title': title,
                'authors': authors,
                'venue': 'IACR Cryptology ePrint Archive',
                'year': year,
                'url': url,
                'paper_id': paper_id,
                'category': category,
                'description': description,
                'source': 'IACR'
            }
            
        except Exception as e:
            logger.debug(f"Failed to extract paper from container: {e}")
            return None
    
    def _parse_content_line(self, content: str) -> Tuple[str, List[str]]:
        """Parse title and authors from a content line"""
        if not content:
            return "", []
        
        # Common IACR format: "Title.AuthorCategory" or "Title Author Category"
        title = ""
        authors = []
        
        # Method 1: Split by period (title.author format)
        if '.' in content:
            parts = content.split('.', 1)
            if len(parts) >= 2:
                potential_title = parts[0].strip()
                potential_author = parts[1].strip()
                
                # Check if this looks like a reasonable split
                if (len(potential_title) > 5 and 
                    len(potential_title) < 150 and
                    self._looks_like_title(potential_title)):
                    title = potential_title
                    
                    # Parse author from remaining text
                    # Often format is "AuthorNameCategory" - need to separate
                    authors = self._extract_author_from_mixed_text(potential_author)
        
        # Method 2: Look for capital letter patterns (AuthorName)
        if not title:
            # Find where author names might start (capital letters)
            words = content.split()
            title_end = -1
            
            for i, word in enumerate(words):
                if (i > 2 and  # Not in first few words
                    len(word) > 2 and 
                    word[0].isupper() and
                    word.isalpha()):  # Likely start of author name
                    title_end = i
                    break
            
            if title_end > 0:
                title = ' '.join(words[:title_end])
                author_text = ' '.join(words[title_end:])
                authors = self._extract_author_from_mixed_text(author_text)
        
        # Fallback: Use whole content as title
        if not title:
            title = content
        
        return self._clean_title(title), authors
    
    def _looks_like_title(self, text: str) -> bool:
        """Check if text looks like a paper title"""
        if not text or len(text) < 5:
            return False
        
        # Has some lowercase letters (not all caps)
        has_lowercase = bool(re.search(r'[a-z]', text))
        
        # Not just author name pattern
        not_just_name = not re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', text.strip())
        
        # Reasonable length
        reasonable_length = 5 <= len(text) <= 200
        
        return has_lowercase and not_just_name and reasonable_length
    
    def _extract_author_from_mixed_text(self, text: str) -> List[str]:
        """Extract author names from mixed text that may contain category info"""
        if not text:
            return []
        
        # Common categories that might appear after author names
        categories = [
            'public-key cryptography', 'symmetric cryptography', 'cryptographic protocols',
            'foundations', 'implementation', 'attacks and cryptanalysis',
            'secret-key cryptography', 'hash functions', 'digital signatures'
        ]
        
        # Remove known categories
        text_clean = text
        for category in categories:
            text_clean = re.sub(re.escape(category), '', text_clean, flags=re.IGNORECASE)
        
        # Remove common non-author patterns
        text_clean = re.sub(r'\b(abstract|introduction|conclusion|references)\b', '', text_clean, flags=re.IGNORECASE)
        text_clean = re.sub(r'\s+', ' ', text_clean).strip()
        
        # Parse the remaining text as authors
        if text_clean:
            return self._parse_author_text(text_clean)
        
        return []
    
    def _extract_title_improved(self, container, paper_link) -> str:
        """Extract title with improved accuracy"""
        # Method 1: Link text if it looks like a title
        link_text = paper_link.get_text(strip=True)
        if link_text and len(link_text) > 10 and not re.match(r'^\d{4}/\d+', link_text):
            return self._clean_title(link_text)
        
        # Method 2: Look for title in specific elements
        title_selectors = [
            '.title', '.paper-title', '.entry-title',
            'h1', 'h2', 'h3', 'h4',
            '.name', '.heading'
        ]
        
        for selector in title_selectors:
            element = container.select_one(selector)
            if element:
                title_text = element.get_text(strip=True)
                if title_text and len(title_text) > 10:
                    return self._clean_title(title_text)
        
        # Method 3: Extract from container text structure
        container_text = container.get_text(separator='\n', strip=True)
        lines = container_text.split('\n')
        
        # Look for the longest line that could be a title
        for line in lines:
            line = line.strip()
            if (len(line) > 15 and 
                len(line) < 200 and  # Reasonable title length
                not re.match(r'^\d{4}/\d+', line) and  # Not a paper ID
                not line.lower().startswith('last updated') and
                not line.lower().startswith('by ') and
                not re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', line)):  # Not likely author name
                
                return self._clean_title(line)
        
        # Method 4: Fallback to link text even if short
        if link_text:
            return self._clean_title(link_text)
        
        return ""
    
    def _extract_authors_improved(self, container) -> List[str]:
        """Extract authors with improved accuracy"""
        authors = []
        
        # Method 1: Look for author-specific elements
        author_selectors = [
            '.authors', '.author', '.by-author',
            '[class*="author"]', '[class*="by"]'
        ]
        
        for selector in author_selectors:
            elements = container.select(selector)
            for element in elements:
                author_text = element.get_text(strip=True)
                if author_text:
                    parsed_authors = self._parse_author_text(author_text)
                    if parsed_authors:
                        authors.extend(parsed_authors)
        
        # Method 2: Look for italic text (often used for authors)
        if not authors:
            italic_elements = container.find_all(['i', 'em'])
            for element in italic_elements:
                author_text = element.get_text(strip=True)
                if author_text and self._looks_like_author_text(author_text):
                    parsed_authors = self._parse_author_text(author_text)
                    if parsed_authors:
                        authors.extend(parsed_authors)
        
        # Method 3: Pattern matching in container text
        if not authors:
            container_text = container.get_text(separator=' ', strip=True)
            
            # Look for "by Author" patterns
            by_pattern = r'\bby\s+([A-Z][a-z]+ (?:[A-Z][a-z]+ )*[A-Z][a-z]+(?:,\s*[A-Z][a-z]+ (?:[A-Z][a-z]+ )*[A-Z][a-z]+)*)'
            match = re.search(by_pattern, container_text)
            if match:
                author_text = match.group(1)
                parsed_authors = self._parse_author_text(author_text)
                if parsed_authors:
                    authors.extend(parsed_authors)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_authors = []
        for author in authors:
            if author and author not in seen:
                seen.add(author)
                unique_authors.append(author)
        
        return unique_authors[:10]  # Limit to reasonable number
    
    def _parse_author_text(self, text: str) -> List[str]:
        """Parse author text into individual names"""
        if not text:
            return []
        
        # Clean up the text
        text = re.sub(r'^by\s+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\([^)]*\)\s*', ' ', text)  # Remove parentheses
        text = re.sub(r'\s*\{[^}]*\}\s*', ' ', text)  # Remove braces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split by common delimiters
        authors = []
        
        if ' and ' in text:
            authors = [a.strip() for a in text.split(' and ')]
        elif ',' in text:
            authors = [a.strip() for a in text.split(',')]
        else:
            # Single author or simple space-separated
            words = text.split()
            if len(words) <= 6:  # Likely single author
                authors = [text]
        
        # Filter valid author names
        valid_authors = []
        for author in authors:
            if self._is_valid_author_name(author):
                valid_authors.append(author)
        
        return valid_authors
    
    def _looks_like_author_text(self, text: str) -> bool:
        """Check if text looks like author information"""
        if not text or len(text) < 3:
            return False
        
        # Has proper name patterns
        has_names = bool(re.search(r'\b[A-Z][a-z]+\b', text))
        
        # Reasonable length
        reasonable_length = 5 <= len(text) <= 200
        
        # Not obviously something else
        not_title = not (len(text) > 50 and text.count(' ') > 8)
        not_description = not text.lower().startswith(('abstract', 'we ', 'this ', 'in this'))
        
        return has_names and reasonable_length and not_title and not_description
    
    def _is_valid_author_name(self, name: str) -> bool:
        """Check if a name looks like a valid author name"""
        if not name or len(name) < 2:
            return False
        
        # Has at least one capital letter
        has_capital = bool(re.search(r'[A-Z]', name))
        
        # Not too long
        reasonable_length = len(name) <= 50
        
        # Has letters
        has_letters = bool(re.search(r'[a-zA-Z]', name))
        
        # Not obviously not a name
        not_junk = not re.match(r'^[^a-zA-Z]*$', name)
        
        return has_capital and reasonable_length and has_letters and not_junk
    
    def _clean_title(self, title: str) -> str:
        """Clean and normalize title text"""
        if not title:
            return ""
        
        # Remove excessive whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Remove common prefixes/suffixes
        title = re.sub(r'^(PDF\s*|Download\s*)', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*(PDF|Download)$', '', title, flags=re.IGNORECASE)
        
        # Remove paper ID if present
        title = re.sub(r'^\d{4}/\d+\s*', '', title)
        
        # Remove dates
        title = re.sub(r'\s*\d{4}-\d{2}-\d{2}\s*', ' ', title)
        
        # Clean up punctuation
        title = re.sub(r'\s*[\.]+\s*$', '', title)  # Remove trailing dots
        
        return title.strip()
    
    def _extract_category(self, container) -> str:
        """Extract paper category/subject"""
        selectors = [
            '.category', '.subject', '.classification',
            '[class*="category"]', '[class*="subject"]'
        ]
        
        for selector in selectors:
            element = container.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        return ""
    
    def _extract_description(self, container) -> str:
        """Extract paper description/abstract"""
        selectors = [
            '.abstract', '.description', '.summary',
            '[class*="abstract"]', '[class*="description"]'
        ]
        
        for selector in selectors:
            element = container.select_one(selector)
            if element:
                desc = element.get_text(strip=True)
                if len(desc) > 50:  # Reasonable description length
                    return desc[:500]  # Truncate if too long
        
        return ""
    
    def _fallback_link_extraction(self, soup) -> List[Dict[str, Any]]:
        """Fallback method to extract papers from links"""
        papers = []
        paper_pattern = re.compile(r'/(\d{4}/\d+)/?$')
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            match = paper_pattern.search(href)
            
            if match and not href.endswith('.pdf'):
                paper_id = match.group(1)
                year_match = re.search(r'^(\d{4})/', paper_id)
                year = int(year_match.group(1)) if year_match else None
                
                title = link.get_text(strip=True)
                if title and len(title) > 5:
                    url = urljoin(self.base_url, href)
                    
                    papers.append({
                        'title': self._clean_title(title),
                        'authors': [],
                        'venue': 'IACR Cryptology ePrint Archive',
                        'year': year,
                        'url': url,
                        'paper_id': paper_id,
                        'category': '',
                        'description': '',
                        'source': 'IACR'
                    })
        
        return papers
    
    def _parse_search_results_regex(self, html_content: str) -> List[Dict[str, Any]]:
        """Regex-based parsing fallback"""
        papers = []
        
        # Enhanced regex patterns
        patterns = [
            # Pattern 1: href="PAPER_URL">TITLE</a>
            r'href=["\']([^"\']*?/(?:\d{4}/\d+)/?)["\'][^>]*>([^<]+)</a>',
            # Pattern 2: More flexible link patterns
            r'<a[^>]+href=["\']([^"\']*?/(?:\d{4}/\d+)/?)["\'][^>]*>([^<]+?)</a>',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            
            for url, title in matches:
                # Make URL absolute
                if url.startswith('/'):
                    url = self.base_url + url
                
                # Extract paper ID and year
                paper_id = ''
                year = None
                match = re.search(r'/(\d{4}/\d+)/?$', url)
                if match:
                    paper_id = match.group(1)
                    year_match = re.search(r'^(\d{4})/', paper_id)
                    if year_match:
                        year = int(year_match.group(1))
                
                title_clean = self._clean_title(title)
                if title_clean and len(title_clean) > 5:
                    papers.append({
                        'title': title_clean,
                        'authors': [],
                        'venue': 'IACR Cryptology ePrint Archive',
                        'year': year,
                        'url': url,
                        'paper_id': paper_id,
                        'category': '',
                        'description': '',
                        'source': 'IACR'
                    })
        
        return papers
    
    def _is_valid_paper(self, paper: Dict[str, Any]) -> bool:
        """Check if extracted paper data is valid"""
        return (
            paper.get('title') and 
            len(paper['title']) > 5 and
            paper.get('paper_id') and
            paper.get('url')
        )
    
    def _search_rss_comprehensive(self, queries: List[str], limit: int) -> List[Dict[str, Any]]:
        """Enhanced RSS search with multiple query matching"""
        try:
            papers = self._get_papers_from_rss()
            if not papers:
                return []
            
            results = []
            for paper in papers:
                best_score = 0.0
                
                # Test each query against the paper
                for query in queries:
                    score = self._calculate_text_similarity(query, paper)
                    best_score = max(best_score, score)
                
                if best_score > 0.1:  # Minimum relevance threshold
                    paper['match_score'] = best_score
                    results.append(paper)
            
            # Sort by score
            results.sort(key=lambda x: x.get('match_score', 0), reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.warning(f"RSS comprehensive search failed: {e}")
            return []
    
    def _get_papers_from_rss(self) -> List[Dict[str, Any]]:
        """Get papers from RSS feed with caching"""
        current_time = time.time()
        
        # Check cache
        if (self._rss_cache is not None and 
            self._rss_cache_timestamp is not None and 
            current_time - self._rss_cache_timestamp < self.rss_cache_timeout):
            return self._rss_cache
        
        try:
            logger.debug("Fetching IACR RSS feed")
            response = self.session.get(self.rss_url, timeout=self.timeout)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            papers = []
            
            for entry in feed.entries:
                paper = self._parse_rss_entry_improved(entry)
                if paper:
                    papers.append(paper)
            
            # Update cache
            self._rss_cache = papers
            self._rss_cache_timestamp = current_time
            
            logger.debug(f"RSS feed loaded {len(papers)} papers")
            return papers
            
        except Exception as e:
            logger.error(f"Failed to fetch IACR RSS: {e}")
            return []
    
    def _parse_rss_entry_improved(self, entry) -> Optional[Dict[str, Any]]:
        """Parse RSS entry with improved data extraction"""
        try:
            title = entry.get('title', '').strip()
            if not title:
                return None
            
            # Extract authors - try multiple methods
            authors = []
            if hasattr(entry, 'authors') and entry.authors:
                for author in entry.authors:
                    if hasattr(author, 'name') and author.name:
                        authors.append(author.name)
            elif hasattr(entry, 'author') and entry.author:
                authors.append(entry.author)
            
            # Extract year
            year = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                year = entry.published_parsed.tm_year
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                year = entry.updated_parsed.tm_year
            
            # Extract URL and paper ID
            url = entry.get('link', '')
            paper_id = ''
            if url:
                match = re.search(r'/(\d{4}/\d+)/?$', url)
                if match:
                    paper_id = match.group(1)
                    # Double check year from paper ID
                    year_match = re.search(r'^(\d{4})/', paper_id)
                    if year_match and not year:
                        year = int(year_match.group(1))
            
            # Extract category/subject
            category = ''
            if hasattr(entry, 'tags') and entry.tags:
                for tag in entry.tags:
                    if hasattr(tag, 'term') and tag.term:
                        category = tag.term
                        break
            elif hasattr(entry, 'category') and entry.category:
                category = entry.category
            
            # Extract description
            description = entry.get('summary', '').strip()
            
            return {
                'title': title,
                'authors': authors,
                'venue': 'IACR Cryptology ePrint Archive',
                'year': year,
                'url': url,
                'paper_id': paper_id,
                'category': category,
                'description': description,
                'source': 'IACR'
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse RSS entry: {e}")
            return None
    
    def _deduplicate_results(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate papers based on multiple criteria"""
        seen_ids = set()
        seen_titles = set()
        unique_papers = []
        
        for paper in papers:
            paper_id = paper.get('paper_id', '')
            title = paper.get('title', '').lower().strip()
            
            # Primary deduplication by paper ID
            if paper_id and paper_id not in seen_ids:
                seen_ids.add(paper_id)
                unique_papers.append(paper)
            # Secondary deduplication by normalized title
            elif not paper_id and title and title not in seen_titles:
                seen_titles.add(title)
                unique_papers.append(paper)
        
        return unique_papers
    
    def _score_and_rank_results(self, papers: List[Dict[str, Any]], 
                               title: str = None, authors: List[str] = None, 
                               year: int = None) -> List[Dict[str, Any]]:
        """Enhanced scoring and ranking of search results"""
        scored_papers = []
        
        for paper in papers:
            score = self._calculate_enhanced_match_score(paper, title, authors, year)
            if score > 0.01:  # Very low threshold to include more results
                paper['match_score'] = score
                scored_papers.append(paper)
        
        # Sort by match score (descending)
        scored_papers.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        return scored_papers
    
    def _calculate_enhanced_match_score(self, paper: Dict[str, Any], 
                                      title: str = None, authors: List[str] = None, 
                                      year: int = None) -> float:
        """Enhanced match scoring with multiple factors"""
        score = 0.0
        
        # Title matching (most important factor)
        if title:
            title_score = self._calculate_title_score(paper.get('title', ''), title)
            score += title_score * 0.6
        
        # Author matching
        if authors:
            author_score = self._calculate_author_score(paper.get('authors', []), authors)
            score += author_score * 0.25
        
        # Year matching
        if year and paper.get('year'):
            year_score = self._calculate_year_score(paper['year'], year)
            score += year_score * 0.1
        
        # Description/abstract matching
        if title and paper.get('description'):
            desc_score = self._calculate_description_score(paper['description'], title)
            score += desc_score * 0.05
        
        return min(score, 1.0)
    
    def _calculate_title_score(self, paper_title: str, search_title: str) -> float:
        """Calculate title similarity score"""
        if not paper_title or not search_title:
            return 0.0
        
        paper_title_lower = paper_title.lower()
        search_title_lower = search_title.lower()
        
        # Exact match gets highest score
        if paper_title_lower == search_title_lower:
            return 1.0
        
        # Substring matches
        if search_title_lower in paper_title_lower:
            return 0.8
        if paper_title_lower in search_title_lower:
            return 0.7
        
        # Word-based matching
        search_words = set(self._extract_key_terms(search_title_lower))
        paper_words = set(self._extract_key_terms(paper_title_lower))
        
        if not search_words:
            return 0.0
        
        # Jaccard similarity
        intersection = search_words.intersection(paper_words)
        union = search_words.union(paper_words)
        
        if union:
            jaccard_score = len(intersection) / len(union)
        else:
            jaccard_score = 0.0
        
        # Overlap ratio
        overlap_ratio = len(intersection) / len(search_words) if search_words else 0.0
        
        # Combined score
        return max(jaccard_score * 0.6, overlap_ratio * 0.4)
    
    def _calculate_author_score(self, paper_authors: List[str], search_authors: List[str]) -> float:
        """Calculate author matching score"""
        if not paper_authors or not search_authors:
            return 0.0
        
        total_score = 0.0
        for search_author in search_authors:
            best_match = 0.0
            search_author_lower = search_author.lower()
            search_parts = search_author_lower.split()
            
            for paper_author in paper_authors:
                paper_author_lower = paper_author.lower()
                paper_parts = paper_author_lower.split()
                
                # Exact match
                if search_author_lower == paper_author_lower:
                    best_match = 1.0
                    break
                
                # Last name match (common in academic citations)
                if (search_parts and paper_parts and 
                    search_parts[-1] == paper_parts[-1]):
                    best_match = max(best_match, 0.8)
                
                # First initial + last name match
                if (len(search_parts) >= 2 and len(paper_parts) >= 2 and
                    search_parts[0][0] == paper_parts[0][0] and
                    search_parts[-1] == paper_parts[-1]):
                    best_match = max(best_match, 0.7)
                
                # Substring match
                if search_author_lower in paper_author_lower or paper_author_lower in search_author_lower:
                    best_match = max(best_match, 0.5)
            
            total_score += best_match
        
        return total_score / len(search_authors)
    
    def _calculate_year_score(self, paper_year: int, search_year: int) -> float:
        """Calculate year matching score"""
        if paper_year == search_year:
            return 1.0
        elif abs(paper_year - search_year) == 1:
            return 0.5
        elif abs(paper_year - search_year) <= 2:
            return 0.2
        else:
            return 0.0
    
    def _calculate_description_score(self, description: str, search_title: str) -> float:
        """Calculate description relevance score"""
        if not description or not search_title:
            return 0.0
        
        description_lower = description.lower()
        search_terms = self._extract_key_terms(search_title.lower())
        
        if not search_terms:
            return 0.0
        
        matches = 0
        for term in search_terms:
            if term in description_lower:
                matches += 1
        
        return matches / len(search_terms)
    
    def _calculate_text_similarity(self, query: str, paper: Dict[str, Any]) -> float:
        """Calculate general text similarity for fallback searches"""
        if not query:
            return 0.0
        
        query_terms = set(self._extract_key_terms(query.lower()))
        if not query_terms:
            return 0.0
        
        # Combine all paper text
        paper_text = ' '.join([
            paper.get('title', ''),
            ' '.join(paper.get('authors', [])),
            paper.get('description', ''),
            paper.get('category', '')
        ]).lower()
        
        paper_terms = set(self._extract_key_terms(paper_text))
        
        if not paper_terms:
            return 0.0
        
        # Calculate overlap
        intersection = query_terms.intersection(paper_terms)
        return len(intersection) / len(query_terms) if query_terms else 0.0
    
    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Verify a reference against IACR database"""
        title = reference.get('title', '')
        authors = reference.get('authors', [])
        year = reference.get('year')
        
        return self.search_paper(title=title, authors=authors, year=year)
    
    def is_available(self) -> bool:
        """Check if IACR service is available"""
        try:
            response = self.session.get(self.base_url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False
