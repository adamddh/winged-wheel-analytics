"""Data-quality gates. Each check is SQL returning a violation count; any failing "error"
check stops the pipeline. Results are written to reports/quality.json."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from wings.config import Settings

log = logging.getLogger(__name__)


@dataclass
class Check:
    name: str
    category: str
    sql: str
    severity: str = "error"  # "warn" checks are reported but never fail the pipeline


class QualityError(RuntimeError):
    pass


def _null_rate(table: str, column: str, max_rate: float, where: str = "true") -> Check:
    return Check(
        f"{table}.{column} null rate <= {max_rate:.1%}",
        "null_rate",
        f"select (avg(({column} is null)::int) > {max_rate})::int from {table} where {where}",
    )


def _unique(table: str, key: str) -> Check:
    return Check(
        f"{table} unique on ({key})",
        "duplicate_keys",
        f"select count(*) from (select {key} from {table} group by all having count(*) > 1)",
    )


def _references(child: str, column: str, parent: str, parent_column: str) -> Check:
    return Check(
        f"{child}.{column} -> {parent}.{parent_column}",
        "referential_integrity",
        f"select count(*) from {child} c where c.{column} is not null and not exists "
        f"(select 1 from {parent} p where p.{parent_column} = c.{column})",
    )


def base_checks(settings: Settings) -> list[Check]:
    seasons = ", ".join(map(str, settings.seasons))
    analysis = ", ".join(map(str, settings.analysis_seasons))
    checks = [
        Check(
            f"{season}: >= {floor} completed games",
            "row_count",
            f"select greatest(0, {floor} - count(*)) from silver.games "
            f"where season = {season} and game_state = 'OFF'",
        )
        for season, floor in settings.min_games.items()
    ]
    checks += [
        Check(
            "every completed game has play-by-play",
            "completeness",
            f"select count(*) from silver.games g where g.game_state = 'OFF' "
            f"and g.season in ({seasons}) "
            "and not exists (select 1 from silver.plays p where p.game_id = g.game_id)",
        ),
        Check(
            f"every completed {settings.team} game has shift charts",
            "completeness",
            f"select count(*) from silver.games g where g.game_state = 'OFF' "
            f"and g.season in ({analysis}) and '{settings.team}' in (g.home_team, g.away_team) "
            "and not exists (select 1 from silver.shifts s where s.game_id = g.game_id)",
            severity="warn",  # the NHL sometimes publishes shift charts hours after the final
        ),
        Check(
            f"current-season schedule refreshed within {settings.freshness_hours}h",
            "freshness",
            "select coalesce(max(ingested_at) < now() - interval "
            f"{settings.freshness_hours} hour, true)::int from bronze.nhl_schedule "
            f"where source_file like '%/{settings.current_season}/%'",
        ),
        _null_rate("silver.plays", "event_type", 0.0),
        _null_rate("silver.plays", "game_seconds", 0.0),
        _null_rate("gold.shots", "situation_code", 0.005),
        _null_rate("gold.shots", "shooter_id", 0.005),
        _null_rate("gold.shots", "distance", 0.01),
        _unique("silver.games", "game_id"),
        _unique("silver.plays", "game_id, event_id"),
        _unique("silver.players", "player_id"),
        _unique("silver.shifts", "shift_id"),
        _unique("silver.moneypuck_shots", "season, mp_shot_id"),
        _unique("gold.shots", "shot_id"),
        _references("silver.plays", "game_id", "silver.games", "game_id"),
        _references("silver.shifts", "game_id", "silver.games", "game_id"),
        _references("silver.shifts", "player_id", "silver.players", "player_id"),
        _references("gold.shots", "shooter_id", "silver.players", "player_id"),
        _references("silver.moneypuck_shots", "game_id", "silver.games", "game_id"),
        Check(
            "shot distance within rink bounds",
            "range",
            "select count(*) from gold.shots where distance not between 0 and 200",
        ),
    ]
    return checks


def mart_checks(settings: Settings) -> list[Check]:
    return [
        Check(
            "xG within [0, 1]",
            "range",
            "select count(*) from gold.shot_xg where xg is null or xg not between 0 and 1",
        ),
        Check(
            "each completed game has exactly two team rows",
            "row_count",
            "select count(*) from silver.games g where game_state = 'OFF' and "
            "(select count(*) from gold.team_games t where t.game_id = g.game_id) <> 2",
        ),
        Check(
            "xG-set goals never exceed scoreboard goals",
            "consistency",
            "select count(*) from gold.team_games where gf > final_gf",
        ),
        _unique("gold.team_games", "game_id, team_id"),
        _unique("gold.player_seasons", "season, player_id"),
        _unique("gold.player_cards", "season, player_id"),
        _references("gold.team_games", "team_id", "silver.teams", "team_id"),
        Check(
            f"{len(settings.focus_players)} focus players x 2 seasons in player_cards",
            "row_count",
            f"select abs(count(*) - {2 * len(settings.focus_players)}) from gold.player_cards",
        ),
    ]


def run(
    con: duckdb.DuckDBPyConnection, checks: list[Check], report_path: Path, stage: str
) -> list[dict]:
    results = []
    for check in checks:
        violations = con.execute(check.sql).fetchone()[0]
        results.append({**asdict(check), "violations": violations, "passed": violations == 0})
        level = logging.INFO if violations == 0 else logging.WARNING
        log.log(level, "[%s] %s: %s", check.category, check.name, violations or "ok")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(report_path.read_text()) if report_path.exists() else {}
    existing[stage] = {
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "results": results,
    }
    report_path.write_text(json.dumps(existing, indent=2, default=str) + "\n")

    failed = [r for r in results if not r["passed"] and r["severity"] == "error"]
    if failed:
        names = "; ".join(f"{r['name']} ({r['violations']})" for r in failed)
        raise QualityError(f"{len(failed)} data-quality check(s) failed: {names}")
    return results
