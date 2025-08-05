"""
RefifyRef - High-performance academic reference verification tool
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

Configuration settings for VerifyRef
"""

import os
from typing import Dict, Any

# =============================================================================
# USER CONFIGURATION SECTION
# =============================================================================
# Edit the values below to configure VerifyRef for your use case

# REQUIRED: Email for CrossRef API access (used for database identification)
# Set your email address here for proper API usage
CROSSREF_EMAIL = "your.email@domain.com"  # ← CHANGE THIS

# OPTIONAL: API Keys for enhanced functionality
# Leave empty ("") if you don't have these keys - the tool will work without them

# Semantic Scholar API Key (recommended for higher rate limits)
# Get it from: https://www.semanticscholar.org/product/api#api-key-form
SEMANTIC_SCHOLAR_API_KEY = ""  # ← Add your key here

# OpenAI API Key (only needed for AI-powered fraud detection)
# Get it from: https://platform.openai.com/api-keys
OPENAI_API_KEY = ""  # ← Add your key here

# NCBI/PubMed API Key (optional, for higher PubMed rate limits)
# Get it from: https://www.ncbi.nlm.nih.gov/account/settings/
NCBI_API_KEY = ""  # ← Add your key here

# =============================================================================
# ADVANCED CONFIGURATION (usually no need to change)
# =============================================================================

# Load environment variables from .env file if it exists (fallback)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, continue without it
    pass

# GROBID Configuration
GROBID_CONFIG = {
    "base_url": os.getenv("GROBID_URL", "http://localhost:8070"),
    "timeout": int(os.getenv("GROBID_TIMEOUT", "60")),
    "max_retries": int(os.getenv("GROBID_MAX_RETRIES", "3")),
}

# Semantic Scholar API Configuration
SEMANTIC_SCHOLAR_CONFIG = {
    "base_url": "https://api.semanticscholar.org/graph/v1",
    "api_key": SEMANTIC_SCHOLAR_API_KEY or os.getenv("SEMANTIC_SCHOLAR_API_KEY"),  # Use config first, then env var
    "timeout": int(os.getenv("SEMANTIC_SCHOLAR_TIMEOUT", "30")),
    "max_retries": int(os.getenv("SEMANTIC_SCHOLAR_MAX_RETRIES", "3")),
    "rate_limit_delay": float(os.getenv("SEMANTIC_SCHOLAR_RATE_LIMIT", "5.0")),  # seconds between requests - increased to avoid 429
    "respect_rate_limits": True,  # Always respect API rate limits
}

# Multi-Database Configuration
DATABASE_CONFIG = {
    "enabled_databases": os.getenv("ENABLED_DATABASES", "openalex,semantic_scholar,dblp,iacr,arxiv,pubmed").split(","),
    "primary_database": os.getenv("PRIMARY_DATABASE", "openalex"),
    
    # OpenAlex Configuration (Recommended primary database)
    "openalex": {
        "base_url": "https://api.openalex.org",
        "timeout": 30,
        "enabled": os.getenv("OPENALEX_ENABLED", "true").lower() == "true",
        "rate_limit_delay": 0.1,  # Very fast, minimal delay needed
        "respect_rate_limits": False,  # No rate limits on OpenAlex
        "per_page": 25,  # Results per page (max 200)
        "mailto": os.getenv("OPENALEX_EMAIL", "refcheck@example.com"),  # Polite identifier (optional)
    },
    
    # DBLP Configuration
    "dblp": {
        "base_url": "https://dblp.org/search/publ/api",
        "timeout": 30,
        "enabled": os.getenv("DBLP_ENABLED", "true").lower() == "true"
    },
    
    # CrossRef Configuration (Optional fallback - disabled by default)
    "crossref": {
        "base_url": "https://api.crossref.org/works",
        "timeout": 30,
        "email": CROSSREF_EMAIL if CROSSREF_EMAIL != "your.email@domain.com" else os.getenv("CROSSREF_EMAIL", "your.email@domain.com"),  # Use config first, then env var
        "enabled": os.getenv("CROSSREF_ENABLED", "false").lower() == "true",  # Disabled by default - use as fallback only
        "rate_limit_delay": 1.0,  # Polite delay between requests
        "respect_rate_limits": True
    },
    
    # IACR ePrint Configuration
    "iacr": {
        "base_url": "https://eprint.iacr.org",
        "rss_url": "https://eprint.iacr.org/rss/rss.xml",
        "timeout": 30,
        "enabled": os.getenv("IACR_ENABLED", "true").lower() == "true",  # Enabled by default for crypto papers
        "cache_duration": 3600  # 1 hour cache for RSS feed
    },
    
    # CryptoDB Author Verification (Optional Enhancement)
    "cryptodb": {
        "enabled": os.getenv("CRYPTODB_ENABLED", "true").lower() == "true",  # Optional feature
        "timeout": int(os.getenv("CRYPTODB_TIMEOUT", "5")),  # Short timeout to avoid delays
        "api_url": "https://www.iacr.org/cryptodb/data/jquery/query.php"
    },
    
    # ArXiv Configuration
    "arxiv": {
        "base_url": "http://export.arxiv.org/api/query",
        "timeout": 10,
        "enabled": os.getenv("ARXIV_ENABLED", "true").lower() == "true"  # Enabled by default
    },
    
    # PubMed/MEDLINE Configuration
    "pubmed": {
        "enabled": os.getenv("PUBMED_ENABLED", "true").lower() == "true",  # Enabled by default
        "api_key": NCBI_API_KEY or os.getenv("NCBI_API_KEY"),  # Use config first, then env var
        "email": CROSSREF_EMAIL if CROSSREF_EMAIL != "your.email@domain.com" else os.getenv("NCBI_EMAIL", "verifyref@example.com"),  # Use same email as CrossRef
        "timeout": 30,
        "rate_limit_delay": 0.34,  # Conservative delay (3 req/sec without API key)
        "max_results": 10,  # Maximum results per search
        "respect_rate_limits": True
    },
    
    # AI Verification Configuration
    "ai_verification": {
        "enabled": os.getenv("ENABLE_AI_VERIFICATION", "false").lower() == "true",  # Disabled by default - users must explicitly enable
        
        # OpenAI API Key - Use config first, then environment variable
        "openai_api_key": OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""),  # No default key - user must provide
        
        "model": "gpt-4o-mini",  # Better compatibility and lower cost - supports JSON format
        "timeout": 30,
        "max_tokens": 1500,
        "temperature": 0.1,  # Low temperature for consistent analysis
        "verification_weight": 0.18  # 18% weight when AI is enabled
    }
}

