# Supabase database

The prototype keeps its SQLite fallback, but uses Supabase Postgres when a database URL or Supabase database password is present.

## Environment

Set these only in the server environment, never in Git or the mobile bundle:

```bash
SUPABASE_SIH_DATABASE_PASS=...
SUPABASE_SIH_PROJECT_REF=jlwgmqwhqrweumngvfqa
```

The server builds the TLS connection to `db.<project-ref>.supabase.co`. Alternatively set `SUPABASE_DATABASE_URL` to the pooled connection string from Supabase Dashboard > Database > Connect. A pooler URL is preferred when the service has many workers.

`SUPABASE_SIH_PUBLISHABLE_KEY` is not a database password. It is for browser-side Supabase APIs and is not needed by the Python server's direct Postgres connection.

## Tables

Run `supabase/schema.sql` in the Supabase SQL Editor once, or let `app.py` create the tables on startup. The schema is additive and keeps the same names as the SQLite demo: `beekeeper`, `batch`, `pooled_lot`, `rating`, and `hive_reading`.

## Data path

The phone writes first to its local `beekeeper.db`. When online it sends JSON to the hosted API. The API validates the payload, computes the canonical SHA-256 batch hash, and writes to Supabase Postgres. A successful response lets the phone mark that local row as synced. The hash chain is still application-level; Supabase is the database, not a blockchain.
