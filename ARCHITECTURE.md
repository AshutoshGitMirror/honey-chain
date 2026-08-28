# Honey Chain — production architecture and deployment for KVIC, SIH 26021

This turns the prototype at https://honey-chain.onrender.com into a real KVIC system. Keeps the simple hash chain you can demo now, and shows where to grow.

## 1. Problem in one line
Counterfeit honey, low trust, weak market link, no traceability, and no hive insight for rural beekeepers under Honey Mission.

## 2. What we ship

* Hash linked batch history with QR consumer check. Works offline at the cluster, syncs later.
* Beekeeper profile: name, village, experience, photo, collective, location, UPI, rating. Know your beekeeper on every verify.
* Collective site: members at same apiary, all people involved, shared map.
* Hive telemetry: temperature, humidity, weight, sound. Simple flags now, AI later.
* Promotion tab: opted in beekeepers sorted by rating and recent harvest. No ads.

## 3. Architecture — keep it small, make it grow

```
[ Beekeeper PWA — offline first ]      [ Consumer PWA — scan QR ]
        |                                       |
        +------> [ Edge Pi at cluster ] <-------+
                   |  MQTT + HTTP
                   |  SQLite + hash chain
                   v
              [ Cloud API — Render / AWS ]
              |  Web service python app.py -> FastAPI
              |  Postgres (batch, beekeeper, rating, hive_reading)
              |  Object storage (photos)
              |  Redis (rate limit)
              |  QR + hash service
                   |
        +----------+----------+
        |          |          |
   [ Blockchain ] [ AI ]  [ Admin Dashboard ]
   optional layer  pipeline   KVIC officers
```

* **Edge first.** The prototype SQLite file per cluster is the edge. No internet needed to create a batch or scan inside the village. Weekly `rsync` to cloud when the KVIC van visits. If you add a Pi, run the same `app.py` there and sync with Litestream.
* **Cloud now.** One Render web service `honey-chain` `srv-da8jedrbc2fs73aero2g` at https://honey-chain.onrender.com. It already handles `$PORT`, `/health`, and OSM maps. For scale, move to Postgres on Render and keep the same API shape.
* **Blockchain when asked.** Keep the hash column now. When KVIC wants immutability, hash the batch JSON to Polygon or Hyperledger Fabric and store the tx hash next to `hash`. No rewrite. The verify page then shows both the local chain and the on chain tx.
* **IoT.** ESP32 + DHT22 + HX711 load cell + MEMS mic. Publish every 30 min via WiFi or LoRa to the Pi gateway over MQTT. Pi runs a small collector that calls `POST /api/hive`. The flag logic stays simple thresholds first: temp >35 or <15, humidity <40 or >85, sound >85, weight drop >10 percent. That already caught the high temp case in demo.
* **AI.** Three small models, not one big one:
  1. Sound CNN for brood disease and queen loss from 5 sec audio
  2. Image check from phone photo of comb for varroa or foulbrood
  3. LSTM for yield from weight + weather + floral calendar
  Start with rules, collect data, then train on KVIC cluster data. Show predictions as low, medium, high confidence, never as a hard block.

## 4. Data model — production

* `beekeeper` id, name, village, phone, experience_years, bio, upi_id, promotion_opt_in, photo_url, collective_name, latitude, longitude, site_people JSON, rating_avg, rating_count
* `batch` id, beekeeper_id, hive_id, harvest_date, location, honey_type, flower_source, horticulture_notes, harvest_method, weight_kg, prev_hash, hash, tx_hash nullable
* `rating` id, beekeeper_id, batch_hash, consumer_id, stars 1-5, unique per batch per consumer
* `hive_reading` id, hive_id, beekeeper_id, temperature, humidity, weight, sound_db, flag, recorded_at

Photos are URL strings. No file upload in v1. Store files in S3 later and keep the same URL field.

## 5. UX that makes sense — three flows

**Beekeeper, low literacy, low bandwidth**
Open home, pick name from dropdown, add harvest date, hive, flower, weight, notes. One tap creates hash and QR. A second form logs hive reading. All works with big buttons, Hindi toggle later, and offline cache. Profile page shows photo, map, collective, people involved, rating, and UPI support button that opens the UPI app with consent.

**Consumer, trust in 5 seconds**
Scan QR, land on `/verify/<hash>`. See Chain intact, honey type and flower, horticulture notes, beekeeper card with photo and experience, collective badge, map, and rating. One tap to rate. No login. If chain is broken, show a clear red flag.

**KVIC officer, cluster view**
Open `/collectives` to see every site group, member count, average location. Open `/collective/Nashik Madhu Collective` to see two markers, all people involved at the site, member cards, and recent batches. Promotion tab shows who to push to market.

## 6. Why this fits KVIC rural

* Offline first. Creation and verification do not need live internet.
* No app store needed. PWA runs in the browser, add to home screen.
* Cheap edge. Python + SQLite runs on a Pi or old laptop per cluster.
* OSM maps, no Google key, no cost.
* UPI support without storing payments. Just an intent link.

## 7. Scale plan — three steps

**Step 1 demo, done.** Single service on Render, SQLite file, hash chain, QR in browser, Leaflet maps, collective and site people, rating, UPI. Live at https://honey-chain.onrender.com, repo https://github.com/AshutoshGitMirror/honey-chain, deploy live.

**Step 2 pilot, one KVIC cluster, 20 beekeepers.** Add Postgres on Render, attach a Pi at the cluster, add auth for KVIC admin, add Hindi, add CSV export for KVIC reports, collect 1000 hive readings for AI baseline.

**Step 3 rollout, many clusters.** Fabric or Polygon for batch hash, object storage for photos, MQTT gateway per cluster, training job for the three AI models, public consumer portal with search by flower and region.

## 8. Security and trust

* One rating per consumer per batch, checked by device hash.
* UPI ID masked until consent.
* Hash chain detects duplicate or tampered batch.
* Health check at `/health`, logs via Render, no secrets in code.

## 9. What we leave out now — YAGNI

No token, no coin, no complex role graph, no built in chat, no ad bidding. Add those only if KVIC asks after the pilot proves trust.
