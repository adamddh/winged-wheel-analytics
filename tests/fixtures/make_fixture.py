"""Rebuild tests/fixtures/raw from a full local data/raw cache.

Keeps two real Detroit games per season (schedule, play-by-play, shift charts, rosters,
MoneyPuck rows) so the integration test exercises the real payload shapes offline.

    uv run python tests/fixtures/make_fixture.py
"""

import csv
import json
import shutil
from pathlib import Path

SRC = Path("data/raw")
DST = Path(__file__).parent / "raw"
GAMES = {
    20242025: [2024020014, 2024020028],
    20252026: [2025020010, 2025020025],
    20262027: [2026020066, 2026020090],
}
TEAM = "DET"


def main() -> None:
    shutil.rmtree(DST, ignore_errors=True)
    wanted = {g for ids in GAMES.values() for g in ids}
    for season, ids in GAMES.items():
        for week in sorted((SRC / f"nhl/schedule/{season}").glob("*.json")):
            payload = json.loads(week.read_text())
            for day in payload["gameWeek"]:
                day["games"] = [g for g in day["games"] if g["id"] in wanted]
            if any(day["games"] for day in payload["gameWeek"]):
                out = DST / f"nhl/schedule/{season}/{week.name}"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(payload))
        for gid in ids:
            for kind in ("pbp", "shifts"):
                src = SRC / f"nhl/{kind}/{season}/{gid}.json"
                if src.exists():
                    (DST / f"nhl/{kind}/{season}").mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, DST / f"nhl/{kind}/{season}/{gid}.json")
        roster = SRC / f"nhl/roster/{season}/{TEAM}.json"
        if roster.exists():
            (DST / f"nhl/roster/{season}").mkdir(parents=True, exist_ok=True)
            shutil.copy(roster, DST / f"nhl/roster/{season}/{TEAM}.json")
        mp = SRC / f"moneypuck/shots_{season // 10000}.csv"
        if mp.exists():
            mp_ids = {str(g % 1000000) for g in ids}
            (DST / "moneypuck").mkdir(parents=True, exist_ok=True)
            with mp.open() as f, (DST / "moneypuck" / mp.name).open("w", newline="") as out:
                reader = csv.DictReader(f)
                writer = csv.DictWriter(out, reader.fieldnames)
                writer.writeheader()
                writer.writerows(r for r in reader if r["game_id"] in mp_ids)


if __name__ == "__main__":
    main()
