"""
SQLite Storage Backend
======================
Persistent storage for all index components.
Modular design for future migrations.
"""

import sqlite3
import json
import os
import time
from typing import List, Dict, Optional, Any, Set, Tuple
from ..models.page_document import PageDocument


class SQLiteStore:
    """
    SQLite-backed persistent storage for NSIndex.
    Stores documents, inverted index, link graph, and metadata.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.expanduser("~"), ".northstar", "nsindex", "index.db"
            )
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self):
        """Create all required tables."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT DEFAULT '',
                description TEXT DEFAULT '',
                domain TEXT DEFAULT '',
                text TEXT DEFAULT '',
                headings TEXT DEFAULT '[]',
                links TEXT DEFAULT '[]',
                images TEXT DEFAULT '[]',
                language TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                content_hash TEXT DEFAULT '',
                indexed_at REAL DEFAULT 0,
                fetched_at REAL DEFAULT 0,
                scraped_at REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS postings (
                token TEXT NOT NULL,
                doc_id INTEGER NOT NULL,
                frequency INTEGER DEFAULT 0,
                in_title INTEGER DEFAULT 0,
                in_heading INTEGER DEFAULT 0,
                positions TEXT DEFAULT '[]',
                PRIMARY KEY (token, doc_id),
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_postings_token ON postings(token);
            CREATE INDEX IF NOT EXISTS idx_postings_doc ON postings(doc_id);

            CREATE TABLE IF NOT EXISTS link_graph (
                from_id INTEGER NOT NULL,
                to_id INTEGER NOT NULL,
                PRIMARY KEY (from_id, to_id),
                FOREIGN KEY (from_id) REFERENCES documents(doc_id) ON DELETE CASCADE,
                FOREIGN KEY (to_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_link_from ON link_graph(from_id);
            CREATE INDEX IF NOT EXISTS idx_link_to ON link_graph(to_id);

            CREATE TABLE IF NOT EXISTS metadata_index (
                doc_id INTEGER NOT NULL,
                domain TEXT DEFAULT '',
                language TEXT DEFAULT '',
                PRIMARY KEY (doc_id),
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_meta_domain ON metadata_index(domain);
            CREATE INDEX IF NOT EXISTS idx_meta_language ON metadata_index(language);

            CREATE TABLE IF NOT EXISTS domain_authority (
                domain TEXT PRIMARY KEY,
                authority REAL DEFAULT 0.5,
                last_updated REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS crawl_frontier (
                url TEXT PRIMARY KEY,
                priority INTEGER DEFAULT 0,
                added_at REAL DEFAULT 0,
                status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS crawl_policies (
                domain TEXT PRIMARY KEY,
                delay REAL DEFAULT 1.0,
                max_depth INTEGER DEFAULT 3,
                enabled INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            );
        """)
        self._conn.commit()

    # ── Document Operations ───────────────────────────────────────────────

    def store_document(self, doc: PageDocument) -> int:
        """Store a document and return its doc_id."""
        cursor = self._conn.execute(
            """INSERT OR REPLACE INTO documents
               (url, title, description, domain, text, headings, links, images,
                language, metadata, content_hash, indexed_at, fetched_at, scraped_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc.url, doc.title, doc.description, doc.domain, doc.text,
                json.dumps(doc.headings), json.dumps(doc.links), json.dumps(doc.images),
                doc.language, json.dumps(doc.metadata), doc.content_hash,
                doc.indexed_at, doc.fetched_at, doc.scraped_at,
            )
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_document(self, doc_id: int) -> Optional[PageDocument]:
        """Retrieve a document by ID."""
        row = self._conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        if row:
            return self._row_to_document(row)
        return None

    def get_document_by_url(self, url: str) -> Optional[PageDocument]:
        """Retrieve a document by URL."""
        row = self._conn.execute(
            "SELECT * FROM documents WHERE url = ?", (url,)
        ).fetchone()
        if row:
            return self._row_to_document(row)
        return None

    def has_url(self, url: str) -> bool:
        """Check if URL exists."""
        row = self._conn.execute(
            "SELECT 1 FROM documents WHERE url = ?", (url,)
        ).fetchone()
        return row is not None

    def has_hash(self, content_hash: str) -> bool:
        """Check if content hash exists."""
        row = self._conn.execute(
            "SELECT 1 FROM documents WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row is not None

    def get_url_by_hash(self, content_hash: str) -> Optional[str]:
        """Get URL for a content hash."""
        row = self._conn.execute(
            "SELECT url FROM documents WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row[0] if row else None

    def delete_document(self, doc_id: int):
        """Delete a document and cascade to related tables."""
        self._conn.execute("DELETE FROM postings WHERE doc_id = ?", (doc_id,))
        self._conn.execute("DELETE FROM link_graph WHERE from_id = ? OR to_id = ?", (doc_id, doc_id))
        self._conn.execute("DELETE FROM metadata_index WHERE doc_id = ?", (doc_id,))
        self._conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        self._conn.commit()

    def get_document_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()
        return row[0] if row else 0

    def get_all_domains(self) -> Set[str]:
        rows = self._conn.execute("SELECT DISTINCT domain FROM documents").fetchall()
        return {r[0] for r in rows if r[0]}

    def get_all_languages(self) -> Set[str]:
        rows = self._conn.execute("SELECT DISTINCT language FROM documents WHERE language != ''").fetchall()
        return {r[0] for r in rows}

    # ── Posting Operations ────────────────────────────────────────────────

    def store_postings(self, doc_id: int, token: str, frequency: int,
                       in_title: bool, in_heading: bool, positions: List[int]):
        self._conn.execute(
            """INSERT OR REPLACE INTO postings
               (token, doc_id, frequency, in_title, in_heading, positions)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (token, doc_id, frequency, int(in_title), int(in_heading), json.dumps(positions))
        )

    def commit_postings(self):
        self._conn.commit()

    def get_postings(self, token: str) -> List[Tuple[int, int, bool, bool, List[int]]]:
        """Get all postings for a token. Returns [(doc_id, freq, in_title, in_heading, positions)]."""
        rows = self._conn.execute(
            "SELECT doc_id, frequency, in_title, in_heading, positions FROM postings WHERE token = ?",
            (token,)
        ).fetchall()
        return [(r[0], r[1], bool(r[2]), bool(r[3]), json.loads(r[4])) for r in rows]

    def get_vocabulary_size(self) -> int:
        row = self._conn.execute("SELECT COUNT(DISTINCT token) FROM postings").fetchone()
        return row[0] if row else 0

    def get_total_postings(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM postings").fetchone()
        return row[0] if row else 0

    def search_prefix(self, prefix: str, limit: int = 10) -> Set[int]:
        """Find doc_ids for tokens starting with prefix."""
        rows = self._conn.execute(
            "SELECT DISTINCT doc_id FROM postings WHERE token LIKE ? LIMIT ?",
            (f"{prefix}%", limit)
        ).fetchall()
        return {r[0] for r in rows}

    # ── Link Graph Operations ─────────────────────────────────────────────

    def store_link(self, from_id: int, to_id: int):
        self._conn.execute(
            "INSERT OR IGNORE INTO link_graph (from_id, to_id) VALUES (?, ?)",
            (from_id, to_id)
        )

    def commit_links(self):
        self._conn.commit()

    def get_outgoing(self, doc_id: int) -> Set[int]:
        rows = self._conn.execute(
            "SELECT to_id FROM link_graph WHERE from_id = ?", (doc_id,)
        ).fetchall()
        return {r[0] for r in rows}

    def get_incoming(self, doc_id: int) -> Set[int]:
        rows = self._conn.execute(
            "SELECT from_id FROM link_graph WHERE to_id = ?", (doc_id,)
        ).fetchall()
        return {r[0] for r in rows}

    def get_total_links(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM link_graph").fetchone()
        return row[0] if row else 0

    # ── Metadata Index Operations ─────────────────────────────────────────

    def store_metadata(self, doc_id: int, domain: str, language: str):
        self._conn.execute(
            "INSERT OR REPLACE INTO metadata_index (doc_id, domain, language) VALUES (?, ?, ?)",
            (doc_id, domain, language)
        )

    def get_docs_by_domain(self, domain: str) -> Set[int]:
        rows = self._conn.execute(
            "SELECT doc_id FROM metadata_index WHERE domain = ?", (domain,)
        ).fetchall()
        return {r[0] for r in rows}

    def get_docs_by_language(self, language: str) -> Set[int]:
        rows = self._conn.execute(
            "SELECT doc_id FROM metadata_index WHERE language = ?", (language,)
        ).fetchall()
        return {r[0] for r in rows}

    # ── Domain Authority Operations ───────────────────────────────────────

    def get_authority(self, domain: str) -> float:
        row = self._conn.execute(
            "SELECT authority FROM domain_authority WHERE domain = ?", (domain,)
        ).fetchone()
        return row[0] if row else 0.5

    def set_authority(self, domain: str, authority: float):
        self._conn.execute(
            "INSERT OR REPLACE INTO domain_authority (domain, authority, last_updated) VALUES (?, ?, ?)",
            (domain, authority, time.time())
        )
        self._conn.commit()

    # ── Crawl Frontier Operations ─────────────────────────────────────────

    def store_frontier_entry(self, url: str, priority: int = 0, status: str = "pending"):
        self._conn.execute(
            "INSERT OR REPLACE INTO crawl_frontier (url, priority, added_at, status) VALUES (?, ?, ?, ?)",
            (url, priority, time.time(), status)
        )

    def get_frontier_entries(self, limit: int = 100) -> List[Tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT url, priority FROM crawl_frontier WHERE status = 'pending' ORDER BY priority DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def mark_frontier_done(self, url: str):
        self._conn.execute(
            "UPDATE crawl_frontier SET status = 'done' WHERE url = ?", (url,)
        )
        self._conn.commit()

    def commit_frontier(self):
        self._conn.commit()

    # ── Crawl Policy Operations ───────────────────────────────────────────

    def get_crawl_policy(self, domain: str) -> Optional[Dict]:
        row = self._conn.execute(
            "SELECT delay, max_depth, enabled FROM crawl_policies WHERE domain = ?", (domain,)
        ).fetchone()
        if row:
            return {"delay": row[0], "max_depth": row[1], "enabled": bool(row[2])}
        return None

    def set_crawl_policy(self, domain: str, delay: float = 1.0, max_depth: int = 3, enabled: bool = True):
        self._conn.execute(
            "INSERT OR REPLACE INTO crawl_policies (domain, delay, max_depth, enabled) VALUES (?, ?, ?, ?)",
            (domain, delay, max_depth, int(enabled))
        )
        self._conn.commit()

    # ── Stats Operations ──────────────────────────────────────────────────

    def set_stat(self, key: str, value: str):
        self._conn.execute(
            "INSERT OR REPLACE INTO stats (key, value) VALUES (?, ?)",
            (key, value)
        )
        self._conn.commit()

    def get_stat(self, key: str) -> Optional[str]:
        row = self._conn.execute("SELECT value FROM stats WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    # ── Helper Methods ────────────────────────────────────────────────────

    def _row_to_document(self, row) -> PageDocument:
        """Convert a database row to PageDocument."""
        return PageDocument(
            doc_id=row[0],
            url=row[1],
            title=row[2] or "",
            description=row[3] or "",
            domain=row[4] or "",
            text=row[5] or "",
            headings=json.loads(row[6]) if row[6] else [],
            links=json.loads(row[7]) if row[7] else [],
            images=json.loads(row[8]) if row[8] else [],
            language=row[9] or "",
            metadata=json.loads(row[10]) if row[10] else {},
            content_hash=row[11] or "",
            indexed_at=row[12] or 0,
            fetched_at=row[13] or 0,
            scraped_at=row[14] or 0,
        )

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.commit()
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
