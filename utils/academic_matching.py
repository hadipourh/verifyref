# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Hosein Hadipour
"""
Academic matching utilities for reference verification.

This module provides comprehensive matching functions for academic references:
- Author name matching (initials, transliterations, diacritics)
- Author list comparison with fraud detection
- Venue similarity with abbreviation handling
- Year similarity with asymmetric tolerance

Handles real-world variations in academic citations:
- Initials vs full names: "H. Hadipour" ↔ "Hosein Hadipour"
- Name ordering: "Hadipour, Hosein" ↔ "Hosein Hadipour"
- Transliterations: "Hosein" ↔ "Hossein" ↔ "Hussein"
- Diacritics: "José" ↔ "Jose", "Müller" ↔ "Mueller"
- Hyphenated names: "Jean-Pierre" ↔ "Jean Pierre"
- Venue abbreviations: "CRYPTO" ↔ "Advances in Cryptology"
"""

import re
import unicodedata
from typing import List, Tuple, Dict, Optional, Set
from dataclasses import dataclass
from enum import Enum


# ============================================================
# Enums and Data Classes
# ============================================================

class AuthorMatchType(Enum):
    """Types of author matches for detailed analysis"""
    EXACT = "exact"
    INITIAL_MATCH = "initial_match"           # H. Hadipour ↔ Hosein Hadipour
    TRANSLITERATION = "transliteration"        # Hosein ↔ Hossein
    PARTIAL = "partial"                        # Some name parts match
    LAST_NAME_ONLY = "last_name_only"         # Only surname matches
    NO_MATCH = "no_match"


@dataclass
class AuthorMatchResult:
    """Detailed result of comparing two author names"""
    match_type: AuthorMatchType
    confidence: float  # 0.0 to 1.0
    ref_author: str
    db_author: str
    details: Dict


@dataclass
class AuthorListComparisonResult:
    """Result of comparing two author lists with fraud detection"""
    overall_similarity: float
    first_author_match: Optional[AuthorMatchResult]
    matched_authors: List[AuthorMatchResult]
    unmatched_ref_authors: List[str]      # In reference but not in DB (potential injection)
    unmatched_db_authors: List[str]       # In DB but not in reference (potential removal)
    author_injection_detected: bool
    author_removal_detected: bool
    reordering_detected: bool


# ============================================================
# Name Transliteration Mappings
# ============================================================

NAME_TRANSLITERATIONS = {
    # Arabic/Persian names
    'hosein': {'hossein', 'hussein', 'hussain', 'husain', 'husein'},
    'hossein': {'hosein', 'hussein', 'hussain', 'husain', 'husein'},
    'hussein': {'hosein', 'hossein', 'hussain', 'husain', 'husein'},
    'mohammad': {'mohamed', 'muhammad', 'mohammed', 'muhammed', 'mohamad'},
    'mohamed': {'mohammad', 'muhammad', 'mohammed', 'muhammed', 'mohamad'},
    'muhammad': {'mohammad', 'mohamed', 'mohammed', 'muhammed', 'mohamad'},
    'ali': {'aly'},
    'ahmad': {'ahmed', 'ahmet'},
    'ahmed': {'ahmad', 'ahmet'},
    'hassan': {'hasan'},
    'hasan': {'hassan'},
    'reza': {'rida', 'ridha'},
    'amir': {'ameer'},
    
    # European names
    'jose': {'josé'},
    'josé': {'jose'},
    'muller': {'müller', 'mueller'},
    'müller': {'muller', 'mueller'},
    'mueller': {'muller', 'müller'},
    'bjorn': {'björn'},
    'björn': {'bjorn'},
    'jorg': {'jörg', 'joerg'},
    'jörg': {'jorg', 'joerg'},
    'joerg': {'jorg', 'jörg'},
    'andras': {'andrás'},
    'andrás': {'andras'},
    'francois': {'françois'},
    'françois': {'francois'},
    
    # Chinese name romanizations
    'xiao': {'hsiao', 'shiao'},
    'zhang': {'chang'},
    'wang': {'wong'},
    'chen': {'chan'},
    'liu': {'lau', 'liew'},
    'li': {'lee', 'ly'},
    'zhou': {'chou', 'chow'},
    'wu': {'woo', 'ng'},
    'huang': {'wong', 'hwang'},
    'yang': {'yeung'},
    
    # Russian names
    'alexander': {'aleksandr', 'alexsandr'},
    'aleksandr': {'alexander', 'alexsandr'},
    'dmitri': {'dmitry', 'dmitrii'},
    'dmitry': {'dmitri', 'dmitrii'},
    'sergei': {'sergey', 'serguei'},
    'sergey': {'sergei', 'serguei'},
    'andrei': {'andrey', 'andre'},
    'andrey': {'andrei', 'andre'},
    'yuri': {'yury', 'yurii'},
    
    # Other common variations
    'michael': {'mikhail', 'michel'},
    'john': {'johann', 'jean', 'jan', 'juan', 'giovanni', 'joao'},
    'peter': {'pierre', 'pedro', 'pietro', 'piotr', 'petr'},
    'william': {'wilhelm', 'guillaume', 'guillermo'},
    'james': {'jacob', 'jacques', 'jaime', 'giacomo'},
    'george': {'georg', 'georges', 'jorge', 'giorgio'},
    'paul': {'pablo', 'paolo', 'pavel'},
    'thomas': {'tomas', 'tommaso'},
    'daniel': {'daniele', 'danilo'},
    'david': {'davide'},
    'robert': {'roberto'},
    'christopher': {'christoph', 'cristopher', 'kristopher'},
}


