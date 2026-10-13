# 📱 Mobile & Web App Integration Guide — Taras F1 Static REST API

Welcome to the **Taras F1 API** developer guide! This document explains how to seamlessly integrate the 100% static, edge-cached Formula 1 REST API into your Android, iOS, Flutter, React Native, or Web applications with zero API keys and zero backend infrastructure.

---

## 🌐 1. Architecture & Base URLs

All endpoints are pre-rendered, strictly-typed static JSON files hosted directly on **GitHub Pages Global Edge CDN** (Fastly / Cloudflare).

| Metric | Specification |
| :--- | :--- |
| **V2 Base CDN URL** | `https://yashajagiya.github.io/TarasAPIstatic/v2/` |
| **V1 (Legacy) Base URL** | `https://yashajagiya.github.io/TarasAPIstatic/v1/` |
| **Authentication** | None required (100% Public & Open) |
| **Rate Limits** | Edge CDN cached (Unlimited requests) |
| **Payload Format** | Standard UTF-8 JSON |
| **Latency** | ~20ms – 50ms worldwide |

---

## 🏎️ 2. Core REST Endpoints & Screen Mappings

### 2.1 Home Screen in 1 Single Request: `GET /v2/overview.json`
Provides everything needed to render an authentic Formula 1 home feed without multiple round-trips:
- **Championship Leaders:** Current P1 driver and P1 constructor with team hex colors and portrait URLs.
- **Next Event:** Upcoming Grand Prix, circuit name, country, and UTC session timetable for countdown clocks.
- **Latest Race:** Most recent Grand Prix winner, circuit details, and the full 3-driver podium.

```bash
curl -X GET "https://yashajagiya.github.io/TarasAPIstatic/v2/overview.json"
```

### 2.2 All 23 Drivers & Encyclopedia: `GET /v2/drivers.json`
Returns all 23 active drivers sorted by championship standings:
- **Identifiers:** `id`, `number`, `code`, `name`, `first_name`, `last_name`, `nationality`.
- **Team Info:** `team.name`, `team.color_argb`, `team.color_hex`, `team.accessible_color`.
- **Images:** Official high-res headshot portrait (`images.portrait`) and driver number emblem (`images.number_logo`).
- **Stats:** 16 season metrics (`season_2026`) and 8 career metrics (`career_stats`).
- **Dossier:** Multi-paragraph official biographies and quotes.

### 2.3 All 11 Constructors & 2026 Cars: `GET /v2/teams.json`
Returns all 11 Formula 1 constructors:
- **Visuals:** High-resolution 2400px car renders (`images.car`) and transparent white monochrome vector logos (`images.logo`).
- **Specs:** Chassis model, power unit supplier, team principal, technical director, headquarters.
- **Roster:** Current active driver IDs.

### 2.4 Championship Leaderboards: `GET /v2/standings.json`
- **Driver Championship:** Position, points, wins, podiums, and round-by-round points progression array.
- **Constructor Championship:** Standings, team colors, points breakdown per race.

### 2.5 24-Race Season Calendar: `GET /v2/calendar.json`
- **Race Schedule:** All 24 rounds with official event names, dates, and full session timetables (FP1..Race).
- **Circuit Assets:** Official vector track layout maps (`circuit.track_map_url`), circuit length, corners, and lap records.

### 2.6 Race Weekend Classifications: `GET /v2/results/latest.json` & `round_{N}.json`
- **Latest Active Weekend:** `GET /v2/results/latest.json`
- **Archived Historical Rounds:** `GET /v2/results/round_1.json` through `round_18.json`
- **Sessions included:**
  - `practice_1`, `practice_2`, `practice_3` (Lap times, gaps, lap counts)
  - `qualifying` (Q1, Q2, Q3 elimination lap times, positions, laps)
  - `sprint_qualifying` & `sprint_race` (For Sprint weekends)
  - `race` (Finishing order, total race time or status, championship points awarded)

---

## 💻 3. Code Integration Examples

### 3.1 Android (Kotlin + OkHttp3 + Kotlinx Serialization)

```kotlin
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request

@Serializable
data class F1Overview(
    val season: Int,
    val championship_leader: ChampionshipLeader,
    val next_event: NextEvent,
    val latest_race: LatestRace
)

@Serializable
data class ChampionshipLeader(
    val driver: LeaderDriver,
    val team: LeaderTeam
)

@Serializable
data class LeaderDriver(val name: String, val points: Double, val image: String?)
@Serializable
data class LeaderTeam(val name: String, val points: Double, val logo: String?)
@Serializable
data class NextEvent(val race_name: String, val circuit_name: String, val country: String)
@Serializable
data class LatestRace(val race_name: String, val winner: String?, val podium: List<PodiumDriver>)
@Serializable
data class PodiumDriver(val position: Int, val driver_name: String, val team: String)

class TarasF1ApiClient(
    private val client: OkHttpClient = OkHttpClient(),
    private val json: Json = Json { ignoreUnknownKeys = true }
) {
    private val baseUrl = "https://yashajagiya.github.io/TarasAPIstatic/v2"

    fun fetchOverview(): F1Overview {
        val request = Request.Builder()
            .url("$baseUrl/overview.json")
            .header("Accept", "application/json")
            .build()

        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IllegalStateException("HTTP ${response.code}")
            val body = response.body?.string() ?: throw IllegalStateException("Empty response")
            return json.decodeFromString(body)
        }
    }
}
```

