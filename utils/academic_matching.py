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
from typing import Dict, List

# Common venue abbreviations and full names
VENUE_ALIASES = {
    # Cryptography conferences
    'crypto': ['crypto', 'advances in cryptology', 'advances in cryptology - crypto'],
    'eurocrypt': ['eurocrypt', 'advances in cryptology', 'advances in cryptology - eurocrypt'],
    'asiacrypt': ['asiacrypt', 'advances in cryptology', 'advances in cryptology - asiacrypt'],
    'fse': ['fse', 'fast software encryption'],
    'ches': ['ches', 'cryptographic hardware and embedded systems'],
    'pkc': ['pkc', 'public key cryptography', 'theory and practice of public key cryptography'],
    'tcc': ['tcc', 'theory of cryptography'],
    'ccs': ['ccs', 'computer and communications security', 'acm conference on computer and communications security'],
    'sp': ['sp', 'ieee symposium on security and privacy', 'ieee s&p', 's&p'],
    'usenix security': ['usenix security', 'usenix security symposium'],
    'ndss': ['ndss', 'network and distributed system security'],
    
    # Cryptography journals  
    'iacr trans symmetric cryptol': ['iacr transactions on symmetric cryptology', 'iacr trans. symmetric cryptol.', 'tosc'],
    'iacr trans cryptogr hardw embed syst': ['iacr transactions on cryptographic hardware and embedded systems', 'iacr trans. cryptogr. hardw. embed. syst.', 'tches'],
    'journal of cryptology': ['j. cryptol.', 'journal of cryptology', 'joc'],
    'des codes cryptogr': ['designs, codes and cryptography', 'des. codes cryptogr.', 'dcc'],
    
    # Computer science conferences
    'stoc': ['stoc', 'symposium on theory of computing', 'acm symposium on theory of computing'],
    'focs': ['focs', 'foundations of computer science', 'ieee symposium on foundations of computer science'],
    'soda': ['soda', 'symposium on discrete algorithms', 'acm-siam symposium on discrete algorithms'],
    'icalp': ['icalp', 'international colloquium on automata, languages and programming'],
    
    # Security conferences
    'oakland': ['oakland', 'ieee symposium on security and privacy', 'ieee s&p', 'sp'],
    'acns': ['acns', 'applied cryptography and network security'],
    'acisp': ['acisp', 'australasian conference on information security and privacy'],
    'africacrypt': ['africacrypt', 'international conference on cryptology in africa'],
    'ctrsa': ['ct-rsa', 'ctrsa', 'rsa conference', 'topics in cryptology'],
    'indocrypt': ['indocrypt', 'international conference on cryptology in india'],
    'inscrypt': ['inscrypt', 'international conference on information security and cryptology'],
    'sac': ['sac', 'selected areas in cryptography'],
    'latincrypt': ['latincrypt', 'international conference on cryptology and information security in latin america'],
}

def normalize_venue_name(venue: str) -> str:
    """
    Normalize venue name for better matching
    
    Args:
        venue: Original venue name
        
    Returns:
        Normalized venue name
    """
    if not venue:
        return ""
    
    # Convert to lowercase and remove extra whitespace
    normalized = re.sub(r'\s+', ' ', venue.lower().strip())
    
    # Remove common prefixes/suffixes
    normalized = re.sub(r'^(international\s+)?(conference\s+on\s+)?', '', normalized)
    normalized = re.sub(r'\s+(conference|symposium|workshop|proceedings)(\s+\d{4})?$', '', normalized)
    
    # Remove year patterns
    normalized = re.sub(r'\s+\d{4}$', '', normalized)
    normalized = re.sub(r'\s+\(\d{4}\)$', '', normalized)
    
    # Remove volume/issue information
    normalized = re.sub(r'\s+vol\.\s*\d+', '', normalized)
    normalized = re.sub(r'\s+volume\s+\d+', '', normalized)
    normalized = re.sub(r'\s+pp\.\s*\d+[-–]\d+', '', normalized)
    
    # Remove punctuation except hyphens and ampersands
    normalized = re.sub(r'[^\w\s\-&]', '', normalized)
    
    # Normalize common abbreviations
    normalized = re.sub(r'\bintl\b', 'international', normalized)
    normalized = re.sub(r'\bconf\b', 'conference', normalized)
    normalized = re.sub(r'\bsymp\b', 'symposium', normalized)
    normalized = re.sub(r'\btrans\b', 'transactions', normalized)
    normalized = re.sub(r'\bj\b', 'journal', normalized)
    
    return normalized.strip()