# ============================================================
# Venue Aliases
# ============================================================

VENUE_ALIASES = {
    # Cryptography conferences
    'crypto': {'advances in cryptology', 'crypto', 'annual international cryptology conference'},
    'eurocrypt': {'advances in cryptology - eurocrypt', 'eurocrypt', 'annual eurocrypt conference'},
    'asiacrypt': {'advances in cryptology - asiacrypt', 'asiacrypt', 'annual asiacrypt conference'},
    'fse': {'fast software encryption', 'fse'},
    'ches': {'cryptographic hardware and embedded systems', 'ches'},
    'pkc': {'public key cryptography', 'pkc'},
    'tcc': {'theory of cryptography', 'tcc', 'theory of cryptography conference'},
    
    # Security conferences
    'sp': {'ieee symposium on security and privacy', 'oakland', 's&p', 'ieee s&p'},
    'ccs': {'acm conference on computer and communications security', 'acm ccs'},
    'usenix security': {'usenix security symposium', 'usenix security'},
    'ndss': {'network and distributed system security', 'ndss symposium'},
    
    # Machine learning conferences
    'neurips': {'advances in neural information processing systems', 'neurips', 'nips'},
    'icml': {'international conference on machine learning', 'icml'},
    'iclr': {'international conference on learning representations', 'iclr'},
    'aaai': {'aaai conference on artificial intelligence', 'aaai'},
    'ijcai': {'international joint conference on artificial intelligence', 'ijcai'},
    
    # Computer vision conferences
    'cvpr': {'ieee conference on computer vision and pattern recognition', 'cvpr'},
    'iccv': {'ieee international conference on computer vision', 'iccv'},
    'eccv': {'european conference on computer vision', 'eccv'},
    
    # NLP conferences
    'acl': {'annual meeting of the association for computational linguistics', 'acl'},
    'emnlp': {'conference on empirical methods in natural language processing', 'emnlp'},
    'naacl': {'north american chapter of the association for computational linguistics', 'naacl'},
    
    # Database conferences
    'sigmod': {'acm sigmod', 'sigmod'},
    'vldb': {'very large data bases', 'vldb', 'pvldb'},
    
    # Systems conferences
    'osdi': {'usenix symposium on operating systems design and implementation', 'osdi'},
    'sosp': {'acm symposium on operating systems principles', 'sosp'},
    
    # Theory conferences
    'stoc': {'symposium on theory of computing', 'stoc'},
    'focs': {'ieee symposium on foundations of computer science', 'focs'},
    
    # Journals
    'jacm': {'journal of the acm', 'jacm'},
    'cacm': {'communications of the acm', 'cacm'},
    'joc': {'journal of cryptology', 'joc'},
    'tocs': {'acm transactions on computer systems', 'tocs'},
    'tosc': {'iacr transactions on symmetric cryptology', 'tosc'},
    'tches': {'iacr transactions on cryptographic hardware and embedded systems', 'tches'},
    
    # Preprints
    'arxiv': {'arxiv', 'arxiv preprint', 'arxiv.org'},
    'iacr eprint': {'iacr eprint', 'cryptology eprint archive', 'eprint', 'iacr cryptology eprint'},
}

