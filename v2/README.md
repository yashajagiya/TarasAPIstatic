# 🏎️ Taras F1 Static REST API v2

High-performance, edge-cached Formula 1 REST API served directly from GitHub Pages (`https://yashajagiya.github.io/Taras/v2/`).

---

## 🌐 Public REST API Endpoints

| Endpoint | Method | Description | Size |
|---|---|---|---|
| [`overview.json`](overview.json) | `GET` | Home dashboard: season metrics, current leader, next GP, latest podium | `~2.1 KB` |
| [`drivers.json`](drivers.json) | `GET` | All 23 drivers with portraits, team colors, 16 season metrics, bios | `~208 KB` |
| [`teams.json`](teams.json) | `GET` | All 11 constructors with official car renders, white logos, specs | `~85 KB` |
| [`standings.json`](standings.json) | `GET` | Driver & Constructor championship tables + round progression | `~190 KB` |
| [`calendar.json`](calendar.json) | `GET` | 24-race schedule with track maps, circuit records, UTC times | `~34 KB` |
| [`live.json`](live.json) | `GET` | Live telemetry state: track flags, on-track count, leader | `~0.4 KB` |
| [`results/latest.json`](results/latest.json) | `GET` | Complete weekend classifications for active / latest GP (FP1..Race) | `~26 KB` |
| [`results/round_{N}.json`](results/round_17.json) | `GET` | Archived session classifications for completed rounds (Rounds 1–18) | `~25 KB` |

---

## 🛠️ Pipeline Engines & Scripts

- **`run_v2.py`:** Master Asynchronous Anti-Ban Runner. Orchestrates polite scraping, builds endpoints, and verifies integrity in one command.
  ```bash
  python v2/run_v2.py                  # Run once safely
  python v2/run_v2.py --loop           # Continuous loop with jitter
  python v2/run_v2.py --stealth        # Maximum safety mode
  python v2/run_v2.py --round 17       # Scrape specific round
  ```
- **`build.py`:** Master endpoint builder and aggregator (`python v2/build.py`).
- **`update.py`:** Pipeline orchestrator CLI (`python v2/update.py`).
- **`extract_rounds.py`:** Historical round extractor (`python v2/extract_rounds.py --round 17`).
- **`test_v2_integrity.py`:** 8-suite automated data integrity test (`python v2/test_v2_integrity.py`).

---

## 📂 Internal Modules & Data Architecture

- **`data/`:** Master organized data store (see [`data/README.md`](data/README.md)):
  - `registries/`: Authoritative season registries (`drivers_registry.json`, `teams_registry.json`, `calendar_master.json`, `drivers_data.json`, `races_data.json`)
  - `images/`: Visual asset lookups (`driverimg.json`, `teamsimgdata.json`, `racesimg.json`)
  - `standings/`: Standings caches & historical backups (`f1_standings.json`, `standings_cache.json`, etc.)
  - `sessions/`:
    - `current/`: Active weekend live session extractions (`fp1_extracted.json`, `qualifying_results.json`, `race_results.json`, etc.)
    - `rounds/`: Archived historical round datasets (`round_1.json` through `round_18.json`)
- **`collectors/`:** Data normalization adapters (`espn_standings.py`, `f1_encyclopedia.py`, `f1_sessions.py`).
- **`scrapers/`:** Session HTML scrapers and parsers.

