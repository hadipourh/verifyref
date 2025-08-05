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
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from xml.etree import ElementTree as ET

from config import GROBID_CONFIG

logger = logging.getLogger(__name__)

class GrobidClient:
    """
    Client for interacting with GROBID service to extract references from PDFs
    """
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize GROBID client
        
        Args:
            base_url: GROBID server URL (defaults to config value)
        """
        self.base_url = base_url or GROBID_CONFIG["base_url"]
        self.timeout = GROBID_CONFIG["timeout"]
        self.max_retries = GROBID_CONFIG["max_retries"]
        
        # Ensure base URL doesn't end with slash
        self.base_url = self.base_url.rstrip('/')
        
    def is_available(self) -> bool:
        """
        Check if GROBID service is available
        
        Returns:
            True if service is available, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/isalive",
                timeout=10
            )
            return response.status_code == 200
        except requests.RequestException as e:
            logger.error(f"GROBID service not available: {e}")
            return False
    
    def extract_references(self, pdf_path: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract references from a PDF document
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of extracted references or None if extraction failed
        """
        if not Path(pdf_path).exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None
        
        # First check if service is available
        if not self.is_available():
            logger.error("GROBID service is not available")
            return None
        
        try:
            with open(pdf_path, 'rb') as pdf_file:
                files = {'input': pdf_file}
                
                # Try processReferences first, fall back to processFulltextDocument
                response = requests.post(
                    f"{self.base_url}/api/processReferences",
                    files=files,
                    timeout=self.timeout
                )
                
                if response.status_code == 200 and response.text.strip():
                    references = self._parse_grobid_response(response.text)
                    if references:
                        return references
                    
                # If no references from processReferences, try full text processing
                logger.info("No references from processReferences, trying full text processing...")
                
                # Reopen file for second request
                pdf_file.seek(0)
                response = requests.post(
                    f"{self.base_url}/api/processFulltextDocument",
                    files={'input': pdf_file},
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return self._parse_grobid_response(response.text)
                else:
                    logger.error(f"GROBID full text processing failed with status {response.status_code}")
                    return None
                    
        except requests.RequestException as e:
            logger.error(f"Error calling GROBID service: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting references: {e}")
            return None
    
    def _parse_grobid_response(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Parse GROBID XML response to extract reference information
        
        Args:
            xml_content: Raw XML response from GROBID
            
        Returns:
            List of parsed references
        """
        references = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Handle TEI namespace
            namespace = ''
            if root.tag.startswith('{'):
                namespace = root.tag.split('}')[0] + '}'
                
            # Find all biblStruct elements (bibliographic structures)
            biblstruct_xpath = f'.//{namespace}biblStruct'
            biblstructs = root.findall(biblstruct_xpath)
            
            logger.info(f"Found {len(biblstructs)} biblStruct elements in XML")
            
            for biblio in biblstructs:
                reference = self._extract_reference_data(biblio, namespace)
                if reference:
                    references.append(reference)
                    
        except ET.ParseError as e:
            logger.error(f"Error parsing GROBID XML response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing references: {e}")
            
        logger.info(f"Extracted {len(references)} references from GROBID response")
        return references
    
    def _extract_reference_data(self, biblio_elem: ET.Element, namespace: str = '') -> Optional[Dict[str, Any]]:
        """
        Extract reference data from a single biblStruct element
        
        Args:
            biblio_elem: XML element containing bibliographic data
            namespace: XML namespace to use in queries
            
        Returns:
            Dictionary with extracted reference data or None
        """
        try:
            reference = {
                'raw_text': '',
                'title': '',
                'authors': [],
                'venue': '',
                'year': None,
                'volume': '',
                'issue': '',
                'pages': '',
                'doi': '',
                'isbn': '',
                'url': ''
            }
            
            # Extract title - try multiple approaches
            title_elem = biblio_elem.find(f'.//{namespace}title[@type="main"]')
            if title_elem is None:
                title_elem = biblio_elem.find(f'.//{namespace}title[@level="a"]')
            if title_elem is None:
                title_elem = biblio_elem.find(f'.//{namespace}title')
                
            if title_elem is not None and title_elem.text:
                reference['title'] = title_elem.text.strip()
            
            # Extract authors
            authors = []
            author_xpath = f'.//{namespace}author/{namespace}persName'
            for author_elem in biblio_elem.findall(author_xpath):
                forename_elem = author_elem.find(f'{namespace}forename')
                surname_elem = author_elem.find(f'{namespace}surname')
                
                author_name = ''
                if forename_elem is not None and forename_elem.text:
                    author_name += forename_elem.text.strip() + ' '
                if surname_elem is not None and surname_elem.text:
                    author_name += surname_elem.text.strip()
                
                if author_name.strip():
                    authors.append(author_name.strip())
            
            reference['authors'] = authors
            
            # Extract venue (journal, conference, etc.)
            venue_elem = biblio_elem.find(f'.//{namespace}title[@level="j"]')  # journal
            if venue_elem is None:
                venue_elem = biblio_elem.find(f'.//{namespace}title[@level="m"]')  # monograph/book
            if venue_elem is None:
                venue_elem = biblio_elem.find(f'.//{namespace}title[@type="j"]')  # alternative journal
                
            if venue_elem is not None and venue_elem.text:
                reference['venue'] = venue_elem.text.strip()
            
            # Extract year
            date_elem = biblio_elem.find(f'.//{namespace}date[@type="published"]')
            if date_elem is not None:
                year_attr = date_elem.get('when')
                if year_attr:
                    try:
                        reference['year'] = int(year_attr[:4])  # Extract year from date
                    except (ValueError, TypeError):
                        pass
            
            # Extract volume, issue, pages
            vol_elem = biblio_elem.find(f'.//{namespace}biblScope[@unit="volume"]')
            if vol_elem is not None and vol_elem.text:
                reference['volume'] = vol_elem.text.strip()
                
            issue_elem = biblio_elem.find(f'.//{namespace}biblScope[@unit="issue"]')
            if issue_elem is not None and issue_elem.text:
                reference['issue'] = issue_elem.text.strip()
                
            pages_elem = biblio_elem.find(f'.//{namespace}biblScope[@unit="page"]')
            if pages_elem is not None:
                from_page = pages_elem.get('from', '')
                to_page = pages_elem.get('to', '')
                if from_page and to_page:
                    reference['pages'] = f"{from_page}-{to_page}"
                elif from_page:
                    reference['pages'] = from_page
                elif pages_elem.text:
                    reference['pages'] = pages_elem.text.strip()
            
            # Extract DOI
            doi_elem = biblio_elem.find(f'.//{namespace}idno[@type="DOI"]')
            if doi_elem is not None and doi_elem.text:
                reference['doi'] = doi_elem.text.strip()
            
            # Only return references with at least a title
            if reference['title']:
                return reference
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error extracting reference data: {e}")
            return None