---

### 3.2 iOS (Swift + URLSession + Decodable)

```swift
import Foundation

struct F1Overview: Codable {
    let season: Int
    let championshipLeader: ChampionshipLeader
    let nextEvent: NextEvent
    let latestRace: LatestRace

    enum CodingKeys: String, CodingKey {
        case season
        case championshipLeader = "championship_leader"
        case nextEvent = "next_event"
        case latestRace = "latest_race"
    }
}

struct ChampionshipLeader: Codable {
    let driver: DriverSummary
    let team: TeamSummary
}

struct DriverSummary: Codable {
    let name: String
    let points: Double
    let image: String?
}

struct TeamSummary: Codable {
    let name: String
    let points: Double
    let logo: String?
}

struct NextEvent: Codable {
    let raceName: String
    let circuitName: String
    let country: String

    enum CodingKeys: String, CodingKey {
        case raceName = "race_name"
        case circuitName = "circuit_name"
        case country
    }
}

struct LatestRace: Codable {
    let raceName: String
    let winner: String?

    enum CodingKeys: String, CodingKey {
        case raceName = "race_name"
        case winner
    }
}

class TarasF1Service {
    static let shared = TarasF1Service()
    private let baseUrl = "https://yashajagiya.github.io/TarasAPIstatic/v2"

    func fetchOverview() async throws -> F1Overview {
        guard let url = URL(string: "\(baseUrl)/overview.json") else {
            throw URLError(.badURL)
        }
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(F1Overview.self, from: data)
    }
}
```

---

### 3.3 Flutter / Dart

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class TarasF1Api {
  static const String baseUrl = 'https://yashajagiya.github.io/TarasAPIstatic/v2';

  static Future<Map<String, dynamic>> getOverview() async {
    final response = await http.get(Uri.parse('$baseUrl/overview.json'));
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      throw Exception('Failed to load overview: ${response.statusCode}');
    }
  }

  static Future<List<dynamic>> getDrivers() async {
    final response = await http.get(Uri.parse('$baseUrl/drivers.json'));
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as List<dynamic>;
    } else {
      throw Exception('Failed to load drivers: ${response.statusCode}');
    }
  }

  static Future<Map<String, dynamic>> getLatestResults() async {
    final response = await http.get(Uri.parse('$baseUrl/results/latest.json'));
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      throw Exception('Failed to load results: ${response.statusCode}');
    }
  }
}
```

---

### 3.4 React Native / TypeScript

```typescript
import axios from 'axios';

const BASE_URL = 'https://yashajagiya.github.io/TarasAPIstatic/v2';

export interface OverviewResponse {
  season: number;
  championship_leader: {
    driver: { name: string; points: number; image?: string };
    team: { name: string; points: number; logo?: string };
  };
  next_event: {
    round: number;
    race_name: string;
    circuit_name: string;
    country: string;
  };
  latest_race: {
    round: number;
    race_name: string;
    winner?: string;
    podium: Array<{ position: number; driver_name: string; team: string }>;
  };
}

export const fetchF1Overview = async (): Promise<OverviewResponse> => {
  const response = await axios.get<OverviewResponse>(`${BASE_URL}/overview.json`);
  return response.data;
};

export const fetchF1Drivers = async () => {
  const response = await axios.get(`${BASE_URL}/drivers.json`);
  return response.data;
};

export const fetchF1Teams = async () => {
  const response = await axios.get(`${BASE_URL}/teams.json`);
  return response.data;
};
```

---

## 🎨 4. Best Practices for Mobile UI Design

1. **Brand Team Accents:**
   Every driver and team object includes `team.color_argb` (e.g. `0xFFE8002D` for Ferrari) and `team.color_hex` (`#E8002D`). Use these for card borders, gradients, and typography accents.
2. **Accessible Light/Dark Color:**
   Use `team.accessible_color` for high-contrast text and labels over bright or dark backgrounds.
3. **High-DPI Image Caching:**
   - On Android: Use [Coil](https://coil-kt.github.io/coil/) or [Glide](https://github.com/bumptech/glide) with memory and disk caching.
   - On iOS: Use [Kingfisher](https://github.com/onevcat/Kingfisher) to stream portraits and car renders.
4. **Local Fallback:**
   Because all endpoints are static JSON, you can bundle a pre-downloaded copy of `overview.json`, `drivers.json`, and `teams.json` directly into your app's `assets/` folder for 100% offline first-launch experience.
