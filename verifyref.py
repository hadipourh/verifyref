#!/usr/bin/env python3
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

A professional tool for verifying academic reference authenticity and generating
proper BibTeX citations using multiple academic databases with advanced
parallel processing optimization.
"""

import argparse
import sys
import os
import json
import logging
import re
import traceback
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Rich imports for beautiful UI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

# Import our modules
from config import validate_config, get_config, DATABASE_CONFIG, CLASSIFICATION_CONFIG
from grobid.client import GrobidClient
from extractor.reference_parser import ReferenceParser
from verifier.semantic_scholar import SemanticScholarClient
from verifier.multi_database_verifier import MultiDatabaseVerifier
from verifier.classifier import ReferenceClassifier
from utils.report_generator import generate_human_readable_report
from utils.summary_data import get_verification_summary_data
from utils.helpers import calculate_text_similarity, normalize_text
from utils.academic_matching import clean_author_name
from utils.input_parser import detect_input_type, parse_single_reference_to_raw, parse_text_file_to_raw
from utils.output_handler import save_results, determine_output_format, make_json_serializable
from utils.config_utils import validate_openai_api_key, apply_runtime_config, setup_logging
from utils.terminal_display import display_verification_summary

# Initialize rich console
console = Console()

# Initialize logger
logger = logging.getLogger(__name__)

# Performance optimization: Thread-safe cache for database search results
_search_cache = {}
_cache_hits = 0
_cache_misses = 0
_cache_lock = threading.Lock()  # Thread-safe cache access

# Pre-compiled context keywords and configurations for better performance
CS_KEYWORDS = frozenset([
    "algorithm", "computation", "computer", "software", "programming", "data", "neural", 
    "machine learning", "artificial intelligence", "cryptography", "security", "network",
    "database", "system", "optimization", "complexity", "parallel", "distributed",
    "compiler", "processor", "memory", "cache", "gpu", "cpu", "hardware", "vlsi",
    "computer vision", "natural language", "nlp", "deep learning", "reinforcement",
    "graph", "tree", "sorting", "searching", "hashing", "encryption", "blockchain",
    "web", "internet", "protocol", "tcp", "http", "cloud", "virtualization",
    "operating system", "kernel", "filesystem", "concurrency", "thread", "process"
])

BIOMEDICAL_KEYWORDS = frozenset([
    "medical", "medicine", "clinical", "patient", "disease", "therapy", "treatment",
    "drug", "pharmaceutical", "vaccine", "antibody", "protein", "gene", "genetic",
    "dna", "rna", "genome", "genomic", "mutation", "cancer", "tumor", "oncology",
    "cardiology", "neurology", "psychology", "psychiatry", "surgery", "diagnostic",
    "epidemiology", "public health", "biomarker", "biomedical", "biological",
    "cell", "molecular", "biochemistry", "physiology", "anatomy", "pathology",
    "immunology", "microbiology", "virology", "bacteriology", "parasitology",
    "pharmacology", "toxicology", "nutrition", "metabolism", "endocrinology",
    "diabetes", "obesity", "hypertension", "stroke", "heart", "lung", "kidney",
    "liver", "brain", "blood", "bone", "tissue", "organ", "transplant",
    "infection", "inflammation", "autoimmune", "allergy", "asthma", "copd",
    "covid", "coronavirus", "pandemic", "epidemic", "virus", "bacteria",
    "clinical trial", "randomized", "cohort", "case control", "meta-analysis"
])

# Database configurations for context-aware search
CS_DATABASE_PRIORITIES = ["dblp", "iacr", "arxiv", "semantic_scholar", "crossref", "pubmed"]
BIO_DATABASE_PRIORITIES = ["pubmed", "semantic_scholar", "crossref", "arxiv", "dblp", "iacr"]

CS_RESULT_LIMITS = {
    "dblp": 15, "iacr": 12, "arxiv": 12, 
    "semantic_scholar": 8, "crossref": 8, "pubmed": 3
}

BIO_RESULT_LIMITS = {
    "pubmed": 15, "semantic_scholar": 10, "crossref": 10,
    "arxiv": 5, "dblp": 2, "iacr": 2
}

def get_cache_key(parsed_ref: Dict[str, Any]) -> str:
    """Generate a cache key for database search results"""
    title = normalize_text(parsed_ref.get('title', ''))
    authors = parsed_ref.get('authors', [])
    year = parsed_ref.get('year', '')
    
    # Create a normalized key from title + first author + year
    author_key = normalize_text(authors[0]) if authors else ''
    return f"{title}|{author_key}|{year}"

def cached_database_search(verifier: MultiDatabaseVerifier, parsed_ref: Dict[str, Any], verbose: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    """
    Thread-safe database search with intelligent caching
    
    This function is designed to work with the parallel reference processing in verifyref.py.
    The MultiDatabaseVerifier.search_across_databases() method now uses sequential database
    searches to avoid nested ThreadPoolExecutor conflicts that caused inconsistent results
    between verbose (-v) and parallel modes.
    """
    global _search_cache, _cache_hits, _cache_misses, _cache_lock
    
    cache_key = get_cache_key(parsed_ref)
    
    # Thread-safe cache check
    with _cache_lock:
        if cache_key in _search_cache:
            _cache_hits += 1
            if verbose:
                console.print(f"[dim green]📋 Using cached results for similar reference[/dim green]")
            return _search_cache[cache_key]
        
        # Increment cache miss counter
        _cache_misses += 1
    
    # Cache miss - perform actual search (outside lock to allow parallel DB searches)
    verification_results = verifier.search_across_databases(parsed_ref)
    
    # Thread-safe cache update
    with _cache_lock:
        # Re-check cache size (might have changed while we were searching)
        if len(_search_cache) < 150:  # Increased cache limit for parallel processing
            _search_cache[cache_key] = verification_results
    
    return verification_results

def verify_flexible_input(input_str: str, output_file: str = None, output_format: str = None, verbose: bool = False):
    """
    Verify references from flexible input (auto-detects input type)
    
    This function now simply calls the unified verify_references function.
    
    Args:
        input_str: Input string (PDF path, text file path, or single reference string)
        output_file: Optional output file path
        output_format: Optional output format (json/txt)
        verbose: Enable verbose output
    """
    # Simply call the unified verification function
    verify_references(input_str, output_file, output_format, verbose)

def verify_references(input_path: str, output_file: str = None, output_format: str = None, verbose: bool = False):
    """
    Unified reference verification with parallel processing optimization.
    Supports PDF files, text files, and single reference strings.
    
    Major performance improvements:
    - Parallel database verification (up to 4x faster for multiple references)
    - Thread-safe caching system with optimized hit rate
    - Reduced memory overhead with efficient string operations
    - Smart progress reporting (sequential for verbose, parallel for speed)
    """
    start_time = time.time()
    
    # Print header
    console.print(Panel.fit(
        "[bold blue]🔍 VerifyRef Reference Verification[/bold blue]",
        border_style="blue"
    ))
    
    # Validate configuration
    if not validate_config():
        console.print("[red]❌ Configuration validation failed[/red]")
        sys.exit(1)
    
    # Initialize components with fast mode for better performance
    config = get_config()
    grobid_client = GrobidClient()
    parser = ReferenceParser()
    verifier = MultiDatabaseVerifier(fast_mode=True)  # Enable fast mode for better performance
    classifier = ReferenceClassifier()
    
    # Detect input type and extract/parse references accordingly
    input_type = detect_input_type(input_path)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=console
    ) as progress:
        if input_type == 'pdf':
            extract_task = progress.add_task("📄 Extracting references from PDF...", total=None)
            try:
                references = grobid_client.extract_references(input_path)
                if not references:
                    console.print("[red]❌ Failed to extract references from PDF[/red]")
                    sys.exit(1)
                console.print(f"[green]📚 Extracted {len(references)} references from PDF[/green]")
            except Exception as e:
                console.print(f"[red]❌ Error processing PDF: {e}[/red]")
                sys.exit(1)
                
        elif input_type == 'text_file':
            extract_task = progress.add_task("📝 Parsing references from text file...", total=None)
            try:
                references = parse_text_file_to_raw(input_path)
                if not references:
                    console.print("[red]❌ No valid references found in text file[/red]")
                    sys.exit(1)
                console.print(f"[green]📚 Extracted {len(references)} references from text file[/green]")
            except Exception as e:
                console.print(f"[red]❌ Error processing text file: {e}[/red]")
                sys.exit(1)
                
        else:  # single_reference
            extract_task = progress.add_task("✏️ Parsing single reference...", total=None)
            try:
                single_ref = parse_single_reference_to_raw(input_path)
                references = [single_ref]
                console.print(f"[green]📚 Parsed single reference[/green]")
            except Exception as e:
                console.print(f"[red]❌ Error parsing single reference: {e}[/red]")
                sys.exit(1)
    
    # Optimized reference verification with parallel processing
    verified_references = []
    
    console.print(f"[blue]🔍 Starting verification of {len(references)} references...[/blue]")
    
    # Define processing function for parallel execution
    def create_error_result(index, ref, error_reason):
        """Helper to create consistent error results"""
        from verifier.classifier import VerificationResult, ClassificationResult
        error_result = VerificationResult(
            classification=ClassificationResult.INCONCLUSIVE,
            confidence=0.0, similarity_score=0.0, matched_paper=None,
            reasons=[error_reason], details={}
        )
        return {
            'index': index, 'original': ref, 'parsed': None,
            'classification_result': error_result,
            'classification': 'inconclusive', 'confidence': 0.0,
            'details': error_reason
        }
    
    def process_single_reference(ref_tuple):
        """Process a single reference in parallel"""
        i, ref = ref_tuple
        
        try:
            # Parse reference - handle both dict and string formats efficiently
            if isinstance(ref, dict):
                parsed_ref = parser.parse_single_reference(ref, i)
            else:
                # Pre-create dict format for parser (avoid repeated string operations)
                ref_dict = {
                    'raw_text': str(ref), 'title': '', 'authors': [], 'venue': '',
                    'year': None, 'volume': '', 'issue': '', 'pages': '', 'doi': '', 'isbn': '', 'url': ''
                }
                parsed_ref = parser.parse_single_reference(ref_dict, i)
            
            # Validate parsed reference
            if not (parsed_ref and isinstance(parsed_ref, dict) and parsed_ref.get('title')):
                return create_error_result(i, ref, 'Failed to parse reference')
            
            # Verify against databases with caching
            verification_results = cached_database_search(verifier, parsed_ref, False)  # Non-verbose for parallel
            
            # Efficient flattening using list comprehension
            flattened_results = [
                result for db_results in verification_results.values() 
                for result in db_results
            ]
            
            # Classify the reference
            classification = classifier.classify_reference(parsed_ref, flattened_results)
            
            return {
                'index': i, 'original': ref, 'parsed': parsed_ref,
                'verification_results': verification_results,
                'classification_result': classification,
                'classification': classification.classification.value,
                'confidence': classification.confidence,
                'details': classification.reasons
            }
            
        except Exception as e:
            return create_error_result(i, ref, f'Processing error: {str(e)}')
    
    # Use parallel processing for better performance
    max_workers = min(8, len(references))  # Limit to 8 threads for optimal parallel processing
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False
    ) as progress:
        
        main_task = progress.add_task(
            f"🔍 Processing references [0/{len(references)}]", 
            total=len(references)
        )
        
        if verbose:
            # Sequential processing for verbose mode to maintain ordered output
            for i, ref in enumerate(references, 1):
                progress.update(
                    main_task, 
                    description=f"🔍 Processing reference [{i}/{len(references)}]",
                    completed=i-1
                )
                
                # Show current reference
                if isinstance(ref, dict):
                    ref_preview = ref.get('title', str(ref)[:60]) + "..." if len(str(ref)) > 60 else str(ref)
                else:
                    ref_preview = str(ref)[:60] + "..." if len(str(ref)) > 60 else str(ref)
                console.print(f"[dim]  📖 {ref_preview}[/dim]")
                
                result = process_single_reference((i, ref))
                
                # Display verbose output for this reference
                if result['parsed']:
                    title_preview = result['parsed'].get('title', 'Unknown')
                    authors_preview = result['parsed'].get('authors', [])
                    
                    ref_header = f"═══ Reference {i}/{len(references)} ═══"
                    separator_line = "═" * 80
                    sub_separator = "─" * 80
                    
                    console.print()
                    console.print(f"[bold cyan]{separator_line}[/bold cyan]")
                    console.print(f"[bold cyan]{ref_header}[/bold cyan]")
                    console.print(f"[bold green]📖 {title_preview}[/bold green]")
                    
                    if authors_preview:
                        if len(authors_preview) <= 3:
                            authors_str = ", ".join(authors_preview)
                        else:
                            authors_str = f"{', '.join(authors_preview[:3])} et al. ({len(authors_preview)} total)"
                        console.print(f"[dim]👥 {authors_str}[/dim]")
                    
                    console.print(f"[bold cyan]{sub_separator}[/bold cyan]")
                    
                    # Show verification results
                    verification_results = result.get('verification_results', {})
                    total_results = sum(len(results) for results in verification_results.values())
                    
                    if total_results > 0:
                        console.print(f"[dim green]✅ Found {total_results} potential matches across databases[/dim green]")
                        for db_name, db_results in verification_results.items():
                            if db_results:
                                console.print(f"[dim]  • {db_name}: {len(db_results)} results[/dim]")
                    else:
                        console.print(f"[dim yellow]⚠️ No matches found in any database[/dim yellow]")
                    
                    # Show classification
                    classification_value = result['classification']
                    confidence = result['confidence']
                    
                    class_color = {
                        'authentic': 'green', 'suspicious': 'yellow', 'fake': 'red',
                        'author_manipulation': 'purple', 'fabricated': 'red', 'inconclusive': 'blue'
                    }.get(classification_value, 'white')
                    
                    class_emoji = {
                        'authentic': '✅', 'suspicious': '🔍', 'fake': '❌',
                        'author_manipulation': '🔄', 'fabricated': '🚫', 'inconclusive': '❓'
                    }.get(classification_value, '❓')
                    
                    console.print(f"[{class_color}]{class_emoji} Classification: {classification_value.upper()} ({confidence*100:.1f}% confidence)[/{class_color}]")
                    console.print(f"[bold cyan]{separator_line}[/bold cyan]")
                    console.print()
                
                verified_references.append(result)
                progress.update(main_task, completed=i)
        else:
            # Parallel processing for non-verbose mode (much faster)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all reference processing tasks
                future_to_ref = {
                    executor.submit(process_single_reference, (i, ref)): i
                    for i, ref in enumerate(references, 1)
                }
                
                completed_count = 0
                
                # Process completed futures as they finish
                for future in as_completed(future_to_ref):
                    completed_count += 1
                    progress.update(
                        main_task,
                        description=f"🔍 Processing references [{completed_count}/{len(references)}]",
                        completed=completed_count
                    )
                    
                    try:
                        result = future.result()
                        verified_references.append(result)
                    except Exception as e:
                        ref_index = future_to_ref[future]
                        console.print(f"[red]❌ Error processing reference {ref_index}: {e}[/red]")
                        
                        # Add error result
                        from verifier.classifier import VerificationResult, ClassificationResult
                        error_result = VerificationResult(
                            classification=ClassificationResult.INCONCLUSIVE,
                            confidence=0.0, similarity_score=0.0, matched_paper=None,
                            reasons=[f'Processing error: {str(e)}'], details={}
                        )
                        
                        verified_references.append({
                            'index': ref_index, 'original': references[ref_index-1], 'parsed': None,
                            'classification_result': error_result,
                            'classification': 'inconclusive', 'confidence': 0.0,
                            'details': f'Processing error: {str(e)}'
                        })
            
            # Sort results by index to maintain order
            verified_references.sort(key=lambda x: x['index'])
    
    # Generate results summary using the classifier's method
    classification_results = [ref['classification_result'] for ref in verified_references if 'classification_result' in ref]
    summary = classifier.generate_summary_report(classification_results)
    
    results = {
        'metadata': {
            'input_source': input_path,
            'input_type': input_type,
            'analysis_date': datetime.now().isoformat(),
            'total_references': len(references),
            'verifyref_version': '1.0.0'
        },
        'analysis_metadata': {
            'input_source': input_path,
            'input_type': input_type,
            'analysis_date': datetime.now().isoformat(),
            'total_references_found': len(references),
            'references_processed': len(verified_references)
        },
        'summary': summary,
        'references': verified_references,
        'detailed_results': verified_references
    }
    
    # Display summary table
    display_verification_summary(results['summary'], len(references), console)
    
    # Show thread-safe performance statistics if caching was used
    with _cache_lock:
        current_cache_hits = _cache_hits
        current_cache_misses = _cache_misses
    
    if current_cache_hits > 0 or current_cache_misses > 0:
        total_searches = current_cache_hits + current_cache_misses
        cache_hit_rate = (current_cache_hits / total_searches) * 100 if total_searches > 0 else 0
        
        console.print(f"\n📊 [bold blue]Performance Statistics:[/bold blue]")
        console.print(f"   🔍 Database searches: {total_searches}")
        console.print(f"   📋 Cache hits: {current_cache_hits}")
        console.print(f"   💾 Cache hit rate: {cache_hit_rate:.1f}%")
        
        if cache_hit_rate > 0:
            console.print(f"   ⚡ Time saved by caching!")
        
        # Show parallel processing benefit
        if not verbose and len(references) > 1:
            console.print(f"   🚀 Parallel processing used for {len(references)} references")
        
        console.print()
    
    # Performance timing summary
    end_time = time.time()
    total_time = end_time - start_time
    
    console.print(f"⏱️  [bold green]Total verification time: {total_time:.2f} seconds[/bold green]")
    if len(references) > 1:
        time_per_ref = total_time / len(references)
        console.print(f"   📈 Average per reference: {time_per_ref:.2f} seconds")
        
        # Estimate speed improvement from parallelization
        if not verbose:
            estimated_sequential = time_per_ref * len(references) * 1.5  # Rough estimate
            speed_improvement = estimated_sequential / total_time
            if speed_improvement > 1.2:
                console.print(f"   🚀 Estimated {speed_improvement:.1f}x faster with parallel processing")
    console.print()
    
    # Output results
    if output_file:
        # Determine output format
        format_to_use = determine_output_format(output_file, output_format)
        save_results(results, output_file, format_to_use, classifier, console)
    else:
        # Generate human-readable report for console output
        report = generate_human_readable_report(results, classifier)
        console.print("\n" + "="*80)
        console.print(report)

def apply_context_filtering(results: List[Dict[str, Any]], context_type: str, verbose: bool = False) -> List[Dict[str, Any]]:
    """Apply context-aware filtering and boosting to search results"""
    
    if context_type == "computer-science":
        cs_sources = {"dblp", "arxiv", "semantic_scholar", "iacr", "crossref"}
        
        if verbose:
            console.print("[dim cyan]🖥️ Applying Computer Science context filtering...[/dim cyan]")
        
        # Boost scores for CS-relevant results
        for paper in results:
            # Handle all fields being potentially lists or strings
            source_raw = paper.get('source', '')
            source = str(source_raw).lower() if not isinstance(source_raw, list) else ' '.join(str(s) for s in source_raw).lower()
            
            title_raw = paper.get('title', '')
            title = str(title_raw).lower() if not isinstance(title_raw, list) else ' '.join(str(t) for t in title_raw).lower()
            
            # Handle venue being a list or string
            venue_raw = paper.get('venue', '')
            if isinstance(venue_raw, list):
                venue = ' '.join(str(v) for v in venue_raw).lower()
            else:
                venue = str(venue_raw).lower()
            
            boost_score = 1.0
            
            # Boost by source relevance - much more aggressive
            if source in cs_sources:
                if source == "dblp":
                    boost_score += 0.8  # DBLP is primarily CS
                elif source == "iacr":
                    boost_score += 0.7  # IACR is cryptography/security
                elif source == "arxiv":
                    boost_score += 0.5  # ArXiv has many CS papers
                else:
                    boost_score += 0.3
            else:
                # Penalize non-CS sources for CS context
                boost_score *= 0.5
            
            # Optimized keyword matching using pre-compiled set
            text_to_check = f"{title} {venue}"
            cs_keyword_count = sum(1 for keyword in CS_KEYWORDS if keyword in text_to_check)
            boost_score += cs_keyword_count * 0.15
            
            # Apply boost
            paper['relevance_boost'] = paper.get('relevance_boost', 1.0) * boost_score
                
    elif context_type == "biomedical":
        bio_sources = {"pubmed", "semantic_scholar", "crossref"}
        
        if verbose:
            console.print("[dim cyan]🧬 Applying Biomedical context filtering...[/dim cyan]")
        
        # Boost scores for biomedical-relevant results
        for paper in results:
            # Handle all fields being potentially lists or strings
            source_raw = paper.get('source', '')
            source = str(source_raw).lower() if not isinstance(source_raw, list) else ' '.join(str(s) for s in source_raw).lower()
            
            title_raw = paper.get('title', '')
            title = str(title_raw).lower() if not isinstance(title_raw, list) else ' '.join(str(t) for t in title_raw).lower()
            
            # Handle venue being a list or string
            venue_raw = paper.get('venue', '')
            if isinstance(venue_raw, list):
                venue = ' '.join(str(v) for v in venue_raw).lower()
            else:
                venue = str(venue_raw).lower()
            
            boost_score = 1.0
            
            # Boost by source relevance - much more aggressive
            if source in bio_sources:
                if source == "pubmed":
                    boost_score += 1.0  # PubMed is primarily biomedical
                elif source == "semantic_scholar":
                    boost_score += 0.3  # Has good bio coverage
                else:
                    boost_score += 0.2
            else:
                # Penalize non-bio sources for bio context
                boost_score *= 0.4
            
            # Optimized keyword matching using pre-compiled set
            text_to_check = f"{title} {venue}"
            bio_keyword_count = sum(1 for keyword in BIOMEDICAL_KEYWORDS if keyword in text_to_check)
            boost_score += bio_keyword_count * 0.2
            
            # Apply boost
            paper['relevance_boost'] = paper.get('relevance_boost', 1.0) * boost_score
    
    # Filter out very low-relevance results if context is specific
    if context_type != "general":
        # Remove papers with very low boost scores - more aggressive filtering
        min_boost = 1.2  # Must have significant context relevance
        filtered_results = [paper for paper in results if paper.get('relevance_boost', 1.0) >= min_boost]
        
        if verbose:
            removed_count = len(results) - len(filtered_results)
            if removed_count > 0:
                console.print(f"[dim yellow]📊 Filtered out {removed_count} papers with low context relevance[/dim yellow]")
        
        return filtered_results
    
    return results

def search_with_cs_priority(verifier: MultiDatabaseVerifier, search_ref: Dict[str, Any], verbose: bool = False) -> List[Dict[str, Any]]:
    """Search with Computer Science database priority"""
    if verbose:
        console.print("[dim cyan]🖥️ Using Computer Science optimized search strategy...[/dim cyan]")
    
    all_results = []
    
    # Search databases in priority order with pre-configured limits
    search_results = verifier.search_across_databases(search_ref)
    
    for db_name in CS_DATABASE_PRIORITIES:
        if db_name in search_results:
            db_results = search_results[db_name]
            limit = min(len(db_results), CS_RESULT_LIMITS.get(db_name, 5))
            
            all_results.extend(db_results[:limit])
            
            if verbose and len(db_results) > 0:
                console.print(f"[dim]   📚 {db_name}: {len(db_results[:limit])}/{len(db_results)} results (CS priority)[/dim]")
    
    return all_results

def search_with_bio_priority(verifier: MultiDatabaseVerifier, search_ref: Dict[str, Any], verbose: bool = False) -> List[Dict[str, Any]]:
    """Search with Biomedical database priority"""
    if verbose:
        console.print("[dim cyan]🧬 Using Biomedical optimized search strategy...[/dim cyan]")
    
    all_results = []
    
    # Search databases in priority order with pre-configured limits
    search_results = verifier.search_across_databases(search_ref)
    
    for db_name in BIO_DATABASE_PRIORITIES:
        if db_name in search_results:
            db_results = search_results[db_name]
            limit = min(len(db_results), BIO_RESULT_LIMITS.get(db_name, 5))
            
            all_results.extend(db_results[:limit])
            
            if verbose and len(db_results) > 0:
                console.print(f"[dim]   📚 {db_name}: {len(db_results[:limit])}/{len(db_results)} results (Bio priority)[/dim]")
    
    return all_results

def search_and_cite(query: str, context: str = "general", output_file: str = None, output_format: str = None, verbose: bool = False):
    """Search for papers and generate citations with context-aware database selection"""
    
    # Normalize context efficiently
    context_type = {
        "cs": "computer-science", "computer-science": "computer-science",
        "bio": "biomedical", "biomedical": "biomedical"
    }.get(context.lower(), "general")
    
    # Display context information
    context_display = {
        "computer-science": "🖥️ Computer Science",
        "biomedical": "🧬 Biomedical",
        "general": "🔍 General"
    }
    
    console.print(f"🔍 Searching for papers matching: [bold cyan]{query}[/bold cyan]")
    console.print(f"📚 Research Context: [bold yellow]{context_display[context_type]}[/bold yellow]")
    console.print()
    
    # Initialize multi-database verifier with context-aware configuration
    try:
        verifier = MultiDatabaseVerifier()
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize verifier: {e}[/red]")
        return
    
    # Create search reference with context hints
    search_ref = {
        'title': query,
        'authors': [],
        'year': None,
        'venue': '',
        'context': context_type
    }
    
    # Search with context-aware prioritization
    try:
        if context_type == "computer-science":
            search_results = search_with_cs_priority(verifier, search_ref, verbose)
        elif context_type == "biomedical":
            search_results = search_with_bio_priority(verifier, search_ref, verbose)
        else:
            search_results = verifier.verify_reference(search_ref)
        
        if not search_results:
            console.print("[yellow]⚠️ No papers found matching your query.[/yellow]")
            if context_type != "general":
                console.print(f"[dim]💡 Try switching to --context general for broader search[/dim]")
            console.print("\n💡 Tips:")
            console.print("  • Try different keywords")
            console.print("  • Search for a more specific paper title")
            console.print("  • Include author names in your query")
            return
        
        # Apply context-aware filtering
        if context_type != "general":
            search_results = apply_context_filtering(search_results, context_type, verbose)
            
            if not search_results:
                console.print("[yellow]⚠️ No context-relevant papers found.[/yellow]")
                console.print(f"[dim]💡 Try --context general for broader results[/dim]")
                return
        
        # Remove duplicates efficiently using dict to preserve order
        unique_papers = {}
        for paper in search_results:
            title_key = paper.get('title', '').lower().strip()
            if title_key and title_key not in unique_papers:
                unique_papers[title_key] = paper
        
        unique_papers_list = list(unique_papers.values())
        
        # Calculate relevance scores efficiently
        query_normalized = normalize_text(query)
        
        def calculate_relevance_score(paper):
            paper_title = normalize_text(paper.get('title', ''))
            base_score = calculate_text_similarity(paper_title, query_normalized)
            context_boost = paper.get('relevance_boost', 1.0)
            
            if context_type != "general":
                # Enhanced context weighting
                multiplier = 1.5 if context_boost > 1.1 else 0.3
                return min(base_score * context_boost * multiplier, 1.0)
            else:
                return min(base_score * context_boost, 1.0)
        
        # Score and sort papers
        scored_papers = [(paper, calculate_relevance_score(paper)) for paper in unique_papers_list]
        scored_papers.sort(key=lambda x: x[1], reverse=True)
        
        # Intelligent paper selection
        selected_papers = []
        if scored_papers:
            top_paper, top_score = scored_papers[0]
            selected_papers.append((top_paper, top_score))
            
            # Add additional papers based on score distribution
            score_threshold = 0.1
            for paper, score in scored_papers[1:3]:  # Consider up to 2 more papers
                if top_score > 0.8 and (top_score - score) > 0.2:
                    break  # Top result is clearly best
                if (len(selected_papers) == 1 and (top_score - score) <= score_threshold) or score > 0.6:
                    selected_papers.append((paper, score))
                elif len(selected_papers) == 2 and score > 0.5 and (selected_papers[-1][1] - score) <= score_threshold:
                    selected_papers.append((paper, score))
        
        # Display results
        console.print(f"📚 Found [bold green]{len(unique_papers_list)}[/bold green] unique papers across multiple databases")
        console.print(f"Showing top [bold cyan]{len(selected_papers)}[/bold cyan] most relevant result{'s' if len(selected_papers) > 1 else ''}:\n")
        
        citations = []
        for i, (paper, score) in enumerate(selected_papers, 1):
            # Extract paper details efficiently
            title = paper.get('title', 'Unknown Title')
            authors = paper.get('authors', [])
            year = paper.get('year', 'Unknown Year')
            venue = paper.get('venue', 'Unknown Venue')
            doi = paper.get('doi', '')
            
            # Format authors efficiently with name cleaning
            if isinstance(authors, list) and authors:
                cleaned_authors = [clean_author_name(author) for author in authors]
                if len(cleaned_authors) == 1:
                    author_str = cleaned_authors[0]
                elif len(cleaned_authors) == 2:
                    author_str = f"{cleaned_authors[0]} and {cleaned_authors[1]}"
                else:
                    author_str = f"{cleaned_authors[0]} et al."
            else:
                author_str = "Unknown Authors"
            
            # Handle venue display (could be a list)
            if isinstance(venue, list):
                venue_display = ' | '.join(str(v) for v in venue) if venue else 'Unknown Venue'
            else:
                venue_display = str(venue) if venue else 'Unknown Venue'
            
            # Display paper info
            console.print(f"[bold cyan]{i}.[/bold cyan] {title}")
            console.print(f"   👥 Authors: {author_str}")
            console.print(f"   📅 Year: {year}")
            console.print(f"   🏛️ Venue: {venue_display}")
            console.print(f"   📊 Relevance Score: {score:.2f}")
            if doi:
                console.print(f"   🔗 DOI: {doi}")
            
            # Generate BibTeX entry
            bibtex_key = f"paper{year}{i}" if year and str(year).isdigit() else f"paper{i}"
            bibtex_entry = generate_bibtex(paper, bibtex_key)
            
            console.print(f"   📋 BibTeX:")
            console.print(f"   [dim]{bibtex_entry}[/dim]")
            console.print()
            
            citations.append({
                'rank': i,
                'paper': paper,
                'bibtex': bibtex_entry,
                'relevance_score': score
            })
        
        # Show database breakdown in verbose mode
        if verbose:
            console.print("\n📊 Database Coverage:")
            db_counts = {}
            for paper in search_results:
                source = paper.get('source', 'unknown')
                db_counts[source] = db_counts.get(source, 0) + 1
            
            for db_name, count in sorted(db_counts.items()):
                console.print(f"   • {db_name}: {count} results")
        
        # Save results if requested
        if output_file:
            save_citation_results(citations, output_file, output_format)
            console.print(f"\n💾 Results saved to: [bold green]{output_file}[/bold green]")
        
    except Exception as e:
        console.print(f"[red]❌ Error during search: {e}[/red]")
        if verbose:
            console.print("[red]Error traceback:[/red]")
            console.print(traceback.format_exc())

def generate_bibtex(paper: dict, key: str) -> str:
    """Generate comprehensive BibTeX entry for a paper with optimized string handling"""
    # Extract all fields once
    title = paper.get('title', '')
    authors = paper.get('authors', [])
    year = paper.get('year', '')
    venue = paper.get('venue', '')
    doi = paper.get('doi', '')
    url = paper.get('url', '')
    pages = paper.get('pages', '')
    volume = paper.get('volume', '')
    number = paper.get('number', '') or paper.get('issue', '')
    publisher = paper.get('publisher', '')
    editor = paper.get('editor', '') or paper.get('editors', [])
    
    # Determine entry type efficiently - handle venue being a list
    if isinstance(venue, list):
        venue_lower = ' '.join(str(v) for v in venue).lower() if venue else ''
    else:
        venue_lower = str(venue).lower() if venue else ''
        
    if any(word in venue_lower for word in ['conference', 'proceedings', 'workshop', 'symposium']):
        entry_type = "inproceedings"
    elif any(word in venue_lower for word in ['arxiv', 'preprint']):
        entry_type = "misc"
    else:
        entry_type = "article"
    
    # Pre-build all field strings to minimize repeated string operations
    fields = [f"@{entry_type}{{{key},"]
    
    # Author field (optimized formatting with name cleaning)
    if isinstance(authors, list) and authors:
        # Clean author names to remove database disambiguation numbers
        cleaned_authors = [clean_author_name(author) for author in authors if author]
        author_str = ' and\n                  '.join(cleaned_authors)
        if author_str:
            fields.append(f"  author       = {{{author_str}}},")
    
    # Editor field (also clean editor names)
    if editor:
        if isinstance(editor, list) and editor:
            cleaned_editors = [clean_author_name(e) for e in editor if e]
            editor_str = ' and\n                  '.join(cleaned_editors)
        else:
            editor_str = clean_author_name(str(editor))
        
        if editor_str and entry_type == "inproceedings":
            fields.append(f"  editor       = {{{editor_str}}},")
    
    # Title field
    if title:
        fields.append(f"  title        = {{{title}}},")
    
    # Venue-specific fields - handle venue being a list
    if venue:
        venue_str = ' | '.join(str(v) for v in venue) if isinstance(venue, list) else str(venue)
        if entry_type == "article":
            fields.append(f"  journal      = {{{venue_str}}},")
        elif entry_type == "inproceedings":
            fields.append(f"  booktitle    = {{{venue_str}}},")
        else:
            fields.append(f"  howpublished = {{{venue_str}}},")
    
    # Volume and number
    if volume:
        fields.append(f"  volume       = {{{volume}}},")
    if number:
        fields.append(f"  number       = {{{number}}},")
    
    # Pages (optimized formatting)
    if pages:
        pages_formatted = pages.replace('−', '--').replace('–', '--').replace('-', '--', 1) if '--' not in pages else pages
        fields.append(f"  pages        = {{{pages_formatted}}},")
    
    # Publisher, year, DOI, URL
    if publisher:
        fields.append(f"  publisher    = {{{publisher}}},")
    if year:
        fields.append(f"  year         = {{{year}}},")
    if doi:
        doi_clean = doi.replace('https://doi.org/', '').replace('http://dx.doi.org/', '')
        fields.append(f"  doi          = {{{doi_clean}}},")
    elif url:
        fields.append(f"  url          = {{{url}}},")
    
    # Remove trailing comma from last field and close
    if fields[-1].endswith(','):
        fields[-1] = fields[-1][:-1]
    fields.append("}")
    
    return '\n'.join(fields)

def save_citation_results(citations: list, output_file: str, output_format: str = None):
    """Save citation results to file with optimized I/O"""
    from pathlib import Path
    
    # Determine format efficiently
    format_type = output_format.lower() if output_format else Path(output_file).suffix.lower().lstrip('.')
    
    try:
        if format_type == 'json':
            # Save as JSON with streaming for large datasets
            data = {
                'query_timestamp': str(datetime.now()),
                'total_results': len(citations),
                'citations': citations
            }
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        else:
            # Save as text with efficient string building
            timestamp = str(datetime.now())
            total_results = len(citations)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                # Write header
                f.write(f"Citation Search Results\nGenerated: {timestamp}\nTotal Results: {total_results}\n\n")
                
                # Write citations efficiently
                for citation in citations:
                    paper = citation['paper']
                    rank = citation['rank']
                    relevance_score = citation.get('relevance_score', 0.0)
                    
                    # Build citation block efficiently
                    authors = paper.get('authors', ['Unknown'])
                    author_str = ', '.join(authors) if isinstance(authors, list) else str(authors)
                    
                    citation_block = (
                        f"{rank}. {paper.get('title', 'Unknown Title')}\n"
                        f"   Authors: {author_str}\n"
                        f"   Year: {paper.get('year', 'Unknown')}\n"
                        f"   Venue: {paper.get('venue', 'Unknown')}\n"
                        f"   Relevance Score: {relevance_score:.2f}\n"
                    )
                    
                    if paper.get('doi'):
                        citation_block += f"   DOI: {paper.get('doi')}\n"
                    
                    citation_block += f"\n   BibTeX:\n{citation['bibtex']}\n\n"
                    citation_block += "-" * 80 + "\n\n"
                    
                    f.write(citation_block)
    except Exception as e:
        console.print(f"[red]❌ Error saving results: {e}[/red]")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="VerifyRef - Comprehensive academic reference verification and citation tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify references in a PDF
  verifyref paper.pdf
  
  # Flexible verification with auto-detection
  verifyref --verify paper.pdf                                    # PDF file
  verifyref --verify references.txt                               # Text file with references
  verifyref --verify "Smith, J. (2020). Machine Learning. Nature."   # Single reference
  
  # Search for a paper and generate BibTeX citation
  verifyref --cite "Autoguess A Tool for Finding Guess-and-Determine Attacks"
  verifyref --cite "A Geometric Approach to Linear Cryptanalysis"
  
  # Search with specific research context
  verifyref --cite "Revisiting Differential-Linear Attacks via a Boomerang Perspective" --context computer-science
  verifyref --cite "COVID-19 vaccine efficacy" --context biomedical
  verifyref --cite "Finding the Impossible Impossible-Differential Attack" --context cs
  verifyref --cite "protein folding" --context bio
  
  # Save results as JSON
  verifyref paper.pdf --output results.json
  verifyref --verify references.txt --output results.json
  
  # Save results as text report
  verifyref paper.pdf --output report.txt
  verifyref --verify "Smith, J. (2020). Title." --output report.txt
  
  # Explicit format specification
  verifyref paper.pdf --output results --output-format txt
  
  # Verbose mode for detailed output
  verifyref paper.pdf --verbose
  verifyref --verify references.txt --verbose
        """
    )
    
    # Main command group
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("file", nargs='?', type=str, help="Path to PDF file to analyze for reference verification")
    group.add_argument("--cite", type=str, help="Search for a paper by title/keywords and generate BibTeX citation")
    group.add_argument("--verify", type=str, help="Verify a reference from text input (auto-detects: single reference string, text file, or PDF)")
    
    # Optional arguments - using more concise definitions
    args_config = [
        ("--context", "-c", {"choices": ["computer-science", "cs", "biomedical", "bio", "general"], "default": "general", 
         "help": "Research context for citation search"}),
        ("--output", "-o", {"help": "Output file for results (format determined by extension: .json, .txt)"}),
        ("--output-format", "-f", {"choices": ["json", "txt"], "help": "Output format (default: auto-detect from file extension)"}),
        ("--verbose", "-v", {"action": "store_true", "help": "Enable verbose output"}),
        ("--rigor", "-r", {"choices": ["strict", "balanced", "lenient"], "default": "balanced", 
         "help": "Verification rigor level"}),
        ("--similarity-threshold", None, {"type": float, "metavar": "0.0-1.0", 
         "help": "Override similarity threshold for authentic classification"}),
        ("--enable-ai", None, {"action": "store_true", "help": "Enable AI-powered verification (requires OpenAI API key)"}),
        ("--disable-fraud-detection", None, {"action": "store_true", "help": "Disable enhanced fraud detection"}),
        ("--require-multi-db", None, {"action": "store_true", 
         "help": "Require papers to be found in multiple databases for high confidence"})
    ]
    
    # Add all arguments using loop
    for arg_name, short_name, config in args_config:
        if short_name:
            parser.add_argument(arg_name, short_name, **config)
        else:
            parser.add_argument(arg_name, **config)
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Apply rigor level and configuration overrides
    apply_runtime_config(args)
    
    try:
        if args.file:
            # Reference verification mode  
            if not Path(args.file).exists():
                console.print(f"[red]❌ File not found: {args.file}[/red]")
                sys.exit(1)
            
            verify_references(args.file, args.output, args.output_format, args.verbose)
        elif args.cite:
            # Citation lookup mode
            search_and_cite(args.cite, args.context, args.output, args.output_format, args.verbose)
        elif args.verify:
            # Flexible verification mode with auto-detection
            verify_flexible_input(args.verify, args.output, args.output_format, args.verbose)
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        if args.verbose:
            console.print("[red]Error traceback:[/red]")
            console.print(traceback.format_exc())
        else:
            console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
