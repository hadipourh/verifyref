"""
DOI Validation Client for VerifyRef
Provides direct DOI resolution and validation services
"""

import requests
import logging
from typing import Optional, Dict, Any
from urllib.parse import quote

logger = logging.getLogger(__name__)

class DOIValidationClient:
    """Client for validating DOIs using DOI.org resolution service"""
    
    def __init__(self):
        self.base_url = "https://doi.org"
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': 'VerifyRef/1.0 (Academic Reference Verification)'
        }
    
    def validate_doi(self, doi: str) -> Dict[str, Any]:
        """
        Validate a DOI by attempting to resolve it
        
        Args:
            doi: DOI string to validate
            
        Returns:
            Dict with validation results
        """
        if not doi:
            return {'valid': False, 'error': 'Empty DOI'}
        
        # Clean DOI
        clean_doi = self._clean_doi(doi)
        if not clean_doi:
            return {'valid': False, 'error': 'Invalid DOI format'}
        
        try:
            # Try to resolve DOI
            url = f"{self.base_url}/{clean_doi}"
            response = requests.get(url, headers=self.headers, timeout=10, allow_redirects=False)
            
            if response.status_code == 200:
                return {
                    'valid': True,
                    'doi': clean_doi,
                    'resolved_url': response.url,
                    'content_type': response.headers.get('content-type'),
                    'publisher': self._extract_publisher_from_url(response.url)
                }
            elif response.status_code in [301, 302, 303, 307, 308]:
                # DOI resolves but redirects (normal behavior)
                redirect_url = response.headers.get('location', '')
                return {
                    'valid': True,
                    'doi': clean_doi,
                    'resolved_url': redirect_url,
                    'publisher': self._extract_publisher_from_url(redirect_url),
                    'redirect': True
                }
            elif response.status_code == 404:
                return {'valid': False, 'error': 'DOI not found', 'status_code': 404}
            else:
                return {'valid': False, 'error': f'HTTP {response.status_code}', 'status_code': response.status_code}
                
        except requests.RequestException as e:
            logger.warning(f"DOI validation request failed: {e}")
            return {'valid': False, 'error': f'Request failed: {str(e)}'}
    
    def get_doi_metadata(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a DOI via content negotiation
        
        Args:
            doi: DOI string
            
        Returns:
            Metadata dict or None if not available
        """
        clean_doi = self._clean_doi(doi)
        if not clean_doi:
            return None
        
        try:
            url = f"{self.base_url}/{clean_doi}"
            headers = {
                'Accept': 'application/vnd.citationstyles.csl+json',
                'User-Agent': self.headers['User-Agent']
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            logger.warning(f"DOI metadata request failed: {e}")
            
        return None
    
    def validate_doi_metadata_match(self, doi: str, claimed_title: str, claimed_authors: list, 
                                   claimed_year: int = None, claimed_venue: str = None) -> Dict[str, Any]:
        """
        Validate that DOI metadata matches the claimed paper details
        
        Args:
            doi: DOI string to validate
            claimed_title: Title claimed in the reference
            claimed_authors: List of authors claimed in the reference
            claimed_year: Publication year claimed in the reference
            claimed_venue: Venue/journal claimed in the reference
            
        Returns:
            Dict with validation results and metadata comparison
        """
        if not doi or not claimed_title or not claimed_authors:
            return {
                'metadata_valid': False,
                'error': 'Missing required fields for metadata validation',
                'confidence_boost': 0.0
            }
        
        # First validate DOI resolves
        doi_validation = self.validate_doi(doi)
        if not doi_validation.get('valid', False):
            return {
                'metadata_valid': False,
                'error': f"DOI does not resolve: {doi_validation.get('error', 'Unknown error')}",
                'confidence_boost': 0.0
            }
        
        # Get metadata from DOI
        metadata = self.get_doi_metadata(doi)
        if not metadata:
            return {
                'metadata_valid': False,
                'error': 'Could not retrieve metadata from DOI',
                'doi_resolves': True,
                'confidence_boost': 0.05  # Small boost for valid DOI, but no metadata match
            }
        
        # Compare metadata
        comparison_results = self._compare_metadata(
            metadata, claimed_title, claimed_authors, claimed_year, claimed_venue
        )
        
        # Calculate confidence boost based on matches
        confidence_boost = self._calculate_metadata_confidence_boost(comparison_results)
        
        return {
            'metadata_valid': comparison_results['overall_match'],
            'doi_resolves': True,
            'metadata_comparison': comparison_results,
            'doi_metadata': {
                'title': metadata.get('title', ''),
                'authors': self._extract_authors_from_metadata(metadata),
                'year': metadata.get('published-print', {}).get('date-parts', [[None]])[0][0] or 
                       metadata.get('published-online', {}).get('date-parts', [[None]])[0][0],
                'venue': metadata.get('container-title', [''])[0] if metadata.get('container-title') else '',
                'publisher': metadata.get('publisher', '')
            },
            'confidence_boost': confidence_boost,
            'validation_details': comparison_results['details']
        }
    
    def _compare_metadata(self, doi_metadata: Dict, claimed_title: str, claimed_authors: list,
                         claimed_year: int = None, claimed_venue: str = None) -> Dict[str, Any]:
        """Compare DOI metadata with claimed reference details"""
        
        # Extract DOI metadata
        doi_title = doi_metadata.get('title', '')
        doi_authors = self._extract_authors_from_metadata(doi_metadata)
        doi_year = (doi_metadata.get('published-print', {}).get('date-parts', [[None]])[0][0] or 
                   doi_metadata.get('published-online', {}).get('date-parts', [[None]])[0][0])
        doi_venue = (doi_metadata.get('container-title', [''])[0] if doi_metadata.get('container-title') 
                    else '')
        
        results = {
            'title_match': False,
            'authors_match': False,
            'year_match': False,
            'venue_match': False,
            'overall_match': False,
            'details': []
        }
        
        # Title comparison
        title_similarity = self._calculate_title_similarity(claimed_title, doi_title)
        results['title_match'] = title_similarity > 0.7  # 70% similarity threshold
        results['title_similarity'] = title_similarity
        results['details'].append(f"Title similarity: {title_similarity:.2f} (claimed: '{claimed_title}' vs DOI: '{doi_title}')")
        
        # Authors comparison
        author_match_score = self._calculate_author_similarity(claimed_authors, doi_authors)
        results['authors_match'] = author_match_score > 0.6  # 60% similarity threshold
        results['author_similarity'] = author_match_score
        results['details'].append(f"Author similarity: {author_match_score:.2f} (claimed: {claimed_authors} vs DOI: {doi_authors})")
        
        # Year comparison
        if claimed_year and doi_year:
            year_diff = abs(claimed_year - doi_year)
            results['year_match'] = year_diff <= 1  # Allow 1 year difference
            results['year_difference'] = year_diff
            results['details'].append(f"Year difference: {year_diff} (claimed: {claimed_year} vs DOI: {doi_year})")
        
        # Venue comparison (optional)
        if claimed_venue and doi_venue:
            venue_similarity = self._calculate_title_similarity(claimed_venue, doi_venue)
            results['venue_match'] = venue_similarity > 0.5  # 50% similarity threshold
            results['venue_similarity'] = venue_similarity
            results['details'].append(f"Venue similarity: {venue_similarity:.2f} (claimed: '{claimed_venue}' vs DOI: '{doi_venue}')")
        
        # Overall match determination - require title and authors to match
        results['overall_match'] = (results['title_match'] and results['authors_match'] and
                                  (not claimed_year or results['year_match']))
        
        return results
    
    def _extract_authors_from_metadata(self, metadata: Dict) -> list:
        """Extract author names from DOI metadata"""
        authors = []
        author_list = metadata.get('author', [])
        
        for author in author_list:
            if isinstance(author, dict):
                given = author.get('given', '')
                family = author.get('family', '')
                if given and family:
                    authors.append(f"{given} {family}")
                elif family:
                    authors.append(family)
        
        return authors
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles using simple token-based approach"""
        if not title1 or not title2:
            return 0.0
        
        # Simple token-based similarity
        from difflib import SequenceMatcher
        # Normalize titles
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()
        
        # Calculate sequence similarity
        similarity = SequenceMatcher(None, t1, t2).ratio()
        
        return similarity
    
    def _calculate_author_similarity(self, claimed_authors: list, doi_authors: list) -> float:
        """Calculate similarity between author lists"""
        if not claimed_authors or not doi_authors:
            return 0.0
        
        # Normalize author names for comparison
        def normalize_author(author):
            return author.lower().strip().replace('.', '').replace(',', '')
        
        claimed_normalized = [normalize_author(a) for a in claimed_authors]
        doi_normalized = [normalize_author(a) for a in doi_authors]
        
        # Calculate how many claimed authors have matches in DOI authors
        matches = 0
        for claimed in claimed_normalized:
            for doi_author in doi_normalized:
                # Check if names match (allowing for different name orders)
                if self._authors_match(claimed, doi_author):
                    matches += 1
                    break
        
        # Return ratio of matched authors
        return matches / max(len(claimed_authors), len(doi_authors))
    
    def _authors_match(self, author1: str, author2: str) -> bool:
        """Check if two author names refer to the same person"""
        # Split names into tokens
        tokens1 = set(author1.split())
        tokens2 = set(author2.split())
        
        # Check for significant overlap in name tokens
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        if not union:
            return False
        
        # Require at least 60% token overlap
        return len(intersection) / len(union) >= 0.6
    
    def _calculate_metadata_confidence_boost(self, comparison_results: Dict) -> float:
        """Calculate confidence boost based on metadata matching quality"""
        if not comparison_results['overall_match']:
            # If metadata doesn't match, DOI might be fraudulent or wrong
            return -0.1  # Slight penalty for non-matching DOI
        
        # Strong matches get higher boost
        boost = 0.1  # Base boost for valid DOI with matching metadata
        
        # Add bonuses for strong matches
        if comparison_results.get('title_similarity', 0) > 0.9:
            boost += 0.05  # Strong title match
        
        if comparison_results.get('author_similarity', 0) > 0.8:
            boost += 0.05  # Strong author match
        
        if comparison_results.get('year_match', False):
            boost += 0.02  # Year match
        
        if comparison_results.get('venue_match', False):
            boost += 0.03  # Venue match
        
        # Cap the maximum boost
        return min(boost, 0.2)  # Maximum 20% boost for perfect metadata match
    
    def _clean_doi(self, doi: str) -> Optional[str]:
        """Clean and validate DOI format"""
        if not doi:
            return None
        
        # Remove URL prefixes
        doi = doi.strip()
        doi = doi.replace('https://doi.org/', '')
        doi = doi.replace('http://doi.org/', '')
        doi = doi.replace('https://dx.doi.org/', '')
        doi = doi.replace('http://dx.doi.org/', '')
        doi = doi.replace('doi:', '')
        
        # Basic format validation
        import re
        if re.match(r'^10\.\d+/.+', doi):
            return doi
        
        return None
    
    def _extract_publisher_from_url(self, url: str) -> str:
        """Extract likely publisher from resolved URL"""
        if not url:
            return 'Unknown'
        
        domain_mapping = {
            'springer.com': 'Springer',
            'ieeexplore.ieee.org': 'IEEE',
            'acm.org': 'ACM',
            'nature.com': 'Nature Publishing Group',
            'science.org': 'Science/AAAS',
            'wiley.com': 'Wiley',
            'elsevier.com': 'Elsevier',
            'pubmed.ncbi.nlm.nih.gov': 'PubMed/NIH',
            'arxiv.org': 'arXiv',
            'eprint.iacr.org': 'IACR'
        }
        
        for domain, publisher in domain_mapping.items():
            if domain in url.lower():
                return publisher
        
        return 'Unknown Publisher'

    def check_retraction(self, doi: str) -> Dict[str, Any]:
        """
        Check if a paper with given DOI has been retracted using CrossRef API.
        
        CrossRef includes Retraction Watch database data since 2023.
        
        Args:
            doi: DOI string to check
            
        Returns:
            Dict with retraction status and details
        """
        if not doi:
            return {'retracted': False, 'error': None}
        
        clean_doi = self._clean_doi(doi)
        if not clean_doi:
            return {'retracted': False, 'error': 'Invalid DOI format'}
        
        url = f"https://api.crossref.org/works/{clean_doi}"
        headers = {
            "User-Agent": "VerifyRef/1.0 (Academic Reference Verification; mailto:verifyref@example.com)"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                work = data.get('message', {})
                
                # Check for update-to relations indicating retraction
                update_to = work.get('update-to', [])
                for update in update_to:
                    update_type = update.get('type', '').lower()
                    if update_type in ['retraction', 'removal']:
                        return {
                            'retracted': True,
                            'retraction_doi': update.get('DOI'),
                            'retraction_date': update.get('updated', {}).get('date-time') if isinstance(update.get('updated'), dict) else None,
                            'retraction_type': update.get('type', 'Retraction').title(),
                            'error': None
                        }
                
                # Also check the relation field for retractions
                relation = work.get('relation', {})
                is_retracted_by = relation.get('is-retracted-by', [])
                if is_retracted_by:
                    retraction = is_retracted_by[0]
                    return {
                        'retracted': True,
                        'retraction_doi': retraction.get('id'),
                        'retraction_date': None,
                        'retraction_type': 'Retraction',
                        'error': None
                    }
                
                # Check for expression of concern
                has_expression_of_concern = relation.get('has-expression-of-concern', [])
                if has_expression_of_concern:
                    concern = has_expression_of_concern[0]
                    return {
                        'retracted': True,
                        'retraction_doi': concern.get('id'),
                        'retraction_date': None,
                        'retraction_type': 'Expression of Concern',
                        'error': None
                    }
                
                return {'retracted': False, 'error': None}
                
            elif response.status_code == 404:
                # DOI not found in CrossRef - can't check retraction status
                return {'retracted': False, 'error': None}
            else:
                return {'retracted': False, 'error': f'CrossRef lookup failed: HTTP {response.status_code}'}
                
        except requests.exceptions.Timeout:
            return {'retracted': False, 'error': 'Retraction check timed out'}
        except requests.exceptions.RequestException as e:
            return {'retracted': False, 'error': f'Retraction check failed: {e}'}
    
    def check_retraction_by_title(self, title: str, threshold: float = 0.95) -> Dict[str, Any]:
        """
        Check if a paper has been retracted by searching CrossRef by title.
        
        Searches CrossRef's retraction database (includes Retraction Watch) by title.
        Uses fuzzy matching to verify the found paper matches the reference.
        
        Args:
            title: Paper title to search for
            threshold: Similarity threshold for title matching (default 0.95)
            
        Returns:
            Dict with retraction status and details
        """
        if not title or len(title) < 10:
            return {'retracted': False, 'error': None}
        
        # Search CrossRef for retracted papers matching this title
        encoded_title = quote(title)
        url = f"https://api.crossref.org/works?query.title={encoded_title}&filter=has-update:true&rows=5"
        headers = {
            "User-Agent": "VerifyRef/1.0 (Academic Reference Verification; mailto:verifyref@example.com)"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('message', {}).get('items', [])
                
                for item in items:
                    item_title = item.get('title', [''])[0] if isinstance(item.get('title'), list) else item.get('title', '')
                    if not item_title:
                        continue
                    
                    # Check for fuzzy title match
                    similarity = self._calculate_title_similarity(title, item_title)
                    if similarity >= threshold:
                        # Found a matching paper - check if it's retracted
                        update_to = item.get('update-to', [])
                        for update in update_to:
                            update_type = update.get('type', '').lower()
                            if update_type in ['retraction', 'removal']:
                                return {
                                    'retracted': True,
                                    'original_doi': item.get('DOI'),
                                    'retraction_doi': update.get('DOI'),
                                    'retraction_date': update.get('updated', {}).get('date-time') if isinstance(update.get('updated'), dict) else None,
                                    'retraction_type': update.get('type', 'Retraction').title(),
                                    'error': None
                                }
                        
                        # Check relation field
                        relation = item.get('relation', {})
                        is_retracted_by = relation.get('is-retracted-by', [])
                        if is_retracted_by:
                            retraction = is_retracted_by[0]
                            return {
                                'retracted': True,
                                'original_doi': item.get('DOI'),
                                'retraction_doi': retraction.get('id'),
                                'retraction_date': None,
                                'retraction_type': 'Retraction',
                                'error': None
                            }
                        
                        # Check for expression of concern
                        has_expression_of_concern = relation.get('has-expression-of-concern', [])
                        if has_expression_of_concern:
                            concern = has_expression_of_concern[0]
                            return {
                                'retracted': True,
                                'original_doi': item.get('DOI'),
                                'retraction_doi': concern.get('id'),
                                'retraction_date': None,
                                'retraction_type': 'Expression of Concern',
                                'error': None
                            }
                
                return {'retracted': False, 'error': None}
                
            elif response.status_code == 404:
                return {'retracted': False, 'error': None}
            else:
                return {'retracted': False, 'error': f'CrossRef search failed: HTTP {response.status_code}'}
                
        except requests.exceptions.Timeout:
            return {'retracted': False, 'error': 'Retraction search timed out'}
        except requests.exceptions.RequestException as e:
            return {'retracted': False, 'error': f'Retraction search failed: {e}'}


# Example usage functions for integration

def validate_reference_dois(references: list) -> dict:
    """
    Validate DOIs for a list of references
    
    Args:
        references: List of reference dictionaries
        
    Returns:
        Dict with validation statistics
    """
    client = DOIValidationClient()
    results = {
        'total_references': len(references),
        'references_with_dois': 0,
        'valid_dois': 0,
        'invalid_dois': 0,
        'retracted_papers': 0,
        'validation_details': []
    }
    
    for ref in references:
        doi = ref.get('doi', '').strip()
        if doi:
            results['references_with_dois'] += 1
            validation = client.validate_doi(doi)
            
            if validation['valid']:
                results['valid_dois'] += 1
                # Also check for retraction
                retraction = client.check_retraction(doi)
                if retraction.get('retracted'):
                    results['retracted_papers'] += 1
                    validation['retraction_info'] = retraction
            else:
                results['invalid_dois'] += 1
            
            results['validation_details'].append({
                'reference_title': ref.get('title', 'Unknown'),
                'doi': doi,
                'validation': validation
            })
    
    return results
