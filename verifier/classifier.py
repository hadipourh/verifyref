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


import logging
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from utils.helpers import calculate_text_similarity, normalize_text
from utils.academic_matching import calculate_venue_similarity, calculate_author_similarity
from config import CLASSIFICATION_CONFIG
import config

logger = logging.getLogger(__name__)

class ClassificationResult(Enum):
    """Classification results for reference authenticity"""
    AUTHENTIC = "authentic"
    SUSPICIOUS = "suspicious"
    FAKE = "fake"
    AUTHOR_MANIPULATION = "author_manipulation"  # New: for detecting author swapping fraud
    FABRICATED = "fabricated"  # New: for completely made-up references
    INCONCLUSIVE = "inconclusive"

@dataclass
class VerificationResult:
    """Result of reference verification"""
    classification: ClassificationResult
    confidence: float
    similarity_score: float
    matched_paper: Optional[Dict[str, Any]]
    reasons: List[str]
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert VerificationResult to JSON-serializable dictionary"""
        return {
            'classification': self.classification.value if hasattr(self.classification, 'value') else str(self.classification),
            'confidence': self.confidence,
            'similarity_score': self.similarity_score,
            'matched_paper': self.matched_paper,
            'reasons': self.reasons,
            'details': self.details
        }

class ReferenceClassifier:
    """
    Classifier for determining the authenticity of academic references
    Enhanced with CryptoDB author verification for cryptography papers
    """
    
    def __init__(self, enable_cryptodb: bool = True, enable_ai_verification: bool = True, google_scholar_client=None):
        """
        Initialize the reference classifier
        
        Args:
            enable_cryptodb: Whether to enable CryptoDB author verification (optional)
            enable_ai_verification: Whether to enable AI-powered verification (optional)
            google_scholar_client: GoogleScholarClient instance for secondary validation (optional)
        """
        # Load configuration settings
        self.similarity_threshold = CLASSIFICATION_CONFIG["similarity_threshold"]
        self.suspicious_threshold = CLASSIFICATION_CONFIG.get("suspicious_threshold", 0.2)
        self.title_weight = CLASSIFICATION_CONFIG["title_weight"]
        self.author_weight = CLASSIFICATION_CONFIG["author_weight"]
        self.venue_weight = CLASSIFICATION_CONFIG["venue_weight"]
        self.year_weight = CLASSIFICATION_CONFIG["year_weight"]
        self.max_year_difference = CLASSIFICATION_CONFIG["max_year_difference"]
        
        # Advanced fraud detection settings
        self.enable_fraud_detection = CLASSIFICATION_CONFIG.get("enable_fraud_detection", True)
        self.author_manipulation_threshold = CLASSIFICATION_CONFIG.get("author_manipulation_threshold", 0.85)
        self.multi_database_requirement = CLASSIFICATION_CONFIG.get("multi_database_requirement", False)
        self.single_database_penalty = CLASSIFICATION_CONFIG.get("single_database_penalty", 0.05)
        
        # Classification confidence adjustments
        self.authentic_confidence_boost = CLASSIFICATION_CONFIG.get("authentic_confidence_boost", 0.1)
        self.fraud_confidence_boost = CLASSIFICATION_CONFIG.get("fraud_confidence_boost", 0.1)
        self.inconclusive_threshold = CLASSIFICATION_CONFIG.get("inconclusive_threshold", 0.15)
        
        # Log current rigor level
        rigor_level = CLASSIFICATION_CONFIG.get("rigor_level", "balanced")
        logger.info(f"Verification rigor level: {rigor_level}")
        
        # Optional CryptoDB integration
        self.cryptodb_client = None
        if enable_cryptodb:
            try:
                from .cryptodb_author_client import CryptoDBAuthorClient
                from config import DATABASE_CONFIG
                cryptodb_config = DATABASE_CONFIG.get("cryptodb", {})
                self.cryptodb_client = CryptoDBAuthorClient(
                    enable_cryptodb=cryptodb_config.get("enabled", True),
                    timeout=cryptodb_config.get("timeout", 5)
                )
            except ImportError:
                logger.warning("CryptoDB client not available, author verification will be limited")
            except Exception as e:
                logger.warning(f"Failed to initialize CryptoDB client: {e}")
        
        # Optional AI verification integration
        self.ai_verifier = None
        if enable_ai_verification:
            # Check if AI verification is enabled in config before initializing
            try:
                from config import DATABASE_CONFIG
                ai_config = DATABASE_CONFIG.get("ai_verification", {})
                ai_enabled = ai_config.get("enabled", True)
                
                if not ai_enabled:
                    logger.info("AI verification disabled in configuration")
                else:
                    from .ai_verifier import AIReferenceVerifier
                    self.ai_verifier = AIReferenceVerifier()
                    if self.ai_verifier.is_available():
                        logger.info("AI-powered reference verification enabled")
                    else:
                        logger.info("AI reference verification not available (no API key)")
            except ImportError:
                logger.warning("AI verifier not available")
            except Exception as e:
                logger.warning(f"Failed to initialize AI verifier: {e}")
        
        # Google Scholar client for secondary validation
        self.google_scholar_client = google_scholar_client
        if self.google_scholar_client:
            logger.info("Google Scholar validation enabled for author manipulation detection")
    
    def classify_reference(self, 
                         extracted_ref: Dict[str, Any], 
                         search_results: List[Dict[str, Any]]) -> VerificationResult:
        """
        Classify a reference based on search results from academic databases
        Enhanced with fraud detection for author manipulation and fabricated references
        
        Args:
            extracted_ref: Reference extracted from the document
            search_results: Search results from academic databases
            
        Returns:
            VerificationResult containing classification and details
        """
        if not search_results:
            return VerificationResult(
                classification=ClassificationResult.FABRICATED,  # Changed: No results = likely fabricated
                confidence=0.8,  # High confidence in fabrication if no DB has it
                similarity_score=0.0,
                matched_paper=None,
                reasons=["Reference not found in any academic database - likely fabricated"],
                details={"search_attempted": True, "results_count": 0, "fraud_type": "fabricated"}
            )
        
        # Enhanced fraud detection
        fraud_result = self._detect_fraud(extracted_ref, search_results)
        if fraud_result:
            return fraud_result
        
        # Find the best match among search results
        best_match, best_score = self._find_best_match(extracted_ref, search_results)
        
        # Enhanced multi-database validation
        validation_result = self._validate_across_databases(extracted_ref, search_results, best_match, best_score)
        if validation_result:
            return validation_result
        
        # Standard classification with stricter requirements
        classification, confidence, reasons = self._determine_enhanced_classification(
            extracted_ref, best_match, best_score, search_results
        )
        
        # AI-powered verification for additional insight
        ai_verification = None
        if self.ai_verifier and self.ai_verifier.is_available():
            try:
                ai_verification = self.ai_verifier.verify_reference(
                    extracted_ref, search_results
                )
                if ai_verification:
                    # Incorporate AI analysis into classification
                    classification, confidence, reasons = self._incorporate_ai_analysis(
                        classification, confidence, reasons, ai_verification
                    )
            except Exception as e:
                logger.warning(f"AI verification failed: {e}")
        
        return VerificationResult(
            classification=classification,
            confidence=confidence,
            similarity_score=best_score,
            matched_paper=best_match,
            reasons=reasons,
            details={
                "search_attempted": True,
                "results_count": len(search_results),
                "best_match_index": search_results.index(best_match) if best_match in search_results else -1,
                "similarity_breakdown": self._get_similarity_breakdown(extracted_ref, best_match) if best_match else {},
                "databases_searched": len(set(r.get('source', 'unknown') for r in search_results)),
                "ai_verification": ai_verification.metadata if ai_verification else None
            }
        )
    
    def _find_best_match(self, 
                        extracted_ref: Dict[str, Any], 
                        search_results: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Find the best matching paper from search results
        
        Args:
            extracted_ref: Reference extracted from document
            search_results: List of papers from academic database
            
        Returns:
            Tuple of (best_match_paper, similarity_score)
        """
        if not search_results:
            return None, 0.0
            
        # Use max to find best match in one line
        best_match = max(search_results, key=lambda paper: self._calculate_overall_similarity(extracted_ref, paper))
        best_score = self._calculate_overall_similarity(extracted_ref, best_match)
        
        return best_match, best_score
    
    def _calculate_overall_similarity(self, 
                                    extracted_ref: Dict[str, Any], 
                                    paper: Dict[str, Any]) -> float:
        """
        Calculate weighted similarity score between extracted reference and database paper
        
        Args:
            extracted_ref: Reference from document
            paper: Paper from academic database
            
        Returns:
            Weighted similarity score (0.0 to 1.0)
        """
        # Calculate individual similarity scores
        title_sim = self._calculate_title_similarity(extracted_ref, paper)
        author_sim = self._calculate_author_similarity(extracted_ref, paper)
        venue_sim = self._calculate_venue_similarity(extracted_ref, paper)
        year_sim = self._calculate_year_similarity(extracted_ref, paper)
        
        # Calculate weighted average
        overall_similarity = (
            title_sim * self.title_weight +
            author_sim * self.author_weight +
            venue_sim * self.venue_weight +
            year_sim * self.year_weight
        )
        
        return overall_similarity
    
    def _calculate_title_similarity(self, extracted_ref: Dict[str, Any], paper: Dict[str, Any]) -> float:
        """Calculate title similarity between reference and paper"""
        ref_title = normalize_text(extracted_ref.get('title', ''), preserve_hyphens=True)
        paper_title = normalize_text(paper.get('title', ''), preserve_hyphens=True)
        
        if not ref_title or not paper_title:
            return 0.0
        
        return calculate_text_similarity(ref_title, paper_title)
    
    def _calculate_author_similarity(self, extracted_ref: Dict[str, Any], paper: Dict[str, Any]) -> float:
        """
        Calculate author similarity between reference and paper
        Enhanced with CryptoDB canonical name matching for crypto papers
        """
        ref_authors = extracted_ref.get('authors', [])
        paper_authors = paper.get('authors', [])
        
        if not ref_authors or not paper_authors:
            return 0.0
        
        # Convert paper authors to list of names
        paper_author_names = []
        for author in paper_authors:
            if isinstance(author, dict):
                name = author.get('name', '')
            else:
                name = str(author)
            if name:
                paper_author_names.append(name)
        
        # Enhanced similarity with CryptoDB for crypto papers
        if self.cryptodb_client:
            venue = paper.get('venue', '')
            enhancement = self.cryptodb_client.enhance_author_comparison(
                ref_authors, paper_author_names, venue
            )
            
            if enhancement.get('enhanced', False):
                # Use CryptoDB canonical matching
                matched_count = len(enhancement.get('matched_authors', []))
                total_ref_authors = len(ref_authors)
                
                if total_ref_authors > 0:
                    # Calculate both similarities
                    cryptodb_similarity = matched_count / total_ref_authors
                    traditional_similarity = calculate_author_similarity(ref_authors, paper_author_names)
                    
                    # Only use CryptoDB enhancement if it improves the similarity
                    # This prevents CryptoDB from reducing similarity when it doesn't find matches
                    if cryptodb_similarity > traditional_similarity:
                        # Give more weight to CryptoDB results for crypto papers
                        return 0.7 * cryptodb_similarity + 0.3 * traditional_similarity
                    else:
                        # Use traditional similarity if CryptoDB doesn't improve it
                        return traditional_similarity
        
        # Fallback to traditional author matching
        return calculate_author_similarity(ref_authors, paper_author_names)
    
    def _calculate_venue_similarity(self, extracted_ref: Dict[str, Any], paper: Dict[str, Any]) -> float:
        """Calculate venue similarity between reference and paper"""
        ref_venue = extracted_ref.get('venue', '')
        
        # Try different venue fields from the paper
        paper_venue = ''
        for field in ['venue', 'journal', 'conference', 'publicationVenue']:
            venue_data = paper.get(field)
            if venue_data:
                if isinstance(venue_data, dict):
                    paper_venue = venue_data.get('name', '')
                else:
                    paper_venue = str(venue_data)
                break
        
        if not ref_venue or not paper_venue:
            return 0.0
        
        # Use improved academic venue matching
        return calculate_venue_similarity(ref_venue, paper_venue)
    
    def _calculate_year_similarity(self, extracted_ref: Dict[str, Any], paper: Dict[str, Any]) -> float:
        """Calculate year similarity between reference and paper"""
        ref_year = extracted_ref.get('year')
        paper_year = paper.get('year')
        
        # Convert years to integers
        try:
            if isinstance(ref_year, str):
                ref_year = int(ref_year)
            elif ref_year is None:
                ref_year = 0
        except (ValueError, TypeError):
            ref_year = 0
            
        try:
            if isinstance(paper_year, str):
                paper_year = int(paper_year)
            elif paper_year is None:
                paper_year = 0
        except (ValueError, TypeError):
            # Try to extract year from publication date
            pub_date = paper.get('publicationDate', '')
            if pub_date:
                try:
                    paper_year = int(pub_date[:4])
                except (ValueError, TypeError):
                    paper_year = 0
            else:
                paper_year = 0
        
        if not ref_year or not paper_year:
            return 0.0
        
        year_diff = abs(ref_year - paper_year)
        
        if year_diff == 0:
            return 1.0
        elif year_diff <= self.max_year_difference:
            return 1.0 - (year_diff / self.max_year_difference)
        else:
            return 0.0
    
    def _determine_classification(self, 
                                extracted_ref: Dict[str, Any], 
                                best_match: Optional[Dict[str, Any]], 
                                similarity_score: float,
                                search_results: List[Dict[str, Any]] = None) -> Tuple[ClassificationResult, float, List[str]]:
        """
        Determine the final classification based on similarity and other factors
        
        Args:
            extracted_ref: Reference from document
            best_match: Best matching paper from database
            similarity_score: Overall similarity score
            
        Returns:
            Tuple of (classification, confidence, reasons)
        """
        reasons = []
        
        # High similarity threshold - likely authentic BUT require stronger evidence for moderate scores
        if similarity_score >= self.similarity_threshold:
            confidence = min(0.95, similarity_score + 0.1)
            reasons.append(f"High similarity score ({similarity_score:.2f})")
            
            # ENHANCED: For moderate high similarity (0.55-0.80), require additional evidence
            if similarity_score < 0.80 and search_results:
                major_databases = {'openalex', 'semantic_scholar', 'dblp', 'pubmed', 'arxiv', 'iacr'}
                found_in_major_db = any(db in major_databases for db in {r.get('source', 'unknown') for r in search_results})
                
                # If moderate similarity and no major database, be more cautious
                if not found_in_major_db:
                    confidence -= 0.15  # Reduce confidence significantly
                    reasons.append("Moderate similarity without major database confirmation")
                    
                    # For borderline cases (0.55-0.65), downgrade to suspicious
                    if similarity_score < 0.65:
                        return ClassificationResult.SUSPICIOUS, max(0.4, confidence), reasons + ["Borderline similarity requires stronger database evidence"]
            
            if best_match:
                # Additional checks for authenticity
                if best_match.get('citationCount', 0) > 0:
                    reasons.append("Paper has citations in database")
                    confidence += 0.05
                
                if best_match.get('doi'):
                    reasons.append("Paper has DOI")
                    confidence += 0.02
            
            return ClassificationResult.AUTHENTIC, min(0.99, confidence), reasons
        
        # Medium similarity threshold - suspicious
        elif similarity_score >= (self.similarity_threshold * 0.7):
            confidence = similarity_score * 0.8
            reasons.append(f"Medium similarity score ({similarity_score:.2f})")
            reasons.append("Reference may be partially correct but needs verification")
            
            return ClassificationResult.SUSPICIOUS, confidence, reasons
        
        # Low similarity but some match found - suspicious or fake
        elif similarity_score > 0.2:  # Lowered from 0.3 to 0.2
            confidence = 0.6
            reasons.append(f"Low similarity score ({similarity_score:.2f})")
            
            # Check if this might be a distorted version of a real paper
            if best_match:
                title_sim = self._calculate_title_similarity(extracted_ref, best_match)
                if title_sim > 0.4:  # Lowered from 0.5 to 0.4
                    reasons.append("Title partially matches existing paper - may be corrupted reference")
                    return ClassificationResult.SUSPICIOUS, confidence, reasons
            
            reasons.append("Low similarity suggests possible formatting issues or incomplete data")
            return ClassificationResult.SUSPICIOUS, confidence, reasons  # Changed from FAKE to SUSPICIOUS
        
        # Very low or no similarity - inconclusive rather than fake
        else:
            if not best_match:
                reasons.append("No similar papers found in database - paper may not be indexed")
                reasons.append("Cannot verify authenticity without database match")
                return ClassificationResult.INCONCLUSIVE, 0.3, reasons
            else:
                confidence = 0.5  # Lowered from 0.8
                reasons.append("Very low similarity to known papers")
                reasons.append("Reference may be from specialized venue or not yet indexed")
                return ClassificationResult.INCONCLUSIVE, confidence, reasons  # Changed from FAKE to INCONCLUSIVE
    
    def _get_similarity_breakdown(self, extracted_ref: Dict[str, Any], paper: Dict[str, Any]) -> Dict[str, float]:
        """Get detailed breakdown of similarity scores"""
        if not paper:
            return {}
        
        return {
            'title_similarity': self._calculate_title_similarity(extracted_ref, paper),
            'author_similarity': self._calculate_author_similarity(extracted_ref, paper),
            'venue_similarity': self._calculate_venue_similarity(extracted_ref, paper),
            'year_similarity': self._calculate_year_similarity(extracted_ref, paper)
        }
    
    def classify_batch(self, 
                      references_with_results: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]]) -> List[VerificationResult]:
        """
        Classify a batch of references
        
        Args:
            references_with_results: List of (reference, search_results) tuples
            
        Returns:
            List of VerificationResult objects
        """
        results = []
        
        for extracted_ref, search_results in references_with_results:
            try:
                result = self.classify_reference(extracted_ref, search_results)
                results.append(result)
            except Exception as e:
                logger.error(f"Error classifying reference: {e}")
                # Add error result
                results.append(VerificationResult(
                    classification=ClassificationResult.INCONCLUSIVE,
                    confidence=0.0,
                    similarity_score=0.0,
                    matched_paper=None,
                    reasons=[f"Classification error: {str(e)}"],
                    details={"error": True}
                ))
        
        return results
    
    def generate_summary_report(self, results: List[VerificationResult]) -> Dict[str, Any]:
        """
        Generate a summary report of classification results
        
        Args:
            results: List of VerificationResult objects
            
        Returns:
            Summary report dictionary
        """
        total_refs = len(results)
        
        if total_refs == 0:
            return {"total_references": 0, "message": "No references to analyze"}
        
        # Count classifications
        classification_counts = {}
        for classification in ClassificationResult:
            classification_counts[classification.value] = sum(
                1 for r in results if r.classification == classification
            )
        
        # Calculate percentages more efficiently
        def calculate_percentage(count):
            return round((count / total_refs) * 100, 1)
        
        percentages = {
            classification.value: calculate_percentage(classification_counts[classification.value])
            for classification in ClassificationResult
        }
        
        # Calculate fraud percentage (author manipulation + fabricated)
        fraud_pct = percentages["author_manipulation"] + percentages["fabricated"]
        percentages["total_fraud"] = round(fraud_pct, 1)
        
        # Calculate average similarity and confidence
        avg_similarity = sum(r.similarity_score for r in results) / total_refs
        avg_confidence = sum(r.confidence for r in results) / total_refs
        
        return {
            "total_references": total_refs,
            "classification_counts": classification_counts,
            "percentages": percentages,
            "statistics": {
                "average_similarity_score": round(avg_similarity, 3),
                "average_confidence": round(avg_confidence, 3),
                "high_confidence_results": sum(1 for r in results if r.confidence > 0.8),
                "verified_with_matches": sum(1 for r in results if r.matched_paper is not None)
            },
            "risk_assessment": self._assess_overall_risk(
                percentages["authentic"], 
                percentages["fake"], 
                percentages["suspicious"], 
                percentages["total_fraud"]
            )
        }
    
    def _detect_fraud(self, extracted_ref: Dict[str, Any], search_results: List[Dict[str, Any]]) -> Optional[VerificationResult]:
        """
        Detect various types of reference fraud including author manipulation
        Enhanced with CryptoDB verification and configurable thresholds
        
        Args:
            extracted_ref: Reference from document
            search_results: All search results from databases
            
        Returns:
            VerificationResult if fraud detected, None otherwise
        """
        # Skip fraud detection if disabled
        if not self.enable_fraud_detection:
            return None
            
        # Look for author manipulation (same title, different authors)
        for paper in search_results:
            title_sim = self._calculate_title_similarity(extracted_ref, paper)
            author_sim = self._calculate_author_similarity(extracted_ref, paper)
            
            # Enhanced fraud detection with configurable thresholds
            ref_authors = extracted_ref.get('authors', [])
            paper_authors = paper.get('authors', [])
            
            # High title similarity but very low author similarity = potential author manipulation
            # Use configurable threshold for title similarity
            if title_sim > self.author_manipulation_threshold and author_sim < 0.3:  # Increased from 0.2 to 0.3
                
                # Additional checks to avoid false positives:
                
                # 1. Skip if single author papers (common name variations)
                if len(ref_authors) <= 1 or len(paper_authors) <= 1:
                    continue
                
                # 2. Check if this is a well-known/established paper (multiple database matches)
                database_sources = set(r.get('source', 'unknown') for r in search_results)
                if len(database_sources) >= 3:  # Found in 3+ databases = likely legitimate
                    continue
                
                # 3. Check for different levels of author manipulation
                if author_sim < 0.1:  # Almost completely different authors
                    fraud_type = "severe_author_manipulation"
                    confidence = 0.9 + self.fraud_confidence_boost
                elif author_sim < 0.2:  # Significantly different authors  
                    fraud_type = "author_manipulation"
                    confidence = 0.85 + self.fraud_confidence_boost
                else:  # Moderately different authors
                    fraud_type = "possible_author_manipulation" 
                    confidence = 0.75 + self.fraud_confidence_boost
                    
                # Enhanced verification with CryptoDB for crypto papers
                cryptodb_details = {}
                if self.cryptodb_client:
                    venue = paper.get('venue', '')
                    enhancement = self.cryptodb_client.enhance_author_comparison(
                        ref_authors,
                        paper_authors,
                        venue
                    )
                    cryptodb_details = enhancement
                    
                    # If CryptoDB confirms legitimate authors, skip fraud detection
                    if enhancement.get('legitimate_match', False):
                        continue
                
                # NEW: Google Scholar validation for author manipulation detection
                # Use Google Scholar to validate our author manipulation detection
                if self.google_scholar_client and self.google_scholar_client.should_validate_author_manipulation('author_manipulation'):
                    logger.info(f"Validating author manipulation detection with Google Scholar for title: {extracted_ref.get('title', 'N/A')}")
                    
                    validation_result = self.google_scholar_client.validate_author_manipulation(
                        extracted_ref.get('title', ''),
                        extracted_ref.get('authors', []),
                        paper.get('title', ''),
                        paper.get('authors', [])
                    )
                    
                    if validation_result.get('validated') == False:
                        # Google Scholar suggests this is not manipulation - override our detection
                        logger.info(f"Google Scholar validation overrode author manipulation detection: {validation_result.get('evidence', 'Unknown reason')}")
                        continue  # Skip fraud detection and continue with next paper
                    elif validation_result.get('validated') == True:
                        # Google Scholar confirms our detection
                        logger.info(f"Google Scholar validation confirmed author manipulation: {validation_result.get('evidence', 'Unknown reason')}")
                        # Add Google Scholar validation details to fraud detection
                        cryptodb_details['google_scholar_validation'] = validation_result
                    else:
                        # Inconclusive - proceed with original detection but add note
                        logger.info(f"Google Scholar validation inconclusive: {validation_result.get('evidence', 'Unknown reason')}")
                        cryptodb_details['google_scholar_validation'] = validation_result
                
                return VerificationResult(
                    classification=ClassificationResult.AUTHOR_MANIPULATION,
                    confidence=confidence,
                    similarity_score=title_sim,
                    matched_paper=paper,
                    reasons=[
                        f"Title matches existing paper with {title_sim:.2f} similarity (threshold: {self.author_manipulation_threshold:.2f})",
                        f"But authors are significantly different (similarity: {author_sim:.2f})",
                        "This suggests deliberate author manipulation fraud"
                    ],
                    details={
                        "fraud_type": fraud_type,
                        "title_similarity": title_sim,
                        "author_similarity": author_sim,
                        "original_authors": paper_authors,
                        "claimed_authors": ref_authors,
                        "cryptodb_verification": cryptodb_details,
                        "threshold_used": self.author_manipulation_threshold
                    }
                )
        
        return None
    
    def _validate_across_databases(self, extracted_ref: Dict[str, Any], search_results: List[Dict[str, Any]], 
                                  best_match: Optional[Dict[str, Any]], best_score: float) -> Optional[VerificationResult]:
        """
        SLIGHTLY PESSIMISTIC validation - multiple databases preferred for high scores
        
        Args:
            extracted_ref: Reference from document  
            search_results: All search results
            best_match: Best matching paper
            best_score: Best similarity score
            
        Returns:
            VerificationResult if specific validation needed, None for standard processing
        """
        # Count unique databases that returned results
        databases = set(r.get('source', 'unknown') for r in search_results)
        num_databases = len(databases)
        
        # Authoritative databases that are sufficient on their own for high-quality matches
        authoritative_databases = {'dblp', 'pubmed', 'ieee', 'acm', 'springer'}
        found_authoritative = databases.intersection(authoritative_databases)
        
        # For high similarity scores, prefer multiple database confirmation
        # But only flag as suspicious if similarity is not overwhelming AND not in authoritative database
        if best_score > 0.75 and best_score < 0.85 and num_databases == 1 and not found_authoritative:
            return VerificationResult(
                classification=ClassificationResult.SUSPICIOUS,
                confidence=0.65,  # Reduced confidence
                similarity_score=best_score,
                matched_paper=best_match,
                reasons=[
                    f"High similarity but found in only {num_databases} database: {', '.join(databases)}",
                    "Single-database moderate matches warrant additional verification",
                    "Very high similarity (>85%) or authoritative databases would override this concern"
                ],
                details={
                    "databases_found": list(databases),
                    "database_count": num_databases,
                    "authoritative_databases_found": list(found_authoritative),
                    "validation_level": "single_database_moderate_similarity_concern"
                }
            )
        
        return None
    
    def _determine_enhanced_classification(self, extracted_ref: Dict[str, Any], 
                                          best_match: Optional[Dict[str, Any]], 
                                          similarity_score: float,
                                          search_results: List[Dict[str, Any]]) -> Tuple[ClassificationResult, float, List[str]]:
        """
        CONFIGURABLE classification using rigor level and advanced settings
        
        Args:
            extracted_ref: Reference from document
            best_match: Best matching paper
            similarity_score: Overall similarity score  
            search_results: All search results
            
        Returns:
            Tuple of (classification, confidence, reasons)
        """
        reasons = []
        databases = set(r.get('source', 'unknown') for r in search_results)
        num_databases = len(databases)
        
        # CRITICAL: Check if major databases found nothing
        major_databases = {'openalex', 'semantic_scholar', 'dblp', 'pubmed', 'arxiv', 'iacr'}
        found_in_major_db = any(db in major_databases for db in databases)
        
        # If no major database found anything AND similarity is low, likely fabricated
        if not found_in_major_db and similarity_score < 0.5:
            # Use Google Scholar validation if available for final confirmation
            if self.google_scholar_client and self.google_scholar_client.should_validate_fabrication_suspicion(list(databases), similarity_score):
                validation_result = self.google_scholar_client.validate_fabrication_suspicion(
                    extracted_ref.get('title', ''),
                    extracted_ref.get('authors', []),
                    extracted_ref.get('year')
                )
                
                if validation_result.get('validated') == True:
                    # Google Scholar confirms fabrication
                    reasons.append("No major academic databases found this reference")
                    reasons.append(f"Low similarity score ({similarity_score:.2f}) with partial matches only")
                    reasons.append(f"Google Scholar validation confirms: {validation_result.get('evidence', 'Paper not found')}")
                    return ClassificationResult.FABRICATED, 0.85, reasons
                elif validation_result.get('validated') == False:
                    # Google Scholar found the paper - continue with normal classification
                    reasons.append(f"Google Scholar validation found legitimate paper: {validation_result.get('evidence', 'Paper exists')}")
                else:
                    # Inconclusive Google Scholar result
                    reasons.append(f"Google Scholar validation inconclusive: {validation_result.get('evidence', 'Mixed evidence')}")
            else:
                # No Google Scholar validation available - use conservative classification
                reasons.append("No major academic databases found this reference")
                reasons.append(f"Low similarity score ({similarity_score:.2f}) with partial matches only")
                reasons.append("Pattern suggests fabricated reference")
                return ClassificationResult.FABRICATED, 0.75, reasons
        
        # Authentic classification using configurable threshold
        if similarity_score >= self.similarity_threshold:
            confidence = min(0.95, similarity_score + self.authentic_confidence_boost)
            reasons.append(f"High similarity score ({similarity_score:.2f}) above threshold ({self.similarity_threshold:.2f})")
            
            # ENHANCED: For moderate high similarity (0.55-0.80), require stronger evidence
            if similarity_score < 0.80:
                major_databases = {'openalex', 'semantic_scholar', 'dblp', 'pubmed', 'arxiv', 'iacr'}
                found_in_major_db = any(db in major_databases for db in databases)
                
                # If moderate similarity and no major database, be more cautious
                if not found_in_major_db:
                    confidence -= 0.20  # Reduce confidence significantly
                    reasons.append("CAUTION: Moderate similarity without major database confirmation")
                    
                    # For borderline cases (0.55-0.70), downgrade to suspicious unless multiple small databases
                    if similarity_score < 0.70 and num_databases < 3:
                        return ClassificationResult.SUSPICIOUS, max(0.4, confidence - 0.1), reasons + ["Borderline similarity requires stronger database evidence or multiple sources"]
            
            # Multiple database presence adds confidence
            if num_databases >= 2:
                reasons.append(f"Verified in {num_databases} databases: {', '.join(databases)}")
                confidence += 0.05
            else:
                reasons.append(f"Found in {num_databases} database: {', '.join(databases)}")
                if self.multi_database_requirement:
                    confidence -= self.single_database_penalty * 2  # Double penalty if multi-DB required
                    reasons.append("Single database presence reduces confidence (multi-DB verification preferred)")
                else:
                    confidence -= self.single_database_penalty  # Standard penalty
                
            if best_match:
                if best_match.get('citationCount', 0) > 0:
                    reasons.append("Paper has citations in database")
                    confidence += 0.03
                
                if best_match.get('doi'):
                    reasons.append("Paper has DOI")
                    confidence += 0.02
            
            return ClassificationResult.AUTHENTIC, min(0.99, confidence), reasons
        
        # Medium similarity - use configurable suspicious threshold
        elif similarity_score >= self.suspicious_threshold:
            confidence = similarity_score * 0.75
            reasons.append(f"Medium similarity score ({similarity_score:.2f})")
            reasons.append("Reference partially matches known papers but lacks strong verification")
            
            if num_databases >= 2:
                reasons.append("Found in multiple databases")
                confidence += 0.05
            else:
                reasons.append("Limited database coverage raises some concerns")
                confidence -= self.single_database_penalty
                
            return ClassificationResult.SUSPICIOUS, confidence, reasons
        
        # Low similarity - likely fabricated or fake
        elif similarity_score > self.inconclusive_threshold:
            confidence = 0.7 + self.fraud_confidence_boost
            reasons.append(f"Low similarity score ({similarity_score:.2f})")
            
            # Check if this appears to be completely made up
            if similarity_score < 0.1:
                reasons.append("Extremely low similarity suggests fabricated reference")
                return ClassificationResult.FABRICATED, confidence, reasons
            else:
                reasons.append("Searched across {} databases but found no strong matches".format(num_databases))
                return ClassificationResult.FABRICATED, confidence, reasons
            
        # Very low or no similarity - clearly fabricated
        else:
            if not best_match:
                reasons.append("No similar papers found in any database")
                reasons.append("Complete absence from academic databases strongly suggests fabrication")
                return ClassificationResult.FABRICATED, 0.8 + self.fraud_confidence_boost, reasons
            else:
                confidence = 0.75 + self.fraud_confidence_boost
                reasons.append("Very low similarity to known papers")
                reasons.append("No meaningful similarity to any papers in academic databases")
                reasons.append(f"Comprehensive search across {num_databases} databases found no matches")
                reasons.append("Reference appears to be fabricated")
                return ClassificationResult.FABRICATED, confidence, reasons
            
            return ClassificationResult.FABRICATED, confidence, reasons
    
    def _assess_overall_risk(self, authentic_pct: float, fake_pct: float, suspicious_pct: float, fraud_pct: float) -> str:
        """Assess overall risk level based on classification percentages including new fraud types"""
        if fraud_pct > 15 or fake_pct > 20:
            return "🚨 CRITICAL - Significant fraud detected (author manipulation or fabrication)"
        elif fraud_pct > 5 or fake_pct > 10 or suspicious_pct > 30:
            return "🔴 HIGH - Notable fraud or suspicious references detected"
        elif fraud_pct > 0 or fake_pct > 5 or suspicious_pct > 15:
            return "🟡 MEDIUM - Some concerning references require investigation"
        elif suspicious_pct > 5:
            return "🟢 LOW - Minor concerns with some references"
        else:
            return "✅ MINIMAL - References appear authentic with rigorous verification"
    
    def _incorporate_ai_analysis(self, 
                                classification: ClassificationResult,
                                confidence: float,
                                reasons: List[str],
                                ai_verification) -> Tuple[ClassificationResult, float, List[str]]:
        """
        Smart AI integration with reduced false positives/negatives
        Uses multi-factor decision making instead of pure AI override
        
        Args:
            classification: Current classification result
            confidence: Current confidence score
            reasons: Current list of reasons
            ai_verification: AI verification result
            
        Returns:
            Updated classification, confidence, and reasons
        """
        if not ai_verification:
            return classification, confidence, reasons
        
        # Calculate database evidence strength
        database_evidence = self._calculate_database_evidence_strength(classification, confidence)
        
        # Calculate AI evidence strength (not just confidence)
        ai_evidence = self._calculate_ai_evidence_strength(ai_verification)
        
        # Map AI authenticity to our classification system
        if ai_verification.is_authentic:
            ai_classification = ClassificationResult.AUTHENTIC
        else:
            # Use AI's red flags to determine specific classification
            red_flags = [flag.lower() for flag in ai_verification.red_flags]
            if any('author' in flag for flag in red_flags):
                ai_classification = ClassificationResult.AUTHOR_MANIPULATION
            elif any('fabricat' in flag or 'fake' in flag for flag in red_flags):
                ai_classification = ClassificationResult.FABRICATED
            else:
                ai_classification = ClassificationResult.SUSPICIOUS
        
        # Smart consensus-based decision making
        return self._make_consensus_decision(
            classification, confidence, reasons,
            ai_classification, ai_verification,
            database_evidence, ai_evidence
        )
    
    def _calculate_database_evidence_strength(self, classification: ClassificationResult, confidence: float) -> float:
        """
        Calculate how strong the database evidence is
        Returns value between 0.0 (weak) and 1.0 (very strong)
        """
        base_strength = confidence
        
        # Boost for authentic classifications with high similarity
        if classification == ClassificationResult.AUTHENTIC:
            if confidence > 0.8:
                base_strength += 0.1  # Very high similarity = strong evidence
            elif confidence > 0.6:
                base_strength += 0.05  # Good similarity = moderate boost
        
        # Reduce strength for problematic classifications with low confidence
        elif classification in [ClassificationResult.SUSPICIOUS, ClassificationResult.FABRICATED]:
            if confidence < 0.6:
                base_strength *= 0.8  # Low confidence = weaker evidence
        
        return min(1.0, base_strength)
    
    def _calculate_ai_evidence_strength(self, ai_verification) -> float:
        """
        Calculate AI evidence strength based on multiple factors, not just confidence
        Returns value between 0.0 (weak) and 1.0 (very strong)
        """
        base_strength = ai_verification.confidence
        
        # Positive indicators boost AI strength
        positive_count = len(ai_verification.positive_indicators)
        if positive_count >= 3:
            base_strength += 0.15  # Many positive indicators
        elif positive_count >= 2:
            base_strength += 0.1   # Some positive indicators
        elif positive_count >= 1:
            base_strength += 0.05  # Few positive indicators
        
        # Red flags reduce AI strength for authentic claims
        if ai_verification.is_authentic:
            red_flag_count = len(ai_verification.red_flags)
            if red_flag_count >= 2:
                base_strength -= 0.1  # AI says authentic but has red flags
            elif red_flag_count >= 1:
                base_strength -= 0.05
        
        # Very high confidence needs additional validation
        if ai_verification.confidence > 0.9:
            base_strength *= 0.95  # Slight penalty for overconfidence
        
        return max(0.0, min(1.0, base_strength))
    
    def _make_consensus_decision(self, 
                                db_classification: ClassificationResult, db_confidence: float, reasons: List[str],
                                ai_classification: ClassificationResult, ai_verification,
                                db_evidence: float, ai_evidence: float) -> Tuple[ClassificationResult, float, List[str]]:
        """
        Make final decision based on consensus between database and AI evidence
        DATABASE-DEPENDENT APPROACH: AI decisions are heavily weighted by database evidence quality
        """
        # Get AI weight from configuration - but make it dependent on database evidence
        base_ai_weight = min(0.4, self.ai_verifier.get_verification_weight() if self.ai_verifier else 0.3)
        
        # Adjust AI weight based on database evidence strength - KEY CHANGE
        if db_evidence > 0.8:
            # Strong database evidence - reduce AI influence significantly
            adjusted_ai_weight = base_ai_weight * getattr(config, 'AI_WEIGHT_WITH_STRONG_DB', 0.2) / base_ai_weight
            database_trust_factor = "strong"
        elif db_evidence > 0.6:
            # Moderate database evidence - moderate AI influence
            adjusted_ai_weight = base_ai_weight * getattr(config, 'AI_WEIGHT_WITH_MODERATE_DB', 0.3) / base_ai_weight
            database_trust_factor = "moderate"
        elif db_evidence > 0.4:
            # Weak database evidence - normal AI influence
            adjusted_ai_weight = base_ai_weight * getattr(config, 'AI_WEIGHT_WITH_WEAK_DB', 0.4) / base_ai_weight
            database_trust_factor = "weak"
        else:
            # Very weak database evidence - AI can have more influence but still limited
            max_ai_weight = getattr(config, 'AI_WEIGHT_WITH_VERY_WEAK_DB', 0.5)
            adjusted_ai_weight = min(base_ai_weight * 1.2, max_ai_weight)
            database_trust_factor = "very_weak"
        
        traditional_weight = 1.0 - adjusted_ai_weight
        
        # Case 1: Both agree - strengthen the decision (but still database-dependent)
        if db_classification == ai_classification:
            if db_classification == ClassificationResult.AUTHENTIC:
                # Boost varies based on database evidence strength
                if db_evidence > 0.8:
                    confidence_boost = min(0.15, (db_evidence + ai_evidence) * 0.12)
                elif db_evidence > 0.6:
                    confidence_boost = min(0.10, (db_evidence + ai_evidence) * 0.08)
                else:
                    confidence_boost = min(0.05, (db_evidence + ai_evidence) * 0.05)
                    
                new_confidence = min(0.99, db_confidence + confidence_boost)
                new_reasons = reasons + [f"Database ({database_trust_factor}) and AI both confirm authenticity (AI: {ai_verification.confidence:.2f})"]
            else:
                confidence_boost = min(0.08, (db_evidence + ai_evidence) * 0.06)
                new_confidence = min(0.95, db_confidence + confidence_boost)
                new_reasons = reasons + [f"Database ({database_trust_factor}) and AI both identify concerns (AI: {ai_verification.confidence:.2f})"]
            
            return db_classification, new_confidence, new_reasons
        
        # Case 2: AI says authentic, database says problematic
        elif ai_classification == ClassificationResult.AUTHENTIC and db_classification != ClassificationResult.AUTHENTIC:
            return self._handle_ai_authentic_db_problematic(
                db_classification, db_confidence, reasons, ai_verification, db_evidence, ai_evidence
            )
        
        # Case 3: Database says authentic, AI says problematic  
        elif db_classification == ClassificationResult.AUTHENTIC and ai_classification != ClassificationResult.AUTHENTIC:
            return self._handle_db_authentic_ai_problematic(
                db_classification, db_confidence, reasons, ai_verification, db_evidence, ai_evidence
            )
        
        # Case 4: Both problematic but different types - favor database more strongly
        else:
            # Use evidence strength but give database more weight in tie situations
            if db_evidence > ai_evidence + 0.15:  # Reduced threshold for database preference
                new_confidence = traditional_weight * db_confidence + adjusted_ai_weight * ai_verification.confidence * 0.5
                new_reasons = reasons + [f"Database evidence ({database_trust_factor}) takes precedence"]
                return db_classification, new_confidence, new_reasons
            elif ai_evidence > db_evidence + 0.3:  # Higher threshold for AI preference
                new_confidence = traditional_weight * db_confidence * 0.6 + adjusted_ai_weight * ai_verification.confidence
                new_reasons = reasons + [f"Exceptional AI evidence overrides weak database: {ai_verification.reasoning[:50]}..."]
                return ai_classification, new_confidence, new_reasons
            else:  # Similar strength - strongly favor conservative database-based decision
                new_confidence = traditional_weight * db_confidence + adjusted_ai_weight * ai_verification.confidence * 0.6
                new_reasons = reasons + [f"Mixed evidence - database ({database_trust_factor}) takes precedence"]
                # Choose more conservative classification
                if db_classification == ClassificationResult.SUSPICIOUS or ai_classification == ClassificationResult.SUSPICIOUS:
                    return ClassificationResult.SUSPICIOUS, new_confidence, new_reasons
                else:
                    return db_classification, new_confidence, new_reasons
    
    def _handle_ai_authentic_db_problematic(self, db_classification, db_confidence, reasons, ai_verification, db_evidence, ai_evidence):
        """
        Handle case where AI says authentic but database says problematic
        CONSERVATIVE APPROACH: Database evidence takes precedence, AI must provide exceptional evidence to override
        """
        
        # Calculate minimum evidence thresholds for AI override (made more conservative)
        if db_classification == ClassificationResult.FABRICATED:
            required_ai_strength = getattr(config, 'AI_OVERRIDE_FABRICATED_THRESHOLD', 0.85)
            required_db_weakness = 0.4  # Database evidence must be weak to consider override
            max_upgrade = ClassificationResult.SUSPICIOUS  # Never upgrade fabricated directly to authentic
        elif db_classification == ClassificationResult.AUTHOR_MANIPULATION:
            required_ai_strength = getattr(config, 'AI_OVERRIDE_AUTHOR_MANIP_THRESHOLD', 0.80)
            required_db_weakness = 0.5
            max_upgrade = ClassificationResult.SUSPICIOUS  # Conservative upgrade
        else:  # SUSPICIOUS
            required_ai_strength = getattr(config, 'AI_OVERRIDE_SUSPICIOUS_THRESHOLD', 0.70)
            required_db_weakness = 0.6
            max_upgrade = ClassificationResult.AUTHENTIC
        
        # Enhanced safety checks for AI override - MUCH MORE RESTRICTIVE
        safety_passed = True
        safety_reasons = []
        
        # Check 1: Database evidence must be weak enough to question - STRENGTHENED
        if db_evidence > required_db_weakness:
            safety_passed = False
            safety_reasons.append(f"Database evidence too strong ({db_evidence:.2f}) to override with AI")
        
        # Check 2: AI must have very strong positive indicators for high-confidence claims - STRENGTHENED
        min_indicators_high = getattr(config, 'AI_MIN_POSITIVE_INDICATORS_HIGH_CONF', 4)  # Increased from 3
        min_indicators_med = getattr(config, 'AI_MIN_POSITIVE_INDICATORS_MED_CONF', 3)    # Increased from 2
        
        if ai_verification.confidence > 0.8:
            if len(ai_verification.positive_indicators) < min_indicators_high:
                safety_passed = False
                safety_reasons.append(f"AI high confidence requires at least {min_indicators_high} positive indicators")
        elif ai_verification.confidence > 0.7:
            if len(ai_verification.positive_indicators) < min_indicators_med:
                safety_passed = False
                safety_reasons.append(f"AI moderate confidence requires at least {min_indicators_med} positive indicators")
        
        # Check 3: AI should have NO red flags for authentic claims - STRENGTHENED
        if len(ai_verification.red_flags) >= 1:
            safety_passed = False
            safety_reasons.append("AI cannot claim authentic while having any red flags")
        
        # Check 4: Database similarity threshold - MUCH MORE CONSERVATIVE
        if db_confidence < 0.3 and ai_evidence < 0.95:  # Increased AI requirement
            safety_passed = False
            safety_reasons.append("Very low database match requires near-perfect AI evidence (>0.95)")
        elif db_confidence < 0.6 and ai_evidence < 0.90:  # Increased thresholds
            safety_passed = False
            safety_reasons.append("Low database match requires exceptional AI evidence (>0.90)")
        
        # Check 5: AI reasoning quality assessment - STRENGTHENED
        if ai_verification.reasoning and len(ai_verification.reasoning) < 100:  # Increased from 50
            safety_passed = False
            safety_reasons.append("AI reasoning too brief for override decision")
        
        # Check 6: Confidence gap requirement - STRENGTHENED
        min_confidence_gap = getattr(config, 'AI_MIN_CONFIDENCE_GAP', 0.5)  # Increased from 0.3
        confidence_gap = ai_verification.confidence - db_confidence
        if confidence_gap < min_confidence_gap:
            safety_passed = False
            safety_reasons.append(f"AI confidence gap insufficient ({confidence_gap:.2f} < {min_confidence_gap})")
        
        # NEW Check 7: Major database requirement - if no major DB found the paper, be extra cautious
        major_databases = {'openalex', 'semantic_scholar', 'dblp', 'pubmed', 'arxiv', 'iacr'}
        if not any(indicator for indicator in ai_verification.positive_indicators 
                  if any(db in indicator.lower() for db in major_databases)):
            safety_passed = False
            safety_reasons.append("No evidence of paper in major academic databases - high risk of fabrication")
        
        # Make decision based on evidence strength and safety checks
        if ai_evidence >= required_ai_strength and safety_passed:
            # AI override approved - but with conservative weighting
            new_classification = max_upgrade
            
            # More conservative AI weight calculation
            base_ai_weight = min(0.4, ai_evidence * 0.6)  # Reduced maximum AI influence
            database_penalty = 0.8 if db_evidence > 0.3 else 0.7  # Penalize when database has evidence
            
            new_confidence = (1 - base_ai_weight) * db_confidence * database_penalty + base_ai_weight * ai_verification.confidence
            new_reasons = reasons + [f"Exceptional AI evidence overrides weak database concerns: {ai_verification.reasoning[:60]}..."]
            new_reasons.append(f"AI confidence: {ai_verification.confidence:.2f}, Database confidence: {db_confidence:.2f}")
            
            if ai_verification.positive_indicators:
                new_reasons.append(f"AI positive indicators: {', '.join(ai_verification.positive_indicators[:3])}")
        else:
            # AI override rejected - trust database evidence
            new_classification = db_classification
            
            # Reduce confidence slightly due to AI disagreement, but trust database more
            if safety_passed:
                # Safety passed but evidence insufficient
                new_confidence = db_confidence * 0.9
                new_reasons = reasons + ["AI suggests authenticity but evidence insufficient for override"]
                new_reasons.append("Database evidence takes precedence")
            else:
                # Safety failed - more significant confidence reduction
                new_confidence = db_confidence * 0.85
                new_reasons = reasons + ["AI suggestion rejected due to safety concerns"]
                new_reasons.extend(safety_reasons[:2])  # Include first 2 safety reasons
        
        return new_classification, new_confidence, new_reasons
    
    def _handle_db_authentic_ai_problematic(self, db_classification, db_confidence, reasons, ai_verification, db_evidence, ai_evidence):
        """
        Handle case where database says authentic but AI says problematic
        ENHANCED AI FRAUD DETECTION: Take AI concerns more seriously when database evidence is weak
        """
        
        # AI fraud detection sensitivity from config
        fraud_sensitivity = getattr(config, 'AI_FRAUD_DETECTION_SENSITIVITY', 0.75)
        
        # More nuanced approach based on database evidence strength
        if db_evidence < 0.5:  # Weak database evidence - trust AI fraud detection more
            if ai_evidence > fraud_sensitivity * 0.8 and len(ai_verification.red_flags) >= 2:
                # Strong AI concerns with weak database evidence
                new_classification = ai_verification.red_flags[0].lower()
                if 'author' in new_classification:
                    new_classification = ClassificationResult.AUTHOR_MANIPULATION
                elif 'fabricat' in new_classification or 'fake' in new_classification:
                    new_classification = ClassificationResult.FABRICATED
                else:
                    new_classification = ClassificationResult.SUSPICIOUS
                
                new_confidence = 0.6 + (ai_evidence - fraud_sensitivity) * 0.5
                new_reasons = reasons + [f"Weak database evidence ({db_evidence:.2f}) + strong AI concerns"]
                new_reasons.append(f"AI identifies: {', '.join(ai_verification.red_flags[:2])}")
                new_reasons.append("Requires immediate manual investigation")
                
            elif ai_evidence > fraud_sensitivity * 0.9 and len(ai_verification.red_flags) >= 1:
                # Moderate AI concerns with weak database evidence
                new_classification = ClassificationResult.SUSPICIOUS
                new_confidence = db_confidence * 0.7
                new_reasons = reasons + [f"Weak database match + AI concerns warrant investigation"]
                new_reasons.append(f"AI flag: {ai_verification.red_flags[0]}")
            else:
                # Weak AI concerns with weak database evidence - stay suspicious
                new_classification = ClassificationResult.SUSPICIOUS
                new_confidence = db_confidence * 0.8
                new_reasons = reasons + ["Both database and AI evidence are weak - requires manual verification"]
                
        elif db_evidence >= 0.8:  # Strong database evidence - be more skeptical of AI concerns
            if ai_evidence > fraud_sensitivity * 1.1 and len(ai_verification.red_flags) >= 3:
                # Very strong AI concerns even with strong database evidence
                new_classification = ClassificationResult.SUSPICIOUS
                new_confidence = db_confidence * 0.75
                new_reasons = reasons + [f"Strong database evidence but serious AI concerns"]
                new_reasons.append(f"AI raises multiple red flags: {', '.join(ai_verification.red_flags[:2])}")
                new_reasons.append("Exceptional case requiring expert review")
            elif ai_evidence > fraud_sensitivity and len(ai_verification.red_flags) >= 2:
                # Moderate AI concerns with strong database evidence
                new_classification = ClassificationResult.SUSPICIOUS
                new_confidence = db_confidence * 0.85
                new_reasons = reasons + [f"Strong database match but AI identifies potential issues"]
                new_reasons.append(f"AI concerns: {', '.join(ai_verification.red_flags[:2])}")
            else:
                # Weak AI concerns with strong database evidence - trust database
                new_classification = db_classification
                new_confidence = db_confidence * 0.95
                new_reasons = reasons + ["Strong database evidence overrides minor AI concerns"]
                if ai_verification.red_flags:
                    new_reasons.append(f"AI notes: {ai_verification.red_flags[0]}")
                    
        else:  # Moderate database evidence (0.5-0.8) - balanced approach
            if ai_evidence > fraud_sensitivity and len(ai_verification.red_flags) >= 2:
                # Strong AI concerns with moderate database evidence
                new_classification = ClassificationResult.SUSPICIOUS
                new_confidence = db_confidence * 0.75
                new_reasons = reasons + [f"Moderate database evidence + AI fraud detection"]
                new_reasons.append(f"AI identifies: {', '.join(ai_verification.red_flags[:2])}")
                new_reasons.append("Balanced evidence suggests manual review needed")
            elif ai_evidence > fraud_sensitivity * 0.8 and len(ai_verification.red_flags) >= 1:
                # Moderate AI concerns
                new_classification = ClassificationResult.SUSPICIOUS
                new_confidence = db_confidence * 0.85
                new_reasons = reasons + [f"AI identifies potential issue: {ai_verification.red_flags[0]}"]
                new_reasons.append("Moderate confidence in both sources - verification recommended")
            else:
                # Weak AI concerns - slight downgrade but trust database more
                new_classification = db_classification
                new_confidence = db_confidence * 0.9
                new_reasons = reasons + ["Database evidence stronger than AI concerns"]
        
        return new_classification, new_confidence, new_reasons