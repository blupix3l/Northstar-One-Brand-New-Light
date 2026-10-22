"""
Adaptive Indexer - Index visited pages automatically
"""
import os
import sqlite3
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from collections import defaultdict
from .core import get_adaptive_dir, KEYWORD_CATEGORY_MAP


class AdaptiveIndex:
    def __init__(self):
        self.adaptive_dir = get_adaptive_dir()
        self.visited_db_path = os.path.join(self.adaptive_dir, "visited.sqlite")
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database"""
        conn = sqlite3.connect(self.visited_db_path)
        cursor = conn.cursor()
        
        # Create visited sites table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visited_sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT,
                description TEXT,
                keywords TEXT,
                category TEXT,
                visit_count INTEGER DEFAULT 1,
                last_visited REAL DEFAULT (strftime('%s', 'now')),
                added_at REAL DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # Create index for faster search
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_visited_url ON visited_sites(url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_visited_category ON visited_sites(category)')
        
        conn.commit()
        conn.close()
    
    def detect_category_from_keywords(self, keywords: List[str]) -> Optional[str]:
        """Detect category from a list of keywords"""
        category_counts = {}
        for kw in keywords:
            if kw in KEYWORD_CATEGORY_MAP:
                cat = KEYWORD_CATEGORY_MAP[kw]
                category_counts[cat] = category_counts.get(cat, 0) + 1
        
        if category_counts:
            return max(category_counts, key=category_counts.get)
        return None
    
    def get_interest_profile(self) -> Dict[str, float]:
        """Get user's interest profile based on visit history"""
        conn = sqlite3.connect(self.visited_db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT category, visit_count FROM visited_sites WHERE category IS NOT NULL')
        rows = cursor.fetchall()
        conn.close()
        
        category_counts = defaultdict(int)
        total_visits = 0
        
        for category, count in rows:
            category_counts[category] += count
            total_visits += count
        
        # Calculate scores normalized to 0-100
        interest_profile = {}
        if total_visits > 0:
            for category, count in category_counts.items():
                interest_profile[category] = (count / total_visits) * 100
        
        # Sort by score descending
        return dict(sorted(interest_profile.items(), key=lambda x: -x[1]))
    
    def index_page(
        self,
        url: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ):
        """Add or update a visited page in the index"""
        if not url:
            return
        
        parsed = urlparse(url)
        if not parsed.netloc:
            return
        
        # Determine category
        category = None
        if keywords:
            category = self.detect_category_from_keywords(keywords)
        
        conn = sqlite3.connect(self.visited_db_path)
        cursor = conn.cursor()
        
        try:
            # Check if URL already exists
            cursor.execute('SELECT id, visit_count FROM visited_sites WHERE url = ?', (url,))
            row = cursor.fetchone()
            
            if row:
                # Update existing record
                site_id, visit_count = row
                cursor.execute('''
                    UPDATE visited_sites
                    SET title = ?, description = ?, keywords = ?, category = ?,
                        visit_count = ?, last_visited = strftime('%s', 'now')
                    WHERE id = ?
                ''', (
                    title, description, ','.join(keywords) if keywords else None,
                    category, visit_count + 1, site_id
                ))
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO visited_sites (url, title, description, keywords, category)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    url, title, description,
                    ','.join(keywords) if keywords else None, category
                ))
            
            conn.commit()
        except Exception as e:
            print(f"[NSIndex] Error indexing page: {e}")
        finally:
            conn.close()
    
    def search(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        limit: int = 20,
        use_interest_profile: bool = True
    ) -> List[Dict[str, Any]]:
        """Search the adaptive index, with optional interest profile boosting"""
        interest_profile = self.get_interest_profile() if use_interest_profile else {}
        
        conn = sqlite3.connect(self.visited_db_path)
        cursor = conn.cursor()
        
        query_lower = query.lower()
        
        sql = '''
            SELECT url, title, description, keywords, category, visit_count, last_visited
            FROM visited_sites
            WHERE (title LIKE ? OR description LIKE ? OR keywords LIKE ?)
        '''
        params = [f'%{query_lower}%'] * 3
        
        if categories:
            placeholders = ','.join('?' for _ in categories)
            sql += f' AND category IN ({placeholders})'
            params.extend(categories)
        
        # Order by visit count, recency, and interest profile
        sql += ' ORDER BY visit_count DESC, last_visited DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = {
                "url": row[0],
                "title": row[1],
                "description": row[2],
                "keywords": row[3].split(',') if row[3] else [],
                "category": row[4],
                "visit_count": row[5],
                "last_visited": row[6],
                "_interest_boost": interest_profile.get(row[4], 0) if row[4] else 0
            }
            results.append(result)
        
        # Re-sort with interest boost considered
        if use_interest_profile:
            results.sort(key=lambda x: (-x["visit_count"], -x["_interest_boost"], -x["last_visited"]))
        
        return results

