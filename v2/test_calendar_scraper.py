import copy
import unittest

from scrapers.scrape_calendar import (
    load_archived_winners,
    merge_calendar,
    update_calendar,
)


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, data):
        self.data = data

    def get(self, url, timeout):
        return FakeResponse(self.data)


class CalendarScraperTests(unittest.TestCase):
    def setUp(self):
        self.master = {
            "season": 2026,
            "totalRaces": 2,
            "races": [
                {
                    "round": 1,
                    "raceId": "race_1",
                    "raceName": "Curated Grand Prix",
                    "schedule": {"race": {"date": "2026-03-01", "time": "12:00:00Z"}},
                    "circuit": {"circuitId": "track_1", "trackImage": "image.webp"},
                    "winner": None,
                },
                {
                    "round": 2,
                    "raceId": "race_2",
                    "raceName": "Upcoming Grand Prix",
                    "schedule": {"race": {"date": "2026-04-01", "time": "12:00:00Z"}},
                    "circuit": {"circuitId": "track_2", "trackImage": "image2.webp"},
                    "winner": None,
                },
            ],
        }
        self.feed = {
            "season": 2026,
            "races": [
                {
                    "round": 1,
                    "raceId": "race_1",
                    "raceName": "Untrusted changed name",
                    "schedule": {"race": {"date": "2026-03-02", "time": "13:00:00Z"}},
                    "circuit": {"circuitId": "track_1", "trackImage": None},
                },
                {
                    "round": 2,
                    "raceId": "race_2",
                    "raceName": "Untrusted changed name",
                    "schedule": {
                        "race": {"date": "2026-04-02", "time": "13:00:00Z"},
                        "fp1": {"date": None, "time": None},
                    },
                    "circuit": {"circuitId": "track_2", "trackImage": None},
                },
            ],
        }

    def test_archived_winner_overrides_feed_but_past_schedule_and_metadata_are_kept(self):
        winner = {"drivernumber": 44, "fullName": "Lewis Hamilton", "teamWinner": "Ferrari"}
        original_master = copy.deepcopy(self.master)
        merged = merge_calendar(self.master, self.feed, {1: winner})

        self.assertEqual(merged["races"][0]["winner"], winner)
        self.assertEqual(merged["races"][0]["schedule"], self.master["races"][0]["schedule"])
        self.assertEqual(merged["races"][0]["raceName"], "Curated Grand Prix")
        self.assertEqual(merged["races"][0]["circuit"]["trackImage"], "image.webp")
        self.assertEqual(self.master, original_master)

    def test_upcoming_schedule_refreshes_without_erasing_missing_data(self):
        merged = merge_calendar(self.master, self.feed, {})
        upcoming = merged["races"][1]

        self.assertEqual(
            upcoming["schedule"]["race"],
            {"date": "2026-04-02", "time": "13:00:00Z"},
        )
        self.assertNotIn("fp1", upcoming["schedule"])
        self.assertEqual(upcoming["raceName"], "Upcoming Grand Prix")
        self.assertEqual(upcoming["circuit"]["trackImage"], "image2.webp")

    def test_existing_rounds_are_not_dropped_when_feed_omits_one(self):
        self.feed["races"].pop()
        merged = merge_calendar(self.master, self.feed, {})
        self.assertEqual([race["round"] for race in merged["races"]], [1, 2])

    def test_partial_feed_schedule_preserves_existing_session_time(self):
        self.feed["races"][1]["schedule"]["race"]["time"] = None
        merged = merge_calendar(self.master, self.feed, {})
        self.assertEqual(
            merged["races"][1]["schedule"]["race"],
            self.master["races"][1]["schedule"]["race"],
        )

    def test_new_round_without_valid_race_schedule_is_rejected(self):
        self.feed["races"].append(
            {
                "round": 3,
                "raceId": "race_3",
                "schedule": {"race": {"date": "2026-05-01", "time": None}},
            }
        )
        with self.assertRaises(ValueError):
            merge_calendar(self.master, self.feed, {})

    def test_season_mismatch_is_rejected(self):
        self.feed["season"] = 2025
        with self.assertRaises(ValueError):
            merge_calendar(self.master, self.feed, {})

    def test_archived_winner_requires_completed_race_classification(self):
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as rounds_dir:
            path = os.path.join(rounds_dir, "round_1.json")
            with open(path, "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "round": 1,
                        "status": "completed",
                        "sessions": {
                            "race": [
                                {
                                    "position": 1,
                                    "driver_number": 63,
                                    "driver_name": "George Russell",
                                    "team": "Mercedes",
                                }
                            ]
                        },
                    },
                    file,
                )

            self.assertEqual(
                load_archived_winners(rounds_dir)[1],
                {
                    "drivernumber": 63,
                    "fullName": "George Russell",
                    "teamWinner": "Mercedes",
                },
            )

    def test_update_calendar_persists_merged_data(self):
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            master_path = os.path.join(temp_dir, "calendar_master.json")
            rounds_dir = os.path.join(temp_dir, "rounds")
            os.makedirs(rounds_dir)
            with open(master_path, "w", encoding="utf-8") as file:
                json.dump(self.master, file)
            with open(os.path.join(rounds_dir, "round_1.json"), "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "round": 1,
                        "status": "completed",
                        "sessions": {
                            "race": [
                                {
                                    "position": 1,
                                    "driver_number": 44,
                                    "driver_name": "Lewis Hamilton",
                                    "team": "Ferrari",
                                }
                            ]
                        },
                    },
                    file,
                )

            changed = update_calendar(
                master_path=master_path,
                rounds_dir=rounds_dir,
                session=FakeSession(self.feed),
            )
            with open(master_path, "r", encoding="utf-8") as file:
                persisted = json.load(file)

        self.assertTrue(changed)
        self.assertEqual(
            persisted["races"][0]["winner"],
            {"drivernumber": 44, "fullName": "Lewis Hamilton", "teamWinner": "Ferrari"},
        )
        self.assertEqual(
            persisted["races"][1]["schedule"]["race"],
            {"date": "2026-04-02", "time": "13:00:00Z"},
        )


if __name__ == "__main__":
    unittest.main()
