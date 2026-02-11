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

from typing import Dict, List, Any, Optional
import logging
from .summary_data import get_verification_summary_data

logger = logging.getLogger(__name__)


def _generate_author_suggestions(
    classification: str, 
    parsed: Dict[str, Any], 
    verification_results: Dict[str, List[Dict]], 
    classification_result: Any
) -> List[str]:
    """
    Generate helpful suggestions for authors to fix their references.
    
    The goal is not just fraud detection, but helping authors correct mistakes.
    
    Args:
        classification: The classification result (authentic, fabricated, etc.)
        parsed: Parsed reference data
        verification_results: Database search results
        classification_result: Full classification result with details
        
    Returns:
        List of suggestion strings
    """
    suggestions = []
    
    if not parsed:
        return suggestions
    
    title = parsed.get('title', '')
    authors = parsed.get('authors', [])
    year = parsed.get('year')
    venue = parsed.get('venue', '')
    
    # Get best match from results
    best_match = None
    best_similarity = 0.0
    all_results = []
    
    if verification_results:
        for db_results in verification_results.values():
            if isinstance(db_results, list):
                all_results.extend(db_results)
    
    # Find best match
    for result in all_results:
        if isinstance(result, dict):
            sim = result.get('similarity', 0)
            if sim > best_similarity:
                best_similarity = sim
                best_match = result
    
    # Get details from classification result
    details = {}
    if classification_result:
        if hasattr(classification_result, 'details'):
            details = classification_result.details or {}
        elif isinstance(classification_result, dict):
            details = classification_result.get('details', {})
    
    # FABRICATED: Reference not found
    if classification == 'fabricated':
        if details.get('reference_type') == 'book':
            # It's a book - suggest book-specific verification
            suggestions.append("This appears to be a BOOK reference (not indexed in paper databases).")
            suggestions.append("Verify via: Google Books, WorldCat, or the publisher's website.")
            suggestions.append("Consider adding ISBN for easier verification.")
        else:
            # Potentially typo or non-indexed venue
            suggestions.append("Check for typos in the title, authors, or venue name.")
            if best_match and best_similarity > 0.5:
                suggestions.append(f"Did you mean: \"{best_match.get('title', '')}\"?")
                if best_match.get('doi'):
                    suggestions.append(f"Suggested DOI: {best_match.get('doi')}")
            suggestions.append("If this is a preprint/tech report, try adding the arXiv ID or URL.")
            suggestions.append("For conference papers, verify the exact conference name and year.")
    
    # AUTHOR_MANIPULATION: Authors don't match
    elif classification == 'author_manipulation':
        claimed_authors = details.get('claimed_authors', authors)
        actual_authors = details.get('actual_authors', [])
        
        suggestions.append("The authors in your reference don't match the database record.")
        if actual_authors:
            suggestions.append(f"Database shows authors: {', '.join(actual_authors[:5])}")
        suggestions.append("Please verify the author list against the original publication.")
        suggestions.append("Common issues: missing co-authors, name spelling variations, or wrong paper.")
    
    # SUSPICIOUS: Something seems off
    elif classification == 'suspicious':
        title_sim = details.get('title_similarity', 0)
        author_sim = details.get('author_similarity', 0)
        
        if title_sim < 0.8 and best_match:
            suggestions.append(f"Title similarity is low ({title_sim*100:.0f}%). Check for typos.")
            suggestions.append(f"Database title: \"{best_match.get('title', '')}\"")
        
        if author_sim < 0.6:
            suggestions.append("Author names partially match. Verify complete author list.")
        
        if not year and best_match and best_match.get('year'):
            suggestions.append(f"Missing year? Database shows: {best_match.get('year')}")
        elif year and best_match and best_match.get('year') and year != best_match.get('year'):
            suggestions.append(f"Year mismatch: you have {year}, database shows {best_match.get('year')}")
    
    # INCONCLUSIVE: Cannot determine
    elif classification == 'inconclusive':
        if details.get('reference_type') == 'book':
            suggestions.append("This appears to be a book - verify via Google Books or WorldCat.")
        else:
            suggestions.append("Could not find a definitive match in academic databases.")
            suggestions.append("Try adding DOI, arXiv ID, or direct URL to help verification.")
            if not venue:
                suggestions.append("Consider adding the venue/journal name.")
    
    # AUTHENTIC: Still provide helpful info
    elif classification == 'authentic':
        if best_match:
            if best_match.get('doi') and not parsed.get('doi'):
                suggestions.append(f"Consider adding DOI for better citation: {best_match.get('doi')}")
            if best_match.get('url') and not parsed.get('url'):
                suggestions.append(f"URL available: {best_match.get('url')}")
    
    return suggestions


