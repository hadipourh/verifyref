# VerifyRef

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A tool for verifying the authenticity of academic references in PDF documents using multiple academic databases and optional AI-powered analysis.

## Why VerifyRef?

While reviewing a journal submission, I found a reference that listed my brother, a businessman with no connection to cryptography, as a co-author of a paper on symmetric-key cryptanalysis with a well-known researcher. My brother had nothing to do with this paper. This triggered me to inspect that reference and others in the paper, which turned out to be partially AI-generated with multiple fake references.

Manually checking dozens of references was time-consuming, so I created VerifyRef to automatically extract and verify references against trusted academic databases. Here is the summary of the output for that paper:

```
                   Verification Summary
+---------------------------+-------+------------+--------+
| Classification            | Count | Percentage | Status |
+---------------------------+-------+------------+--------+
| [+] AUTHENTIC             |     6 |      33.3% |   *    |
| [?] SUSPICIOUS            |     8 |      44.4% |   *    |
| [X] FAKE                  |     0 |       0.0% |   -    |
| [~] AUTHOR MANIPULATION   |     0 |       0.0% |   -    |
| [-] FABRICATED            |     4 |      22.2% |   *    |
| [!] INCONCLUSIVE          |     0 |       0.0% |   -    |
+---------------------------+-------+------------+--------+

[HIGH RISK] Significant fraud detected
```

This tool helps reviewers quickly identify potentially fabricated references and AI-generated content, making the peer review process more efficient. Note that VerifyRef is not a replacement for human judgment but a powerful assistant to streamline the verification process.

## Features

- Multi-database verification across 8+ academic databases
- PDF processing using GROBID (works out of the box with public server)
- Retraction detection via CrossRef and Retraction Watch
- Author manipulation detection (real titles with fake authors)
- Optional AI verification using free (Gemini, Groq, Ollama) or paid (OpenAI) providers
- Book reference handling for textbooks that may not appear in paper databases
- Parallel processing with multi-threaded database queries
- JSON and text output formats

## Installation

### Quick Start (No Docker Required)

```bash
git clone https://github.com/hadipourh/verifyref.git
cd verifyref
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run verification (uses public GROBID server automatically)
python verifyref.py paper.pdf -o results.txt
```

### Docker Installation

```bash
git clone https://github.com/hadipourh/verifyref.git
cd verifyref
docker build -t verifyref .

# Interactive mode
docker run -it --rm -v "$(pwd):/app/workspace" verifyref

# Inside the container:
cd /app/workspace/
verifyref paper.pdf -o results.txt
```

### Local GROBID (Optional)

For faster processing or privacy, run GROBID locally:

```bash
docker run -d -p 8070:8070 lfoppiano/grobid:0.8.2
export GROBID_URL="http://localhost:8070"
python verifyref.py paper.pdf
```

VerifyRef automatically detects and uses local GROBID when available.

## Usage

### Basic Usage

```bash
# Verify references in a PDF
python verifyref.py paper.pdf -o results.txt

# Search for a specific citation
python verifyref.py --cite "Differential Cryptanalysis of DES"

# Verify a single reference
python verifyref.py --verify "Author, A.: Title. Venue, 2024"
```

### Advanced Options

```bash
# Verification rigor levels
python verifyref.py paper.pdf --rigor strict    # High precision
python verifyref.py paper.pdf --rigor balanced  # Default
python verifyref.py paper.pdf --rigor lenient   # High recall

# Context-aware search
python verifyref.py --cite "cryptanalysis" --context cs
python verifyref.py --cite "gene therapy" --context bio

# AI-enhanced verification
python verifyref.py paper.pdf --enable-ai

# Verbose output
python verifyref.py paper.pdf --verbose
```

### AI Verification Setup

VerifyRef supports multiple AI providers. Ollama is recommended for unlimited free usage:

```bash
# Option 1: Ollama (free, local, no rate limits)
brew install ollama
ollama serve
ollama pull llama3.2
export AI_PROVIDER="ollama"
python verifyref.py paper.pdf --enable-ai

# Option 2: Google Gemini (free tier)
export AI_PROVIDER="gemini"
export GOOGLE_GEMINI_API_KEY="your-key"
python verifyref.py paper.pdf --enable-ai

# Option 3: Groq (free tier)
export AI_PROVIDER="groq"
export GROQ_API_KEY="your-key"
python verifyref.py paper.pdf --enable-ai
```

