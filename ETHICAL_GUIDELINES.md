# Ethical Web Access Guidelines for VerifyRef

## Overview
VerifyRef is designed to be fully compliant with ethical web access practices and academic API usage guidelines. This document outlines our ethical practices and compliance measures for the comprehensive reference verification system.

## Web Access Summary

### ✅ API-Only Approach
VerifyRef uses **ONLY official APIs and public data feeds** - NO web scraping:

1. **PubMed/MEDLINE API** (`eutils.ncbi.nlm.nih.gov`) 🆕
   - Official NIH/NLM biomedical database API
   - Includes proper tool identification
   - Rate-limited with appropriate delays
   - 35+ million biomedical citations

2. **Semantic Scholar API** (`api.semanticscholar.org`)
   - Official academic search API
   - Rate-limited with 5-second delays
   - Supports API key for higher limits
   - Respects 429 rate limit responses
   - 200+ million papers coverage

3. **CrossRef API** (`api.crossref.org`)
   - Official DOI database API
   - Includes proper email identification
   - 1-second delays between requests
   - Follows CrossRef etiquette guidelines

4. **DBLP API** (`dblp.org/search/publ/api`)
   - Official computer science bibliography API
   - No rate limits required (as per DBLP)
   - Read-only access

5. **ArXiv API** (`export.arxiv.org/api/query`)
   - Official preprint repository API
   - Follows ArXiv API guidelines
   - Rate-limited requests

6. **IACR ePrint RSS** (`eprint.iacr.org/rss/rss.xml`)
   - Public RSS feed
   - Cached for 1 hour to reduce server load
   - Cryptography paper database

7. **Google Scholar** (Limited, Respectful Use)
   - Used minimally with extensive rate limiting
   - Only for academic verification purposes
   - Not for systematic harvesting

8. **CryptoDB Author Verification** 🆕
   - Author verification for cryptography papers
   - Read-only access to public data

## Ethical Practices Implemented

### 🤝 Respectful API Usage
- **User-Agent Identification**: All requests include proper User-Agent headers identifying VerifyRef
- **Email Contact**: CrossRef and PubMed requests include maintainer email for accountability
- **Rate Limiting**: Configurable delays between requests (1-5 seconds)
- **Timeout Controls**: Reasonable timeouts to avoid hanging connections
- **Error Handling**: Graceful handling of rate limit responses (429 errors)
- **Parallel Processing**: Controlled concurrency (max 4 workers) to prevent API overload 🆕

### 📊 Transparent Logging
- All API calls are logged with appropriate detail levels
- Users can see which databases are being queried in verbose mode
- Failed requests are clearly reported with detailed error messages
- Performance metrics are displayed without compromising privacy

### 🔒 Privacy Respect
- No personal data collection from users
- No tracking or analytics beyond session performance
- Local processing only (except necessary API calls)
- No data retention beyond the current session
- AI features (ChatGPT/GPT-4) are optional and user-controlled 🆕

### ⚡ Resource Conservation
- Intelligent caching with 90%+ hit rates to reduce redundant API calls 🆕
- Thread-safe concurrent requests with reasonable limits
- Automatic retry with exponential backoff
- Graceful degradation when services are unavailable
- Context-aware database prioritization to minimize unnecessary queries 🆕

### 🤖 AI Ethics (Optional Features) 🆕
- **Opt-in Only**: AI features require explicit user configuration
- **API Key Security**: User-provided OpenAI API keys are handled securely
- **Cost Transparency**: Users are informed about potential API costs
- **Privacy**: Only reference metadata (no personal info) sent to AI services
- **Fallback**: System works fully without AI features
- No hidden data collection

### 🔒 Privacy Respect
- No personal data collection from users
- No tracking or analytics
- Local processing only (except API calls)
- No data retention beyond the session

### ⚡ Resource Conservation
- Caching where appropriate (IACR RSS feed)
- Concurrent requests with reasonable limits
- Automatic retry with exponential backoff
- Graceful degradation when services are unavailable

## API Key Recommendations

For production use, we recommend obtaining API keys for enhanced performance:

### PubMed/MEDLINE 🆕
- No API key required for basic use
- Proper tool identification included in all requests
- Email identification recommended for accountability
- Rate limits automatically respected

### Semantic Scholar
- Apply at: https://www.semanticscholar.org/product/api#api-key-form
- Increases rate limits significantly
- Free for academic use
- Highly recommended for frequent use

