# VerifyRef

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](https://github.com/user/verifyref/releases)

A comprehensive tool for verifying the authenticity of academic references in PDF documents using multiple academic databases and AI-powered analysis, with parallel processing optimization.

## Why VerifyRef?

While reviewing a journal submission, I found a reference that shocked me. It listed my brother, a businessman with no link to cryptography, as a co-author of a paper on symmetric-key cryptanalysis with a well-known researcher. 
My brother, who doesn’t even know what "cryptanalysis" means, had nothing to do with this. 
This triggered me to inspect that reference and other references in the paper that turned out to be partially AI-generated with multiple fake references.


Manually checking dozens of references was time-consuming, so I created VerifyRef to automatically extract and verify references against trusted academic databases using both automated queries and AI-powered analysis. 
Here is the summary of the output of the tool for that paper: 

```sh
                 [*] Verification Summary
╭──────────────────────────┬───────┬────────────┬────────╮
│ Classification           │ Count │ Percentage │ Status │
├──────────────────────────┼───────┼────────────┼────────┤
│ [+] AUTHENTIC            │     6 │      33.3% │   ●    │
│ [?] SUSPICIOUS           │     8 │      44.4% │   ●    │
│ [X] FAKE                 │     0 │       0.0% │   ○    │
│ [~] AUTHOR MANIPULATION  │     0 │       0.0% │   ○    │
│ [-] FABRICATED           │     4 │      22.2% │   ●    │
│ [!] INCONCLUSIVE         │     0 │       0.0% │   ○    │
╰──────────────────────────┴───────┴────────────┴────────╯

🚨 CRITICAL - Significant fraud detected (author manipulation or fabrication)
```

I called this tool VerifyRef and decided to publish it to help other researchers. 
This tool helps reviewers quickly identify potentially fabricated references and AI-generated content, making the peer review process more efficient and reliable. 
**Note that VerifyRef is not a replacement for human judgment but a powerful assistant to streamline the verification process.**

- [VerifyRef](#verifyref)
  - [Why VerifyRef?](#why-verifyref)
  - [Features](#features)
  - [Installation and Quick Start](#installation-and-quick-start)
    - [Docker (Recommended)](#docker-recommended)
    - [Manual Installation](#manual-installation)
    - [Advanced Options](#advanced-options)
  - [Classification System](#classification-system)
  - [Database Integration](#database-integration)
  - [Configuration](#configuration)
    - [AI-Powered Verification](#ai-powered-verification)
  - [Usage Scenarios](#usage-scenarios)
  - [Troubleshooting](#troubleshooting)
  - [Project Structure](#project-structure)
  - [Ethical Usage](#ethical-usage)
  - [Contributing](#contributing)
  - [License](#license)
  - [Caution](#caution)
  - [Acknowledgments](#acknowledgments)


## Features

- **Multi-Database Verification**: Cross-references across 8+ academic databases including Google Scholar
- **PDF Processing**: Extracts and parses references from academic PDFs using GROBID
- **Smart Decision Logic**: Intelligent AI-database consensus system that reduces false positives/negatives
- **Google Scholar Smart Fallback**: Advanced fallback strategy used only when other databases find poor matches (<0.7 similarity)
- **Google Scholar Author Validation**: Secondary validation layer to distinguish legitimate papers from manipulation
- **Google Scholar Fabrication Detection**: Advanced validation to detect fabricated references using comprehensive search
- **AI-Powered Analysis**: Optional GPT-based fraud detection and pattern recognition
- **Enhanced DOI Validation & Fraud Prevention**: Comprehensive metadata matching to verify DOI authenticity and prevent fraudulent DOI usage
- **Enhanced Fraud Detection**: Advanced author manipulation detection with multi-layered validation
- **Stricter Classification Thresholds**: Conservative similarity requirements (0.55) and suspicious thresholds (0.25) for improved accuracy
- **Major Database Requirements**: Enhanced validation requiring evidence from authoritative academic databases
- **Context-Aware Search**: Optimized database selection for different research domains
- **5-Category Classification**: Comprehensive authenticity assessment system
- **Parallel Processing**: Efficient verification with automatic performance optimization
- **Flexible Output**: JSON and text format support with detailed reporting
- **Comprehensive Test Suite**: Automated testing with authentic and fabricated reference examples

## Installation and Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/hadipourh/verifyref.git
cd verifyref
docker build -t verifyref .

# Interactive mode with workspace mounting (GROBID starts automatically)
docker run -it --rm -v "$(pwd):/app/workspace" verifyref

# Once inside the container, GROBID is already running:
cd /app/workspace/

# For citation search only
verifyref --cite "Autoguess A Tool for Finding Guess-and-Determine Attacks"

# Verify the references in a PDF
verifyref paper.pdf -o results.txt
```

### Manual Installation

```bash
# Clone and install
git clone https://github.com/hadipourh/verifyref.git
cd verifyref

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure your environment
cp .env.example .env
# Edit .env: Set CROSSREF_EMAIL and optionally OPENAI_API_KEY

# Start GROBID (for PDF processing)
docker run -d -p 8070:8070 lfoppiano/grobid:0.8.2

# Search for citations
python verifyref.py --cite "Revisiting Differential-Linear Attacks via a Boomerang Perspective"

# Verify PDF references 
python verifyref.py paper.pdf --output results.txt
```

### Advanced Options

```bash
# Verification rigor levels
python verifyref.py paper.pdf --rigor strict -o refrevire.txt   # High precision
python verifyref.py paper.pdf --rigor balanced -o refrevire.txt # Default
python verifyref.py paper.pdf --rigor lenient -o refrevire.txt  # High recall

# Context-aware search
python verifyref.py --cite "Finding the Impossible Impossible-Differential Attack" --context cs
python verifyref.py --cite "gene therapy" --context bio

# AI-enhanced verification
python verifyref.py paper.pdf --enable-ai # requires OPENAI_API_KEY in config.py

# Custom similarity threshold
python verifyref.py paper.pdf --similarity-threshold 0.8
```

## Classification System

VerifyRef uses a 5-category system with enhanced accuracy thresholds to evaluate reference authenticity:

| Category | Criteria | Action |
|----------|----------|---------|
| **AUTHENTIC** 🟢 | High similarity (>55%), multiple DB matches, major database evidence | Accept reference |
| **SUSPICIOUS** 🟡 | Moderate similarity (25-55%), limited evidence, needs verification | Manual review |
| **FABRICATED** 🔴 | Very low similarity (<25%), no matches in major databases | Investigate |
| **AUTHOR_MANIPULATION** 🔴 | High title similarity but low author match (validated by Google Scholar) | Flag misconduct |
| **INCONCLUSIVE** ⚪ | Parsing errors, network issues | Re-verify |

**Enhanced Accuracy Features**:
- **Stricter Thresholds**: Similarity threshold increased from 45% to 55% for more conservative classification
- **Major Database Requirements**: Papers must be found in authoritative databases (OpenAlex, DBLP, PubMed, etc.)
- **Enhanced DOI Validation**: DOI resolution + metadata verification to prevent fraud and reduce false negatives
- **Google Scholar Fabrication Detection**: Advanced validation for suspected fabricated references
- **Conservative AI Override**: AI requires exceptional evidence (>90% confidence) to override database findings

**Confidence Levels**: 90-100% (very high), 70-89% (high), 50-69% (moderate), 30-49% (low), <30% (very low)

## Database Integration

**Primary**: OpenAlex (comprehensive coverage, no rate limits)  
**Specialized**: DBLP (CS), PubMed (Bio), IACR (Crypto), ArXiv (Preprints), Springer Nature (STM), Semantic Scholar, CrossRef  
**Smart Fallback**: Google Scholar (used only when other databases find similarity < 0.7)  
**Enhanced DOI Validation**: Comprehensive metadata matching via doi.org to prevent DOI fraud

**Major Database Authority**:
VerifyRef now prioritizes evidence from major academic databases (OpenAlex, Semantic Scholar, DBLP, PubMed, ArXiv, IACR) and requires stronger evidence for authentic classification when papers are not found in these authoritative sources.

**Context-Aware Prioritization**:
- **CS**: OpenAlex → DBLP → IACR → ArXiv → Semantic Scholar → Google Scholar*
- **Bio**: OpenAlex → PubMed → Semantic Scholar → ArXiv → Google Scholar*  
- **General**: OpenAlex → Semantic Scholar → DBLP → ArXiv → PubMed → Google Scholar*

**Enhanced Validation Features**:
- **Google Scholar Fabrication Detection**: Triggered when no major databases find matches and similarity < 0.5
- **Enhanced DOI Validation**: DOIs are resolved via doi.org AND metadata (title, authors, year) is verified against claimed details to prevent fraud
- **DOI Fraud Prevention**: Papers with valid but mismatched DOI metadata receive confidence penalties instead of boosts
- **Conservative Thresholds**: Borderline cases (55-70% similarity) without major database evidence are classified as suspicious
- **Multi-Source Requirements**: Moderate similarity papers require evidence from multiple databases or major database confirmation

*Google Scholar is triggered only when other databases find poor matches (< 0.7 similarity) and at least 3 databases have been searched, dramatically reducing API usage while maximizing value.

## Configuration

**Setup**: Edit configuration in `config.py`

1. Open `config.py` in your editor
2. **Database Enable/Disable**: Use the convenient enable flags at the top:
   - `ENABLE_CROSSREF = True` - Enable CrossRef database searches
   - `ENABLE_GOOGLE_SCHOLAR = True` - Enable Google Scholar with smart fallback
3. **Required**: Set `CROSSREF_EMAIL` to your email address
4. **Optional**: Add API keys for enhanced features:
   - `SEMANTIC_SCHOLAR_API_KEY` - Higher rate limits (recommended)
   - `OPENAI_API_KEY` - AI-powered fraud detection
   - `NCBI_API_KEY` - Higher PubMed rate limits
   - `SPRINGER_API_KEY` - Access to Springer Nature database

```python
# In config.py - Easy-to-find configuration at the top:

# Database Configuration (Enable/Disable specific databases)
ENABLE_CROSSREF = True  # ← Set to True to enable CrossRef database searches
ENABLE_GOOGLE_SCHOLAR = True  # ← Set to True to enable Google Scholar searches (free but rate-limited)

# Required for CrossRef
CROSSREF_EMAIL = "your.email@domain.com"  # ← REQUIRED

# Optional API keys for enhanced features
SEMANTIC_SCHOLAR_API_KEY = "your-key-here"  # ← Optional
OPENAI_API_KEY = "your-key-here"  # ← Optional
NCBI_API_KEY = "your-key-here"  # ← Optional
SPRINGER_API_KEY = "your-key-here"  # ← Optional
```

#### API Key Setup Guide

**Free Databases (No API Key Required):**
- OpenAlex, DBLP, IACR, ArXiv - Work out of the box
- Google Scholar - Free but rate-limited with smart fallback strategy (maybe use serpapi?)

**Enhanced with API Keys (Optional):**
- **Semantic Scholar API Key**: [Get it here](https://www.semanticscholar.org/product/api#api-key-form) - Higher rate limits
- **NCBI/PubMed API Key**: [Get it here](https://www.ncbi.nlm.nih.gov/account/settings/) - Higher rate limits

**API Key Required:**
- **OpenAI API Key**: [Get it here](https://platform.openai.com/api-keys) - For AI fraud detection
- **Springer Nature API Key**: [Get it here](https://dev.springernature.com/) - Required for all access (free signup)

### Google Scholar Smart Fallback

VerifyRef includes Google Scholar with an intelligent fallback strategy that dramatically reduces API usage while maximizing value, plus enhanced author manipulation validation.

**How It Works:**
1. **Primary Search**: 7 other databases search first (OpenAlex, DBLP, etc.)
2. **Smart Decision**: Google Scholar only searches if:
   - Best similarity from other databases < 0.7 (poor matches)
   - At least 3 databases have been searched
   - Google Scholar is enabled
3. **Author Validation**: When author manipulation is detected, Google Scholar validates whether it's legitimate different papers or actual fraud
4. **Conservative Usage**: 20-second delays, 10 requests/hour limit

**Benefits:**
- **~90% Reduction** in Google Scholar API usage
- **Maximum Value** - only searches when really needed
- **Enhanced Accuracy** - validates author manipulation to prevent false positives
- **Rate Limit Safe** - prevents blocking with conservative limits
- **Academic Compliant** - respectful behavior and user agents

**Author Manipulation Validation:**
```python
# Google Scholar distinguishes between:
# 1. Legitimate different papers with similar titles → Override detection
# 2. Actual author manipulation fraud → Confirm detection
# 3. Inconclusive evidence → Proceed with original analysis

validation_result = {
    "validated": True/False/None,
    "conclusion": "legitimate_different_papers" | "confirmed_author_manipulation",
    "evidence": "Detailed reasoning for decision"
}
```

**Configuration:**
```python
# Easy control in config.py
ENABLE_GOOGLE_SCHOLAR = True  # Enable/disable with one flag

# Advanced settings (usually no need to change)
"fallback_threshold": 0.7,     # Only search if other DBs find < 0.7 similarity
"min_databases_searched": 3,   # Must search at least 3 other DBs first
"rate_limit_delay": 20.0,      # Conservative 20-second delays
```

### AI-Powered Verification

Enhanced AI analysis system with strengthened safety controls and conservative decision-making to prevent over-optimistic classifications.

**Key Features:**
- **Strengthened AI Override Controls**: AI confidence gap requirement increased to 0.5 (from 0.3)
- **Enhanced Safety Checks**: Multiple safety validations prevent AI over-optimism
- **Conservative Evidence Requirements**: AI requires 90%+ confidence and exceptional evidence to override database findings
- **Major Database Validation**: AI cannot claim authentic without evidence from major academic databases
- **Enhanced Fraud Detection**: AI fraud detection is enhanced when database evidence is weak
- **Multi-Indicator Requirements**: High-confidence AI claims require 4+ positive indicators (increased from 3)

**Configuration** (in `config.py`):
```python
# Enhanced AI Safety Controls
AI_OVERRIDE_FABRICATED_THRESHOLD = 0.95    # Increased from 0.85 - very high bar for overriding fabricated classification
AI_MIN_CONFIDENCE_GAP = 0.5                # Increased from 0.3 - larger gap required between AI and database confidence
AI_MIN_POSITIVE_INDICATORS_HIGH_CONF = 4   # Increased from 3 - more evidence required for high-confidence claims

# Conservative Database-Dependent AI Weights
AI_WEIGHT_WITH_STRONG_DB = 0.2      # 20% AI influence with strong database evidence
AI_WEIGHT_WITH_MODERATE_DB = 0.3    # 30% AI influence with moderate database evidence  
AI_WEIGHT_WITH_WEAK_DB = 0.4        # 40% AI influence with weak database evidence
AI_WEIGHT_WITH_VERY_WEAK_DB = 0.5   # 50% max AI influence with very weak database evidence
```

**Usage:**
```bash
python verifyref.py paper.pdf --enable-ai
```

**Analysis Includes**: Pattern recognition, author collaboration validation, timeline analysis, venue relationship verification, DOI consistency checking

**Safety Features**: 
- AI cannot claim authentic while having any red flags
- Requires exceptional evidence (>95%) to override fabricated classification
- Multiple positive indicators required for high-confidence claims
- Major database evidence required for authentic classification
- Conservative confidence gap requirements prevent over-optimistic decisions

## Testing Framework

VerifyRef includes a comprehensive testing framework to validate accuracy improvements and ensure robust fraud detection:

**Test Suite**: Located in `test/test.txt` with curated examples including:
- **Authentic References**: Classic cryptography papers from reputable venues
- **Fabricated References**: Known fake papers for validation testing  
- **Author Manipulation Cases**: References with corrupted author names
- **Edge Cases**: Partial information, venue fraud, impossible references

**Accuracy Validation**:
```bash
# Test the enhanced system with the comprehensive test suite
python verifyref.py --verify test/test.txt --enable-ai --output test_results.txt

# Test with specific fabricated examples
python verifyref.py --verify "Catching the boomerangs: a new method to improve finding boomerang attacks. In Computer Science and Social Engineering, pages 13–22. Springer, 2018." --enable-ai
```

**Expected Improvements**:
- Fabricated references correctly classified as SUSPICIOUS (26.1%) instead of AUTHENTIC (72.1%)
- Enhanced detection of author manipulation and venue fraud
- Reduced false positives through stricter classification thresholds
- Better handling of borderline cases with conservative evidence requirements

## Usage Scenarios

```bash
# Academic integrity investigation
python verifyref.py paper.pdf --rigor strict --require-multi-db --enable-ai --output review_report.txt

# Standard peer review
python verifyref.py paper.pdf --rigor balanced --output review_report.txt

# Biomedical literature
python verifyref.py paper.pdf --context bio --rigor balanced

# Batch processing
for pdf in papers/*.pdf; do
  python verifyref.py "$pdf" --output "${pdf%.pdf}_results.json"
done
```

## Troubleshooting

**Common Issues**:
- No references found → Check PDF quality, ensure GROBID running
- High INCONCLUSIVE rate → Use `--rigor lenient` for specialized papers  
- Too many false positives → Try `--rigor lenient`
- Database timeouts → Check internet connection
- GROBID not responding → Restart: `curl http://localhost:8070/api/isalive`
- Port 8070 in use → `docker stop $(docker ps -q --filter "publish=8070")` and again run `docker run -d -p 8070:8070 lfoppiano/grobid:0.8.2`. 

**Performance**: Automatic parallel processing (4 workers), smart caching, context-aware database selection

**Debug**: Use `python verifyref.py paper.pdf --verbose` for detailed logging

## Project Structure

```
verifyref/
├── verifyref.py                 # Main CLI entry point (~1,119 lines)
├── config.py                    # Configuration (edit API keys here)
├── requirements.txt             # Dependencies
├── Dockerfile                   # Container setup
├── grobid/
│   └── client.py               # PDF extraction and GROBID integration
├── extractor/
│   └── reference_parser.py     # Reference parsing and normalization
├── verifier/
│   ├── multi_database_verifier.py  # Main verification coordinator
│   ├── openalex_client.py          # Primary academic database
│   ├── dblp_client.py              # Computer Science literature
│   ├── pubmed_client.py            # Biomedical literature
│   ├── iacr_client.py              # Cryptography research
│   ├── arxiv_client.py             # Preprint repository
│   ├── springer_client.py          # Springer Nature STM
│   ├── semantic_scholar.py         # Academic search engine
│   ├── crossref_client.py          # DOI resolution service
│   ├── classifier.py               # Authenticity classification
│   ├── ai_verifier.py              # AI-powered fraud detection
│   └── cryptodb_author_client.py   # CryptoDB author verification
├── utils/
│   ├── helpers.py              # Common utilities and helpers
│   ├── academic_matching.py    # Venue and author matching algorithms
│   ├── report_generator.py     # Output formatting and report generation
│   ├── input_parser.py         # Input type detection and parsing
│   ├── output_handler.py       # File output and format handling
│   ├── config_utils.py         # Configuration management utilities
│   └── terminal_display.py     # Rich-based terminal output formatting
└── tests/
    ├── test_verifier.py        # Verification system tests
    └── test_grobid.py          # PDF processing tests
```

## Ethical Usage

VerifyRef follows strict ethical guidelines:

- **API-Only Access**: No web scraping, only official APIs
- **Rate Limiting**: Respects all service rate limits  
- **Privacy**: No personal data collection or storage
- **Transparency**: All API calls logged and visible
- **Attribution**: Proper User-Agent and contact information

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, guidelines, and testing requirements.

```bash
git clone https://github.com/hadipourh/verifyref.git && cd verifyref
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pytest tests/
# Edit config.py to set your API keys
```

## License

This project is licensed under the GNU General Public License v3 (GPLv3) - see the [LICENSE](LICENSE) file for details.

Copyright (C) 2025 Hosein Hadipour <hsn.hadipour@gmail.com>

## Caution

VerifyRef is designed to assist in the verification of academic references and **should not** be used as a sole determinant of reference authenticity. It is intended to complement human judgment and expertise in the peer review process.

## Acknowledgments

- **GROBID Project**: PDF parsing capabilities
- **Database Providers**: OpenAlex, DBLP, PubMed, IACR, ArXiv, Semantic Scholar
- **Academic Community**: Feedback and testing from researchers worldwide

---

## Documentation

- **User Guide**: This README covers installation, usage, and configuration
- **Technical Documentation**: See [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) for detailed architecture, API reference, and development guide
- **Source Code**: Explore the [verifier/](verifier/) directory for implementation details
