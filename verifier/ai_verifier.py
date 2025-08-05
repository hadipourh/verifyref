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
    AI-powered reference verifier using ChatGPT API
    Analyzes reference authenticity using advanced natural language understanding
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize AI verifier
        
        Args:
            api_key: OpenAI API key (if None, will try environment variable)
            model: OpenAI model to use (default: gpt-4)
        """
        self.client = None
        
        # Check if AI verification is enabled first
        try:
            from config import DATABASE_CONFIG
            ai_config = DATABASE_CONFIG.get("ai_verification", {})
            
            # If AI is disabled, don't initialize anything
            if not ai_config.get("enabled", True):
                logger.info("AI verification disabled in configuration - skipping initialization")
                return
                
            self.model = ai_config.get("model", model)
            self.timeout = ai_config.get("timeout", 30)
            self.max_tokens = ai_config.get("max_tokens", 1500)
            self.temperature = ai_config.get("temperature", 0.1)
            self.verification_weight = ai_config.get("verification_weight", 0.25)
            
        except ImportError:
            # Fallback if config not available
            self.model = model
            self.timeout = 30
            self.max_tokens = 1500
            self.temperature = 0.1
            self.verification_weight = 0.25
        
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
            if not ai_config.get("enabled", True):
                return False
        except ImportError:
            pass
            
        return self.client is not None
    
    def verify_reference(self, 
                        extracted_ref: Dict[str, Any], 
                        database_results: List[Dict[str, Any]], 
                        paper_context: Optional[str] = None) -> Optional[AIVerificationResult]:
        """
        Verify reference authenticity using AI analysis
        
        Args:
            extracted_ref: Extracted reference data
            database_results: Results from database searches
            paper_context: Optional context about the source paper
            
        Returns:
            AIVerificationResult or None if verification failed
        """
        if not self.is_available():
            return None
            
        try:
            # Prepare the analysis prompt
            prompt = self._build_analysis_prompt(extracted_ref, database_results, paper_context)
            
            # Get AI analysis
            # Prepare request parameters
            request_params = {
                "model": self.model,
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
                "temperature": self.temperature,  # Use configured temperature
                "max_tokens": self.max_tokens,   # Use configured max tokens
            }
            
            # Add JSON response format only for compatible models
            if self.model in ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo-1106", "gpt-4-1106-preview"]:
                request_params["response_format"] = {"type": "json_object"}
            
            response = self.client.chat.completions.create(**request_params)
            
            # Parse the response (handle both JSON and text responses)
            response_content = response.choices[0].message.content
            result_data = self._parse_ai_response(response_content)
            
            return AIVerificationResult(
                is_authentic=result_data.get('is_authentic', False),
                confidence=float(result_data.get('confidence', 0.0)),
                reasoning=result_data.get('reasoning', ''),
                red_flags=result_data.get('red_flags', []),
                positive_indicators=result_data.get('positive_indicators', []),
                metadata={
                    'model': self.model,
                    'tokens_used': response.usage.total_tokens if response.usage else 0,
                    'analysis_version': '1.0'
                }
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"AI response content: {response.choices[0].message.content}")
            return None
        except Exception as e:
            error_msg = str(e)
            if "response_format" in error_msg and "json_object" in error_msg:
                logger.error(f"Model {self.model} does not support JSON response format. Consider using gpt-4o-mini or gpt-3.5-turbo-1106")
            else:
                logger.error(f"AI verification failed: {e}")
            return None
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the AI verifier"""
        return """You are a balanced academic reference verification specialist with deep knowledge of:
- Academic publishing standards and practices
- Common citation formats and conventions
- Legitimate reasons for database mismatches (new papers, indexing delays, coverage gaps)
- Author name variations and institutional affiliations
- Venue naming conventions and abbreviations
- Publication timeline patterns

Your task is to provide a BALANCED analysis of reference authenticity, giving equal weight to evidence supporting AND questioning authenticity.

IMPORTANT GUIDELINES:
- Default to AUTHENTIC unless there are clear red flags
- Consider legitimate reasons for database mismatches (indexing delays, new publications, database coverage)
- Author name variations are NORMAL and expected
- Minor inconsistencies often reflect legitimate citation practices
- Be CAREFUL not to flag legitimate references as suspicious

IMPORTANT: Provide your analysis in JSON format if possible, otherwise use clear structured text.

Preferred JSON format:
{
    "is_authentic": boolean,
    "confidence": float (0.0 to 1.0),
    "reasoning": "detailed explanation of your analysis",
    "red_flags": ["list of genuine concerns only"],
    "positive_indicators": ["list of evidence supporting authenticity"],
    "overall_assessment": "brief summary of your conclusion"
}

If JSON format is not supported, structure your response clearly with:
- AUTHENTICITY: [True/False]
- CONFIDENCE: [0.0-1.0]
- REASONING: [detailed explanation]
- RED FLAGS: [list genuine concerns only]
- POSITIVE INDICATORS: [list supporting evidence]

Be analytical but BALANCED. Favor authenticity unless there are clear signs of fabrication or manipulation.
Avoid false positives - legitimate academic references should be classified as authentic."""

    def _build_analysis_prompt(self, 
                              extracted_ref: Dict[str, Any], 
                              database_results: List[Dict[str, Any]], 
                              paper_context: Optional[str]) -> str:
        """Build the analysis prompt for the AI verifier"""
        
        prompt = "Please analyze the following reference for authenticity:\n\n"
        
        # Add extracted reference information
        prompt += "=== EXTRACTED REFERENCE ===\n"
        prompt += f"Title: {extracted_ref.get('title', 'N/A')}\n"
        prompt += f"Authors: {', '.join(extracted_ref.get('authors', []))}\n"
        prompt += f"Venue: {extracted_ref.get('venue', 'N/A')}\n"
        prompt += f"Year: {extracted_ref.get('year', 'N/A')}\n"
        prompt += f"Pages: {extracted_ref.get('pages', 'N/A')}\n"
        prompt += f"Volume: {extracted_ref.get('volume', 'N/A')}\n"
        prompt += f"DOI: {extracted_ref.get('doi', 'N/A')}\n"
        prompt += f"Raw Citation: {extracted_ref.get('raw_text', 'N/A')}\n\n"
        
        # Add database search results
        prompt += "=== DATABASE SEARCH RESULTS ===\n"
        if database_results:
            for i, result in enumerate(database_results, 1):
                prompt += f"\n--- Database {i}: {result.get('source', 'Unknown')} ---\n"
                prompt += f"Found: {result.get('found', False)}\n"
                
                if result.get('found') and result.get('papers'):
                    best_paper = result['papers'][0] if result['papers'] else {}
                    prompt += f"Best Match Title: {best_paper.get('title', 'N/A')}\n"
                    prompt += f"Best Match Authors: {', '.join([str(a) for a in best_paper.get('authors', [])])}\n"
                    prompt += f"Best Match Venue: {best_paper.get('venue', 'N/A')}\n"
                    prompt += f"Best Match Year: {best_paper.get('year', 'N/A')}\n"
                    prompt += f"Similarity Scores: {result.get('similarity_scores', {})}\n"
                else:
                    prompt += "No matches found in this database\n"
        else:
            prompt += "No database results provided\n"
        
        # Add paper context if available
        if paper_context:
            prompt += f"\n=== SOURCE PAPER CONTEXT ===\n"
            prompt += f"{paper_context}\n"
        
        prompt += "\n=== ANALYSIS REQUEST ===\n"
        prompt += """Please analyze this reference for authenticity considering:

1. **Internal Consistency**: Do all parts of the reference make sense together?
2. **Database Validation**: How well do the database results support the reference?
3. **Author Patterns**: Are author names consistent and plausible?
4. **Venue Information**: Is the venue appropriate for the claimed content?
5. **Publication Timeline**: Does the year make sense in context?
6. **Data Quality**: Are there signs of fabrication or manipulation?

Consider both legitimate reasons for database mismatches (e.g., new papers, database coverage gaps, name variations) and potential red flags (e.g., impossible author combinations, non-existent venues, anachronistic references).

Provide your analysis in the requested JSON format."""
        
        return prompt
    
    def get_verification_weight(self) -> float:
        """Get the weight this verifier should have in final classification"""
        return self.verification_weight
    
    def _parse_ai_response(self, response_content: str) -> dict:
        """
        Parse AI response, handling both JSON and text formats
        
        Args:
            response_content: Raw response from AI
            
        Returns:
            Parsed response data as dictionary
        """
        try:
            # Try to parse as JSON first
            return json.loads(response_content)
        except json.JSONDecodeError:
            # If not JSON, try to extract from text response
            logger.warning("AI response not in JSON format, attempting text parsing")
            return self._extract_from_text_response(response_content)
    
    def _extract_from_text_response(self, text: str) -> dict:
        """
        Extract structured data from text response when JSON format fails
        
        Args:
            text: AI response text
            
        Returns:
            Extracted data as dictionary
        """
        # Default response structure
        result = {
            "is_authentic": False,
            "confidence": 0.5,
            "reasoning": text[:500] + "..." if len(text) > 500 else text,
            "red_flags": [],
            "positive_indicators": [],
            "overall_assessment": "Analysis from text response"
        }
        
        # Try to extract key information from text
        text_lower = text.lower()
        
        # Determine authenticity based on keywords
        authentic_indicators = ["authentic", "legitimate", "valid", "genuine", "real"]
        suspicious_indicators = ["suspicious", "concerning", "questionable", "doubtful"]
        fake_indicators = ["fabricated", "fake", "fraudulent", "manipulated", "false"]
        
        authentic_count = sum(1 for word in authentic_indicators if word in text_lower)
        suspicious_count = sum(1 for word in suspicious_indicators if word in text_lower)
        fake_count = sum(1 for word in fake_indicators if word in text_lower)
        
        if authentic_count > fake_count + suspicious_count:
            result["is_authentic"] = True
            result["confidence"] = min(0.8, 0.5 + authentic_count * 0.1)
        elif fake_count > authentic_count:
            result["is_authentic"] = False
            result["confidence"] = min(0.8, 0.5 + fake_count * 0.1)
        else:
            result["confidence"] = 0.4  # Low confidence for unclear responses
        
        # Extract any obvious red flags or positive indicators from text
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower().strip()
            if any(word in line_lower for word in ["red flag", "concerning", "suspicious"]):
                result["red_flags"].append(line.strip()[:100])
            elif any(word in line_lower for word in ["positive", "legitimate", "authentic"]):
                result["positive_indicators"].append(line.strip()[:100])
        
        return result