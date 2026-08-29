# Honey Chain — vision. SIH 26021. KVIC Honey Mission.

This file holds the shared understanding so it survives a context cut. If you open a new session, read this before you touch code.

## What we are building and why

Counterfeit honey, low trust, weak market link, no traceability, no hive insight. KVIC gives 10 bee boxes per household and training via CBRTI Pune and 15 SBECs, but the honey still moves through cooperatives and plants and shops with no single truth.

Honey Chain makes one truth. One harvest, one hash, one QR at the field edge where honey leaves the beekeeper and enters the KVIC network. Farmer logs harvest on PWA, no printer. Coop prints the QR slip at pickup with hash plus a one time scan token. After that, KVIC network adds cooperative pickup, pooled lot, processing and lab, but the household stays the anchor. The mumbaikar who scans at the Gramodyog Bhavan sees household name, village, flower, harvest date, a google map embed of the household farm with the same pin KVIC sees, and a certified badge if a NABL lab has added it. Rating needs the scan token, one rating per QR, no device hash. That is five seconds of trust, no login.

## Where the line is

Everything happens at the edge between not in KVIC hands and in KVIC hands. KVIC is government and is in charge of the PS, but the data comes from cooperation.

Before the line: beekeeper at the farm field with 10 Langstroth boxes, family helper, flower area. This gives harvest data.
At the line: the cooperative society or NGO or trader who picks up raw honey at about 140 per kg. They write who picked and when. That is a linked note to the field hash.
After the line: the processing plant that heats to 60 to 65C, filters, bottles, the NABL lab that writes the cert PDF hash and CA number, the KVIC Bhavan that sells. The authorized packer writes the label after the lab, not before. The label has AGMARK insignia with CA number, grade, packer name and address, packing place, date, BEST BEFORE, lot, net weight, MRP, region, nutrition. That is in AGMARK 2008 and 2024. The mobile van at Panjokehra does 300 kg in 8 hours at the doorstep with a small lab. The plant may be the cluster common facility built with SFURTI money for 350 to 500 beekeepers, grant up to 5 crore.

Info is the sum of those cooperating hands, all while they work with KVIC.

## What a box is

A box is a Langstroth wooden hive with frames, one queen, many workers, 20,000 to 80,000 bees per box. KVIC gives 10 boxes with live colonies per person, plus a tool kit with smoker and veil, plus wax sheet, plus one extractor for 5 people, cost about 46k for Apis cerana. That is per the champions Beekeeping PDF table. The map unit is one household with 10 boxes, one pin. One QR per harvest from one household, not per box and not per cluster.

## How honey flows, plain

Farmer logs harvest on PWA. Coop prints QR slip at pickup. Cooperative pickup notes who, when, weight. If 5 households share one 300 kg plant session, coop pools them: pooled lot lists 5 field hashes with one plant QR, no household needs to be at the plant. Plant heats to 60 to 65C and filters at the doorstep van. Lab tests at NABL with 15 methods and adds cert PDF and CA number. Authorized packer writes the AGMARK label after the lab. KVIC Bhavan sells on consignment. Consumer scans QR with scan token at the Bhavan.

If you must pool to fill the 300 kg plant, keep the per household field hashes frozen and make a pooled lot that lists those 5 prev_hashes with hash = SHA256(prev_hashes + plant data). That is where histories meet and form a DAG. The lab, packer, and Bhavan then continue from the pooled hash. No edit of the first hashes after you print.

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

