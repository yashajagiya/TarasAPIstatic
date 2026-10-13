# Formula 1 & ESPN Hidden APIs Documentation

This document outlines the internal, undocumented APIs and data sources discovered that power ESPN's F1 coverage and Formula 1's live timing/blog systems.

> [!WARNING]
> **Unofficial APIs:** These endpoints are not officially supported for public use. They do not require API keys, but they can be changed, deprecated, or rate-limited without warning. Implement error handling and caching if using them in a project.

---

## 1. ESPN F1 APIs

ESPN uses a core internal API to power its website and mobile app (the `site.api.espn.com` infrastructure). All responses are in JSON format.

### A. Scoreboard (Race Calendar & Live Status)
- **Endpoint:** `GET https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard`
- **Description:** Returns the complete season calendar, live race status, and top-level results.
- **Key Data Provided:**
  - Season details (start date, end date).
  - List of all races (e.g., "Belgian Grand Prix").
  - Current status of races (pre-race, live, post-race).
  - High-level podium results for completed races.

### B. Summary (Gamepackage / Specific Race Data)
- **Endpoint:** `GET https://site.api.espn.com/apis/site/v2/sports/racing/f1/summary`
- **Query Parameters:**
  - `event` (Required): The unique numerical ID for the race event (can be found via the Scoreboard endpoint). Example: `?event=600057439`
- **Description:** This is the "Gamepackage" endpoint that populates the detailed view of a single race weekend.
- **Key Data Provided:**
  - Full race classification (finishing order, times, grid position).
  - Results for Practice (FP1, FP2, FP3) and Qualifying sessions.
  - Driver points awarded for the specific race.
  - Laps completed and fastest lap details.

### C. Championship Standings
- **Endpoint:** `GET https://site.api.espn.com/apis/v2/sports/racing/f1/standings`
- **Description:** Returns the current standings for the F1 World Championship.
- **Key Data Provided:**
  - **Driver Standings:** Rank, driver name, team, total points, and wins.
  - **Constructor Standings:** Rank, team name, total points, and wins.

### D. F1 News Feed
- **Endpoint:** `GET https://site.api.espn.com/apis/site/v2/sports/racing/f1/news`
- **Description:** Returns a feed of recent editorial articles, headlines, and imagery from ESPN's F1 news desk.

---

## 2. Formula 1 Official Live Timing Assets

Formula1.com hosts its live timing audio (like team radio clips) on an open static file server. While not a REST API that returns JSON, it is a predictable URL structure you can use to programmatically fetch audio.

### A. Team Radio Audio Files
- **Endpoint Pattern:** `GET https://livetiming.formula1.com/static/{YEAR}/{RACE_FOLDER}/{SESSION_FOLDER}/TeamRadio/{FILENAME}.mp3`
- **Description:** Serves raw `.mp3` files of team radio communications broadcasted during sessions.
- **Path Breakdown:**
  - `{YEAR}`: The championship year (e.g., `2026`).
  - `{RACE_FOLDER}`: Date and race name (e.g., `2026-07-19_Belgian_Grand_Prix`).
  - `{SESSION_FOLDER}`: Date and session name (e.g., `2026-07-17_Practice_1`).
  - `{FILENAME}`: Typically formatted as `{DRIVER_TLA}_{CAR_NUMBER}_{DATE}_{TIME}.mp3` (e.g., `ANT_12_20260717_134817.mp3`).

---

## 3. Monterosa Interaction Cloud (F1 Live Blog)

Formula 1 uses a third-party fan engagement platform called Monterosa to run their live editorial blogs and interactive features on Formula1.com.

### A. Monterosa CDN & Live Feed
- **Base URL:** `https://cdn.monterosa.cloud/...`
- **Description:** This infrastructure delivers the real-time text commentary, polls, and images (like the tyre icons you saw). 
- **How to interact:** Because the specific live-blog text API endpoint is generated dynamically per race, you cannot hit a static URL. To intercept this JSON data during a race:
  1. Open Formula1.com Live Blog during a session.
  2. Open browser Developer Tools -> Network tab.
  3. Filter by `Fetch/XHR`.
  4. Look for recurring requests to a Monterosa endpoint containing the live commentary feed.
