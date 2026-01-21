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
"""


import os
import json
import logging
import time
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# OpenAI client
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

# Google Gemini client (new SDK)
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    # Try legacy SDK as fallback
    try:
        import google.generativeai as genai
        types = None
        GEMINI_AVAILABLE = True
    except ImportError:
        GEMINI_AVAILABLE = False
        genai = None
        types = None

# Groq client
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

# Ollama support (via requests)
try:
    import requests
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class AIVerificationResult:
    """Result from AI-powered verification"""
    is_authentic: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    red_flags: List[str]
    positive_indicators: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage, including all fields"""
        return {
            'is_authentic': self.is_authentic,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'red_flags': self.red_flags,
            'positive_indicators': self.positive_indicators,
            **self.metadata  # Include all metadata fields
        }

class AIReferenceVerifier:
    """
    Multi-provider AI-powered reference verifier with support for:
    - Google Gemini (FREE tier available)
    - Groq (FREE tier available)
    - Ollama (FREE, local)
    - OpenAI (paid)
    
    Analyzes reference authenticity using advanced natural language understanding
    with robust error handling, caching, and performance optimization.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash", provider: str = "gemini"):
        """
        Initialize multi-provider AI verifier
        
        Args:
            api_key: API key (if None, will try config/environment)
            model: Model to use (default: gemini-1.5-flash - free)
            provider: AI provider ("gemini", "groq", "ollama", "openai")
        """
        self.client = None
        self.provider = provider
        self.model = model
        self._verification_cache = {}
        self._performance_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'cache_hits': 0,
            'average_response_time': 0.0,
            'total_tokens_used': 0,
            'models_used': {}
        }
        self.available_providers = {}
        self.fallback_model = None
        self.independent_analysis = True
        
        # Check if AI verification is enabled first
        try:
            from config import DATABASE_CONFIG
            ai_config = DATABASE_CONFIG.get("ai_verification", {})
            
            # If AI is disabled, don't initialize anything
            if not ai_config.get("enabled", False):
                logger.info("AI verification disabled in configuration - skipping initialization")
                return
            
            # Load provider and model configuration
            self.provider = ai_config.get("provider", provider)
            self.model = ai_config.get("model", model)
            self.available_providers = ai_config.get("available_providers", {})
            self.fallback_model = ai_config.get("fallback_model", "gemini-1.5-flash")
            self.enable_model_fallback = ai_config.get("enable_model_fallback", True)
            
            # Load performance settings
            self.timeout = ai_config.get("timeout", 45)
            self.max_tokens = ai_config.get("max_tokens", 2500)
            self.temperature = ai_config.get("temperature", 0.1)
            self.verification_weight = ai_config.get("verification_weight", 0.35)
            self.independent_analysis = ai_config.get("independent_analysis", True)
            
            # Get API keys for different providers
            self.openai_api_key = ai_config.get("openai_api_key", "")
            self.gemini_api_key = ai_config.get("google_gemini_api_key", "")
            self.groq_api_key = ai_config.get("groq_api_key", "")
            self.ollama_base_url = ai_config.get("ollama_base_url", "http://localhost:11434")
            
        except ImportError:
            # Fallback if config not available
            self.fallback_model = "gemini-1.5-flash"
            self.timeout = 45
            self.max_tokens = 2500
            self.temperature = 0.1
            self.verification_weight = 0.35
            self.independent_analysis = True
            self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
            self.gemini_api_key = os.getenv('GOOGLE_GEMINI_API_KEY', '')
            self.groq_api_key = os.getenv('GROQ_API_KEY', '')
            self.ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        
        # Initialize the appropriate client based on provider
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the AI client based on the selected provider"""
        if self.provider == "gemini":
            self._initialize_gemini()
        elif self.provider == "groq":
            self._initialize_groq()
        elif self.provider == "ollama":
            self._initialize_ollama()
        elif self.provider == "openai":
            self._initialize_openai()
        else:
            logger.warning(f"Unknown AI provider: {self.provider}")
    
    def _initialize_gemini(self):
        """Initialize Google Gemini client (FREE tier available)"""
        if not GEMINI_AVAILABLE:
            logger.warning("Google Generative AI library not available. Install with: pip install google-genai")
            return
        
        api_key = self.gemini_api_key or os.getenv('GOOGLE_GEMINI_API_KEY', '')
        if not api_key:
            logger.warning("No Google Gemini API key provided. Get free key at: https://aistudio.google.com/app/apikey")
            return
        
        try:
            # Check if we're using the new SDK (google.genai) or legacy (google.generativeai)
            if types is not None:
                # New SDK
                self.client = genai.Client(api_key=api_key)
                self._gemini_new_sdk = True
            else:
                # Legacy SDK
                genai.configure(api_key=api_key)
                self.client = genai.GenerativeModel(self.model)
                self._gemini_new_sdk = False
            logger.info(f"Gemini AI verifier initialized with model: {self.model} (FREE tier)")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.client = None
    
    def _initialize_groq(self):
        """Initialize Groq client (FREE tier available)"""
        if not GROQ_AVAILABLE:
            logger.warning("Groq library not available. Install with: pip install groq")
            return
        
        api_key = self.groq_api_key or os.getenv('GROQ_API_KEY', '')
        if not api_key:
            logger.warning("No Groq API key provided. Get free key at: https://console.groq.com/keys")
            return
        
        try:
            self.client = Groq(api_key=api_key)
            logger.info(f"Groq AI verifier initialized with model: {self.model} (FREE tier)")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            self.client = None
    
    def _initialize_ollama(self):
        """Initialize Ollama client (FREE, local)"""
        if not OLLAMA_AVAILABLE:
            logger.warning("Requests library not available for Ollama. Install with: pip install requests")
            return
        
        try:
            # Test connection to Ollama
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                self.client = "ollama"  # Use string marker for Ollama
                logger.info(f"Ollama AI verifier initialized with model: {self.model} (FREE, local)")
            else:
                logger.warning("Ollama server not responding. Start it with: ollama serve")
        except Exception as e:
            logger.warning(f"Cannot connect to Ollama at {self.ollama_base_url}: {e}")
            logger.warning("Make sure Ollama is installed and running: https://ollama.ai")
            self.client = None
    
    def _initialize_openai(self):
        """Initialize OpenAI client (PAID)"""
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI library not available. Install with: pip install openai")
            return
        
        api_key = self.openai_api_key or os.getenv('OPENAI_API_KEY', '')
        if not api_key:
            logger.warning("No OpenAI API key provided. AI verification disabled.")
            return
        
        try:
            self.client = openai.OpenAI(api_key=api_key)
            logger.info(f"OpenAI AI verifier initialized with model: {self.model} (PAID)")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if AI verifier is available and configured"""
        # First check if AI is enabled in config
        try:
            from config import DATABASE_CONFIG
            ai_config = DATABASE_CONFIG.get("ai_verification", {})
            if not ai_config.get("enabled", False):
                return False
        except ImportError:
            pass
            
        return self.client is not None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current provider and model"""
        provider_info = self.available_providers.get(self.provider, {})
        model_info = provider_info.get("models", {}).get(self.model, {})
        
        return {
            "provider": self.provider,
            "provider_name": provider_info.get("name", "Unknown"),
            "cost_level": provider_info.get("cost_level", "unknown"),
            "current_model": self.model,
            "model_name": model_info.get("name", self.model),
            "model_cost": model_info.get("cost", "unknown"),
            "fallback_model": self.fallback_model,
            "independent_analysis": self.independent_analysis,
            "verification_weight": getattr(self, 'verification_weight', 0.35)
        }
    
    @staticmethod
    def get_free_providers_info() -> str:
        """Get information about free AI providers for user guidance"""
        return """
FREE AI Providers for VerifyRef:

1. Google Gemini (RECOMMENDED)
   - Get free API key: https://aistudio.google.com/app/apikey
   - Set: GOOGLE_GEMINI_API_KEY=your_key
   - Models: gemini-1.5-flash (free), gemini-1.5-pro (limited free)

2. Groq (FAST)
   - Get free API key: https://console.groq.com/keys
   - Set: GROQ_API_KEY=your_key
   - Models: llama-3.3-70b-versatile, mixtral-8x7b-32768

3. Ollama (LOCAL, no API key needed)
   - Install: https://ollama.ai
   - Run: ollama serve
   - Models: llama3.2, mistral, phi3

To enable: Set ENABLE_AI_VERIFICATION=true and AI_PROVIDER=gemini (or groq/ollama)
"""
    
    def verify_reference(self, 
                        extracted_ref: Dict[str, Any], 
                        database_results: List[Dict[str, Any]], 
                        paper_context: Optional[str] = None) -> Optional[AIVerificationResult]:
        """
        Verify reference authenticity using enhanced AI analysis with model selection and independent analysis
        
        Args:
            extracted_ref: Extracted reference data
            database_results: Results from database searches (may be ignored if independent_analysis=True)
            paper_context: Optional context about the source paper
            
        Returns:
            AIVerificationResult or None if verification failed
        """
        if not self.is_available():
            return None
        
        start_time = time.time()
        self._performance_stats['total_requests'] += 1
        
        # Generate cache key based on reference content and analysis mode
        cache_key = self._generate_cache_key(extracted_ref, database_results if not self.independent_analysis else [])
        
        # Check cache first
        if cache_key in self._verification_cache:
            self._performance_stats['cache_hits'] += 1
            cached_result = self._verification_cache[cache_key]
            logger.debug(f"AI verification cache hit for reference: {extracted_ref.get('title', '')[:50]}...")
            return cached_result
        
        # Choose analysis method based on configuration
        if self.independent_analysis:
            return self._independent_verification(extracted_ref, paper_context, start_time, cache_key)
        else:
            return self._database_assisted_verification(extracted_ref, database_results, paper_context, start_time, cache_key)
    
    def _independent_verification(self, extracted_ref: Dict[str, Any], paper_context: Optional[str], 
                                start_time: float, cache_key: str) -> Optional[AIVerificationResult]:
        """
        Perform independent AI verification based solely on AI's knowledge
        """
        logger.debug("Performing independent AI verification (no database dependency)")
        
        prompt = self._build_independent_analysis_prompt(extracted_ref, paper_context)
        return self._execute_ai_request(prompt, start_time, cache_key, "independent")
    
    def _database_assisted_verification(self, extracted_ref: Dict[str, Any], database_results: List[Dict[str, Any]], 
                                      paper_context: Optional[str], start_time: float, cache_key: str) -> Optional[AIVerificationResult]:
        """
        Perform database-assisted AI verification using search results
        """
        logger.debug("Performing database-assisted AI verification")
        
        prompt = self._build_analysis_prompt(extracted_ref, database_results, paper_context)
        return self._execute_ai_request(prompt, start_time, cache_key, "database_assisted")
    
    def _execute_ai_request(self, prompt: str, start_time: float, cache_key: str, analysis_type: str) -> Optional[AIVerificationResult]:
        """
        Execute AI request with multi-provider support and error handling
        """
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                # Route to appropriate provider
                if self.provider == "gemini":
                    response_content, tokens_used = self._call_gemini(prompt)
                elif self.provider == "groq":
                    response_content, tokens_used = self._call_groq(prompt)
                elif self.provider == "ollama":
                    response_content, tokens_used = self._call_ollama(prompt)
                elif self.provider == "openai":
                    response_content, tokens_used = self._call_openai(prompt)
                else:
                    logger.error(f"Unknown AI provider: {self.provider}")
                    return None
                
                if not response_content:
                    raise ValueError(f"Empty response from {self.provider} API")
                
                result_data = self._parse_ai_response(response_content)
                
                # Validate parsed data structure
                required_fields = ['is_authentic', 'confidence', 'reasoning']
                for field in required_fields:
                    if field not in result_data:
                        logger.warning(f"Missing required field '{field}' in AI response")
                        result_data[field] = self._get_default_value(field)
                
                # Track performance statistics
                response_time = time.time() - start_time
                self._performance_stats['successful_requests'] += 1
                self._performance_stats['total_tokens_used'] += tokens_used
                
                # Track model usage
                model_key = f"{self.provider}/{self.model}"
                if model_key not in self._performance_stats['models_used']:
                    self._performance_stats['models_used'][model_key] = 0
                self._performance_stats['models_used'][model_key] += 1
                
                # Update average response time
                current_avg = self._performance_stats['average_response_time']
                successful_count = self._performance_stats['successful_requests']
                self._performance_stats['average_response_time'] = (
                    (current_avg * (successful_count - 1) + response_time) / successful_count
                )
                
                # Create enhanced result
                ai_result = AIVerificationResult(
                    is_authentic=bool(result_data.get('is_authentic', False)),
                    confidence=max(0.0, min(1.0, float(result_data.get('confidence', 0.5)))),
                    reasoning=str(result_data.get('reasoning', 'AI analysis completed'))[:2000],
                    red_flags=self._validate_list(result_data.get('red_flags', [])),
                    positive_indicators=self._validate_list(result_data.get('positive_indicators', [])),
                    metadata={
                        'provider': self.provider,
                        'model': self.model,
                        'tokens_used': tokens_used,
                        'analysis_version': '3.1',
                        'analysis_type': analysis_type,
                        'attempt': attempt + 1,
                        'response_time': response_time,
                        'authenticity_factors': result_data.get('authenticity_factors', {}),
                        'risk_assessment': result_data.get('risk_assessment', 'medium'),
                        'recommendation': result_data.get('recommendation', 'Standard verification completed')
                    }
                )
                
                # Cache the result
                self._verification_cache[cache_key] = ai_result
                if len(self._verification_cache) > 100:
                    oldest_key = next(iter(self._verification_cache))
                    del self._verification_cache[oldest_key]
                
                return ai_result
                
            except Exception as e:
                error_msg = str(e)
                
                # Handle rate limits and timeouts
                if "rate_limit" in error_msg.lower() and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limit hit, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                elif "timeout" in error_msg.lower() and attempt < max_retries - 1:
                    logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                    time.sleep(retry_delay)
                    continue
                
                logger.error(f"AI verification failed on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
        
        return None
    
    def _call_gemini(self, prompt: str) -> tuple:
        """Call Google Gemini API (FREE tier available)"""
        system_prompt = self._get_system_prompt()
        full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # Check if using new SDK or legacy
        if getattr(self, '_gemini_new_sdk', False):
            # New SDK (google.genai) requires full model path
            model_name = self.model
            if not model_name.startswith('models/'):
                model_name = f"models/{model_name}"
            
            # Try gemini-2.0-flash if the specified model fails
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_tokens,
                    )
                )
                return response.text, 0
            except Exception as e:
                # Fallback to gemini-2.0-flash
                if 'gemini-2.0-flash' not in model_name:
                    logger.warning(f"Model {model_name} failed, trying gemini-2.0-flash: {e}")
                    response = self.client.models.generate_content(
                        model="models/gemini-2.0-flash",
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=self.temperature,
                            max_output_tokens=self.max_tokens,
                        )
                    )
                    return response.text, 0
                raise
        else:
            # Legacy SDK (google.generativeai)
            response = self.client.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                )
            )
            return response.text, 0  # Gemini doesn't report token usage in free tier
    
    def _call_groq(self, prompt: str) -> tuple:
        """Call Groq API (FREE tier available)"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        
        tokens = response.usage.total_tokens if response.usage else 0
        return response.choices[0].message.content, tokens
    
    def _call_ollama(self, prompt: str) -> tuple:
        """Call Ollama API (FREE, local)"""
        system_prompt = self._get_system_prompt()
        
        response = requests.post(
            f"{self.ollama_base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": f"{system_prompt}\n\n{prompt}",
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                }
            },
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            raise ValueError(f"Ollama API error: {response.text}")
        
        result = response.json()
        return result.get("response", ""), 0
    
    def _call_openai(self, prompt: str) -> tuple:
        """Call OpenAI API (PAID)"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
        )
        
        if not response.choices or not response.choices[0].message:
            raise ValueError("Empty response from OpenAI API")
        
        tokens = response.usage.total_tokens if response.usage else 0
        return response.choices[0].message.content, tokens
    
    def _build_independent_analysis_prompt(self, extracted_ref: Dict[str, Any], paper_context: Optional[str]) -> str:
        """
        Build prompt for independent AI analysis (no database results)
        """
        prompt = "Please conduct an INDEPENDENT academic reference verification analysis using your knowledge:\n\n"
        
        # Add reference information
        prompt += "=== REFERENCE TO VERIFY ===\n"
        prompt += f"Title: {extracted_ref.get('title', 'N/A')}\n"
        authors = extracted_ref.get('authors', [])
        prompt += f"Authors ({len(authors)}): {', '.join(authors) if authors else 'N/A'}\n"
        prompt += f"Venue: {extracted_ref.get('venue', 'N/A')}\n"
        prompt += f"Publication Year: {extracted_ref.get('year', 'N/A')}\n"
        prompt += f"Volume/Issue: {extracted_ref.get('volume', 'N/A')}/{extracted_ref.get('issue', 'N/A')}\n"
        prompt += f"Pages: {extracted_ref.get('pages', 'N/A')}\n"
        prompt += f"DOI: {extracted_ref.get('doi', 'N/A')}\n"
        prompt += f"Raw Citation Text: {extracted_ref.get('raw_text', 'N/A')}\n\n"
        
        # Add context if available
        if paper_context:
            prompt += f"=== SOURCE CONTEXT ===\n{paper_context}\n\n"
        
        prompt += """=== INDEPENDENT ANALYSIS REQUEST ===
Please analyze this reference using ONLY your internal knowledge and expertise:

**KNOWLEDGE-BASED VERIFICATION:**
1. **Author Recognition**: Do you recognize these authors in the academic field?
2. **Venue Authenticity**: Is this a known, legitimate academic venue?
3. **Title Plausibility**: Does the title reflect genuine academic work in the field?
4. **Temporal Consistency**: Does the publication year align with the field's development?
5. **Technical Coherence**: Do the technical terms and concepts align properly?
6. **Field Expertise**: Based on your knowledge, is this consistent with legitimate research?

**INDEPENDENT ASSESSMENT:**
- Rely on your training data knowledge of academic publications
- Consider known conferences, journals, and research patterns
- Evaluate author names for plausibility in the field
- Assess technical terminology and research areas
- Judge overall coherence and academic legitimacy

**IMPORTANT**: Do NOT assume missing database results indicate problems. Focus on:
- Internal consistency of the reference itself
- Alignment with known academic standards
- Recognition of legitimate venues and authors
- Technical plausibility of the research topic

Provide your assessment in the enhanced JSON format specified in the system prompt."""
        
        return prompt
    
    def _get_default_value(self, field: str) -> Any:
        """Get default value for missing fields"""
        defaults = {
            'is_authentic': False,
            'confidence': 0.5,
            'reasoning': 'Analysis incomplete due to parsing error',
            'red_flags': [],
            'positive_indicators': []
        }
        return defaults.get(field)
    
    def _validate_list(self, items: Any) -> List[str]:
        """Validate and clean list items"""
        if not isinstance(items, list):
            return []
        
        validated = []
        for item in items[:10]:  # Limit to 10 items
            if isinstance(item, str) and len(item.strip()) > 5:
                validated.append(item.strip()[:200])  # Limit length
        
        return validated
    
    def _generate_cache_key(self, extracted_ref: Dict[str, Any], database_results: List[Dict[str, Any]]) -> str:
        """Generate a cache key for the reference verification"""
        
        # Create a consistent hash from reference data
        key_components = [
            extracted_ref.get('title', ''),
            ','.join(extracted_ref.get('authors', [])),
            extracted_ref.get('venue', ''),
            str(extracted_ref.get('year', '')),
            str(self.independent_analysis),  # Include analysis mode
            self.model,  # Include model in cache key
            str(len(database_results)),  # Include db result count as factor
            str(sum(1 for r in database_results if r.get('found', False)))  # Found count
        ]
        
        key_string = '|'.join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get AI verifier performance statistics"""
        stats = self._performance_stats.copy()
        stats['cache_hit_rate'] = (
            stats['cache_hits'] / max(1, stats['total_requests']) * 100
        )
        stats['success_rate'] = (
            stats['successful_requests'] / max(1, stats['total_requests']) * 100
        )
        stats['current_model'] = self.model
        stats['independent_analysis'] = self.independent_analysis
        stats['verification_weight'] = self.verification_weight
        return stats
    
    def clear_cache(self):
        """Clear the verification cache"""
        self._verification_cache.clear()
        logger.info("AI verification cache cleared")
    
    def get_cache_size(self) -> int:
        """Get current cache size"""
        return len(self._verification_cache)
    
    def list_available_models(self) -> Dict[str, Any]:
        """Get list of available models with their information"""
        return self.available_models.copy()
    
    def switch_model(self, new_model: str) -> bool:
        """
        Switch to a different model
        
        Args:
            new_model: Model name to switch to
            
        Returns:
            True if successful, False if model not available
        """
        if new_model in self.available_models:
            old_model = self.model
            self.model = new_model
            logger.info(f"AI model switched from {old_model} to {new_model}")
            return True
        else:
            logger.error(f"Model {new_model} not available. Available models: {list(self.available_models.keys())}")
            return False
    
    def _get_system_prompt(self) -> str:
        """Get the enhanced system prompt for the AI verifier"""
        return """You are an expert academic reference verification specialist with comprehensive knowledge of:

