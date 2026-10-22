"""
NSIndex API - Main interface for the NorthStar search system
"""
from typing import Dict, Any, List, Optional, Set
from .core import split_query, detect_categories
from .pack_manager import PackManager
from .adaptive_indexer import AdaptiveIndex
from .intent_detector import detect_intent, group_by_ecosystem
from .semantic_walls import SemanticWalls


class NSIndex:
    """Main NSIndex search engine interface"""
    def __init__(self, debug_mode: bool = False):
        self.pack_manager = PackManager()
        self.adaptive_index = AdaptiveIndex()
        self.semantic_walls = SemanticWalls(debug_mode=debug_mode)
        self._search_cache: Dict[str, Dict[str, Any]] = {}  # Simple in-memory cache
    
    def search(
        self,
        query: str,
        include_adaptive: bool = True,
        categories: Optional[Set[str]] = None,
        limit_per_category: int = 10,
        use_interest_profile: bool = True,
        expand_ecosystem_grouping: bool = True,
        expand_relationships: bool = False,
        max_expanded: int = 20,
        use_semantic_walls: bool = True
    ) -> Dict[str, Any]:
        """
        Main search function that combines pack search and adaptive index results
        with all new features: intent detection, relationship expansion, interest profile,
        and semantic walls system!
        """
        # Check cache first
        cache_key = f"{query}:{include_adaptive}:{categories}:{use_interest_profile}:{use_semantic_walls}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]
        
        query_keywords = split_query(query)
        interest_profile = self.adaptive_index.get_interest_profile() if use_interest_profile else {}
        
        results: Dict[str, Any] = {
            "pack_results": {},
            "adaptive_results": [],
            "intent": detect_intent(query),
            "interest_profile": interest_profile,
            "expanded_results": [],
            "semantic_walls_applied": use_semantic_walls
        }
        
        # Search category packs
        raw_pack_results = self.pack_manager.search(
            query, categories, limit_per_category
        )
        
        # Search adaptive index
        raw_adaptive_results = []
        if include_adaptive:
            raw_adaptive_results = self.adaptive_index.search(
                query, list(categories) if categories else None, limit_per_category, use_interest_profile
            )
        
        # Expand results using relationships if requested
        raw_expanded_results = []
        if expand_relationships:
            raw_expanded_results = self.pack_manager.expand_results(
                raw_pack_results,
                max_expanded=max_expanded
            )
        
        # Combine all raw results
        all_raw_results = []
        for cat, sites in raw_pack_results.items():
            for site in sites:
                all_raw_results.append({**site, "source": "pack"})
        for site in raw_adaptive_results:
            all_raw_results.append({**site, "source": "adaptive"})
        for site in raw_expanded_results:
            all_raw_results.append({**site, "source": "expanded"})
        
        # Apply semantic walls
        if use_semantic_walls:
            processed_results = self.semantic_walls.filter_and_rank_results(
                all_raw_results, query_keywords, interest_profile
            )
            results["processed_results"] = processed_results
            results["semantic_debug"] = self.semantic_walls.get_debug_info()
        else:
            results["processed_results"] = all_raw_results
        
        # Also keep original pack results for reference
        results["pack_results"] = raw_pack_results
        results["adaptive_results"] = raw_adaptive_results
        results["expanded_results"] = raw_expanded_results
        
        # Cache result for 5 minutes
        self._search_cache[cache_key] = results
        if len(self._search_cache) > 100:
            self._search_cache.clear()
        
        return results
    
    def get_interest_profile(self) -> Dict[str, float]:
        """Get user's interest profile from adaptive index"""
        return self.adaptive_index.get_interest_profile()
    
    def expand_by_ecosystem(
        self,
        query: str,
        page: int = 1,
        use_semantic_walls: bool = True
    ) -> Dict[str, Any]:
        """Get semantically paginated results, each page expands semantically"""
        base_results = self.search(
            query, expand_relationships=True, max_expanded=30, use_semantic_walls=use_semantic_walls
        )
        intent = base_results["intent"]
        
        # Use processed results if semantic walls are applied
        if use_semantic_walls and "processed_results" in base_results:
            all_results = base_results["processed_results"]
        else:
            all_results = []
            for cat, sites in base_results["pack_results"].items():
                for site in sites:
                    all_results.append({**site, "source": "pack"})
            for site in base_results["adaptive_results"]:
                all_results.append({**site, "source": "adaptive"})
            for site in base_results["expanded_results"]:
                all_results.append({**site, "source": "expanded"})
        
        # Group by ecosystem
        grouped = group_by_ecosystem(all_results, intent)
        
        # Semantic pagination: page 1 is exact/official, page 2 is related, page3+ is exploratory
        page_size = 10
        start = (page -1)*page_size
        end = start + page_size
        
        # Flatten grouped into ordered list for pagination
        flattened = []
        for ecosystem in sorted(intent.keys(), key=lambda x: -intent[x]) + list(grouped.keys()):
            if ecosystem in grouped:
                flattened.extend(grouped[ecosystem])
        
        paginated_results = flattened[start:end]
        
        return {
            "page": page,
            "page_size": page_size,
            "total_results": len(flattened),
            "results": paginated_results,
            "intent": intent,
            "interest_profile": base_results["interest_profile"],
            "semantic_walls_applied": base_results["semantic_walls_applied"]
        }
    
    def index_visited_page(
        self,
        url: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ):
        """Index a visited page into the adaptive index"""
        self.adaptive_index.index_page(url, title, description, keywords)
        # Invalidate cache when new page is indexed
        self._search_cache.clear()


# Global instance
_nsindex_instance: Optional[NSIndex] = None


def get_nsindex(debug_mode: bool = False) -> NSIndex:
    """Get the global NSIndex instance"""
    global _nsindex_instance
    if _nsindex_instance is None or _nsindex_instance.semantic_walls.debug_mode != debug_mode:
        _nsindex_instance = NSIndex(debug_mode=debug_mode)
    return _nsindex_instance