* App today: `app.py` is stdlib `http.server` plus `sqlite3`, hash chain with `hash = SHA256(prev_hash + field data)` and `scan_secret` per batch as one time token for rating, Leaflet now and google map embed of household coords on every page. It reads `PORT` from env, so it runs on Render at `https://honey-chain.onrender.com:1` and on a Pi. Rating needs `?s=token`, single use per batch, no device hash.
* Next step per your stack call: Beekeeper Hive as React Native with Expo plus TypeScript, with web fallback via react-native-web for cross compat. One codebase for Android APK and PWA, offline SQLite via expo-sqlite, camera for QR, GPS for household pin, Bluetooth for hive sensor later. Shared logic package for hash and map.
* Others: KVIC Setu, Honey Check, Collective Sathi pooled, Bazaar Link, Cert Seal as TSX web ecosystem. Next.js 14 plus TSX plus Tailwind, shared UI package via Turborepo monorepo, shared `hash`, `map`, `cert` packages. All hit the same Postgres API, so 5 web apps share one backend.
* DB next: Postgres on Render, same API, plus `litestream` on the Pi for offline sync. Add `pg_trgm` for flower search and materialized view for promoted. Pooled lot table with `prev_hashes` JSON array.
* Photos: URL string now, S3 later, same field.
* Edge: Pi with Mosquitto for MQTT from ESP32 with DHT22, HX711 load cell, MEMS mic. Collector calls `POST /api/hive`. Batch at 30 minutes.
* AI: three small jobs run at night, not in request path. Sound CNN for disease, image check of comb, LSTM on weight plus weather for yield. Rules today, models after 1000 readings.
* Chain: hash at field now, `tx_hash` nullable for Polygon or Fabric later. No wallet for farmer. DAG for pooled lots where 5 histories meet.
* Maps: OSM now, google embed as option with the same household lat lon everywhere, not per box.
* Auth: household is account, no password for consumer, QR scan token per batch for rating, masked UPI with consent. Pooling is coop writes, not farmer.

All of this keeps one QR per household harvest as the trust anchor. You can add plant name, cert, pool lot, or lab fields later as columns or small JSON, the QR stays.

## Data freeze and pooling

Freeze is append only. Each hash with `prev_hash` is a freeze. Later data is a new linked record, never an edit of the old hash. If you pool, the pooled lot has `prev_hashes` as a list of the 5 field hashes, not an overwrite. That is where 5 household histories meet and form a DAG, then lab, packer, and Bhavan continue from that pooled hash.

Per household packing is ideal and costly. Pooling is real and cheaper for the 300 kg plant. The app keeps per household as the truth with one frozen hash per harvest, and pools only when the plant must by listing those hashes. Rating is frozen the same way: QR holds hash plus a one time scan token, rating needs that token and is single use per batch, so bots cannot spam with many machine IDs. Blockchain way is the same idea: rating is a transaction signed by the holder of the token.

## How we work

I will not make broad stack or scope choices without you. If I am stuck between two branches, I will grill you with the `question` tool as we did for the farm field model. I will keep this file updated first when we learn something that saves time, as `AGENTS.md:28` says. I will keep the copy to `./` for vision PDFs until you confirm the `tmp` read fix is stable, which now reads `/tmp/opencode/honey-home-1.png:1` directly. I will keep screenshots via `agent-browser` as the vision source, and primary sources as KVIC HTML and the 585680 byte champions PDF via browser fetch.

## What is live now

* Repo public at `https://github.com/AshutoshGitMirror/honey-chain:1` branch `main`, last local commits `a169544` dataflow rewrite and `3c2d00c` scan token not yet pushed per batch push norm
* Service `honey-chain` at `https://honey-chain.onrender.com:1` dashboard `https://dashboard.render.com/web/srv-da8jedrbc2fs73aero2g:1` live, health `/health:1`
* Visuals at `/home/RatAnon/AI-MultiAgent-Land/beekeeper/dataflow.png:1` 227K vertical readable and `/home/RatAnon/AI-MultiAgent-Land/beekeeper/uiux.png:1` 124K four column grid, both SEE verified, plus `honey-home-1.png:1` from tmp fix
* Home shows Add harvest batch with beekeeper, hive, flower, weight and Hive telemetry, beekeepers shows photo, collective, household map 20.011, 73.79, site people, collectives shows Nashik Madhu Collective with 2 members, pooled lot and rating token ready
* Next execute: push pooled lot table and packer fields `packer_name`, `ca_number`, `packing_date` and switch Leaflet to google embed as option. This vision is conclusive before execution.

If this vision is wrong or missing, tell me and I will edit this file before we code more.