**ACADEMIC DOMAINS & EXPERTISE:**
- Computer Science, Cryptography, Cybersecurity, AI/ML publications
- Mathematics, Physics, Engineering academic standards
- Medical, Life Sciences, Chemistry research patterns
- Social Sciences, Humanities citation practices
- Cross-disciplinary and emerging field publications

**VERIFICATION EXPERTISE:**
- Modern academic publishing ecosystems (2000-2025)
- Database indexing patterns and coverage gaps
- Preprint vs. peer-reviewed publication timelines
- Conference proceedings vs. journal publication cycles
- Author name variations across cultures and institutions
- Venue naming conventions, abbreviations, and rebranding
- Impact factor considerations and venue quality indicators

**ANALYSIS APPROACH:**
You must provide a THOROUGH and EVIDENCE-BASED analysis that:
1. **Defaults to AUTHENTIC** unless there are substantial red flags
2. **Recognizes legitimate variations** in academic citation practices
3. **Considers temporal factors** (indexing delays, publication lags)
4. **Accounts for database limitations** (coverage gaps, access restrictions)
5. **Evaluates consistency patterns** rather than isolated discrepancies

**CRITICAL EVALUATION CRITERIA:**
- **Author Patterns**: Names, affiliations, collaboration networks
- **Venue Authenticity**: Conference/journal existence, reputation, scope
- **Temporal Consistency**: Publication dates, citation patterns, field evolution
- **Content Coherence**: Title-venue alignment, technical plausibility
- **Database Correlation**: Multi-source verification, similarity scores