def generate_summary_table(summary: Dict[str, Any], total_refs: int) -> List[str]:
    """Generate clean text-based summary table for file output (no borders)"""
    lines = []
    
    # Get the same data used by the terminal display
    summary_data = get_verification_summary_data(summary)
    
    # Create clean text version without borders for file output
    lines.append("                 [*] Verification Summary")
    lines.append("")
    lines.append("Classification           Count  Percentage  Status")
    lines.append("─────────────────────────────────────────────────")
    
    for item in summary_data:
        label = item['label']
        count = item['count']
        percentage = item['percentage']
        status = "●" if count > 0 else "○"
        
        # Format with proper spacing (no borders)
        line = f"{label:<24} {count:5d}      {percentage:5.1f}%    {status}"
        lines.append(line)
    
    lines.append("")
    
    # Add risk assessment if available  
    risk_assessment = summary.get('risk_assessment', '')
    if risk_assessment:
        lines.append(f"{risk_assessment}")
        lines.append("")
    
    return lines

def generate_human_readable_report(results: Dict[str, Any], classifier=None) -> str:
    """Generate a human-readable text report with professional formatting (no icons)"""
    report_lines = []
    
    # Header
    report_lines.append("=" * 80)
    report_lines.append("VerifyRef - Reference Verification Report")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Summary using consistent function
    summary = results.get('summary', {})
    total_refs = summary.get('total_references', 0)
    summary_lines = generate_summary_table(summary, total_refs)
    report_lines.extend(summary_lines)
    report_lines.append("")
    
    # Detailed results
    report_lines.append("DETAILED RESULTS")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    references = results.get('references', [])
    for ref_data in references:
        index = ref_data.get('index', 0)
        parsed = ref_data.get('parsed', {})
        classification = ref_data.get('classification', 'unknown')
        confidence = ref_data.get('confidence', 0.0)
        verification_results = ref_data.get('verification_results', {})
        
        # Get issue summary if available
        classification_result = ref_data.get('classification_result')
        issue_summary = ""
        if classification_result and hasattr(classification_result, 'issue_summary'):
            issue_summary = classification_result.issue_summary
        elif isinstance(classification_result, dict):
            issue_summary = classification_result.get('issue_summary', '')
        
        # Reference header with enhanced separator
        report_lines.append("=" * 80)
        report_lines.append(f"Reference {index}/{total_refs}")
        
        # Paper title
        title = parsed.get('title', 'Unknown Title') if parsed else 'Failed to parse'
        report_lines.append(f"Title: {title}")
        
        # Authors
        if parsed and parsed.get('authors'):
            authors = parsed.get('authors', [])
            authors_str = ", ".join(authors[:3])
            if len(authors) > 3:
                authors_str += f" et al. ({len(authors)} total)"
            report_lines.append(f"Authors: {authors_str}")
        
        # Year and venue
        if parsed:
            year = parsed.get('year')
            venue = parsed.get('venue')
            if venue:
                report_lines.append(f"Venue: {venue}")
            if year:
                report_lines.append(f"Year: {year}")
        
        report_lines.append("-" * 80)
        
        # Classification result - professional labels
        class_label = {
            'authentic': '[VERIFIED]',
            'suspicious': '[SUSPICIOUS]',
            'fake': '[FAKE]',
            'author_manipulation': '[AUTHOR ISSUE]',
            'fabricated': '[NOT FOUND]',
            'inconclusive': '[INCONCLUSIVE]'
        }.get(classification, '[UNKNOWN]')
        
        report_lines.append(f"Classification: {class_label} {classification.upper()} ({confidence*100:.1f}% confidence)")
        
        # Issue summary - the key new feature
        if issue_summary:
            report_lines.append(f"Issue: {issue_summary}")
        
        # RETRACTION WARNING - Critical new feature
        retraction_info = None
        if classification_result:
            if hasattr(classification_result, 'retraction_info'):
                retraction_info = classification_result.retraction_info
            elif isinstance(classification_result, dict):
                retraction_info = classification_result.get('retraction_info')
        
        if retraction_info and retraction_info.get('retracted'):
            report_lines.append("")
            report_lines.append("!" * 60)
            report_lines.append("[CRITICAL WARNING] THIS PAPER HAS BEEN RETRACTED")
            report_lines.append("!" * 60)
            retraction_type = retraction_info.get('retraction_type', 'Retraction')
            report_lines.append(f"Retraction Type: {retraction_type}")
            if retraction_info.get('retraction_doi'):
                report_lines.append(f"Retraction Notice DOI: {retraction_info['retraction_doi']}")
            if retraction_info.get('retraction_date'):
                report_lines.append(f"Retraction Date: {retraction_info['retraction_date']}")
            if retraction_info.get('original_doi'):
                report_lines.append(f"Original Paper DOI: {retraction_info['original_doi']}")
            report_lines.append("")
            report_lines.append("Citing retracted papers may compromise research integrity.")
            report_lines.append("Please verify and consider removing or replacing this citation.")
            report_lines.append("!" * 60)
        
        # AUTHOR-FRIENDLY SUGGESTIONS - Help authors fix their references
        suggestions = _generate_author_suggestions(
            classification, parsed, verification_results, classification_result
        )
        if suggestions:
            report_lines.append("")
            report_lines.append("SUGGESTIONS FOR AUTHORS:")
            report_lines.append("-" * 60)
            for suggestion in suggestions:
                report_lines.append(f"  -> {suggestion}")
        
        # Database verification results (detailed information)
        if verification_results:
            report_lines.append("")
            report_lines.append("DATABASE VERIFICATION RESULTS:")
            report_lines.append("-" * 60)
            
            # Use provided classifier or create one if none provided
            if classifier is None:
                from verifier.classifier import ReferenceClassifier
                temp_classifier = ReferenceClassifier()
            else:
                temp_classifier = classifier
            
            for db_name, db_results in verification_results.items():
                if isinstance(db_results, list) and db_results:
                    report_lines.append(f"{db_name.upper()}:")
                    report_lines.append(f"  Found {len(db_results)} result(s)")
                    
                    for i, result in enumerate(db_results[:3], 1):  # Show top 3 results
                        if isinstance(result, dict):
                            result_title = result.get('title', 'Unknown')
                            result_authors = result.get('authors', [])
                            result_year = result.get('year', 'Unknown')
                            
                            # Calculate similarity for display
                            similarity = temp_classifier._calculate_overall_similarity(parsed, result) * 100
                            
                            report_lines.append(f"  {i}. {result_title}")
                            if result_authors:
                                authors_str = ", ".join(result_authors[:2])
                                if len(result_authors) > 2:
                                    authors_str += " et al."
                                report_lines.append(f"     Authors: {authors_str}")
                            report_lines.append(f"     Year: {result_year} | Similarity: {similarity:.1f}%")
                            
                            # DOI or URL if available
                            if result.get('doi'):
                                report_lines.append(f"     DOI: {result['doi']}")
                            elif result.get('url'):
                                report_lines.append(f"     URL: {result['url']}")
                            
                            report_lines.append("")
                    
                    if len(db_results) > 3:
                        report_lines.append(f"  ... and {len(db_results) - 3} more results")
                        report_lines.append("")
                elif isinstance(db_results, list):
                    report_lines.append(f"{db_name.upper()}: No results found")
                else:
                    report_lines.append(f"{db_name.upper()}: {str(db_results)}")
                    
                report_lines.append("")
        
        # Analysis details/reasons
        details = ref_data.get('details', [])
        if details and isinstance(details, list):
            report_lines.append("ANALYSIS DETAILS:")
            report_lines.append("-" * 60)
            for detail in details:
                report_lines.append(f"  * {detail}")
        elif details:
            report_lines.append("ANALYSIS DETAILS:")
            report_lines.append("-" * 60)
            report_lines.append(f"  {details}")
        
        # AI verification results if available
        # The classification_result contains the VerificationResult with details including ai_verification
        classification_result = ref_data.get('classification_result')
        ai_verification = None
        if classification_result:
            if hasattr(classification_result, 'details'):
                ai_verification = classification_result.details.get('ai_verification')
            elif isinstance(classification_result, dict):
                ai_verification = classification_result.get('details', {}).get('ai_verification')
        
        if ai_verification:
            report_lines.append("")
            report_lines.append("AI VERIFICATION ANALYSIS:")
            report_lines.append("-" * 60)
            report_lines.append(f"  Model: {ai_verification.get('model', 'Unknown')}")
            report_lines.append(f"  Provider: {ai_verification.get('provider', 'Unknown')}")
            
            # Show AI's assessment
            ai_authentic = ai_verification.get('is_authentic')
            ai_confidence = ai_verification.get('confidence', 0)
            if ai_authentic is not None:
                ai_verdict = "AUTHENTIC" if ai_authentic else "SUSPICIOUS/FAKE"
                report_lines.append(f"  AI Verdict: {ai_verdict} ({ai_confidence*100:.1f}% confidence)")
            
            # Show reasoning
            ai_reasoning = ai_verification.get('reasoning', '')
            if ai_reasoning:
                report_lines.append(f"  AI Reasoning: {ai_reasoning[:200]}{'...' if len(ai_reasoning) > 200 else ''}")
            
            # Show red flags if any
            red_flags = ai_verification.get('red_flags', [])
            if red_flags:
                report_lines.append(f"  Red Flags: {', '.join(red_flags[:3])}")
            
            report_lines.append(f"  Tokens Used: {ai_verification.get('tokens_used', 'Unknown')}")
        
        # Original reference text
        original = ref_data.get('original')
        if original:
            report_lines.append("")
            report_lines.append("ORIGINAL REFERENCE:")
            report_lines.append("-" * 60)
            report_lines.append(f"  {str(original)}")
        
        report_lines.append("=" * 80)
        report_lines.append("")
    
    # Footer
    report_lines.append("Generated by VerifyRef - Reference Verification Tool")
    report_lines.append("Using ethical API-only verification methods")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)
