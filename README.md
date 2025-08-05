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
                 📊 Verification Summary
╭──────────────────────────┬───────┬────────────┬────────╮
│ Classification           │ Count │ Percentage │ Status │
├──────────────────────────┼───────┼────────────┼────────┤
│ ✅ AUTHENTIC             │     9 │      50.0% │   ●    │
│ 🔍 SUSPICIOUS            │     8 │      44.4% │   ●    │
│ ❌ FAKE                  │     0 │       0.0% │   ○    │
│ 🔄 AUTHOR MANIPULATION   │     0 │       0.0% │   ○    │
│ 🚫 FABRICATED            │     1 │       5.6% │   ●    │
│ ❓ INCONCLUSIVE          │     0 │       0.0% │   ○    │
╰──────────────────────────┴───────┴────────────┴────────╯
🔴 HIGH - Notable fraud or suspicious references detected
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
git clone https://github.com/user/verifyref.git
cd verifyref
docker build -t verifyref .

# Interactive mode with workspace mounting (GROBID starts automatically)
docker run -it --rm -v "$(pwd):/app/workspace" verifyref

# Once inside the container, GROBID is already running:
cd /app/workspace/

# Verify the references in a PDF
verifyref paper.pdf -o results.txt

# For citation search only
verifyref --cite "Autoguess A Tool for Finding Guess-and-Determine Attacks"
```

### Manual Installation

```bash
# Clone and install
git clone https://github.com/user/verifyref.git
cd verifyref

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: Set CROSSREF_EMAIL=your.email@domain.com

# Start GROBID (for PDF processing)
docker run -d -p 8070:8070 lfoppiano/grobid:0.8.2

# Verify PDF references 
python verifyref.py paper.pdf --output results.txt

# Search for citations
python verifyref.py --cite "Revisiting Differential-Linear Attacks via a Boomerang Perspective"
```

### Advanced Options

```bash
# Verification rigor levels
python verifyref.py paper.pdf --rigor strict    # High precision
python verifyref.py paper.pdf --rigor balanced  # Default
python verifyref.py paper.pdf --rigor lenient   # High recall

# Context-aware search
python verifyref.py --cite "Finding the Impossible Impossible-Differential Attack" --context cs
python verifyref.py --cite "gene therapy" --context bio

# AI-enhanced verification
python verifyref.py paper.pdf --enable-ai # do not forget to set OPENAI_API_KEY in .env

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
**Specialized**: DBLP (CS), PubMed (Bio), IACR (Crypto), ArXiv (Preprints), Semantic Scholar, CrossRef

**Context-Aware Prioritization**:
- **CS**: OpenAlex → DBLP → IACR → ArXiv → Semantic Scholar
- **Bio**: OpenAlex → PubMed → Semantic Scholar → ArXiv  
- **General**: OpenAlex → Semantic Scholar → DBLP → ArXiv → PubMed

## Configuration

**Required**: Email for CrossRef API access
```bash
cp .env.example .env
# Edit .env: CROSSREF_EMAIL=your.email@domain.com
```

**Optional API Keys**: OPENAI_API_KEY (AI verification), SEMANTIC_SCHOLAR_API_KEY (higher limits), NCBI_API_KEY (PubMed access)

## AI-Powered Verification

Optional GPT-based analysis for enhanced fraud detection.

```bash
# Set API key and enable
export OPENAI_API_KEY="your-key"
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
- Port 8070 in use → `docker stop $(docker ps -q --filter "publish=8070")`

**Performance**: Automatic parallel processing (4 workers), smart caching, context-aware database selection

**Debug**: Use `python verifyref.py paper.pdf --verbose` for detailed logging

## Project Structure

```
verifyref/
├── verifyref.py                 # Main CLI tool
├── config.py                    # Configuration
├── requirements.txt             # Dependencies
├── Dockerfile                   # Container setup
├── .env.example                 # Environment template
├── grobid/
│   └── client.py               # PDF extraction
├── extractor/
│   └── reference_parser.py     # Reference parsing
├── verifier/
│   ├── multi_database_verifier.py  # Main coordinator
│   ├── openalex_client.py          # Primary database
│   ├── dblp_client.py              # Computer Science
│   ├── pubmed_client.py            # Biomedical
│   ├── iacr_client.py              # Cryptography
│   ├── arxiv_client.py             # Preprints
│   ├── semantic_scholar.py         # Academic search
│   ├── crossref_client.py          # DOI resolution
│   ├── classifier.py               # Authenticity classification
│   ├── ai_verifier.py              # AI-powered analysis
│   └── cryptodb_author_client.py   # CryptoDB verification
├── utils/
│   ├── helpers.py              # Common utilities
│   ├── academic_matching.py    # Venue/author matching
│   └── report_generator.py     # Output formatting
└── tests/
    ├── test_verifier.py        # Verification tests
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
git clone https://github.com/user/verifyref.git && cd verifyref
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pytest tests/
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

**For technical documentation and API details, see the [verifier/](verifier/) directory.**
