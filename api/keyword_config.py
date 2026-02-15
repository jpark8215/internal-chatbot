import json
import os
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from .logging_config import get_logger
from .rag_service import SearchStrategy

logger = get_logger(__name__)

class KeywordConfig:
    """Manages keyword-based configuration for search strategies and boosting."""
    
    _instance = None
    _rules: List[Dict[str, Any]] = []
    _last_loaded: float = 0
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config/keyword_rules.json relative to project root
            # Assuming this file is in api/ and project root is one level up
            base_dir = Path(__file__).parent.parent
            config_path = str(base_dir / "config" / "keyword_rules.json")
            
        self.config_path = config_path
        self.load_rules()
    
    @classmethod
    def get_instance(cls) -> 'KeywordConfig':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = KeywordConfig()
        return cls._instance
        
    def load_rules(self):
        """Load rules from JSON configuration file."""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Keyword rules file not found at {self.config_path}")
                self._rules = []
                return
                
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                self._rules = data.get("rules", [])
            logger.info(f"Loaded {len(self._rules)} keyword rules from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load keyword rules: {e}")
            self._rules = []

    def get_strategy_for_query(self, query: str) -> Optional[SearchStrategy]:
        """Determine if a query matches any rule for strategy selection."""
        query_lower = query.lower()
        
        # Check explicit rules first
        for rule in self._rules:
            keywords = rule.get("keywords", [])
            if any(k.lower() in query_lower for k in keywords):
                strategy_str = rule.get("strategy")
                if strategy_str:
                    try:
                        return SearchStrategy(strategy_str.lower())
                    except ValueError:
                        logger.warning(f"Invalid strategy '{strategy_str}' in rule")
        
        return None

    def get_boost_rules_for_query(self, query: str) -> List[str]:
        """Get list of source keywords to boost for this query."""
        query_lower = query.lower()
        boost_sources = []
        
        for rule in self._rules:
            keywords = rule.get("keywords", [])
            if any(k.lower() in query_lower for k in keywords):
                sources = rule.get("boost_sources", [])
                boost_sources.extend(sources)
                
        return list(set(boost_sources))  # Deduplicate
