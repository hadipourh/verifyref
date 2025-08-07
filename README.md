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

- **Multi-Database Verification**: Cross-references across 7+ academic databases
- **PDF Processing**: Extracts and parses references from academic PDFs using GROBID
- **AI-Powered Analysis**: Optional GPT-based fraud detection and pattern recognition
- **Context-Aware Search**: Optimized database selection for different research domains
- **5-Category Classification**: Comprehensive authenticity assessment system
- **Parallel Processing**: Efficient verification with automatic performance optimization
- **Flexible Output**: JSON and text format support with detailed reporting

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

# Configure API keys and email
# Edit config.py: Set CROSSREF_EMAIL and optional API keys

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

VerifyRef uses a 5-category system to evaluate reference authenticity:

| Category | Criteria | Action |
|----------|----------|---------|
| **AUTHENTIC** 🟢 | High similarity (>threshold), multiple DB matches | Accept reference |
| **SUSPICIOUS** 🟡 | Moderate similarity (20-45%), few matches | Manual review |
| **FABRICATED** 🔴 | Very low similarity (<20%), no matches | Investigate |
| **AUTHOR_MANIPULATION** 🔴 | High title similarity but low author match | Flag misconduct |
| **INCONCLUSIVE** ⚪ | Parsing errors, network issues | Re-verify |

**Confidence Levels**: 90-100% (very high), 70-89% (high), 50-69% (moderate), 30-49% (low), <30% (very low)

## Database Integration

**Primary**: OpenAlex (comprehensive coverage, no rate limits)  
**Specialized**: DBLP (CS), PubMed (Bio), IACR (Crypto), ArXiv (Preprints), Springer Nature (STM), Semantic Scholar, CrossRef

**Context-Aware Prioritization**:
- **CS**: OpenAlex → DBLP → IACR → ArXiv → Semantic Scholar
- **Bio**: OpenAlex → PubMed → Semantic Scholar → ArXiv  
- **General**: OpenAlex → Semantic Scholar → DBLP → ArXiv → PubMed

## Configuration

**Setup**: Edit API keys and email in `config.py`

1. Open `config.py` in your editor
2. **Required**: Set `CROSSREF_EMAIL` to your email address
3. **Optional**: Add API keys for enhanced features:
   - `SEMANTIC_SCHOLAR_API_KEY` - Higher rate limits (recommended)
   - `OPENAI_API_KEY` - AI-powered fraud detection
   - `NCBI_API_KEY` - Higher PubMed rate limits
   - `SPRINGER_API_KEY` - Access to Springer Nature database

```python
# In config.py - Edit these values:
CROSSREF_EMAIL = "your.email@domain.com"  # ← REQUIRED
SEMANTIC_SCHOLAR_API_KEY = "your-key-here"  # ← Optional
OPENAI_API_KEY = "your-key-here"  # ← Optional
NCBI_API_KEY = "your-key-here"  # ← Optional
SPRINGER_API_KEY = "your-key-here"  # ← Optional
```

#### API Key Setup Guide

**Free Databases (No API Key Required):**
- OpenAlex, DBLP, IACR, ArXiv - Work out of the box

**Enhanced with API Keys (Optional):**
- **Semantic Scholar API Key**: [Get it here](https://www.semanticscholar.org/product/api#api-key-form) - Higher rate limits
- **NCBI/PubMed API Key**: [Get it here](https://www.ncbi.nlm.nih.gov/account/settings/) - Higher rate limits

**API Key Required:**
- **OpenAI API Key**: [Get it here](https://platform.openai.com/api-keys) - For AI fraud detection
- **Springer Nature API Key**: [Get it here](https://dev.springernature.com/) - Required for all access (free signup)

### AI-Powered Verification

Optional GPT-based analysis for enhanced fraud detection.

1. Set `OPENAI_API_KEY` in `config.py`
2. Enable with `--enable-ai` flag:

```bash
python verifyref.py paper.pdf --enable-ai
```

**Model**: `gpt-4o-mini` (default) - Cost-effective with structured output support  
**Analysis**: Pattern recognition, author collaboration, timeline validation, venue relationships

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
