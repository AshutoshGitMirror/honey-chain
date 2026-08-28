# Honey Chain — prototype

Small, honest prototype for KVIC Honey Mission. Hash linked batch history, QR check, and hive telemetry. No heavy chain node.

## Run

```bash
python3 app.py
# open http://localhost:8000
```

No pip needed. Uses stdlib `http.server` and `sqlite3`. QR is drawn in the browser with qrcode.js.

If you want server side QR images:

```bash
python3 -m venv /tmp/venv && source /tmp/venv/bin/activate
pip install -r requirements.txt
python3 app.py  # same file, will use qrcode if present
```

## What is inside

* `app.py` — one file server. Creates `honeychain.db` on first run. Serves UI and JSON api.
* `schema.sql` — tables for beekeeper, batch, rating, hive reading.
* `requirements.txt` — optional, only for server side QR.

## Flow

1. Beekeeper creates profile. Includes experience, bio, optional UPI ID, promotion opt in.
2. Beekeeper logs harvest. App hashes `prev_hash + fields` into `hash`. QR encodes that hash.
3. Consumer scans QR at `/verify/<hash>`. Page shows if hash links correctly, batch fields, and the beekeeper card. No valid hash, no sale.
4. Consumer rates the beekeeper once per verified batch. Rating updates the average.
5. Promotion tab at `/promotion` lists opted in beekeepers sorted by rating and recent harvest.

## Batch fields

`beekeeper_id`, `hive_id`, `harvest_date`, `location`, `honey_type`, `flower_source`, `horticulture_notes`, `harvest_method`, `prev_hash`, `hash`

## Hive telemetry

POST to `/api/hive` with `hive_id`, `temperature`, `humidity`, `weight`, `sound_db`. App stores it and flags:

* temp > 35 or < 15, humidity < 40 or > 85, weight drop > 10 percent week on week, sound anomaly placeholder. These are simple thresholds for now. Replace with a real model when you have data.

Productivity prediction is a naive 7 day moving average shown on the beekeeper page. Good enough to test the loop.

## Deployment sketch for a KVIC cluster

One small box per cluster. Raspberry Pi or old laptop with SQLite file per cluster. No internet needed for creation and verification inside the cluster. Sync the SQLite files to a central KVIC node weekly with `rsync`. When you outgrow this, move the hash column to a real chain and keep the same API shape.

## Notes on trust

* UPI ID is opt in and masked. The UI shows a consent line before revealing it. We never log transactions.
* Rating allows one per consumer per batch, checked by `consumer_id` you send from the app. For the prototype `consumer_id` is a device hash, not an account.
