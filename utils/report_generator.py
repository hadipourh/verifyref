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

import json
from datetime import datetime
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

def generate_human_readable_report(results: Dict[str, Any], output_file: str = None) -> str:
    """
    Generate a human-readable analysis report
    
    Args:
        results: Analysis results dictionary
        output_file: Optional file path to save the report
        
    Returns:
        String containing the formatted report
    """
    
    report_lines = []
    
    # Header
    report_lines.append("="*80)
    report_lines.append("REFCHECK ACADEMIC REFERENCE VERIFICATION REPORT")
    report_lines.append("="*80)
    report_lines.append("")
    
    # Metadata
    metadata = results.get('analysis_metadata', {})
    report_lines.append(f"📄 PDF File: {metadata.get('pdf_file', 'Unknown')}")
    report_lines.append(f"📅 Analysis Date: {metadata.get('analysis_date', 'Unknown')}")
    report_lines.append(f"🔍 Total References Found: {metadata.get('total_references_found', 0)}")
    report_lines.append(f"✅ References Processed: {metadata.get('references_processed', 0)}")
    report_lines.append("")
    
    # Processing notes
    notes = metadata.get('processing_notes', [])
    if notes:
        report_lines.append("📝 Processing Notes:")
        for note in notes:
            report_lines.append(f"   • {note}")
        report_lines.append("")
    
    # Summary
    summary = results.get('summary', {})
    report_lines.append("📊 SUMMARY STATISTICS")
    report_lines.append("-" * 40)
    
    counts = summary.get('classification_counts', {})
    percentages = summary.get('percentages', {})
    
    report_lines.append(f"✅ Authentic References:       {counts.get('authentic', 0):3d} ({percentages.get('authentic', 0):5.1f}%)")
    report_lines.append(f"🔍 Suspicious References:      {counts.get('suspicious', 0):3d} ({percentages.get('suspicious', 0):5.1f}%)")
    report_lines.append(f"❌ Fake References:           {counts.get('fake', 0):3d} ({percentages.get('fake', 0):5.1f}%)")
    report_lines.append(f"🔄 Author Manipulation:       {counts.get('author_manipulation', 0):3d} ({percentages.get('author_manipulation', 0):5.1f}%)")
    report_lines.append(f"🚫 Fabricated References:     {counts.get('fabricated', 0):3d} ({percentages.get('fabricated', 0):5.1f}%)")
    report_lines.append(f"❓ Inconclusive:              {counts.get('inconclusive', 0):3d} ({percentages.get('inconclusive', 0):5.1f}%)")
    report_lines.append("")
    
    # Risk assessment
    risk = summary.get('risk_assessment', 'Unknown')
    if risk.startswith('LOW'):
        risk_emoji = "🟢"
    elif risk.startswith('MEDIUM'):
        risk_emoji = "🟡"
    else:
        risk_emoji = "🔴"
    
    report_lines.append(f"🎯 Risk Assessment: {risk_emoji} {risk}")
    report_lines.append("")
    
    # Detailed results
    report_lines.append("📋 DETAILED REFERENCE ANALYSIS")
    report_lines.append("="*80)
    
    detailed_results = results.get('detailed_results', [])
    
    for result in detailed_results:
        ref_index = result.get('index', 0)
        extracted = result.get('parsed', {})
        classification = result.get('classification', 'unknown')
        confidence = result.get('confidence', 0.0)
        similarity = result.get('similarity_score', 0.0)
        matched_paper = result.get('matched_paper')
        reasons = result.get('reasons', [])
        
        # Classification emoji
        if classification == 'authentic':
            class_emoji = "✅"
        elif classification == 'suspicious':
            class_emoji = "⚠️"
        elif classification == 'fake':
            class_emoji = "❌"
        elif classification == 'author_manipulation':
            class_emoji = "🔄"
        elif classification == 'fabricated':
            class_emoji = "🚫"
        else:
            class_emoji = "❓"
        
        # Add a clear separator between references
        report_lines.append("\n" + "-" * 80 + "\n")
        report_lines.append(f"[{ref_index:2d}] {class_emoji} {classification.upper()}")
        report_lines.append("-" * 60)
        
        # Reference details
        title = extracted.get('title', 'No title')
        authors = extracted.get('authors', [])
        venue = extracted.get('venue', 'Unknown venue')
        year = extracted.get('year', 'Unknown year')
        
        report_lines.append(f"📖 Title: {title}")
        if authors:
            if len(authors) <= 3:
                author_str = ", ".join(authors)
            else:
                author_str = f"{', '.join(authors[:3])}, et al. ({len(authors)} total)"
            report_lines.append(f"👥 Authors: {author_str}")
        else:
            report_lines.append("👥 Authors: Not specified")
        
        report_lines.append(f"📰 Venue: {venue}")
        report_lines.append(f"📅 Year: {year}")
        
        # Verification details
        report_lines.append(f"🎯 Confidence: {confidence:.1%}")
        if similarity > 0:
            report_lines.append(f"📊 Similarity Score: {similarity:.2f}")
        
        # Matched paper (if any)
        if matched_paper:
            report_lines.append(f"🔗 Matched Paper: {matched_paper.get('title', 'Unknown')}")
            citations = matched_paper.get('citation_count', 0)
            if citations > 0:
                report_lines.append(f"📈 Citations: {citations}")
        
        # Reasons
        if reasons:
            report_lines.append("💭 Analysis Notes:")
            for reason in reasons:
                report_lines.append(f"   • {reason}")
    
    # Footer
    report_lines.append("\n" + "="*80)
    report_lines.append("Report generated by RefCheck - Academic Reference Verification Tool")
    report_lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("="*80)
    
    # Combine all lines
    report_text = "\n".join(report_lines)
    
    # Save to file if specified
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            logger.info(f"Human-readable report saved to: {output_file}")
        except Exception as e:
            logger.error(f"Failed to save report to {output_file}: {e}")
    
    return report_text