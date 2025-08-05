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

def normalize_author_name(author: str) -> str:
    """
    Normalize author name for better matching
    
    Args:
        author: Original author name
        
    Returns:
        Normalized author name
    """
    if not author:
        return ""
    
    # Remove extra whitespace and convert to lowercase
    normalized = re.sub(r'\s+', ' ', author.lower().strip())
    
    # Handle different name formats
    # "Last, First Middle" -> "first middle last"
    if ',' in normalized:
        parts = normalized.split(',', 1)
        if len(parts) == 2:
            last_name = parts[0].strip()
            first_names = parts[1].strip()
            normalized = f"{first_names} {last_name}"
    
    # Remove common prefixes/suffixes
    normalized = re.sub(r'\b(dr|prof|professor)\.\s*', '', normalized)
    normalized = re.sub(r'\s+(jr|sr|ii|iii)\.?$', '', normalized)
    
    # Handle initials - convert "J. Smith" to "j smith"
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
    
    norm_authors1 = [normalize_author_name(a) for a in authors1]
    norm_authors2 = [normalize_author_name(a) for a in authors2]
    
    # Remove empty names
    norm_authors1 = [a for a in norm_authors1 if a]
    norm_authors2 = [a for a in norm_authors2 if a]
    
    if not norm_authors1 or not norm_authors2:
        return 0.0
    
    # Find best matches between authors
    matches = 0
    total_comparisons = max(len(norm_authors1), len(norm_authors2))
    
    for author1 in norm_authors1:
        best_match = 0.0
        for author2 in norm_authors2:
            # Check if names are similar
            if author1 == author2:
                best_match = 1.0
                break
            elif author1 in author2 or author2 in author1:
                best_match = max(best_match, 0.8)
            else:
                # Check if last names match (common in academic citations)
                words1 = author1.split()
                words2 = author2.split()
                if words1 and words2 and words1[-1] == words2[-1]:
                    best_match = max(best_match, 0.6)
        
        if best_match > 0.5:
            matches += best_match
    
    return matches / total_comparisons