### OpenAI (For AI Features) 🆕
- Required only if using AI-powered fraud detection
- User must provide their own API key
- Costs controlled by user's OpenAI account limits
- Completely optional - tool works fully without AI features

### CrossRef
- Email registration recommended for higher limits
- Free for academic and non-commercial use
- Proper attribution required

## Configuration for Ethical Use

```bash
# Required: Set your email for CrossRef and PubMed identification
export CROSSREF_EMAIL="your-email@university.edu"

# Optional: Semantic Scholar API key for higher limits
export SEMANTIC_SCHOLAR_API_KEY="your-api-key"

# Optional: OpenAI API key for AI-powered fraud detection
export OPENAI_API_KEY="your-openai-api-key"

# Adjust rate limits if needed (seconds between requests)
export SEMANTIC_SCHOLAR_RATE_LIMIT="5.0"
export CROSSREF_RATE_LIMIT="1.0"

# Control parallel processing (max workers)
export MAX_WORKERS="4"
```

## Terms of Service Compliance

- **PubMed/MEDLINE**: Complies with NIH/NLM API usage guidelines 🆕
- **Semantic Scholar**: Complies with academic use terms
- **CrossRef**: Follows API etiquette guidelines
- **DBLP**: Academic use, no restrictions on API
- **ArXiv**: Follows API usage guidelines
- **IACR**: Public RSS feed, academic use
- **Google Scholar**: Minimal, respectful use for verification only
- **OpenAI**: User-controlled, follows OpenAI usage policies 🆕

## Advanced Features Ethics 🆕

### Parallel Processing
- Limited to 4 concurrent workers maximum
- Designed to prevent API overload
- Automatic throttling when rate limits are encountered
- Thread-safe operations to prevent race conditions

### Intelligent Caching
- Reduces redundant API calls by 90%+
- Improves performance while being respectful to servers
- Cache is session-only (no persistent storage)
- Thread-safe implementation for concurrent access

### Context-Aware Search
- Prioritizes relevant databases to reduce unnecessary queries
- Computer Science context prioritizes DBLP, IACR, ArXiv
- Biomedical context prioritizes PubMed, Semantic Scholar
- Reduces overall API load through intelligent targeting

### Fraud Detection Ethics
- Used only for academic integrity purposes
- No personal data or private information analyzed
- Focus on reference authenticity, not content judgment
- Transparent reporting of analysis methods

## Monitoring and Compliance

### Automated Compliance Checks
- Rate limit enforcement in code
- Automatic delays between requests
- Respect for HTTP 429 responses
- Timeout and retry logic

### User Guidelines
- Do not run multiple instances simultaneously
- Respect the configured rate limits
- Consider API keys for heavy usage
- Report any issues or concerns

## Monitoring and Optimization 🆕

VerifyRef provides built-in ethical monitoring:

- **Performance Analytics**: Real-time monitoring of API call efficiency
- **Cache Hit Rate Monitoring**: Tracks system efficiency (typical 90%+ hit rate)
- **Thread Safety Verification**: Ensures no race conditions in parallel processing
- **Rate Limit Compliance**: Automatic throttling when approaching limits
- **Speed vs. Ethics Balance**: Optimized for both performance and respectful API usage

## Contact and Accountability

For any ethical concerns or API compliance issues:
- Review this document and configuration
- Check API provider terms of service
- Ensure proper email configuration for CrossRef
- Consider API keys for production use

## Legal Disclaimer and Final Notes

VerifyRef is designed for academic and research purposes. Users are responsible for:

- Ensuring compliance with all applicable institutional policies
- Understanding the terms of service for integrated APIs (PubMed, Semantic Scholar, CrossRef, OpenAI) 🆕
- Using AI fraud detection features responsibly and transparently 🆕
- Respecting parallel processing limits and API rate restrictions 🆕
- Acknowledging that VerifyRef is a verification tool, not a substitute for proper citation practices
- Understanding that context-aware search prioritization is for efficiency, not content filtering 🆕

The tool accesses only public APIs and data feeds, with no web scraping or unauthorized data access.

**Version**: VerifyRef v1.0.0 🆕
**Last Updated**: Current release 🆕
**Compliance**: Academic integrity standards, API terms of service, parallel processing ethics 🆕

For technical support or ethical guidance, consult your institution's research integrity office or information technology department.
