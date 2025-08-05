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
from config import DATABASE_CONFIG

logger = logging.getLogger(__name__)

class MultiDatabaseVerifier:
    """
    Coordinator for verifying references across multiple academic databases
    """
    
    def __init__(self, enable_cryptodb: bool = True):
        """
        Initialize multi-database verifier
        
        Args:
            enable_cryptodb: Whether to enable CryptoDB author verification
        """
        self.enabled_databases = DATABASE_CONFIG.get("enabled_databases", ["semantic_scholar"])
        self.primary_database = DATABASE_CONFIG.get("primary_database", "semantic_scholar")
        
        # Initialize clients
        self.clients = {}
        
        # OpenAlex - Fast, comprehensive, and free (primary recommendation)
        if "openalex" in self.enabled_databases and DATABASE_CONFIG.get("openalex", {}).get("enabled", True):
            openalex_config = DATABASE_CONFIG.get("openalex", {})
            self.clients["openalex"] = OpenAlexClient(openalex_config)
        
        if "semantic_scholar" in self.enabled_databases:
            self.clients["semantic_scholar"] = SemanticScholarClient()
        
        if "dblp" in self.enabled_databases and DATABASE_CONFIG.get("dblp", {}).get("enabled", True):
            self.clients["dblp"] = DBLPClient()
        
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
    
    def search_across_databases(self, query_info: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for papers across all enabled databases and return results from each
        
        Args:
            query_info: Dictionary with search parameters (title, authors, year, venue)
            
        Returns:
            Dictionary mapping database names to their search results
        """
        results = {}
        
        # Sequential database search to avoid nested threading issues
        # This ensures thread safety when called from parallel reference processing
        for db_name, client in self.clients.items():
            try:
                if not client.is_available():
                    logger.warning(f"{db_name} service unavailable, skipping")
                    results[db_name] = []
                    continue
                
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
                
                results[db_name] = db_results
                logger.info(f"{db_name} returned {len(db_results)} results")
                
                # Add small delay to respect API rate limits
                if db_name == "semantic_scholar":
                    time.sleep(1.0)  # Moderate delay for Semantic Scholar
                elif db_name in ["pubmed", "crossref"]:
                    time.sleep(0.5)  # Brief delay for rate-limited APIs
                else:
                    time.sleep(0.1)  # Minimal delay for other APIs
                    
            except Exception as e:
                logger.error(f"Error searching {db_name}: {e}")
                results[db_name] = []
        
        return results
    
    def verify_reference(self, reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Verify reference across all enabled databases
        
        Args:
            reference: Reference to verify
            
        Returns:
            Combined and deduplicated results from all databases
        """
        all_results = {}
        
        # Search each database
        for db_name, client in self.clients.items():
            try:
                if not client.is_available():
                    logger.warning(f"{db_name} service unavailable, skipping")
                    all_results[db_name] = []
                    continue
                    
                logger.debug(f"Searching {db_name} for reference: {reference.get('title', 'No title')[:50]}...")
                results = client.verify_reference(reference)
                all_results[db_name] = results
                logger.info(f"{db_name} returned {len(results)} results")
                
                # Add delay between database calls to respect rate limits
                if db_name == "semantic_scholar":
                    time.sleep(5.0)  # Longer delay for Semantic Scholar to avoid rate limiting
                else:
                    time.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Search failed for {db_name}: {e}")
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