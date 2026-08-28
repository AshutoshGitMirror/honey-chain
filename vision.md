# Honey Chain — vision. SIH 26021. KVIC Honey Mission.

This file holds the shared understanding so it survives a context cut. If you open a new session, read this before you touch code.

## What we are building and why

Counterfeit honey, low trust, weak market link, no traceability, no hive insight. KVIC gives 10 bee boxes per household and training via CBRTI Pune and 15 SBECs, but the honey still moves through cooperatives and plants and shops with no single truth.

Honey Chain makes one truth. One harvest, one hash, one QR at the field edge where honey leaves the beekeeper and enters the KVIC network. After that, KVIC network adds processing and lab, but the household stays the anchor. The mumbaikar who scans at the Gramodyog Bhavan sees household name, village, flower, harvest date, a google map of the household farm, and a certified badge if a NABL lab has added it. That is five seconds of trust, no login.

## Where the line is

Everything happens at the edge between not in KVIC hands and in KVIC hands. KVIC is government and is in charge of the PS, but the data comes from cooperation.

Before the line: beekeeper at the farm field with 10 Langstroth boxes, family helper, flower area. This gives harvest data.
At the line: the cooperative society or NGO or trader who picks up raw honey at about 140 per kg. They write who picked and when. That is a linked note to the field hash.
After the line: the processing plant that heats to 60 to 65C, filters, bottles, the NABL lab that writes the cert PDF hash and CA number, the KVIC Bhavan that sells. The authorized packer writes the label after the lab, not before. The label has AGMARK insignia with CA number, grade, packer name and address, packing place, date, BEST BEFORE, lot, net weight, MRP, region, nutrition. That is in AGMARK 2008 and 2024. The mobile van at Panjokehra does 300 kg in 8 hours at the doorstep with a small lab. The plant may be the cluster common facility built with SFURTI money for 350 to 500 beekeepers, grant up to 5 crore.

Info is the sum of those cooperating hands, all while they work with KVIC.

## What a box is

A box is a Langstroth wooden hive with frames, one queen, many workers, 20,000 to 80,000 bees per box. KVIC gives 10 boxes with live colonies per person, plus a tool kit with smoker and veil, plus wax sheet, plus one extractor for 5 people, cost about 46k for Apis cerana. That is per the champions Beekeeping PDF table. The map unit is one household with 10 boxes, one pin. One QR per harvest from one household, not per box and not per cluster.

## How honey flows, plain

Beekeeper harvests. Cooperative takes it to plant. Plant heats and bottles. Lab tests at NABL and adds cert. Authorized packer writes the label. KVIC Bhavan sells. Consumer scans.

If you must pool to fill the 300 kg plant, keep the per household field hashes frozen and make a pooled lot that lists those hashes. Think of a basket with many field QRS inside and one plant QR outside. No edit of the first hash after you print.

## Who matters

Household beekeeper who gets rating and UPI, collective of households at one farm location like Nashik Madhu Collective with site people like Ramesh lead and Amit helper, cooperative IA and TA who aggregate for the cluster, plant operator, NABL lab, KVIC officer who reads and promotes, consumer at the shop. KVIC is the nodal agency, not the daily aggregator.

## Apps, separate but one core

All apps hit the same Postgres and hash service. That is how we scale to many clusters without rewriting.

* Beekeeper Hive PWA for the household. Offline first, big buttons, Hindi ready later, camera for QR, GPS for household pin. Two forms: add harvest, log hive.
* Collective Sathi as a role inside the same PWA for the lead. Site map with all members, people involved list.
* KVIC Setu web dashboard for officers. Collectives table, site map, batch timeline, hive health board, CSV export.
* Honey Check web for consumers. `/verify/<hash>` with chain intact, household card, google map embed of household coords, cert badge, one tap rate.
* Bazaar Link web for bulk buyers and NAFED, search by flower and region.
* Cert Seal web for labs, one form to add PDF hash.

We ship the PWA plus Honey Check plus KVIC Setu first. The rest when a real buyer and lab join the pilot. That is KISS.

## Stack, hyper optimal, extensible, YAGNI KISS

I chose small pieces that can run on a village Pi and also on Render without a rewrite.

* App: `app.py` now is stdlib `http.server` plus `sqlite3`, hash chain, Leaflet now and google map embed ready, qrcode in browser. It reads `PORT` from env, so it runs on Render at `https://honey-chain.onrender.com:1` and on a Pi.
* Next step when we outgrow SQLite: Postgres on Render, same API, plus `litestream` on the Pi for offline sync. Add `pg_trgm` for flower search and a materialized view for promoted.
* Photos: URL string now, S3 later, same field.
* Edge: Pi with Mosquitto for MQTT from ESP32 with DHT22, HX711 load cell, MEMS mic. Collector calls `POST /api/hive`. Batch at 30 minutes.
* AI: three small jobs run at night, not in the request path. Sound CNN for disease, image check of comb, LSTM on weight plus weather for yield. Rules today, models after 1000 readings.
* Chain: hash at field now, `tx_hash` nullable for Polygon or Fabric later. No wallet for the farmer.
* Maps: OSM now, google embed as option with the same lat lon.
* Auth: household is the account, no password for consumer, device hash per batch for rating, masked UPI with consent.

All of this keeps one QR per household harvest as the trust anchor. You can add plant name, cert, pool lot, or lab fields later as columns or small JSON, the QR stays.

## Data freeze and pooling

Freeze is append only. Each hash with `prev_hash` is a freeze. Later data is a new linked record, never an edit of the old hash. If you pool, the pooled lot has `prev_hashes` as a list, not an overwrite. That avoids the compromise you feared.

Per household packing is ideal and costly. Pooling is real and cheaper for the plant. The app keeps per household as the truth and pools only when the plant must. That is the realistic compromise we agreed on.

## How we work

I will not make broad stack or scope choices without you. If I am stuck between two branches, I will grill you with the `question` tool as we did for the farm field model. I will keep this file updated first when we learn something that saves time, as `AGENTS.md:28` says. I will keep the copy to `./` for vision PDFs until you confirm the `tmp` read fix is stable, which now reads `/tmp/opencode/honey-home-1.png:1` directly. I will keep screenshots via `agent-browser` as the vision source, and primary sources as KVIC HTML and the 585680 byte champions PDF via browser fetch.

## What is live now

* Repo public at `https://github.com/AshutoshGitMirror/honey-chain:1` branch `main`
* Service `honey-chain` at `https://honey-chain.onrender.com:1` dashboard `https://dashboard.render.com/web/srv-da8jedrbc2fs73aero2g:1` live, health `/health:1`
* Home shows Add harvest batch and Hive telemetry, beekeepers shows photo, collective, lat 20.011 lon 73.79, site people, collectives shows Nashik Madhu Collective with 2 members.
* Next is to add `packer_name`, `ca_number`, `packing_date` to the schema and switch the Leaflet map to a google embed, as you asked.

If this vision is wrong or missing, tell me and I will edit this file before we code more.

