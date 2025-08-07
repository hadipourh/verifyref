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
    """Generate a human-readable text report with enhanced formatting"""
    report_lines = []
    
    # Header
    report_lines.append("=" * 80)
    report_lines.append("🔍 VerifyRef Reference Verification Report")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Summary using consistent function
    summary = results.get('summary', {})
    total_refs = summary.get('total_references', 0)
    summary_lines = generate_summary_table(summary, total_refs)
    report_lines.extend(summary_lines)
    report_lines.append("")
    
    # Detailed results
    report_lines.append("📚 DETAILED RESULTS")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    references = results.get('references', [])
    for ref_data in references:
        index = ref_data.get('index', 0)
        parsed = ref_data.get('parsed', {})
        classification = ref_data.get('classification', 'unknown')
        confidence = ref_data.get('confidence', 0.0)
        verification_results = ref_data.get('verification_results', {})
        
        # Reference header with enhanced separator
        report_lines.append("=" * 80)
        report_lines.append(f"═══ Reference {index}/{total_refs} ═══")
        
        # Paper title
        title = parsed.get('title', 'Unknown Title') if parsed else 'Failed to parse'
        report_lines.append(f"📖 {title}")
        
        # Authors
        if parsed and parsed.get('authors'):
            authors = parsed.get('authors', [])
            authors_str = ", ".join(authors[:3])
            if len(authors) > 3:
                authors_str += f" et al. ({len(authors)} total)"
            report_lines.append(f"👥 {authors_str}")
        
        # Year and venue
        if parsed:
            year = parsed.get('year')
            venue = parsed.get('venue')
            if year or venue:
                venue_line = ""
                if venue:
                    venue_line += f"📍 {venue}"
                if year:
                    venue_line += f" ({year})" if venue else f"📅 {year}"
                report_lines.append(venue_line)
        
        report_lines.append("-" * 80)
        
        # Classification result
        class_emoji = {
            'authentic': '✅',
            'suspicious': '🔍',
            'fake': '❌',
            'author_manipulation': '🔄',
            'fabricated': '🚫',
            'inconclusive': '❓'
        }.get(classification, '❓')
        
        report_lines.append(f"{class_emoji} Classification: {classification.upper()} ({confidence*100:.1f}% confidence)")
        
        # Database verification results (detailed information)
        if verification_results:
            report_lines.append("")
            report_lines.append("🔍 DATABASE VERIFICATION RESULTS:")
            report_lines.append("-" * 60)
            
            # Use provided classifier or create one if none provided
            if classifier is None:
                from verifier.classifier import ReferenceClassifier
                temp_classifier = ReferenceClassifier()
            else:
                temp_classifier = classifier
            
            for db_name, db_results in verification_results.items():
                if isinstance(db_results, list) and db_results:
                    report_lines.append(f"📚 {db_name.upper()}:")
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
                    report_lines.append(f"📚 {db_name.upper()}: No results found")
                else:
                    report_lines.append(f"📚 {db_name.upper()}: {str(db_results)}")
                    
                report_lines.append("")
        
        # Analysis details/reasons
        details = ref_data.get('details', [])
        if details and isinstance(details, list):
            report_lines.append("🔍 ANALYSIS DETAILS:")
            report_lines.append("-" * 60)
            for detail in details:
                report_lines.append(f"  • {detail}")
        elif details:
            report_lines.append("🔍 ANALYSIS DETAILS:")
            report_lines.append("-" * 60)
            report_lines.append(f"  {details}")
        
        # AI verification results if available
        verification_result = ref_data.get('verification_result', {})
        ai_verification = verification_result.get('details', {}).get('ai_verification')
        if ai_verification:
            report_lines.append("")
            report_lines.append("🤖 AI VERIFICATION ANALYSIS:")
            report_lines.append("-" * 60)
            report_lines.append(f"  Model: {ai_verification.get('model', 'Unknown')}")
            report_lines.append(f"  Tokens Used: {ai_verification.get('tokens_used', 'Unknown')}")
            
            # Note: The actual AI reasoning and flags are incorporated into the main reasons
            # This section shows the technical details of the AI analysis
            report_lines.append(f"  Analysis Version: {ai_verification.get('analysis_version', '1.0')}")
        
        # Original reference text
        original = ref_data.get('original')
        if original:
            report_lines.append("")
            report_lines.append("📝 ORIGINAL REFERENCE:")
            report_lines.append("-" * 60)
            report_lines.append(f"  {str(original)}")
        
        report_lines.append("=" * 80)
        report_lines.append("")
    
    # Footer
    report_lines.append("Generated by VerifyRef - Reference Verification Tool")
    report_lines.append("Using ethical API-only verification methods")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)
