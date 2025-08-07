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
        # Validate API key if AI is enabled
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key required for AI verification. Set OPENAI_API_KEY environment variable.")
        
        if not validate_openai_api_key(api_key):
            raise ValueError("Invalid OpenAI API key format. Please check your OPENAI_API_KEY environment variable.")
        
        CLASSIFICATION_CONFIG['ai_verification']['api_key'] = api_key
        logger.info("AI verification enabled with OpenAI API")
    else:
        logger.info("AI verification disabled (default)")

def setup_logging(verbose=False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create custom formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
