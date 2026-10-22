"""
NSIndex Core - Query splitting, category detection, search logic
"""
import re
from typing import List, Dict, Any, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import json
import sqlite3


# Keyword to category mapping
KEYWORD_CATEGORY_MAP = {
    # Encoding
    "base64": "encoding", "encoder": "encoding", "decoder": "encoding",
    "utf-8": "encoding", "unicode": "encoding", "encode": "encoding",
    "decode": "encoding", "urlencode": "encoding", "urldecode": "encoding",
    "hex": "encoding", "binary": "encoding", "json": "encoding",

    # Travel
    "travel": "travel", "flight": "travel", "hotel": "travel", "booking": "travel",
    "trip": "travel", "vacation": "travel", "destination": "travel",
    "airport": "travel", "train": "travel", "route": "travel",
    "map": "travel", "navigation": "travel",

    # Coding
    "python": "coding", "javascript": "coding", "java": "coding",
    "cpp": "coding", "c++": "coding", "c#": "coding",
    "rust": "coding", "go": "coding", "golang": "coding",
    "programming": "coding", "code": "coding", "developer": "coding",
    "github": "coding", "git": "coding", "stackoverflow": "coding",
    "docs": "coding", "documentation": "coding", "api": "coding",
    "html": "coding", "css": "coding", "react": "coding",
    "vue": "coding", "angular": "coding", "node": "coding",

    # Gaming
    "game": "gaming", "steam": "gaming", "epic": "gaming", "gog": "gaming",
    "xbox": "gaming", "playstation": "gaming", "nintendo": "gaming",
    "mod": "gaming", "mods": "gaming", "walkthrough": "gaming",
    "guide": "gaming", "wiki": "gaming",

    # AI
    "ai": "ai", "artificial intelligence": "ai", "chatgpt": "ai",
    "claude": "ai", "ollama": "ai", "llm": "ai",
    "machine learning": "ai", "ml": "ai", "deep learning": "ai",
    "generative": "ai", "prompt": "ai",

    # Video
    "video": "video", "youtube": "video", "vimeo": "video",
    "stream": "video", "streaming": "video", "twitch": "video",
    "tiktok": "video", "edit": "video", "editor": "video",

    # Education
    "learn": "education", "course": "education", "tutorial": "education",
    "school": "education", "university": "education", "edX": "education",
    "coursera": "education", "udemy": "education", "khan": "education",
    "study": "education", "quiz": "education", "flashcards": "education",

    # Tools
    "tool": "tools", "calculator": "tools", "converter": "tools",
    "utility": "tools", "productivity": "tools", "notion": "tools",
    "obsidian": "tools", "todo": "tools", "task": "tools",
    "calendar": "tools", "email": "tools"
}


def split_query(query: str) -> List[str]:
    """
    Split query into keywords, handling 'and', commas, etc.
    
    Example input: "encoder and travel"
    Output: ["encoder", "travel"]
    """
    # Normalize query to lowercase
    query = query.lower().strip()
    
    # Replace separators with spaces
    separators = [" and ", ",", " & ", " + "]
    for sep in separators:
        query = query.replace(sep, " ")
    
    # Split into words and clean
    keywords = re.split(r'\s+', query)
    keywords = [kw.strip() for kw in keywords if kw.strip()]
    
    # Remove duplicates while preserving order
    seen = set()
    result = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    
    return result


def detect_categories(keywords: List[str]) -> Set[str]:
    """
    Detect relevant categories from a list of keywords
    """
    categories = set()
    for kw in keywords:
        if kw in KEYWORD_CATEGORY_MAP:
            categories.add(KEYWORD_CATEGORY_MAP[kw])
    return categories


def get_base_dir() -> str:
    """Get base directory of the project"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_nsindex_dir() -> str:
    """Get nsindex directory"""
    return os.path.join(get_base_dir(), "nsindex")


def get_packs_dir() -> str:
    return os.path.join(get_nsindex_dir(), "packs")


def get_adaptive_dir() -> str:
    return os.path.join(get_nsindex_dir(), "adaptive")
