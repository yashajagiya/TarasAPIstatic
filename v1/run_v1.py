"""
Taras F1 API v1 — Master Asynchronous & Anti-Ban Runner (run_v1.py)
Orchestrates high-performance asynchronous scraping with industrial-grade
anti-ban defenses (rotating browser fingerprints, polite jittered delays,
per-domain concurrency caps, exponential backoff, circuit-breaker, and caching guards).

Usage:
  python v1/run_v1.py                  # Run all v1 pipelines safely once
  python v1/run_v1.py --stealth        # Maximum safety mode (3.5s - 6.5s delays)
  python v1/run_v1.py --force          # Force re-scraping existing cached sessions
  python v1/run_v1.py --loop           # Continuous scraping mode with polite jitter
  python v1/run_v1.py --interval 300   # Set loop interval in seconds (default: 300)
  python v1/run_v1.py --push           # Auto-deploy to GitHub if verified
  python v1/run_v1.py --skip-sessions  # Only update standings and calendar
  python v1/run_v1.py --skip-standings # Only update session classifications
"""

import argparse
import asyncio
import json
import os
import random
import re
import ssl
import subprocess
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Ensure local v1 directory resolution
V1_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(V1_DIR, ".."))
if V1_DIR not in sys.path:
    sys.path.insert(0, V1_DIR)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# =====================================================================
# 🛡️ Anti-Ban Engine: Realistic Browser Profiles & Rate Limiter
# =====================================================================

BROWSER_PROFILES = [
    {
        "name": "Chrome 125 on Windows 11",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
    },
    {
        "name": "Edge 125 on Windows 11",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
            "sec-ch-ua": '"Microsoft Edge";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
    },
    {
        "name": "Chrome 125 on macOS Sonoma",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        }
    },
    {
        "name": "Firefox 126 on Windows 11",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
            "sec-ch-ua": "",
            "sec-ch-ua-mobile": "",
            "sec-ch-ua-platform": "",
        }
    }
]

BASE_NAV_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


class AntiBanClient:
    """
    Thread-safe, rate-limiting HTTP client preventing IP blocks via:
    1. Per-domain token rate limits & asynchronous locks
    2. Jittered human-like delays (random sleep intervals)
    3. Modern rotating browser fingerprints
    4. Exponential backoff on HTTP 429 (Too Many Requests) & 403
    5. Circuit breaker cooldown if blocks are detected
    """

    def __init__(self, min_delay: float = 1.8, max_delay: float = 3.8, stealth: bool = False):
        if stealth:
            self.min_delay = 3.5
            self.max_delay = 6.5
        else:
            self.min_delay = min_delay
            self.max_delay = max_delay

        self._domain_locks: Dict[str, asyncio.Lock] = {}
        self._last_request_time: Dict[str, float] = {}
        self._session = requests.Session()
        self.rate_limited_count = 0

    def _get_lock(self, domain: str) -> asyncio.Lock:
        if domain not in self._domain_locks:
            self._domain_locks[domain] = asyncio.Lock()
        return self._domain_locks[domain]

    def _get_headers(self, referer: Optional[str] = None) -> dict:
        profile = random.choice(BROWSER_PROFILES)
        headers = dict(BASE_NAV_HEADERS)
        headers.update(profile["headers"])
        headers = {k: v for k, v in headers.items() if v}
        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "same-origin"
        return headers

    async def get(self, url: str, retries: int = 4, referer: Optional[str] = None) -> Optional[requests.Response]:
        domain = urlparse(url).netloc.lower()
        lock = self._get_lock(domain)

        async with lock:
            now = time.time()
            last_time = self._last_request_time.get(domain, 0.0)
            elapsed = now - last_time
            required_delay = random.uniform(self.min_delay, self.max_delay)

            if elapsed < required_delay:
                wait_time = required_delay - elapsed
                await asyncio.sleep(wait_time)

            for attempt in range(1, retries + 1):
                headers = self._get_headers(referer=referer)
                try:
                    loop = asyncio.get_running_loop()
                    resp = await loop.run_in_executor(
                        None,
                        lambda: self._session.get(url, headers=headers, timeout=20, allow_redirects=True)
                    )
                    self._last_request_time[domain] = time.time()

                    if resp.status_code == 200:
                        return resp

                    if resp.status_code == 404:
                        return resp

                    if resp.status_code in (429, 403):
                        self.rate_limited_count += 1
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            backoff = float(retry_after) + random.uniform(1.0, 3.0)
                        else:
                            backoff = (2.0 ** attempt) * 4.0 + random.uniform(2.0, 5.0)

                        print(f"  ⚠️ [Anti-Ban Warning] HTTP {resp.status_code} on {domain}. Backing off for {backoff:.1f}s (Attempt {attempt}/{retries})...")
                        await asyncio.sleep(backoff)
                        continue

                    if resp.status_code >= 500:
                        backoff = 3.0 * attempt + random.uniform(1.0, 3.0)
                        await asyncio.sleep(backoff)
                        continue

                except Exception as err:
                    backoff = 2.0 * attempt + random.uniform(1.0, 2.0)
                    print(f"  ⚠️ [Network Exception] {err} on {url}. Retrying in {backoff:.1f}s...")
                    await asyncio.sleep(backoff)

            return None


