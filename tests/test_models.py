"""Tests of the no-Home-Assistant-dependency Nourish API response parser."""

import sys
from datetime import date, datetime, timezone
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "nourish"))
from models import parse_goals_response  # noqa: E402


class ParseTest(unittest.TestCase):
    def test_numeric_goal_and_progress(self):
        result = parse_goals_response(
            [
                {"type": "LOG_NUTRIENT", "subType": "PROTEIN",
                 "goalAmount": 120, "goalProgress": [87.5]},
                {"type": "OTHER", "subType": "FAT", "goalAmount": 50},
            ],
            date(2026, 11, 9),
            datetime(2026, 11, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(result.nutrients["PROTEIN"].goal, 120)
        self.assertEqual(result.nutrients["PROTEIN"].progress, 87.5)
        self.assertNotIn("FAT", result.nutrients)

    def test_unknown_progress_object_is_not_misinterpreted(self):
        result = parse_goals_response(
            [{"type": "LOG_NUTRIENT", "subType": "FIBER",
              "goalAmount": 30, "goalProgress": [{"unrecognized": 9}]}],
            date(2026, 11, 9),
            datetime(2026, 11, 10, tzinfo=timezone.utc),
        )
        self.assertIsNone(result.nutrients["FIBER"].progress)

    def test_rejects_non_list_response(self):
        with self.assertRaises(ValueError):
            parse_goals_response({}, date(2026, 11, 9), datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
