# 🏗️ Taras F1 API — Architecture & Extension Guide

This document outlines the **Clean, Standalone Static API Architecture** of the Taras F1 API dataset, explaining how both `v1` and `v2` operate as completely self-contained, independent modules.

---

## 🏛️ Core Architectural Principles

1. **100% Standalone Modules (`v1` and `v2`):**
   Both `v1/` and `v2/` are entirely self-contained. Each version includes its own scrapers, build engines, registries, and generated JSON endpoints. Neither relies on external shared pipeline directories.
2. **Edge-Cached Zero Compute:**
   No runtime application servers, virtual machines, or active databases. All API endpoints exist as pre-rendered JSON files served directly via GitHub's worldwide Fastly/Cloudflare CDN.
3. **Deterministic & Idempotent Builds:**
   Running `python v2/update.py --skip-scrape` builds the entire V2 dataset deterministically from registries and local caches without side-effects or network dependencies.
4. **Non-Destructive Storage:**
   Historical session results (`v2/results/round_{1..18}.json`) are preserved permanently. New rounds are appended without overwriting or destroying past race data.
5. **Backwards Compatibility:**
   Legacy `v1/` endpoints remain intact with their dedicated legacy scrapers, while `v2/` powers modern high-performance client applications.

---

## 📁 Repository Directory Structure

```text
TarasAPIstatic/
├── .github/
│   └── workflows/
│       └── update-f1.yml        # Weekly automated GitHub Actions scraper & deployer
├── index.html                   # Interactive Developer Portal & REST API Explorer for GitHub Pages
├── README.md                    # Primary repository overview and developer guide
├── run_v1.py                    # Root CLI shortcut: Asynchronous anti-ban runner for V1
├── run_v2.py                    # Root CLI shortcut: Asynchronous anti-ban runner for V2
│
├── v1/                          # 100% Self-Contained Legacy API Module
│   ├── README.md
│   ├── run_v1.py                # Standalone async anti-ban runner with AntiBanClient
│   ├── peerracepointdriver.py   # Legacy driver standings scraper & generator
│   ├── peerracepointcar.py      # Legacy constructor standings scraper & generator
│   ├── f1Info/                  # Historical driver & race metadata scrapers
│   ├── practice1/ ...           # Session-specific legacy folders & outputs
│   └── *.json                   # Legacy public JSON datasets
│
├── v2/                          # 100% Self-Contained Modern REST API Module
│   ├── README.md
│   │
│   ├── 🌐 PUBLIC REST ENDPOINTS (GitHub Pages CDN)
│   ├── overview.json            # Home screen in 1 request
│   ├── drivers.json             # All 23 drivers with portraits & stats
│   ├── teams.json               # All 11 constructors with cars & logos
│   ├── standings.json           # Championship tables & round progression
│   ├── calendar.json            # 24-race schedule & track maps
│   ├── live.json                # Live session status metadata
│   ├── results/                 # Public session endpoints: latest.json & round_{1..18}.json
│   │
│   ├── ⚙️ PIPELINE LAUNCHERS & RUNNERS
│   ├── run_v2.py                # Standalone async anti-ban runner with AntiBanClient
│   ├── build.py                 # Master endpoint builder & aggregator
│   │   ├── test_v2_integrity.py     # 8-suite automated integrity verification
│   ├── collectors/              # Data adapters (ESPN, Encyclopedia, Sessions)
│   ├── scrapers/                # Official Formula 1 session HTML parsers
│   │
│   └── 📦 INTERNAL DATA REPOSITORY (`v2/data/`)
│       ├── registries/          # Authoritative base schemas & catalogs
│       │   ├── calendar_master.json
│       │   ├── teams_registry.json
│       │   └── drivers_data.json
│       ├── images/              # Image & media lookup maps
│       │   ├── driverimg.json
│       │   ├── teamsimgdata.json
│       │   └── racesimg.json
│       ├── standings/           # Championship point tracking & car-per-race tables
│       │   ├── driversperrace.json
│       │   └── carperrace.json
│       ├── sessions/            # Raw session cache & extracted weekend packages
│       │   ├── current/         # Raw session extractions (fp1_extracted.json, etc.)
│       │   └── rounds/          # Historical round raw packages (round_1.json .. round_18.json)
│
└── docs/                        # Complete technical documentation
    ├── APP_INTEGRATION_GUIDE.md # Android, iOS, Flutter, React Native integration guide
    ├── API_REFERENCE.md         # Full REST API endpoint reference & schemas
    ├── ARCHITECTURE.md          # Architecture & extension guide (this document)
    ├── F1_DATA_SOURCES.md       # External data source catalog
    ├── PROJECT.md               # Product background & Taras ecosystem role
    ```

---

