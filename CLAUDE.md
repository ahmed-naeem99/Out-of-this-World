# FireWatch — Shared Claude Context

This file is auto-loaded by Claude Code at the start of every session.
Both founders should pull the latest version before a session and push updates after significant discussions.

---

## What Is FireWatch

FireWatch is a Near Real-Time (NRT) wildfire detection and validation platform.

**The Problem:** NASA satellite programs (VIIRS, MODIS) detect thermal anomalies globally, but the raw feed is extremely noisy — gas flares, sun glint, industrial heat all trigger false positives. Emergency agencies can't act on raw data.

**The Solution:** FireWatch ingests raw satellite data (Layer 1) and runs it through a multi-sensor confidence scoring algorithm to output validated fire alerts (Layer 2).

**Target customers:** Federal agencies (CIFFC), provincial fire operations, insurance/reinsurance companies.

---

## Repo Structure

Two active branches:
- `demo` — static demo mode, locked to August 10–17 2025 data, used for pitches
- `dev` — live production system running against NASA FIRMS API on AWS Lightsail

```
backend/
  server.py                  # Flask API (port 5000)
  data_pipeline.py           # Orchestrator — fetches + validates
  fire_alert_validator.py    # Core scoring engine
  firms_data_collector_v2.py # NASA FIRMS API integration
  hourly_loop.py             # 15-min scheduler (runs on Lightsail)
  Procfile                   # gunicorn deployment config

frontend/fire-map-frontend/
  src/App.js                 # Root — view mode toggle (validated vs raw)
  src/MapComponent.js        # Leaflet map, fire markers, AOI controls
  src/SidebarPanel.js        # Time range, confidence filters, AOI inputs

.github/workflows/
  firms-pipeline.yml         # GitHub Actions hourly pipeline (backup to Lightsail)

current_bbox.txt             # Persisted AOI bbox for production server
```

Databases (SQLite, local to each deployment):
- `viirs.db` — 3 tables: viirs_snpp, viirs_noaa20, viirs_noaa21
- `modis.db`, `landsat.db`, `goes.db`
- `validated_fires.db` — output of the scoring engine

---

## The Validation Algorithm (Core IP)

### Sensor Weights
```
VIIRS:   0.60  (375m resolution, most reliable)
MODIS:   0.20  (1km resolution, backup)
GOES:    0.15  (rapid temporal updates, marginal Canada coverage)
Landsat: 0.05  (gold standard but 16-day revisit)
```

### Input Score Normalization
- "h" / "high" / numeric ≥85 → 1.0
- "n" / "nominal" / numeric 60–84 → 0.7
- "l" / "low" / numeric <60 → 0.2

### Scoring Formula
```
Final Score = min(Σ(W_i × S_i) × 100, 100.0)
```
- Primary sensor: VIIRS NOAA-20
- Secondary sensors matched by time window + distance threshold:
  - VIIRS:   ±6h, 5.0km
  - MODIS:   ±3h, 3.0km
  - GOES:    ±15min, 10.0km
  - Landsat: ±72h, 1.0km
- Triple-pass bonus: +0.25 if 3+ distinct VIIRS timestamps agree

### Confidence Tiers (dev branch)
```
Level 4: ≥85%  — Confirmed Fire (red)
Level 3: 60–84% — Active Alert (orange)
Level 2: 40–59% — Potential Anomaly (yellow)
Level 1: <40%  — Filtered out
```

### Demo Branch Tiers (3-tier system)
```
≥85%:   Confirmed Fire
60–84%: Active Alert
40–59%: Potential Anomaly
<40%:   Hidden
```

---

## Known Issues & Open Design Decisions

### Critical / Unresolved
1. **VIIRS NOAA-20 is the only primary sensor** — if NOAA-20 has a data gap, no fires validate even if SNPP and NOAA-21 both agree. Single point of failure in primary detection.
2. **BBOX clear is nuclear** — changing AOI deletes all sensor data and re-fetches. Map goes blank during the fetch window. No "keep old while loading new" behavior.
3. **GOES coverage for Canada is marginal** — GOES-West and GOES-East coverage of Alberta/Saskatchewan is inconsistent. The 0.15 weight may be doing little real work. Needs verification against live data.
4. **GitHub Actions + Lightsail are independent** — both run the pipeline but against separate SQLite files with no sync. Relationship needs to be clarified (redundancy vs duplication).
5. **NASA API key is hardcoded** in `firms_data_collector_v2.py`. Should be moved to `.env`.
6. **`current_bbox.txt` is committed to the repo** — mutable server state in version control causes conflicts between developers.