# Build reverse lookup for venue aliases
_VENUE_REVERSE_LOOKUP = {}
for canonical, aliases in VENUE_ALIASES.items():
    for alias in aliases:
        _VENUE_REVERSE_LOOKUP[alias.lower()] = canonical
    _VENUE_REVERSE_LOOKUP[canonical.lower()] = canonical


# ============================================================
# Basic Text Utilities
# ============================================================

def remove_diacritics(text: str) -> str:
    """Remove diacritical marks from text (é → e, ü → u, etc.)"""
    if not text:
        return text
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


def clean_author_name(author: str) -> str:
    """
    Clean author name by removing database disambiguation artifacts.
    
    Removes DBLP disambiguation numbers like " 0001", " (1)", etc.
    
    Args:
        author: Original author name
        
    Returns:
        Cleaned author name
    """
    if not author:
        return author
    
    cleaned = str(author).strip()
    
    # Remove DBLP disambiguation numbers
    cleaned = re.sub(r'\s+\d{4}$', '', cleaned)     # " 0001", " 0002"
    cleaned = re.sub(r'\s+\(\d+\)$', '', cleaned)   # " (1)", " (2)"
    cleaned = re.sub(r'\s+\[\d+\]$', '', cleaned)   # " [1]", " [2]"
    
    return cleaned.strip()


# ============================================================
# Author Name Matching
# ============================================================

def normalize_author_name(author: str) -> str:
    """
    Normalize author name for basic matching.
    
    This is the simple version for backward compatibility.
    For advanced matching, use normalize_author_name_advanced().
    
    Args:
        author: Original author name
        
    Returns:
        Normalized author name
    """
    if not author:
        return ""
    
    cleaned = clean_author_name(author)
    normalized = re.sub(r'\s+', ' ', cleaned.lower().strip())
    
    # Handle "Last, First" format
    if ',' in normalized:
        parts = normalized.split(',', 1)
        if len(parts) == 2:
            normalized = f"{parts[1].strip()} {parts[0].strip()}"
    
    # Remove titles and suffixes
    normalized = re.sub(r'\b(dr|prof|professor)\.\s*', '', normalized)
    normalized = re.sub(r'\s+(jr|sr|ii|iii)\.?$', '', normalized)
    
    # Convert "j." to "j "
    normalized = re.sub(r'\b([a-z])\.\s*', r'\1 ', normalized)
    
    return normalized.strip()


def normalize_author_name_advanced(author: str) -> Tuple[str, List[str], str]:
    """
    Advanced author name normalization with part extraction.
    
    Returns:
        Tuple of (normalized_full_name, name_parts, last_name)
    """
    if not author:
        return "", [], ""
    
    cleaned = str(author).strip().lower()
    
    # Remove database disambiguation
    cleaned = re.sub(r'\s+\d{4}$', '', cleaned)
    cleaned = re.sub(r'\s+\(\d+\)$', '', cleaned)
    cleaned = re.sub(r'\s+\[\d+\]$', '', cleaned)
    
    # Remove titles and honorifics
    cleaned = re.sub(r'\b(dr|prof|professor|mr|mrs|ms|sir|dame)\.\s*', '', cleaned)
    cleaned = re.sub(r'\s+(jr|sr|ii|iii|iv|phd|md|esq)\.?$', '', cleaned)
    
    # Handle "Last, First Middle" format
    if ',' in cleaned:
        parts = cleaned.split(',', 1)
        if len(parts) == 2:
            cleaned = f"{parts[1].strip()} {parts[0].strip()}"
    
    # Remove diacritics for matching
    cleaned = remove_diacritics(cleaned)
    
    # Normalize periods and hyphens
    cleaned = re.sub(r'\.', ' ', cleaned)
    cleaned = re.sub(r'-', ' ', cleaned)
    
    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    parts = cleaned.split()
    last_name = parts[-1] if parts else ""
    
    # Handle multi-part surnames
    if len(parts) >= 2:
        surname_prefixes = {'van', 'von', 'de', 'del', 'della', 'di', 'da', 'dos', 'das', 'le', 'la', 'el', 'al'}
        if parts[-2].lower() in surname_prefixes:
            last_name = f"{parts[-2]} {parts[-1]}"
    
    return cleaned, parts, last_name


