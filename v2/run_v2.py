"""
Taras F1 API v2 — Master Asynchronous & Anti-Ban Runner (run_v2.py)
Orchestrates high-performance asynchronous scraping with industrial-grade
anti-ban defenses (rotating browser fingerprints, polite jittered delays,
domain concurrency caps, exponential backoff, and caching guards).

Usage:
  python v2/run_v2.py                  # Auto-detect active weekend & run safely
  python v2/run_v2.py --round 17       # Scrape specific round
  python v2/run_v2.py --skip-scrape    # Build & verify without web requests
  python v2/run_v2.py --stealth        # Maximum safety mode (3.5s - 6.5s delays)
  python v2/run_v2.py --force          # Force re-scraping existing cached rounds
  python v2/run_v2.py                  # Build, verify, and publish to GitHub
  python v2/run_v2.py --no-push        # Build and verify locally only
"""

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Ensure local v2 modules can be resolved
V2_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(V2_DIR, ".."))
if V2_DIR not in sys.path:
    sys.path.insert(0, V2_DIR)

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
    5. Automatic Retry-After header parsing
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
            # Enforce polite jittered delay between requests to the same domain
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
                    # Run requests.get in executor thread to keep event loop free
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

                    # Handle Rate Limits (HTTP 429) & Forbidden (HTTP 403)
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

                    # Server errors (500, 502, 503, 504)
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
# 🏎️ Asynchronous Session Scraper Engine
# =====================================================================

from extract_rounds import F1_WEB_ROUNDS, clean_str, parse_driver_cell, load_drivers_lookup


async def scrape_session_table_async(
    client: AntiBanClient,
    url: str,
    session_name: str,
    referer: Optional[str] = None
) -> Tuple[Optional[List[dict]], str, str, str]:
    """Scrapes a single session table asynchronously with anti-ban protections."""
    resp = await client.get(url, referer=referer)
    if not resp or resp.status_code != 200:
        return None, "", "", ""

    soup = BeautifulSoup(resp.text, "html.parser")
    h1 = soup.find("h1")
    title = clean_str(h1.text) if h1 else ""

    caption = soup.find("p", class_=re.compile(r"f1-header-sub", re.I))
    header_meta = clean_str(caption.text) if caption else ""

    date_text, circuit_text = "", ""
    if "-" in header_meta:
        parts = [p.strip() for p in header_meta.split("-", 1)]
        date_text, circuit_text = parts[0], parts[1]
    else:
        circuit_text = header_meta

    table = soup.find("table")
    if not table:
        return None, title, date_text, circuit_text

    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")
    lookup, _ = load_drivers_lookup()

    parsed_rows = []
    for tr in rows:
        tds = tr.find_all("td")
        if not tds or len(tds) < 4:
            continue

        pos_str = clean_str(tds[0].text)
        num_str = clean_str(tds[1].text)
        name, code = parse_driver_cell(tds[2], lookup_by_num=lookup, fallback_num=num_str)
        team = clean_str(tds[3].text)

        entry = {
            "position": int(pos_str) if pos_str.isdigit() else pos_str,
            "driver_number": int(num_str) if num_str.isdigit() else num_str,
            "driver_name": name,
            "driver_code": code,
            "team": team,
        }

        # Session-specific columns
        s_lower = session_name.lower()
        if "practice" in s_lower:
            time_gap = clean_str(tds[4].text) if len(tds) > 4 else ""
            laps = clean_str(tds[6].text) if len(tds) > 6 else (clean_str(tds[5].text) if len(tds) > 5 else "")
            entry["time_or_gap"] = time_gap
            entry["laps"] = int(laps) if laps.isdigit() else laps
        elif "qualifying" in s_lower or "sprint_qualifying" in s_lower:
            entry["q1"] = clean_str(tds[4].text) if len(tds) > 4 else ""
            entry["q2"] = clean_str(tds[5].text) if len(tds) > 5 else ""
            entry["q3"] = clean_str(tds[6].text) if len(tds) > 6 else ""
            entry["laps"] = int(clean_str(tds[7].text)) if len(tds) > 7 and clean_str(tds[7].text).isdigit() else 0
        else: # race or sprint race
            entry["laps"] = int(clean_str(tds[4].text)) if len(tds) > 4 and clean_str(tds[4].text).isdigit() else 0
            entry["time_or_retired"] = clean_str(tds[5].text) if len(tds) > 5 else ""
            entry["points"] = float(clean_str(tds[6].text)) if len(tds) > 6 and clean_str(tds[6].text).replace(".", "").isdigit() else 0

        parsed_rows.append(entry)

    return parsed_rows, title, date_text, circuit_text


