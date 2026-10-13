# 📦 Taras F1 API v2 — Data Directory Architecture

This directory serves as the **master internal data store** for the Taras F1 API v2 build engine and scrapers. All raw inputs, season registries, encyclopedia dossiers, media maps, and session archives are neatly categorized below.

---

## 📂 Categorized Directory Layout

```text
v2/data/
├── registries/           ← Authoritative 2026 Season Registries & Encyclopedias
│   ├── drivers_registry.json    • All 23 drivers: permanent numbers, codes, team colors, portrait URLs
│   ├── teams_registry.json      • All 11 constructors: chassis, power units, team chiefs, technical specs
│   ├── calendar_master.json     • Canonical 24-race calendar: circuits, corners, lap records, UTC times
│   ├── drivers_data.json        • Deep encyclopedia: biographies, 16 season metrics, 8 career statistics
│   └── races_data.json          • Circuit details: geo-coordinates, circuit lengths, track metadata
│
├── images/               ← Visual Asset Maps & CDN Lookup Tables
│   ├── driverimg.json           • Official driver headshot / portrait image URLs
│   ├── teamsimgdata.json        • Constructor car renders (2400px cutouts) & white monochrome vector logos
│   └── racesimg.json            • High-resolution circuit track layout maps & diagrams
│
├── standings/            ← Championship Standings Backups & Caches
│   ├── standings_cache.json     • Unified master standings cache (drivers + constructors)
│   ├── f1_standings.json        • Driver championship standings points table
│   ├── f1_constructor_standings.json • Constructor championship standings points table
│   ├── driversperrace.json      • Round-by-round driver points breakdown across all completed races
│   └── carperrace.json          • Round-by-round constructor points breakdown across all completed races
│
├── sessions/             ← Complete Race Weekend Session Classifications
│   ├── current/                 • Active race weekend raw extraction files (FP1, FP2, FP3, Qualy, Sprint, Race)
│   │   ├── fp1_extracted.json
│   │   ├── fp2_extracted.json
│   │   ├── fp3_extracted.json
│   │   ├── qualifying_results.json
│   │   ├── sprint_quly_result.json
│   │   ├── sprint_race_result.json
│   │   └── race_results.json
│   └── rounds/                  • Archived historical round packages (Rounds 1 through 18)
│       ├── round_1.json         • Australia (FP1..Race)
│       ├── round_2.json         • China (FP1..Race)
│       └── ... round_{18}.json  • Complete weekend session classifications
```

---

## 🛠️ Data Flow & Build Pipeline

1. **Scraping (`run_v2.py` / `extract_rounds.py`):**
   - Live weekend sessions are parsed and written into `data/sessions/current/`.
   - Completed weekend packages are archived into `data/sessions/rounds/round_{N}.json`.
2. **Aggregating (`build.py`):**
   - Reads registries from `data/registries/`.
   - Merges standings from `data/standings/` and live ESPN feed.
   - Combines image assets from `data/images/`.
   - Compiles session packages from `data/sessions/rounds/` and `data/sessions/current/`.
3. **Publishing (`v2/*.json` & `v2/results/`):**
   - Emits standardized, edge-cached static REST endpoints directly into `v2/` for GitHub Pages distribution.