# Reference Classification Configuration
CLASSIFICATION_CONFIG = {
    # Core similarity thresholds (0.0 to 1.0)
    "similarity_threshold": float(os.getenv("SIMILARITY_THRESHOLD", "0.45")),  # Main threshold for authentic classification
    "suspicious_threshold": float(os.getenv("SUSPICIOUS_THRESHOLD", "0.2")),   # Below this = fabricated/fake
    
    # Feature weights (must sum to 1.0)
    "title_weight": float(os.getenv("TITLE_WEIGHT", "0.6")),     # Title similarity importance
    "author_weight": float(os.getenv("AUTHOR_WEIGHT", "0.2")),   # Author similarity importance  
    "venue_weight": float(os.getenv("VENUE_WEIGHT", "0.15")),    # Venue similarity importance
    "year_weight": float(os.getenv("YEAR_WEIGHT", "0.05")),      # Year similarity importance
    "max_year_difference": int(os.getenv("MAX_YEAR_DIFFERENCE", "3")),  # Max acceptable year difference
    
    # Rigor Level Presets - Override individual settings
    "rigor_level": os.getenv("RIGOR_LEVEL", "balanced").lower(),  # strict, balanced, lenient
    
    # Advanced fraud detection settings
    "enable_fraud_detection": os.getenv("ENABLE_FRAUD_DETECTION", "true").lower() == "true",
    "author_manipulation_threshold": float(os.getenv("AUTHOR_MANIP_THRESHOLD", "0.85")),  # Title sim for author fraud
    "multi_database_requirement": os.getenv("MULTI_DB_REQUIRED", "false").lower() == "true",  # Require multiple DBs
    "single_database_penalty": float(os.getenv("SINGLE_DB_PENALTY", "0.05")),  # Confidence reduction for single DB
    
    # Classification confidence adjustments
    "authentic_confidence_boost": float(os.getenv("AUTHENTIC_BOOST", "0.1")),    # Extra confidence for authentic
    "fraud_confidence_boost": float(os.getenv("FRAUD_BOOST", "0.1")),           # Extra confidence for fraud detection
    "inconclusive_threshold": float(os.getenv("INCONCLUSIVE_THRESHOLD", "0.15")), # Very low similarity threshold
}

# Output Configuration
OUTPUT_CONFIG = {
    "format": os.getenv("OUTPUT_FORMAT", "json"),  # json, csv, txt
    "include_raw_data": os.getenv("INCLUDE_RAW_DATA", "false").lower() == "true",
    "verbose": os.getenv("VERBOSE", "false").lower() == "true",
}

# Logging Configuration
LOGGING_CONFIG = {
    "level": os.getenv("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": os.getenv("LOG_FILE"),  # If None, logs to console
}

# Text Processing Configuration
TEXT_PROCESSING_CONFIG = {
    "normalize_whitespace": True,
    "remove_punctuation_for_comparison": True,
    "case_sensitive": False,
    "min_title_length": int(os.getenv("MIN_TITLE_LENGTH", "10")),
    "min_author_length": int(os.getenv("MIN_AUTHOR_LENGTH", "3")),
}

def get_config() -> Dict[str, Any]:
    """
    Get all configuration settings as a dictionary
    Apply rigor level presets if specified
    
    Returns:
        Dict containing all configuration settings
    """
    # Apply rigor level presets before returning config
    apply_rigor_level_preset()
    
    return {
        "grobid": GROBID_CONFIG,
        "semantic_scholar": SEMANTIC_SCHOLAR_CONFIG,
        "databases": DATABASE_CONFIG,
        "classification": CLASSIFICATION_CONFIG,
        "output": OUTPUT_CONFIG,
        "logging": LOGGING_CONFIG,
        "text_processing": TEXT_PROCESSING_CONFIG,
    }

def apply_rigor_level_preset():
    """
    Apply rigor level presets to override individual classification settings
    """
    rigor_level = CLASSIFICATION_CONFIG["rigor_level"]
    
    if rigor_level == "strict":
        # Strict/Pessimistic settings - catch more fraud but more false positives
        CLASSIFICATION_CONFIG.update({
            "similarity_threshold": 0.75,           # Higher threshold for authentic
            "suspicious_threshold": 0.35,           # Higher threshold for suspicious  
            "author_manipulation_threshold": 0.80,  # Lower threshold = easier to detect author fraud
            "single_database_penalty": 0.15,       # Higher penalty for single DB
            "fraud_confidence_boost": 0.15,        # More confidence in fraud detection
            "authentic_confidence_boost": 0.05,    # Less confidence in authentic classification
        })
        # Update AI weight for stricter analysis
        if "ai_verification" in DATABASE_CONFIG:
            DATABASE_CONFIG["ai_verification"]["verification_weight"] = 0.25  # Higher AI influence
            
    elif rigor_level == "lenient":
        # Lenient/Optimistic settings - fewer false positives but might miss some fraud
        CLASSIFICATION_CONFIG.update({
            "similarity_threshold": 0.35,           # Lower threshold for authentic
            "suspicious_threshold": 0.10,           # Lower threshold for suspicious
            "author_manipulation_threshold": 0.90,  # Higher threshold = harder to detect author fraud  
            "single_database_penalty": 0.0,        # No penalty for single DB
            "fraud_confidence_boost": 0.05,        # Less confidence in fraud detection
            "authentic_confidence_boost": 0.15,    # More confidence in authentic classification
        })
        # Update AI weight for more lenient analysis
        if "ai_verification" in DATABASE_CONFIG:
            DATABASE_CONFIG["ai_verification"]["verification_weight"] = 0.10  # Lower AI influence
            
    elif rigor_level == "balanced":
        # Balanced settings (current defaults) - no changes needed
        pass
    
    else:
        print(f"Warning: Unknown rigor level '{rigor_level}'. Using balanced settings.")

def set_rigor_level(level: str):
    """
    Programmatically set the rigor level
    
    Args:
        level: "strict", "balanced", or "lenient"
    """
    if level.lower() in ["strict", "balanced", "lenient"]:
        CLASSIFICATION_CONFIG["rigor_level"] = level.lower()
        apply_rigor_level_preset()
        print(f"Rigor level set to: {level}")
    else:
        print(f"Error: Invalid rigor level '{level}'. Use: strict, balanced, or lenient")

def validate_config() -> bool:
    """
    Validate configuration settings
    
    Returns:
        True if configuration is valid, False otherwise
    """
    # Check required settings
    if not GROBID_CONFIG["base_url"]:
        print("Error: GROBID base URL not configured")
        return False
    
    # Validate thresholds
    if not 0 <= CLASSIFICATION_CONFIG["similarity_threshold"] <= 1:
        print("Error: Similarity threshold must be between 0 and 1")
        return False
    
    # Validate weights sum to 1.0
    weight_sum = (
        CLASSIFICATION_CONFIG["title_weight"] +
        CLASSIFICATION_CONFIG["author_weight"] +
        CLASSIFICATION_CONFIG["venue_weight"] +
        CLASSIFICATION_CONFIG["year_weight"]
    )
    
    if abs(weight_sum - 1.0) > 0.01:
        print(f"Warning: Classification weights sum to {weight_sum}, not 1.0")
    
    return True
