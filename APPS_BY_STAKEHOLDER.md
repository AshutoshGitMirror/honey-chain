# Honey Chain — separate apps by stakeholder class. SIH 26021, scalable from day one.

You asked for all platforms on the table and for a real choice per class, not one generic app. This file maps who they are, how they decide, and which app shape fits them. Code stays small. Services stay shared. Scale comes from the back end, not from building five different stacks on day one.

## How I chose. What matters when picking a platform

I looked at four things for each class: literacy and age, connectivity and power, device in hand, and what they need to decide. A rural beekeeper who is 45, reads Hindi, and shares one Android phone on 2G does not want the same screen a KVIC officer on a desktop with fiber wants. If I ignored that, the app would be pretty and unused. I also kept scalability as the first filter: every app hits the same Postgres and hash service, so I can add a state or a thousand clusters without rewriting.

## The classes

### 1. Rural beekeeper. The core user. Around 30 to 60 years old, 5 to 10 boxes, works with family.
* Where they live: village near fields, patchy 2G, power cuts. Many share a single Android phone, 5 inch screen, Android 11 or 12. Storage is tight.
* What they read: Hindi, Marathi, some English batch codes. Long forms are a pain. Voice and pictures work better than paragraphs.
* What they decide: Is my hive ok today. Should I harvest now. Who will buy at a fair price. Will my honey be trusted.
* What they need from us: One tap harvest log that makes a QR, a quick hive reading with a green or red flag, a profile that proves their work with photo and map, a way to get paid direct.

### 2. Collective lead or SHG didi. The site manager. Often the most phone savvy person at the apiary.
* Where they live: same village, but they travel to the KVIC cluster office and the haat.
* What they decide: Which members need help. Which batches to pool for a buyer. Who did what at the site.
* Need: a site view that lists every person involved and every member by collective_name, an aggregate map, and a single screen to push several beekeepers to the promotion tab.

### 3. KVIC officer and cluster coordinator. Desk plus field.
* Where they live: desktop at the district centre, plus field visits with a phone. Good internet at the office, spotty in the field.
* What they decide: Which collectives are real, which batches are certified, which cluster needs training or kits.
* Need: a report heavy dashboard, not a phone form. Filters by district, flower, date, rating, plus exports for the Honey Mission file. Needs to see hash chain and hive flags at a glance. Does not need to edit hive readings in the field.

### 4. Consumer. Urban, 22 to 45, buys on Amazon or at a KVIC store.
* Where they live: phone always on hand, fast data, iOS or Android. Scans QR at the shop or after delivery.
* What they decide: Is this honey real. Is it the flower I want. Do I trust this beekeeper enough to pay a premium and tip.
* Need: a five second verify, not an account. Photo, map, flower, horticulture notes, rating, and a UPI tip that does not ask them to sign up. If the chain is broken, a clear red block, not jargon.

### 5. Retail buyer and aggregator and NAFED or TRIFED.
* Where they live: desktop, needs bulk view.
* What they decide: Can I source 200 kg of litchi honey from Muzaffarpur with proof this month.
* Need: search by flower, region, collective, rating, and harvest date, with batch hashes and cert status ready to download.

### 6. Cert lab and FSSAI contact.
* Where they live: desktop, lab system.
* What they decide: Is this batch tested and what grade.
* Need: a tiny portal to attach a test PDF and set `cert_status` to the batch. No other write access.

## Platform matrix. All options, honest trade offs

This is where scalability meets reality. All of these can exist, but you do not ship all at once.

