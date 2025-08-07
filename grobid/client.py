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
        Initialize GROBID client with enhanced configuration
        
        Args:
            base_url: GROBID server URL (defaults to config value)
        """
        self.base_url = base_url or GROBID_CONFIG["base_url"]
        self.timeout = GROBID_CONFIG["timeout"]
        self.max_retries = GROBID_CONFIG["max_retries"]
        
        # Enhanced processing options
        self.use_consolidation = GROBID_CONFIG.get("use_consolidation", True)
        self.include_raw_citations = GROBID_CONFIG.get("include_raw_citations", True)
        self.segment_sentences = GROBID_CONFIG.get("segment_sentences", True)
        self.generate_ids = GROBID_CONFIG.get("generate_ids", True)
        
        # Ensure base URL doesn't end with slash
        self.base_url = self.base_url.rstrip('/')
        
        logger.info(f"GROBID initialized - base_url={self.base_url}, timeout={self.timeout}, "
                   f"consolidation={self.use_consolidation}, "
                   f"raw_citations={self.include_raw_citations}")
    
    def parse_citation_string(self, citation_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single citation string using GROBID's processCitation endpoint
        
        Args:
            citation_text: A single citation string to parse
            
        Returns:
            Dictionary in the same format as extract_references output, or None if parsing fails
        """
        if not citation_text or not citation_text.strip():
            return None
            
        try:
            # Use GROBID's processCitation endpoint
            endpoint = f"{self.base_url}/api/processCitation"
            
            data = {
                'citations': citation_text.strip(),
                'consolidateCitations': '1' if self.use_consolidation else '0'
            }
            
            response = requests.post(
                endpoint,
                data=data,
                timeout=self.timeout,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code == 200:
                # Parse the XML response
                parsed_citation = self._parse_citation_xml(response.text, citation_text)
                if parsed_citation:
                    logger.debug(f"Successfully parsed citation: {citation_text[:60]}...")
                    return parsed_citation
                else:
                    logger.warning(f"Failed to parse citation XML response")
                    return None
            else:
                logger.error(f"GROBID processCitation failed with status {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to GROBID for citation parsing: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing citation with GROBID: {e}")
            return None
        
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
    
    def extract_references(self, pdf_path: str, use_consolidation: Optional[bool] = None, 
                          include_raw_citations: Optional[bool] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Extract references from a PDF document with enhanced processing options
        
        Args:
            pdf_path: Path to the PDF file
            use_consolidation: Whether to use bibliographic consolidation (defaults to config)
            include_raw_citations: Whether to include raw citation text (defaults to config)
            
        Returns:
            List of extracted references or None if extraction failed
        """
        # Use instance defaults if not specified
        if use_consolidation is None:
            use_consolidation = self.use_consolidation
        if include_raw_citations is None:
            include_raw_citations = self.include_raw_citations
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
                
                # Enhanced parameters for better processing
                data = {}
                if use_consolidation:
                    data['consolidateHeader'] = '1'  # Consolidate header information
                    data['consolidateCitations'] = '1'  # Consolidate citations with external sources
                if include_raw_citations:
                    data['includeRawCitations'] = '1'  # Include raw citation strings
                
                # Try processReferences first with enhanced parameters
                response = requests.post(
                    f"{self.base_url}/api/processReferences",
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200 and response.text.strip():
                    references = self._parse_grobid_response(response.text, include_raw_citations)
                    if references:
                        logger.info(f"Successfully extracted {len(references)} references using processReferences")
                        return references
                    
                # If no references from processReferences, try full text processing with enhanced parameters
                logger.info("No references from processReferences, trying full text processing...")
                
                # Reopen file for second request
                pdf_file.seek(0)
                
                # Enhanced parameters for full text processing
                fulltext_data = {
                    'consolidateHeader': '1' if use_consolidation else '0',
                    'consolidateCitations': '1' if use_consolidation else '0',
                    'includeRawCitations': '1' if include_raw_citations else '0',
                    'generateIDs': '1' if self.generate_ids else '0',  # Generate unique IDs for elements
                    'segmentSentences': '1' if self.segment_sentences else '0'  # Improve sentence segmentation
                }
                
                response = requests.post(
                    f"{self.base_url}/api/processFulltextDocument",
                    files={'input': pdf_file},
                    data=fulltext_data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    references = self._parse_grobid_response(response.text, include_raw_citations)
                    if references:
                        logger.info(f"Successfully extracted {len(references)} references using processFulltextDocument")
                    return references
                else:
                    logger.error(f"GROBID full text processing failed with status {response.status_code}")
                    return None
                    
        except requests.RequestException as e:
            logger.error(f"Error calling GROBID service: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting references: {e}")
            return None
    
    def _parse_grobid_response(self, xml_content: str, include_raw_citations: bool = True) -> List[Dict[str, Any]]:
        """
        Parse GROBID XML response to extract reference information with enhanced extraction
        
        Args:
            xml_content: Raw XML response from GROBID
            include_raw_citations: Whether to extract raw citation text for fallback processing
            
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
                reference = self._extract_reference_data(biblio, namespace, include_raw_citations)
                if reference:
                    references.append(reference)
                    
        except ET.ParseError as e:
            logger.error(f"Error parsing GROBID XML response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing references: {e}")
            
        logger.info(f"Extracted {len(references)} references from GROBID response")
        return references
    
    def _parse_citation_xml(self, xml_content: str, original_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse GROBID processCitation XML response into our standard format
        
        Args:
            xml_content: XML response from GROBID processCitation
            original_text: Original citation text
            
        Returns:
            Dictionary in the same format as extract_references output
        """
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Handle namespace (GROBID uses TEI namespace)
            namespace = ''
            if root.tag.startswith('{'):
                namespace = root.tag[:root.tag.index('}')+1]
            
            # Create base reference structure
            reference = {
                'raw_text': original_text,
                'title': '',
                'authors': [],
                'venue': '',
                'year': None,
                'volume': '',
                'issue': '',
                'pages': '',
                'doi': '',
                'isbn': '',
                'url': '',
                'confidence_indicators': {}
            }
            
            # Extract data using existing helper method
            extracted_ref = self._extract_reference_data(root, namespace, True)
            if extracted_ref:
                # Merge the extracted data but keep our original raw_text
                reference.update(extracted_ref)
                reference['raw_text'] = original_text
            
            # Ensure we have some basic information
            if not reference['title'] and not reference['authors']:
                logger.warning("Parsed citation lacks both title and authors")
                return None
                
            return reference
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse GROBID citation XML: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing GROBID citation response: {e}")
            return None
    
    def _extract_reference_data(self, biblio_elem: ET.Element, namespace: str = '', 
                              include_raw_citations: bool = True) -> Optional[Dict[str, Any]]:
        """
        Extract reference data from a single biblStruct element with enhanced parsing
        
        Args:
            biblio_elem: XML element containing bibliographic data
            namespace: XML namespace to use in queries
            include_raw_citations: Whether to extract raw citation text
            
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
                'url': '',
                'confidence_indicators': {}  # Add confidence indicators from GROBID
            }
            
            # Extract raw citation text if available and requested
            if include_raw_citations:
                raw_elem = biblio_elem.find(f'.//{namespace}note[@type="raw_reference"]')
                if raw_elem is not None and raw_elem.text:
                    reference['raw_text'] = raw_elem.text.strip()
            
            # Extract title with enhanced approach - try multiple strategies
            title_elem = self._find_title_element(biblio_elem, namespace)
            if title_elem is not None and title_elem.text:
                title_text = title_elem.text.strip()
                # Check for confidence attributes
                if 'confidence' in title_elem.attrib:
                    reference['confidence_indicators']['title'] = float(title_elem.attrib['confidence'])
                reference['title'] = title_text
            
            # Extract authors with enhanced parsing
            # Extract authors with enhanced parsing
            authors = []
            author_xpath = f'.//{namespace}author/{namespace}persName'
            for author_elem in biblio_elem.findall(author_xpath):
                author_name = self._extract_author_name(author_elem, namespace)
                if author_name:
                    authors.append(author_name)
            
            reference['authors'] = authors
            
            # Extract venue with enhanced approach
            venue_elem = self._find_venue_element(biblio_elem, namespace)
            if venue_elem is not None and venue_elem.text:
                reference['venue'] = venue_elem.text.strip()
            
            # Extract publication date with enhanced parsing
            year = self._extract_publication_year(biblio_elem, namespace)
            if year:
                reference['year'] = year
            
            # Extract bibliographic details
            self._extract_bibliographic_details(biblio_elem, namespace, reference)
            
            # Extract identifiers (DOI, ISBN, etc.)
            self._extract_identifiers(biblio_elem, namespace, reference)
            
            # Only return references with at least a title or substantial content
            if reference['title'] or reference['raw_text'] or (reference['authors'] and reference['venue']):
                return reference
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error extracting reference data: {e}")
            return None
    
    def _find_title_element(self, biblio_elem: ET.Element, namespace: str) -> Optional[ET.Element]:
        """Find the best title element using multiple strategies"""
        # Strategy 1: Article title (level="a")
        title_elem = biblio_elem.find(f'.//{namespace}title[@level="a"]')
        if title_elem is not None and title_elem.text and title_elem.text.strip():
            return title_elem
        
        # Strategy 2: Main title
        title_elem = biblio_elem.find(f'.//{namespace}title[@type="main"]')
        if title_elem is not None and title_elem.text and title_elem.text.strip():
            return title_elem
        
        # Strategy 3: Any title that's not a journal title
        for title_elem in biblio_elem.findall(f'.//{namespace}title'):
            if (title_elem.get('level') != 'j' and 
                title_elem.get('type') != 'j' and
                title_elem.text and title_elem.text.strip()):
                return title_elem
        
        return None
    
    def _find_venue_element(self, biblio_elem: ET.Element, namespace: str) -> Optional[ET.Element]:
        """Find the best venue/journal element"""
        # Strategy 1: Journal title (level="j")
        venue_elem = biblio_elem.find(f'.//{namespace}title[@level="j"]')
        if venue_elem is not None and venue_elem.text:
            return venue_elem
        
        # Strategy 2: Monograph/book title (level="m")
        venue_elem = biblio_elem.find(f'.//{namespace}title[@level="m"]')
        if venue_elem is not None and venue_elem.text:
            return venue_elem
        
        # Strategy 3: Journal type title
        venue_elem = biblio_elem.find(f'.//{namespace}title[@type="j"]')
        if venue_elem is not None and venue_elem.text:
            return venue_elem
        
        return None
    
    def _extract_author_name(self, author_elem: ET.Element, namespace: str) -> str:
        """Extract a properly formatted author name"""
        forename_elem = author_elem.find(f'{namespace}forename')
        surname_elem = author_elem.find(f'{namespace}surname')
        
        # Try different name extraction strategies
        parts = []
        
        # Get forename(s)
        if forename_elem is not None and forename_elem.text:
            forename = forename_elem.text.strip()
            if forename:
                parts.append(forename)
        
        # Get surname
        if surname_elem is not None and surname_elem.text:
            surname = surname_elem.text.strip()
            if surname:
                parts.append(surname)
        
        if parts:
            return ' '.join(parts)
        
        # Fallback: use the full text content
        if author_elem.text:
            return author_elem.text.strip()
        
        return ''
    
    def _extract_publication_year(self, biblio_elem: ET.Element, namespace: str) -> Optional[int]:
        """Extract publication year with multiple strategies"""
        # Strategy 1: Published date
        date_elem = biblio_elem.find(f'.//{namespace}date[@type="published"]')
        if date_elem is not None:
            when_attr = date_elem.get('when')
            if when_attr:
                try:
                    return int(when_attr[:4])
                except (ValueError, TypeError):
                    pass
        
        # Strategy 2: Any date element
        for date_elem in biblio_elem.findall(f'.//{namespace}date'):
            when_attr = date_elem.get('when')
            if when_attr:
                try:
                    return int(when_attr[:4])
                except (ValueError, TypeError):
                    continue
            # Try text content
            if date_elem.text:
                import re
                year_match = re.search(r'\b(19|20)\d{2}\b', date_elem.text)
                if year_match:
                    return int(year_match.group())
        
        return None
    
    def _extract_bibliographic_details(self, biblio_elem: ET.Element, namespace: str, reference: Dict[str, Any]):
        """Extract volume, issue, pages with enhanced parsing"""
        # Volume
        vol_elem = biblio_elem.find(f'.//{namespace}biblScope[@unit="volume"]')
        if vol_elem is not None and vol_elem.text:
            reference['volume'] = vol_elem.text.strip()
        
        # Issue
        issue_elem = biblio_elem.find(f'.//{namespace}biblScope[@unit="issue"]')
        if issue_elem is not None and issue_elem.text:
            reference['issue'] = issue_elem.text.strip()
        
        # Pages - try multiple strategies
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
    
    def _extract_identifiers(self, biblio_elem: ET.Element, namespace: str, reference: Dict[str, Any]):
        """Extract DOI, ISBN, and other identifiers"""
        # DOI
        doi_elem = biblio_elem.find(f'.//{namespace}idno[@type="DOI"]')
        if doi_elem is not None and doi_elem.text:
            reference['doi'] = doi_elem.text.strip()
        
        # Alternative DOI extraction
        if not reference['doi']:
            for idno_elem in biblio_elem.findall(f'.//{namespace}idno'):
                if idno_elem.text and 'doi' in idno_elem.text.lower():
                    reference['doi'] = idno_elem.text.strip()
                    break
        
        # ISBN
        isbn_elem = biblio_elem.find(f'.//{namespace}idno[@type="ISBN"]')
        if isbn_elem is not None and isbn_elem.text:
            reference['isbn'] = isbn_elem.text.strip()
        
        # URL/URI
        ptr_elem = biblio_elem.find(f'.//{namespace}ptr')
        if ptr_elem is not None:
            target = ptr_elem.get('target')
            if target:
                reference['url'] = target