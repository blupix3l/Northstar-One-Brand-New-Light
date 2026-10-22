-- NorthStar NSIndex Starter SQLite Schema
-- Optimized for local search, adaptive indexing, and performance
-- Designed for Intel i3-7100U (4 threads, low memory footprint)

-- Pack sites table (for fast search across packs)
CREATE TABLE IF NOT EXISTS pack_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    description TEXT,
    keywords TEXT,  -- JSON array
    priority INTEGER DEFAULT 50,
    official INTEGER DEFAULT 0,  -- 0 = false, 1 = true
    related TEXT,  -- JSON array
    added_at REAL DEFAULT (strftime('%s', 'now')),
    last_used REAL DEFAULT 0
);

-- Adaptive index table (for pages the user visited)
CREATE TABLE IF NOT EXISTS adaptive_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    description TEXT,
    keywords TEXT,  -- JSON array
    category TEXT,
    visit_count INTEGER DEFAULT 1,
    last_visited REAL DEFAULT (strftime('%s', 'now')),
    added_at REAL DEFAULT (strftime('%s', 'now')),
    content_snippet TEXT  -- Small snippet for better relevance
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_pack_sites_category ON pack_sites (category);
CREATE INDEX IF NOT EXISTS idx_pack_sites_priority ON pack_sites (priority DESC);
CREATE INDEX IF NOT EXISTS idx_pack_sites_official ON pack_sites (official DESC);

CREATE INDEX IF NOT EXISTS idx_adaptive_visit_count ON adaptive_sites (visit_count DESC);
CREATE INDEX IF NOT EXISTS idx_adaptive_last_visited ON adaptive_sites (last_visited DESC);
CREATE INDEX IF NOT EXISTS idx_adaptive_category ON adaptive_sites (category);

-- Full-text search virtual tables for quick title/description/keywords search
-- (FTS5 for modern SQLite performance)
CREATE VIRTUAL TABLE IF NOT EXISTS pack_sites_fts USING fts5(
    title,
    description,
    keywords,
    content=pack_sites,
    content_rowid=id,
    tokenize='porter unicode61'  -- Porter stemming + unicode support
);

CREATE VIRTUAL TABLE IF NOT EXISTS adaptive_sites_fts USING fts5(
    title,
    description,
    keywords,
    content=adaptive_sites,
    content_rowid=id,
    tokenize='porter unicode61'
);

-- Triggers to keep FTS tables updated
CREATE TRIGGER IF NOT EXISTS pack_sites_ai AFTER INSERT ON pack_sites BEGIN
    INSERT INTO pack_sites_fts (rowid, title, description, keywords)
    VALUES (new.id, new.title, new.description, new.keywords);
END;

CREATE TRIGGER IF NOT EXISTS pack_sites_ad AFTER DELETE ON pack_sites BEGIN
    INSERT INTO pack_sites_fts (pack_sites_fts, rowid, title, description, keywords)
    VALUES ('delete', old.id, old.title, old.description, old.keywords);
END;

CREATE TRIGGER IF NOT EXISTS pack_sites_au AFTER UPDATE ON pack_sites BEGIN
    INSERT INTO pack_sites_fts (pack_sites_fts, rowid, title, description, keywords)
    VALUES ('delete', old.id, old.title, old.description, old.keywords);
    INSERT INTO pack_sites_fts (rowid, title, description, keywords)
    VALUES (new.id, new.title, new.description, new.keywords);
END;

-- Similarly for adaptive sites
CREATE TRIGGER IF NOT EXISTS adaptive_sites_ai AFTER INSERT ON adaptive_sites BEGIN
    INSERT INTO adaptive_sites_fts (rowid, title, description, keywords)
    VALUES (new.id, new.title, new.description, new.keywords);
END;

CREATE TRIGGER IF NOT EXISTS adaptive_sites_ad AFTER DELETE ON adaptive_sites BEGIN
    INSERT INTO adaptive_sites_fts (adaptive_sites_fts, rowid, title, description, keywords)
    VALUES ('delete', old.id, old.title, old.description, old.keywords);
END;

CREATE TRIGGER IF NOT EXISTS adaptive_sites_au AFTER UPDATE ON adaptive_sites BEGIN
    INSERT INTO adaptive_sites_fts (adaptive_sites_fts, rowid, title, description, keywords)
    VALUES ('delete', old.id, old.title, old.description, old.keywords);
    INSERT INTO adaptive_sites_fts (rowid, title, description, keywords)
    VALUES (new.id, new.title, new.description, new.keywords);
END;
