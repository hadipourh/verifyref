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
import re
import html
from pathlib import Path
from typing import Optional, Dict, Any, List
from xml.etree import ElementTree as ET

from config import GROBID_CONFIG

logger = logging.getLogger(__name__)

# GROBID server URLs for fallback chain
GROBID_PUBLIC_SERVER = "https://kermitt2-grobid.hf.space"
GROBID_LOCAL_SERVER = "http://localhost:8070"


def clean_extracted_title(title: str) -> str:
    """
    Clean and normalize extracted titles from GROBID.
    
    Handles common issues like:
    - Mangled HTML tags: "SPHINCS sup+/sup" -> "SPHINCS+"
    - Empty/mangled tags: "SPHINCS <>+<>" -> "SPHINCS+"
    - Leftover XML tags: "<sup>+</sup>" -> "+"
    - HTML entities: "&amp;" -> "&"
    - Extra whitespace around special characters
    
    Args:
        title: Raw title string from GROBID
        
    Returns:
        Cleaned title string
    """
    if not title:
        return title
    
    # Pattern 1: Handle proper XML/HTML tags <sup>...</sup>, <sub>...</sub> FIRST
    # Preserve a space after the content to avoid merging words
    title = re.sub(r'\s*<sup>([^<]*)</sup>\s*', r'\1 ', title)
    title = re.sub(r'\s*<sub>([^<]*)</sub>\s*', r'\1 ', title)
    title = re.sub(r'<i>([^<]*)</i>', r'\1', title)
    title = re.sub(r'<b>([^<]*)</b>', r'\1', title)
    title = re.sub(r'<em>([^<]*)</em>', r'\1', title)
    
    # Pattern 2: Handle mangled sup/sub tags like "sup+/sup" or "sub2/sub"
    # This handles cases where GROBID outputs "text sup+/sup more" instead of "text+ more"
    title = re.sub(r'\s*sup([^/]*)/sup\s*', r'\1 ', title)
    title = re.sub(r'\s*sub([^/]*)/sub\s*', r'\1 ', title)
    
    # Pattern 3: Handle empty/mangled tags like "<>+<>" or "< >+< >"
    # Common GROBID artifact: SPHINCS <>+<> -> SPHINCS+ (keep space after)
    title = re.sub(r'\s*<\s*>\s*([^<]*)\s*<\s*>\s*', r'\1 ', title)
    title = re.sub(r'\s*<>\s*', '', title)
    
    # Pattern 4: Handle self-closing or empty tags
    title = re.sub(r'<[^>]+/>', '', title)
    
    # Pattern 5: Remove any remaining HTML/XML tags
    title = re.sub(r'<[^>]+>', '', title)
    
    # Decode HTML entities
    title = html.unescape(title)
    
    # Clean up whitespace (normalizes multiple spaces to single)
    title = ' '.join(title.split())
    
    return title.strip()

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
        
        # Advanced accuracy settings
        self.tei_coordinates = GROBID_CONFIG.get("tei_coordinates", True)
        self.include_raw_affiliations = GROBID_CONFIG.get("include_raw_affiliations", True)
        self.consolidate_header = GROBID_CONFIG.get("consolidate_header", True)
        self.consolidate_citations = GROBID_CONFIG.get("consolidate_citations", True)
        
        # Ensure base URL doesn't end with slash
        self.base_url = self.base_url.rstrip('/')
        
        logger.info(f"GROBID initialized - base_url={self.base_url}, timeout={self.timeout}, "
                   f"consolidation={self.use_consolidation}, "
                   f"raw_citations={self.include_raw_citations}, "
                   f"enhanced_accuracy=True")
    
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
            # IMPORTANT FOR FRAUD DETECTION:
            # First parse WITHOUT consolidation to get the ORIGINAL authors from the citation
            # This preserves what the user actually wrote, which is critical for detecting author manipulation
            endpoint = f"{self.base_url}/api/processCitation"
            
            # Step 1: Parse without consolidation to get original data
            data_no_consolidate = {
                'citations': citation_text.strip(),
                'consolidateCitations': '0'  # NO consolidation first
            }
            
            response_original = requests.post(
                endpoint,
                data=data_no_consolidate,
                timeout=self.timeout,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            original_authors = []
            if response_original.status_code == 200:
                parsed_original = self._parse_citation_xml(response_original.text, citation_text)
                if parsed_original:
                    original_authors = parsed_original.get('authors', [])
            
            # Step 2: Parse with consolidation for enhanced metadata (DOI, full title, etc.)
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
                    # CRITICAL: Preserve original authors for fraud detection
                    # If we got original authors without consolidation, store them separately
                    if original_authors:
                        parsed_citation['original_authors'] = original_authors
                        # Use original authors as primary if consolidation changed them
                        if original_authors != parsed_citation.get('authors', []):
                            parsed_citation['consolidated_authors'] = parsed_citation.get('authors', [])
                            parsed_citation['authors'] = original_authors  # Use original for comparison
                            logger.debug(f"Preserved original authors for fraud detection: {original_authors}")
                    
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
                
                # Enhanced parameters for better processing and accuracy
                data = {}
                if use_consolidation:
                    data['consolidateHeader'] = '1'  # Consolidate header information
                    data['consolidateCitations'] = '1'  # Consolidate citations with external sources
                if include_raw_citations:
                    data['includeRawCitations'] = '1'  # Include raw citation strings
                if self.tei_coordinates:
                    data['teiCoordinates'] = '1'  # Include coordinates for better structure
                if self.generate_ids:
                    data['generateIDs'] = '1'  # Generate unique IDs
                
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
                
                # Enhanced parameters for full text processing with higher accuracy
                fulltext_data = {
                    'consolidateHeader': '1' if self.consolidate_header else '0',
                    'consolidateCitations': '1' if self.consolidate_citations else '0',
                    'includeRawCitations': '1' if include_raw_citations else '0',
                    'generateIDs': '1' if self.generate_ids else '0',
                    'segmentSentences': '1' if self.segment_sentences else '0',
                    'teiCoordinates': '1' if self.tei_coordinates else '0',
                    'includeRawAffiliations': '1' if self.include_raw_affiliations else '0'
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
            if title_elem is not None:
                # Get full text including child elements (handles <sup>, <sub>, etc.)
                title_text = ''.join(title_elem.itertext()).strip()
                # Clean up mangled HTML/XML artifacts from GROBID
                title_text = clean_extracted_title(title_text)
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


class SmartGrobidClient:
    """
    Smart GROBID client with automatic fallback chain:
    1. Try configured GROBID URL (public demo by default)
    2. Try local GROBID (localhost:8070) if available
    3. Fall back to PyMuPDF parser (lower accuracy) if all else fails
    
    This ensures VerifyRef always works, with graceful degradation.
    """
    
    def __init__(self):
        self.primary_url = GROBID_CONFIG["base_url"]
        self.fallback_urls = []
        
        # Build fallback chain (avoid duplicates)
        if self.primary_url != GROBID_PUBLIC_SERVER:
            self.fallback_urls.append(GROBID_PUBLIC_SERVER)
        if self.primary_url != GROBID_LOCAL_SERVER:
            self.fallback_urls.append(GROBID_LOCAL_SERVER)
        
        self._active_client = None
        self._active_source = None
        self._fallback_parser = None
    
    def _get_fallback_parser(self):
        """Lazy load fallback parser"""
        if self._fallback_parser is None:
            try:
                from grobid.fallback_parser import get_fallback_parser
                self._fallback_parser = get_fallback_parser()
            except ImportError:
                self._fallback_parser = None
        return self._fallback_parser
    
    def _find_available_grobid(self) -> Optional[GrobidClient]:
        """Find an available GROBID server from the fallback chain"""
        
        # Try primary URL first
        urls_to_try = [self.primary_url] + self.fallback_urls
        
        for url in urls_to_try:
            try:
                client = GrobidClient(base_url=url)
                if client.is_available():
                    logger.info(f"Using GROBID server: {url}")
                    self._active_source = url
                    return client
                else:
                    logger.debug(f"GROBID not available at {url}")
            except Exception as e:
                logger.debug(f"Failed to connect to GROBID at {url}: {e}")
        
        return None
    
    def extract_references(self, pdf_path: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract references with automatic fallback.
        
        Returns:
            List of references, or None if all methods fail
        """
        # Try GROBID servers first
        if self._active_client is None:
            self._active_client = self._find_available_grobid()
        
        if self._active_client:
            try:
                result = self._active_client.extract_references(pdf_path)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"GROBID extraction failed: {e}")
                # Reset client to try finding another
                self._active_client = None
                self._active_client = self._find_available_grobid()
                if self._active_client:
                    try:
                        result = self._active_client.extract_references(pdf_path)
                        if result:
                            return result
                    except:
                        pass
        
        # All GROBID servers failed - try fallback parser
        fallback = self._get_fallback_parser()
        if fallback and fallback.is_available():
            logger.warning("⚠️  GROBID unavailable - using fallback parser (lower accuracy)")
            return fallback.extract_references(pdf_path)
        
        logger.error("All reference extraction methods failed. "
                    "Install PyMuPDF for fallback: pip install PyMuPDF")
        return None
    
    def parse_citation_string(self, citation_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single citation string with automatic fallback.
        """
        # Try GROBID first
        if self._active_client is None:
            self._active_client = self._find_available_grobid()
        
        if self._active_client:
            try:
                result = self._active_client.parse_citation_string(citation_text)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"GROBID citation parsing failed: {e}")
        
        # Fallback to regex parser
        fallback = self._get_fallback_parser()
        if fallback and fallback.is_available():
            logger.debug("Using fallback parser for citation")
            return fallback.parse_citation_string(citation_text)
        
        return None
    
    def is_available(self) -> bool:
        """Check if any extraction method is available"""
        # Check GROBID
        if self._active_client is None:
            self._active_client = self._find_available_grobid()
        
        if self._active_client:
            return True
        
        # Check fallback
        fallback = self._get_fallback_parser()
        return fallback is not None and fallback.is_available()
    
    def get_active_source(self) -> str:
        """Return which source is being used for extraction"""
        if self._active_client:
            return f"GROBID ({self._active_source})"
        
        fallback = self._get_fallback_parser()
        if fallback and fallback.is_available():
            return "PyMuPDF Fallback (lower accuracy)"
        
        return "None available"


# Convenience function to get the smart client
_smart_client = None

def get_smart_client() -> SmartGrobidClient:
    """Get or create the smart GROBID client with fallback support"""
    global _smart_client
    if _smart_client is None:
        _smart_client = SmartGrobidClient()
    return _smart_client