## 📂 Session Data Architecture: Where Does Session Data Live?

A common question is: **Where does session data live? Should it be in `data/`?**

In Taras F1 API v2, there is a clean separation of concerns:

1. **Internal Raw Session Data (`v2/data/sessions/`)**:
   - **`v2/data/sessions/current/`**: Stores temporary raw session extractions (e.g., `fp1_extracted.json`, `qualifying_raw.json`) actively parsed by scrapers during a race weekend.
   - **`v2/data/sessions/rounds/`**: Stores offline raw weekend packages (`round_1.json` through `round_18.json`). The anti-ban runner inspects these to determine cache hits (`⚡ Cache Hit`) and prevent redundant network requests.

2. **Public REST Endpoints (`v2/results/`)**:
   - **`v2/results/latest.json`**: The public REST endpoint served to client applications representing the most recent race weekend (Practice 1, Practice 2, Practice 3, Qualifying, Sprint, Race).
   - **`v2/results/round_{1..18}.json`**: Standardized, edge-cached public REST endpoints served to mobile apps and websites via GitHub Pages (`https://<username>.github.io/<repo>/v2/results/round_17.json`).

This separation keeps the `v2/` root clean:
- **`v2/` root**: Only contains public endpoints, launchers, and core subdirectories.
- **`v2/data/`**: Houses all internal registries, image dictionaries, standings tables, and session archives organized by category.

---

## 🔄 Data Pipeline Flow

```mermaid
graph TD
    A[Official F1 Web / ESPN / Ergast] -->|Async Anti-Ban Scrapers| B[v2/scrapers/]
    B -->|Normalized Raw Sessions| C[v2/data/sessions/current/<br/>v2/data/sessions/rounds/]
    D[Master Registries<br/>v2/data/registries/<br/>calendar_master.json, teams_registry.json] --> E[v2/build.py]
    C --> E
    E -->|Generates Public Endpoints| F[v2/ Root & v2/results/]
    F -->|Validation| G[v2/test_v2_integrity.py]
    G -->|All 8 Tests Pass| H[Git Commit & Push]
    H -->|Deploy| I[GitHub Pages Edge CDN<br/>yashajagiya.github.io/Taras/v2/]
```

---

## 🛠️ How to Extend & Maintain

### 1. Adding a New Driver or Mid-Season Driver Swap
1. Open [`v2/data/registries/teams_registry.json`](file:///M:/TarasAPIstatic/v2/data/registries/teams_registry.json).
2. Locate the team (e.g. `racing-bulls`).
3. Add or update the driver entry with `id`, `name`, `code`, `number`, and `portrait_url`.
4. Run `python run_v2.py --skip-scrape`.
5. The build engine automatically updates `v2/drivers.json`, `v2/teams.json`, and `v2/overview.json`.

### 2. Updating Constructor Renders or Colors
1. Open [`v2/build.py`](file:///M:/TarasAPIstatic/v2/build.py).
2. Update the `OFFICIAL_TEAM_ASSETS` dictionary with new high-resolution URLs or ARGB hex color codes.
3. Run `python run_v2.py --skip-scrape`.

### 3. Scraping & Archiving a Race Weekend (Anti-Ban Protected)
```bash
# Scrape specific round with anti-ban protections:
python run_v2.py --round 18

# Continuous background loop mode (every 5 minutes with jitter & safety circuit breaker):
python run_v2.py --loop --interval 300

# Stealth mode with extra conservative delays:
python run_v2.py --stealth --round 18
```
This automatically checks local cache in `v2/data/sessions/rounds/`, scrapes any missing sessions safely, writes `v2/results/round_18.json`, updates `v2/results/latest.json`, recalculates `v2/standings.json`, and runs the integrity verification suite.

### 4. Running Data Integrity Tests
```bash
python v2/test_v2_integrity.py
```
Tests verified:
- [x] `overview.json` schema and leadership presence
- [x] All 23 drivers present with 16 season + 8 career metrics
- [x] All 11 constructors present with car renders and specs
- [x] Driver and Constructor standings with round points
- [x] Calendar coverage with valid dates and track maps
- [x] `results/latest.json` full weekend classification
- [x] Historical rounds 1 to 16 data retention
- [x] Specific Sprint weekend formatting (e.g. Round 17)

---

## 🌐 Deploying to GitHub Pages (`github.io`)

1. Commit and push the repository to GitHub:
   ```bash
   git add .
   git commit -m "Update F1 Static API dataset"
   git push origin main
   ```
2. In GitHub Repository Settings -> **Pages**:
   - **Source:** Deploy from a branch
   - **Branch:** `main` / `/ (root)`
3. Within ~60 seconds, all endpoints are live at `https://<username>.github.io/<repo>/v2/<endpoint>.json`.
