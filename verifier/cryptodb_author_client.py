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
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

class CryptoDBAuthorClient:
    """
    Client for CryptoDB author verification using their public API
    Only uses the officially documented JSON autosuggest API
    """
    
    def __init__(self, enable_cryptodb: bool = True, timeout: int = 5):
        """
        Initialize CryptoDB client
        
        Args:
            enable_cryptodb: Whether to enable CryptoDB lookups (can be disabled for performance)
            timeout: Request timeout in seconds (kept short to avoid delays)
        """
        self.enabled = enable_cryptodb
        self.base_url = "https://www.iacr.org/cryptodb/data/jquery/query.php"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RefCheck/1.0 (Academic Reference Verification)'
        })
        
        if not self.enabled:
            logger.info("CryptoDB author verification disabled")
    
    @lru_cache(maxsize=1000)  # Cache results to avoid repeated API calls
    def lookup_author(self, author_name: str) -> Optional[Dict[str, Any]]:
        """
        Look up an author in CryptoDB using their public API
        
        Args:
            author_name: Name to search for
            
        Returns:
            Author info dict with id, canonical name, affiliation if found, None otherwise
        """
        if not self.enabled or not author_name or len(author_name.strip()) < 2:
            return None
        
        # Clean the author name - remove database disambiguation artifacts
        from utils.academic_matching import clean_author_name
        clean_name = clean_author_name(author_name)
        
        try:
            # Try multiple search strategies for better matching
            search_terms = [clean_name]
            
            # If it's an initial format like "N. Smart", also try searching by lastname
            if len(clean_name.split()) == 2 and len(clean_name.split()[0]) <= 2:
                lastname = clean_name.split()[-1]
                search_terms.append(lastname)
            
            for search_term in search_terms:
                params = {'term': search_term}
                response = self.session.get(self.base_url, params=params, timeout=self.timeout)
                response.raise_for_status()
                
                results = response.json()
                if not results or not isinstance(results, list):
                    continue
                
                # Look for exact or very close matches
                for result in results:
                    if not isinstance(result, dict):
                        continue
                        
                    result_name = result.get('value', '')
                    
                    # Exact match (case insensitive)
                    if result_name.lower() == clean_name.lower():
                        return {
                            'id': result.get('id'),
                            'canonical_name': result_name,
                            'lastname': result.get('lastname', ''),
                            'affiliation': result.get('affiliation'),
                            'match_type': 'exact'
                        }
                
                # If no exact match, look for very similar matches
                best_match = self._find_best_match(clean_name, results)
                if best_match:
                    return best_match
            
            return None
            
        except requests.exceptions.Timeout:
            logger.warning(f"CryptoDB author lookup timeout for: {author_name}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"CryptoDB author lookup failed for {author_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in CryptoDB lookup for {author_name}: {e}")
            return None
    
    def _find_best_match(self, query_name: str, results: List[Dict]) -> Optional[Dict[str, Any]]:
        """Find the best matching author from search results"""
        query_lastname = query_name.split()[-1].lower()
        query_parts = query_name.lower().split()
        
        for result in results:
            if not isinstance(result, dict):
                continue
                
            result_lastname = result.get('lastname', '').lower()
            result_name = result.get('value', '')
            result_parts = result_name.lower().split()
            
            # Same lastname and compatible structure
            if result_lastname == query_lastname:
                if self._names_are_compatible(query_parts, result_parts):
                    return {
                        'id': result.get('id'),
                        'canonical_name': result_name,
                        'lastname': result.get('lastname', ''),
                        'affiliation': result.get('affiliation'),
                        'match_type': 'similar'
                    }
        
        return None
    
    def _names_are_compatible(self, name_parts1: List[str], name_parts2: List[str]) -> bool:
        """
        Check if two name part lists are compatible
        Handles cases like ["n.", "smart"] and ["nigel", "smart"]
        """
        if len(name_parts1) != len(name_parts2):
            return False
        
        for p1, p2 in zip(name_parts1, name_parts2):
            # Remove dots for comparison
            p1_clean = p1.rstrip('.')
            p2_clean = p2.rstrip('.')
            
            # If one is an initial (length 1) and the other starts with that letter
            if len(p1_clean) == 1 or len(p2_clean) == 1:
                if p1_clean[0].lower() != p2_clean[0].lower():
                    return False
            elif p1_clean.lower() != p2_clean.lower():
                return False
        
        return True
    
    def verify_author_against_cryptodb(self, author_name: str, paper_venue: str = "") -> Dict[str, Any]:
        """
        Verify an author against CryptoDB and return verification info
        
        Args:
            author_name: Author name to verify
            paper_venue: Venue of the paper (to check if it's crypto-related)
            
        Returns:
            Dict with verification results
        """
        if not self.enabled:
            return {'verified': False, 'reason': 'CryptoDB disabled'}
        
        # Only use CryptoDB for crypto-related venues
        crypto_venues = [
            'crypto', 'eurocrypt', 'asiacrypt', 'ches', 'pkc', 'tcc', 'fse',
            'iacr', 'journal of cryptology', 'tches', 'tosc'
        ]
        
        is_crypto_venue = any(venue in paper_venue.lower() for venue in crypto_venues)
        if not is_crypto_venue:
            return {'verified': False, 'reason': 'Not a cryptography venue'}
        
        author_info = self.lookup_author(author_name)
        if not author_info:
            return {
                'verified': False, 
                'reason': 'Author not found in CryptoDB',
                'cryptodb_lookup': True
            }
        
        return {
            'verified': True,
            'cryptodb_id': author_info['id'],
            'canonical_name': author_info['canonical_name'],
            'affiliation': author_info.get('affiliation'),
            'match_type': author_info['match_type'],
            'cryptodb_lookup': True
        }
    
    def enhance_author_comparison(self, ref_authors: List[str], paper_authors: List[str], 
                                paper_venue: str = "") -> Dict[str, Any]:
        """
        Enhance author comparison using CryptoDB canonical names
        
        Args:
            ref_authors: Authors from the reference
            paper_authors: Authors from the found paper
            paper_venue: Venue to determine if CryptoDB should be used
            
        Returns:
            Enhanced comparison results
        """
        if not self.enabled:
            return {'enhanced': False, 'reason': 'CryptoDB disabled'}
        
        # Only enhance for crypto venues
        crypto_venues = [
            'crypto', 'eurocrypt', 'asiacrypt', 'ches', 'pkc', 'tcc', 'fse',
            'iacr', 'journal of cryptology', 'tches', 'tosc'
        ]
        
        is_crypto_venue = any(venue in paper_venue.lower() for venue in crypto_venues)
        if not is_crypto_venue:
            return {'enhanced': False, 'reason': 'Not a cryptography venue'}
        
        # Look up canonical names for reference authors
        ref_canonical = []
        for author in ref_authors:
            author_info = self.lookup_author(author)
            if author_info:
                ref_canonical.append({
                    'original': author,
                    'canonical': author_info['canonical_name'],
                    'id': author_info['id']
                })
        
        # Look up canonical names for paper authors  
        paper_canonical = []
        for author in paper_authors:
            author_info = self.lookup_author(author)
            if author_info:
                paper_canonical.append({
                    'original': author,
                    'canonical': author_info['canonical_name'],
                    'id': author_info['id']
                })
        
        # Compare using canonical IDs
        matched_authors = []
        mismatched_authors = []
        
        for ref_auth in ref_canonical:
            found_match = False
            for paper_auth in paper_canonical:
                if ref_auth['id'] == paper_auth['id']:
                    matched_authors.append({
                        'ref_name': ref_auth['original'],
                        'paper_name': paper_auth['original'],
                        'canonical_name': ref_auth['canonical'],
                        'cryptodb_id': ref_auth['id']
                    })
                    found_match = True
                    break
            
            if not found_match:
                mismatched_authors.append(ref_auth['original'])
        
        return {
            'enhanced': True,
            'matched_authors': matched_authors,
            'mismatched_authors': mismatched_authors,
            'ref_canonical_count': len(ref_canonical),
            'paper_canonical_count': len(paper_canonical),
            'cryptodb_lookup': True
        }
    
    def is_available(self) -> bool:
        """
        Check if CryptoDB author API is available
        
        Returns:
            True if service is available and enabled, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            response = self.session.get(f"{self.base_url}?term=test", timeout=3)
            return response.status_code == 200
        except Exception:
            return False