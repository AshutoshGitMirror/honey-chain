#!/usr/bin/env python3
"""
Honey Chain — minimal prototype, stdlib only.
Run: python3 app.py
Open: http://localhost:8000
"""
import hashlib
import html
import json
import sqlite3
import os
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "honeychain.db")
SCHEMA = os.path.join(BASE_DIR, "schema.sql")
POSTGRES_SCHEMA = os.path.join(BASE_DIR, "supabase", "schema.sql")

def postgres_dsn():
    explicit = os.environ.get("SUPABASE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    password = os.environ.get("SUPABASE_SIH_DATABASE_PASS")
    project_ref = os.environ.get("SUPABASE_SIH_PROJECT_REF")
    if password and project_ref:
        encoded = urllib.parse.quote(password, safe="")
        # Prefer Supabase pooler (IPv4) for hosts like Render free tier where direct db.* IPv6 is unreachable.
        # Pooler host region defaults to ap-south-1 for India; override via SUPABASE_POOLER_HOST if needed.
        pooler_host = os.environ.get("SUPABASE_POOLER_HOST") or "aws-0-ap-south-1.pooler.supabase.com"
        pooler_port = os.environ.get("SUPABASE_POOLER_PORT") or "6543"
        # Use transaction pooler with user postgres.<project_ref>
        pooler_dsn = f"postgresql://postgres.{project_ref}:{encoded}@{pooler_host}:{pooler_port}/postgres?sslmode=require"
        # Also keep direct DSN as fallback; caller will try pooler first.
        return pooler_dsn
    return None

def postgres_dsn_candidates():
    candidates = []
    explicit = os.environ.get("SUPABASE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if explicit:
        candidates.append(explicit)
        return candidates
    password = os.environ.get("SUPABASE_SIH_DATABASE_PASS")
    project_ref = os.environ.get("SUPABASE_SIH_PROJECT_REF")
    if password and project_ref:
        encoded = urllib.parse.quote(password, safe="")
        pooler_host = os.environ.get("SUPABASE_POOLER_HOST") or "aws-0-ap-south-1.pooler.supabase.com"
        pooler_port = os.environ.get("SUPABASE_POOLER_PORT") or "6543"
        candidates.append(f"postgresql://postgres.{project_ref}:{encoded}@{pooler_host}:{pooler_port}/postgres?sslmode=require")
        # direct as fallback
        candidates.append(f"postgresql://postgres:{encoded}@db.{project_ref}.supabase.co:5432/postgres?sslmode=require")
    return candidates

class PostgresConnection:
    is_postgres = True

    def __init__(self, dsn):
        if psycopg is None:
            raise RuntimeError("Postgres is configured but psycopg is not installed")
        self.connection = psycopg.connect(dsn, row_factory=dict_row)

    def execute(self, sql, params=()):
        return self.connection.execute(sql.replace("?", "%s"), params)

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

def db():
    for dsn in postgres_dsn_candidates():
        try:
            return PostgresConnection(dsn)
        except Exception as e:
            # Log and try next candidate; if all fail, fallback to SQLite instead of crashing deploy
            try:
                print(f"[db] postgres connect failed for {dsn.split('@')[-1][:40]}: {e}")
            except:
                pass
            continue
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def column_exists(con, table, col):
    if getattr(con, "is_postgres", False):
        return con.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=? AND column_name=?",
            (table, col),
        ).fetchone() is not None
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)

