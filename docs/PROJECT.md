# TARAS F1 Data — Project Document

**Repository:** `tarasF1Data`  
**Maintainer:** [Yash Ajagiya](https://github.com/yashajagiya)  
**Season covered:** 2026 Formula 1 World Championship  
**License:** MIT (data sourced from public sports feeds; F1 marks belong to Formula One Licensing B.V.)

This document describes **what this project is**, **how it is built**, and **how to operate it**. Endpoint field-level API reference lives in [`README.md`](README.md).

---

## 1. Purpose

**tarasF1Data** is a headless Formula 1 dataset and static REST API. It exists so the **TARAS** Android app (and any other client) can load championship standings, driver/team profiles, calendar, and weekend session results **without a paid commercial F1 API, backend server, or API key**.

Clients fetch JSON over HTTPS from GitHub Pages. There is no application server, database, or authentication layer.

**In one sentence:** scrape public F1 sources → normalize into JSON → commit to git → GitHub Pages serves the files as a CDN-cached API.

---

## 2. Product context (TARAS)

| Piece | Role |
|---|---|
| **TARAS (Android)** | Consumer app: Paddock, Grid, Calendar, Drivers. Jetpack Compose, Material 3 Expressive. Separate repo (`Taras`). |
| **tarasF1Data (this repo)** | Producer: scrapers, JSON datasets, GitHub Pages API. |
| **Notifications** | Optional push of in-app notification copy into the Taras repo via GitHub REST API. |

UI design for the app is specified in:

- [`TARAS_Design_Blueprint_M3.md`](TARAS_Design_Blueprint_M3.md)
- [`TARAS_Design_Blueprint_M3_v3.md`](TARAS_Design_Blueprint_M3_v3.md)
- [`TARAS_Screen_Specifications.md`](TARAS_Screen_Specifications.md)
- [`implementation_plan.md`](implementation_plan.md) / [`task.md`](task.md)

Those files are **app design**, not the data pipeline. This repository is the data plane.

---

## 3. Goals and non-goals

### Goals

- Deliver current 2026 standings, session classifications, and encyclopedia-style driver data as stable JSON URLs.
- Update after race weekends with little or no manual hosting work.
- Stay free: no keys, no quotas, no always-on compute.
- Keep payloads simple enough for mobile (Retrofit/Gson) and web (`fetch` / Axios).

### Non-goals

- Live telemetry, sector times, or radio feeds.
- Official FIA timing or licensed F1 TV data.
- A query language, GraphQL, or authenticated write API.
- Guaranteeing source-site HTML/API contracts (scrapers can break when formula1.com or ESPN change markup).

---

## 4. Architecture

```
Public sources          This repo                    Delivery              Clients
─────────────────       ─────────────────────        ──────────────        ────────
formula1.com results    Python scrapers              GitHub Pages CDN      TARAS app
ESPN F1 standings  →    → JSON files in git    →     yashajagiya.github    Dashboards
F1 media CDN            GitHub Actions (Mon)         .io/tarasF1Data/      Bots
Calendar / schedule.json
```

1. **Collect** — Session scrapers load `schedule.json`, pick the active or latest weekend, request the matching formula1.com results page, parse HTML with BeautifulSoup.
2. **Normalize** — Driver names, team names, circuit IDs, times/gaps, Q1–Q3 / SQ1–SQ3 columns, and championship points are written as indented JSON.
3. **Publish** — Scripts can copy into the git repo, commit, and `git push origin main`. Pages rebuild; files are available worldwide as static HTTPS resources.
4. **Consume** — Apps `GET` JSON. No CORS keys; treat as public read-only.

Standings files in this working tree (`f1_standings.json`, `f1_constructor_standings.json`) follow the same “leaderboard + per-round points” shape as the documented `driversperrace.json` / `carperrace.json` endpoints on Pages.

---

## 5. Public API (GitHub Pages)

**Base URL:** `https://yashajagiya.github.io/tarasF1Data/`

| Dataset | Local / published path | Contents |
|---|---|---|
| Driver standings | `f1_standings.json` (published as `driversperrace.json` on Pages) | Rank, car number, team, total points, per-race points |
| Constructor standings | `f1_constructor_standings.json` (published as `carperrace.json`) | Team rank, points, per-round constructor points |
| Driver profiles | `drivers_data.json` (published under `f1Info/` on Pages) | Bio, images, 2026 stats, career stats |
| FP1 / FP2 / FP3 | `practice1/fp1_extracted.json`, `practice2/…`, `practice3/…` | Session order, lap time or gap, laps |
| Qualifying | `qualifying/qualifying_results.json` | Grid, Q1 / Q2 / Q3 |
| Sprint qualifying | `sprint-quly/sprint_quly_result.json` | SQ1 / SQ2 / SQ3 |
| Sprint race | `sprint-race/sprint_race_result.json` | Finish, time/retired, sprint points |
| Grand Prix | `race-result/race_results.json` | Official classification and GP points |

Full field tables and client samples: [`README.md`](README.md).  
Unofficial ESPN / F1 source URLs: [`f1_apis_documentation.md`](f1_apis_documentation.md).

---

## 6. Repository layout

```text
tarasF1Data/
├── PROJECT.md                 ← this document
├── README.md                  ← public API guide
├── f1_apis_documentation.md   ← ESPN / F1 source notes
├── drivers_data.json          ← driver encyclopedia
├── f1_standings.json          ← WDC standings
├── f1_constructor_standings.json
├── practice1/                 ← FP1 scraper + output JSON
│   ├── fp1_extracted.json
│   └── code/fp1.py, schedule.json
├── practice2/ … practice3/
├── qualifying/
├── sprint-quly/
├── sprint-race/
├── race-result/
├── notification/              ← TARAS in-app notification publisher
│   ├── notification.json
│   └── update_notification.py
└── TARAS_*.md, task.md, implementation_plan.md
```

Each session folder follows the same pattern:

- `code/schedule.json` — 2026 calendar with event IDs and session dates (used to build formula1.com URLs).
- `code/<scraper>.py` — fetch, parse, write JSON next to the folder root, optionally commit/push.
- `<session>_*.json` — last extracted classification (empty `results` if the session is not published yet).

---

## 7. Session pipeline (how scrapers work)

Typical flow (FP1 is representative; qualifying, race, and sprint scripts are the same idea):

1. Read `code/schedule.json`.
2. If today falls inside a race weekend that has that session, use that event; otherwise use the **latest session date ≤ today**.
3. Build a URL such as  
   `https://www.formula1.com/en/results/2026/races/{event_id}/practice/1`
4. HTTP GET with a browser User-Agent.
5. Parse the results table (`BeautifulSoup`).
6. Write JSON. On fetch failure, write **metadata + empty `results`** from the schedule so clients still get circuit/race identity.
7. Optional: locate the `tarasF1Data` git remote, `git pull --rebase`, copy files, commit, `git push origin main`.

**Dependencies:** Python 3.9+, `beautifulsoup4`; race/qualifying/sprint scripts also use `requests`. Practice scripts use `urllib`.

**Example:**

```bash
python practice1/code/fp1.py
python qualifying/code/qualifying_scraper.py
python race-result/code/raceResult.py
```

Run from a machine that can reach formula1.com. Pushing requires git credentials for `origin`.

---

## 8. Notifications (TARAS app)

[`notification/update_notification.py`](notification/update_notification.py) publishes [`notification/notification.json`](notification/notification.json) into the **Taras** GitHub repo (`yashajagiya/Taras`, path `notification/notification.json`, branch `master`).

- Payload: `id`, `title`, `message` (title may include `[username]` for client-side personalization).
- Cooldown: 16 minutes (tracked in local `notificationhistory.json`, gitignored).
- Auth: local `token.json` with `github_token` (gitignored). Never commit tokens.

```bash
python notification/update_notification.py
```

---

## 9. Operations

| Activity | How |
|---|---|
| Refresh session results | Run the relevant scraper after FP/Q/Sprint/Race is published on formula1.com |
| Refresh standings | Process ESPN-derived standings (documented Monday GitHub Action on the published repo: `.github/workflows/update-f1.yml`) |
| Serve API | Push to `main`; GitHub Pages hosts the JSON |
| Breakage | formula1.com CSS/class names or ESPN JSON shape changed — update the matching scraper |

**Reliability notes**

- Static files do not go down with a custom server, but **stale data** is possible until a scraper or Action runs.
- Empty `results` arrays mean “session identity known, classification not available yet,” not necessarily a crash.
- Source sites are unofficial for this use; treat them as best-effort.

---

## 10. Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3 |
| HTML parse | BeautifulSoup |
| HTTP | `urllib` (practice) / `requests` (qualifying, race, sprint, notifications) |
| Storage | Git + JSON files |
| Hosting | GitHub Pages |
| Automation | GitHub Actions (standings on the published remote) |
| Consumers | Kotlin/Retrofit (TARAS), any HTTP JSON client |

---

## 11. Related documents

| File | Use when |
|---|---|
| [`README.md`](README.md) | Integrating a client; endpoint schemas and code samples |
| [`f1_apis_documentation.md`](f1_apis_documentation.md) | Understanding ESPN / F1 unofficial feeds |
| [`TARAS_Design_Blueprint_M3.md`](TARAS_Design_Blueprint_M3.md) | Implementing TARAS UI theming |
| [`TARAS_Screen_Specifications.md`](TARAS_Screen_Specifications.md) | Screen-by-screen app specs |
| [`implementation_plan.md`](implementation_plan.md) | Compose navigation / Calendar / Grid work in the Android project |

---

## 12. Attribution

Created for the TARAS F1 project. Championship and session data are aggregated from publicly available ESPN and Formula 1 web pages for informational and educational use. Formula 1, F1, and related marks are trademarks of Formula One Licensing B.V.
