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

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

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

class AIReferenceVerifier:
    """
    Enhanced AI-powered reference verifier with model selection and independent analysis
    Analyzes reference authenticity using advanced natural language understanding
    with robust error handling, caching, and performance optimization
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize enhanced AI verifier with model selection support
        
        Args:
            api_key: OpenAI API key (if None, will try environment variable)
            model: OpenAI model to use (default: gpt-4o-mini)
        """
        self.client = None
        self._verification_cache = {}  # Simple in-memory cache
        self._performance_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'cache_hits': 0,
            'average_response_time': 0.0,
            'total_tokens_used': 0,
            'models_used': {}
        }
        self.available_models = {}
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
                
            # Load model configuration
            self.available_models = ai_config.get("available_models", {})
            self.model = ai_config.get("model", model)
            self.fallback_model = ai_config.get("fallback_model", "gpt-3.5-turbo")
            self.enable_model_fallback = ai_config.get("enable_model_fallback", True)
            
            # Load performance settings
            self.timeout = ai_config.get("timeout", 45)
            self.max_tokens = ai_config.get("max_tokens", 2500)
            self.temperature = ai_config.get("temperature", 0.1)
            self.verification_weight = ai_config.get("verification_weight", 0.35)
            self.independent_analysis = ai_config.get("independent_analysis", True)
            
            # Validate selected model
            if self.model not in self.available_models and self.available_models:
                logger.warning(f"Selected model '{self.model}' not in available models. Using fallback.")
                self.model = self.fallback_model
            
            # Log model selection
            model_info = self.available_models.get(self.model, {})
            logger.info(f"AI verifier initialized with model: {self.model} ({model_info.get('name', 'Unknown')})")
            if self.independent_analysis:
                logger.info("AI independent analysis enabled - AI will make decisions based on its own knowledge")
            
        except ImportError:
            # Fallback if config not available
            self.model = model
            self.fallback_model = "gpt-3.5-turbo"
            self.timeout = 45
            self.max_tokens = 2500
            self.temperature = 0.1
            self.verification_weight = 0.35
            self.independent_analysis = True
        
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI library not available. AI verification disabled.")
            return
            
        # Get API key from parameter, config, or environment
        self.api_key = api_key
        if not self.api_key:
            try:
                from config import DATABASE_CONFIG
                self.api_key = DATABASE_CONFIG.get("ai_verification", {}).get("openai_api_key")
            except ImportError:
                pass
        
        if not self.api_key:
            self.api_key = os.getenv('OPENAI_API_KEY')
        
        if not self.api_key:
            logger.warning("No OpenAI API key provided. AI verification disabled.")
            return
            
        try:
            self.client = openai.OpenAI(api_key=self.api_key)
            # Note: Success logging is handled by the classifier
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
        """Get information about the current model"""
        model_info = self.available_models.get(self.model, {})
        return {
            "current_model": self.model,
            "model_name": model_info.get("name", "Unknown"),
            "description": model_info.get("description", "No description available"),
            "cost_level": model_info.get("cost_level", "unknown"),
            "supports_json": model_info.get("supports_json", False),
            "fallback_model": self.fallback_model,
            "independent_analysis": self.independent_analysis,
            "verification_weight": self.verification_weight
        }
    
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
        Execute AI request with model fallback and error handling
        """
        max_retries = 3
        retry_delay = 1
        current_model = self.model
        
        for attempt in range(max_retries):
            try:
                # Prepare request parameters with intelligent model selection
                request_params = {
                    "model": current_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": self._get_system_prompt()
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
                
                # Add JSON response format only for compatible models
                model_info = self.available_models.get(current_model, {})
                if model_info.get("supports_json", False):
                    request_params["response_format"] = {"type": "json_object"}
                
                # Make API call with timeout
                response = self.client.chat.completions.create(
                    timeout=self.timeout,
                    **request_params
                )
                
                # Validate response
                if not response.choices or not response.choices[0].message:
                    raise ValueError("Empty response from OpenAI API")
                
                response_content = response.choices[0].message.content
                if not response_content:
                    raise ValueError("Empty content in OpenAI response")
                
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
                self._performance_stats['total_tokens_used'] += response.usage.total_tokens if response.usage else 0
                
                # Track model usage
                if current_model not in self._performance_stats['models_used']:
                    self._performance_stats['models_used'][current_model] = 0
                self._performance_stats['models_used'][current_model] += 1
                
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
                        'model': current_model,
                        'model_fallback_used': current_model != self.model,
                        'tokens_used': response.usage.total_tokens if response.usage else 0,
                        'analysis_version': '3.0',
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
                
                # Handle model fallback
                if (("response_format" in error_msg or "model" in error_msg.lower()) 
                    and current_model != self.fallback_model 
                    and self.enable_model_fallback 
                    and attempt == 0):
                    logger.warning(f"Model {current_model} failed, trying fallback model {self.fallback_model}")
                    current_model = self.fallback_model
                    continue
                
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