def calculate_venue_similarity(venue1: str, venue2: str) -> float:
    """
    Calculate similarity between two venue names with academic context
    
    Args:
        venue1: First venue name
        venue2: Second venue name
        
    Returns:
        Similarity score (0.0 to 1.0)
    """
    if not venue1 or not venue2:
        return 0.0
    
    norm1 = normalize_venue_name(venue1)
    norm2 = normalize_venue_name(venue2)
    
    # Exact match after normalization
    if norm1 == norm2:
        return 1.0
    
    # Check if one is contained in the other (common for abbreviations)
    if norm1 in norm2 or norm2 in norm1:
        return 0.9
    
    # Check venue aliases
    for key, aliases in VENUE_ALIASES.items():
        if any(alias in norm1 for alias in aliases) and any(alias in norm2 for alias in aliases):
            return 0.85
    
    # Check for common words
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity for words
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    if union == 0:
        return 0.0
    
    jaccard = intersection / union
    
    # Boost score if key venue words match
    key_words = {'crypto', 'security', 'cryptology', 'symposium', 'conference', 'transactions', 'journal'}
    key_matches = len(words1.intersection(words2).intersection(key_words))
    
    if key_matches > 0:
        jaccard += 0.1 * key_matches
    
    return min(1.0, jaccard)

def clean_author_name(author: str) -> str:
    """
    Clean author name by removing database disambiguation artifacts
    
    Args:
        author: Original author name
        
    Returns:
        Cleaned author name
    """
    if not author:
        return author
    
    cleaned = str(author).strip()
    
    # Remove DBLP disambiguation numbers (e.g., " 0001", " 0002", etc.)
    cleaned = re.sub(r'\s+\d{4}$', '', cleaned)             # " 0001", " 0002"
    cleaned = re.sub(r'\s+\(\d+\)$', '', cleaned)           # " (1)", " (2)"
    cleaned = re.sub(r'\s+\[\d+\]$', '', cleaned)           # " [1]", " [2]"
    
    return cleaned.strip()

def normalize_author_name(author: str) -> str:
    """
    Normalize author name for better matching
    Includes cleaning of database disambiguation artifacts
    
    Args:
        author: Original author name
        
    Returns:
        Normalized author name
    """
    if not author:
        return ""
    
    # Clean database disambiguation artifacts in one pass
    cleaned = clean_author_name(author)
    
    # Normalize whitespace and convert to lowercase
    normalized = re.sub(r'\s+', ' ', cleaned.lower().strip())
    
    # Handle "Last, First" format
    if ',' in normalized:
        parts = normalized.split(',', 1)
        if len(parts) == 2:
            normalized = f"{parts[1].strip()} {parts[0].strip()}"
    
    # Remove titles and suffixes
    normalized = re.sub(r'\b(dr|prof|professor)\.\s*', '', normalized)
    normalized = re.sub(r'\s+(jr|sr|ii|iii)\.?$', '', normalized)
    
    # Convert "j. smith" to "j smith"
    normalized = re.sub(r'\b([a-z])\.\s*', r'\1 ', normalized)
    
    return normalized.strip()

def calculate_author_similarity(authors1: List[str], authors2: List[str]) -> float:
    """
    Calculate similarity between two author lists
    
    Args:
        authors1: First author list
        authors2: Second author list
        
    Returns:
        Similarity score (0.0 to 1.0)
    """
    if not authors1 or not authors2:
        return 0.0
    
    norm_authors1 = [normalize_author_name(a) for a in authors1 if a]
    norm_authors2 = [normalize_author_name(a) for a in authors2 if a]
    
    if not norm_authors1 or not norm_authors2:
        return 0.0
    
    def get_author_match_score(author1, author2):
        """Get similarity score between two authors with improved initial handling"""
        if author1 == author2:
            return 1.0
        elif author1 in author2 or author2 in author1:
            return 0.8
        else:
            words1, words2 = author1.split(), author2.split()
            if not words1 or not words2:
                return 0.0
            
            # Check if last names match
            if words1[-1] == words2[-1]:
                # Same last name - check first names/initials
                if len(words1) >= 1 and len(words2) >= 1:
                    first1, first2 = words1[0], words2[0]
                    
                    # Handle initial vs full name matching
                    if len(first1) == 1 and len(first2) > 1:
                        # first1 is initial, first2 is full name
                        if first2.startswith(first1):
                            return 0.9  # High score for initial match
                    elif len(first2) == 1 and len(first1) > 1:
                        # first2 is initial, first1 is full name
                        if first1.startswith(first2):
                            return 0.9  # High score for initial match
                    elif first1 == first2:
                        return 0.8  # Exact first name match
                
                return 0.6  # Same last name, different first names
            
            # Check for partial matches in multi-part names
            overlap = len(set(words1).intersection(set(words2)))
            if overlap > 0:
                total_words = len(set(words1).union(set(words2)))
                return 0.3 + (overlap / total_words) * 0.4  # 0.3-0.7 range
                
        return 0.0
    
    # Find best matches using list comprehension and max
    matches = sum(
        max((get_author_match_score(author1, author2) for author2 in norm_authors2), default=0.0)
        for author1 in norm_authors1
    )
    
    return matches / max(len(norm_authors1), len(norm_authors2))