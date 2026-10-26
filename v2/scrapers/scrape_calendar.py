"""Refresh the V2 calendar feed and reconcile it with archived race results."""

import copy
import json
import os
import re
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional

import requests

V2_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(V2_DIR, "data")
MASTER_PATH = os.path.join(DATA_DIR, "registries", "calendar_master.json")
ROUNDS_DIR = os.path.join(DATA_DIR, "sessions", "rounds")
CALENDAR_URL = "https://f1api.dev/api/current"
SCHEDULE_KEYS = {
    "race": ("race",),
    "qualy": ("qualy", "qualifying"),
    "fp1": ("fp1",),
    "fp2": ("fp2",),
    "fp3": ("fp3",),
    "sprintQualy": ("sprintQualy", "sprint_qualifying", "sprint_qualy"),
    "sprintRace": ("sprintRace", "sprint_race"),
}
CIRCUIT_KEYS = (
    "circuitId",
    "circuitName",
    "gpName",
    "country",
    "city",
    "circuitLength",
    "lapRecord",
    "corners",
    "firstParticipationYear",
    "fastestLapDriverId",
    "fastestLapTeamId",
    "fastestLapYear",
    "trackImage",
)


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def fetch_calendar(session: Optional[requests.Session] = None) -> Dict[str, Any]:
    """Fetch and validate the upstream season calendar."""
    client = session or requests.Session()
    response = client.get(CALENDAR_URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("races"), list):
        raise ValueError("Calendar feed response must contain a races list")
    return data


def _valid_session(value: Any) -> Optional[Dict[str, str]]:
    if not isinstance(value, dict):
        return None
    date = value.get("date")
    time = value.get("time")
    if not isinstance(date, str) or not isinstance(time, str):
        return None
    try:
        datetime.strptime(date, "%Y-%m-%d")
        datetime.strptime(time, "%H:%M:%SZ")
    except ValueError:
        return None
    return {"date": date, "time": time}


def _normalise_schedule(schedule: Any) -> Dict[str, Dict[str, str]]:
    if not isinstance(schedule, dict):
        return {}
    normalized = {}
    for output_key, input_keys in SCHEDULE_KEYS.items():
        for input_key in input_keys:
            value = _valid_session(schedule.get(input_key))
            if value:
                normalized[output_key] = value
                break
    return normalized


def load_archived_winners(rounds_dir: str = ROUNDS_DIR) -> Dict[int, Dict[str, Any]]:
    """Read winner facts from completed round archives with a classified P1."""
    winners = {}
    if not os.path.isdir(rounds_dir):
        return winners

    for filename in os.listdir(rounds_dir):
        match = re.fullmatch(r"round_(\d+)\.json", filename)
        if not match:
            continue
        file_round = int(match.group(1))
        payload = _read_json(os.path.join(rounds_dir, filename))
        if payload.get("round") != file_round:
            raise ValueError(f"Round number mismatch in {filename}")
        if payload.get("status") != "completed":
            continue

        race_results = payload.get("sessions", {}).get("race", [])
        winner = next(
            (result for result in race_results if str(result.get("position")) == "1"),
            None,
        )
        if not winner or not winner.get("driver_name"):
            continue
        winners[file_round] = {
            "drivernumber": winner.get("driver_number"),
            "fullName": winner["driver_name"],
            "teamWinner": winner.get("team"),
        }
    return winners


