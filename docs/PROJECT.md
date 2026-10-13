# TARAS F1 Static API — Project & Ecosystem Document

**Repository:** `TarasAPIstatic` (`yashajagiya/TarasAPIstatic`)  
**Maintainer:** [Yash Ajagiya](https://github.com/yashajagiya)  
**Season Covered:** 2026 Formula 1 World Championship  
**Deployment:** 100% Static REST API on GitHub Pages Global Edge CDN (`github.io`)  
**License:** MIT (Data aggregated from public sports feeds; F1 marks belong to Formula One Licensing B.V.)

---

## 1. Executive Summary & Purpose

**TarasAPIstatic** is a high-performance, 100% static Formula 1 REST API and dataset. It provides client applications (such as mobile apps, web dashboards, and bots) with real-time and historical championship standings, driver dossiers, constructor specifications, calendar schedules, track maps, and full race weekend classifications — **all without paid commercial API subscriptions, backend server infrastructure, or API keys**.

Every endpoint is pre-rendered and saved as a deterministic JSON file in git. When pushed, GitHub Pages serves the entire API from Fastly/Cloudflare edge cache locations worldwide with sub-50ms latency.

**In one sentence:** Scrape & normalize official F1 feeds via async anti-ban runners → aggregate into standardized JSON endpoints → host statically on GitHub Pages edge CDN.

---

## 2. Product Context & Ecosystem Role

```text
┌────────────────────────────────────────────────────────┐
│               CONSUMER APPLICATIONS                   │
│  • TARAS Mobile App (Android Jetpack Compose & iOS)    │
│  • Web Portals & Real-Time Race Dashboards             │
│  • Community Discord & Telegram Formula 1 Bots         │
└───────────────────────────▲────────────────────────────┘
                            │ HTTPS GET (Static JSON)
┌───────────────────────────┴────────────────────────────┐
│          GITHUB PAGES GLOBAL EDGE CDN (github.io)      │
│  https://yashajagiya.github.io/TarasAPIstatic/v2/      │
└───────────────────────────▲────────────────────────────┘
                            │ Git Push (Zero-Server Deployment)
┌───────────────────────────┴────────────────────────────┐
│            TarasAPIstatic DATA ENGINE (Python)         │
│  • Master Anti-Ban Async Runner (run_v2.py)            │
│  • Master Endpoint Aggregator (v2/build.py)            │
│  • 8-Suite Data Integrity Verifier (test_v2_integrity) │
│  • Internal Data Store (v2/data/)                      │
└────────────────────────────────────────────────────────┘
```

| Component | Role | Stack |
|---|---|---|
| **Data Plane (`TarasAPIstatic`)** | Scrapes, normalizes, validates, and serves static JSON. | Python 3.11+, BeautifulSoup, Asyncio |
| **CDN Host (`github.io`)** | Worldwide edge-caching with unlimited read bandwidth. | GitHub Pages (Fastly / Cloudflare Edge) |
| **Developer Portal (`index.html`)** | Interactive in-browser endpoint tester & code generator. | Vanilla HTML5, CSS3, JavaScript |
| **Client Applications** | Consume JSON endpoints for UI presentation. | Kotlin/Compose, Swift, Dart/Flutter, React |

---

## 3. Goals & Non-Goals

### Core Goals
- **Zero Compute Cost:** No continuous cloud servers, virtual machines, or container runtimes.
- **Zero API Keys & Quotas:** 100% open public access without rate limits, billing, or token expiration.
- **Instant Client Hydration:** Complete home screen dashboard loaded in a single request (`/v2/overview.json`).
- **Non-Destructive Historical Retention:** Archive every race weekend permanently (`v2/results/round_{1..18}.json`) without overwriting previous sessions.
- **Industrial Anti-Ban Defense:** Run unattended continuous scraping loops safely without risking IP bans or rate limits.

### Explicit Non-Goals
- Real-time millisecond live telemetry (car throttle, brake, RPM, or micro-sector telemetry).
- Official licensed FIA timing or F1 TV video streaming feeds.
- Complex write APIs or GraphQL database mutations.

---

## 4. Public API Delivery & Base URLs

### Primary V2 Next-Gen REST API
**Base URL:** `https://yashajagiya.github.io/TarasAPIstatic/v2/`

| Endpoint | Path | Key Data Provided |
|---|---|---|
| **Overview** | `/v2/overview.json` | Championship leaders, next race countdown, live schedule, latest podium in 1 call |
| **Drivers** | `/v2/drivers.json` | All 23 drivers with transparent portraits, vector numbers, hex team colors, 16 season metrics, 8 career stats |
| **Teams** | `/v2/teams.json` | All 11 constructors with 2026 car side cutouts, white monochrome logos, technical specs, chassis, engines |
| **Standings** | `/v2/standings.json` | Drivers & Constructors championship tables with complete round-by-round point breakdowns |
| **Calendar** | `/v2/calendar.json` | 24-race schedule with transparent circuit outlines, lap records, corner counts, UTC timestamps |
| **Active Weekend** | `/v2/results/latest.json` | Full classifications for active Grand Prix (FP1..FP3, Qualifying, Sprint Qualifying, Sprint Race, Grand Prix) |
| **Historical Rounds** | `/v2/results/round_{N}.json` | Dedicated static endpoints for completed rounds (Rounds 1–17) and upcoming rounds (Round 18) |
| **Live Telemetry** | `/v2/live.json` | Track flags, current leader, on-track car count, session timing metadata |

### Legacy V1 Compatibility API
**Base URL:** `https://yashajagiya.github.io/TarasAPIstatic/v1/`
- Full backwards compatibility with original legacy file paths (`driversperrace.json`, `carperrace.json`, `f1Info/drivers_data.json`, `practice1/`..`race-result/`).

---

## 5. Industrial Anti-Ban Scraping Engine

To collect data safely from public sports feeds without triggering Cloudflare blocks or IP bans, the repository utilizes an asynchronous runner architecture (`run_v2.py` and `v2/run_v2.py`):

1. **Rotating Browser Profiles:** Dynamic rotation across modern Chrome 125/126, Edge 125, macOS Safari, and Firefox 126 with realistic `sec-ch-ua` and `Sec-Fetch-*` navigation headers.
2. **Per-Domain Concurrency Locks:** Separate `asyncio.Lock` per domain (`formula1.com`, `site.api.espn.com`, `f1api.dev`) ensuring parallel execution never overwhelms a single host.
3. **Polite Human Jitter:** Randomized sleep delays (`1.8s - 3.8s` standard, `3.5s - 6.5s` in `--stealth`).
4. **Smart Cache Hit Guards:** Finalized sessions and historical round archives are cached locally in `v2/data/sessions/rounds/`. When already present, network calls are completely bypassed (`⚡ Cache Hit`).
5. **Circuit Breakers & Exponential Backoff:** Automatic detection of HTTP 429/403 with safety cooldown pauses to protect the host IP.

---

## 6. How to Operate & Build

```bash
# Run V2 async anti-ban pipeline once
python run_v2.py

# Continuous loop mode (every 5 minutes with polite jitter)
python run_v2.py --loop --interval 300

# Stealth mode
python run_v2.py --stealth

# Scrape specific round (e.g. Round 17 Singapore)
python run_v2.py --round 17

# Offline endpoint build from local cache
python run_v2.py --skip-scrape

# Run 8-suite data integrity verifier
python v2/test_v2_integrity.py
```

---

## 7. Related Documentation

- [📑 API Reference](API_REFERENCE.md) — Complete endpoint schemas, response payloads, and field explanations.
- [🏗️ Architecture Guide](ARCHITECTURE.md) — System flow, data directory layouts, and extension instructions.
- [📱 App Integration Guide](APP_INTEGRATION_GUIDE.md) — Code samples for Android (Kotlin), iOS (Swift), Flutter (Dart), React Native, and Python.
- [🌐 Developer Portal](../index.html) — Live in-browser API explorer and snippet generator.
