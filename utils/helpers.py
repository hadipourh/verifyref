"""
RefifyRef - High-performance academic reference verification tool
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

import re
import string
from typing import List, Optional, Union
from difflib import SequenceMatcher
import unicodedata

def normalize_text(text: str) -> str:
    """
    Normalize text for comparison by removing extra whitespace, 
    normalizing unicode, and standardizing case
    
    Args:
        text: Input text string
        
    Returns:
        Normalized text string
    """
    if not text:
        return ''
    
    # Convert to string if not already
    text = str(text)
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    
    # Remove control characters
    text = ''.join(char for char in text if not unicodedata.category(char).startswith('C'))
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def calculate_text_similarity(text1: str, text2: str, method: str = 'sequence_matcher') -> float:
    """
    Calculate similarity between two text strings
    
    Args:
        text1: First text string
        text2: Second text string
        method: Similarity calculation method ('sequence_matcher', 'jaccard', 'cosine')
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0
    
    # Normalize texts
    text1 = normalize_text(text1).lower()
    text2 = normalize_text(text2).lower()
    
    if text1 == text2:
        return 1.0
    
    if method == 'sequence_matcher':
        return SequenceMatcher(None, text1, text2).ratio()
    
    elif method == 'jaccard':
        return _jaccard_similarity(text1, text2)
    
    elif method == 'cosine':
        return _cosine_similarity(text1, text2)
    
    else:
        # Default to sequence matcher
        return SequenceMatcher(None, text1, text2).ratio()

