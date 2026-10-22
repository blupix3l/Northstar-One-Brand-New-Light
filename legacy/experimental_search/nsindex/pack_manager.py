"""
Pack Manager - Load and manage category packs
"""
import os
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Set
from .core import get_packs_dir, split_query, detect_categories


class Pack:
    """Represents a single category pack"""
    def __init__(self, category: str, pack_dir: str):
        self.category = category
        self.pack_dir = pack_dir
        self.pack_json_path = os.path.join(pack_dir, "pack.json")
        self.index_db_path = os.path.join(pack_dir, "index.sqlite")
        self.metadata: Dict[str, Any] = {}
        self.sites: List[Dict[str, Any]] = []
        self._site_lookup: Dict[str, Dict[str, Any]] = {}  # For quick lookups
        self._loaded = False
    
    def load(self):
        """Load pack from disk"""
        if self._loaded:
            return
        
        # Load pack metadata
        if os.path.exists(self.pack_json_path):
            try:
                with open(self.pack_json_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                    self.sites = self.metadata.get("sites", [])
                # Build lookup table for quick searches
                self._site_lookup = {}
                for site in self.sites:
                    self._site_lookup[site["url"]] = site
            except Exception as e:
                print(f"[NSIndex] Error loading {self.pack_json_path}: {e}")
                self.sites = []
                self._site_lookup = {}
        
        self._loaded = True
    
    def search(self, keywords: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """Search this pack for sites matching keywords"""
        results = []
        
        # Simple keyword matching (case-insensitive)
        keywords_lower = [kw.lower() for kw in keywords]
        
        for site in self.sites:
            score = 0
            title = site.get("title", "").lower()
            desc = site.get("description", "").lower()
            site_keywords = [kw.lower() for kw in site.get("keywords", [])]
            
            # Count matches
            for kw in keywords_lower:
                if kw in title:
                    score += 3
                if kw in desc:
                    score += 2
                if kw in site_keywords:
                    score += 5
            
            # Add priority boost
            score += site.get("priority", 50)
            
            # Official site boost
            if site.get("official", False):
                score += 20
            
            if score > 0:
                site_with_score = site.copy()
                site_with_score["_score"] = score
                results.append(site_with_score)
        
        # Sort by score, descending
        results.sort(key=lambda x: -x["_score"])
        return results[:limit]
    
    def _find_site_by_keywords(self, keywords: List[str]) -> List[Dict[str, Any]]:
        matches = []
        keywords_lower = [kw.lower() for kw in keywords]
        for site in self.sites:
            site_keywords = [kw.lower() for kw in site.get("keywords", [])]
            title_lower = site.get("title", "").lower()
            for kw in keywords_lower:
                if kw in site_keywords or kw in title_lower:
                    matches.append(site)
                    break
        return matches


class PackManager:
    """Manages all category packs"""
    def __init__(self):
        self.packs: Dict[str, Pack] = {}
        self._all_sites_lookup: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
    
    def initialize(self):
        """Load all available packs"""
        if self._initialized:
            return
        
        packs_dir = get_packs_dir()
        if not os.path.exists(packs_dir):
            return
        
        # Iterate all category directories in packs_dir
        for entry in os.listdir(packs_dir):
            cat_dir = os.path.join(packs_dir, entry)
            if os.path.isdir(cat_dir):
                pack = Pack(entry, cat_dir)
                self.packs[entry] = pack
                pack.load()
                for site in pack.sites:
                    self._all_sites_lookup[site["url"]] = {**site, "pack": entry}
        
        self._initialized = True
    
    def get_pack(self, category: str) -> Optional[Pack]:
        """Get a specific pack by category"""
        self.initialize()
        if category in self.packs:
            self.packs[category].load()
            return self.packs[category]
        return None
    
    def get_all_packs(self) -> List[Pack]:
        """Get all packs"""
        self.initialize()
        for pack in self.packs.values():
            pack.load()
        return list(self.packs.values())
    
    def search(
        self, 
        query: str, 
        categories: Optional[Set[str]] = None,
        limit_per_category: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search all (or specified) packs and return categorized results
        """
        keywords = split_query(query)
        if not categories:
            categories = detect_categories(keywords)
        
        # If no categories detected, search all packs
        if not categories:
            categories = set(self.packs.keys())
        
        results: Dict[str, List[Dict[str, Any]]] = {}
        
        # Parallel search across packs
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {}
            for cat in categories:
                pack = self.get_pack(cat)
                if pack:
                    futures[executor.submit(pack.search, keywords, limit_per_category)] = cat
            
            for future in as_completed(futures):
                cat = futures[future]
                try:
                    cat_results = future.result()
                    if cat_results:
                        results[cat] = cat_results
                except Exception as e:
                    print(f"[NSIndex] Error searching {cat}: {e}")
        
        return results
    
    def expand_results(
        self,
        initial_results: Dict[str, List[Dict[str, Any]]],
        expansion_depth: int = 1,
        max_expanded: int = 20
    ) -> List[Dict[str, Any]]:
        """Expand initial results using relationship graph"""
        self.initialize()
        expanded = []
        seen_urls = set()
        
        # Add initial results to seen
        for cat_results in initial_results.values():
            for site in cat_results:
                seen_urls.add(site["url"])
        
        # Now traverse relationships
        for cat_results in initial_results.values():
            for site in cat_results:
                related_keywords = site.get("related", [])
                # Search all packs for matches
                for pack in self.packs.values():
                    rel_sites = pack._find_site_by_keywords(related_keywords)
                    for s in rel_sites:
                        if s["url"] not in seen_urls:
                            seen_urls.add(s["url"])
                            s_copy = s.copy()
                            s_copy["_expanded_from"] = site["title"]
                            expanded.append(s_copy)
        
        # Sort and limit
        expanded.sort(key=lambda x: (-x.get("priority", 50)))
        return expanded[:max_expanded]
