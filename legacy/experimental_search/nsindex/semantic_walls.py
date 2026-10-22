"""
Semantic Walls System - Handles ecosystem partitioning, distance scoring, wall penalties, etc.
"""
from typing import Dict, List, Any, Optional
from collections import defaultdict
import math


class SemanticWalls:
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.debug_log: List[Dict[str, Any]] = []
        
        # Configuration parameters
        self.cross_domain_penalty_base = 0.5  # Base penalty for cross-domain transitions
        self.semantic_distance_threshold = 0.3  # Min distance to be considered "close"
        self.max_exploration_depth = 3  # Max steps away from initial query
        self.dominant_node_saturation = 5  # Max results per dominant node in top N
        self.interest_profile_max_boost = 1.3  # Max multiplier from interest profile
        self.coherence_min_threshold = 0.15  # Min coherence to keep a result
        
    def _log_debug(self, message: str, data: Any = None):
        """Log debug information if debug mode is enabled"""
        if self.debug_mode:
            log_entry = {"message": message}
            if data is not None:
                log_entry["data"] = data
            self.debug_log.append(log_entry)
    
    def calculate_semantic_distance(
        self,
        source_keywords: List[str],
        target_keywords: List[str],
        source_category: Optional[str] = None,
        target_category: Optional[str] = None
    ) -> float:
        """
        Calculate lightweight semantic distance between two nodes using keyword overlap,
        including partial matches for better flexibility.
        Returns distance 0-1 (0 = identical, 1 = completely unrelated).
        """
        if not source_keywords or not target_keywords:
            return 1.0
        
        source_lower = [kw.lower() for kw in source_keywords]
        target_lower = [kw.lower() for kw in target_keywords]
        
        # Calculate match score
        match_score = 0.0
        for src_kw in source_lower:
            for tgt_kw in target_lower:
                if src_kw == tgt_kw:
                    match_score += 1.0
                elif src_kw in tgt_kw or tgt_kw in src_kw:
                    match_score += 0.5
        
        # Normalize to 0-1 similarity
        max_possible = max(len(source_keywords), len(target_keywords))
        similarity = match_score / max_possible if max_possible > 0 else 0.0
        similarity = min(similarity, 1.0)
        
        # Add category penalty if different
        category_penalty = 0.0
        if source_category and target_category and source_category != target_category:
            category_penalty = self.cross_domain_penalty_base
        
        distance = 1.0 - similarity
        distance += category_penalty
        distance = min(distance, 1.0)  # Clamp to 0-1
        
        self._log_debug("Semantic distance calculated", {
            "source_keywords": source_keywords,
            "target_keywords": target_keywords,
            "source_category": source_category,
            "target_category": target_category,
            "match_score": match_score,
            "similarity": similarity,
            "category_penalty": category_penalty,
            "distance": distance
        })
        
        return distance
    
    def apply_semantic_penalty(
        self,
        result: Dict[str, Any],
        query_keywords: List[str],
        exploration_depth: int,
        dominant_node_counts: Dict[str, int],
        interest_profile: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Apply all semantic penalties and boosts to a result, with debug info.
        """
        debug_info = {}
        
        base_score = result.get("_score", result.get("priority", 50))
        final_score = base_score
        
        # 1. Calculate semantic distance penalty
        result_keywords = result.get("keywords", [])
        result_category = result.get("category", None)
        semantic_distance = self.calculate_semantic_distance(
            query_keywords, result_keywords, None, result_category
        )
        debug_info["semantic_distance"] = semantic_distance
        distance_penalty = semantic_distance * 30
        final_score -= distance_penalty
        debug_info["distance_penalty"] = distance_penalty
        
        # 2. Exploration depth penalty
        depth_penalty = exploration_depth * 15
        final_score -= depth_penalty
        debug_info["exploration_depth"] = exploration_depth
        debug_info["depth_penalty"] = depth_penalty
        
        # 3. Dominant node penalty
        node_identifier = result.get("url", result.get("title", ""))
        node_count = dominant_node_counts.get(node_identifier, 0)
        if node_count >= self.dominant_node_saturation:
            dominant_penalty = (node_count - self.dominant_node_saturation + 1) * 20
            final_score -= dominant_penalty
            debug_info["dominant_node_count"] = node_count
            debug_info["dominant_penalty"] = dominant_penalty
        
        # 4. Interest profile boost (bounded)
        if interest_profile and result_category in interest_profile:
            interest_boost = min(interest_profile[result_category] / 100 * base_score, 
                                 base_score * (self.interest_profile_max_boost - 1))
            final_score += interest_boost
            debug_info["interest_boost"] = interest_boost
        
        # 5. Semantic purity validation
        semantic_purity = 1.0 - semantic_distance
        debug_info["semantic_purity"] = semantic_purity
        if semantic_purity < self.coherence_min_threshold:
            final_score -= 1000  # Effectively filter this result
            debug_info["purity_filtered"] = True
        
        result_with_debug = result.copy()
        result_with_debug["_final_score"] = final_score
        result_with_debug["_semantic_debug"] = debug_info
        
        return result_with_debug
    
    def filter_and_rank_results(
        self,
        results: List[Dict[str, Any]],
        query_keywords: List[str],
        interest_profile: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Apply semantic wall system to filter and rank results.
        """
        dominant_node_counts: Dict[str, int] = defaultdict(int)
        processed_results: List[Dict[str, Any]] = []
        
        for idx, result in enumerate(results):
            # Estimate exploration depth (simplified: based on position in list)
            exploration_depth = math.floor(idx / 10)
            
            processed = self.apply_semantic_penalty(
                result, query_keywords, exploration_depth, dominant_node_counts, interest_profile
            )
            
            # Track dominant nodes
            node_identifier = processed.get("url", processed.get("title", ""))
            dominant_node_counts[node_identifier] += 1
            
            processed_results.append(processed)
        
        # Filter out results with too low score and sort
        filtered = [r for r in processed_results if r["_final_score"] > -500]
        filtered.sort(key=lambda x: -x["_final_score"])
        
        return filtered
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get all debug logs and system state"""
        return {
            "config": {
                "cross_domain_penalty_base": self.cross_domain_penalty_base,
                "semantic_distance_threshold": self.semantic_distance_threshold,
                "max_exploration_depth": self.max_exploration_depth,
                "dominant_node_saturation": self.dominant_node_saturation,
                "interest_profile_max_boost": self.interest_profile_max_boost,
                "coherence_min_threshold": self.coherence_min_threshold
            },
            "logs": self.debug_log
        }
