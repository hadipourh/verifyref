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
        'validation_details': []
    }
    
    for ref in references:
        doi = ref.get('doi', '').strip()
        if doi:
            results['references_with_dois'] += 1
            validation = client.validate_doi(doi)
            
            if validation['valid']:
                results['valid_dois'] += 1
            else:
                results['invalid_dois'] += 1
            
            results['validation_details'].append({
                'reference_title': ref.get('title', 'Unknown'),
                'doi': doi,
                'validation': validation
            })
    
    return results
