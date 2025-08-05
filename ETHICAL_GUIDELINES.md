# Ethical Guidelines for VerifyRef

## Overview
VerifyRef follows strict ethical practices for academic API usage and reference verification.

## API-Only Access (No Web Scraping)

**Official APIs Used:**
- **PubMed/MEDLINE**: NIH/NLM biomedical database (35M+ citations)
- **Semantic Scholar**: Academic search API (200M+ papers) 
- **CrossRef**: DOI database with email identification
- **DBLP**: Computer science bibliography
- **ArXiv**: Preprint repository
- **IACR**: Cryptography papers (RSS feed)
- **OpenAlex**: Comprehensive academic database
- **CryptoDB**: Author verification for crypto papers

## Ethical Practices

### Respectful Usage
- Proper User-Agent headers and email identification
- Rate limiting: 1-5 second delays between requests
- Controlled parallel processing (max 4 workers)
- Graceful handling of rate limit responses (HTTP 429)
- No systematic harvesting or unauthorized access

### Privacy & Transparency
- No personal data collection or tracking
- Local processing only (except necessary API calls)
- All API calls logged transparently
- Session-only data retention
- Optional AI features with user-controlled API keys

### Performance Optimization
- 90%+ cache hit rate to reduce redundant calls
- Context-aware database prioritization
- Thread-safe concurrent operations
- Automatic retry with exponential backoff

## Required Configuration

Edit `config.py` to set:
```python
# Required for CrossRef API
CROSSREF_EMAIL = "your-email@domain.com"

# Optional for enhanced features
SEMANTIC_SCHOLAR_API_KEY = "your-key"
OPENAI_API_KEY = "your-key"  # AI features only
NCBI_API_KEY = "your-key"    # Higher PubMed limits
```

## API Compliance

All database integrations comply with their respective terms of service:
- PubMed/MEDLINE: NIH/NLM guidelines
- Semantic Scholar: Academic use terms
- CrossRef: API etiquette guidelines
- Others: Standard academic/research use policies

## AI Ethics (Optional)

- **Opt-in only**: Requires explicit user configuration
- **Privacy**: Only reference metadata sent, no personal data
- **Cost transparency**: User controls API costs
- **Fallback**: System works fully without AI features

## User Responsibilities

- Don't run multiple instances simultaneously
- Respect configured rate limits
- Use for academic/research purposes only
- Obtain API keys for heavy usage
- Comply with institutional policies

## Contact

For ethical concerns or compliance questions, contact maintainers or consult your institution's research integrity office.

**Version**: VerifyRef v1.0.0