* **Beekeeper and collective lead. Primary: Android PWA.** Install from the browser, no Play Store wait, works offline, small install, updates without a store review. Secondary: native wrapper later with Capacitor if you need Bluetooth to the hive sensor. Fallback: WhatsApp bot for alerts and IVR for voice logging when data is down. I would start with PWA. Rural Android already struggles with store installs and updates. PWA gives you offline cache, camera for QR, and GPS for map with one codebase.
* **KVIC officer. Primary: web dashboard.** Next.js or plain server rendered pages, desktop first, fast tables, CSV export. No need for offline beyond a cached collective page for field visits. This is where you see scale. One dashboard queries the same Postgres that the PWA writes to, so adding a thousand collectives does not change the app.
* **Consumer. Primary: web PWA, no install.** Scan QR in the phone camera, open the verify URL, see the card and map. Add to home screen if they want. No login. This is the fastest path to trust. A full consumer app is more than you need before the pilot proves people even scan.
* **Retail buyer. Web portal.** Search and export. Same API, different view.
* **Cert lab. Web portal.** A single form, lock it by role.
* **Edge at the cluster. Not a platform users see, but it decides scale.** A Pi at the cluster runs the same `app.py` and an MQTT broker for the ES32 sensors. It holds SQLite and syncs to Postgres over the night. That is how you survive no signal. It also keeps the chain intact when the cloud is away.

My take: ship the PWA for beekeeper and collective first, plus the two web apps for KVIC and consumer verify. Those three cover 90 percent of the value. Add native, WhatsApp, and IVR only after the first 20 beekeepers use the PWA daily for a month. That is the hyper idealistic KISS call. It keeps you scalable without building five apps nobody maintains.

## Separate apps, what each one is. Not just pages, different products with a shared core.

A surprising amount can stay shared: Postgres, hash service, rating service, photo storage, map tiles, auth. The apps differ in UX, offline rules, and permissions.

### App 1. Beekeeper Hive — PWA for the beekeeper

* **Who.** Rural beekeeper and family helper.
* **Platform.** PWA, Android first, works in Chrome. Install prompt, offline cache for forms and recent batches, camera for QR, geolocation for map. Later wrap with Capacitor for BLE.
* **Stack.** Vite + Svelte or Preact, Workbox for offline, Leaflet for map. One API: `POST /api/batch`, `POST /api/hive`, `GET /beekeeper/:id`. No heavy framework. Keeps the install under 2 MB.
* **Screens.**
  1. Home with two cards: Add harvest and Log hive. Big buttons, Hindi toggle.
  2. Harvest form: beekeeper picker, hive, date, flower, honey type, weight, location, horticulture notes. On submit show hash and QR to print.
  3. Hive log: temp, humidity, weight, sound. On save show green or red flag. Weight drop check uses last reading from the edge.
  4. My profile: photo, collective, map, site people, rating, UPI button.
* **Offline.** Cache the forms and the last 20 batches in IndexedDB. Queue posts when offline, flush when back. Edge Pi is the offline source of truth if the phone is off.
* **Scale note.** One PWA build serves all clusters. Tenant is `collective_name` and `village`. No per cluster build.

### App 2. Collective Sathi — PWA extension for the lead, same codebase, different nav

You could ship this as a role inside Beekeeper Hive, but thinking of it as a separate app keeps the UX clean. The lead sees a site dashboard, not just their own hives.

* **Screens.**
  1. Site map with all members as markers at `/collective/<name>`.
  2. People involved list merged from each member's `site_people`.
  3. Batch pool view for the whole collective, filter by date and flower.
  4. One toggle to promote several members at once.
* **Why separate.** The beekeeper flow is one person, one hive. The lead flow is many people, one site. Mixing them on a small screen hurts both. A second nav inside the same PWA, gated by collective_name, solves it without a second deploy.

### App 3. KVIC Setu — web dashboard for officers

* **Who.** KVIC cluster officer and HQ.
* **Platform.** Web, desktop first, Next.js with server pages, Postgres directly, no offline needed except a cached collective page for field use.
* **Screens.**
  1. Collectives table by district, member count, avg rating, last harvest.
  2. Collective detail with map, members, people involved, batches, hive flag timeline.
  3. Verify audit: search any hash, see chain, see cert status.
  4. Hive health board: filters for high temp, low humidity, sound anomaly across hives.
  5. Export CSV for Honey Mission reporting.