## Classification System

VerifyRef uses a 5-category system to evaluate reference authenticity:

| Category            | Criteria                                          | Action          |
| ------------------- | ------------------------------------------------- | --------------- |
| AUTHENTIC           | High similarity (>55%), multiple database matches | Accept          |
| SUSPICIOUS          | Moderate similarity (25-55%), limited evidence    | Manual review   |
| FABRICATED          | Very low similarity (<25%), no database matches   | Investigate     |
| AUTHOR_MANIPULATION | Title matches but authors differ significantly    | Flag misconduct |
| INCONCLUSIVE        | Parsing errors, books, or network issues          | Re-verify       |

Retracted papers are flagged with a warning regardless of classification.

## Database Integration

**Primary Databases** (no API key required):

- OpenAlex - Comprehensive coverage (200M+ works)
- DBLP - Computer Science
- IACR - Cryptography
- ArXiv - Preprints
- CrossRef - DOI metadata and retraction status

**Enhanced with API Keys** (optional):

- Semantic Scholar - Higher rate limits
- PubMed - Biomedical (NCBI key)
- Springer Nature - STM publications

**Smart Fallback**:

- Google Scholar - Used only when other databases find poor matches (<70% similarity)

## Configuration

Edit `config.py` to configure:

```python
# Required
CROSSREF_EMAIL = "your.email@domain.com"

# Optional API keys
SEMANTIC_SCHOLAR_API_KEY = ""
NCBI_API_KEY = ""
SPRINGER_API_KEY = ""

# AI providers (for --enable-ai)
GOOGLE_GEMINI_API_KEY = ""
GROQ_API_KEY = ""
OPENAI_API_KEY = ""

# Database toggles
ENABLE_CROSSREF = True
ENABLE_GOOGLE_SCHOLAR = True
```

### GROBID Configuration

VerifyRef uses a smart fallback chain for PDF processing:

1. Public GROBID server (default, no setup required)
2. Local GROBID (if running on localhost:8070)
3. PyMuPDF fallback (lower accuracy, used when GROBID unavailable)

Override the default GROBID URL:

```bash
export GROBID_URL="http://localhost:8070"
```

## Project Structure

```
verifyref/
├── verifyref.py              # CLI entry point
├── config.py                 # Configuration
├── grobid/
│   ├── client.py             # GROBID client with smart fallback
│   └── fallback_parser.py    # PyMuPDF fallback parser
├── extractor/
│   └── reference_parser.py   # Reference parsing
├── verifier/
│   ├── multi_database_verifier.py
│   ├── classifier.py         # Classification logic
│   ├── ai_verifier.py        # AI verification
│   ├── doi_validation_client.py  # DOI and retraction checking
│   └── *_client.py           # Database clients
└── utils/
    ├── helpers.py
    ├── report_generator.py
    └── ...
```

## Troubleshooting

| Issue                  | Solution                                         |
| ---------------------- | ------------------------------------------------ |
| No references found    | Check PDF quality; try a different PDF           |
| GROBID timeout         | Public server may be busy; try local GROBID      |
| High INCONCLUSIVE rate | Use `--rigor lenient`                            |
| AI rate limits         | Use Ollama (no limits) or wait for cooldown      |

## Ethical Usage

VerifyRef follows strict ethical guidelines:

- API-only access (no web scraping)
- Respects all service rate limits
- No personal data collection
- Proper attribution in requests

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

GNU General Public License v3 (GPLv3)

Copyright (C) 2025-2026 Hosein Hadipour

## Documentation

- [Technical Documentation](TECHNICAL_DOCUMENTATION.md) - Architecture and API reference
- [Ethical Guidelines](ETHICAL_GUIDELINES.md) - Usage policies
- [Contributing](CONTRIBUTING.md) - Development guidelines

## Caution

VerifyRef is designed to assist in verification of academic references and should not be used as a sole determinant of reference authenticity. It is intended to complement human judgment in the peer review process.
