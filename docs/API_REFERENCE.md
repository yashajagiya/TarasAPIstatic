# 🏎️ Taras F1 API v2 — Complete API Reference

Welcome to the definitive API reference for **Taras F1 API v2**. This static REST API provides live and historical Formula 1 data, championship standings, driver profiles, team specifications, and weekend session classifications without API keys or rate limits.

---

## 🌐 Base URL & CDN Delivery

All endpoints are statically hosted and edge-cached globally on GitHub's Fastly/Cloudflare CDN:

```text
https://yashajagiya.github.io/Taras/v2/
```
*(Legacy fallback URL: `https://yashajagiya.github.io/tarasF1Data/v2/`)*

- **Protocol:** HTTPS
- **Format:** Standard JSON (UTF-8)
- **Authentication:** None required (Zero config / 100% free)
- **HTTP Method:** `GET` for all endpoints
- **Cache-Control:** Edge-cached with automatic CDN invalidation on commit

---

## 📑 Summary of Endpoints

| Resource | Path | Size | Description |
|---|---|:---:|---|
| **Overview** | [`/v2/overview.json`](#1-overview-v2overviewjson) | ~2.1 KB | Single-request home dashboard: leaders, next race countdown, session schedule, latest podium. |
| **Drivers** | [`/v2/drivers.json`](#2-drivers-v2driversjson) | ~210 KB | All 23 drivers: portraits, numbers, transparent vector logos, team hex colors, career & season stats. |
| **Teams** | [`/v2/teams.json`](#3-teams-v2teamsjson) | ~86 KB | All 11 constructors: official white vector logos, transparent 2026 car side cutouts, specs, leadership. |
| **Standings** | [`/v2/standings.json`](#4-standings-v2standingsjson) | ~195 KB | Complete Drivers and Constructors championship leaderboards with round-by-round points progression. |
| **Calendar** | [`/v2/calendar.json`](#5-calendar-v2calendarjson) | ~35 KB | Full 24-race 2026 calendar with transparent SVG/PNG circuit track maps, lap records, and UTC schedules. |
| **Active Weekend** | [`/v2/results/latest.json`](#6-active-weekend-results-v2resultslatestjson) | ~26 KB | Complete classifications for active / latest weekend (FP1, FP2, FP3, Qualy, Sprint, Race). |
| **Historical Rounds** | [`/v2/results/round_{N}.json`](#7-historical-rounds-v2resultsround_njson) | ~25 KB | Complete weekend session archives for Rounds 1 through 18 (e.g. `round_17.json`). |
| **Live Telemetry** | [`/v2/live.json`](#8-live-telemetry-v2livejson) | ~0.4 KB | Live race session state, flag status, current leader, and active timing relay metadata. |

---

## 1. Overview (`/v2/overview.json`)

Designed to hydrate a mobile or web home screen in **a single network request**.

### Response Schema

```json
{
  "season": 2026,
  "generated_at": "2026-10-14T00:54:05Z",
  "championship_leader": {
    "driver": {
      "id": "max-verstappen",
      "name": "Max Verstappen",
      "number": 1,
      "code": "VER",
      "points": 331,
      "team": "Red Bull",
      "avatar": "https://media.formula1.com/..."
    },
    "team": {
      "id": "mclaren",
      "name": "McLaren",
      "points": 517,
      "color": "0xFFFF8000",
      "logo": "https://media.formula1.com/..."
    }
  },
  "next_event": {
    "round": 18,
    "race_name": "United States Grand Prix",
    "circuit_name": "Circuit of The Americas",
    "country": "United States",
    "city": "Austin",
    "date": "2026-10-18",
    "time_utc": "19:00:00Z",
    "is_sprint": true,
    "track_map": "https://media.formula1.com/...",
    "sessions": {
      "fp1": "2026-10-16T17:30:00Z",
      "sprint_qualifying": "2026-10-16T21:30:00Z",
      "sprint_race": "2026-10-17T18:00:00Z",
      "qualifying": "2026-10-17T22:00:00Z",
      "race": "2026-10-18T19:00:00Z"
    }
  },
  "latest_podium": [
    { "position": 1, "driver_name": "Max Verstappen", "team": "Red Bull", "points": 25 },
    { "position": 2, "driver_name": "Lando Norris", "team": "McLaren", "points": 18 },
    { "position": 3, "driver_name": "Charles Leclerc", "team": "Ferrari", "points": 15 }
  ]
}
```

---

## 2. Drivers (`/v2/drivers.json`)

Complete roster of all 23 official Formula 1 drivers (including mid-season substitutions like Yuki Tsunoda #22 at Racing Bulls).

### Key Fields per Driver
- `id`: Unique kebab-case driver slug (e.g. `"lewis-hamilton"`).
- `name`: Full driver name (e.g. `"Lewis Hamilton"`).
- `number`: Official permanent race number (`44`).
- `code`: 3-letter timing broadcast code (`"HAM"`).
- `portrait`: High-resolution transparent driver cutout.
- `team`: Object containing team `id`, `name`, and canonical `color` (ARGB hex, e.g. `"0xFFE8002D"`).
- `season_2026_stats`: 16 granular season metrics (points, podiums, wins, poles, fastest laps, DNFs, average grid position, etc.).
- `career_stats`: 8 lifetime statistics (Grand Prix entered, World Championships, career podiums, career points).

---

## 3. Teams (`/v2/teams.json`)

All 11 constructors competing in the 2026 FIA Formula 1 World Championship.

### Key Fields per Constructor
- `id`: Constructor slug (e.g. `"ferrari"`).
- `name`: Official constructor name (`"Ferrari"`).
- `team_color`: Official ARGB primary color code (e.g. `"0xFFE8002D"`).
- `team_logo`: Transparent white vector logo optimized for dark mode UIs.
- `team_car`: High-resolution side cutout of the 2026 challenger.
- `technical_specs`: Power unit manufacturer, chassis designation, team principal, technical director, and factory headquarters.
- `drivers`: Array of driver summaries assigned to this constructor.

---

## 4. Standings (`/v2/standings.json`)

Dual championship tables with complete round-by-round points accumulation history.

### Structure
- `drivers`: Array sorted by current championship ranking P1 through P23. Each entry includes:
  - `position`, `points`, `wins`, `podiums`
  - `round_by_round`: Map of round numbers to points scored in each Grand Prix weekend (`{"1": 25, "2": 18, ...}`).
- `constructors`: Array sorted by current team championship ranking P1 through P11 with points progression.

---

## 5. Calendar (`/v2/calendar.json`)

Complete 24-event schedule of the 2026 World Championship.

### Key Fields per Event
- `round`: Integer round number (1 to 24).
- `race_name`: Official Grand Prix title (e.g. `"Singapore Grand Prix"`).
- `circuit_name`: Track venue name.
- `circuit_map`: Transparent vector circuit layout diagram.
- `circuit_length_km`: Length in kilometers.
- `lap_record`: Lap time, driver, and year recorded.
- `is_sprint`: Boolean indicating whether the weekend follows the Sprint format.
- `sessions`: Exact UTC timestamps for all practice, qualifying, sprint, and grand prix sessions.

---

## 6. Active Weekend Results (`/v2/results/latest.json`)

Classifications of the active or most recently completed Grand Prix weekend across all 5 sessions:
- `sessions.practice_1`: Practice 1 classification table (positions 1 through 22, lap times, gaps, laps run).
- `sessions.practice_2` / `practice_3`: FP2 and FP3 classifications (or null on Sprint weekends).
- `sessions.sprint_qualifying` & `sessions.sprint_race`: Sprint classifications (where applicable).
- `sessions.qualifying`: Q1, Q2, and Q3 knockout lap times and final grid positions.
- `sessions.race`: Final official Grand Prix classification with finish status (`"1:31:24.412"`, `"+5.214s"`, or `"DNF"`), points awarded, and fastest lap bonuses.

---

## 7. Historical Rounds (`/v2/results/round_{N}.json`)

Non-destructive historical archive. Fetch any specific round by replacing `{N}` with the round number:
- `GET /v2/results/round_1.json` (Bahrain GP)
- `GET /v2/results/round_14.json` (Spanish GP at Madrid)
- `GET /v2/results/round_17.json` (Singapore GP)

---

## 8. Live Telemetry (`/v2/live.json`)

Lightweight polling endpoint updated during live race sessions:
```json
{
  "is_live": false,
  "race_name": "United States Grand Prix",
  "session": "Race",
  "flag": "GREEN",
  "leader": "Max Verstappen",
  "drivers_on_track": 22,
  "last_updated": "2026-10-14T00:54:05Z"
}
```

---

## 🚀 Client Integration Examples

### JavaScript / TypeScript
```javascript
const response = await fetch("https://yashajagiya.github.io/Taras/v2/overview.json");
const data = await response.json();
console.log(`Leader: ${data.championship_leader.driver.name}`);
```

### Kotlin (Android / OkHttp)
```kotlin
val client = OkHttpClient()
val request = Request.Builder()
    .url("https://yashajagiya.github.io/Taras/v2/drivers.json")
    .build()

val response = client.newCall(request).execute()
val driversJson = response.body?.string()
```

### Python
```python
import requests
data = requests.get("https://yashajagiya.github.io/Taras/v2/standings.json").json()
print("Top 3 Drivers:")
for driver in data["drivers"][:3]:
    print(f"P{driver['position']}: {driver['name']} - {driver['points']} pts")
```
