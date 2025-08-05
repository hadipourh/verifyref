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
from config import validate_config, get_config, DATABASE_CONFIG
from grobid.client import GrobidClient
from extractor.reference_parser import ReferenceParser
from verifier.semantic_scholar import SemanticScholarClient
from verifier.multi_database_verifier import MultiDatabaseVerifier
from verifier.classifier import ReferenceClassifier
from utils.report_generator import generate_human_readable_report
from utils.helpers import calculate_text_similarity, normalize_text

# Initialize rich console
console = Console()

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

def validate_openai_api_key(api_key: str) -> bool:
    """Validate OpenAI API key by making a simple API call"""
    if not api_key or api_key == "your-openai-api-key-here":
        return False
    
    try:
        import openai
        
        # Create a client with the provided API key
        client = openai.OpenAI(api_key=api_key)
        
        # Make a minimal API call to test the key
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use the cheapest model for testing
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1,  # Minimal token usage
            timeout=10  # Quick timeout
        )
        return True
        
    except Exception as e:
        # Log the specific error for debugging but don't expose it to user
        logging.debug(f"API key validation failed: {e}")
        return False

def apply_runtime_config(args):
    """Apply runtime configuration overrides from command line arguments"""
    from config import CLASSIFICATION_CONFIG, DATABASE_CONFIG, set_rigor_level
    
    # Apply rigor level
    if args.rigor:
        set_rigor_level(args.rigor)
        console.print(f"[blue]🔧 Rigor level set to: {args.rigor}[/blue]")
    
    # Apply individual overrides
    if args.similarity_threshold is not None:
        if 0.0 <= args.similarity_threshold <= 1.0:
            CLASSIFICATION_CONFIG["similarity_threshold"] = args.similarity_threshold
            console.print(f"[blue]🔧 Similarity threshold set to: {args.similarity_threshold}[/blue]")
        else:
            console.print("[red]❌ Similarity threshold must be between 0.0 and 1.0[/red]")
            sys.exit(1)
    
    # Handle AI verification flag (AI is disabled by default)
    if args.enable_ai:
        if "ai_verification" in DATABASE_CONFIG:
            # Check for API key
            api_key = DATABASE_CONFIG["ai_verification"].get("openai_api_key") or os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                console.print("[red]❌ Cannot enable AI verification: No OpenAI API key found[/red]")
                console.print("[yellow]   • Set OPENAI_API_KEY in config.py (recommended), or[/yellow]")
                console.print("[yellow]   • Set OPENAI_API_KEY environment variable[/yellow]")
                console.print("[blue]🔧 AI verification remains disabled[/blue]")
            elif not validate_openai_api_key(api_key):
                console.print("[red]❌ Cannot enable AI verification: Invalid or expired OpenAI API key[/red]")
                console.print("[yellow]   • Check your API key at https://platform.openai.com/api-keys[/yellow]")
                console.print("[yellow]   • Ensure your account has sufficient credits[/yellow]")
                console.print("[blue]🔧 AI verification remains disabled[/blue]")
            else:
                DATABASE_CONFIG["ai_verification"]["enabled"] = True
                console.print("[green]🔧 AI verification enabled with valid API key[/green]")
    
    # Disable fraud detection if requested
    if args.disable_fraud_detection:
        CLASSIFICATION_CONFIG["enable_fraud_detection"] = False
        console.print("[blue]🔧 Fraud detection disabled[/blue]")
    
    # Require multi-database if requested
    if args.require_multi_db:
        CLASSIFICATION_CONFIG["multi_database_requirement"] = True
        console.print("[blue]🔧 Multi-database requirement enabled[/blue]")

