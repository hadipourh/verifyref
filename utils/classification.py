# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 Hosein Hadipour
"""
Enhanced classification logic for academic reference verification.

This module implements a multi-stage classification approach that handles
real-world academic reference formats and detects various types of fraud.

Key improvements over simple weighted averaging:
1. Conditional logic that catches fraud patterns
2. Author injection/removal detection
3. Venue tier plausibility checking
4. Asymmetric year validation
5. Source credibility weighting
6. Hard floors to prevent AI override of clear fraud
"""

import re
import logging
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from utils.academic_matching import (
    compare_author_lists,
    calculate_venue_similarity,
    AuthorListComparisonResult,
    AuthorMatchType
)
from utils.helpers import calculate_text_similarity, normalize_text

logger = logging.getLogger(__name__)


class FraudType(Enum):
    """Types of detected fraud"""
    NONE = "none"
    AUTHOR_INJECTION = "author_injection"      # Fake authors added
    AUTHOR_REMOVAL = "author_removal"          # Real authors removed
    AUTHOR_SWAP = "author_swap"                # Completely different authors
    TITLE_MANIPULATION = "title_manipulation"  # Modified title
    VENUE_FABRICATION = "venue_fabrication"    # Fake venue claimed
    COMPLETE_FABRICATION = "complete_fabrication"  # Entire reference made up
    DOI_FRAUD = "doi_fraud"                    # Real DOI with wrong metadata


@dataclass
class EnhancedClassificationResult:
    """Detailed classification result with fraud analysis"""
    classification: str  # authentic, suspicious, fake, author_manipulation, fabricated, inconclusive
    confidence: float
    similarity_breakdown: Dict[str, float]
    fraud_indicators: List[FraudType]
    fraud_details: Dict[str, Any]
    evidence_strength: Dict[str, float]  # Per-source evidence
    reasons: List[str]
    requires_manual_review: bool
    review_priority: str  # low, medium, high, critical
    issue_summary: str = ""  # Brief human-readable issue description for reviewers


# Venue tier classification for plausibility checking
VENUE_TIERS = {
    "preprints": {
        "arxiv", "biorxiv", "medrxiv", "iacr eprint", "cryptology eprint",
        "eprint archive", "ssrn", "preprint"
    },
    "tier1_journals": {
        "nature", "science", "cell", "lancet", "nejm", "new england journal",
        "journal of cryptology", "ieee transactions", "acm transactions",
        "journal of the acm", "siam journal"
    },
    "tier1_conferences": {
        "crypto", "eurocrypt", "asiacrypt", "neurips", "icml", "cvpr", "iccv",
        "stoc", "focs", "sp", "oakland", "usenix security", "ccs", "ndss",
        "sigmod", "vldb", "osdi", "sosp", "pldi", "popl"
    },
    "tier2_conferences": {
        "fse", "ches", "pkc", "tcc", "aaai", "ijcai", "eccv", "iclr",
        "acl", "emnlp", "naacl", "www", "kdd", "icde", "wsdm"
    },
    "workshops": {
        "workshop", "symposium", "colloquium"
    }
}

# Source credibility for evidence weighting
SOURCE_CREDIBILITY = {
    "dblp": 0.95,           # Very reliable for CS
    "pubmed": 0.95,         # Very reliable for bio/medical
    "crossref": 0.90,       # Official DOI registry
    "semantic_scholar": 0.85,
    "openalex": 0.85,
    "arxiv": 0.80,          # Preprints, but well-maintained
    "iacr": 0.90,           # Authoritative for crypto
    "ieee": 0.90,
    "acm": 0.90,
    "springer": 0.85,
    "google_scholar": 0.65,  # Can have false positives
    "unknown": 0.50
}


def get_venue_tier(venue: str) -> str:
    """Classify venue into tiers"""
    if not venue:
        return "unknown"
    
    venue_lower = venue.lower()
    
    for tier, keywords in VENUE_TIERS.items():
        if any(kw in venue_lower for kw in keywords):
            return tier
    
    return "other"


