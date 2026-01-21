# VerifyRef Technical Documentation

**Version**: 1.1.0  
**Last Updated**: January 2026  
**Author**: Hosein Hadipour  
**License**: GPL-3.0

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Data Flow](#data-flow)
4. [Database Clients](#database-clients)
5. [Classification System](#classification-system)
6. [AI Verification](#ai-verification)
7. [Configuration](#configuration)
8. [API Reference](#api-reference)

---

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
    |   grobid/client   |        | verifier/multi_db     |        | utils/output    |
    |   (PDF Parsing)   |        | (Database Coordinator)|        | (Report Gen)    |
    +-------------------+        +-----------+-----------+        +-----------------+
                                             |
         +-----------------------------------+-----------------------------------+
         |           |           |           |           |           |           |
    +----v----+ +----v----+ +----v----+ +----v----+ +----v----+ +----v----+ +----v----+
    |OpenAlex | |  DBLP   | | PubMed  | |  IACR   | |  ArXiv  | |CrossRef | | Scholar |
    +---------+ +---------+ +---------+ +---------+ +---------+ +---------+ +---------+
                                             |
                                    +--------v--------+
                                    |   classifier    |
                                    | (Fraud Detect)  |
                                    +--------+--------+
                                             |
                                    +--------v--------+
                                    |   ai_verifier   |
                                    |   (Optional)    |
                                    +-----------------+
```

### Design Principles

1. **Modular Architecture**: Each component has a single responsibility
2. **Parallel Processing**: Multi-threaded database searches for performance
3. **Fail-Safe Operation**: Graceful degradation when services are unavailable
4. **Configurable Sensitivity**: Adjustable thresholds for different use cases
5. **Multi-Provider AI**: Support for free (Gemini, Groq, Ollama) and paid (OpenAI) AI providers

---

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
- `process_single_reference()`: Processes one reference through the pipeline

### 2. PDF Processing (grobid/client.py)

GROBID client for extracting references from PDF documents.

**Features**:
- Connects to GROBID service (default: localhost:8070)
- Extracts structured reference data (title, authors, venue, year, DOI)
- Title post-processing to clean HTML artifacts (e.g., `sup+/sup` to `+`)
- Two-pass parsing: preserves original authors before consolidation for fraud detection

**Key Methods**:
```python
class GrobidClient:
    def extract_references(pdf_path: str) -> List[Dict]
    def parse_citation_string(citation_text: str) -> Dict
    def is_available() -> bool
```

### 3. Reference Parser (extractor/reference_parser.py)

Parses and normalizes reference data from various formats.

**Responsibilities**:
- Text file parsing (one reference per line)
- Single reference string parsing
- Author name normalization
- Year extraction from various formats
- Venue name cleaning

### 4. Multi-Database Verifier (verifier/multi_database_verifier.py)

Coordinates searches across multiple academic databases.

**Features**:
- Parallel database queries with thread pool
- Smart caching to avoid duplicate searches
- Context-aware database prioritization (CS, Bio, General)
- Configurable database enable/disable

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
- Weighted similarity scoring (title: 0.45, author: 0.35, venue: 0.15, year: 0.05)
- Explicit author manipulation detection
- Book reference detection (ISBN, publisher, edition indicators)
- DOI validation for false negative reduction

### 6. AI Verifier (verifier/ai_verifier.py)

Optional AI-powered verification using multiple providers.

**Supported Providers**:

| Provider | Cost | API Key Required | Rate Limits |
|----------|------|------------------|-------------|
| Ollama | Free | No (local) | None |
| Gemini | Free | Yes | 15 req/min |
| Groq | Free | Yes | 30 req/min |
| OpenAI | Paid | Yes | Varies |

**Analysis Includes**:
- Pattern recognition for fake references
- Author collaboration plausibility
- Venue-topic consistency
- Timeline analysis

---

## Data Flow

### Reference Verification Pipeline

```
1. Input Detection
   - PDF: GROBID extraction
   - Text file: Line-by-line parsing
   - Single ref: Direct parsing

2. Reference Parsing
   - Extract: title, authors, venue, year, DOI, URL
   - Normalize: clean text, standardize names
   - Preserve: original data for fraud detection

3. Database Search (Parallel)
   - Query all enabled databases
   - Collect results with source attribution
   - Cache results for duplicate references

4. Classification
   - Find best match by similarity score
   - Check for author manipulation
   - Detect book references
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

**Search Result**:
```python
{
    'title': str,
    'authors': List[str],
    'year': int,
    'venue': str,
    'doi': str,
    'url': str,
    'source': str,  # Database name
    'similarity': float
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
```

---

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

- **Usage**: Only when other databases find poor matches (less than 70% similarity)
- **Rate Limit**: Conservative (20s delay, 10 req/hour)
- **Purpose**: Author manipulation validation

---

## Classification System

### Similarity Calculation

The classifier uses weighted similarity scoring:

```python
similarity = (
    title_similarity * 0.45 +
    author_similarity * 0.35 +
    venue_similarity * 0.15 +
    year_similarity * 0.05
)
```

### Classification Thresholds

| Threshold | Value | Description |
|-----------|-------|-------------|
| Authentic | >= 0.55 | High confidence match |
| Suspicious | 0.25 - 0.55 | Needs review |
| Fabricated | < 0.25 | No credible match |

### Author Manipulation Detection

Triggered when:
- Title similarity > 70%
- Author similarity < 40%
- Best match found in database

This catches cases where someone copies a real paper title but changes the authors.

### Book Reference Detection

References are flagged as potential books when they contain:
- ISBN numbers
- Publisher names (Springer, Wiley, Cambridge, etc.)
- Edition indicators (2nd edition, etc.)
- Book-style titles (Handbook of, Introduction to, etc.)

Books are classified as INCONCLUSIVE rather than FABRICATED since they may not appear in paper databases.

---

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

### AI Analysis Output

The AI verifier returns:

```python
@dataclass
class AIVerificationResult:
    is_authentic: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    red_flags: List[str]
    positive_indicators: List[str]
    metadata: Dict
```

### Integration with Classification

AI results are incorporated with configurable weight:
- Strong database evidence: 20% AI weight
- Weak database evidence: 50% AI weight
- AI cannot override clear database evidence without exceptional confidence (>95%)

---

## Configuration

### config.py Structure

```python
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
    "similarity_threshold": 0.55,
    "suspicious_threshold": 0.25,
    "title_weight": 0.45,
    "author_weight": 0.35,
    "venue_weight": 0.15,
    "year_weight": 0.05,
}

# AI configuration
DATABASE_CONFIG = {
    "ai_verification": {
        "enabled": False,  # Enable with --enable-ai flag
        "provider": "gemini",
        "model": "gemini-2.0-flash",
    }
}
```

### Runtime Configuration

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

---

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
from verifier.multi_database_verifier import MultiDatabaseVerifier
from verifier.classifier import ReferenceClassifier
from grobid.client import GrobidClient

# Extract references from PDF
grobid = GrobidClient()
references = grobid.extract_references("paper.pdf")

# Search databases
verifier = MultiDatabaseVerifier()
for ref in references:
    results = verifier.search_across_databases(ref)
    
    # Classify
    classifier = ReferenceClassifier()
    classification = classifier.classify_reference(ref, results)
    
    print(f"{ref['title']}: {classification.classification}")
```

---

## File Structure

```
verifyref/
├── verifyref.py              # CLI entry point
├── config.py                 # Configuration
├── grobid/
│   └── client.py             # GROBID PDF processing
├── extractor/
│   └── reference_parser.py   # Reference parsing
├── verifier/
│   ├── multi_database_verifier.py
│   ├── classifier.py         # Classification logic
│   ├── ai_verifier.py        # AI verification
│   ├── openalex_client.py
│   ├── dblp_client.py
│   ├── pubmed_client.py
│   ├── iacr_client.py
│   ├── arxiv_client.py
│   ├── semantic_scholar.py
│   ├── crossref_client.py
│   ├── google_scholar_client.py
│   ├── springer_client.py
│   └── doi_validation_client.py
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

---

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

---

## License

VerifyRef is licensed under the GNU General Public License v3 (GPLv3).

Copyright (C) 2025-2026 Hosein Hadipour