* **Scale.** Server rendered tables over Postgres with indexes on `collective_name`, `harvest_date`, `flower_source`. Add read replicas when you go from 20 to 2000 beekeepers. No change to the PWA.

### App 4. Honey Check — consumer verify web PWA, no install required

* **Who.** Buyer in a shop or at home.
* **Platform.** Plain web page that works from a QR scan. No app store. Add to home screen optional.
* **Screens.**
  1. `GET /verify/<hash>` shows hash, QR, Chain intact or broken, batch card with flower and horticulture notes, beekeeper card with photo and experience, collective badge, Leaflet map, rating and one tap rate, UPI tip masked until consent.
* **Scale.** Cache verify responses at the CDN by hash. Hash is immutable, so cache hit is high. No login means no user table blow up.

### App 5. Bazaar Link — web portal for retail and NAFED

* **Who.** Buyer who needs bulk with proof.
* **Platform.** Web portal, same API, different query.
* **Screens.**
  1. Search by flower, honey type, region, collective, rating, date.
  2. Results show beekeeper, collective, location, weight available, rating, cert status.
  3. Export list with hashes and QR sheet for printing.
* **Scale.** Postgres with GIN index on flower and location, plus a materialized view for promoted beekeepers.

### App 6. Cert Seal — tiny lab portal

* **Who.** Lab technician.
* **Platform.** Web, single form, role locked.
* **Screens.**
  1. Lookup batch by hash, upload PDF, set `cert_status` to pass or fail, hash the PDF and store `cert_hash`.
  2. Verify page then shows certified with a link to the PDF.
* **Scale.** Object storage for PDFs, same batch row, no extra service.

### Invisible layer. Edge and IoT and AI, not an app but it makes the apps believable

* **Edge Pi at each cluster.** Runs `app.py` and Mosquitto. Sensors publish over MQTT every 30 minutes. Collector calls `POST /api/hive` on the Pi. Night sync via Litestream to Postgres. If you lose internet for a week, you still create batches and still verify inside the cluster.
* **AI jobs.** Not in the request path. Nightly job reads `hive_reading` and `batch`, runs the three small models, writes flags and a yield estimate back to the beekeeper app as a push notification or WhatsApp message. No extra latency for the user.

## Scalability by design, not by promise

* **One API shape everywhere.** Beekeeper PWA, KVIC dashboard, and Bazaar all call `batch`, `beekeeper`, `collective`, `rating`, `hive`. Add Postgres read replicas and a Render disk later, not a new backend.
* **Stateless web services.** `app.py` already reads `PORT` from the environment. It runs on one Render free instance now and can run on ten behind a load balancer later.
* **Photos.** URL string now. When you need files, put S3 behind it and keep the same field. No migration.
* **Maps.** OSM via Leaflet now. No vendor key, no quota surprise at 1000 clusters.
* **Offline.** PWA cache plus Pi edge is the scalable path for rural. SMS and WhatsApp are fallbacks, not the core. That keeps the system honest when signal is weak.
* **Blockchain.** Hash chain now, tx hash later. That is the scalable promise without asking a farmer to hold a wallet.

## What to ship first, in order

1. Beekeeper Hive PWA and Honey Check verify, live now at https://honey-chain.onrender.com. This proves trust.
2. KVIC Setu dashboard with collectives and hive flags. This proves the cluster view.
3. Add Postgres and S3, keep the same screens.
4. Add Edge Pi and MQTT at one pilot cluster.
5. Add the three AI jobs.
6. Then split Bazaar and Cert Seal as separate views when a real buyer and a real lab join the pilot.

That order is deliberate. You get a usable system for SIH and for KVIC in weeks, and you do not prebuild five native apps that nobody can maintain in a village with patchy power.