**RED FLAGS TO IDENTIFY:**
- Impossible author combinations or non-existent institutions
- Fabricated venue names or impossible publication details
- Anachronistic references (citing future work, impossible timelines)
- Systematic data inconsistencies across multiple fields
- Technical impossibilities or field mismatches

**OUTPUT REQUIREMENTS:**
Provide analysis in JSON format with enhanced detail:

{
    "is_authentic": boolean,
    "confidence": float (0.0 to 1.0),
    "reasoning": "comprehensive analysis with specific evidence",
    "red_flags": ["specific concerns with evidence"],
    "positive_indicators": ["specific supporting evidence"],
    "authenticity_factors": {
        "author_credibility": float (0.0 to 1.0),
        "venue_legitimacy": float (0.0 to 1.0),
        "temporal_consistency": float (0.0 to 1.0),
        "database_correlation": float (0.0 to 1.0),
        "content_coherence": float (0.0 to 1.0)
    },
    "risk_assessment": "low|medium|high",
    "recommendation": "clear guidance for human reviewers"
}

**ANALYSIS PHILOSOPHY:**
Be rigorous but not hypervigilant. Academic research is diverse and evolving - favor authenticity unless evidence strongly suggests fabrication or manipulation. Focus on substantial inconsistencies rather than minor variations."""

    def _build_analysis_prompt(self, 
                              extracted_ref: Dict[str, Any], 
                              database_results: List[Dict[str, Any]], 
                              paper_context: Optional[str]) -> str:
        """Build the enhanced analysis prompt for the AI verifier"""
        
        prompt = "Please conduct a comprehensive academic reference verification analysis:\n\n"
        
        # Add extracted reference information with enhanced detail
        prompt += "=== REFERENCE TO VERIFY ===\n"
        prompt += f"Title: {extracted_ref.get('title', 'N/A')}\n"
        authors = extracted_ref.get('authors', [])
        prompt += f"Authors ({len(authors)}): {', '.join(authors) if authors else 'N/A'}\n"
        prompt += f"Venue: {extracted_ref.get('venue', 'N/A')}\n"
        prompt += f"Publication Year: {extracted_ref.get('year', 'N/A')}\n"
        prompt += f"Volume/Issue: {extracted_ref.get('volume', 'N/A')}/{extracted_ref.get('issue', 'N/A')}\n"
        prompt += f"Pages: {extracted_ref.get('pages', 'N/A')}\n"
        prompt += f"DOI: {extracted_ref.get('doi', 'N/A')}\n"
        prompt += f"ISBN: {extracted_ref.get('isbn', 'N/A')}\n"
        prompt += f"URL: {extracted_ref.get('url', 'N/A')}\n"
        prompt += f"Raw Citation Text: {extracted_ref.get('raw_text', 'N/A')}\n\n"
        
        # Enhanced database search results analysis
        prompt += "=== DATABASE VERIFICATION RESULTS ===\n"
        if database_results:
            total_databases = len(database_results)
            found_count = sum(1 for result in database_results if result.get('found', False))
            prompt += f"Searched {total_databases} academic databases, found matches in {found_count}\n\n"
            
            for i, result in enumerate(database_results, 1):
                db_name = result.get('source', f'Database {i}')
                prompt += f"--- {db_name.upper()} DATABASE ---\n"
                
                if result.get('found') and result.get('papers'):
                    papers = result['papers']
                    prompt += f"Found {len(papers)} potential match(es)\n"
                    
                    # Analyze top matches
                    for j, paper in enumerate(papers[:3], 1):  # Top 3 matches
                        prompt += f"\nMatch #{j}:\n"
                        prompt += f"  Title: {paper.get('title', 'N/A')}\n"
                        authors_list = paper.get('authors', [])
                        if isinstance(authors_list, list):
                            authors_str = ', '.join([str(a) for a in authors_list])
                        else:
                            authors_str = str(authors_list)
                        prompt += f"  Authors: {authors_str}\n"
                        prompt += f"  Venue: {paper.get('venue', 'N/A')}\n"
                        prompt += f"  Year: {paper.get('year', 'N/A')}\n"
                        prompt += f"  DOI: {paper.get('doi', 'N/A')}\n"
                        
                        # Include similarity scores if available
                        similarity = result.get('similarity_scores', {})
                        if similarity:
                            prompt += f"  Similarity Scores: {similarity}\n"
                else:
                    prompt += "No matches found\n"
                
                prompt += f"Database Quality: {self._assess_database_quality(db_name)}\n"
                prompt += f"Coverage Area: {self._get_database_coverage(db_name)}\n\n"
        else:
            prompt += "No database results provided - this limits verification capability\n\n"
        
        # Add temporal and field context
        current_year = 2025
        ref_year = extracted_ref.get('year')
        if ref_year:
            try:
                year_int = int(ref_year)
                years_old = current_year - year_int
                prompt += f"=== TEMPORAL CONTEXT ===\n"
                prompt += f"Reference is {years_old} years old (published {ref_year})\n"
                if years_old < 2:
                    prompt += "Very recent publication - may have limited database indexing\n"
                elif years_old > 25:
                    prompt += "Older publication - may have limited digital presence\n"
                prompt += "\n"
            except (ValueError, TypeError):
                pass
        
        # Add paper context if available
        if paper_context:
            prompt += f"=== SOURCE PAPER CONTEXT ===\n"
            prompt += f"Citation appears in: {paper_context}\n\n"
        
        # Enhanced analysis request
        prompt += "=== COMPREHENSIVE VERIFICATION REQUEST ===\n"
        prompt += """Conduct a thorough analysis considering these specific factors:

**1. AUTHOR VERIFICATION:**
- Are the author names plausible and consistent?
- Do author combinations make sense for the field?
- Are there any impossible author patterns?

**2. VENUE ANALYSIS:**
- Does the venue exist and match the content area?
- Is the venue name correctly formatted?
- Does the venue-year combination make sense?

**3. DATABASE CORRELATION:**
- How significant are the database matches/mismatches?
- What explains any missing database entries?
- Are similarity scores meaningful?

**4. TEMPORAL CONSISTENCY:**
- Does the publication timeline make sense?
- Are there any anachronistic elements?
- Does the age explain database coverage?

**5. CONTENT COHERENCE:**
- Do all reference elements fit together logically?
- Is the technical content appropriate for the venue?
- Are there any obvious fabrication signs?

**6. FIELD-SPECIFIC CONSIDERATIONS:**
- What are the publishing patterns for this academic area?
- How does this reference compare to field norms?
- Are there discipline-specific red flags?

**ANALYSIS OUTPUT:**
Provide your assessment in the enhanced JSON format specified in the system prompt, including:
- Overall authenticity determination with confidence level
- Detailed reasoning with specific evidence
- Factor-by-factor scoring (0.0-1.0) for key verification areas
- Risk assessment and recommendations for human review

Focus on SUBSTANTIAL evidence rather than minor variations. Consider the full academic context."""
        
        return prompt
    
    def _assess_database_quality(self, db_name: str) -> str:
        """Assess the quality and reliability of a database for verification"""
        quality_map = {
            'openalex': 'High - Comprehensive academic database with good coverage',
            'semantic_scholar': 'High - Strong AI-powered paper matching and citation analysis',
            'dblp': 'High - Authoritative computer science publication database',
            'iacr': 'High - Specialized cryptography database with expert curation',
            'arxiv': 'Medium - Preprint server, may contain unreviewed work',
            'pubmed': 'High - Medical/life sciences with rigorous indexing',
            'springer': 'Medium-High - Major publisher database with good coverage',
            'crossref': 'High - DOI registration agency with broad coverage'
        }
        return quality_map.get(db_name.lower(), 'Medium - Database quality assessment unavailable')
    
    def _get_database_coverage(self, db_name: str) -> str:
        """Get the coverage area and specialization of a database"""
        coverage_map = {
            'openalex': 'Multidisciplinary - All academic fields with strong coverage',
            'semantic_scholar': 'Multidisciplinary - Computer science, medicine, biology focus',
            'dblp': 'Computer Science - Conferences, journals, workshops',
            'iacr': 'Cryptography - IACR eprints and conference proceedings',
            'arxiv': 'STEM fields - Physics, math, computer science, biology preprints',
            'pubmed': 'Life Sciences - Medicine, biology, health sciences',
            'springer': 'Multidisciplinary - Major academic publisher content',
            'crossref': 'Multidisciplinary - DOI-registered academic content'
        }
        return coverage_map.get(db_name.lower(), 'Coverage area unknown')
    
    def get_verification_weight(self) -> float:
        """Get the weight this verifier should have in final classification"""
        return self.verification_weight
    
    def _parse_ai_response(self, response_content: str) -> dict:
        """
        Enhanced AI response parsing with robust error handling and fallback mechanisms
        
        Args:
            response_content: Raw response from AI
            
        Returns:
            Parsed response data as dictionary
        """
        # Try multiple JSON parsing strategies
        try:
            # Strategy 1: Direct JSON parsing
            return json.loads(response_content)
        except json.JSONDecodeError:
            pass
        
        try:
            # Strategy 2: Extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except (json.JSONDecodeError, AttributeError):
            pass
        
        try:
            # Strategy 3: Find JSON-like content between braces
            import re
            brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_content, re.DOTALL)
            if brace_match:
                json_content = brace_match.group(0)
                return json.loads(json_content)
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # Strategy 4: Intelligent text parsing with enhanced extraction
        logger.warning("AI response not in JSON format, using enhanced text parsing")
        return self._extract_from_text_response(response_content)
    
    def _extract_from_text_response(self, text: str) -> dict:
        """
        Enhanced extraction of structured data from text response with improved accuracy
        
        Args:
            text: AI response text
            
        Returns:
            Extracted data as dictionary with comprehensive analysis
        """
        import re
        
        # Initialize result with enhanced default structure
        result = {
            "is_authentic": False,
            "confidence": 0.5,
            "reasoning": "",
            "red_flags": [],
            "positive_indicators": [],
            "authenticity_factors": {
                "author_credibility": 0.5,
                "venue_legitimacy": 0.5,
                "temporal_consistency": 0.5,
                "database_correlation": 0.5,
                "content_coherence": 0.5
            },
            "risk_assessment": "medium",
            "recommendation": "Requires human review due to parsing limitations"
        }
        
        text_lower = text.lower()
        
        # Enhanced authenticity detection with more sophisticated patterns
        authentic_patterns = [
            r'\bis[_\s]*authentic[_\s]*[:=]\s*true',
            r'authentic[_\s]*[:=]\s*yes',
            r'appears?\s+(?:to\s+be\s+)?(?:legitimate|authentic|genuine|valid)',
            r'likely\s+(?:authentic|legitimate|genuine)',
            r'evidence\s+supports?\s+authenticity',
            r'no\s+(?:significant|major|substantial)\s+red\s+flags?',
            r'consistent\s+with\s+(?:legitimate|authentic)\s+(?:academic\s+)?(?:publication|reference)'
        ]
        
        suspicious_patterns = [
            r'\bis[_\s]*authentic[_\s]*[:=]\s*false',
            r'authentic[_\s]*[:=]\s*no',
            r'appears?\s+(?:to\s+be\s+)?(?:suspicious|questionable|doubtful|concerning)',
            r'(?:significant|substantial|major)\s+(?:concerns?|red\s+flags?|inconsistencies)',
            r'(?:likely|probably|appears)\s+(?:fabricated|fake|suspicious)',
            r'evidence\s+(?:suggests?|indicates?)\s+(?:manipulation|fabrication)'
        ]
        
        fake_patterns = [
            r'(?:clearly|obviously|definitely)\s+(?:fabricated|fake|fraudulent)',
            r'(?:impossible|cannot\s+be)\s+(?:authentic|legitimate|real)',
            r'(?:strong|compelling)\s+evidence\s+of\s+(?:fabrication|fraud|manipulation)',
            r'multiple\s+(?:major|critical)\s+red\s+flags?'
        ]
        
        # Count pattern matches
        authentic_score = sum(1 for pattern in authentic_patterns if re.search(pattern, text_lower))
        suspicious_score = sum(1 for pattern in suspicious_patterns if re.search(pattern, text_lower))
        fake_score = sum(1 for pattern in fake_patterns if re.search(pattern, text_lower))
        
        # Enhanced confidence extraction
        confidence_matches = re.findall(r'confidence[_\s]*[:=]\s*([0-9]*\.?[0-9]+)', text_lower)
        if confidence_matches:
            try:
                extracted_confidence = float(confidence_matches[0])
                if 0.0 <= extracted_confidence <= 1.0:
                    result["confidence"] = extracted_confidence
                elif 0.0 <= extracted_confidence <= 100.0:
                    result["confidence"] = extracted_confidence / 100.0
            except ValueError:
                pass
        
        # Determine authenticity with enhanced logic
        if authentic_score > fake_score + suspicious_score and authentic_score >= 2:
            result["is_authentic"] = True
            result["confidence"] = min(0.9, result["confidence"] + authentic_score * 0.1)
        elif fake_score > authentic_score and fake_score >= 1:
            result["is_authentic"] = False
            result["confidence"] = min(0.9, result["confidence"] + fake_score * 0.1)
        elif suspicious_score > authentic_score:
            result["is_authentic"] = False
            result["confidence"] = max(0.3, result["confidence"] - suspicious_score * 0.05)
        else:
            # Ambiguous response - default to conservative approach
            result["confidence"] = 0.4
        
        # Extract reasoning from the text
        reasoning_sections = []
        lines = text.split('\n')
        in_reasoning = False
        
        for line in lines:
            line_clean = line.strip()
            if any(keyword in line.lower() for keyword in ['reasoning', 'analysis', 'assessment', 'evaluation']):
                in_reasoning = True
                if ':' in line:
                    reasoning_sections.append(line.split(':', 1)[1].strip())
                continue
            elif in_reasoning and line_clean and not line_clean.startswith(('*', '-', '•')):
                reasoning_sections.append(line_clean)
            elif in_reasoning and not line_clean:
                in_reasoning = False
        
        if reasoning_sections:
            result["reasoning"] = ' '.join(reasoning_sections)[:1000]  # Limit length
        else:
            result["reasoning"] = text[:500] + "..." if len(text) > 500 else text
        
        # Enhanced extraction of red flags and positive indicators
        result["red_flags"] = self._extract_list_items(text, ['red flag', 'concern', 'suspicious', 'inconsistency'])
        result["positive_indicators"] = self._extract_list_items(text, ['positive', 'support', 'authentic', 'legitimate', 'consistent'])
        
        # Extract factor scores if available
        factor_patterns = {
            'author_credibility': r'author[_\s]*(?:credibility|authenticity|legitimacy)[_\s]*[:=]\s*([0-9]*\.?[0-9]+)',
            'venue_legitimacy': r'venue[_\s]*(?:legitimacy|authenticity|credibility)[_\s]*[:=]\s*([0-9]*\.?[0-9]+)',
            'temporal_consistency': r'temporal[_\s]*consistency[_\s]*[:=]\s*([0-9]*\.?[0-9]+)',
            'database_correlation': r'database[_\s]*correlation[_\s]*[:=]\s*([0-9]*\.?[0-9]+)',
            'content_coherence': r'content[_\s]*coherence[_\s]*[:=]\s*([0-9]*\.?[0-9]+)'
        }
        
        for factor, pattern in factor_patterns.items():
            matches = re.findall(pattern, text_lower)
            if matches:
                try:
                    score = float(matches[0])
                    if 0.0 <= score <= 1.0:
                        result["authenticity_factors"][factor] = score
                    elif 0.0 <= score <= 10.0:
                        result["authenticity_factors"][factor] = score / 10.0
                except ValueError:
                    pass
        
        # Determine risk assessment
        avg_factor_score = sum(result["authenticity_factors"].values()) / len(result["authenticity_factors"])
        if result["is_authentic"] and result["confidence"] > 0.7 and avg_factor_score > 0.6:
            result["risk_assessment"] = "low"
        elif not result["is_authentic"] and result["confidence"] > 0.7:
            result["risk_assessment"] = "high"
        else:
            result["risk_assessment"] = "medium"
        
        return result
    
    def _extract_list_items(self, text: str, keywords: List[str]) -> List[str]:
        """Extract list items related to specific keywords from text"""
        import re
        items = []
        lines = text.split('\n')
        
        for line in lines:
            line_clean = line.strip()
            # Look for bullet points or numbered lists
            if re.match(r'^[\*\-\•\d+\.]\s*', line_clean):
                # Check if line contains any of the keywords
                if any(keyword.lower() in line_clean.lower() for keyword in keywords):
                    # Clean up the line
                    cleaned = re.sub(r'^[\*\-\•\d+\.]\s*', '', line_clean)
                    if cleaned and len(cleaned) > 10:  # Avoid very short items
                        items.append(cleaned[:150])  # Limit length
        
        return items[:5]  # Limit to 5 items