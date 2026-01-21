"""
VerifyRef - High-performance academic reference verification tool
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

Configuration and validation utilities
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def validate_openai_api_key(api_key: str) -> bool:
    """Validate OpenAI API key format"""
    if not api_key:
        return False
    
    # Basic format validation for OpenAI API keys
    if not api_key.startswith('sk-'):
        return False
    
    # Check if it has reasonable length (OpenAI keys are typically 51 chars)
    if len(api_key) < 40:
        return False
    
    return True

def apply_runtime_config(args):
    """Apply runtime configuration from command line arguments"""
    from config import DATABASE_CONFIG, CLASSIFICATION_CONFIG
    
    # Update database configurations
    if hasattr(args, 'no_semantic_scholar') and args.no_semantic_scholar:
        DATABASE_CONFIG['semantic_scholar']['enabled'] = False
    if hasattr(args, 'no_openalex') and args.no_openalex:
        DATABASE_CONFIG['openalex']['enabled'] = False
    if hasattr(args, 'no_dblp') and args.no_dblp:
        DATABASE_CONFIG['dblp']['enabled'] = False
    if hasattr(args, 'no_arxiv') and args.no_arxiv:
        DATABASE_CONFIG['arxiv']['enabled'] = False
    if hasattr(args, 'no_pubmed') and args.no_pubmed:
        DATABASE_CONFIG['pubmed']['enabled'] = False
    if hasattr(args, 'no_iacr') and args.no_iacr:
        DATABASE_CONFIG['iacr']['enabled'] = False
    if hasattr(args, 'no_springer') and args.no_springer:
        DATABASE_CONFIG['springer']['enabled'] = False
    if hasattr(args, 'no_crossref') and args.no_crossref:
        DATABASE_CONFIG['crossref']['enabled'] = False

    # Handle AI verification flag (AI is disabled by default)
    ai_enabled = getattr(args, 'enable_ai', False)
    if 'ai_verification' in DATABASE_CONFIG:
        DATABASE_CONFIG['ai_verification']['enabled'] = ai_enabled
    
    if ai_enabled:
        # Get the AI provider (default to gemini which is free)
        provider = os.getenv('AI_PROVIDER', 'gemini')
        DATABASE_CONFIG['ai_verification']['provider'] = provider
        
        # Check for API key based on provider
        api_key = None
        provider_name = ""
        
        if provider == "gemini":
            api_key = os.getenv('GOOGLE_GEMINI_API_KEY')
            if not api_key:
                try:
                    from config import GOOGLE_GEMINI_API_KEY
                    api_key = GOOGLE_GEMINI_API_KEY
                except (ImportError, AttributeError):
                    pass
            provider_name = "Google Gemini (FREE)"
            key_env_var = "GOOGLE_GEMINI_API_KEY"
            key_url = "https://aistudio.google.com/app/apikey"
            
        elif provider == "groq":
            api_key = os.getenv('GROQ_API_KEY')
            if not api_key:
                try:
                    from config import GROQ_API_KEY
                    api_key = GROQ_API_KEY
                except (ImportError, AttributeError):
                    pass
            provider_name = "Groq (FREE)"
            key_env_var = "GROQ_API_KEY"
            key_url = "https://console.groq.com/keys"
            # Set appropriate model for Groq
            groq_model = os.getenv('AI_MODEL', 'llama-3.3-70b-versatile')
            DATABASE_CONFIG['ai_verification']['model'] = groq_model
            
        elif provider == "ollama":
            # Ollama doesn't need an API key, just check if server is running
            api_key = "local"  # Placeholder - Ollama runs locally
            provider_name = "Ollama (FREE, local)"
            key_env_var = None
            key_url = "https://ollama.ai"
            # Set appropriate model for Ollama (not Gemini model)
            ollama_model = os.getenv('AI_MODEL', 'llama3.2')
            DATABASE_CONFIG['ai_verification']['model'] = ollama_model
            
        elif provider == "openai":
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                try:
                    from config import OPENAI_API_KEY
                    api_key = OPENAI_API_KEY
                except (ImportError, AttributeError):
                    pass
            provider_name = "OpenAI (PAID)"
            key_env_var = "OPENAI_API_KEY"
            key_url = "https://platform.openai.com/api-keys"
            
            # Validate OpenAI key format
            if api_key and not validate_openai_api_key(api_key):
                raise ValueError("Invalid OpenAI API key format. Please check your OPENAI_API_KEY.")
        
        else:
            raise ValueError(f"Unknown AI provider: {provider}. Supported: gemini, groq, ollama, openai")
        
        if not api_key:
            error_msg = f"{provider_name} API key required for AI verification.\n"
            if key_env_var:
                error_msg += f"Set {key_env_var} environment variable or configure it in config.py.\n"
                error_msg += f"Get a FREE key at: {key_url}"
            else:
                error_msg += f"Install and start Ollama: {key_url}"
            raise ValueError(error_msg)
        
        # Store the API key in config
        if provider == "gemini":
            DATABASE_CONFIG['ai_verification']['google_gemini_api_key'] = api_key
        elif provider == "groq":
            DATABASE_CONFIG['ai_verification']['groq_api_key'] = api_key
        elif provider == "openai":
            DATABASE_CONFIG['ai_verification']['openai_api_key'] = api_key
        
        logger.info(f"AI verification enabled with {provider_name}")
    else:
        logger.info("AI verification disabled (default)")

def setup_logging(verbose=False):
    """Setup logging configuration"""
    import sys
    
    # Setup root logger
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    if verbose:
        # Enable logging for verbose mode
        level = logging.DEBUG
        root_logger.setLevel(level)
        
        # Create custom formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add console handler - use stdout for main logging
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    else:
        # Disable all logging for non-verbose mode
        root_logger.setLevel(logging.CRITICAL + 1)  # Higher than CRITICAL to disable all logs