def _normalise_feed_winner(race: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    driver = race.get("winner")
    if not isinstance(driver, dict):
        return None
    name = " ".join(
        part for part in (driver.get("name"), driver.get("surname")) if part
    ).strip()
    if not name:
        return None
    team = race.get("teamWinner")
    return {
        "drivernumber": driver.get("number"),
        "fullName": name,
        "teamWinner": team.get("teamName") if isinstance(team, dict) else None,
    }


def _new_race(feed_race: Dict[str, Any]) -> Dict[str, Any]:
    circuit = feed_race.get("circuit")
    return {
        "raceId": feed_race.get("raceId"),
        "raceName": feed_race.get("raceName"),
        "round": feed_race["round"],
        "laps": feed_race.get("laps"),
        "schedule": _normalise_schedule(feed_race.get("schedule")),
        "circuit": {
            key: circuit[key]
            for key in CIRCUIT_KEYS
            if isinstance(circuit, dict) and key in circuit
        },
        "winner": _normalise_feed_winner(feed_race),
    }


def merge_calendar(
    master: Dict[str, Any],
    feed: Dict[str, Any],
    archived_winners: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge fresh schedules while preserving curated metadata and past schedules."""
    if feed.get("season") != master.get("season"):
        raise ValueError(
            f"Calendar feed season {feed.get('season')} does not match "
            f"master season {master.get('season')}"
        )

    working_master = copy.deepcopy(master)
    existing_races = working_master.get("races")
    feed_races = feed.get("races")
    if not isinstance(existing_races, list) or not isinstance(feed_races, list) or not feed_races:
        raise ValueError("Both master and feed must contain race lists; feed cannot be empty")

    merged_by_round = {}
    for race in existing_races:
        round_num = race.get("round")
        if not isinstance(round_num, int) or round_num in merged_by_round:
            raise ValueError(f"Invalid or duplicate round in master calendar: {round_num}")
        merged_by_round[round_num] = race

    feed_rounds = set()
    for feed_race in feed_races:
        round_num = feed_race.get("round")
        if not isinstance(round_num, int) or round_num in feed_rounds:
            raise ValueError(f"Invalid or duplicate round in calendar feed: {round_num}")
        feed_rounds.add(round_num)
        feed_schedule = _normalise_schedule(feed_race.get("schedule"))

        existing = merged_by_round.get(round_num)
        if existing is None:
            if "race" not in feed_schedule:
                raise ValueError(
                    f"New calendar round {round_num} has no valid race schedule"
                )
            merged_by_round[round_num] = _new_race(feed_race)
            existing = merged_by_round[round_num]
        else:
            circuit = feed_race.get("circuit")
            if not isinstance(circuit, dict):
                circuit = {}
            for key in ("raceId", "raceName", "laps"):
                if existing.get(key) in (None, "") and feed_race.get(key) not in (None, ""):
                    existing[key] = feed_race[key]

            # Keep the curated master values; use the feed only to fill missing details.
            existing_circuit = existing.setdefault("circuit", {})
            for key in CIRCUIT_KEYS:
                value = circuit.get(key)
                if existing_circuit.get(key) in (None, "") and value not in (None, ""):
                    existing_circuit[key] = value

            # Archived weekends are protected from feed schedule errors or later revisions.
            if round_num not in archived_winners:
                existing_schedule = existing.setdefault("schedule", {})
                existing_schedule.update(feed_schedule)

        if round_num in archived_winners:
            existing["winner"] = archived_winners[round_num]

    for race in merged_by_round.values():
        if not _valid_session(race.get("schedule", {}).get("race")):
            raise ValueError(
                f"Calendar has no valid race schedule for round {race.get('round')}"
            )

    result = working_master
    result["totalRaces"] = len(merged_by_round)
    result["races"] = [merged_by_round[round_num] for round_num in sorted(merged_by_round)]
    return result


def _write_json_atomic(path: str, data: Dict[str, Any]) -> None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=os.path.dirname(path), delete=False
        ) as file:
            temp_path = file.name
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def update_calendar(
    master_path: str = MASTER_PATH,
    rounds_dir: str = ROUNDS_DIR,
    session: Optional[requests.Session] = None,
) -> bool:
    """Refresh the master registry. Returns whether its contents changed."""
    master = _read_json(master_path)
    feed = fetch_calendar(session)
    winners = load_archived_winners(rounds_dir)
    updated = merge_calendar(master, feed, winners)
    if updated == master:
        print(f"Calendar unchanged ({len(updated['races'])} rounds).")
        return False

    _write_json_atomic(master_path, updated)
    print(
        f"Calendar updated ({len(updated['races'])} rounds; "
        f"{len(winners)} archived winners reconciled)."
    )
    return True


if __name__ == "__main__":
    update_calendar()
