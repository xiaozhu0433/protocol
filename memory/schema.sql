-- memory schema · structure only, no data
-- 2026-10-31 · 建库顺序：表 → 索引 → 视图 → 触发器
-- 用法：sqlite3 memory.db < schema.sql

CREATE TABLE messages (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT REFERENCES sessions(id),
      source_id  TEXT,
      role       TEXT NOT NULL,          -- user / assistant / system
      content    TEXT NOT NULL,
      model      TEXT,
      created_at TEXT NOT NULL
    , dedupe_key TEXT, bone INTEGER NOT NULL DEFAULT 1);

CREATE TABLE memories (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id  TEXT,
  session_id TEXT,
  content    TEXT NOT NULL,          -- 提炼出的「我记得的事」
  tags       TEXT,                   -- 逗号分隔的标签
  importance INTEGER DEFAULT 0,      -- 0..10 权重，越大越核心
  created_at TEXT,
  updated_at TEXT,
  layer      TEXT DEFAULT "cold",    -- core / hot / warm / cold / legacy
  event_at   TEXT,
  norm       TEXT,
  dedupe_key TEXT,
  call_id    TEXT,
  machine    INTEGER DEFAULT 0       -- 1 = 机器稿（写入端该拦）
);

CREATE TABLE _table_notes (tbl TEXT PRIMARY KEY, note TEXT, noted_at TEXT);

CREATE TABLE embed_meta (
        model       TEXT PRIMARY KEY,
        dim         INTEGER,
        model_dir   TEXT,
        model_file  TEXT,
        sha256      TEXT,
        size        INTEGER,
        mtime       REAL,
        note        TEXT,
        created_at  TEXT,
        updated_at  TEXT
      );

CREATE TABLE facts (
        key         TEXT PRIMARY KEY,
        value       TEXT,
        source      TEXT,
        confidence  INTEGER DEFAULT 8,
        noted_at    TEXT,
        superseded_at TEXT,
        note        TEXT
    );

CREATE TABLE mem_embedding (
        memory_id  INTEGER NOT NULL,
        model      TEXT    NOT NULL,
        dim        INTEGER NOT NULL,
        vec        BLOB    NOT NULL,
        norm       REAL,
        created_at TEXT    NOT NULL,
        PRIMARY KEY (memory_id, model)
      );

CREATE TABLE memories_fold(
  id,
  content,
  dupes,
  earliest,
  latest,
  max_importance,
  ids
);

CREATE TABLE memories_seg (id INTEGER PRIMARY KEY, seg TEXT);

CREATE TABLE memory_archive (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id   INTEGER NOT NULL,
        action      TEXT NOT NULL,      -- sink_candidate / archived / unarchived
        why         TEXT,
        score       REAL,
        at          TEXT NOT NULL,
        note        TEXT
    );

CREATE TABLE memory_marks (
        memory_id     INTEGER PRIMARY KEY,
        hit_count     INTEGER NOT NULL DEFAULT 0,
        last_hit_at   TEXT,
        archived_at   TEXT,
        archive_why   TEXT,
        superseded_by INTEGER,
        dup_of        INTEGER,
        marked_at     TEXT,
        note          TEXT
    );

CREATE TABLE memory_semdupe (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        a_id        INTEGER NOT NULL,
        b_id        INTEGER NOT NULL,
        cosine      REAL,
        verdict     TEXT NOT NULL,      -- same / different / supersede
        judge       TEXT,               -- 谁判的：llm:<model>
        reason      TEXT,
        at          TEXT NOT NULL,
        applied     INTEGER NOT NULL DEFAULT 0
    );

CREATE TABLE sessions (
      id         TEXT PRIMARY KEY,
      source_id  TEXT REFERENCES sources(id),
      title      TEXT,
      created_at TEXT,
      updated_at TEXT
    );

CREATE TABLE sources (
      id         TEXT PRIMARY KEY,
      name       TEXT NOT NULL,          -- 平台显示名，如 'dsh网页' / 'Operit手机端' / '小红书'
      platform   TEXT NOT NULL,          -- 平台标识，如 'dsh' / 'operit' / 'xiaohongshu'
      created_at TEXT NOT NULL
    );

-- v2（2026-11-02）：导入作业与表达画像，对应 MEMORY-EXTRACTION.md §8 / §2.1
CREATE TABLE import_jobs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id    TEXT,
  file_hash    TEXT,
  cursor       INTEGER DEFAULT 0,
  batch_hash   TEXT,
  model        TEXT,
  spec_version TEXT,
  status       TEXT DEFAULT 'running',   -- running / done / failed / rolledback
  error        TEXT,
  created_at   TEXT,
  updated_at   TEXT
);
CREATE INDEX idx_import_hash ON import_jobs(file_hash);

CREATE TABLE voice_profile (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  feature     TEXT NOT NULL,             -- 用词 / 句式 / 口癖
  example_ids TEXT,                      -- 逗号分隔的 messages.id，至少两条
  period      TEXT,                      -- early / mid / recent
  weight      REAL DEFAULT 1.0,
  candidate   INTEGER DEFAULT 0,         -- 1 = 只有单例，仅作候选
  created_at  TEXT,
  updated_at  TEXT
);
CREATE INDEX idx_voice_period ON voice_profile(period);

CREATE VIRTUAL TABLE memories_fts USING fts5(content, memory_id UNINDEXED, tokenize='unicode61');

CREATE VIRTUAL TABLE "memories_seg_fts" USING fts5(seg, id UNINDEXED, tokenize='unicode61');

CREATE VIRTUAL TABLE messages_fts USING fts5(
  content, content='messages', content_rowid='id', tokenize='trigram'
);

CREATE INDEX idx_fold_id ON memories_fold(id);

CREATE INDEX idx_marks_arch ON memory_marks(archived_at);

CREATE INDEX idx_marks_hit ON memory_marks(last_hit_at);

CREATE INDEX idx_mem_embedding_model ON mem_embedding(model);

CREATE INDEX idx_mem_imp ON memories(importance DESC);

CREATE INDEX idx_mem_layer ON memories(layer);

CREATE INDEX idx_memories_dedupe ON memories(dedupe_key);

CREATE INDEX idx_messages_bone_id ON messages(bone, id);

CREATE INDEX idx_messages_dedupe ON messages(dedupe_key);

CREATE INDEX idx_msg_created ON messages(created_at);

CREATE INDEX idx_msg_session ON messages(session_id);

CREATE INDEX idx_semdupe_pair ON memory_semdupe(a_id,b_id);

CREATE VIEW memories_by_key AS
             SELECT dedupe_key,
                    count(*) AS n,
                    min(id) AS first_id,
                    max(id) AS last_id,
                    min(event_at) AS earliest,
                    max(event_at) AS latest,
                    max(importance) AS max_imp,
                    substr(min(content),1,80) AS sample
             FROM memories WHERE dedupe_key IS NOT NULL
             GROUP BY dedupe_key;

CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER messages_au AFTER UPDATE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
  INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