def are_names_transliterations(name1: str, name2: str) -> bool:
    """Check if two names are transliteration variants of each other."""
    n1 = remove_diacritics(name1.lower().strip())
    n2 = remove_diacritics(name2.lower().strip())
    
    if n1 == n2:
        return True
    
    if n1 in NAME_TRANSLITERATIONS and n2 in NAME_TRANSLITERATIONS.get(n1, set()):
        return True
    if n2 in NAME_TRANSLITERATIONS and n1 in NAME_TRANSLITERATIONS.get(n2, set()):
        return True
    
    return False


def match_initials(initial: str, full_name: str) -> bool:
    """Check if an initial matches a full name."""
    if not initial or not full_name:
        return False
    
    initial = initial.lower().strip().rstrip('.')
    full_name = full_name.lower().strip()
    
    if len(initial) == 1:
        return full_name.startswith(initial)
    
    return False


def compare_author_names(ref_author: str, db_author: str) -> AuthorMatchResult:
    """
    Compare two author names with academic-aware matching.
    
    Handles initials, transliterations, diacritics, and name ordering.
    
    Args:
        ref_author: Author name from reference being verified
        db_author: Author name from database (ground truth)
        
    Returns:
        AuthorMatchResult with match type and confidence
    """
    if not ref_author or not db_author:
        return AuthorMatchResult(
            match_type=AuthorMatchType.NO_MATCH,
            confidence=0.0,
            ref_author=ref_author or "",
            db_author=db_author or "",
            details={"reason": "empty_name"}
        )
    
    # Normalize both names
    ref_norm, ref_parts, ref_last = normalize_author_name_advanced(ref_author)
    db_norm, db_parts, db_last = normalize_author_name_advanced(db_author)
    
    # Exact match after normalization
    if ref_norm == db_norm:
        return AuthorMatchResult(
            match_type=AuthorMatchType.EXACT,
            confidence=1.0,
            ref_author=ref_author,
            db_author=db_author,
            details={"match": "exact_normalized"}
        )
    
    # Check if last names match (required for most match types)
    last_name_match = (
        ref_last == db_last or 
        are_names_transliterations(ref_last, db_last)
    )
    
    if not last_name_match:
        return AuthorMatchResult(
            match_type=AuthorMatchType.NO_MATCH,
            confidence=0.0,
            ref_author=ref_author,
            db_author=db_author,
            details={"reason": "last_names_differ"}
        )
    
    # Last names match - now check first names/initials
    ref_first_parts = ref_parts[:-1] if len(ref_parts) > 1 else []
    db_first_parts = db_parts[:-1] if len(db_parts) > 1 else []
    
    # Handle case where one has only last name
    if not ref_first_parts or not db_first_parts:
        return AuthorMatchResult(
            match_type=AuthorMatchType.LAST_NAME_ONLY,
            confidence=0.6,
            ref_author=ref_author,
            db_author=db_author,
            details={"match": "last_name_only"}
        )
    
    ref_first = ref_first_parts[0] if ref_first_parts else ""
    db_first = db_first_parts[0] if db_first_parts else ""
    
    # Full first name match (with transliteration)
    if ref_first == db_first or are_names_transliterations(ref_first, db_first):
        return AuthorMatchResult(
            match_type=AuthorMatchType.EXACT,
            confidence=0.95,
            ref_author=ref_author,
            db_author=db_author,
            details={"match": "first_and_last"}
        )
    
    # Initial matching: "h" vs "hosein"
    if len(ref_first) == 1 and len(db_first) > 1:
        if match_initials(ref_first, db_first):
            return AuthorMatchResult(
                match_type=AuthorMatchType.INITIAL_MATCH,
                confidence=0.85,
                ref_author=ref_author,
                db_author=db_author,
                details={"match": "ref_initial_to_db_full"}
            )
    elif len(db_first) == 1 and len(ref_first) > 1:
        if match_initials(db_first, ref_first):
            return AuthorMatchResult(
                match_type=AuthorMatchType.INITIAL_MATCH,
                confidence=0.85,
                ref_author=ref_author,
                db_author=db_author,
                details={"match": "db_initial_to_ref_full"}
            )
    
    # Both are initials
    if len(ref_first) == 1 and len(db_first) == 1:
        if ref_first == db_first:
            return AuthorMatchResult(
                match_type=AuthorMatchType.INITIAL_MATCH,
                confidence=0.7,
                ref_author=ref_author,
                db_author=db_author,
                details={"match": "both_initials"}
            )
    
    # Last name matches but first name doesn't
    return AuthorMatchResult(
        match_type=AuthorMatchType.LAST_NAME_ONLY,
        confidence=0.4,
        ref_author=ref_author,
        db_author=db_author,
        details={"reason": "first_names_differ"}
    )


