"""Incremental, idempotent ingest from the official NHL APIs into data/raw/nhl.

Cache policy: anything that can no longer change (past-season schedules, play-by-play and
shift charts of official final games) is fetched once and never again. Current-season
schedules and rosters are re-fetched every run because game states change.
"""

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from wings.config import Settings
from wings.ingest.http import ThrottledClient, write_json

log = logging.getLogger(__name__)

WEB = "https://api-web.nhle.com/v1"
STATS = "https://api.nhle.com/stats/rest/en"
REGULAR_SEASON = 2
FINAL_STATE = "OFF"  # "FINAL" games can still receive scoring corrections; "OFF" is official


def ingest_schedule(client: ThrottledClient, raw: Path, season: int, current: bool) -> None:
    out = raw / "nhl" / "schedule" / str(season)
    done = out / "_complete"
    if done.exists() and not current:
        return
    week = date(season // 10000, 9, 15)
    end = None
    for _ in range(60):
        payload = client.get_json(f"{WEB}/schedule/{week.isoformat()}")
        write_json(out / f"{week.isoformat()}.json", payload)
        end = end or date.fromisoformat(payload["regularSeasonEndDate"])
        nxt = payload.get("nextStartDate")
        if not nxt or date.fromisoformat(nxt) > end:
            break
        if current and date.fromisoformat(nxt) > date.today() + timedelta(days=7):
            break  # future weeks hold no completed games
        week = date.fromisoformat(nxt)
    if not current:
        done.touch()


def completed_games(raw: Path, season: int, team: str | None = None) -> list[int]:
    """Official-final regular-season game ids for a season, optionally for one team."""
    ids = set()
    for f in (raw / "nhl" / "schedule" / str(season)).glob("*.json"):
        for day in json.loads(f.read_text())["gameWeek"]:
            for g in day["games"]:
                if (
                    g["season"] == season
                    and g["gameType"] == REGULAR_SEASON
                    and g["gameState"] == FINAL_STATE
                    and team in (None, g["homeTeam"]["abbrev"], g["awayTeam"]["abbrev"])
                ):
                    ids.add(g["id"])
    return sorted(ids)


def ingest_play_by_play(client: ThrottledClient, raw: Path, season: int) -> int:
    fetched = 0
    for gid in completed_games(raw, season):
        path = raw / "nhl" / "pbp" / str(season) / f"{gid}.json"
        if path.exists():
            continue
        write_json(path, client.get_json(f"{WEB}/gamecenter/{gid}/play-by-play"))
        fetched += 1
        if fetched % 100 == 0:
            log.info("pbp %s: %d new games fetched", season, fetched)
    return fetched


def ingest_shifts(client: ThrottledClient, raw: Path, season: int, team: str) -> int:
    fetched = 0
    for gid in completed_games(raw, season, team):
        path = raw / "nhl" / "shifts" / str(season) / f"{gid}.json"
        if path.exists():
            continue
        payload = client.get_json(f"{STATS}/shiftcharts?cayenneExp=gameId={gid}")
        if not payload.get("data"):
            log.warning("no shift data yet for %s; will retry next run", gid)
            continue
        write_json(path, payload)
        fetched += 1
    return fetched


def ingest_roster(client: ThrottledClient, raw: Path, season: int, team: str, current: bool):
    path = raw / "nhl" / "roster" / str(season) / f"{team}.json"
    if path.exists() and not current:
        return
    write_json(path, client.get_json(f"{WEB}/roster/{team}/{season}"))


def run(settings: Settings, client: ThrottledClient | None = None) -> None:
    client = client or ThrottledClient(settings.request_interval_s)
    raw = settings.raw_dir
    for season in settings.seasons:
        current = season == settings.current_season
        ingest_schedule(client, raw, season, current)
        n = ingest_play_by_play(client, raw, season)
        log.info("season %s: %d new play-by-play files", season, n)
    for season in settings.analysis_seasons:
        current = season == settings.current_season
        ingest_roster(client, raw, season, settings.team, current)
        n = ingest_shifts(client, raw, season, settings.team)
        log.info("season %s: %d new %s shift charts", season, n, settings.team)