def _jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity coefficient"""
    # Split into words
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    if not words1 and not words2:
        return 1.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0

def _cosine_similarity(text1: str, text2: str) -> float:
    """Calculate cosine similarity"""
    import math
    from collections import Counter
    
    # Get word counts
    words1 = text1.split()
    words2 = text2.split()
    
    if not words1 or not words2:
        return 0.0
    
    # Create word vectors
    counter1 = Counter(words1)
    counter2 = Counter(words2)
    
    # Get all unique words
    all_words = set(counter1.keys()).union(set(counter2.keys()))
    
    # Create vectors
    vector1 = [counter1.get(word, 0) for word in all_words]
    vector2 = [counter2.get(word, 0) for word in all_words]
    
    # Calculate cosine similarity
    dot_product = sum(a * b for a, b in zip(vector1, vector2))
    magnitude1 = math.sqrt(sum(a * a for a in vector1))
    magnitude2 = math.sqrt(sum(a * a for a in vector2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)

def extract_year_from_text(text: str) -> Optional[int]:
    """
    Extract a publication year from text
    
    Args:
        text: Text that may contain a year
        
    Returns:
        Extracted year as integer or None if not found
    """
    if not text:
        return None
    
    # Look for 4-digit years in reasonable range
    year_pattern = r'\b(19[5-9]\d|20[0-4]\d)\b'
    matches = re.findall(year_pattern, text)
    
    if matches:
        # Return the first valid year found
        try:
            return int(matches[0])
        except ValueError:
            pass
    
    return None

def clean_author_name(name: str) -> str:
    """
    Clean and normalize author name
    
    Args:
        name: Raw author name
        
    Returns:
        Cleaned author name
    """
    if not name:
        return ''
    
    name = normalize_text(name)
    
    # Remove common prefixes/suffixes
    name = re.sub(r'^(Dr\.?|Prof\.?|Mr\.?|Ms\.?|Mrs\.?)\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+(Jr\.?|Sr\.?|III?|IV)$', '', name, flags=re.IGNORECASE)
    
    # Remove extra punctuation
    name = re.sub(r'[^\w\s\.\-]', '', name)
    
    return name.strip()

def extract_doi_from_text(text: str) -> Optional[str]:
    """
    Extract DOI from text
    
    Args:
        text: Text that may contain a DOI
        
    Returns:
        Extracted DOI string or None if not found
    """
    if not text:
        return None
    
    # DOI pattern
    doi_pattern = r'(?:doi:?\s*|https?://(?:dx\.)?doi\.org/)(10\.\d+/[^\s]+)'
    
    match = re.search(doi_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None

def remove_punctuation(text: str, keep_spaces: bool = True) -> str:
    """
    Remove punctuation from text
    
    Args:
        text: Input text
        keep_spaces: Whether to keep spaces
        
    Returns:
        Text with punctuation removed
    """
    if not text:
        return ''
    
    if keep_spaces:
        # Remove punctuation but keep spaces
        translator = str.maketrans('', '', string.punctuation)
        return text.translate(translator)
    else:
        # Remove punctuation and spaces
        translator = str.maketrans('', '', string.punctuation + ' ')
        return text.translate(translator)

def split_author_list(author_string: str) -> List[str]:
    """
    Split a string containing multiple authors into individual names
    
    Args:
        author_string: String with multiple authors
        
    Returns:
        List of individual author names
    """
    if not author_string:
        return []
    
    # Common separators for author lists
    separators = [';', ' and ', ' & ', ',']
    
    authors = [author_string]
    
    for separator in separators:
        new_authors = []
        for author in authors:
            new_authors.extend(author.split(separator))
        authors = new_authors
    
    # Clean each author name
    cleaned_authors = []
    for author in authors:
        cleaned = clean_author_name(author)
        if cleaned and cleaned.lower() not in ['et al', 'et al.', 'others']:
            cleaned_authors.append(cleaned)
        elif cleaned.lower() in ['et al', 'et al.']:
            cleaned_authors.append('et al.')
            break  # Stop processing after et al.
    
    return cleaned_authors

def format_reference_citation(reference: dict) -> str:
    """
    Format a reference dictionary as a citation string
    
    Args:
        reference: Reference dictionary
        
    Returns:
        Formatted citation string
    """
    parts = []
    
    # Authors
    authors = reference.get('authors', [])
    if authors:
        if len(authors) == 1:
            parts.append(authors[0])
        elif len(authors) <= 3:
            parts.append(', '.join(authors[:-1]) + ' and ' + authors[-1])
        else:
            parts.append(authors[0] + ' et al.')
    
    # Year
    year = reference.get('year')
    if year:
        if parts:
            parts.append(f"({year})")
        else:
            parts.append(str(year))
    
    # Title
    title = reference.get('title')
    if title:
        parts.append(f'"{title}"')
    
    # Venue
    venue = reference.get('venue')
    if venue:
        parts.append(venue)
    
    # Volume and pages
    volume = reference.get('volume')
    pages = reference.get('pages')
    
    if volume and pages:
        parts.append(f"vol. {volume}, pp. {pages}")
    elif volume:
        parts.append(f"vol. {volume}")
    elif pages:
        parts.append(f"pp. {pages}")
    
    return '. '.join(parts) + '.' if parts else 'Unknown reference'

def calculate_levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings
    
    Args:
        s1: First string
        s2: Second string
        
    Returns:
        Levenshtein distance
    """
    if not s1:
        return len(s2) if s2 else 0
    if not s2:
        return len(s1)
    
    # Create matrix
    rows = len(s1) + 1
    cols = len(s2) + 1
    
    # Initialize first row and column
    matrix = [[0] * cols for _ in range(rows)]
    
    for i in range(rows):
        matrix[i][0] = i
    for j in range(cols):
        matrix[0][j] = j
    
    # Fill the matrix
    for i in range(1, rows):
        for j in range(1, cols):
            if s1[i-1] == s2[j-1]:
                cost = 0
            else:
                cost = 1
            
            matrix[i][j] = min(
                matrix[i-1][j] + 1,      # deletion
                matrix[i][j-1] + 1,      # insertion
                matrix[i-1][j-1] + cost  # substitution
            )
    
    return matrix[rows-1][cols-1]

def is_valid_year(year: Union[str, int]) -> bool:
    """
    Check if a year value is valid for academic publications
    
    Args:
        year: Year value to check
        
    Returns:
        True if year is valid, False otherwise
    """
    try:
        year_int = int(year)
        # Reasonable range for academic publications
        return 1950 <= year_int <= 2030
    except (ValueError, TypeError):
        return False

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix