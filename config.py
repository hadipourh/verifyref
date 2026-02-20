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
CROSSREF_EMAIL = "hsn.hadipour@gmail.com"  # ← CHANGE THIS

# Database Configuration (Enable/Disable specific databases)
# Set to True to enable, False to disable
ENABLE_CROSSREF = True  # ← Set to True to enable CrossRef database searches
ENABLE_GOOGLE_SCHOLAR = True  # ← Set to True to enable Google Scholar searches (free but rate-limited)

# OPTIONAL: API Keys for enhanced functionality
# Leave empty ("") if you don't have these keys - the tool will work without them

# Semantic Scholar API Key (recommended for higher rate limits)
# Get it from: https://www.semanticscholar.org/product/api#api-key-form
SEMANTIC_SCHOLAR_API_KEY = ""  # ← Add your key here

# OpenAI API Key (only needed for AI-powered fraud detection with OpenAI models)
# Get it from: https://platform.openai.com/api-keys
# Set via environment variable or .env file for security
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # ← Set in .env file or environment

# Google Gemini API Key (FREE tier available - recommended for cost-free AI verification)
# Get it from: https://aistudio.google.com/app/apikey
GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")  # ← Set in .env file or environment

# Groq API Key (FREE tier with fast inference)
# Get it from: https://console.groq.com/keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # ← Set in .env file or environment

# AI Provider Selection (choose which AI service to use)
# Available options: "openai", "gemini", "groq", "ollama"
# - "openai": Paid, most capable (GPT-4, GPT-3.5)
# - "gemini": FREE tier available (Gemini Pro)
# - "groq": FREE tier available, very fast (Llama, Mixtral)
# - "ollama": FREE, runs locally (requires Ollama installed)
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")  # ← Default to free Gemini

# AI Model Selection (model name depends on provider)
# OpenAI: "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"
# Gemini: "gemini-2.0-flash" (free), "gemini-2.5-flash" (free)
# Groq: "llama-3.3-70b-versatile" (free), "mixtral-8x7b-32768" (free)
# Ollama: "llama3.2", "mistral", "phi3" (local, free)
AI_MODEL = os.getenv("AI_MODEL", "gemini-2.0-flash")  # ← Default to free Gemini 2.0 Flash

# AI Decision Weight (how much influence AI has in final verification decision)
# Range: 0.0 to 1.0 (0% to 100% influence)
# Recommended: 0.35-0.50 for balanced analysis, higher for AI-heavy decisions
AI_WEIGHT = 0.50  # ← Increase this to give AI more influence (currently 50%)

# Smart Decision Making Configuration (reduces false positives/negatives)
# These thresholds control when AI can override traditional database decisions
AI_OVERRIDE_FABRICATED_THRESHOLD = 0.95  # STRENGTHENED: Very high bar for overriding fabricated classification
AI_OVERRIDE_AUTHOR_MANIP_THRESHOLD = 0.90  # STRENGTHENED: Very high bar for overriding author manipulation
AI_OVERRIDE_SUSPICIOUS_THRESHOLD = 0.80  # STRENGTHENED: Higher bar for overriding suspicious
AI_FRAUD_DETECTION_SENSITIVITY = 0.85  # STRENGTHENED: More sensitive AI fraud detection

# Database-Dependent AI Decision Making (prevents AI over-optimism)
# Controls how much AI influence is allowed based on database evidence strength
AI_WEIGHT_WITH_STRONG_DB = 0.15   # REDUCED: Less AI influence when database evidence is strong (>0.8)
AI_WEIGHT_WITH_MODERATE_DB = 0.25 # REDUCED: Less AI influence with moderate database evidence (0.6-0.8)
AI_WEIGHT_WITH_WEAK_DB = 0.30     # REDUCED: Less AI influence with weak database evidence (0.4-0.6)
AI_WEIGHT_WITH_VERY_WEAK_DB = 0.35 # REDUCED: Less AI influence even with very weak database evidence (<0.4)

# Conservative AI Override Requirements
AI_MIN_POSITIVE_INDICATORS_HIGH_CONF = 4  # STRENGTHENED: More positive indicators required for high confidence AI claims (>0.8)
AI_MIN_POSITIVE_INDICATORS_MED_CONF = 3   # STRENGTHENED: More positive indicators required for medium confidence AI claims (>0.7)
AI_MIN_CONFIDENCE_GAP = 0.5              # STRENGTHENED: Larger confidence gap required for AI to override database

# NCBI/PubMed API Key (optional, for higher PubMed rate limits)
# Get it from: https://www.ncbi.nlm.nih.gov/account/settings/
NCBI_API_KEY = ""  # ← Add your key here

# Springer Nature API Key (optional, for access to Springer Nature database)
# Get it from: https://dev.springernature.com/
SPRINGER_API_KEY = ""  # ← Add your key here

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
# Options for GROBID server:
#   1. Local Docker: "http://localhost:8070" (requires: docker run -p 8070:8070 grobid/grobid:0.8.0)
#   2. Public demo:  "https://kermitt2-grobid.hf.space" (free, no setup required, may be slower)
# Set GROBID_URL environment variable or change the default below
GROBID_CONFIG = {
    "base_url": os.getenv("GROBID_URL", "https://kermitt2-grobid.hf.space"),
    "timeout": int(os.getenv("GROBID_TIMEOUT", "300")),  # Increased timeout for better processing
    "max_retries": int(os.getenv("GROBID_MAX_RETRIES", "3")),
    
    # Enhanced processing options for higher accuracy
    "use_consolidation": os.getenv("GROBID_USE_CONSOLIDATION", "true").lower() == "true",
    "include_raw_citations": os.getenv("GROBID_INCLUDE_RAW", "true").lower() == "true",
    "segment_sentences": os.getenv("GROBID_SEGMENT_SENTENCES", "true").lower() == "true",
    "generate_ids": os.getenv("GROBID_GENERATE_IDS", "true").lower() == "true",
    
    # Advanced accuracy settings
    "tei_coordinates": os.getenv("GROBID_TEI_COORDINATES", "true").lower() == "true",
    "include_raw_affiliations": os.getenv("GROBID_RAW_AFFILIATIONS", "true").lower() == "true",
    "consolidate_header": os.getenv("GROBID_CONSOLIDATE_HEADER", "true").lower() == "true",
    "consolidate_citations": os.getenv("GROBID_CONSOLIDATE_CITATIONS", "true").lower() == "true",
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
    "enabled_databases": os.getenv("ENABLED_DATABASES", "openalex,semantic_scholar,dblp,iacr,arxiv,pubmed,crossref,google_scholar,springer").split(","),
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
    
    # CrossRef Configuration (Optional fallback - controlled by ENABLE_CROSSREF)
    "crossref": {
        "base_url": "https://api.crossref.org/works",
        "timeout": 30,
        "email": CROSSREF_EMAIL if CROSSREF_EMAIL != "your.email@domain.com" else os.getenv("CROSSREF_EMAIL", "your.email@domain.com"),  # Use config first, then env var
        "enabled": ENABLE_CROSSREF or os.getenv("CROSSREF_ENABLED", "false").lower() == "true",  # Use config variable first, then env var
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
    
    # Springer Nature Configuration
    "springer": {
        "enabled": os.getenv("SPRINGER_ENABLED", "false").lower() == "true",  # Disabled by default - requires API key
        "api_key": SPRINGER_API_KEY or os.getenv("SPRINGER_API_KEY"),  # Use config first, then env var
        "base_url": "https://api.springernature.com/meta/v2",
        "timeout": 30,
        "rate_limit_delay": 1.0,  # Conservative delay for API compliance
        "max_results": 10,  # Maximum results per search
        "respect_rate_limits": True
    },
    
    # Google Scholar Configuration (Smart Fallback + Anti-Bot Protection)
    "google_scholar": {
        "enabled": ENABLE_GOOGLE_SCHOLAR or os.getenv("GOOGLE_SCHOLAR_ENABLED", "false").lower() == "true",  # Disabled by default - respect rate limits
        "method": "scholarly",  # Free scholarly library
        
        # Smart Fallback Strategy - Only use when other databases fail
        "fallback_only": os.getenv("GOOGLE_SCHOLAR_FALLBACK_ONLY", "true").lower() == "true",  # Use only as last resort
        "fallback_threshold": float(os.getenv("GOOGLE_SCHOLAR_FALLBACK_THRESHOLD", "0.7")),  # Only search if best match < 0.7
        "min_databases_searched": int(os.getenv("GOOGLE_SCHOLAR_MIN_DB_SEARCHED", "3")),  # Must search at least 3 other DBs first
        
        # Conservative Rate Limiting
        "rate_limit_delay": float(os.getenv("GOOGLE_SCHOLAR_RATE_LIMIT", "20.0")),  # Very conservative 20 seconds between requests
        "max_requests_per_hour": int(os.getenv("GOOGLE_SCHOLAR_MAX_HOURLY", "10")),  # Ultra conservative hourly limit
        "max_requests_per_day": int(os.getenv("GOOGLE_SCHOLAR_MAX_DAILY", "50")),  # Daily limit to stay safe
        "cooldown_after_block": int(os.getenv("GOOGLE_SCHOLAR_COOLDOWN", "3600")),  # 1 hour cooldown if blocked
        
        # Anti-Bot Protection Measures
        "randomize_delays": True,  # Add random variance to delays (±30%)
        "min_delay_variance": 0.7,  # Minimum 70% of base delay
        "max_delay_variance": 1.3,  # Maximum 130% of base delay
        "session_rotation": True,  # Rotate sessions periodically
        "max_requests_per_session": 5,  # Limit requests per session before rotation
        
        # User Agent Rotation (Academic-focused)
        "rotate_user_agents": True,
        "user_agents": [
            "Mozilla/5.0 (compatible; Academic Research Tool; +research@university.edu)",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ],
        
        # Network Configuration
        "timeout": 45,  # Longer timeout to avoid rushing
        "max_results": 3,  # Limit results to absolute minimum
        "retry_delay": 600,  # 10 minutes if blocked
        "max_retries": 2,  # Limited retries
        
        # Optional: Institutional proxy support for academic users
        "proxy_url": os.getenv("GOOGLE_SCHOLAR_PROXY", ""),  # University proxy if available
        "proxy_rotation": os.getenv("GOOGLE_SCHOLAR_PROXY_ROTATION", "false").lower() == "true",  # Multiple proxies
        "institutional_access": os.getenv("GOOGLE_SCHOLAR_INSTITUTIONAL", "false").lower() == "true",
        
        # Behavioral Mimicking
        "human_like_behavior": True,
        "page_load_simulation": True,  # Simulate natural page loading
        "mouse_movement_simulation": False,  # Keep simple for now
        "respect_robots_txt": True,
    },
    
    # AI Verification Configuration (Enhanced with Multi-Provider Support)
    "ai_verification": {
        "enabled": os.getenv("ENABLE_AI_VERIFICATION", "false").lower() == "true",  # Disabled by default
        
        # AI Provider Selection ("openai", "gemini", "groq", "ollama")
        "provider": AI_PROVIDER or os.getenv("AI_PROVIDER", "gemini"),  # Default to free Gemini
        
        # API Keys for different providers
        "openai_api_key": OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""),
        "google_gemini_api_key": GOOGLE_GEMINI_API_KEY or os.getenv("GOOGLE_GEMINI_API_KEY", ""),
        "groq_api_key": GROQ_API_KEY or os.getenv("GROQ_API_KEY", ""),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),  # Local Ollama server
        
        # Available Providers and Models
        "available_providers": {
            "gemini": {
                "name": "Google Gemini",
                "description": "FREE tier available - Recommended for cost-free verification",
                "cost_level": "free",
                "models": {
                    "gemini-2.0-flash": {"name": "Gemini 2.0 Flash", "cost": "free", "recommended": True},
                    "gemini-2.5-flash": {"name": "Gemini 2.5 Flash", "cost": "free", "recommended": False},
                    "gemini-2.5-pro": {"name": "Gemini 2.5 Pro", "cost": "limited-free", "recommended": False},
                }
            },
            "groq": {
                "name": "Groq (Fast Inference)",
                "description": "FREE tier - Very fast inference with open models",
                "cost_level": "free",
                "models": {
                    "llama-3.3-70b-versatile": {"name": "Llama 3.3 70B", "cost": "free", "recommended": True},
                    "llama-3.1-8b-instant": {"name": "Llama 3.1 8B", "cost": "free", "recommended": False},
                    "mixtral-8x7b-32768": {"name": "Mixtral 8x7B", "cost": "free", "recommended": False},
                }
            },
            "ollama": {
                "name": "Ollama (Local)",
                "description": "FREE - Runs locally, requires Ollama installation",
                "cost_level": "free",
                "models": {
                    "llama3.2": {"name": "Llama 3.2", "cost": "free", "recommended": True},
                    "mistral": {"name": "Mistral", "cost": "free", "recommended": False},
                    "phi3": {"name": "Phi-3", "cost": "free", "recommended": False},
                }
            },
            "openai": {
                "name": "OpenAI",
                "description": "Paid - Most capable models",
                "cost_level": "paid",
                "models": {
                    "gpt-4o": {"name": "GPT-4 Omni", "cost": "high", "recommended": False},
                    "gpt-4o-mini": {"name": "GPT-4 Omni Mini", "cost": "low", "recommended": True},
                    "gpt-4-turbo": {"name": "GPT-4 Turbo", "cost": "medium-high", "recommended": False},
                    "gpt-3.5-turbo": {"name": "GPT-3.5 Turbo", "cost": "very-low", "recommended": False},
                }
            }
        },
        
        # Selected Model Configuration
        "model": AI_MODEL or os.getenv("AI_MODEL", "gemini-2.0-flash"),  # Default to free Gemini 2.0 Flash
        "fallback_model": "gemini-2.0-flash",  # Fallback if primary model fails
        
        # Performance Settings
        "timeout": 45,  # Increased timeout for enhanced prompts
        "max_tokens": 2500,  # Increased for more detailed analysis
        "temperature": 0.1,  # Low temperature for consistent analysis
        
        # Decision Weight Configuration
        "verification_weight": AI_WEIGHT or float(os.getenv("AI_WEIGHT", "0.35")),  # Use config variable first, then env var, then default
        "independent_analysis": True,  # AI makes decisions independent of database results
        
        # Advanced Settings
        "enable_model_fallback": True,  # Try fallback model if primary fails
        "cache_responses": True,  # Cache AI responses to reduce costs
        "detailed_reasoning": True,  # Include detailed reasoning in responses
    }
}

# Reference Classification Configuration
CLASSIFICATION_CONFIG = {
    # Core similarity thresholds (0.0 to 1.0)
    # REDUCED thresholds to decrease false positives - papers with minor metadata issues should not be flagged
    "similarity_threshold": float(os.getenv("SIMILARITY_THRESHOLD", "0.50")),  # REDUCED: Lower bar for authentic (was 0.55)
    "suspicious_threshold": float(os.getenv("SUSPICIOUS_THRESHOLD", "0.20")),   # REDUCED: Fewer papers marked fabricated (was 0.25)
    
    # Feature weights (must sum to 1.0)
    # NOTE: Title weight increased as it's most reliable; author weight reduced due to name format variations
    "title_weight": float(os.getenv("TITLE_WEIGHT", "0.55")),    # Title similarity importance (increased - most reliable signal)
    "author_weight": float(os.getenv("AUTHOR_WEIGHT", "0.25")),  # Author similarity importance (reduced - name variations cause FPs)
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
    "fraud_confidence_boost": float(os.getenv("FRAUD_BOOST", "0.05")),           # REDUCED: Less aggressive fraud confidence (was 0.1)
    "inconclusive_threshold": float(os.getenv("INCONCLUSIVE_THRESHOLD", "0.25")), # INCREASED: More papers get INCONCLUSIVE vs FABRICATED (was 0.15)
    
    # Confidence dampening for harsh classifications (reduces false positives)
    "max_fabricated_confidence": float(os.getenv("MAX_FABRICATED_CONF", "0.70")),  # Never exceed this for FABRICATED without multiple signals
    "require_multiple_signals_for_fraud": os.getenv("REQUIRE_MULTI_FRAUD_SIGNALS", "true").lower() == "true",  # Require 2+ reasons for fraud
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