def init_db():
    if getattr(db, "_initialized", False):
        return
    need_seed = not os.path.exists(DB)
    con = db()
    if getattr(con, "is_postgres", False):
        try:
            with open(POSTGRES_SCHEMA) as f:
                for statement in f.read().split(";"):
                    statement = statement.strip()
                    if statement:
                        con.execute(statement)
            con.commit()
        except Exception as e:
            print(f"[init_db] postgres schema init failed: {e}")
            con.close()
            # Fallback to SQLite init
            con = sqlite3.connect(DB)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys=ON")
            with open(SCHEMA) as f:
                con.executescript(f.read())
    elif need_seed:
        with open(SCHEMA) as f:
            con.executescript(f.read())
    else:
        # migrate existing SQLite DB and ensure base tables exist
        with open(SCHEMA) as f:
            con.executescript(f.read())
        for col, typ in [("photo_url","TEXT"),("collective_name","TEXT"),("latitude","REAL"),("longitude","REAL"),("site_people","TEXT")]:
            if not column_exists(con, "beekeeper", col):
                con.execute(f"ALTER TABLE beekeeper ADD COLUMN {col} {typ}")
        for col, typ in [("scan_secret","TEXT"),("packer_name","TEXT"),("ca_number","TEXT"),("packing_date","TEXT"),("best_before","TEXT"),("lot_number","TEXT"),("mrp","REAL"),("net_weight","REAL")]:
            if not column_exists(con, "batch", col):
                con.execute(f"ALTER TABLE batch ADD COLUMN {col} {typ}")
        if not column_exists(con, "rating", "scan_secret"):
            try:
                con.execute("ALTER TABLE rating ADD COLUMN scan_secret TEXT")
            except sqlite3.OperationalError:
                pass
        # fix pooled rating FK: rating.batch_hash originally REFERENCES batch(hash) blocks pooled lots. Remove FK per vision DAG.
        try:
            fk = list(con.execute("PRAGMA foreign_key_list(rating)").fetchall())
            has_batch_fk = any(r["table"] == "batch" for r in fk)
            if has_batch_fk:
                con.execute("ALTER TABLE rating RENAME TO rating_old")
                con.execute("CREATE TABLE rating (id INTEGER PRIMARY KEY AUTOINCREMENT, beekeeper_id INTEGER NOT NULL REFERENCES beekeeper(id), batch_hash TEXT NOT NULL, scan_secret TEXT, consumer_id TEXT, stars INTEGER CHECK(stars BETWEEN 1 AND 5), created_at TEXT DEFAULT (datetime('now')), UNIQUE(batch_hash, scan_secret))")
                con.execute("INSERT INTO rating (id, beekeeper_id, batch_hash, scan_secret, consumer_id, stars, created_at) SELECT id, beekeeper_id, batch_hash, scan_secret, consumer_id, stars, created_at FROM rating_old")
                con.execute("DROP TABLE rating_old")
        except Exception:
            pass
        con.commit()
    # seed if empty
    cnt = con.execute("SELECT COUNT(*) as c FROM beekeeper").fetchone()["c"]
    if cnt == 0:
        con.execute("INSERT INTO beekeeper (name, village, experience_years, bio, upi_id, promotion_opt_in, photo_url, collective_name, latitude, longitude, site_people) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    ("Ramesh Yadav", "Nashik MH", 8, "8 years, mustard and ber honey. 12 boxes. KVIC 2019 batch.", "ramesh@ybl", 1, "https://cdn.pixabay.com/photo/2016/03/26/13/27/beekeeper-1280389_640.jpg", "Nashik Madhu Collective", 20.011, 73.790, '["Ramesh Yadav - lead","Amit Pawar - helper","KVIC trainer Sunil"]'))
        con.execute("INSERT INTO beekeeper (name, village, experience_years, bio, promotion_opt_in, collective_name, latitude, longitude, site_people) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("Sunita Devi", "Muzaffarpur BR", 5, "Litchi honey specialist. KVIC trained 2021.", 1, "Muzaffarpur Litchi Group", 26.122, 85.390, '["Sunita Devi - lead","Rajesh Kumar - harvest","Anjali - packaging"]'))
        con.execute("INSERT INTO beekeeper (name, village, experience_years, bio, collective_name, latitude, longitude) VALUES (?,?,?,?,?,?,?)",
                    ("Kareem Ali", "Nashik MH", 6, "Ber honey, 8 boxes near orchard.", "Nashik Madhu Collective", 20.015, 73.795))
        con.commit()
    con.close()
    db._initialized = True

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def batch_hash(prev, beekeeper_id, hive_id, harvest_date, flower_source, honey_type, location):
    raw = f"{prev or ''}|{beekeeper_id}|{hive_id}|{harvest_date}|{flower_source}|{honey_type}|{location}"
    return sha256(raw)

def pooled_hash(prev_hashes, plant_name, plant_date):
    # prev_hashes is list of strings, sort for determinism
    joined = "|".join(sorted(prev_hashes))
    raw = f"{joined}|{plant_name}|{plant_date}"
    return sha256(raw)

def verify_chain(target_hash):
    con = db()
    rows = con.execute("SELECT * FROM batch ORDER BY id").fetchall()
    con.close()
    m = {r["hash"]: dict(r) for r in rows}
    if target_hash not in m:
        return {"found": False, "valid": False, "reason": "hash not found"}
    valid = True
    chain = []
    h = target_hash
    visited = set()
    while h:
        if h in visited:
            valid = False
            break
        visited.add(h)
        r = m.get(h)
        if not r:
            break
        chain.append(r)
        prev = r["prev_hash"]
        if prev:
            if prev not in m:
                valid = False
                chain.append({"hash": prev, "missing": True})
                break
            h = prev
        else:
            break
    return {"found": True, "valid": valid, "chain": list(reversed(chain))}

def hive_flag(temp, hum, weight, sound):
    flags = []
    if temp is not None:
        if temp > 35: flags.append("high temp")
        if temp < 15: flags.append("low temp")
    if hum is not None:
        if hum < 40: flags.append("low humidity")
        if hum > 85: flags.append("high humidity")
    if sound is not None and sound > 85:
        flags.append("sound anomaly")
    return ", ".join(flags) if flags else "ok"

HTML_HEAD = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Honey Chain</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
*{box-sizing:border-box}body{font-family:system-ui,Arial,sans-serif;max-width:1000px;margin:0 auto;padding:20px;line-height:1.5;color:#222}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
nav a{margin-right:12px;text-decoration:none;color:#8a5a00}
.card{border:1px solid #ddd;border-radius:12px;padding:16px;margin:12px 0}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;background:#fff2cc;font-size:12px}
.ok{color:#0a7a00}.bad{color:#b00020}
input,select,textarea{padding:8px;border:1px solid #ccc;border-radius:8px;width:100%;margin:4px 0 8px}
button{padding:8px 14px;border:0;border-radius:8px;background:#f5b301;cursor:pointer}
button.secondary{background:#eee}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
small{color:#666}
pre{white-space:pre-wrap;word-break:break-all;background:#fafafa;padding:10px;border-radius:8px}
#map{height:280px;border-radius:12px;margin-top:10px}
.photo{width:100%;height:180px;object-fit:cover;border-radius:12px;background:#f5f5f5}
.avatar{width:72px;height:72px;border-radius:50%;object-fit:cover}
</style>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head><body>
<header><div><h1 style="margin:0">Honey Chain</h1><small>KVIC prototype — hash chain + QR + hive check + map</small></div>
<nav><a href="/">Home</a> <a href="/promotion">Promotion</a> <a href="/beekeeper">Beekeepers</a> <a href="/collectives">Collectives</a> <a href="/pooled">Pooled lots</a></nav></header><hr>
"""

HTML_FOOT = "<hr><small>Prototype. SQLite + hash chain + OSM. Replace hash with real chain when KVIC needs it.</small></body></html>"

def render_home():
    con = db()
    batches = con.execute("SELECT b.*, k.name as beekeeper_name, k.village, k.collective_name FROM batch b JOIN beekeeper k ON k.id=b.beekeeper_id ORDER BY b.id DESC LIMIT 20").fetchall()
    beekeepers = con.execute("SELECT * FROM beekeeper ORDER BY id").fetchall()
    con.close()
    opts = "".join(f'<option value="{r["id"]}">{r["name"]} — {r["village"]}{" — "+r["collective_name"] if r["collective_name"] else ""}</option>' for r in beekeepers)
    batch_rows = ""
    for r in batches:
        batch_rows += f'<div class="card"><div><strong>{r["honey_type"] or "Honey"} — {r["flower_source"] or "-"}</strong> <span class="badge">{r["hash"][:10]}...</span></div><div>Beekeeper: {r["beekeeper_name"]} | Hive: {r["hive_id"]} | {r["harvest_date"]}</div><div><small>{r["location"] or ""} — {r["collective_name"] or ""} — {r["horticulture_notes"] or ""}</small></div><div style="margin-top:8px"><a href="/verify/{r["hash"]}">Verify and see QR</a> | <a href="/beekeeper/{r["beekeeper_id"]}">Know your beekeeper</a></div></div>'
    if not batch_rows:
        batch_rows = "<p>No batches yet. Add one below.</p>"
    return HTML_HEAD + f"""
<h2>Add harvest batch</h2>
<div class="card">
<form method="POST" action="/api/batch">
<div class="grid">
<div><label>Beekeeper<select name="beekeeper_id" required>{opts}</select></label></div>
<div><label>Hive ID<input name="hive_id" required value="HIVE-01"></label></div>
<div><label>Harvest date<input type="date" name="harvest_date" required value="{datetime.now().date()}"></label></div>
<div><label>Location<input name="location" placeholder="village, district"></label></div>
<div><label>Honey type<input name="honey_type" placeholder="raw, filtered"></label></div>
<div><label>Flower source<input name="flower_source" placeholder="mustard, litchi, ber"></label></div>
<div><label>Weight kg<input type="number" step="0.1" name="weight_kg"></label></div>
<div><label>Harvest method<input name="harvest_method" placeholder="manual, extractor"></label></div>
</div>
<label>Horticulture notes<textarea name="horticulture_notes" placeholder="surrounding crop, season, hive health notes"></textarea></label>
<button type="submit">Create batch and generate hash</button>
</form>
</div>
<h2>Recent batches</h2>
{batch_rows}
<h2>Hive telemetry — quick log</h2>
<div class="card">
<form method="POST" action="/api/hive">
<div class="grid">
<div><label>Hive ID<input name="hive_id" value="HIVE-01" required></label></div>
<div><label>Beekeeper<select name="beekeeper_id">{opts}</select></label></div>
<div><label>Temperature C<input type="number" step="0.1" name="temperature"></label></div>
<div><label>Humidity %<input type="number" step="0.1" name="humidity"></label></div>
<div><label>Weight kg<input type="number" step="0.1" name="weight"></label></div>
<div><label>Sound dB<input type="number" step="0.1" name="sound_db"></label></div>
</div>
<button type="submit">Log reading</button>
</form>
<small>Flags: temp &gt;35 or &lt;15, humidity &lt;40 or &gt;85, sound &gt;85. Weight drop check uses last reading.</small>
</div>
""" + HTML_FOOT

def render_verify(hash_val, scan_token=None):
    res = verify_chain(hash_val)
    con = db()
    batch = con.execute("SELECT b.*, k.name, k.village, k.experience_years, k.bio, k.upi_id, k.rating_avg, k.rating_count, k.photo_url, k.collective_name, k.latitude, k.longitude, k.site_people FROM batch b JOIN beekeeper k ON k.id=b.beekeeper_id WHERE b.hash=?", (hash_val,)).fetchone()
    con.close()
    if not res["found"] or not batch:
        return HTML_HEAD + f'<div class="card bad"><h2>Not found</h2><p>No batch with that hash.</p><pre>{hash_val}</pre></div>' + HTML_FOOT
    status = '<span class="ok">Chain intact</span>' if res["valid"] else '<span class="bad">Chain broken</span>'
    chain_pre = json.dumps([{"hash": c.get("hash"), "prev": c.get("prev_hash"), "hive": c.get("hive_id"), "date": c.get("harvest_date")} for c in res["chain"]], indent=2)
    # rating via scan token to prevent gaming
    # batch scan_secret is stored, QR contains ?s=token, rating needs that token, one rating per batch per token
    batch_secret = batch["scan_secret"]
    has_valid_token = scan_token and batch_secret and scan_token == batch_secret
    # if batch has no secret (old data), allow legacy
    if not batch_secret:
        has_valid_token = True
        token_note = "<small>Legacy batch without scan token, rating allowed.</small>"
    elif has_valid_token:
        token_note = "<small>Valid scan, you can rate once. Token is single use per batch.</small>"
    else:
        token_note = "<small>Scan the QR on the bottle to get a valid link with token. Rating needs the scan token to prevent bots. Add ?s=token to the URL.</small>"
    if has_valid_token:
        rating_form = f'''
<form method="POST" action="/api/rate">
<input type="hidden" name="batch_hash" value="{hash_val}">
<input type="hidden" name="beekeeper_id" value="{batch["beekeeper_id"]}">
<input type="hidden" name="scan_secret" value="{scan_token or ''}">
<label>Stars<select name="stars"><option>5</option><option>4</option><option>3</option><option>2</option><option>1</option></select></label>
<button type="submit">Submit rating</button>
</form>
'''
    else:
        rating_form = "<p><em>Rating locked. Scan the QR with token.</em></p>"
    rating_block = f'''
<div class="card">
<h3>Rate this beekeeper</h3>
{rating_form}
{token_note}
</div>
'''
    upi = batch["upi_id"]
    upi_block = ""
    if upi:
        masked = upi[:2] + "***" + upi[-4:] if len(upi) > 6 else "***"
        upi_block = f'''
<div class="card">
<h3>Support the beekeeper</h3>
<p>UPI: <span id="upi_mask">{masked}</span> <button class="secondary" onclick="document.getElementById('upi_full').style.display='block'; this.style.display='none'">Show with consent</button></p>
<div id="upi_full" style="display:none"><p>Full UPI: <strong>{upi}</strong></p>
<a href="upi://pay?pa={urllib.parse.quote(upi)}&pn={urllib.parse.quote(batch['name'])}&cu=INR"><button>Pay via UPI app</button></a></div>
</div>
'''
    # map for verify if coords exist - household pin everywhere, with google embed as requested
    map_block = ""
    if batch["latitude"] and batch["longitude"]:
        map_block = f'''
<div class="card">
<h3>Location — {batch["collective_name"] or batch["village"]}</h3>
<p><small>Household farm — home address for visit. Same pin for customer and KVIC.</small></p>
<div id="map"></div>
<script>var m=L.map('map').setView([{batch["latitude"]},{batch["longitude"]}],13); L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19, attribution:'OSM'}}).addTo(m); L.marker([{batch["latitude"]},{batch["longitude"]}]).addTo(m).bindPopup("{batch["name"]} — household");</script>
<iframe width="100%" height="280" style="border:0; border-radius:12px; margin-top:10px" loading="lazy" src="https://www.google.com/maps?q={batch["latitude"]},{batch["longitude"]}&z=15&output=embed"></iframe>
<small>{batch["latitude"]}, {batch["longitude"]} — household farm</small>
</div>
'''
    # Packer / AGMARK per vision: packer writes after lab
    if batch["ca_number"] or batch["packer_name"] or batch["lot_number"]:
        packer_block = f'<div class="card"><h3>Packing & Cert — AGMARK</h3><p>CA: {batch["ca_number"] or "-"} | Packer: {batch["packer_name"] or "-"} | Lot: {batch["lot_number"] or "-"} | Packing: {batch["packing_date"] or "-"} | Best before: {batch["best_before"] or "-"} | MRP: {batch["mrp"] or "-"} | Net: {batch["net_weight"] or "-"} kg</p><p><span class="ok">Certified</span> — AGMARK</p></div>'
    else:
        packer_block = '<div class="card"><h3>Packing & Cert</h3><p><small>Not yet packed — label written after NABL lab per AGMARK 2008/2024.</small></p></div>' 
    photo = batch["photo_url"]
    photo_tag = f'<img class="avatar" src="{html.escape(photo, quote=True)}" onerror="this.style.display=\'none\'">' if photo else ""
    collective = batch["collective_name"] or "-"
    qr_token = batch["scan_secret"]
    qr_js = f"new QRCode(document.getElementById('qrcode'), {{text: window.location.origin + '/verify/{hash_val}?s={qr_token}', width: 160, height: 160}});" if qr_token else "new QRCode(document.getElementById('qrcode'), {text: window.location.href, width: 160, height: 160});"
    return HTML_HEAD + f"""
<h2>Verify</h2>
<div class="card">
<div>Hash: <pre>{hash_val}</pre></div>
<div>Status: {status}</div>
<div>Scan token: <small>{qr_token or 'legacy - no token'}</small></div>
<div id="qrcode" style="margin-top:12px"></div>
<script>{qr_js}</script>
</div>
<div class="card">
<h3>Batch</h3>
<p><strong>{batch["honey_type"] or "Honey"}</strong> from <strong>{batch["flower_source"] or "-"}</strong></p>
<p>Hive {batch["hive_id"]} | {batch["harvest_date"]} | {batch["location"] or ""}</p>
<p>Horticulture: {batch["horticulture_notes"] or "-"}</p>
<p>Method: {batch["harvest_method"] or "-"} | Weight: {batch["weight_kg"] or "-"} kg</p>
<p>Prev hash: <small>{batch["prev_hash"] or "genesis"}</small></p>
</div>
{packer_block}
<div class="card">
<h3>Know your beekeeper {photo_tag}</h3>
<p><strong>{batch["name"]}</strong> — {batch["village"]} <span class="badge">{collective}</span></p>
<p>Experience: {batch["experience_years"]} years</p>
<p>{batch["bio"] or ""}</p>
<p>Rating: {batch["rating_avg"]:.1f} ({batch["rating_count"]} votes)</p>
<p><a href="/beekeeper/{batch["beekeeper_id"]}">Full profile</a> | <a href="/collective/{urllib.parse.quote(collective)}">View collective</a></p>
</div>
{map_block}
{upi_block}
{rating_block}
<details><summary>Chain data</summary><pre>{chain_pre}</pre></details>
""" + HTML_FOOT

def render_beekeeper_list():
    con = db()
    rows = con.execute("SELECT * FROM beekeeper ORDER BY rating_avg DESC, id").fetchall()
    con.close()
    cards = ""
    for r in rows:
        promo = " <span class=badge>promoted</span>" if r["promotion_opt_in"] else ""
        collective = f'<span class="badge">{r["collective_name"]}</span>' if r["collective_name"] else ""
        photo = f'<img class="avatar" src="{html.escape(r["photo_url"], quote=True)}" onerror="this.style.display=\'none\'">' if r["photo_url"] else ""
        cards += f'<div class="card" style="display:flex;gap:12px;align-items:center"><div>{photo}</div><div><h3 style="margin:0">{r["name"]}{promo} {collective}</h3><div>{r["village"]} — {r["experience_years"]} yrs</div><p>{r["bio"] or ""}</p><div>Rating {r["rating_avg"]:.1f} ({r["rating_count"]})</div><div><a href="/beekeeper/{r["id"]}">Profile</a> {"<a href=\"/collective/"+urllib.parse.quote(r["collective_name"])+"\" style=\"margin-left:8px\">Collective</a>" if r["collective_name"] else ""}</div></div></div>'
    return HTML_HEAD + f"""
<h2>Beekeepers</h2>
<div class="card">
<h3>Add beekeeper</h3>
<form method="POST" action="/api/beekeeper">
<div class="grid">
<div><label>Name<input name="name" required></label></div>
<div><label>Village<input name="village"></label></div>
<div><label>Phone<input name="phone"></label></div>
<div><label>Experience years<input type="number" name="experience_years"></label></div>
<div><label>UPI ID<input name="upi_id" placeholder="name@upi"></label></div>
<div><label>Promote? <select name="promotion_opt_in"><option value="1">yes</option><option value="0" selected>no</option></select></label></div>
<div><label>Collective name<input name="collective_name" placeholder="Nashik Madhu Collective"></label></div>
<div><label>Photo URL<input name="photo_url" placeholder="https://..."></label></div>
<div><label>Latitude<input type="number" step="0.0001" name="latitude" placeholder="20.011"></label></div>
<div><label>Longitude<input type="number" step="0.0001" name="longitude" placeholder="73.79"></label></div>
</div>
<label>Site people — who is involved (comma separated, e.g. Ramesh - lead, Amit - helper)<textarea name="site_people" placeholder="names and roles"></textarea></label>
<label>Bio<textarea name="bio" placeholder="crops, hive count, training"></textarea></label>
<button type="submit">Add beekeeper</button>
</form>
</div>
{cards}
""" + HTML_FOOT

def render_beekeeper_one(bid):
    con = db()
    r = con.execute("SELECT * FROM beekeeper WHERE id=?", (bid,)).fetchone()
    if not r:
        con.close()
        return HTML_HEAD + "<p>Beekeeper not found</p>" + HTML_FOOT
    batches = con.execute("SELECT * FROM batch WHERE beekeeper_id=? ORDER BY id DESC", (bid,)).fetchall()
    readings = con.execute("SELECT * FROM hive_reading WHERE beekeeper_id=? ORDER BY id DESC LIMIT 10", (bid,)).fetchall()
    collective_members = []
    if r["collective_name"]:
        collective_members = con.execute("SELECT * FROM beekeeper WHERE collective_name=?", (r["collective_name"],)).fetchall()
    con.close()
    promo = " <span class=badge>promoted</span>" if r["promotion_opt_in"] else ""
    batch_list = "".join(f'<div><a href="/verify/{b["hash"]}">{b["harvest_date"]} — {b["flower_source"] or "honey"} — {b["hive_id"]}</a> <small>{b["hash"][:10]}...</small></div>' for b in batches) or "<p>No harvests yet</p>"
    reading_list = "".join(f'<div>{x["recorded_at"]}: temp {x["temperature"]}C hum {x["humidity"]}% weight {x["weight"]}kg — {x["flag"]}</div>' for x in readings) or "<p>No readings</p>"
    upi = r["upi_id"]
    upi_line = f'<p>UPI: {upi[:2]}***{upi[-4:]} <small>consent needed</small></p>' if upi else "<p>No UPI shared</p>"
    photo_block = f'<img class="photo" src="{html.escape(r["photo_url"], quote=True)}" onerror="this.style.display=\'none\'">' if r["photo_url"] else "<div class='photo' style='display:flex;align-items:center;justify-content:center;color:#999'>no photo</div>"
    # site people parse
    site_people_raw = r["site_people"] or ""
    try:
        people = json.loads(site_people_raw) if site_people_raw.strip().startswith("[") else [p.strip() for p in site_people_raw.split(",") if p.strip()]
    except:
        people = [site_people_raw]
    people_html = "".join(f"<li>{p}</li>" for p in people) if people and people[0] else "<li>no detail added</li>"
    # collective list
    collective_html = ""
    if collective_members and len(collective_members) > 1:
        collective_html = "<ul>" + "".join(f'<li><a href="/beekeeper/{m["id"]}">{m["name"]}</a> — {m["village"]} ({m["experience_years"]} yrs) {"<span class=badge>lead</span>" if m["id"]==r["id"] else ""}</li>' for m in collective_members) + "</ul>"
    else:
        collective_html = "<p>Only this beekeeper in collective. Add others with same collective name.</p>"
    # map - household pin everywhere
    map_html = ""
    if r["latitude"] and r["longitude"]:
        map_html = f'<div id="map"></div><script>var m=L.map("map").setView([{r["latitude"]},{r["longitude"]}],13); L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",{{maxZoom:19, attribution:"OSM"}}).addTo(m); L.marker([{r["latitude"]},{r["longitude"]}]).addTo(m).bindPopup("{r["name"]} — household farm");</script><iframe width="100%" height="280" style="border:0; border-radius:12px; margin-top:10px" loading="lazy" src="https://www.google.com/maps?q={r["latitude"]},{r["longitude"]}&z=15&output=embed"></iframe><small>{r["latitude"]}, {r["longitude"]} — household farm, same for customer and KVIC</small>'
    else:
        map_html = "<p>No location set. Add latitude and longitude.</p>"
    # collective name badge
    collective_badge = f'<span class="badge">{r["collective_name"]}</span>' if r["collective_name"] else ""
    return HTML_HEAD + f"""
<div class="grid">
<div>
<div class="card">
{photo_block}
<h2 style="margin:8px 0 0">{r["name"]}{promo} {collective_badge}</h2>
<div>{r["village"]} — {r["experience_years"]} years</div>
<p>{r["bio"] or ""}</p>
<p>Rating {r["rating_avg"]:.1f} ({r["rating_count"]} votes)</p>
{upi_line}
</div>
<div class="card">
<h3>Site — {r["collective_name"] or "no collective"}</h3>
<p>All people at this beekeeping site:</p>
<ul>{people_html}</ul>
<h4>Collective members ({len(collective_members)})</h4>
{collective_html}
<p><a href="/collective/{urllib.parse.quote(r["collective_name"] or "")}">Open collective page</a></p>
</div>
</div>
<div>
<div class="card">
<h3>Location</h3>
{map_html}
</div>
<div class="card">
<h3>Update profile</h3>
<form method="POST" action="/api/beekeeper/{r["id"]}/update">
<div class="grid">
<div><label>Photo URL<input name="photo_url" value="{r["photo_url"] or ""}"></label></div>
<div><label>Collective name<input name="collective_name" value="{r["collective_name"] or ""}"></label></div>
<div><label>Latitude<input type="number" step="0.0001" name="latitude" value="{r["latitude"] or ""}"></label></div>
<div><label>Longitude<input type="number" step="0.0001" name="longitude" value="{r["longitude"] or ""}"></label></div>
</div>
<label>Site people<textarea name="site_people">{r["site_people"] or ""}</textarea></label>
<label>Promotion<select name="promotion_opt_in"><option value="1" {"selected" if r["promotion_opt_in"] else ""}>yes</option><option value="0" {"selected" if not r["promotion_opt_in"] else ""}>no</option></select></label>
<button type="submit">Save</button>
</form>
</div>
</div>
</div>
<div class="card"><h3>Batches</h3>{batch_list}</div>
<div class="card"><h3>Recent hive readings</h3>{reading_list}</div>
""" + HTML_FOOT

def render_promotion():
    con = db()
    rows = con.execute("""
      SELECT k.*, (SELECT MAX(b.harvest_date) FROM batch b WHERE b.beekeeper_id=k.id) as last_harvest
      FROM beekeeper k WHERE promotion_opt_in=1
      ORDER BY rating_avg DESC, last_harvest DESC
    """).fetchall()
    con.close()
    if not rows:
        body = "<p>No promoted beekeepers yet.</p>"
    else:
        body = ""
        for r in rows:
            photo = f'<img class="avatar" src="{html.escape(r["photo_url"], quote=True)}" onerror="this.style.display=\'none\'">' if r["photo_url"] else ""
            collective = f' <span class="badge">{r["collective_name"]}</span>' if r["collective_name"] else ""
            body += f'<div class="card" style="display:flex;gap:12px"><div>{photo}</div><div><h3 style="margin:0">{r["name"]}{collective} <span class="badge">{r["rating_avg"]:.1f} stars</span></h3><div>{r["village"]} — {r["experience_years"]} yrs</div><p>{r["bio"] or ""}</p><div>Last harvest: {r["last_harvest"] or "-"}</div><div><a href="/beekeeper/{r["id"]}">View and support</a> | <a href="/collective/{urllib.parse.quote(r["collective_name"] or "")}">Collective</a></div></div></div>'
    return HTML_HEAD + f"<h2>Promotion tab</h2><p>Beekeepers who opted in, sorted by rating and recent harvest. Shows photo and collective.</p>{body}" + HTML_FOOT

def render_collectives():
    con = db()
    rows = con.execute("SELECT collective_name, COUNT(*) as c FROM beekeeper WHERE collective_name IS NOT NULL AND collective_name!='' GROUP BY collective_name").fetchall()
    if not rows:
        con.close()
        return HTML_HEAD + "<h2>Collectives</h2><p>No collectives yet. Add a beekeeper with a collective name.</p>" + HTML_FOOT
    body = ""
    for r in rows:
        members = con.execute("SELECT * FROM beekeeper WHERE collective_name=?", (r["collective_name"],)).fetchall()
        # get center coords
        lats = [m["latitude"] for m in members if m["latitude"]]
        lngs = [m["longitude"] for m in members if m["longitude"]]
        loc = f"{sum(lats)/len(lats):.3f}, {sum(lngs)/len(lngs):.3f}" if lats else "no coords"
        body += f'<div class="card"><h3 style="margin:0">{r["collective_name"]} <span class="badge">{r["c"]} members</span></h3><div>Location: {loc}</div><ul>' + "".join(f'<li><a href="/beekeeper/{m["id"]}">{m["name"]}</a> — {m["village"]} — {m["experience_years"]} yrs</li>' for m in members) + f'</ul><a href="/collective/{urllib.parse.quote(r["collective_name"])}">Open site page</a></div>'
    con.close()
    return HTML_HEAD + f"<h2>Collectives</h2><p>Groups of beekeepers at the same site.</p>{body}" + HTML_FOOT

def render_collective_one(name):
    con = db()
    name = urllib.parse.unquote(name)
    members = con.execute("SELECT * FROM beekeeper WHERE collective_name=? ORDER BY experience_years DESC", (name,)).fetchall()
    if not members:
        con.close()
        return HTML_HEAD + f"<p>Collective not found: {name}</p>" + HTML_FOOT
    # site people union
    all_people = []
    for m in members:
        sp = m["site_people"] or ""
        try:
            lst = json.loads(sp) if sp.strip().startswith("[") else [p.strip() for p in sp.split(",") if p.strip()]
        except:
            lst = [sp]
        all_people.extend(lst)
    all_people = list(dict.fromkeys([p for p in all_people if p]))
    # map with multiple markers
    markers_js = "\n".join(f'L.marker([{m["latitude"]},{m["longitude"]}]).addTo(m).bindPopup("{m["name"]}");' for m in members if m["latitude"] and m["longitude"])
    # center - household pin everywhere
    lats = [m["latitude"] for m in members if m["latitude"]]
    lngs = [m["longitude"] for m in members if m["longitude"]]
    if lats:
        center = f"[{sum(lats)/len(lats)},{sum(lngs)/len(lngs)}]"
        glat = sum(lats)/len(lats); glon = sum(lngs)/len(lngs)
        map_html = f'<div id="map"></div><script>var m=L.map("map").setView({center},12); L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",{{maxZoom:19, attribution:"OSM"}}).addTo(m); {markers_js}</script><iframe width="100%" height="280" style="border:0; border-radius:12px; margin-top:10px" loading="lazy" src="https://www.google.com/maps?q={glat},{glon}&z=13&output=embed"></iframe><small>Household farms — same pins for customer and KVIC</small>'
    else:
        map_html = "<p>No coords for this collective.</p>"
    batches = con.execute("SELECT b.*, k.name FROM batch b JOIN beekeeper k ON k.id=b.beekeeper_id WHERE k.collective_name=? ORDER BY b.id DESC LIMIT 20", (name,)).fetchall()
    con.close()
    batch_html = "".join(f'<div><a href="/verify/{b["hash"]}">{b["harvest_date"]} — {b["flower_source"] or "honey"} — {b["name"]} — {b["hive_id"]}</a></div>' for b in batches) or "<p>No batches for this site yet.</p>"
    people_html = "".join(f"<li>{p}</li>" for p in all_people) or "<li>no detail</li>"
    member_html = "".join(f'<div class="card" style="display:flex;gap:12px"><img class="avatar" src="{html.escape(m["photo_url"] or "", quote=True)}" onerror="this.style.display=\'none\'"><div><strong><a href="/beekeeper/{m["id"]}">{m["name"]}</a></strong> — {m["village"]} — {m["experience_years"]} yrs<br>{m["bio"] or ""}<br>Rating {m["rating_avg"]:.1f} ({m["rating_count"]})</div></div>' for m in members)
    return HTML_HEAD + f"""
<h2>{name}</h2>
<div class="grid">
<div>
<div class="card">
<h3>Map — site location</h3>
{map_html}
</div>
<div class="card">
<h3>All people involved at this site</h3>
<ul>{people_html}</ul>
<small>Combined from each beekeeper's site_people field. Edit any member to update.</small>
</div>
</div>
<div>
<h3>Members ({len(members)})</h3>
{member_html}
</div>
</div>
<div class="card"><h3>Recent batches from this site</h3>{batch_html}</div>
""" + HTML_FOOT

def render_pooled():
    con = db()
    lots = con.execute("SELECT * FROM pooled_lot ORDER BY id DESC").fetchall()
    batches = con.execute("SELECT hash, flower_source, harvest_date, beekeeper_id FROM batch ORDER BY id DESC LIMIT 50").fetchall()
    con.close()
    # options for 5 hashes
    opts = "".join(f'<option value="{b["hash"]}">{b["hash"][:10]} — {b["flower_source"] or "?"} — {b["harvest_date"]}</option>' for b in batches)
    lots_html = ""
    for lot in lots:
        try:
            prevs = json.loads(lot["prev_hashes"])
        except:
            prevs = [lot["prev_hashes"]]
        lots_html += f'<div class="card"><h3 style="margin:0">Pooled lot {lot["pooled_hash"][:10]}... <span class="badge">{lot["plant_name"] or "plant"}</span></h3><div>Plant: {lot["plant_name"] or "-"} — {lot["plant_date"]} — {lot["weight_kg"] or "-"} kg</div><div>From {len(prevs)} field hashes:</div><ul>' + "".join(f'<li><a href="/verify/{h}">{h[:10]}...</a> (<a href="/pooled/{lot["pooled_hash"]}?s={lot["scan_secret"] or ""}">{lot["pooled_hash"][:10]} lot</a>)</li>' for h in prevs[:5]) + f'</ul><div><a href="/pooled/{lot["pooled_hash"]}">Open lot</a> | <a href="/verify/{lot["pooled_hash"]}?s={lot["scan_secret"] or ""}">Verify lot QR</a></div></div>'
    if not lots_html:
        lots_html = "<p>No pooled lots yet. Coop can pool 5 field harvests for one plant run.</p>"
    form = f'''
<div class="card">
<h3>Create pooled lot — coop at plant</h3>
<p><small>Pick 5 field hashes from same flower and date, coop operator creates one pooled lot. Households need not be at plant.</small></p>
<form method="POST" action="/api/pooled">
<div class="grid">
<div><label>Plant name<input name="plant_name" placeholder="Ramnagar or Mobile Van"></label></div>
<div><label>Plant date<input type="date" name="plant_date" value="{datetime.now().date()}" required></label></div>
<div><label>Weight kg<input type="number" step="0.1" name="weight_kg" placeholder="300"></label></div>
<div><label>Flower filter<small> optional</small><input name="flower" placeholder="mustard"></label></div>
</div>
<label>Pick 5 field hashes (hold Ctrl) <select name="prev_hashes" multiple size="6" required>{opts}</select></label>
<small>One pooled lot lists 5 field hashes. Hash = SHA256(sorted hashes + plant + date). Rating uses pooled QR token.</small>
<button type="submit">Pool and make lot QR</button>
</form>
</div>
'''
    return HTML_HEAD + f"<h2>Pooled lots — where 5 histories meet</h2><p>Coop pools 5 household harvests for one 300 kg plant run. Each field hash is already frozen, pooled lot links to them as a DAG.</p>{form}{lots_html}" + HTML_FOOT

def render_pooled_one(pooled_hash, scan_token=None):
    con = db()
    lot = con.execute("SELECT * FROM pooled_lot WHERE pooled_hash=?", (pooled_hash,)).fetchone()
    if not lot:
        # maybe it is a batch hash, fall back to verify
        con.close()
        return render_verify(pooled_hash, scan_token)
    try:
        prevs = json.loads(lot["prev_hashes"])
    except:
        prevs = [lot["prev_hashes"]]
    # get field batches
    placeholders = ",".join(["?"]*len(prevs))
    fields = con.execute(f"SELECT b.*, k.name, k.village FROM batch b JOIN beekeeper k ON k.id=b.beekeeper_id WHERE b.hash IN ({placeholders})", prevs).fetchall() if prevs else []
    con.close()
    field_list = "".join(f'<li><a href="/verify/{f["hash"]}?s={f["scan_secret"] or ""}">{f["hash"][:10]} — {f["name"]} — {f["flower_source"]} — {f["harvest_date"]}</a></li>' for f in fields) or "".join(f"<li>{h[:10]}...</li>" for h in prevs)
    has_valid = scan_token and lot["scan_secret"] and scan_token == lot["scan_secret"]
    note = "<span class='ok'>Valid scan token — you can rate this pooled lot once.</span>" if has_valid else "<small>Scan the pooled QR with ?s=token to rate. One rating per pooled QR.</small>"
    rating = f'''
<div class="card"><h3>Rate this pooled lot</h3>
{'<form method="POST" action="/api/rate_pooled"><input type="hidden" name="pooled_hash" value="'+pooled_hash+'"><input type="hidden" name="scan_secret" value="'+(scan_token or '')+'"><label>Stars<select name="stars"><option>5</option><option>4</option><option>3</option><option>2</option><option>1</option></select></label><button type="submit">Rate pooled lot</button></form>' if has_valid else '<p><em>Rating locked. Scan pooled QR.</em></p>'}
{note}
</div>
'''
    qr_js = f"new QRCode(document.getElementById('qrcode'), {{text: window.location.origin + '/pooled/{pooled_hash}?s={lot['scan_secret']}', width: 160, height: 160}});" if lot["scan_secret"] else "new QRCode(document.getElementById('qrcode'), {text: window.location.href, width: 160, height: 160});"
    return HTML_HEAD + f"""
<h2>Pooled lot</h2>
<div class="card">
<div>Pooled hash: <pre>{pooled_hash}</pre></div>
<div>Plant: {lot["plant_name"] or "-"} — {lot["plant_date"]} — {lot["weight_kg"] or "-"} kg</div>
<div>Scan token: <small>{lot["scan_secret"] or "legacy"}</small></div>
<div id="qrcode" style="margin-top:12px"></div>
<script>{qr_js}</script>
</div>
<div class="card"><h3>From {len(prevs)} field harvests</h3><ul>{field_list}</ul></div>
{rating}
""" + HTML_FOOT

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/":
            self.send_html(render_home())
        elif path == "/promotion":
            self.send_html(render_promotion())
        elif path == "/beekeeper":
            self.send_html(render_beekeeper_list())
        elif path == "/collectives":
            self.send_html(render_collectives())
        elif path.startswith("/collective/"):
            name = path[len("/collective/"):]
            self.send_html(render_collective_one(name))
        elif path.startswith("/beekeeper/"):
            try:
                bid = int(path.split("/")[2])
                self.send_html(render_beekeeper_one(bid))
            except:
                self.send_error(404)
        elif path == "/pooled":
            self.send_html(render_pooled())
        elif path.startswith("/pooled/"):
            h = path.split("/pooled/")[1].strip().split("?")[0].split("#")[0]
            qs = urllib.parse.parse_qs(parsed.query)
            s = qs.get("s", [None])[0]
            self.send_html(render_pooled_one(h, s))
        elif path.startswith("/verify/"):
            h = path.split("/verify/")[1].strip().split("?")[0].split("#")[0]
            qs = urllib.parse.parse_qs(parsed.query)
            s = qs.get("s", [None])[0]
            self.send_html(render_verify(h, s))
        elif path == "/api/batches":
            con = db()
            rows = [dict(r) for r in con.execute("SELECT * FROM batch ORDER BY id DESC").fetchall()]
            con.close()
            self.send_json(rows)
        elif path == "/api/beekeepers":
            con = db()
            rows = [dict(r) for r in con.execute("SELECT * FROM beekeeper").fetchall()]
            con.close()
            self.send_json(rows)
        elif path == "/health":
            self.send_json({"ok": True})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode() if length else ""
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        wants_json = content_type == "application/json"
        if wants_json:
            try:
                d = json.loads(body) if body else {}
                if not isinstance(d, dict):
                    raise ValueError("JSON body must be an object")
                form_data = {}
            except (json.JSONDecodeError, ValueError) as e:
                self.send_error(400, f"Invalid JSON body: {e}")
                return
        else:
            form_data = urllib.parse.parse_qs(body)
            d = {k: v[0] for k, v in form_data.items()}
        if path == "/api/beekeeper":
            con = db()
            con.execute("INSERT INTO beekeeper (name, phone, village, experience_years, bio, upi_id, promotion_opt_in, photo_url, collective_name, latitude, longitude, site_people) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (d.get("name"), d.get("phone"), d.get("village"), int(d.get("experience_years") or 0), d.get("bio"), d.get("upi_id"), int(d.get("promotion_opt_in") or 0), d.get("photo_url"), d.get("collective_name"), float(d.get("latitude") or 0) or None, float(d.get("longitude") or 0) or None, d.get("site_people")))
            con.commit(); con.close()
            self.redirect("/beekeeper")
        elif path.startswith("/api/beekeeper/") and path.endswith("/update"):
            try:
                bid = int(path.split("/")[3])
                con = db()
                con.execute("UPDATE beekeeper SET photo_url=?, collective_name=?, latitude=?, longitude=?, site_people=?, promotion_opt_in=? WHERE id=?",
                            (d.get("photo_url") or None, d.get("collective_name") or None, float(d.get("latitude") or 0) or None, float(d.get("longitude") or 0) or None, d.get("site_people"), int(d.get("promotion_opt_in") or 0), bid))
                con.commit(); con.close()
                self.redirect(f"/beekeeper/{bid}")
            except Exception as e:
                self.send_error(400, str(e))
        elif path.startswith("/api/beekeeper/") and path.endswith("/promote"):
            try:
                bid = int(path.split("/")[3])
                con = db()
                con.execute("UPDATE beekeeper SET promotion_opt_in=? WHERE id=?", (int(d.get("promotion_opt_in") or 0), bid))
                con.commit(); con.close()
                self.redirect(f"/beekeeper/{bid}")
            except Exception as e:
                self.send_error(400, str(e))
        elif path == "/api/batch":
            con = db()
            last = con.execute("SELECT hash FROM batch ORDER BY id DESC LIMIT 1").fetchone()
            prev = last["hash"] if last else None
            try:
                beekeeper_id = int(d.get("beekeeper_id") or 1)
            except (TypeError, ValueError):
                beekeeper_id = 1
            hive_id = d.get("hive_id")
            harvest_date = d.get("harvest_date")
            flower = d.get("flower_source") or d.get("floral_source") or ""
            honey_type = d.get("honey_type") or ""
            location = d.get("location") or ""
            h = batch_hash(prev, beekeeper_id, hive_id, harvest_date, flower, honey_type, location)
            scan_secret = secrets.token_hex(8)
            try:
                con.execute("INSERT INTO batch (beekeeper_id, hive_id, harvest_date, location, honey_type, flower_source, horticulture_notes, harvest_method, weight_kg, prev_hash, hash, scan_secret) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (beekeeper_id, hive_id, harvest_date, location, honey_type, flower, d.get("horticulture_notes"), d.get("harvest_method"), float(d.get("weight_kg") or 0) or None, prev, h, scan_secret))
                con.commit(); con.close()
                if wants_json:
                    self.send_json({"ok": True, "hash": h, "scan_secret": scan_secret, "verify_url": f"/verify/{h}?s={scan_secret}"}, status=201)
                else:
                    self.redirect(f"/verify/{h}?s={scan_secret}")
            except Exception as e:
                is_dup = isinstance(e, sqlite3.IntegrityError)
                if psycopg and hasattr(psycopg, 'errors'):
                    try:
                        is_dup = is_dup or isinstance(e, psycopg.errors.UniqueViolation)
                    except: pass
                if not is_dup and "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                    con.close()
                    self.send_error(500, str(e))
                    return
                con.close()
                if wants_json:
                    self.send_json({"error": str(e), "hash": h}, status=409)
                else:
                    self.send_html(HTML_HEAD + f"<p>Duplicate hash or error: {e}</p><pre>{h}</pre>" + HTML_FOOT)
        elif path == "/api/hive":
            con = db()
            def f(*keys):
                v = next((d.get(key) for key in keys if d.get(key) not in (None, "")), None)
                return float(v) if v not in (None, "") else None
            temp = f("temperature", "temp_c"); hum = f("humidity"); weight = f("weight", "weight_kg"); sound = f("sound_db", "sound")
            hive_id = d.get("hive_id")
            beekeeper_id = int(d.get("beekeeper_id")) if d.get("beekeeper_id") else None
            flag = hive_flag(temp, hum, weight, sound)
            if weight is not None and hive_id:
                prev = con.execute("SELECT weight FROM hive_reading WHERE hive_id=? ORDER BY id DESC LIMIT 1", (hive_id,)).fetchone()
                if prev and prev["weight"]:
                    if weight < prev["weight"]*0.9:
                        flag = (flag + ", weight drop") if flag!="ok" else "weight drop"
            con.execute("INSERT INTO hive_reading (hive_id, beekeeper_id, temperature, humidity, weight, sound_db, flag) VALUES (?,?,?,?,?,?,?)",
                        (hive_id, beekeeper_id, temp, hum, weight, sound, flag))
            con.commit(); con.close()
            if wants_json:
                self.send_json({"ok": True, "flag": flag}, status=201)
            else:
                self.redirect("/")
        elif path == "/api/rate":
            con = db()
            try:
                stars = int(d.get("stars"))
                b_hash = d.get("batch_hash")
                scan_secret = d.get("scan_secret")
                # verify scan_secret matches batch if batch has one
                brow = con.execute("SELECT scan_secret FROM batch WHERE hash=?", (b_hash,)).fetchone()
                if brow and brow["scan_secret"]:
                    if scan_secret != brow["scan_secret"]:
                        con.close()
                        self.send_html(HTML_HEAD + "<p>Rating needs a valid scan token from the QR. Scan the QR with ?s=token.</p><a href='/'>back</a>" + HTML_FOOT)
                        return
                # prevent reuse of same token for same batch
                if scan_secret:
                    exists = con.execute("SELECT 1 FROM rating WHERE batch_hash=? AND scan_secret=?", (b_hash, scan_secret)).fetchone()
                    if exists:
                        con.close()
                        self.send_html(HTML_HEAD + "<p>This QR has already been used to rate this batch. One rating per scan.</p><a href='/'>back</a>" + HTML_FOOT)
                        return
                con.execute("INSERT INTO rating (beekeeper_id, batch_hash, scan_secret, consumer_id, stars) VALUES (?,?,?,?,?)",
                            (int(d.get("beekeeper_id")), b_hash, scan_secret, d.get("consumer_id"), stars))
                avg = con.execute("SELECT AVG(stars) as a, COUNT(*) as c FROM rating WHERE beekeeper_id=?", (int(d.get("beekeeper_id")),)).fetchone()
                con.execute("UPDATE beekeeper SET rating_avg=?, rating_count=? WHERE id=?", (avg["a"], avg["c"], int(d.get("beekeeper_id"))))
                con.commit(); con.close()
                # keep token in redirect so QR stays valid
                qs = f"?s={scan_secret}" if scan_secret else ""
                self.redirect(f"/verify/{b_hash}{qs}")
            except Exception as e:
                is_dup = isinstance(e, sqlite3.IntegrityError)
                if psycopg and hasattr(psycopg, 'errors'):
                    try:
                        is_dup = is_dup or isinstance(e, psycopg.errors.UniqueViolation)
                    except: pass
                if not is_dup and "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                    con.close()
                    self.send_error(500, str(e))
                    return
                con.close()
                if d.get("scan_secret") or d.get("batch_hash"):
                    wants = self.headers.get("Content-Type","").split(";",1)[0].strip().lower()=="application/json"
                    if wants:
                        self.send_json({"error": "duplicate rating", "detail": str(e)}, status=409)
                        return
                self.send_html(HTML_HEAD + "<p>You already rated this batch with that scan token.</p><a href='/'>back</a>" + HTML_FOOT)
        elif path == "/api/pooled":
            con = db()
            try:
                plant_name = d.get("plant_name") or "Plant"
                plant_date = d.get("plant_date") or datetime.now().date().isoformat()
                weight = float(d.get("weight_kg") or 0) or None
                prevs = form_data.get("prev_hashes", []) if not wants_json else d.get("prev_hashes", [])
                if isinstance(prevs, str):
                    prevs = [prevs]
                if len(prevs)==1 and "," in prevs[0]:
                    prevs = [p.strip() for p in prevs[0].split(",") if p.strip()]
                if len(prevs) < 1:
                    con.close()
                    self.send_html(HTML_HEAD + "<p>Pick at least one field hash to pool.</p><a href='/pooled'>back</a>" + HTML_FOOT)
                    return
                phash = pooled_hash(prevs, plant_name, plant_date)
                scan_secret = secrets.token_hex(8)
                con.execute("INSERT INTO pooled_lot (plant_name, plant_date, pooled_hash, prev_hashes, weight_kg, scan_secret) VALUES (?,?,?,?,?,?)",
                            (plant_name, plant_date, phash, json.dumps(prevs), weight, scan_secret))
                con.commit(); con.close()
                if wants_json:
                    self.send_json({"ok": True, "pooled_hash": phash, "scan_secret": scan_secret, "pooled_url": f"/pooled/{phash}?s={scan_secret}"}, status=201)
                else:
                    self.redirect(f"/pooled/{phash}?s={scan_secret}")
            except Exception as e:
                con.close()
                if wants_json:
                    self.send_json({"error": str(e)}, status=400)
                else:
                    self.send_html(HTML_HEAD + f"<p>Pool error: {e}</p><a href='/pooled'>back</a>" + HTML_FOOT)
        elif path == "/api/rate_pooled":
            con = db()
            try:
                stars = int(d.get("stars"))
                phash = d.get("pooled_hash")
                scan_secret = d.get("scan_secret")
                brow = con.execute("SELECT scan_secret FROM pooled_lot WHERE pooled_hash=?", (phash,)).fetchone()
                if brow and brow["scan_secret"] and scan_secret != brow["scan_secret"]:
                    con.close()
                    self.send_html(HTML_HEAD + "<p>Rating needs valid pooled scan token.</p><a href='/pooled'>back</a>" + HTML_FOOT)
                    return
                # simple check for reuse
                exists = con.execute("SELECT 1 FROM rating WHERE batch_hash=? AND scan_secret=?", (phash, scan_secret)).fetchone() if scan_secret else None
                if exists:
                    con.close()
                    self.send_html(HTML_HEAD + "<p>This pooled QR already used to rate.</p><a href='/pooled'>back</a>" + HTML_FOOT)
                    return
                # find a beekeeper for rating aggregation - use first field's beekeeper or plant
                # for now use first field's beekeeper or 1
                first = None
                try:
                    prevs = json.loads(con.execute("SELECT prev_hashes FROM pooled_lot WHERE pooled_hash=?", (phash,)).fetchone()["prev_hashes"])
                    if prevs:
                        first = con.execute("SELECT beekeeper_id FROM batch WHERE hash=?", (prevs[0],)).fetchone()
                except:
                    pass
                bid = first["beekeeper_id"] if first else 1
                con.execute("INSERT INTO rating (beekeeper_id, batch_hash, scan_secret, stars) VALUES (?,?,?,?)",
                            (bid, phash, scan_secret, stars))
                avg = con.execute("SELECT AVG(stars) as a, COUNT(*) as c FROM rating WHERE beekeeper_id=?", (bid,)).fetchone()
                con.execute("UPDATE beekeeper SET rating_avg=?, rating_count=? WHERE id=?", (avg["a"], avg["c"], bid))
                con.commit(); con.close()
                qs = f"?s={scan_secret}" if scan_secret else ""
                self.redirect(f"/pooled/{phash}{qs}")
            except Exception as e:
                con.close()
                self.send_html(HTML_HEAD + f"<p>Rate pooled error: {e}</p><a href='/pooled'>back</a>" + HTML_FOOT)
        else:
            self.send_error(404)

    def send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def send_json(self, obj, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj, indent=2).encode())

    def redirect(self, loc):
        self.send_response(303)
        self.send_header("Location", loc)
        self.end_headers()

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    print(f"Honey Chain running on http://localhost:{port}")
    print(f"DB: {os.path.abspath(DB)}")
    HTTPServer(("", port), Handler).serve_forever()
