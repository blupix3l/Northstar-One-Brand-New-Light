"""
NorthStar Intent Detector & Semantic Ecosystem Grouping
Detects user intent and groups results by semantic ecosystems
"""
import re
import json
from typing import Dict, List, Tuple, Set
from collections import defaultdict

# Category-keyword mappings (expanded for ecosystem detection)
_ECOSYSTEM_KEYWORDS = {
    # Coding & Technology
    "coding": ["python", "java", "javascript", "js", "typescript", "ts", "react", "vue", 
               "angular", "next.js", "flask", "django", "fastapi", "vscode", "vim", 
               "neovim", "git", "github", "api", "programming", "code", "software", 
               "developer", "engineer", "rust", "go", "golang", "c++", "c", "ruby", 
               "php", "swift", "kotlin", "flutter", "android", "ios", "mobile"],
    "ai": ["ai", "machine learning", "ml", "deep learning", "chatgpt", "openai", 
           "claude", "anthropic", "llm", "gpt", "stable diffusion", "dalle", 
           "generative", "neural network", "tensorflow", "pytorch", "huggingface"],
    "linux": ["linux", "ubuntu", "debian", "fedora", "arch", "gentoo", "manjaro",
              "kernel", "bash", "shell", "terminal", "cli", "command line", 
              "systemd", "gnu", "unix"],
    "gaming": ["game", "games", "gaming", "steam", "epic", "gog", "ps5", 
               "playstation", "xbox", "switch", "nintendo", "mod", "mods", 
               "walkthrough", "guide", "twitch", "youtube gaming"],
    "design": ["design", "figma", "photoshop", "illustrator", "indesign",
               "ui", "ux", "graphic design", "vector", "drawing", "illustration"],
    "security": ["security", "cybersecurity", "hacking", "privacy", "encryption",
                 "vpn", "firewall", "penetration testing", "pentest", "cve"],
    
    # Science & Education
    "science": ["science", "physics", "chemistry", "biology", "astronomy", "math",
                "mathematics", "calculus", "statistics", "data science", "research"],
    "education": ["education", "school", "university", "college", "course", 
                  "learning", "learn", "study", "tutorial", "lecture", "notes"],
    
    # Daily life & Productivity
    "productivity": ["productivity", "todo", "task", "notion", "obsidian", 
                     "notes", "workflow", "efficiency", "organization"],
    "finance": ["finance", "money", "banking", "stock", "stocks", "crypto", 
                "bitcoin", "ethereum", "investment", "budget", "tax"],
    "travel": ["travel", "flight", "flights", "hotel", "hotels", "booking", 
               "trip", "vacation", "destination", "map", "maps", "navigation"],
    "cooking": ["cooking", "recipe", "recipes", "food", "cook", "bake", 
                "kitchen", "chef", "dinner", "lunch", "breakfast"],
    
    # Entertainment
    "music": ["music", "song", "songs", "spotify", "apple music", "youtube music",
              "pandora", "artist", "band", "album", "playlist"],
    "movies": ["movie", "movies", "film", "films", "netflix", "hulu", 
               "disney+", "prime video", "cinema", "actor", "director"],
    "books": ["book", "books", "read", "reading", "author", "novel", 
              "fiction", "non-fiction", "kindle", "audible"],
    "social": ["social", "twitter", "x", "facebook", "instagram", "reddit", 
               "tiktok", "snapchat", "discord", "forum", "community"]
}

def detect_intent(query: str) -> Dict[str, float]:
    """
    Detect user intent and return confidence scores for each semantic ecosystem
    Example: "python" → {"coding": 0.92, "animals": 0.31}
    """
    query_lower = query.lower()
    scores = defaultdict(float)
    total_keywords = 0
    
    for ecosystem, keywords in _ECOSYSTEM_KEYWORDS.items():
        matches = 0
        keyword_count = len(keywords)
        
        for keyword in keywords:
            if keyword in query_lower:
                matches += 1
                
        if matches > 0:
            # Normalize score based on keyword frequency and number of matches
            scores[ecosystem] = (matches / keyword_count) * 0.9 + (0.1 * min(matches / 3, 1.0))
            total_keywords += matches

    # If no ecosystems detected, return empty dict
    return dict(scores) if scores else {"general": 0.5}


def group_by_ecosystem(
    results: List[Dict], 
    intent_scores: Dict[str, float]
) -> Dict[str, List[Dict]]:
    """
    Group results by semantic ecosystem based on intent and result metadata
    """
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    all_categories = list(intent_scores.keys())
    
    for result in results:
        assigned = False
        category = result.get("category", "general")
        
        if category in all_categories:
            grouped[category].append(result)
            assigned = True
        
        if not assigned:
            if intent_scores:
                best_category = max(intent_scores.items(), key=lambda x: x[1])[0]
                grouped[best_category].append(result)
            else:
                grouped["general"].append(result)
    
    return dict(grouped)
