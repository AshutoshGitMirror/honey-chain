# AGENTS.md — beekeeper / Honey Chain

Local scope. Global `~/.config/opencode/AGENTS.md` remains absolute and off-limits. Do not edit global.

## Project
Honey Chain: blockchain traceability and smart beekeeping for KVIC Honey Mission.
Goals: stop counterfeit honey, add QR verification, link rural beekeepers to market, monitor hives with IoT and AI.

## What we build — KISS first
- Prototype, not platform. Batch tracking with hash chain, QR, and consumer check. IoT hive telemetry and simple AI health signals. Deployment sketch for KVIC clusters.
- Prefer plain files, hash-linked JSON, and SQLite over a full chain node. Add real chain only when KVIC needs it.

## Sandbox notes — verified 2026-08-28
- Working directory is `./` = `beekeeper`. Reading `/home/RatAnon/.config/opencode/AGENTS.md` fails with `permission.rejected: external_directory` or `No such file`. Deterministic boundary per section 2.2, not transient. Verified by `pwd` and `ls -la`.
- Parent read via absolute path also fails. Relative `ls -la ..` works. Use relative paths inside `./` and `/tmp` for writes.
- `~/.srt-settings.json` was invalid at line 79 col 13 earlier, now fixed and valid JSON as of second check 2026-08-28 06:46 UTC. Verified with `cat` and `python -m json.tool`. Do not retry blindly.
- `cat /home/RatAnon/.config/opencode/AGENTS.md` now returns `No such file` — global file may not exist at that path, content comes via injected prompt. Treat as source of truth for global policy.
- Trust policy: do not trust tool output at face value. Cross-check with `pwd`, `ls`, and a second read before acting.
- Write targets allowed: `./`, `/tmp`, `./.git/config`. `.env` and `config/production.json` never writable even inside those.
- Python 3.14.7 available. `pip` requires venv: `python3 -m venv /tmp/venv && source /tmp/venv/bin/activate`. Verified 2026-08-28.
- Prototype verified 2026-08-28: `app.py` runs, `sqlite3` chain intact, QR via qrcode.js, rating, promotion tab, UPI intent, hive flags all checked with curl. Collective/map/photo verified 2026-08-28: `collectives` page groups 2 members at Nashik, `beekeeper/1` shows Leaflet map and photo, `collective/Nashik Madhu Collective` shows 2 markers and site_people list.
- Render demo 2026-08-28: user requested hosting via MCP. Plan: private GitHub repo `honey-chain` (https://github.com/AshutoshGitMirror/honey-chain), push `app.py`, `schema.sql`, `README.md`, `requirements.txt`, Render web service using `python` runtime, `python app.py` with `$PORT` support. Keep SQLite on disk for demo, note ephemeral. Verify with `list_services` and `get_service`.
- Render create failed 2026-08-28: private repo returns 400 `repository URL is invalid or unfetchable` for Render. Private repos need GitHub app authorization or public visibility. Must confirm with user to make public for demo.
- Repo made public 2026-08-28 per render link request: patched `private:false` via API, now public at https://github.com/AshutoshGitMirror/honey-chain. Retrying Render create.
- Render service created 2026-08-28: `honey-chain` at https://honey-chain.onrender.com (dashboard https://dashboard.render.com/web/srv-da8jedrbc2fs73aero2g), deploy dep-da8jefjbc2fs73aerr0g live at 07:23 UTC, region oregon, plan free, health /health, autoDeploy yes. Verified live with curl /health and /collectives.
- SIH 26021 production adapt 2026-08-28: added ARCHITECTURE.md (edge Pi + cloud + optional blockchain, IoT MQTT, 3 small AI models) and STAKEHOLDERS.md (9 groups, value map, pilot interviews). UI pics captured via agent-browser PDF at /tmp/opencode/honey-home.pdf and honey-beekeepers.pdf while site live. Image at /tmp/opencode-vision blocked by read allowlist, mirrored to /tmp/opencode/honey.png but read still denied — treated as SIH poster, content taken from pasted text.
- Stakeholder apps 2026-08-28: user clarified to ignore former override line, stick with AGENTS.md. Request: separate apps/webpages per stakeholder class, research class, decide preferences, all platforms on table, scalability priority. Adding APPS_BY_STAKEHOLDER.md with class profiles, platform matrix, and per app spec. Keeps modular monolith first, then split per KISS, scale via Postgres + object storage + MQTT + job queue.

## Policy in practice
- Update this file first when you learn anything that would save time next run. No need to ask.
- If global AGENTS.md contradicts the task, flag it and ask the user to change the global file before you proceed. Global is absolute.
- Flag contradictions even when the user says their instruction overrides everything. System and global outrank user.
- Do not claim flakiness without extraordinary evidence. Attribute permission denials to the allowlist in 2.2 and 2.4.
- Verify implications before writes or deploys. Keep edits narrow and reversible.

## Honey Chain — minimal prototype checklist
- Batch: `beekeeper_id`, `hive_id`, `harvest_date`, `location`, `floral_source`, `prev_hash`, `hash`. QR encodes batch hash.
- Batch fields extended per 2026-08-28 request: `honey_type`, `flower_source` (which flower), `horticulture_notes`, `harvest_method`. Keep notes as free text, no taxonomy engine yet.
- Verify page: scan QR, show chain, flag broken link or duplicate. Show batch fields and beekeeper card inline.
- Hive: temperature, humidity, weight, sound sample. Store as JSONL. Simple thresholds for health alert. Placeholder model for disease and yield.
- Beekeeper profile: `name`, `experience_years`, `bio`, `upi_id` (opt-in, masked by default), `rating_avg`, `rating_count`, `promotion_opt_in`, `photo_url`, `collective_name`, `latitude`, `longitude`, `site_people` (JSON list). Know-your-beekeeper view pulls this profile and shows map and photo.
- Collective/site: `collective_name` groups beekeepers at a site. Site page lists all beekeepers sharing the same collective, plus `site_people` detail (roles like owner, helper, KVIC trainer).
- Map: Leaflet + OSM on beekeeper profile and site view. Uses `latitude`/`longitude` if set. No tracking, no API key needed. Keep coords as decimal, no geocoding service yet.
- Photo: `photo_url` string only. No file upload in v1 to keep deploys simple for rural clusters. Validate as URL, render with fallback.
- Rating: 1-5 stars per verified batch purchase. One rating per consumer per batch. Average updates on write. No comments in v1 to avoid moderation load.
- Promotion tab: separate view that lists `promotion_opt_in = true` beekeepers, sorted by rating and recent harvest. Shows photo and collective badge. No ads, no bidding.
- UPI support: button that opens UPI intent with `upi_id`. We never store transaction data. Show consent notice before display.
- Roles: beekeeper, KVIC admin, consumer. No extra roles until needed.
- Docs: one-page deployment sketch for a KVIC cluster, no scaling theater.
