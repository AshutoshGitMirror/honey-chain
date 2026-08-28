PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS beekeeper (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  phone TEXT,
  village TEXT,
  experience_years INTEGER DEFAULT 0,
  bio TEXT,
  upi_id TEXT,
  promotion_opt_in INTEGER DEFAULT 0,
  rating_avg REAL DEFAULT 0,
  rating_count INTEGER DEFAULT 0,
  photo_url TEXT,
  collective_name TEXT,
  latitude REAL,
  longitude REAL,
  site_people TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS batch (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beekeeper_id INTEGER NOT NULL REFERENCES beekeeper(id),
  hive_id TEXT NOT NULL,
  harvest_date TEXT NOT NULL,
  location TEXT,
  honey_type TEXT,
  flower_source TEXT,
  horticulture_notes TEXT,
  harvest_method TEXT,
  weight_kg REAL,
  prev_hash TEXT,
  hash TEXT UNIQUE NOT NULL,
  scan_secret TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rating (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  beekeeper_id INTEGER NOT NULL REFERENCES beekeeper(id),
  batch_hash TEXT NOT NULL REFERENCES batch(hash),
  scan_secret TEXT,
  consumer_id TEXT,
  stars INTEGER CHECK(stars BETWEEN 1 AND 5),
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(batch_hash, scan_secret)
);

CREATE TABLE IF NOT EXISTS hive_reading (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hive_id TEXT NOT NULL,
  beekeeper_id INTEGER REFERENCES beekeeper(id),
  temperature REAL,
  humidity REAL,
  weight REAL,
  sound_db REAL,
  recorded_at TEXT DEFAULT (datetime('now')),
  flag TEXT
);

CREATE INDEX IF NOT EXISTS idx_batch_hash ON batch(hash);
CREATE INDEX IF NOT EXISTS idx_batch_beekeeper ON batch(beekeeper_id);
CREATE INDEX IF NOT EXISTS idx_hive_hiveid ON hive_reading(hive_id);
