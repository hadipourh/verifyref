# VerifyRef Technical Documentation

**Version**: 1.1.0  
**Last Updated**: February 2026  
**Author**: Hosein Hadipour  
**License**: GPL-3.0

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Data Flow](#data-flow)
4. [Database Clients](#database-clients)
5. [Classification System](#classification-system)
6. [AI Verification](#ai-verification)
7. [Configuration](#configuration)
8. [API Reference](#api-reference)

## Architecture Overview

VerifyRef is a modular academic reference verification tool that combines multi-database searches with optional AI-powered analysis to detect fabricated or manipulated references.

### System Architecture

```
                                    +-----------------+
                                    |   verifyref.py  |
                                    |   (CLI Entry)   |
                                    +--------+--------+
                                             |
              +------------------------------+------------------------------+
              |                              |                              |
    +---------v---------+        +-----------v-----------+        +--------v--------+
    | grobid/client.py  |        | verifier/multi_db     |        | utils/output    |
    | (Smart PDF Parse) |        | (Database Coordinator)|        | (Report Gen)    |
    +-------------------+        +-----------+-----------+        +-----------------+
              |                              |
              v                              |
    +-------------------+    +---------------+---------------+
    | fallback_parser   |    |       Database Clients        |
    | (PyMuPDF backup)  |    +-------------------------------+
    +-------------------+    | OpenAlex | DBLP | PubMed | ...|
                             +---------------+---------------+
                                             |
                                    +--------v--------+
                                    |   classifier    |
                                    | (Fraud Detect)  |
                                    +--------+--------+
                                             |
                              +--------------+--------------+
                              |                             |
                     +--------v--------+           +--------v--------+
                     | doi_validation  |           |   ai_verifier   |
                     | (Retraction)    |           |   (Optional)    |
                     +-----------------+           +-----------------+
```

### Design Principles

1. **Modular Architecture**: Each component has a single responsibility
2. **Parallel Processing**: Multi-threaded database searches for performance
3. **Fail-Safe Operation**: Graceful degradation when services are unavailable
4. **Configurable Sensitivity**: Adjustable thresholds for different use cases
5. **Multi-Provider AI**: Support for free (Gemini, Groq, Ollama) and paid (OpenAI) AI providers

## Core Components

### 1. CLI Entry Point (verifyref.py)

The main entry point handles:
- Command-line argument parsing
- Input type detection (PDF, text file, single reference)
- Workflow orchestration
- Progress display and result formatting

**Key Functions**:
- `verify_references()`: Main verification pipeline
- `search_and_cite()`: Citation lookup and BibTeX generation
- `detect_input_type()`: Determines input format

### 2. PDF Processing (grobid/client.py)

Smart GROBID client with automatic fallback chain.

**Fallback Chain**:
1. Public GROBID server (kermitt2-grobid.hf.space) - default, no setup
2. Local GROBID (localhost:8070) - faster, private
3. PyMuPDF fallback (grobid/fallback_parser.py) - lower accuracy (~75%)

**Key Classes**:
```python
class GrobidClient:
    """Standard GROBID client for a single server"""
    def extract_references(pdf_path: str) -> List[Dict]
    def parse_citation_string(citation_text: str) -> Dict
    def is_available() -> bool

class SmartGrobidClient:
    """Client with automatic fallback chain"""
    def extract_references(pdf_path: str) -> List[Dict]
    def get_active_source() -> str  # Returns which backend is in use
```

**Features**:
- Connects to GROBID service
- Extracts structured reference data (title, authors, venue, year, DOI)
- Title post-processing to clean HTML artifacts
- Two-pass parsing: preserves original authors before consolidation

### 3. Fallback Parser (grobid/fallback_parser.py)

Lightweight PDF reference parser using PyMuPDF when GROBID is unavailable.

**Accuracy**: ~75% (vs GROBID's ~95%)

**Features**:
- Reference section detection
- Basic author/title/year extraction
- DOI and arXiv ID extraction
- No external service required

### 4. Multi-Database Verifier (verifier/multi_database_verifier.py)

Coordinates searches across multiple academic databases.

**Features**:
- Parallel database queries with thread pool
- Early exit when high-confidence match found
- Smart caching to avoid duplicate searches
- Retry mechanism for failed databases
- Context-aware database prioritization (CS, Bio, General)

**Search Priority by Context**:
- **CS**: OpenAlex, DBLP, IACR, Semantic Scholar, ArXiv
- **Bio**: OpenAlex, PubMed, Semantic Scholar, ArXiv
- **General**: All databases equally weighted

### 5. Classifier (verifier/classifier.py)

Determines reference authenticity based on search results.

**Classification Categories**:

| Category | Description |
|----------|-------------|
| AUTHENTIC | High similarity match found in major databases |
| SUSPICIOUS | Moderate match, needs manual review |
| FABRICATED | No matches found, likely fake |
| AUTHOR_MANIPULATION | Title matches but authors differ significantly |
| INCONCLUSIVE | Unable to determine (parsing errors, etc.) |

**Key Features**:
- Weighted similarity scoring
- Author manipulation detection
- Book reference detection
- DOI validation
- Retraction status checking

### 6. DOI Validation (verifier/doi_validation_client.py)

DOI resolution and retraction detection.

**Features**:
- DOI metadata retrieval from CrossRef
- Retraction status checking via CrossRef
- Title-based retraction search via Retraction Watch
- Publisher and metadata validation

### 7. AI Verifier (verifier/ai_verifier.py)

Optional AI-powered verification using multiple providers.

**Supported Providers**:

| Provider | Cost | API Key Required | Rate Limits |
|----------|------|------------------|-------------|
| Ollama | Free | No (local) | None |
| Gemini | Free | Yes | 15 req/min |
| Groq | Free | Yes | 30 req/min |
| OpenAI | Paid | Yes | Varies |

## Data Flow

### Reference Verification Pipeline

```
1. Input Detection
   - PDF: Smart GROBID client (with fallback)
   - Text file: Line-by-line parsing
   - Single ref: Direct parsing

2. Reference Parsing
   - Extract: title, authors, venue, year, DOI, URL
   - Normalize: clean text, standardize names
   - Preserve: original data for fraud detection

3. Database Search (Parallel)
   - Query all enabled databases
   - Early exit on high-confidence match (>90%)
   - Retry failed databases once

4. Classification
   - Find best match by similarity score
   - Check for author manipulation
   - Detect book references
   - Check retraction status
   - Apply classification rules

5. AI Verification (Optional)
   - Send reference + search results to AI
   - Parse AI assessment
   - Incorporate into final classification

6. Output Generation
   - Terminal display with Rich formatting
   - File output (TXT or JSON)
   - Summary statistics
```

### Data Structures

**Parsed Reference**:
```python
{
    'title': str,
    'authors': List[str],
    'venue': str,
    'year': int,
    'doi': str,
    'url': str,
    'volume': str,
    'pages': str,
    'raw_text': str,
    'original_authors': List[str]  # Preserved for fraud detection
}
```

**Classification Result**:
```python
@dataclass
class VerificationResult:
    classification: ClassificationResult
    confidence: float
    similarity_score: float
    matched_paper: Optional[Dict]
    reasons: List[str]
    details: Dict
    issue_summary: str
    retraction_info: Optional[Dict]  # Retraction status if applicable
```

## Database Clients

### OpenAlex (verifier/openalex_client.py)

Primary database with comprehensive coverage.

- **API**: https://api.openalex.org
- **Rate Limit**: None (polite use expected)
- **Coverage**: 200M+ works

### DBLP (verifier/dblp_client.py)

Computer Science bibliography.

- **API**: https://dblp.org/search/publ/api
- **Rate Limit**: None
- **Coverage**: CS publications

### PubMed (verifier/pubmed_client.py)

Biomedical literature database.

- **API**: NCBI E-utilities
- **Rate Limit**: 3 req/sec (10 with API key)
- **Coverage**: 35M+ biomedical citations

### IACR (verifier/iacr_client.py)

International Association for Cryptologic Research.

- **API**: https://eprint.iacr.org
- **Rate Limit**: None
- **Coverage**: Cryptography papers

### ArXiv (verifier/arxiv_client.py)

Preprint repository.

- **API**: https://export.arxiv.org/api
- **Rate Limit**: None (be polite)
- **Coverage**: 2M+ preprints

### Semantic Scholar (verifier/semantic_scholar.py)

AI-powered academic search.

- **API**: https://api.semanticscholar.org
- **Rate Limit**: 100 req/5min (higher with API key)
- **Coverage**: 200M+ papers

### CrossRef (verifier/crossref_client.py)

DOI registration and metadata.

- **API**: https://api.crossref.org
- **Rate Limit**: 50 req/sec (polite pool)
- **Coverage**: 130M+ DOIs

### Google Scholar (verifier/google_scholar_client.py)

Smart fallback with rate limiting.

- **Usage**: Only when other databases find poor matches (<70% similarity)
- **Rate Limit**: Conservative (20s delay, 10 req/hour)
- **Purpose**: Author manipulation validation

## Classification System

### Similarity Calculation

The classifier uses weighted similarity scoring:

```python
similarity = (
    title_similarity * 0.55 +   # Increased - most reliable signal
    author_similarity * 0.25 +  # Reduced - name variations cause FPs
    venue_similarity * 0.15 +
    year_similarity * 0.05
)
```

### Classification Thresholds

| Threshold | Value | Description |
|-----------|-------|-------------|
| Authentic | >= 0.50 | High confidence match |
| Suspicious | 0.20 - 0.50 | Needs review |
| Inconclusive | < 0.20 | No credible match - manual verification needed |

> **Note**: Thresholds have been adjusted in v1.1.0 to reduce false positives. References that cannot be verified are now classified as INCONCLUSIVE rather than FABRICATED.

### Author Manipulation Detection

Triggered when:
- Title similarity > 80% (increased from 70% to reduce FPs)
- Author similarity < 25% (reduced from 40% to reduce FPs)
- Best match found in database
- Paper found in fewer than 2 databases
- Title similarity < 95% (very high matches skip this check)

This catches cases where someone copies a real paper title but changes the authors, while reducing false positives from name format variations.

### Retraction Detection

References are checked against:
- CrossRef retraction metadata (via DOI)
- Retraction Watch database (via title search)

Retracted papers are flagged with a warning regardless of other classification.

### Book Reference Detection

References are flagged as potential books when they contain:
- ISBN numbers
- Publisher names (Springer, Wiley, Cambridge, etc.)
- Edition indicators (2nd edition, etc.)
- Book-style titles (Handbook of, Introduction to, etc.)

Books are classified as INCONCLUSIVE rather than FABRICATED since they may not appear in paper databases.

## AI Verification

### Provider Configuration

Set the AI provider via environment variable:

```bash
# Ollama (free, local, no rate limits)
export AI_PROVIDER="ollama"

# Gemini (free, requires API key)
export AI_PROVIDER="gemini"
export GOOGLE_GEMINI_API_KEY="your-key"

# Groq (free, requires API key)
export AI_PROVIDER="groq"
export GROQ_API_KEY="your-key"

# OpenAI (paid)
export AI_PROVIDER="openai"
export OPENAI_API_KEY="your-key"
```

### Integration with Classification

AI results are incorporated with configurable weight:
- Strong database evidence: 20% AI weight
- Weak database evidence: 50% AI weight
- AI cannot override clear database evidence without exceptional confidence (>95%)

## Configuration

### config.py Structure

```python
# GROBID Configuration
GROBID_CONFIG = {
    "base_url": "https://kermitt2-grobid.hf.space",  # Public server default
    "timeout": 300,
    "max_retries": 3,
}

# Database enable/disable
ENABLE_CROSSREF = True
ENABLE_GOOGLE_SCHOLAR = True

# Required
CROSSREF_EMAIL = "your.email@domain.com"

# Optional API keys
SEMANTIC_SCHOLAR_API_KEY = ""
OPENAI_API_KEY = ""
GOOGLE_GEMINI_API_KEY = ""
GROQ_API_KEY = ""
NCBI_API_KEY = ""

# Classification thresholds
CLASSIFICATION_CONFIG = {
    "similarity_threshold": 0.50,
    "suspicious_threshold": 0.20,
    "title_weight": 0.55,
    "author_weight": 0.25,
    "venue_weight": 0.15,
    "year_weight": 0.05,
}
```

### Environment Variables

```bash
# GROBID server URL (overrides config)
export GROBID_URL="http://localhost:8070"

# AI provider selection
export AI_PROVIDER="ollama"

# API keys
export GOOGLE_GEMINI_API_KEY="..."
export GROQ_API_KEY="..."
export OPENAI_API_KEY="..."
```

### Runtime Options

```bash
# Rigor levels
--rigor strict    # High precision, may miss some
--rigor balanced  # Default
--rigor lenient   # High recall, more false positives

# Custom threshold
--similarity-threshold 0.6

# Enable AI
--enable-ai
```

## API Reference

### Command Line Interface

```
verifyref.py [OPTIONS] FILE

Arguments:
  FILE                    PDF file, text file, or reference string

Options:
  -o, --output FILE       Output file path
  --output-format FORMAT  Output format (txt, json)
  --rigor LEVEL           Verification rigor (strict, balanced, lenient)
  --similarity-threshold  Custom similarity threshold (0.0-1.0)
  --enable-ai             Enable AI-powered verification
  --verbose               Show detailed logging
  --cite QUERY            Search for a citation
  --context TYPE          Search context (cs, bio, general)
  --verify REF            Verify a single reference string
```

### Python API

```python
from grobid.client import get_smart_client
from verifier.multi_database_verifier import MultiDatabaseVerifier
from verifier.classifier import ReferenceClassifier

# Extract references from PDF (with automatic fallback)
grobid = get_smart_client()
print(f"Using: {grobid.get_active_source()}")
references = grobid.extract_references("paper.pdf")

# Search databases
verifier = MultiDatabaseVerifier()
for ref in references:
    results = verifier.search_across_databases(ref)
    
    # Classify
    classifier = ReferenceClassifier()
    classification = classifier.classify_reference(ref, results)
    
    print(f"{ref['title']}: {classification.classification}")
    if classification.retraction_info:
        print(f"  WARNING: Paper may be retracted")
```

## File Structure

```
verifyref/
├── verifyref.py              # CLI entry point
├── config.py                 # Configuration
├── grobid/
│   ├── __init__.py
│   ├── client.py             # GROBID client + SmartGrobidClient
│   └── fallback_parser.py    # PyMuPDF fallback parser
├── extractor/
│   └── reference_parser.py   # Reference parsing
├── verifier/
│   ├── multi_database_verifier.py
│   ├── classifier.py         # Classification logic
│   ├── ai_verifier.py        # AI verification
│   ├── doi_validation_client.py  # DOI + retraction checking
│   ├── openalex_client.py
│   ├── dblp_client.py
│   ├── pubmed_client.py
│   ├── iacr_client.py
│   ├── arxiv_client.py
│   ├── semantic_scholar.py
│   ├── crossref_client.py
│   ├── google_scholar_client.py
│   └── springer_client.py
├── utils/
│   ├── helpers.py            # Common utilities
│   ├── academic_matching.py  # Similarity algorithms
│   ├── report_generator.py   # Output formatting
│   ├── input_parser.py       # Input handling
│   ├── output_handler.py     # File output
│   ├── config_utils.py       # Config management
│   └── terminal_display.py   # Terminal formatting
└── test/
    └── test.txt              # Test references
```

## Development

### Adding a New Database Client

1. Create `verifier/new_client.py`:
```python
class NewDatabaseClient:
    def __init__(self):
        self.base_url = "https://api.example.com"
    
    def search(self, title: str, authors: List[str], year: int) -> List[Dict]:
        # Implement search logic
        return results
```

2. Register in `verifier/multi_database_verifier.py`:
```python
self.clients['new_database'] = NewDatabaseClient()
```

3. Add configuration in `config.py`:
```python
ENABLE_NEW_DATABASE = True
```

### Running Tests

```bash
# Test with the test file
python verifyref.py test/test.txt -o test_results.txt

# Test single reference
python verifyref.py --verify "Author, A.: Title. Venue, 2024"
```

## License

VerifyRef is licensed under the GNU General Public License v3 (GPLv3).

Copyright (C) 2025-2026 Hosein Hadipour
