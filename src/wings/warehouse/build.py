"""Build the DuckDB warehouse by executing the SQL models layer by layer."""

from pathlib import Path

import duckdb

from wings.config import Settings

SQL_DIR = Path(__file__).parent / "sql"
LAYERS = {"base": ["bronze", "silver", "gold_features"], "marts": ["gold_marts"]}


def connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.db_path))
    con.execute("set enable_progress_bar = false")
    for schema in ("bronze", "silver", "gold", "meta"):
        con.execute(f"create schema if not exists {schema}")
    con.execute((SQL_DIR / "macros.sql").read_text())
    con.execute(f"set variable current_season = {settings.current_season}")
    con.execute(f"set variable test_season = {settings.test_season}")
    con.execute("create or replace table meta.focus_players (player_id integer, name varchar)")
    con.executemany(
        "insert into meta.focus_players values (?, ?)",
        [(pid, name) for name, pid in settings.focus_players.items()],
    )
    return con


def build(con: duckdb.DuckDBPyConnection, settings: Settings, stage: str) -> None:
    raw = settings.raw_dir.resolve().as_posix()
    for layer in LAYERS[stage]:
        for path in sorted((SQL_DIR / layer).glob("*.sql")):
            con.execute(path.read_text().replace("{{raw_dir}}", raw))