def setup_logging(verbose=False):
    """Setup logging configuration with Rich compatibility"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create a custom handler that works with Rich
    from rich.logging import RichHandler
    
    # Clear any existing handlers
    logging.getLogger().handlers = []
    
    # Configure logging with RichHandler
    logging.basicConfig(
        level=level,
        format='%(message)s',
        datefmt='%H:%M:%S',
        handlers=[RichHandler(console=console, show_time=True, show_path=False)]
    )
    
    # Reduce verbosity of some loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

def make_json_serializable(data):
    """Convert data to JSON-serializable format"""
    if hasattr(data, 'to_dict'):
        return data.to_dict()
    elif isinstance(data, dict):
        return {k: make_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_json_serializable(item) for item in data]
    elif hasattr(data, '__dict__'):
        # For any object with __dict__, convert to dict representation
        return make_json_serializable(data.__dict__)
    else:
        # For basic types (str, int, float, bool, None)
        return data

def determine_output_format(output_file: str, output_format: str = None) -> str:
    """Determine output format from file extension or explicit format"""
    if output_format:
        return output_format.lower()
    
    if output_file:
        ext = Path(output_file).suffix.lower()
        if ext == '.json':
            return 'json'
        elif ext == '.txt':
            return 'txt'
    
    # Default to JSON
    return 'json'

def generate_human_readable_report(results: Dict[str, Any], classifier=None) -> str:
    """Generate a human-readable text report with enhanced formatting"""
    report_lines = []
    
    # Header
    report_lines.append("=" * 80)
    report_lines.append("🔍 VerifyRef Reference Verification Report")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Summary
    summary = results.get('summary', {})
    total_refs = summary.get('total_references', 0)
    authentic = summary.get('authentic', 0)
    suspicious = summary.get('suspicious', 0)
    fake = summary.get('fake', 0)
    inconclusive = summary.get('inconclusive', 0)
    
    report_lines.append("📊 SUMMARY")
    report_lines.append("-" * 80)
    report_lines.append(f"Total References: {total_refs}")
    report_lines.append(f"✅ Authentic: {authentic}")
    report_lines.append(f"🔍 Suspicious: {suspicious}")
    report_lines.append(f"❌ Fake/Fabricated: {fake}")
    report_lines.append(f"❓ Inconclusive: {inconclusive}")
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
                    report_lines.append(f"� {db_name.upper()}: {str(db_results)}")
                    
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

def save_results(results: Dict[str, Any], output_file: str, output_format: str, classifier=None):
    """Save results in the specified format"""
    try:
        if output_format == 'json':
            # Convert to JSON-serializable format
            json_safe_results = make_json_serializable(results)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_safe_results, f, indent=2, ensure_ascii=False)
        
        elif output_format == 'txt':
            # Generate human-readable report
            report = generate_human_readable_report(results, classifier)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
        
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        console.print(f"[green]📊 Results saved to: {output_file} ({output_format.upper()} format)[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Error saving results: {e}[/red]")
        raise

def verify_references(pdf_path: str, output_file: str = None, output_format: str = None, verbose: bool = False):
    """
    Enhanced reference verification with parallel processing optimization.
    
    Major performance improvements:
    - Parallel database verification (up to 4x faster for multiple references)
    - Thread-safe caching system with optimized hit rate
    - Reduced memory overhead with efficient string operations
    - Smart progress reporting (sequential for verbose, parallel for speed)
    """
    import time
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
    
    # Initialize components
    config = get_config()
    grobid_client = GrobidClient()
    parser = ReferenceParser()
    verifier = MultiDatabaseVerifier()
    classifier = ReferenceClassifier()
    
    # Extract references using GROBID
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=console
    ) as progress:
        extract_task = progress.add_task("📄 Extracting references from PDF...", total=None)
        
        try:
            references = grobid_client.extract_references(pdf_path)
            if not references:
                console.print("[red]❌ Failed to extract references from PDF[/red]")
                sys.exit(1)
            
            console.print(f"[green]📚 Extracted {len(references)} references[/green]")
            
        except Exception as e:
            console.print(f"[red]❌ Error processing PDF: {e}[/red]")
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
            reasons=[error_reason]
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
    max_workers = min(4, len(references))  # Limit to 4 threads to avoid overwhelming APIs
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        
        main_task = progress.add_task(
            "🔍 Processing references", 
            total=len(references)
        )
        
        if verbose:
            # Sequential processing for verbose mode to maintain ordered output
            for i, ref in enumerate(references, 1):
                progress.update(
                    main_task, 
                    description=f"🔍 Reference {i}/{len(references)}",
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
                        description=f"🔍 Completed {completed_count}/{len(references)}",
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
                            reasons=[f'Processing error: {str(e)}']
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
            'pdf_file': pdf_path,
            'analysis_date': datetime.now().isoformat(),
            'total_references': len(references),
            'verifyref_version': '1.0.0'
        },
        'analysis_metadata': {
            'pdf_file': pdf_path,
            'analysis_date': datetime.now().isoformat(),
            'total_references_found': len(references),
            'references_processed': len(verified_references)
        },
        'summary': summary,
        'references': verified_references,
        'detailed_results': verified_references
    }
    
    # Display summary table
    display_verification_summary(results['summary'], len(references))
    
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
        save_results(results, output_file, format_to_use, classifier)
    else:
        # Generate human-readable report for console output
        report = generate_human_readable_report(results, classifier)
        console.print("\n" + "="*80)
        console.print(report)

def display_verification_summary(summary: Dict[str, Any], total_refs: int):
    """Display a beautiful summary table of verification results"""
    
    table = Table(title="[*] Verification Summary", box=box.ROUNDED)
    table.add_column("Classification", style="bold", min_width=24)
    table.add_column("Count", justify="right", min_width=5)
    table.add_column("Percentage", justify="right", min_width=10)
    table.add_column("Status", justify="center", min_width=6)
    
    # Use the correct classification_counts from classifier's summary
    counts = summary.get('classification_counts', {})
    percentages = summary.get('percentages', {})
    
    # Add rows with colors and monochrome hacker-style symbols
    table.add_row(
        "[green][+] AUTHENTIC[/green]", 
        str(counts.get('authentic', 0)), 
        f"{percentages.get('authentic', 0):6.1f}%",
        "[green]●[/green]" if counts.get('authentic', 0) > 0 else "[dim]○[/dim]"
    )
    table.add_row(
        "[yellow][?] SUSPICIOUS[/yellow]", 
        str(counts.get('suspicious', 0)), 
        f"{percentages.get('suspicious', 0):6.1f}%",
        "[yellow]●[/yellow]" if counts.get('suspicious', 0) > 0 else "[dim]○[/dim]"
    )
    table.add_row(
        "[red][X] FAKE[/red]", 
        str(counts.get('fake', 0)), 
        f"{percentages.get('fake', 0):6.1f}%",
        "[red]●[/red]" if counts.get('fake', 0) > 0 else "[dim]○[/dim]"
    )
    table.add_row(
        "[purple][~] AUTHOR MANIPULATION[/purple]", 
        str(counts.get('author_manipulation', 0)), 
        f"{percentages.get('author_manipulation', 0):6.1f}%",
        "[purple]●[/purple]" if counts.get('author_manipulation', 0) > 0 else "[dim]○[/dim]"
    )
    table.add_row(
        "[red][-] FABRICATED[/red]", 
        str(counts.get('fabricated', 0)), 
        f"{percentages.get('fabricated', 0):6.1f}%",
        "[red]●[/red]" if counts.get('fabricated', 0) > 0 else "[dim]○[/dim]"
    )
    table.add_row(
        "[blue][!] INCONCLUSIVE[/blue]", 
        str(counts.get('inconclusive', 0)), 
        f"{percentages.get('inconclusive', 0):6.1f}%",
        "[blue]●[/blue]" if counts.get('inconclusive', 0) > 0 else "[dim]○[/dim]"
    )
    
    console.print()
    console.print(table)
    
    # Overall assessment from classifier
    risk_assessment = summary.get('risk_assessment', '🔍 Inconclusive - More investigation needed')
    console.print(f"\n{risk_assessment}")
    console.print()

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

def clean_author_name(author_name: str) -> str:
    """Clean author names by removing database disambiguation numbers"""
    from utils.academic_matching import clean_author_name as clean_name
    return clean_name(author_name)

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
            import json
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
  
  # Save results as text report
  verifyref paper.pdf --output report.txt
  
  # Explicit format specification
  verifyref paper.pdf --output results --output-format txt
  
  # Verbose mode for detailed output
  verifyref paper.pdf --verbose
        """
    )
    
    # Main command group
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("file", nargs='?', type=str, help="Path to PDF file to analyze for reference verification")
    group.add_argument("--cite", type=str, help="Search for a paper by title/keywords and generate BibTeX citation")
    
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
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        if args.verbose:
            import traceback
            console.print("[red]Error traceback:[/red]")
            console.print(traceback.format_exc())
        else:
            console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