def compare_author_lists(
    ref_authors: List[str],
    db_authors: List[str],
    check_first_author: bool = True
) -> AuthorListComparisonResult:
    """
    Compare two author lists with fraud detection.
    
    Detects:
    - Author injection (fake authors added to real paper)
    - Author removal (real authors removed)
    - Author reordering
    
    Args:
        ref_authors: Authors from the reference being verified
        db_authors: Authors from the database (ground truth)
        check_first_author: Whether to specially check first author match
    
    Returns:
        AuthorListComparisonResult with fraud indicators
    """
    if not ref_authors or not db_authors:
        return AuthorListComparisonResult(
            overall_similarity=0.0,
            first_author_match=None,
            matched_authors=[],
            unmatched_ref_authors=ref_authors or [],
            unmatched_db_authors=db_authors or [],
            author_injection_detected=bool(ref_authors and not db_authors),
            author_removal_detected=bool(db_authors and not ref_authors),
            reordering_detected=False
        )
    
    matched_authors: List[AuthorMatchResult] = []
    ref_matched_indices: Set[int] = set()
    db_matched_indices: Set[int] = set()
    
    # Match each reference author to database authors
    for i, ref_author in enumerate(ref_authors):
        best_match: Optional[AuthorMatchResult] = None
        best_db_idx: int = -1
        
        for j, db_author in enumerate(db_authors):
            if j in db_matched_indices:
                continue
            
            match = compare_author_names(ref_author, db_author)
            
            if match.match_type != AuthorMatchType.NO_MATCH:
                if best_match is None or match.confidence > best_match.confidence:
                    best_match = match
                    best_db_idx = j
        
        if best_match and best_match.confidence >= 0.4:
            matched_authors.append(best_match)
            ref_matched_indices.add(i)
            db_matched_indices.add(best_db_idx)
    
    # Identify unmatched authors
    unmatched_ref = [ref_authors[i] for i in range(len(ref_authors)) if i not in ref_matched_indices]
    unmatched_db = [db_authors[i] for i in range(len(db_authors)) if i not in db_matched_indices]
    
    # Check first author match
    first_author_match = None
    if check_first_author and ref_authors and db_authors:
        first_author_match = compare_author_names(ref_authors[0], db_authors[0])
    
    # Detect author injection (requires at least 2 matches to distinguish from complete swap)
    author_injection = len(unmatched_ref) > 0 and len(matched_authors) >= 2
    
    # Detect author removal
    author_removal = len(unmatched_db) > 0 and len(matched_authors) >= 1
    
    # Detect reordering
    reordering = False
    if first_author_match and first_author_match.match_type == AuthorMatchType.NO_MATCH:
        for j, db_author in enumerate(db_authors[1:], 1):
            match = compare_author_names(ref_authors[0], db_author)
            if match.confidence >= 0.8:
                reordering = True
                break
    
    # Calculate overall similarity
    if not matched_authors:
        overall_sim = 0.0
    else:
        total_confidence = sum(m.confidence for m in matched_authors)
        max_possible = max(len(ref_authors), len(db_authors))
        overall_sim = total_confidence / max_possible
        
        # Penalties for unmatched authors
        injection_penalty = len(unmatched_ref) * 0.1
        removal_penalty = len(unmatched_db) * 0.05  # Less penalty (might be "et al.")
        
        overall_sim = max(0.0, overall_sim - injection_penalty - removal_penalty)
    
    return AuthorListComparisonResult(
        overall_similarity=overall_sim,
        first_author_match=first_author_match,
        matched_authors=matched_authors,
        unmatched_ref_authors=unmatched_ref,
        unmatched_db_authors=unmatched_db,
        author_injection_detected=author_injection,
        author_removal_detected=author_removal,
        reordering_detected=reordering
    )