async def scrape_round_async(
    client: AntiBanClient,
    round_num: int,
    force: bool = False
) -> bool:
    """
    Asynchronously scrapes all sessions for a specific Grand Prix weekend
    with smart caching (skips completed historical races unless --force).
    """
    data_dir = os.path.join(V2_DIR, "data")
    sessions_dir = os.path.join(data_dir, "sessions")
    rounds_dir = os.path.join(sessions_dir, "rounds")
    target_cache_candidates = [
        os.path.join(rounds_dir, f"round_{round_num}.json"),
        os.path.join(sessions_dir, f"round_{round_num}.json"),
    ]
    target_cache_file = next((p for p in target_cache_candidates if os.path.exists(p)), target_cache_candidates[0])

    # Anti-Ban Cache Guard: If round is completed and not forced, skip network scraping!
    if not force and os.path.exists(target_cache_file):
        try:
            with open(target_cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("status") == "completed" and cached.get("sessions", {}).get("race"):
                print(f"  ⚡ [Cache Hit] Round {round_num} ({cached.get('race_name')}) is fully archived. Skipping scrape.")
                return True
        except Exception:
            pass

    meta = F1_WEB_ROUNDS.get(round_num)
    if not meta:
        print(f"  ⚠️ Round {round_num} not found in 2026 web mappings.")
        return False

    race_id, slug = meta["f1_id"], meta["slug"]
    base_url = f"https://www.formula1.com/en/results/2026/races/{race_id}/{slug}"

    # Determine sprint vs conventional weekend
    cal_candidates = [
        os.path.join(data_dir, "registries", "calendar_master.json"),
        os.path.join(data_dir, "calendar_master.json"),
    ]
    cal_file = next((p for p in cal_candidates if os.path.exists(p)), cal_candidates[0])
    is_sprint = False
    if os.path.exists(cal_file):
        try:
            with open(cal_file, "r", encoding="utf-8") as f:
                races = json.load(f).get("races", [])
            for r in races:
                if r.get("round") == round_num:
                    sched = r.get("schedule", {})
                    is_sprint = bool("sprintQualy" in sched or "sprintRace" in sched)
                    break
        except Exception:
            pass

    session_keys = (
        ["practice_1", "sprint_qualifying", "sprint_race", "qualifying", "race"]
        if is_sprint else
        ["practice_1", "practice_2", "practice_3", "qualifying", "race"]
    )

    url_suffixes = {
        "practice_1": "practice/1",
        "practice_2": "practice/2",
        "practice_3": "practice/3",
        "sprint_qualifying": "sprint-qualifying",
        "sprint_race": "sprint-results",
        "qualifying": "qualifying",
        "race": "race-result",
    }

    print(f"\n🏎️ [Scraping] Round {round_num} ({slug.title()}) — Format: {'Sprint' if is_sprint else 'Standard'}...")
    sessions_data = {}
    detected_circuit = ""

    # Scrape sessions politely with AntiBanClient
    for sk in session_keys:
        suffix = url_suffixes.get(sk)
        if not suffix:
            continue
        session_url = f"{base_url}/{suffix}"
        rows, title, _, circuit = await scrape_session_table_async(
            client,
            session_url,
            session_name=sk,
            referer=base_url
        )
        if rows:
            sessions_data[sk] = rows
            if circuit and not detected_circuit:
                detected_circuit = circuit
            print(f"  ✓ {sk:<18} ({len(rows):>2} drivers classified)")
        else:
            sessions_data[sk] = None

    if not any(sessions_data.values()):
        print(f"  ⚠️ No classifications found for Round {round_num} (Session not held yet).")
        return False

    race_results = sessions_data.get("race")
    has_race = bool(race_results and len(race_results) > 0)

    round_payload = {
        "round": round_num,
        "season": 2026,
        "race_name": f"{slug.replace('-', ' ').title()} Grand Prix",
        "circuit_name": detected_circuit or "Official Circuit",
        "status": "completed" if has_race else "in_progress",
        "is_sprint": is_sprint,
        "completed_sessions": [key for key in session_keys if sessions_data.get(key)],
        "upcoming_sessions": [key for key in session_keys if not sessions_data.get(key)],
        "sessions": sessions_data,
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    os.makedirs(sessions_dir, exist_ok=True)
    os.makedirs(rounds_dir, exist_ok=True)
    with open(os.path.join(rounds_dir, f"round_{round_num}.json"), "w", encoding="utf-8") as f:
        json.dump(round_payload, f, indent=2, ensure_ascii=False)
    with open(os.path.join(sessions_dir, f"round_{round_num}.json"), "w", encoding="utf-8") as f:
        json.dump(round_payload, f, indent=2, ensure_ascii=False)

    # Save to public v2 results directly
    results_dir = os.path.join(V2_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, f"round_{round_num}.json"), "w", encoding="utf-8") as f:
        json.dump(round_payload, f, indent=2, ensure_ascii=False)

    print(f"  🎉 Round {round_num} saved successfully to data/sessions/rounds/ and results/round_{round_num}.json")
    return True


# =====================================================================
# 🚀 Master Async Pipeline Orchestrator
# =====================================================================

def get_auto_target_round(events: dict) -> int:
    from collectors.f1_sessions import get_latest_weekend_event

    mapped_events = [
        event for event in events.values()
        if event.get("round") in F1_WEB_ROUNDS
    ]
    in_progress_events = [
        event for event in mapped_events
        if event.get("status") == "in_progress"
    ]
    if in_progress_events:
        return max(in_progress_events, key=lambda event: event["round"])["round"]

    upcoming_events = [
        event for event in mapped_events
        if event.get("status") == "upcoming"
    ]
    if upcoming_events:
        return min(upcoming_events, key=lambda event: event["round"])["round"]

    latest = get_latest_weekend_event(events)
    return latest.get("round", 17) if latest else 17


async def run_v2_cycle(
    client: AntiBanClient,
    round_num: Optional[int] = None,
    all_rounds: bool = False,
    skip_scrape: bool = False,
    force: bool = False,
    stealth: bool = False,
    push: bool = True
) -> bool:
    print("=" * 75)
    print(f"  🚀 TARAS F1 API v2 — ASYNCHRONOUS ANTI-BAN RUNNER [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("=" * 75)
    start_time = time.time()

    if not skip_scrape:
        print("\n[Step 1/4] Running Asynchronous Anti-Ban Scraping Engine...")
        if stealth:
            print("  🛡️ Stealth Mode ACTIVE: Random delays 3.5s - 6.5s per domain.")
        else:
            print("  🛡️ Standard Anti-Ban ACTIVE: Random delays 1.8s - 3.8s, rotating headers.")

        if round_num:
            rounds_to_scrape = [round_num]
        elif all_rounds:
            rounds_to_scrape = list(F1_WEB_ROUNDS.keys())
        else:
            # Auto-detect latest upcoming or in-progress round
            from collectors.f1_sessions import load_all_known_sessions
            auto_r = get_auto_target_round(load_all_known_sessions())
            print(f"  • Auto-detected target: Round {auto_r}")
            rounds_to_scrape = [auto_r]

        for r in rounds_to_scrape:
            await scrape_round_async(client, r, force=force)
    else:
        print("\n[Step 1/4] Web scraping skipped (--skip-scrape).")

    # Step 2: Build All V2 Endpoints
    print("\n[Step 2/4] Building Taras F1 API v2 Endpoints directly in v2/...")
    from build import build_v2_api
    build_v2_api()

    # Step 3: Run 100% Data Integrity Verification
    print("\n[Step 3/4] Verifying 100% Data Integrity & Zero Data Loss...")
    from test_v2_integrity import run_integrity_tests
    run_integrity_tests()

    # Step 4: Publish verified changes unless explicitly disabled
    if push:
        print("\n[Step 4/4] Auto-committing and deploying updates to GitHub...")
        from build import git_commit_and_push
        git_commit_and_push(ROOT_DIR)
    else:
        print("\n[Step 4/4] GitHub deployment skipped (--no-push).")

    total_time = time.time() - start_time
    print("\n" + "=" * 75)
    print(f"  ✅ RUN COMPLETE in {total_time:.2f}s: Taras F1 API v2 is 100% verified & ready! (Blocks: {client.rate_limited_count})")
    print("=" * 75)
    return True


async def main_async(args):
    client = AntiBanClient(stealth=args.stealth)

    if not args.loop:
        await run_v2_cycle(
            client=client,
            round_num=args.round,
            all_rounds=args.all,
            skip_scrape=args.skip_scrape,
            force=args.force,
            stealth=args.stealth,
            push=args.push,
        )
    else:
        print(f"\n🔄 CONTINUOUS SCRAPING MODE ACTIVE (Interval: {args.interval}s with random jitter)")
        print("  Press Ctrl+C at any time to cleanly stop the runner.\n")
        cycle = 1
        try:
            while True:
                print(f"\n>>> Running V2 Cycle #{cycle}...")
                prior_limits = client.rate_limited_count
                await run_v2_cycle(
                    client=client,
                    round_num=args.round,
                    all_rounds=args.all,
                    skip_scrape=args.skip_scrape,
                    force=args.force,
                    stealth=args.stealth,
                    push=args.push,
                )

                # Circuit breaker check:
                new_limits = client.rate_limited_count - prior_limits
                if new_limits > 0:
                    cooldown = random.uniform(300, 600)
                    print(f"\n🚨 [Circuit Breaker Triggered] {new_limits} rate-limit events detected on V2.")
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
    parser = argparse.ArgumentParser(description="Taras F1 API v2 — Asynchronous Anti-Ban Runner")
    parser.add_argument("--round", "-r", type=int, default=None, help="Target specific round (e.g. --round 17)")
    parser.add_argument("--all", "-a", action="store_true", help="Scrape all 24 rounds in the season")
    parser.add_argument("--skip-scrape", "-s", action="store_true", help="Skip web scraping and build from current data")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-scraping even if cached")
    parser.add_argument("--stealth", action="store_true", help="Enable maximum safety jitter (3.5s - 6.5s delay)")
    parser.add_argument("--loop", "-l", action="store_true", help="Run continuously in a polite jittered loop")
    parser.add_argument("--interval", "-i", type=int, default=300, help="Loop interval in seconds (default: 300)")
    publish_group = parser.add_mutually_exclusive_group()
    publish_group.add_argument("--push", "-p", dest="push", action="store_true", help="Publish updates to GitHub (default)")
    publish_group.add_argument("--no-push", dest="push", action="store_false", help="Build and verify without publishing")
    parser.set_defaults(push=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main_async(args))
