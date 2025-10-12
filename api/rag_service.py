"""
RAG Service Layer - Centralized RAG logic with improved architecture.
"""

import time
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


class RAGService:
    """Centralized RAG service with improved architecture."""
    
    def __init__(self):
        self.settings = get_settings()
        self.dao = get_dao()
        self.llm = get_local_llm()
        
        # RAG configuration
        self.default_top_k = 5
        self.max_context_length = 8000  # Tokens
        self.relevance_threshold = 50.0  # Adjusted for actual score ranges
        
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
        
        embedding_time_ms = None
        documents = []
        
        try:
            if strategy in [SearchStrategy.SEMANTIC, SearchStrategy.HYBRID, SearchStrategy.ENHANCED, SearchStrategy.COMBINED]:
                # Generate embeddings
                embed_start = time.time()
                vectors = await embed_texts([query])
                embedding_time_ms = (time.time() - embed_start) * 1000
                query_vec = vectors[0]
                
                # Execute search based on strategy
                if strategy == SearchStrategy.SEMANTIC:
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
            documents = self._filter_by_relevance(documents, strategy)
            
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
        """Determine optimal search strategy based on query characteristics."""
        query_lower = query.lower()
        
        # Drug/substance queries benefit from enhanced search
        drug_keywords = ['drug', 'substance', 'test', 'testing', 'list']
        if any(keyword in query_lower for keyword in drug_keywords):
            return SearchStrategy.ENHANCED
        
        # Short queries or exact terms benefit from keyword search
        if len(query.split()) <= 2 or any(char in query for char in ['"', "'"]):
            return SearchStrategy.KEYWORD
        
        # Complex queries benefit from hybrid search
        if len(query.split()) > 10 or '?' in query:
            return SearchStrategy.HYBRID if self.settings.enable_hybrid_search else SearchStrategy.COMBINED
        
        # Default to enhanced search
        return SearchStrategy.ENHANCED
    
    def _filter_by_relevance(self, documents: List[Tuple[int, str, float, Optional[str]]], 
                           strategy: SearchStrategy) -> List[Tuple[int, str, float, Optional[str]]]:
        """Filter documents by relevance threshold."""
        if not documents:
            return documents
        
        # Different thresholds for different strategies
        if strategy == SearchStrategy.SEMANTIC:
            # For semantic search, lower scores are better (cosine distance)
            return [doc for doc in documents if doc[2] <= self.relevance_threshold]
        elif strategy == SearchStrategy.KEYWORD:
            # For keyword search, we trust the ranking
            return documents
        else:
            # For hybrid/enhanced, use adaptive threshold
            if documents:
                best_score = documents[0][2]
                threshold = best_score * 2  # Allow scores up to 2x the best score
                return [doc for doc in documents if doc[2] <= threshold]
        
        return documents
    
    def _build_context(self, documents: List[Tuple[int, str, float, Optional[str]]]) -> Tuple[str, List[Dict[str, Any]]]:
        """Build context string and source metadata from retrieved documents."""
        if not documents:
            return "", []
        
        ctx_chunks = []
        sources = []
        
        for i, (doc_id, content, score, source_file) in enumerate(documents):
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
            normalized_score = max(0, min(1, 1 - score)) if score < 1 else max(0, min(1, 1 / (1 + score)))
            
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
    
    async def generate_response(self, query: str, user_system_prompt: Optional[str] = None,
                              top_k: Optional[int] = None, strategy: Optional[SearchStrategy] = None) -> RAGResponse:
        """Generate RAG response with retrieval and generation."""
        start_time = time.time()
        
        # Retrieve documents
        retrieval_result = await self.retrieve_documents(query, top_k, strategy)
        
        # Build context and sources
        context_text, sources = self._build_context(retrieval_result.documents)
        
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
                success=True
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
                error_message=str(e)
            )


# Global instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get or create the RAG service instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service