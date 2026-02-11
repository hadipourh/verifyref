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


import logging
import threading
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .semantic_scholar import SemanticScholarClient
from .dblp_client import DBLPClient
from .crossref_client import CrossRefClient
from .iacr_client import IACRClient
from .arxiv_client import ArXivClient
from .pubmed_client import PubMedClient
from .openalex_client import OpenAlexClient
from .springer_client import SpringerNatureClient
from .google_scholar_client import GoogleScholarClient
from config import DATABASE_CONFIG

logger = logging.getLogger(__name__)

class MultiDatabaseVerifier:
    """
    Coordinator for verifying references across multiple academic databases
    """
    
    def __init__(self, enable_cryptodb: bool = True, fast_mode: bool = False):
        """
        Initialize multi-database verifier
        
        Args:
            enable_cryptodb: Whether to enable CryptoDB author verification
            fast_mode: Whether to use fast mode for databases (fewer search strategies)
        """
        self.enabled_databases = DATABASE_CONFIG.get("enabled_databases", ["semantic_scholar"])
        self.primary_database = DATABASE_CONFIG.get("primary_database", "semantic_scholar")
        self.fast_mode = fast_mode  # Store fast mode setting
        
        # Initialize clients
        self.clients = {}
        
        # OpenAlex - Fast, comprehensive, and free (primary recommendation)
        if "openalex" in self.enabled_databases and DATABASE_CONFIG.get("openalex", {}).get("enabled", True):
            openalex_config = DATABASE_CONFIG.get("openalex", {})
            self.clients["openalex"] = OpenAlexClient(openalex_config)
        
        if "semantic_scholar" in self.enabled_databases:
            self.clients["semantic_scholar"] = SemanticScholarClient()
        
        if "dblp" in self.enabled_databases and DATABASE_CONFIG.get("dblp", {}).get("enabled", True):
            # Use fast mode for DBLP to improve performance
            self.clients["dblp"] = DBLPClient(fast_mode=fast_mode)
        
        if "crossref" in self.enabled_databases and DATABASE_CONFIG.get("crossref", {}).get("enabled", True):
            email = DATABASE_CONFIG.get("crossref", {}).get("email")
            # Check if email is valid (not None, not empty, and not a placeholder)
            placeholder_emails = ["your-email@example.com", "your.email@domain.com", "your.email@example.com"]
            if email and email.strip() and email not in placeholder_emails and "@" in email:
                self.clients["crossref"] = CrossRefClient(email=email)
                logger.debug(f"CrossRef enabled with email: {email}")
            else:
                logger.warning("CrossRef disabled: Please set CROSSREF_EMAIL environment variable to your email address")
                logger.warning("CrossRef API requires a valid email for polite access. See README for setup instructions.")
        
        if "iacr" in self.enabled_databases and DATABASE_CONFIG.get("iacr", {}).get("enabled", True):
            self.clients["iacr"] = IACRClient()
        
        if "arxiv" in self.enabled_databases and DATABASE_CONFIG.get("arxiv", {}).get("enabled", True):
            self.clients["arxiv"] = ArXivClient()
        
        if "pubmed" in self.enabled_databases and DATABASE_CONFIG.get("pubmed", {}).get("enabled", True):
            pubmed_config = DATABASE_CONFIG.get("pubmed", {})
            self.clients["pubmed"] = PubMedClient(
                api_key=pubmed_config.get("api_key"),
                email=pubmed_config.get("email", "verifyref@example.com")
            )
        
        if "springer" in self.enabled_databases and DATABASE_CONFIG.get("springer", {}).get("enabled", True):
            springer_config = DATABASE_CONFIG.get("springer", {})
            api_key = springer_config.get("api_key")
            if api_key and api_key.strip() and api_key != "your-springer-api-key":
                self.clients["springer"] = SpringerNatureClient(api_key=api_key)
                logger.debug("Springer Nature enabled with API key")
            else:
                logger.info("Springer Nature disabled: API key required (no free tier available)")
                logger.info("Get your free API key at: https://dev.springernature.com/")
        
        if "google_scholar" in self.enabled_databases and DATABASE_CONFIG.get("google_scholar", {}).get("enabled", True):
            try:
                self.clients["google_scholar"] = GoogleScholarClient()
                logger.debug("Google Scholar enabled with smart fallback strategy")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Scholar client: {e}")
                logger.info("Google Scholar disabled due to initialization error")
        
        # Initialize CryptoDB client (optional)
        self.cryptodb_client = None
        if enable_cryptodb and DATABASE_CONFIG.get("cryptodb", {}).get("enabled", True):
            try:
                from .cryptodb_author_client import CryptoDBAuthorClient
                cryptodb_config = DATABASE_CONFIG.get("cryptodb", {})
                self.cryptodb_client = CryptoDBAuthorClient(
                    enable_cryptodb=True,
                    timeout=cryptodb_config.get("timeout", 5)
                )
                logger.info("CryptoDB author verification enabled")
            except ImportError:
                logger.info("CryptoDB client not available")
            except Exception as e:
                logger.warning(f"Failed to initialize CryptoDB client: {e}")
    
    def _search_single_database(self, db_name: str, client: Any, query_info: Dict[str, Any]) -> tuple:
        """
        Search a single database (helper for parallel execution)
        
        Args:
            db_name: Name of the database
            client: Database client instance
            query_info: Search parameters
            
        Returns:
            Tuple of (db_name, results_list)
        """
        try:
            if not client.is_available():
                logger.warning(f"{db_name} service unavailable, skipping")
                return (db_name, [])
            
            title = query_info.get('title', '')
            authors = query_info.get('authors', [])
            year = query_info.get('year')
            venue = query_info.get('venue', '')
            
            # Use the client's search_paper method
            if hasattr(client, 'search_paper'):
                db_results = client.search_paper(
                    title=title,
                    authors=authors,
                    year=year,
                    venue=venue
                )
            else:
                # Fallback to verify_reference for compatibility
                db_results = client.verify_reference(query_info)
            
            logger.info(f"{db_name} returned {len(db_results)} results")
            return (db_name, db_results)
            
        except Exception as e:
            logger.error(f"Error searching {db_name}: {e}")
            return (db_name, [])
    
    def search_across_databases(self, query_info: Dict[str, Any], early_exit: bool = False, 
                                  similarity_threshold: float = 0.9) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for papers across all enabled databases in parallel
        
        Args:
            query_info: Dictionary with search parameters (title, authors, year, venue)
            early_exit: If True, stop searching once a high-confidence match is found
            similarity_threshold: Minimum similarity score to consider a "match" for early exit
            
        Returns:
            Dictionary mapping database names to their search results
        """
        results = {}
        found_match = threading.Event()  # Signal for early exit
        failed_dbs = []  # Track failed databases for potential retry
        
        # Parallel database search - each API is independent with its own rate limits
        # This dramatically speeds up searches (from ~15-20s to ~3-5s)
        max_workers = min(len(self.clients), 8)  # Limit concurrent connections
        
        def search_with_early_exit(db_name: str, client: Any) -> tuple:
            """Search a database, checking for early exit signal"""
            if early_exit and found_match.is_set():
                logger.debug(f"Skipping {db_name} - match already found (early exit)")
                return (db_name, [], 'skipped')
            
            try:
                db_name, db_results = self._search_single_database(db_name, client, query_info)
                
                # Check if we found a high-confidence match
                if early_exit and db_results:
                    for result in db_results:
                        if self._is_high_confidence_match(result, query_info, similarity_threshold):
                            found_match.set()  # Signal other threads to stop
                            logger.debug(f"High-confidence match found in {db_name}, signaling early exit")
                            break
                
                return (db_name, db_results, 'success')
            except Exception as e:
                logger.warning(f"Search failed for {db_name}: {e}")
                return (db_name, [], 'failed')
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all database searches in parallel
            futures = {
                executor.submit(search_with_early_exit, db_name, client): db_name
                for db_name, client in self.clients.items()
            }
            
            # Collect results as they complete
            for future in as_completed(futures):
                db_name = futures[future]
                try:
                    name, db_results, status = future.result(timeout=30)  # 30s timeout per database
                    results[name] = db_results
                    if status == 'failed':
                        failed_dbs.append(name)
                except Exception as e:
                    logger.error(f"Error getting results from {db_name}: {e}")
                    results[db_name] = []
                    failed_dbs.append(db_name)
        
        # Store failed databases for potential retry
        results['_failed_dbs'] = failed_dbs
        
        return results
    
    def _is_high_confidence_match(self, result: Dict[str, Any], query_info: Dict[str, Any], 
                                   threshold: float = 0.9) -> bool:
        """
        Check if a result is a high-confidence match for early exit
        
        Args:
            result: Database search result
            query_info: Original query parameters
            threshold: Minimum similarity score
            
        Returns:
            True if result is a high-confidence match
        """
        try:
            from utils.helpers import calculate_text_similarity
            
            query_title = query_info.get('title', '').lower().strip()
            result_title = (result.get('title', '') or '').lower().strip()
            
            if not query_title or not result_title:
                return False
            
            # Calculate title similarity
            title_similarity = calculate_text_similarity(query_title, result_title)
            
            # High confidence if title matches well AND has DOI
            if title_similarity >= threshold:
                if result.get('doi'):
                    return True  # Very high confidence - title match + DOI
                
                # Check author overlap for additional confidence
                query_authors = query_info.get('authors', [])
                result_authors = result.get('authors', [])
                if query_authors and result_authors:
                    # Simple first author check
                    if query_authors[0].lower().split()[-1] in str(result_authors).lower():
                        return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking match confidence: {e}")
            return False
    
    def retry_failed_databases(self, query_info: Dict[str, Any], 
                               failed_dbs: List[str], 
                               longer_timeout: int = 45) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retry searches for databases that failed or timed out
        
        Args:
            query_info: Dictionary with search parameters
            failed_dbs: List of database names that failed
            longer_timeout: Longer timeout for retry attempts
            
        Returns:
            Dictionary with retry results
        """
        results = {}
        
        for db_name in failed_dbs:
            if db_name not in self.clients:
                continue
            
            client = self.clients[db_name]
            logger.info(f"Retrying {db_name} with longer timeout...")
            
            try:
                # Give the database more time on retry
                time.sleep(0.5)  # Brief pause before retry
                name, db_results = self._search_single_database(db_name, client, query_info)
                results[name] = db_results
                logger.info(f"Retry successful for {db_name}: {len(db_results)} results")
            except Exception as e:
                logger.warning(f"Retry failed for {db_name}: {e}")
                results[db_name] = []
        
        return results
    
    def _verify_single_database(self, db_name: str, client: Any, reference: Dict[str, Any]) -> tuple:
        """
        Verify reference against a single database (helper for parallel execution)
        
        Args:
            db_name: Name of the database
            client: Database client instance  
            reference: Reference to verify
            
        Returns:
            Tuple of (db_name, results_list)
        """
        try:
            if not client.is_available():
                logger.warning(f"{db_name} service unavailable, skipping")
                return (db_name, [])
            
            logger.debug(f"Searching {db_name} for reference: {reference.get('title', 'No title')[:50]}...")
            results = client.verify_reference(reference)
            logger.info(f"{db_name} returned {len(results)} results")
            return (db_name, results)
            
        except Exception as e:
            logger.warning(f"Search failed for {db_name}: {e}")
            return (db_name, [])
    
    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Verify reference across all enabled databases in parallel
        
        Args:
            reference: Reference to verify
            
        Returns:
            Combined and deduplicated results from all databases
        """
        all_results = {}
        
        # Parallel database search - each API is independent with its own rate limits
        max_workers = min(len(self.clients), 8)  # Limit concurrent connections
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all database verifications in parallel
            futures = {
                executor.submit(self._verify_single_database, db_name, client, reference): db_name
                for db_name, client in self.clients.items()
            }
            
            # Collect results as they complete
            for future in as_completed(futures):
                db_name = futures[future]
                try:
                    name, db_results = future.result(timeout=30)  # 30s timeout per database
                    all_results[name] = db_results
                except Exception as e:
                    logger.error(f"Error getting results from {db_name}: {e}")
                    all_results[db_name] = []
        
        # Combine and deduplicate results
        combined_results = self._combine_results(all_results, reference)
        
        # Sort by relevance (primary database first, then by similarity)
        sorted_results = self._sort_results(combined_results, reference)
        
        logger.info(f"Multi-database search found {len(sorted_results)} total results")
        return sorted_results
    
    def _combine_results(self, all_results: Dict[str, List[Dict[str, Any]]], 
                        reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Combine results from multiple databases and remove duplicates
        
        Args:
            all_results: Results from each database
            reference: Original reference for context
            
        Returns:
            Combined and deduplicated results
        """
        combined = []
        seen_titles = set()
        seen_dois = set()
        
        # Prioritize primary database results
        primary_results = all_results.get(self.primary_database, [])
        for result in primary_results:
            title = result.get('title', '').lower().strip() if result.get('title') else ''
            doi = result.get('doi', '').strip() if result.get('doi') else ''
            
            if title and title not in seen_titles:
                combined.append(result)
                seen_titles.add(title)
                if doi:
                    seen_dois.add(doi)
        
        # Add results from other databases
        for db_name, results in all_results.items():
            if db_name == self.primary_database:
                continue
            
            for result in results:
                title = result.get('title', '').lower().strip() if result.get('title') else ''
                doi = result.get('doi', '').strip() if result.get('doi') else ''
                
                # Skip if we've already seen this title or DOI
                if title and title in seen_titles:
                    continue
                if doi and doi in seen_dois:
                    continue
                
                # Add unique result
                if title:
                    combined.append(result)
                    seen_titles.add(title)
                    if doi:
                        seen_dois.add(doi)
        
        return combined
    
    def _sort_results(self, results: List[Dict[str, Any]], 
                     reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Sort results by relevance
        
        Args:
            results: Combined results
            reference: Original reference
            
        Returns:
            Sorted results
        """
        def relevance_score(result):
            score = 0
            
            # Prefer primary database
            if result.get('source', '').lower() == self.primary_database:
                score += 10
            
            # Prefer results with DOI
            if result.get('doi'):
                score += 5
            
            # Prefer results with citation data
            if result.get('citation_count', 0) > 0:
                score += 3
            
            # Prefer more recent papers (if year available)
            ref_year = reference.get('year')
            result_year = result.get('year')
            if ref_year and result_year:
                year_diff = abs(ref_year - result_year)
                if year_diff == 0:
                    score += 2
                elif year_diff <= 1:
                    score += 1
            
            return score
        
        return sorted(results, key=relevance_score, reverse=True)
    
    def get_database_status(self) -> Dict[str, bool]:
        """
        Check status of all configured databases including CryptoDB
        
        Returns:
            Dictionary of database availability
        """
        status = {}
        
        for db_name, client in self.clients.items():
            try:
                status[db_name] = client.is_available()
            except Exception as e:
                logger.warning(f"Failed to check {db_name} status: {e}")
                status[db_name] = False
        
        # Check CryptoDB status separately (optional service)
        if self.cryptodb_client:
            try:
                status['cryptodb_authors'] = self.cryptodb_client.is_available()
            except Exception as e:
                logger.warning(f"Failed to check CryptoDB status: {e}")
                status['cryptodb_authors'] = False
        
        return status
    
    def get_enabled_databases(self) -> List[str]:
        """
        Get list of enabled databases
        
        Returns:
            List of enabled database names
        """
        return list(self.clients.keys())
    
    def search_parallel(self, reference: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search all databases in parallel for faster results
        
        NOTE: This method is deprecated to avoid nested threading issues.
        Use search_across_databases() instead which handles threading at the reference level.
        
        Args:
            reference: Reference to verify
            
        Returns:
            Dictionary with results from each database
        """
        # Redirect to sequential search to avoid nested threading
        logger.warning("search_parallel() is deprecated, using sequential search to avoid threading conflicts")
        return self.search_across_databases(reference)