### Scoring Logic Issues
7. **The static veto (demo branch)** — Oil Sands and other industrial sites are hard-capped to score 10.0. This would silence a real Fort McMurray-scale fire. Needs to change from veto to penalty + flag.
8. **The 3-pass bonus is described as "+25%" in pitches but implemented as flat +0.25** — these are different operations. Description and code are inconsistent.
9. **GOES confidence string parsing** — parser handles "h"/"l" single chars and numerics, but GOES/Landsat may send full strings like "high"/"nominal"/"low". Would silently assign 0.7 (nominal) to a "high" detection.

### Frontend Issues
10. **Demo branch has hardcoded `DEMO_NOW = 2025-08-17`** — works fine for pitches, but make sure anyone running the demo knows the time slider is anchored to that date.
11. **Confidence level buttons in sidebar** — dev branch has 4 levels, need to confirm sidebar toggles match.

---

## Active Brainstorming / Next Steps

### Reverse-Engineering the Validation Engine (Priority Discussion)
The idea: use historical ground truth (CWFIS NFDB confirmed fire locations) + historical NASA FIRMS raw detections to build a labeled dataset, then empirically derive optimal weights instead of guessing them.

**Ground truth sources:**
- CWFIS NFDB (`NFDB_point_20240613.txt` already in repo) — fire points up to June 2024
- Provincial fire agency records (Alberta Wildfire, Saskatchewan SPSA)
- NFDB perimeter shapefiles — FIRMS detections inside a confirmed perimeter = confirmed real fire

**False positive labeling approaches:**
- Persistent detection sites (same pixel every month = industrial, not fire)
- Cross-reference with known industrial facility locations
- Winter detections in Canadian Prairies (Jan–Feb = zero real fires = clean FP training set)

**Three levels of ambition discussed:**
1. Weight tuning — keep existing formula, optimize W values via grid search
2. Feature-based classifier — logistic regression or random forest on cluster features
3. Temporal sequence model — model fire evolution over time

**Open questions on this:**
- Which metric matters most: recall (never miss a fire) or precision (never false alarm)?
- Keep the system interpretable for fire managers, or accept a black box for accuracy?
- Is this for product improvement or a validation study for investors/agencies?

---

## Architecture Decisions & Rationale

- **SQLite over PostgreSQL** — intentional for portability and single-instance deployment. Works on Lightsail without a separate DB server. Revisit if concurrent writes become a problem.
- **Flask over FastAPI** — simplicity. No async requirements identified yet.
- **React + Leaflet** — react-leaflet v4 with CartoDB/Esri basemaps. Satellite view uses Esri World Imagery.
- **Demo data** — real NASA FIRMS downloads for August 2025 (actual active fire season), filtered to AB/SK. ~48k rows per VIIRS sensor.

---

## How to Run Locally

**Backend:**
```bash
cd backend
python server.py   # runs on http://127.0.0.1:5000
```

**Frontend:**
```bash
cd frontend/fire-map-frontend
npm start          # runs on http://localhost:3000
```

**Seed demo data (demo branch only):**
```bash
cd backend
python seed_demo_data.py
```

**Run pipeline manually:**
```bash
cd backend
python data_pipeline.py
```

---

## Deployment (AWS Lightsail)

- Single instance runs both Flask API and `hourly_loop.py`
- Frontend is a static build
- `Procfile` uses gunicorn for Flask
- `.env` on server contains `REACT_APP_DEFAULT_BBOX` and `REACT_APP_API_URL` (set to Lightsail IP)
- GitHub Actions workflow provides hourly redundancy (independent pipeline run, separate DB state)

---

*Last updated: 2026-03-23 — Initial full project audit and brainstorming session (validation algorithm reverse-engineering approach discussed).*