def calculate_author_similarity(authors1: List[str], authors2: List[str]) -> float:
    """
    Calculate similarity between two author lists.
    
    This is the simple version for backward compatibility.
    For detailed analysis, use compare_author_lists().
    
    Args:
        authors1: First author list
        authors2: Second author list
        
    Returns:
        Similarity score (0.0 to 1.0)
    """
    result = compare_author_lists(authors1, authors2)
    return result.overall_similarity


# ============================================================
# Venue Matching
# ============================================================

def normalize_venue_name(venue: str) -> str:
    """
    Normalize venue name for matching.
    
    Args:
        venue: Original venue name
        
    Returns:
        Normalized venue name
    """
    if not venue:
        return ""
    
    normalized = re.sub(r'\s+', ' ', venue.lower().strip())
    
    # Remove year patterns
    normalized = re.sub(r'[\(\-,\s]*\d{4}[\)\s]*$', '', normalized)
    normalized = re.sub(r'\s+\d{4}\s+', ' ', normalized)
    
    # Remove common prefixes/suffixes
    normalized = re.sub(r'^proceedings of (the\s+)?', '', normalized)
    normalized = re.sub(r'\s+proceedings$', '', normalized)
    normalized = re.sub(r'^\d+(st|nd|rd|th)\s+', '', normalized)
    normalized = re.sub(r'\s+\d+(st|nd|rd|th)\s+', ' ', normalized)
    
    # Remove LNCS/volume info
    normalized = re.sub(r'lecture notes in computer science.*', '', normalized)
    normalized = re.sub(r'lncs\s*\d+', '', normalized)
    normalized = re.sub(r'volume\s*\d+', '', normalized)
    normalized = re.sub(r'\s+vol\.\s*\d+', '', normalized)
    normalized = re.sub(r'\s+pp\.\s*\d+[-–]\d+', '', normalized)
    
    # Remove punctuation except hyphens and ampersands
    normalized = re.sub(r'[^\w\s\-&]', '', normalized)
    
    return normalized.strip()


def get_canonical_venue(venue: str) -> str:
    """Get canonical venue name if known."""
    normalized = normalize_venue_name(venue)
    
    if normalized in _VENUE_REVERSE_LOOKUP:
        return _VENUE_REVERSE_LOOKUP[normalized]
    
    for key, canonical in _VENUE_REVERSE_LOOKUP.items():
        if key in normalized or normalized in key:
            return canonical
    
    return normalized


def calculate_venue_similarity(venue1: str, venue2: str) -> float:
    """
    Calculate similarity between two venue names.
    
    Handles abbreviations, full names, and year variations.
    
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
    
    # Check canonical names
    canon1 = get_canonical_venue(venue1)
    canon2 = get_canonical_venue(venue2)
    
    if canon1 == canon2:
        return 0.95
    
    # One contains the other
    if norm1 in norm2 or norm2 in norm1:
        return 0.85
    
    # Check venue aliases
    for key, aliases in VENUE_ALIASES.items():
        if any(alias in norm1 for alias in aliases) and any(alias in norm2 for alias in aliases):
            return 0.85
    
    # Calculate word overlap
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    stopwords = {'the', 'of', 'on', 'in', 'for', 'and', 'a', 'an', 'at', 'to', 
                 'annual', 'international', 'conference', 'symposium', 'workshop'}
    words1 -= stopwords
    words2 -= stopwords
    
    if words1 and words2:
        overlap = len(words1 & words2)
        max_terms = max(len(words1), len(words2))
        jaccard = overlap / max_terms if max_terms > 0 else 0
        
        if jaccard >= 0.5:
            return 0.7 + jaccard * 0.2
    
    # Fallback: character-level similarity
    from difflib import SequenceMatcher
    return SequenceMatcher(None, norm1, norm2).ratio()