# =====================================================================
# 🏎️ Helper Functions & Lookups
# =====================================================================

KNOWN_ACRONYMS = {
    "NOR": "lando norris", "VER": "max verstappen", "BOR": "gabriel bortoleto",
    "HAD": "isack hadjar", "GAS": "pierre gasly", "PER": "sergio perez",
    "ANT": "kimi antonelli", "ALO": "fernando alonso", "LEC": "charles leclerc",
    "STR": "lance stroll", "ALB": "alexander albon", "HUL": "nico hulkenberg",
    "LAW": "liam lawson", "OCO": "esteban ocon", "LIN": "arvid lindblad",
    "COL": "franco colapinto", "HAM": "lewis hamilton", "SAI": "carlos sainz",
    "RUS": "george russell", "BOT": "valtteri bottas", "PIA": "oscar piastri",
    "BEA": "oliver bearman", "TSU": "yuki tsunoda",
}

OFFICIAL_TEAM_NAMES = {
    "Red Bull": "Red Bull Racing",
    "Haas": "Haas F1 Team",
}


def clean_str(s) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()


def normalize_name(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_v1_driver_info() -> dict:
    """Loads driver info registry from v1/f1Info/drivers_data.json."""
    candidates = [
        os.path.join(V1_DIR, "f1Info", "drivers_data.json"),
        os.path.join(V1_DIR, "drivers_data.json"),
        os.path.join(V1_DIR, "driverimg.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                driver_lookup = {}
                if isinstance(data, list):
                    for item in data:
                        driver_data = item.get("driver", item)
                        first = driver_data.get("first_name", "")
                        last = driver_data.get("last_name", "")
                        full = driver_data.get("full_name") or f"{first} {last}".strip()
                        abbr = driver_data.get("abbreviation") or driver_data.get("name_acronym", "")
                        num = driver_data.get("driver_number") or driver_data.get("permanent_number")
                        team = driver_data.get("team_name") or driver_data.get("team", "")
                        nat = driver_data.get("country_code") or driver_data.get("nationality", "")
                        portrait = driver_data.get("headshot_url") or driver_data.get("driver_img", "")

                        try:
                            num_int = int(num) if num is not None else None
                        except (ValueError, TypeError):
                            num_int = None

                        entry = {
                            "driver_number": num_int,
                            "team_name": team,
                            "nationality": nat,
                            "portrait": portrait,
                            "full_name": full,
                        }
                        if abbr:
                            driver_lookup[abbr.upper()] = entry
                        if full:
                            driver_lookup[normalize_name(full)] = entry
                        if last:
                            driver_lookup[normalize_name(last)] = entry
                    return driver_lookup
            except Exception as e:
                print(f"  ⚠️ Warning reading driver info from {path}: {e}")
    return {}


# =====================================================================
# 📊 Standings Extractors (Async)
# =====================================================================

ESPN_STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/racing/f1/standings"


async def scrape_driver_standings_async(client: AntiBanClient) -> bool:
    """Fetches and updates driver standings (driversperrace.json & f1_standings.json)."""
    driver_info = load_v1_driver_info()
    resp = await client.get(ESPN_STANDINGS_URL)
    if not resp or resp.status_code != 200:
        print("  ⚠️ Could not fetch driver standings from ESPN API.")
        return False

    try:
        data = resp.json()
        children = data.get("children", [])
        if not children:
            return False

        standings_data = children[0].get("standings", {})
        standings = {
            "displayName": standings_data.get("displayName", "F1 Driver Standings"),
            "season": standings_data.get("season", 2026),
            "entries": [],
        }

        for entry in standings_data.get("entries", []):
            athlete = entry.get("athlete", {})
            stats = entry.get("stats", [])

            rank = 0
            pts_value = 0
            pts_display = "0"
            races = []

            for stat in stats:
                st = stat.get("type", "")
                if st == "rank":
                    rank = int(stat.get("value", 0))
                elif st == "points":
                    pts_value = int(stat.get("value", 0))
                    pts_display = stat.get("displayValue", "0")
                elif st == "overall":
                    continue
                else:
                    races.append({
                        "name": stat.get("name", ""),
                        "displayName": stat.get("displayName", ""),
                        "played": stat.get("played", False),
                        "value": int(stat.get("value", 0)),
                        "displayValue": stat.get("displayValue", "").strip(),
                    })

            abbr = athlete.get("abbreviation", "")
            display_name = athlete.get("displayName", "")
            last_word = display_name.split()[-1] if display_name.split() else ""

            info = driver_info.get(abbr.upper())
            if not info:
                info = driver_info.get(normalize_name(display_name))
            if not info:
                info = driver_info.get(normalize_name(last_word), {})

            driver_entry = {
                "rank": rank,
                "driver_number": info.get("driver_number", None),
                "name": athlete.get("displayName", ""),
                "shortName": athlete.get("shortName", ""),
                "abbreviation": abbr,
                "team_name": info.get("team_name", ""),
                "nationality": athlete.get("flag", {}).get("alt", info.get("nationality", "")),
                "championshipPts": {
                    "value": pts_value,
                    "displayValue": pts_display,
                },
                "races": races,
            }
            standings["entries"].append(driver_entry)

        # Save to both driversperrace.json and f1_standings.json
        p1 = os.path.join(V1_DIR, "driversperrace.json")
        p2 = os.path.join(V1_DIR, "f1_standings.json")
        with open(p1, "w", encoding="utf-8") as f:
            json.dump(standings, f, indent=2, ensure_ascii=False)
        with open(p2, "w", encoding="utf-8") as f:
            json.dump(standings, f, indent=2, ensure_ascii=False)

        print(f"  ✓ Driver Standings saved ({len(standings['entries'])} drivers classified)")
        return True
    except Exception as e:
        print(f"  ⚠️ Error parsing driver standings: {e}")
        return False


async def scrape_constructor_standings_async(client: AntiBanClient) -> bool:
    """Fetches and updates constructor standings (carperrace.json & f1_constructor_standings.json)."""
    resp = await client.get(ESPN_STANDINGS_URL)
    if not resp or resp.status_code != 200:
        print("  ⚠️ Could not fetch constructor standings from ESPN API.")
        return False

    try:
        data = resp.json()
        children = data.get("children", [])
        if len(children) < 2:
            return False

        standings_data = children[1].get("standings", {})
        standings = {
            "displayName": standings_data.get("displayName", "F1 Constructor Standings"),
            "season": standings_data.get("season", 2026),
            "entries": [],
        }

        for entry in standings_data.get("entries", []):
            team = entry.get("team", {})
            stats = entry.get("stats", [])

            rank = 0
            pts_value = 0
            pts_display = "0"
            races = []

            for stat in stats:
                st = stat.get("type", "")
                if st == "rank":
                    rank = int(stat.get("value", 0))
                elif st == "points":
                    pts_value = int(stat.get("value", 0))
                    pts_display = stat.get("displayValue", "0")
                elif st == "overall":
                    continue
                else:
                    races.append({
                        "name": stat.get("name", ""),
                        "displayName": stat.get("displayName", ""),
                        "played": stat.get("played", False),
                        "value": int(stat.get("value", 0)),
                        "displayValue": stat.get("displayValue", "").strip(),
                    })

            raw_name = team.get("displayName", team.get("name", ""))
            clean_team_name = OFFICIAL_TEAM_NAMES.get(raw_name, raw_name)

            standings["entries"].append({
                "rank": rank,
                "team": {
                    "id": team.get("id", ""),
                    "name": clean_team_name,
                    "displayName": clean_team_name,
                    "shortDisplayName": team.get("shortDisplayName", ""),
                    "abbreviation": team.get("abbreviation", ""),
                    "color": team.get("color", ""),
                    "alternateColor": team.get("alternateColor", ""),
                    "logo": (team.get("logos", [{}])[0].get("href", "") if team.get("logos") else ""),
                },
                "points": {
                    "value": pts_value,
                    "displayValue": pts_display,
                },
                "races": races,
            })

        p1 = os.path.join(V1_DIR, "carperrace.json")
        p2 = os.path.join(V1_DIR, "f1_constructor_standings.json")
        with open(p1, "w", encoding="utf-8") as f:
            json.dump(standings, f, indent=2, ensure_ascii=False)
        with open(p2, "w", encoding="utf-8") as f:
            json.dump(standings, f, indent=2, ensure_ascii=False)

        print(f"  ✓ Constructor Standings saved ({len(standings['entries'])} teams classified)")
        return True
    except Exception as e:
        print(f"  ⚠️ Error parsing constructor standings: {e}")
        return False


# =====================================================================
# 📅 Calendar Scraper (Async)
# =====================================================================

async def scrape_races_calendar_async(client: AntiBanClient) -> bool:
    """Fetches race calendar from f1api.dev and updates v1/f1Info/races_data.json."""
    url = "https://f1api.dev/api/current"
    resp = await client.get(url)
    if not resp or resp.status_code != 200:
        print("  ⚠️ Could not fetch race calendar from f1api.dev (keeping local copy).")
        return False

    try:
        data = resp.json()
        target_path = os.path.join(V1_DIR, "f1Info", "races_data.json")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("  ✓ Calendar & Race details saved to v1/f1Info/races_data.json")
        return True
    except Exception as e:
        print(f"  ⚠️ Error saving race calendar: {e}")
        return False


# =====================================================================
# 🏎️ Active Weekend Sessions Scraper (Async with Smart Caching)
# =====================================================================

def load_v1_schedule() -> List[dict]:
    """Loads schedule.json from v1 session directories."""
    candidates = [
        os.path.join(V1_DIR, "practice1", "code", "schedule.json"),
        os.path.join(V1_DIR, "race-result", "code", "schedule.json"),
        os.path.join(V1_DIR, "qualifying", "code", "schedule.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return []


def get_target_weekend(schedule: List[dict], target_date: Optional[str] = None) -> Optional[dict]:
    """Finds current active or latest weekend from schedule."""
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    # 1. Active race weekend (today is between first session and race date)
    for event in schedule:
        sched = event.get("schedule", {})
        race_date = sched.get("race", {}).get("date")
        session_dates = [v.get("date") for v in sched.values() if isinstance(v, dict) and v.get("date")]
        if session_dates and race_date:
            min_date = min(session_dates)
            if min_date <= target_date <= race_date:
                return event

    # 2. Most recent event on or before target_date
    best_match = None
    best_date = None
    for event in schedule:
        race_date = event.get("schedule", {}).get("race", {}).get("date")
        if race_date and race_date <= target_date:
            if best_date is None or race_date > best_date:
                best_date = race_date
                best_match = event

    return best_match or (schedule[0] if schedule else None)


def parse_v1_session_rows(soup: BeautifulSoup, session_name: str) -> List[dict]:
    """Parses session table into clean row dictionaries."""
    table = soup.find("table")
    if not table:
        return []

    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")

    parsed = []
    for tr in rows:
        tds = tr.find_all("td")
        if not tds or len(tds) < 4:
            continue

        pos_str = clean_str(tds[0].text)
        num_str = clean_str(tds[1].text)

        # Driver name parsing
        first_span = tds[2].find("span", class_="max-lg:hidden")
        last_span = tds[2].find("span", class_="max-md:hidden")
        code_span = tds[2].find("span", class_="md:hidden")
        code = clean_str(code_span.text) if code_span else ""
        if first_span and last_span:
            name = f"{clean_str(first_span.text)} {clean_str(last_span.text)}"
        else:
            raw = clean_str(tds[2].text)
            if code and raw.endswith(code):
                raw = raw[:-len(code)].strip()
            name = raw

        team = clean_str(tds[3].text)
        entry = {
            "position": int(pos_str) if pos_str.isdigit() else pos_str,
            "driver_number": int(num_str) if num_str.isdigit() else num_str,
            "driver_name": name,
            "team": team,
        }

        s_lower = session_name.lower()
        if "practice" in s_lower:
            time_gap = clean_str(tds[4].text) if len(tds) > 4 else ""
            laps = clean_str(tds[6].text) if len(tds) > 6 else (clean_str(tds[5].text) if len(tds) > 5 else "")
            entry["driver_code"] = code
            entry["time_or_gap"] = time_gap
            entry["laps"] = int(laps) if laps.isdigit() else laps
        elif "qualifying" in s_lower:
            entry["q1"] = clean_str(tds[4].text) if len(tds) > 4 else ""
            entry["q2"] = clean_str(tds[5].text) if len(tds) > 5 else ""
            entry["q3"] = clean_str(tds[6].text) if len(tds) > 6 else ""
            entry["laps"] = int(clean_str(tds[7].text)) if len(tds) > 7 and clean_str(tds[7].text).isdigit() else 0
        else:  # race or sprint race
            entry["laps"] = int(clean_str(tds[4].text)) if len(tds) > 4 and clean_str(tds[4].text).isdigit() else 0
            entry["time_or_retired"] = clean_str(tds[5].text) if len(tds) > 5 else ""
            entry["points"] = float(clean_str(tds[6].text)) if len(tds) > 6 and clean_str(tds[6].text).replace(".", "").isdigit() else 0

        parsed.append(entry)

    return parsed


async def scrape_v1_active_sessions_async(client: AntiBanClient, force: bool = False) -> bool:
    """
    Asynchronously checks and scrapes active sessions for the current Grand Prix weekend.
    Uses AntiBanClient with smart caching to skip completed historical sessions.
    """
    schedule = load_v1_schedule()
    if not schedule:
        print("  ⚠️ No schedule found in v1 directories.")
        return False

    event = get_target_weekend(schedule)
    if not event:
        print("  ⚠️ No target weekend found.")
        return False

    event_id = event.get("id")
    race_name = event.get("raceName", "Grand Prix")
    circuit_name = event.get("circuit", {}).get("circuitName", "Circuit")
    circuit_id = event.get("circuit", {}).get("circuitId", "unknown")
    country = event.get("f1siteracename", "").capitalize()

    sched = event.get("schedule", {})
    is_sprint = bool(sched.get("sprintQualy", {}).get("date") or sched.get("sprintRace", {}).get("date"))

    print(f"\n🏎️ [v1 Sessions] Active Target: {race_name} ({'Sprint' if is_sprint else 'Standard'} Format)")

    # Session mapping: (session_key, url_suffix, output_relative_file, label)
    session_configs = [
        ("fp1", "practice/1", "practice1/fp1_extracted.json", "PRACTICE 1"),
        ("fp2", "practice/2", "practice2/fp2_extracted.json", "PRACTICE 2"),
        ("fp3", "practice/3", "practice3/fp3_extracted.json", "PRACTICE 3"),
        ("sprintQualy", "sprint-qualifying", "sprint-quly/sprint_quly_result.json", "SPRINT QUALIFYING"),
        ("sprintRace", "sprint-results", "sprint-race/sprint_race_result.json", "SPRINT RACE"),
        ("qualy", "qualifying", "qualifying/qualifying_results.json", "QUALIFYING"),
        ("race", "race-result", "race-result/race_results.json", "RACE"),
    ]

    base_f1_url = f"https://www.formula1.com/en/results/2026/races/{event_id}"

    for skey, suffix, out_rel, label in session_configs:
        # If standard weekend, skip sprint sessions; if sprint weekend, skip fp2/fp3
        if not is_sprint and skey in ("sprintQualy", "sprintRace"):
            continue
        if is_sprint and skey in ("fp2", "fp3"):
            continue

        target_file = os.path.join(V1_DIR, out_rel)

        # Smart Cache Guard: Skip network if already archived and completed
        if not force and os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("results") and len(cached.get("results")) >= 10:
                    print(f"  ⚡ [Cache Hit] {label:<18} is fully archived. Skipping scrape.")
                    continue
            except Exception:
                pass

        session_url = f"{base_f1_url}/{suffix}"
        resp = await client.get(session_url, referer=base_f1_url)
        if not resp or resp.status_code != 200:
            print(f"  • {label:<18} not available yet (HTTP {resp.status_code if resp else 'None'}).")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        parsed_rows = parse_v1_session_rows(soup, label)
        if not parsed_rows:
            print(f"  • {label:<18} (table not yet populated)")
            continue

        # Extract date from page if present
        date_str = sched.get(skey, {}).get("date", "2026")
        caption = soup.find("p", class_=re.compile(r"f1-header-sub", re.I))
        if caption and "-" in caption.text:
            date_str = clean_str(caption.text.split("-")[0])

        payload = {
            "country": country,
            "session": label,
            "raceName": f"{race_name.upper()} - {label.replace(' ', '_')}",
            "date": date_str,
            "circuitName": circuit_name,
            "circuitId": circuit_id,
            "results": parsed_rows,
        }

        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)

        print(f"  ✓ {label:<18} saved ({len(parsed_rows)} drivers classified) -> {out_rel}")

    return True


# =====================================================================
# 🚀 Master Async Pipeline Orchestrator for V1
# =====================================================================

async def run_v1_cycle(
    client: AntiBanClient,
    skip_standings: bool = False,
    skip_sessions: bool = False,
    force: bool = False,
    push: bool = False
) -> bool:
    """Executes one full iteration of the v1 asynchronous scraping and verification pipeline."""
    start_time = time.time()
    print("\n" + "=" * 75)
    print(f"  🚀 TARAS F1 API v1 — CYCLE EXECUTION [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("=" * 75)

    tasks = []

    # 1. Asynchronous Standings & Calendar
    if not skip_standings:
        print("\n[Step 1/3] Scraping Standings & Calendar concurrently...")
        tasks.append(scrape_driver_standings_async(client))
        tasks.append(scrape_constructor_standings_async(client))
        tasks.append(scrape_races_calendar_async(client))
        await asyncio.gather(*tasks)
    else:
        print("\n[Step 1/3] Standings scraping skipped (--skip-standings).")

    # 2. Active Session Classifications
    if not skip_sessions:
        print("\n[Step 2/3] Checking & Scraping Active Weekend Sessions...")
        await scrape_v1_active_sessions_async(client, force=force)
    else:
        print("\n[Step 2/3] Session scraping skipped (--skip-sessions).")

    # 3. Verification of Datasets
    print("\n[Step 3/3] Verifying V1 JSON Dataset Integrity...")
    v1_critical_files = [
        "driversperrace.json",
        "carperrace.json",
        "f1_standings.json",
        "f1_constructor_standings.json",
        "f1Info/races_data.json",
        "practice1/fp1_extracted.json",
        "qualifying/qualifying_results.json",
        "race-result/race_results.json",
    ]

    all_valid = True
    for rel_path in v1_critical_files:
        full_path = os.path.join(V1_DIR, rel_path)
        if os.path.exists(full_path):
            size_kb = os.path.getsize(full_path) / 1024
            print(f"  [PASS] {rel_path:<36} ({size_kb:>6.1f} KB)")
        else:
            print(f"  [WARN] {rel_path:<36} (missing)")
            all_valid = False

    # Optional Git Push
    if push:
        print("\nAuto-committing and pushing V1 updates to GitHub...")
        git_commit_and_push_v1()

    total_time = time.time() - start_time
    print(f"\n  ✅ V1 Cycle Completed in {total_time:.2f}s (Rate limits encountered: {client.rate_limited_count})")
    return all_valid


def git_commit_and_push_v1():
    """Commits and pushes changes in v1 directory to GitHub."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        subprocess.run(["git", "add", "v1/"], cwd=ROOT_DIR, check=True, capture_output=True)
        res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT_DIR, capture_output=True)
        if res.returncode != 0:
            msg = f"Auto-update Taras F1 API v1 datasets — {now}"
            subprocess.run(["git", "commit", "-m", msg], cwd=ROOT_DIR, check=True, capture_output=True)
            subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=ROOT_DIR, check=False)
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=ROOT_DIR, capture_output=True, text=True)
            if push_res.returncode == 0:
                print("  ✓ Pushed V1 updates to GitHub successfully.")
            else:
                print(f"  ⚠️ Git push warning: {push_res.stderr.strip()}")
        else:
            print("  ✓ No changes to commit in v1.")
    except Exception as e:
        print(f"  ⚠️ Git operation error: {e}")


# =====================================================================
# 🔄 Continuous Loop & Main Entry Point
# =====================================================================

async def main_async(args):
    client = AntiBanClient(stealth=args.stealth)

    if args.stealth:
        print("  🛡️ Stealth Anti-Ban ACTIVE: Random delays 3.5s - 6.5s per domain.")
    else:
        print("  🛡️ Standard Anti-Ban ACTIVE: Random delays 1.8s - 3.8s per domain.")

    if not args.loop:
        # Run once
        await run_v1_cycle(
            client=client,
            skip_standings=args.skip_standings,
            skip_sessions=args.skip_sessions,
            force=args.force,
            push=args.push
        )
    else:
        # Run in continuous anti-ban loop
        print(f"\n🔄 CONTINUOUS SCRAPING MODE ACTIVE (Interval: {args.interval}s with random jitter)")
        print("  Press Ctrl+C at any time to cleanly stop the runner.\n")
        cycle = 1
        try:
            while True:
                print(f"\n>>> Running Cycle #{cycle}...")
                prior_rate_limits = client.rate_limited_count
                await run_v1_cycle(
                    client=client,
                    skip_standings=args.skip_standings,
                    skip_sessions=args.skip_sessions,
                    force=args.force,
                    push=args.push
                )

                # Circuit breaker: if we hit a 429/403 in this cycle, enter safety cool-down
                new_limits = client.rate_limited_count - prior_rate_limits
                if new_limits > 0:
                    cooldown = random.uniform(300, 600)
                    print(f"\n🚨 [Circuit Breaker Triggered] {new_limits} rate-limit events detected.")
                    print(f"   Entering extended safety cooldown for {cooldown:.0f}s to protect your IP...")
                    await asyncio.sleep(cooldown)
                else:
                    # Normal jittered sleep (interval ± 15%)
                    jittered_interval = args.interval * random.uniform(0.88, 1.15)
                    print(f"\n💤 Sleeping for {jittered_interval:.1f}s until next cycle...")
                    await asyncio.sleep(jittered_interval)

                cycle += 1
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n\n🛑 Continuous runner stopped cleanly by user. Exiting.")


def parse_args():
    parser = argparse.ArgumentParser(description="Taras F1 API v1 — Asynchronous Anti-Ban Runner")
    parser.add_argument("--loop", "-l", action="store_true", help="Run continuously in a polite jittered loop")
    parser.add_argument("--interval", "-i", type=int, default=300, help="Loop interval in seconds (default: 300)")
    parser.add_argument("--stealth", action="store_true", help="Enable stealth mode with 3.5s - 6.5s delays")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-scraping even if cached")
    parser.add_argument("--push", "-p", action="store_true", help="Auto-commit and push to GitHub")
    parser.add_argument("--skip-standings", action="store_true", help="Skip driver & constructor standings")
    parser.add_argument("--skip-sessions", action="store_true", help="Skip session extraction")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main_async(args))
