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

Parsing utilities for different input types
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List
import logging

from grobid.client import GrobidClient

logger = logging.getLogger(__name__)

def detect_input_type(input_str: str) -> str:
    """
    Detect the type of input:
    - 'pdf' for PDF file paths
    - 'text_file' for text file paths  
    - 'single_reference' for single reference strings
    """
    if os.path.exists(input_str):
        if input_str.lower().endswith('.pdf'):
            return 'pdf'
        elif input_str.lower().endswith(('.txt', '.text')):
            return 'text_file'
        else:
            # Check if it's a readable text file
            try:
                with open(input_str, 'r', encoding='utf-8') as f:
                    f.read(100)  # Try to read first 100 chars
                return 'text_file'
            except:
                return 'single_reference'
    else:
        return 'single_reference'

def parse_single_reference_to_raw(reference_text: str) -> Dict[str, Any]:
    """Parse a single reference string using GROBID's processCitation endpoint"""
    try:
        logger.debug(f"Parsing single reference: {reference_text[:100]}...")
        
        grobid_client = GrobidClient()
        
        # Use GROBID's processCitation endpoint for single reference parsing
        parsed_data = grobid_client.parse_citation_string(reference_text)
        
        if parsed_data:
            logger.debug(f"Successfully parsed reference with title: {parsed_data.get('title', 'Unknown')}")
            return {
                'raw_text': reference_text,
                **parsed_data
            }
        else:
            logger.warning(f"GROBID failed to parse reference: {reference_text[:50]}...")
            return {
                'raw_text': reference_text,
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
            
    except Exception as e:
        logger.error(f"Error parsing single reference: {e}")
        return {
            'raw_text': reference_text,
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

def parse_text_file_to_raw(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse a text file containing references into a list of raw reference dictionaries.
    Uses a hybrid approach: manual text file structure parsing + GROBID citation parsing.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by lines and clean up
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        references = []
        current_ref = ""
        
        for line in lines:
            # Check if this looks like a new reference (starts with number or bullet)
            if re.match(r'^\s*\d+\.?\s*', line) or re.match(r'^\s*[\-\*\•]\s*', line):
                # Save previous reference if we have one
                if current_ref.strip():
                    # Parse using GROBID
                    parsed_ref = parse_single_reference_to_raw(current_ref.strip())
                    references.append(parsed_ref)
                
                # Clean the line (remove numbering/bullets)
                current_ref = re.sub(r'^\s*(\d+\.?|\-|\*|\•)\s*', '', line)
            else:
                # Continue current reference
                if current_ref:
                    current_ref += " " + line
                else:
                    current_ref = line
        
        # Don't forget the last reference
        if current_ref.strip():
            parsed_ref = parse_single_reference_to_raw(current_ref.strip())
            references.append(parsed_ref)
        
        logger.info(f"Successfully parsed {len(references)} references from text file")
        return references
        
    except Exception as e:
        logger.error(f"Error parsing text file {file_path}: {e}")
        return []
