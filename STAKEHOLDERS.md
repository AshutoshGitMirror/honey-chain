# Stakeholders — Honey Chain SIH 26021

## Who matters and what they get

**1. Rural beekeeper**
Gives honey, hive care, harvest data. GetsQR for each batch, fair price, rating and promotion, UPI support, hive alerts, collective identity. UX is the simple two form home page and their profile with photo and map.

**2. Collective or SHG or site group**
The apiary site, not just one person. Example `Nashik Madhu Collective` has Ramesh Yadav and Kareem Ali at 20.011,73.79. Gives shared labor, training, storage. Gets a site page that lists every person involved and all members, plus a joint map. KVIC sees the site as one unit.

**3. KVIC Honey Mission and field officer**
Gives bee boxes, toolkits, training, cluster approval. Gets traceability from harvest to sale, tamper check via hash chain, cluster dashboards via collectives and hive flags, and data for policy. The admin view is the collectives list and site pages plus batch history.

**4. Consumer**
Gives trust and money. Gets instant QR verify at `/verify/<hash>` showing chain intact, flower source, horticulture notes, beekeeper card with experience and photo, collective badge, map, and a one tap rating. No account needed.

**5. Retailer and e commerce and haat**
Gives shelf access. Gets verifiable batches with story and location, and promotion sorted beekeepers to source from.

**6. Logistics and mandi**
Gives movement. Could add a scan at each hop later as `prev_hash` chain, now just the origin batch is proven.

**7. Cert lab and FSSAI and APEDA**
Gives lab test flag. Future step is to add `cert_hash` to the batch row when the lab approves. The verify page then shows certified.

**8. State beekeeping boards and NAFED and TRIFED**
Gives market linkage and procurement. Gets aggregated data by flower, region, season.

**9. Tech team and student team**
Keeps the service live on Render, the Pi at the cluster, and the AI models honest about confidence.

## Map — how value moves

Beekeeper at site -> creates batch hash and QR at edge Pi or phone -> consumer scans QR and rates -> rating raises beekeeper score -> promotion tab surfaces the beekeeper -> KVIC uses collective site pages to pick clusters to support -> retailer picks promoted batches -> money goes via UPI intent straight to beekeeper.

Counterfeit breaks because the hash chain has no duplicate and the QR must match a stored hash. No hash, no sale.

## Who to interview for pilot

* 2 beekeepers from Nashik Madhu Collective, 1 from Muzaffarpur Litchi Group
* 1 KVIC field officer per cluster
* 5 consumers at a KVIC honey stall
* 1 cert lab contact

Those five conversations will tell you if the map helps, if the photo builds trust, and if the site people list is actually useful.

## Risks and mitigations

* Low connectivity — solved with offline first PWA and Pi edge.
* Photo and location privacy — opt in, URL only, consent before showing UPI, coords rounded to 3 decimals.
* Rating gaming — one vote per batch per device, no text, average only.
* Blockchain hype — keep hash chain now, add chain tx later only if KVIC asks.