def check_venue_plausibility(claimed_venue: str, actual_venue: str) -> Dict[str, Any]:
    """
    Check if the claimed venue is plausible given the actual venue.
    
    Flags suspicious cases like:
    - Claiming Nature when paper is on arXiv
    - Claiming top conference when it's a workshop paper
    """
    claimed_tier = get_venue_tier(claimed_venue)
    actual_tier = get_venue_tier(actual_venue)
    
    result = {
        "claimed_tier": claimed_tier,
        "actual_tier": actual_tier,
        "plausible": True,
        "suspicious": False,
        "reason": None
    }
    
    # Suspicious patterns
    if claimed_tier == "tier1_journals" and actual_tier == "preprints":
        result["plausible"] = False
        result["suspicious"] = True
        result["reason"] = f"Claims top journal ({claimed_venue}) but found as preprint ({actual_venue})"
    
    elif claimed_tier == "tier1_conferences" and actual_tier == "preprints":
        # This can be legitimate (preprint of accepted paper)
        result["plausible"] = True
        result["suspicious"] = False  # Don't flag, common practice
        result["reason"] = "Conference paper may have preprint version"
    
    elif claimed_tier == "tier1_journals" and actual_tier in ["workshops", "other"]:
        result["plausible"] = False
        result["suspicious"] = True
        result["reason"] = f"Claims top journal but found in lower venue"
    
    return result


def calculate_year_similarity_asymmetric(ref_year: int, db_year: int) -> Tuple[float, str]:
    """
    Calculate year similarity with asymmetric tolerance.
    
    Key insight: It's more suspicious to claim a NEWER year than actual.
    - Claiming 2020 when paper is from 2018: might be revised version (OK)
    - Claiming 2023 when paper is from 2020: very suspicious (fraud indicator)
    
    Returns:
        Tuple of (similarity_score, reason)
    """
    if not ref_year or not db_year:
        return 0.5, "year_missing"
    
    diff = ref_year - db_year
    
    if diff == 0:
        return 1.0, "exact_match"
    
    elif diff > 0:  # Reference claims NEWER year
        # Very suspicious - claiming newer publication date
        if diff == 1:
            return 0.7, "ref_one_year_newer"  # Might be proceedings delay
        elif diff == 2:
            return 0.4, "ref_two_years_newer_suspicious"
        else:
            return 0.1, "ref_much_newer_highly_suspicious"
    
    else:  # Reference claims OLDER year (diff < 0)
        # More acceptable - preprint vs published, etc.
        abs_diff = abs(diff)
        if abs_diff == 1:
            return 0.9, "ref_one_year_older"
        elif abs_diff == 2:
            return 0.8, "ref_two_years_older"
        elif abs_diff <= 4:
            return 0.6, "ref_several_years_older"
        else:
            return 0.3, "ref_much_older"


def calculate_source_evidence_strength(sources: List[str]) -> Dict[str, Any]:
    """
    Calculate overall evidence strength based on sources.
    
    Multiple authoritative sources = strong evidence
    Single obscure source = weak evidence
    """
    if not sources:
        return {
            "overall_strength": 0.0,
            "max_credibility": 0.0,
            "source_count": 0,
            "authoritative_count": 0
        }
    
    credibilities = [SOURCE_CREDIBILITY.get(s.lower(), 0.5) for s in sources]
    max_cred = max(credibilities)
    
    # Count authoritative sources (credibility >= 0.85)
    authoritative = sum(1 for c in credibilities if c >= 0.85)
    
    # Calculate overall strength
    # Multiple sources boost confidence
    base_strength = max_cred
    multi_source_bonus = min(0.15, 0.05 * (len(sources) - 1))
    authoritative_bonus = min(0.10, 0.05 * authoritative)
    
    overall = min(1.0, base_strength + multi_source_bonus + authoritative_bonus)
    
    return {
        "overall_strength": overall,
        "max_credibility": max_cred,
        "source_count": len(sources),
        "authoritative_count": authoritative,
        "sources": sources
    }


