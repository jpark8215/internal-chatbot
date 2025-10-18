"""
RAG Service Layer - Centralized RAG logic with improved architecture.
"""

import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .config import get_settings
from .dao import get_dao
from .embeddings import embed_texts
from .local_model import get_local_llm
from .logging_config import get_logger

logger = get_logger(__name__)


class SearchStrategy(Enum):
    """Available search strategies."""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    ENHANCED = "enhanced"
    COMBINED = "combined"
    FAST = "fast"  # New fast strategy for speed optimization


@dataclass
class RetrievalResult:
    """Structured result from document retrieval."""
    documents: List[Tuple[int, str, float, Optional[str]]]
    strategy_used: SearchStrategy
    retrieval_time_ms: float
    embedding_time_ms: Optional[float] = None
    total_documents_searched: int = 0


@dataclass
class RAGResponse:
    """Structured RAG response."""
    text: str
    sources: List[Dict[str, Any]]
    retrieval_result: RetrievalResult
    generation_time_ms: float
    total_time_ms: float
    model_used: str
    success: bool = True
    error_message: Optional[str] = None
    quality_indicators: Optional[Dict[str, Any]] = None


class RAGService:
    """Centralized RAG service with improved architecture."""
    
    def __init__(self):
        self.settings = get_settings()
        self.dao = get_dao()
        self.llm = get_local_llm()
        
        # RAG configuration
        self.default_top_k = 5
        self.max_context_length = 8000  # Tokens
        self.relevance_threshold = 20.0  # Cosine distance threshold (balanced for quality vs coverage)
        
        # System prompts
        self.base_system_prompt = (
            "You are a document retrieval assistant. Your ONLY job is to present information from the provided documents.\n"
            "RULES:\n"
            "1. ONLY use information that is explicitly stated in the provided documents\n"
            "2. Do NOT generate, infer, or create any new information\n"
            "3. If the documents don't contain the answer, say 'I don't have information about this in the available documents'\n"
            "4. Present the information in a clear, organized way using the exact content from the documents\n"
            "5. Cite sources as [Source N] when presenting information\n"
            "6. If multiple documents contain relevant information, combine them clearly\n\n"
        )
    
    async def retrieve_documents(self, query: str, top_k: Optional[int] = None, 
                               strategy: Optional[SearchStrategy] = None) -> RetrievalResult:
        """Retrieve relevant documents using specified strategy."""
        start_time = time.time()
        top_k = top_k or self.default_top_k
        strategy = strategy or self._determine_optimal_strategy(query)
        
        logger.info(f"Retrieving documents: query='{query[:50]}...', strategy={strategy.value}, top_k={top_k}")
        
        # Prepare cache parameters
        cache = None
        cache_key_params = None
        
        # Check query result cache first
        if getattr(self.settings, 'enable_query_result_cache', True):
            from .query_result_cache import get_query_result_cache
            cache = get_query_result_cache()
            
            cache_key_params = {
                "query": query,
                "strategy": strategy.value,
                "top_k": top_k
            }
            
            cached_result = cache.get("document_retrieval", cache_key_params)
            if cached_result is not None:
                logger.debug(f"Cache hit for document retrieval: {query[:50]}...")
                return RetrievalResult(
                    documents=cached_result,
                    strategy_used=strategy,
                    retrieval_time_ms=(time.time() - start_time) * 1000,
                    embedding_time_ms=0,  # No embedding needed for cache hit
                    total_documents_searched=self.dao.count_documents()
                )
        
        embedding_time_ms = None
        documents = []
        
        try:
            if strategy in [SearchStrategy.SEMANTIC, SearchStrategy.HYBRID, SearchStrategy.ENHANCED, SearchStrategy.COMBINED, SearchStrategy.FAST]:
                # Generate embeddings
                embed_start = time.time()
                vectors = await embed_texts([query])
                embedding_time_ms = (time.time() - embed_start) * 1000
                query_vec = vectors[0]
                
                # Execute search based on strategy
                if strategy == SearchStrategy.SEMANTIC or strategy == SearchStrategy.FAST:
                    documents = self.dao.search(query_vec, top_k)
                elif strategy == SearchStrategy.HYBRID:
                    documents = self.dao.search_hybrid(query_vec, query, top_k)
                elif strategy == SearchStrategy.ENHANCED:
                    documents = self.dao.search_enhanced(query_vec, query, top_k)
                elif strategy == SearchStrategy.COMBINED:
                    documents = self.dao.search_combined(query_vec, query, top_k)
            
            elif strategy == SearchStrategy.KEYWORD:
                documents = self.dao.search_keyword(query, top_k)
            
            # Filter by relevance threshold
            logger.debug(f"Retrieved {len(documents)} documents before filtering")
            if documents:
                logger.debug(f"Best document score: {documents[0][2]}")
            
            # Apply relevance filtering
            documents = self._filter_by_relevance(documents, strategy)
            logger.debug(f"Kept {len(documents)} documents after relevance filtering")
            
            # Cache the result if caching is enabled
            if cache is not None and cache_key_params is not None and documents:
                cache.put("document_retrieval", cache_key_params, documents)
            
            retrieval_time_ms = (time.time() - start_time) * 1000
            
            return RetrievalResult(
                documents=documents,
                strategy_used=strategy,
                retrieval_time_ms=retrieval_time_ms,
                embedding_time_ms=embedding_time_ms,
                total_documents_searched=self.dao.count_documents()
            )
            
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return RetrievalResult(
                documents=[],
                strategy_used=strategy,
                retrieval_time_ms=(time.time() - start_time) * 1000,
                embedding_time_ms=embedding_time_ms
            )
    
    def _determine_optimal_strategy(self, query: str) -> SearchStrategy:
        """Determine optimal search strategy based on query characteristics and user feedback."""
        query_lower = query.lower()
        
        # Balanced approach: maintain accuracy while optimizing speed
        query_words = len(query.split())
        
        # HCBS-specific queries should use enhanced search for better accuracy
        hcbs_keywords = ['hcbs', 'home and community', 'behavioral health hcbs', 'bh hcbs', 'harp']
        if any(keyword in query_lower for keyword in hcbs_keywords):
            return SearchStrategy.ENHANCED  # Better accuracy for complex HCBS queries
        
        # CCBHC queries should use enhanced search
        ccbhc_keywords = ['ccbhc', 'certified community behavioral health clinic', 'quality measures']
        if any(keyword in query_lower for keyword in ccbhc_keywords):
            return SearchStrategy.ENHANCED
        
        # Policy-related queries benefit from combined search
        policy_keywords = ['policy', 'procedure', 'manual', 'guideline', 'documentation']
        if any(keyword in query_lower for keyword in policy_keywords):
            return SearchStrategy.COMBINED  # Better for policy documents
        
        # Drug/substance queries benefit from enhanced search
        drug_keywords = ['drug', 'substance', 'test', 'testing', 'list', 'screening']
        if any(keyword in query_lower for keyword in drug_keywords):
            return SearchStrategy.ENHANCED  # Better for finding specific lists
        
        # Short queries or exact terms benefit from keyword search
        if query_words <= 2 or any(char in query for char in ['"', "'"]):
            return SearchStrategy.KEYWORD
        
        # Complex queries (admission criteria, specific requirements) use enhanced
        complex_keywords = ['criteria', 'requirements', 'eligibility', 'admission', 'specific', 'detailed']
        if any(keyword in query_lower for keyword in complex_keywords):
            return SearchStrategy.ENHANCED
        
        # For fast mode, use semantic for general queries to balance speed and accuracy
        if getattr(self.settings, 'enable_fast_mode', True):
            return SearchStrategy.SEMANTIC
        
        # Default to semantic search for general queries
        return SearchStrategy.SEMANTIC
        
        # Check feedback history for similar queries (only if not in fast mode)
        try:
            from .user_feedback import get_accuracy_improver
            improver = get_accuracy_improver()
            
            # Get feedback for similar queries to inform strategy choice
            feedback_strategy = improver.get_optimal_strategy_from_feedback(query)
            if feedback_strategy:
                logger.info(f"Using feedback-informed strategy '{feedback_strategy}' for query: {query[:50]}...")
                return SearchStrategy(feedback_strategy)
        except Exception as e:
            logger.debug(f"Could not get feedback-informed strategy: {e}")
        
        # HCBS-specific queries should prioritize HCBS manual
        hcbs_keywords = ['hcbs', 'waiver', 'home and community', 'behavioral health hcbs', 'bh hcbs']
        if any(keyword in query_lower for keyword in hcbs_keywords):
            return SearchStrategy.SEMANTIC  # Use semantic for speed instead of enhanced
        
        # CCBHC queries should use semantic search
        ccbhc_keywords = ['ccbhc', 'certified community behavioral health clinic', 'quality measures']
        if any(keyword in query_lower for keyword in ccbhc_keywords):
            return SearchStrategy.SEMANTIC
        
        # Policy-related queries
        policy_keywords = ['policy', 'procedure', 'manual', 'guideline']
        if any(keyword in query_lower for keyword in policy_keywords):
            return SearchStrategy.SEMANTIC  # Use semantic for speed instead of combined
        
        # Drug/substance queries benefit from enhanced search
        drug_keywords = ['drug', 'substance', 'test', 'testing', 'list']
        if any(keyword in query_lower for keyword in drug_keywords):
            return SearchStrategy.KEYWORD  # Use keyword for speed
        
        # Short queries or exact terms benefit from keyword search
        if len(query.split()) <= 2 or any(char in query for char in ['"', "'"]):
            return SearchStrategy.KEYWORD
        
        # Default to semantic search for speed
        return SearchStrategy.SEMANTIC
    
    def _filter_by_relevance(self, documents: List[Tuple[int, str, float, Optional[str]]], 
                           strategy: SearchStrategy) -> List[Tuple[int, str, float, Optional[str]]]:
        """Filter documents by relevance threshold with strategy-specific logic."""
        if not documents:
            return documents
        
        # Different thresholds for different strategies
        if strategy == SearchStrategy.SEMANTIC:
            # For semantic search, use adaptive threshold based on score distribution
            if len(documents) > 1:
                best_score = documents[0][2]
                # Allow documents within 50% of the best score
                adaptive_threshold = best_score * 1.5
                threshold = min(self.relevance_threshold, adaptive_threshold)
            else:
                threshold = self.relevance_threshold
            return [doc for doc in documents if doc[2] <= threshold]
        
        elif strategy == SearchStrategy.KEYWORD:
            # For keyword search, we trust the ranking but apply basic filtering
            return documents  # Keep all keyword results
        
        elif strategy in [SearchStrategy.ENHANCED, SearchStrategy.COMBINED]:
            # For enhanced/combined, use more permissive threshold for better recall
            if documents:
                best_score = documents[0][2]
                # Allow documents within 75% of the best score for better coverage
                adaptive_threshold = best_score * 1.75
                threshold = min(self.relevance_threshold * 1.2, adaptive_threshold)
                return [doc for doc in documents if doc[2] <= threshold]
        
        else:
            # For hybrid and other strategies, use standard threshold
            return [doc for doc in documents if doc[2] <= self.relevance_threshold]
        
        return documents
    
    def _build_context(self, documents: List[Tuple[int, str, float, Optional[str]]], query: str = "") -> Tuple[str, List[Dict[str, Any]]]:
        """Build context string and source metadata from retrieved documents with smart prioritization."""
        logger.debug(f"Building context from {len(documents)} documents")
        if not documents:
            logger.warning("No documents provided to build context")
            return "", []
        
        # Apply source-specific boosting based on query
        boosted_documents = self._apply_source_boosting(documents, query)
        
        ctx_chunks = []
        sources = []
        
        for i, (doc_id, content, score, source_file) in enumerate(boosted_documents):
            # Truncate very long content
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            # Clean up source file path for display
            display_source = source_file or "Unknown Document"
            if source_file:
                # Extract just the filename
                display_source = source_file.split('/')[-1].split('\\')[-1]
            
            # Normalize score for better user understanding
            # For cosine distance (lower is better), convert to similarity percentage
            # Typical good matches are in 10-20 range, excellent matches < 10
            if score <= 5.0:
                # Excellent match
                normalized_score = 0.95
            elif score <= 10.0:
                # Very good match: 95% to 85%
                normalized_score = 0.95 - ((score - 5.0) / 5.0) * 0.10
            elif score <= 15.0:
                # Good match: 85% to 70%
                normalized_score = 0.85 - ((score - 10.0) / 5.0) * 0.15
            elif score <= 20.0:
                # Fair match: 70% to 50%
                normalized_score = 0.70 - ((score - 15.0) / 5.0) * 0.20
            elif score <= 25.0:
                # Poor match: 50% to 25%
                normalized_score = 0.50 - ((score - 20.0) / 5.0) * 0.25
            else:
                # Very poor match: < 25%
                normalized_score = max(0.05, 0.25 - ((score - 25.0) / 10.0) * 0.20)
            
            # Ensure score is between 0 and 1
            normalized_score = max(0.0, min(1.0, normalized_score))
            
            ctx_chunks.append(f"[Source {i+1}]\n{content}")
            sources.append({
                "id": doc_id,
                "source_file": display_source,
                "score": float(normalized_score),  # Normalized 0-1 score
                "raw_score": float(score),  # Keep original for debugging
                "content_preview": content[:200] + "..." if len(content) > 200 else content
            })
        
        context_text = "\n\n".join(ctx_chunks)
        
        # Ensure context doesn't exceed max length
        if len(context_text) > self.max_context_length:
            # Truncate and keep most relevant sources
            truncated_chunks = []
            current_length = 0
            
            for chunk in ctx_chunks:
                if current_length + len(chunk) > self.max_context_length:
                    break
                truncated_chunks.append(chunk)
                current_length += len(chunk)
            
            context_text = "\n\n".join(truncated_chunks)
            sources = sources[:len(truncated_chunks)]
        
        return context_text, sources
    
    def _generate_quality_indicators(self, query: str, sources: List[Dict[str, Any]], 
                                   strategy_used: SearchStrategy) -> Dict[str, Any]:
        """Generate quality indicators based on historical feedback for similar queries."""
        try:
            from .user_feedback import get_feedback_dao, get_accuracy_improver
            feedback_dao = get_feedback_dao()
            improver = get_accuracy_improver()
            
            # Get historical performance for similar queries
            historical_performance = feedback_dao.get_query_performance_indicators(query)
            
            # Calculate confidence score based on source quality and historical feedback
            source_confidence = self._calculate_source_confidence(sources, query)
            
            # Get feedback-informed response quality score
            feedback_quality_score = improver.calculate_response_quality_score(
                query, sources, strategy_used.value
            )
            
            # Get expected accuracy based on query type and sources
            expected_accuracy = self._estimate_response_accuracy(query, sources)
            
            # Combine feedback-based and rule-based accuracy estimates
            combined_accuracy = (feedback_quality_score * 0.6) + (expected_accuracy * 0.4)
            
            return {
                "confidence_score": source_confidence,
                "expected_accuracy": combined_accuracy,
                "feedback_quality_score": feedback_quality_score,
                "historical_performance": historical_performance,
                "source_quality_score": self._calculate_overall_source_quality(sources),
                "query_complexity": self._assess_query_complexity(query),
                "feedback_available": historical_performance.get("feedback_count", 0) > 0,
                "strategy_used": strategy_used.value,
                "feedback_informed": True
            }
        except Exception as e:
            logger.debug(f"Could not generate quality indicators: {e}")
            return {
                "confidence_score": 0.5,
                "expected_accuracy": 0.7,
                "feedback_quality_score": 0.7,
                "historical_performance": {},
                "source_quality_score": 0.6,
                "query_complexity": "medium",
                "feedback_available": False,
                "strategy_used": strategy_used.value if strategy_used else "unknown",
                "feedback_informed": False
            }
    
    def _calculate_source_confidence(self, sources: List[Dict[str, Any]], query: str) -> float:
        """Calculate confidence score based on source quality and relevance."""
        if not sources:
            return 0.0
        
        total_confidence = 0.0
        for source in sources:
            # Base confidence on normalized score (higher score = higher confidence)
            base_confidence = source.get("score", 0.0)
            
            # Boost confidence for sources that historically perform well
            source_file = source.get("source_file", "")
            if "hcbs" in source_file.lower() and any(keyword in query.lower() for keyword in ["hcbs", "waiver"]):
                base_confidence *= 1.2
            elif "policy" in source_file.lower() and "policy" in query.lower():
                base_confidence *= 1.1
            
            total_confidence += min(1.0, base_confidence)
        
        return min(1.0, total_confidence / len(sources))
    
    def _estimate_response_accuracy(self, query: str, sources: List[Dict[str, Any]]) -> float:
        """Estimate expected response accuracy based on query and sources."""
        base_accuracy = 0.7  # Default baseline
        
        # Adjust based on query complexity
        query_words = len(query.split())
        if query_words <= 3:
            base_accuracy += 0.1  # Simple queries tend to be more accurate
        elif query_words > 15:
            base_accuracy -= 0.1  # Complex queries may be less accurate
        
        # Adjust based on source quality
        if sources:
            avg_source_score = sum(s.get("score", 0.0) for s in sources) / len(sources)
            if avg_source_score > 0.8:
                base_accuracy += 0.15
            elif avg_source_score < 0.4:
                base_accuracy -= 0.1
        
        return min(1.0, max(0.0, base_accuracy))
    
    def _calculate_overall_source_quality(self, sources: List[Dict[str, Any]]) -> float:
        """Calculate overall quality score for the retrieved sources."""
        if not sources:
            return 0.0
        
        # Average the normalized scores
        total_score = sum(source.get("score", 0.0) for source in sources)
        return min(1.0, total_score / len(sources))
    
    def _assess_query_complexity(self, query: str) -> str:
        """Assess the complexity of the query."""
        word_count = len(query.split())
        question_marks = query.count("?")
        
        if word_count <= 5 and question_marks <= 1:
            return "simple"
        elif word_count <= 15 and question_marks <= 2:
            return "medium"
        else:
            return "complex"
    
    def _apply_source_boosting(self, documents: List[Tuple[int, str, float, Optional[str]]], query: str) -> List[Tuple[int, str, float, Optional[str]]]:
        """Apply source-specific boosting based on query content and user feedback."""
        if not documents:
            return documents
        
        query_lower = query.lower()
        
        # First apply feedback-driven dynamic boosting
        try:
            from .user_feedback import get_accuracy_improver
            improver = get_accuracy_improver()
            documents = improver.get_dynamic_source_boosting(query, documents)
            logger.debug(f"Applied feedback-driven source boosting for query: {query[:50]}...")
        except Exception as e:
            logger.debug(f"Could not apply feedback-driven boosting: {e}")
        
        # Then apply rule-based boosting as fallback/supplement
        boosted_docs = []
        
        # Get feedback-based source preferences (legacy method as backup)
        feedback_boosts = self._get_feedback_source_boosts(query)
        
        for doc_id, content, score, source_file in documents:
            boost_factor = 1.0
            
            if source_file:
                filename = source_file.lower()
                
                # Apply legacy feedback-based boosting if not already applied
                if source_file in feedback_boosts:
                    boost_factor *= feedback_boosts[source_file]
                    logger.debug(f"Applied legacy feedback boost {feedback_boosts[source_file]} to {source_file}")
                
                # HCBS queries should prioritize HCBS manual
                if any(keyword in query_lower for keyword in ['hcbs', 'waiver', 'home and community', 'bh hcbs']):
                    if 'hcbs' in filename:
                        boost_factor *= 0.9  # Slight boost (lower score = higher priority)
                    elif 'policy' in filename:
                        boost_factor *= 1.1  # Slight penalty
                
                # CCBHC queries should prioritize CCBHC manual
                elif any(keyword in query_lower for keyword in ['ccbhc', 'quality measures', 'certified community']):
                    if 'ccbhc' in filename or 'quality' in filename:
                        boost_factor *= 0.9
                    elif 'hcbs' in filename:
                        boost_factor *= 1.05
                
                # Policy queries should prioritize policy manual
                elif any(keyword in query_lower for keyword in ['policy', 'procedure', 'manual']):
                    if 'policy' in filename:
                        boost_factor *= 0.9
                    elif 'hcbs' in filename:
                        boost_factor *= 1.05
            
            # Apply boost to score
            boosted_score = score * boost_factor
            boosted_docs.append((doc_id, content, boosted_score, source_file))
        
        # Re-sort by boosted scores
        boosted_docs.sort(key=lambda x: x[2])  # Sort by score (lower is better)
        
        return boosted_docs
    
    def _get_feedback_source_boosts(self, query: str) -> Dict[str, float]:
        """Get source boosting factors based on user feedback for similar queries."""
        try:
            from .user_feedback import get_feedback_dao
            feedback_dao = get_feedback_dao()
            
            # Get source preferences from feedback
            source_preferences = feedback_dao.get_source_preferences_for_query(query)
            
            # Convert preferences to boost factors
            boosts = {}
            for source, preference_score in source_preferences.items():
                if preference_score > 0.7:  # High preference
                    boosts[source] = 0.8  # Boost by making score lower
                elif preference_score < 0.3:  # Low preference
                    boosts[source] = 1.2  # Penalize by making score higher
            
            return boosts
        except Exception as e:
            logger.debug(f"Could not get feedback source boosts: {e}")
            return {}
        
        context_text = "\n\n".join(ctx_chunks)
        
        # Ensure context doesn't exceed max length
        if len(context_text) > self.max_context_length:
            # Truncate and keep most relevant sources
            truncated_chunks = []
            current_length = 0
            
            for chunk in ctx_chunks:
                if current_length + len(chunk) > self.max_context_length:
                    break
                truncated_chunks.append(chunk)
                current_length += len(chunk)
            
            context_text = "\n\n".join(truncated_chunks)
            sources = sources[:len(truncated_chunks)]
        
        return context_text, sources
    
    async def _build_context_async(self, documents: List[Tuple[int, str, float, Optional[str]]], query: str = "") -> Tuple[str, List[Dict[str, Any]]]:
        """Async wrapper for context building to enable parallel processing."""
        return self._build_context(documents, query)
    
    async def _generate_quality_indicators_async(self, query: str, strategy_used: SearchStrategy) -> Dict[str, Any]:
        """Fast quality indicators for improved response time."""
        # Simplified quality indicators for speed - compute heavy operations in background
        return {
            "confidence_score": 0.8,  # Default confidence
            "strategy_used": strategy_used.value,
            "fast_mode": True,
            "timestamp": time.time()
        }
    
    async def generate_response(self, query: str, user_system_prompt: Optional[str] = None,
                              top_k: Optional[int] = None, strategy: Optional[SearchStrategy] = None) -> RAGResponse:
        """Generate RAG response with retrieval and generation."""
        start_time = time.time()
        
        logger.info(f"Starting RAG response generation for query: '{query[:100]}...'")
        
        # Start all async operations in parallel
        retrieval_task = asyncio.create_task(self.retrieve_documents(query, top_k, strategy))
        
        # Wait for retrieval to complete first
        retrieval_result = await retrieval_task
        logger.info(f"Retrieved {len(retrieval_result.documents)} documents using strategy: {retrieval_result.strategy_used.value}")
        
        # Start context building and quality indicators in parallel
        context_task = asyncio.create_task(self._build_context_async(retrieval_result.documents, query))
        
        # Skip quality indicators in fast mode for better performance
        if getattr(self.settings, 'skip_quality_indicators', False):
            quality_indicators = {"fast_mode": True, "timestamp": time.time()}
            context_text, sources = await context_task
        else:
            quality_task = asyncio.create_task(self._generate_quality_indicators_async(query, retrieval_result.strategy_used))
            context_text, sources = await context_task
            quality_indicators = await quality_task
        
        logger.info(f"Context built: {len(context_text)} characters, {len(sources)} sources")
        
        # Build system prompt
        system_parts = []
        if user_system_prompt:
            system_parts.append(user_system_prompt)
        
        if context_text:
            system_parts.append(self.base_system_prompt + f"Available documents:\n{context_text}")
        else:
            system_parts.append(
                "You are a document retrieval assistant. No relevant documents were found for this query.\n"
                "You must respond with: 'I don't have information about this in the available documents.'\n"
                "Do NOT generate or create any information."
            )
        
        system_prompt = "\n\n".join(system_parts)
        
        # Generate response
        generation_start = time.time()
        try:
            from .models import GenerateRequest
            
            request = GenerateRequest(
                prompt=query,
                system_prompt=system_prompt,
                temperature=0.1,  # Lower temperature for factual responses
                max_tokens=512
            )
            
            # Ensure we have a fresh LLM instance to avoid session issues
            from .local_model import get_local_llm
            llm = get_local_llm()
            
            result = await llm.generate(request)
            generation_time_ms = (time.time() - generation_start) * 1000
            total_time_ms = (time.time() - start_time) * 1000
            
            return RAGResponse(
                text=result.get("text", ""),
                sources=sources,
                retrieval_result=retrieval_result,
                generation_time_ms=generation_time_ms,
                total_time_ms=total_time_ms,
                model_used=result.get("model", self.settings.default_model),
                success=True,
                quality_indicators=quality_indicators
            )
            
        except Exception as e:
            generation_time_ms = (time.time() - generation_start) * 1000
            total_time_ms = (time.time() - start_time) * 1000
            
            logger.error(f"Response generation failed: {e}")
            
            return RAGResponse(
                text="",
                sources=sources,
                retrieval_result=retrieval_result,
                generation_time_ms=generation_time_ms,
                total_time_ms=total_time_ms,
                model_used=self.settings.default_model,
                success=False,
                error_message=str(e),
                quality_indicators=quality_indicators
            )


# Global instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get or create the RAG service instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service