def classify_reference(
    extracted_ref: Dict[str, Any],
    best_match: Optional[Dict[str, Any]],
    all_results: List[Dict[str, Any]],
    similarity_threshold: float = 0.55,
    suspicious_threshold: float = 0.25
) -> EnhancedClassificationResult:
    """
    Classify a reference with multi-stage fraud detection.
    
    This replaces simple weighted averaging with conditional logic
    that catches various fraud patterns.
    """
    reasons = []
    fraud_indicators = []
    fraud_details = {}
    
    # Get sources
    sources = list(set(r.get('source', 'unknown') for r in all_results))
    evidence_strength = calculate_source_evidence_strength(sources)
    
    # No results at all
    if not all_results or not best_match:
        return EnhancedClassificationResult(
            classification="fabricated",
            confidence=0.85,
            similarity_breakdown={},
            fraud_indicators=[FraudType.COMPLETE_FABRICATION],
            fraud_details={"reason": "No results in any database"},
            evidence_strength=evidence_strength,
            reasons=["Reference not found in any academic database"],
            requires_manual_review=True,
            review_priority="high",
            issue_summary="NOT FOUND: This reference was not found in any academic database (DBLP, CrossRef, Semantic Scholar, OpenAlex, etc.)"
        )
    
    # === STAGE 1: Calculate individual similarities ===
    
    # Title similarity
    ref_title = normalize_text(extracted_ref.get('title', ''), preserve_hyphens=True)
    db_title = normalize_text(best_match.get('title', ''), preserve_hyphens=True)
    title_sim = calculate_text_similarity(ref_title, db_title)
    
    # Author comparison (advanced)
    ref_authors = extracted_ref.get('authors', [])
    db_authors = best_match.get('authors', [])
    
    # Handle different author formats from database
    if db_authors and isinstance(db_authors[0], dict):
        db_authors = [a.get('name', str(a)) for a in db_authors]
    
    author_comparison = compare_author_lists(ref_authors, db_authors)
    author_sim = author_comparison.overall_similarity
    
    # Venue similarity
    ref_venue = extracted_ref.get('venue', '')
    db_venue = best_match.get('venue', '') or best_match.get('journal', '') or best_match.get('conference', '')
    
    venue_sim = calculate_venue_similarity(ref_venue, db_venue)
    
    # Year similarity (asymmetric)
    ref_year = extracted_ref.get('year')
    db_year = best_match.get('year')
    try:
        ref_year = int(ref_year) if ref_year else None
        db_year = int(db_year) if db_year else None
    except (ValueError, TypeError):
        ref_year = None
        db_year = None
    
    year_sim, year_reason = calculate_year_similarity_asymmetric(ref_year, db_year)
    
    similarity_breakdown = {
        "title": title_sim,
        "author": author_sim,
        "venue": venue_sim,
        "year": year_sim,
        "year_reason": year_reason
    }
    
    # === STAGE 2: Fraud Pattern Detection ===
    
    # Pattern 1: High title match + low author match = AUTHOR MANIPULATION
    if title_sim > 0.85 and author_sim < 0.4:
        fraud_indicators.append(FraudType.AUTHOR_SWAP)
        fraud_details["author_swap"] = {
            "title_similarity": title_sim,
            "author_similarity": author_sim,
            "ref_authors": ref_authors,
            "db_authors": db_authors
        }
        reasons.append(f"Title matches ({title_sim:.2f}) but authors very different ({author_sim:.2f})")
        
        # Build clear issue summary
        ref_authors_str = ", ".join(ref_authors[:3]) + (" et al." if len(ref_authors) > 3 else "")
        db_authors_str = ", ".join(db_authors[:3]) + (" et al." if len(db_authors) > 3 else "")
        issue = f"AUTHOR MISMATCH: Title matches but authors differ significantly. Claimed: [{ref_authors_str}] vs Database: [{db_authors_str}]"
        
        return EnhancedClassificationResult(
            classification="author_manipulation",
            confidence=0.9,
            similarity_breakdown=similarity_breakdown,
            fraud_indicators=fraud_indicators,
            fraud_details=fraud_details,
            evidence_strength=evidence_strength,
            reasons=reasons + ["Detected author swapping fraud"],
            requires_manual_review=True,
            review_priority="critical",
            issue_summary=issue
        )
    
    # Pattern 2: Author injection (extra authors added)
    if author_comparison.author_injection_detected:
        injected = author_comparison.unmatched_ref_authors
        fraud_indicators.append(FraudType.AUTHOR_INJECTION)
        fraud_details["author_injection"] = {
            "injected_authors": injected,
            "matched_authors": [m.ref_author for m in author_comparison.matched_authors]
        }
        reasons.append(f"Detected injected authors: {injected}")
        
        # If title matches well but has extra authors, this is manipulation
        if title_sim > 0.8:
            injected_str = ", ".join(injected[:3]) + (" et al." if len(injected) > 3 else "")
            issue = f"AUTHOR INJECTION: Extra authors added to legitimate paper. Injected authors: [{injected_str}]"
            
            return EnhancedClassificationResult(
                classification="author_manipulation",
                confidence=0.85,
                similarity_breakdown=similarity_breakdown,
                fraud_indicators=fraud_indicators,
                fraud_details=fraud_details,
                evidence_strength=evidence_strength,
                reasons=reasons + ["Authors injected into legitimate paper"],
                requires_manual_review=True,
                review_priority="critical",
                issue_summary=issue
            )
    
    # Pattern 3: Venue tier mismatch
    venue_check = check_venue_plausibility(ref_venue, db_venue)
    if venue_check["suspicious"]:
        fraud_indicators.append(FraudType.VENUE_FABRICATION)
        fraud_details["venue_mismatch"] = venue_check
        reasons.append(venue_check["reason"])
    
    # Pattern 4: Suspicious year (claiming newer than actual)
    if year_reason in ["ref_two_years_newer_suspicious", "ref_much_newer_highly_suspicious"]:
        reasons.append(f"Reference claims newer year ({ref_year}) than found ({db_year})")
        # Don't add fraud indicator yet, but note it
        fraud_details["year_discrepancy"] = {
            "ref_year": ref_year,
            "db_year": db_year,
            "reason": year_reason
        }
    
    # Pattern 5: First author mismatch (important in academia)
    if author_comparison.first_author_match:
        if author_comparison.first_author_match.match_type == AuthorMatchType.NO_MATCH:
            if not author_comparison.reordering_detected:
                reasons.append("First author does not match any author in database")
                # This is suspicious but might be legitimate reordering
    
    # === STAGE 3: Calculate overall score with conditional logic ===
    
    # Don't use simple weighted average - use conditional logic
    
    # If title is very low, cannot be authentic regardless of other fields
    if title_sim < 0.4:
        overall_sim = title_sim * 0.6  # Cap at low value
        reasons.append("Low title similarity caps overall score")
    
    # If authors have injection fraud, penalize heavily
    elif author_comparison.author_injection_detected:
        overall_sim = min(title_sim * 0.7, author_sim)
        reasons.append("Author injection detected - score penalized")
    
    # Normal case: weighted but with safeguards
    else:
        # Weighted calculation
        overall_sim = (
            title_sim * 0.50 +      # Title most important
            author_sim * 0.30 +     # Authors very important
            venue_sim * 0.10 +      # Venue somewhat important
            year_sim * 0.10         # Year least important
        )
        
        # Apply evidence strength modifier
        if evidence_strength["authoritative_count"] == 0:
            overall_sim *= 0.9  # Penalty for no authoritative sources
            reasons.append("No authoritative database sources found")
    
    # === STAGE 4: Final Classification ===
    
    if overall_sim >= similarity_threshold:
        # Potential authentic - but check for any fraud indicators
        if fraud_indicators:
            # Build issue summary from fraud details
            fraud_issues = []
            if FraudType.VENUE_FABRICATION in fraud_indicators:
                fraud_issues.append("venue tier mismatch")
            if FraudType.AUTHOR_INJECTION in fraud_indicators:
                fraud_issues.append("possible author injection")
            if fraud_details.get("year_discrepancy"):
                yd = fraud_details["year_discrepancy"]
                fraud_issues.append(f"year discrepancy (claimed {yd.get('ref_year')} vs {yd.get('db_year')})")
            issue = f"SUSPICIOUS: High similarity but issues detected: {'; '.join(fraud_issues)}"
            
            # Has fraud indicators but high similarity - suspicious
            return EnhancedClassificationResult(
                classification="suspicious",
                confidence=overall_sim * 0.8,
                similarity_breakdown=similarity_breakdown,
                fraud_indicators=fraud_indicators,
                fraud_details=fraud_details,
                evidence_strength=evidence_strength,
                reasons=reasons + ["High similarity but fraud indicators present"],
                requires_manual_review=True,
                review_priority="high",
                issue_summary=issue
            )
        
        # Authentic
        confidence = min(0.95, overall_sim + evidence_strength["overall_strength"] * 0.1)
        db_list = ", ".join(evidence_strength.get("sources", [])[:3]) or "databases"
        issue = f"VERIFIED: Reference found and verified in {db_list} with {overall_sim*100:.0f}% similarity"
        
        return EnhancedClassificationResult(
            classification="authentic",
            confidence=confidence,
            similarity_breakdown=similarity_breakdown,
            fraud_indicators=[FraudType.NONE],
            fraud_details={},
            evidence_strength=evidence_strength,
            reasons=reasons + [f"High similarity ({overall_sim:.2f}) with clean fraud check"],
            requires_manual_review=False,
            review_priority="low",
            issue_summary=issue
        )
    
    elif overall_sim >= suspicious_threshold:
        # Suspicious - build descriptive issue
        issue = f"LOW CONFIDENCE: Only {overall_sim*100:.0f}% similarity found. Best match may not be the same paper."
        
        # Suspicious
        return EnhancedClassificationResult(
            classification="suspicious",
            confidence=overall_sim,
            similarity_breakdown=similarity_breakdown,
            fraud_indicators=fraud_indicators if fraud_indicators else [FraudType.NONE],
            fraud_details=fraud_details,
            evidence_strength=evidence_strength,
            reasons=reasons + ["Moderate similarity - needs verification"],
            requires_manual_review=True,
            review_priority="medium",
            issue_summary=issue
        )
    
    else:
        # Low similarity - likely fabricated
        if evidence_strength["authoritative_count"] >= 2:
            # Multiple authoritative sources but low similarity - might be wrong match
            classification = "inconclusive"
            reasons.append("Low similarity but found in authoritative sources - possible indexing issue")
            issue = f"INCONCLUSIVE: Found in databases but with low similarity ({overall_sim*100:.0f}%). May be indexing issue or different paper."
        else:
            classification = "fabricated"
            fraud_indicators.append(FraudType.COMPLETE_FABRICATION)
            reasons.append("Low similarity and weak database presence")
            issue = f"NOT VERIFIED: Low similarity ({overall_sim*100:.0f}%) and not found in authoritative databases. This reference could not be verified."
        
        return EnhancedClassificationResult(
            classification=classification,
            confidence=0.7,
            similarity_breakdown=similarity_breakdown,
            fraud_indicators=fraud_indicators,
            fraud_details=fraud_details,
            evidence_strength=evidence_strength,
            reasons=reasons,
            requires_manual_review=True,
            review_priority="high",
            issue_summary=issue
        )
