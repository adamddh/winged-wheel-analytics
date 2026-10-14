"""End-to-end: run the whole pipeline offline against real cached payloads for six games."""

import json
import shutil
from pathlib import Path

import duckdb
import pytest

from wings.cli import pipeline
from wings.config import load_settings

FIXTURE = Path(__file__).parent / "fixtures" / "raw"

CONFIG = """
data_dir = "{root}/data"
output_dir = "{root}"
team = "DET"
train_seasons = [20242025]
test_season = 20252026
current_season = 20262027
offline = true
freshness_hours = 1000000

[focus_players]
"Dylan Larkin" = 8477946
"Lucas Raymond" = 8482078
"Moritz Seider" = 8481542
"Simon Edvinsson" = 8482762

[min_games]
20242025 = 2
20252026 = 2
20262027 = 2
"""


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    root = tmp_path_factory.mktemp("pipeline")
    shutil.copytree(FIXTURE, root / "data" / "raw")
    (root / "README.md").write_text("# x\n<!-- findings:start -->\n<!-- findings:end -->\n")
    (root / "wings.toml").write_text(CONFIG.format(root=root.as_posix()))
    settings = load_settings(root / "wings.toml")
    pipeline(settings)
    pipeline(settings)  # a second run must be a clean, idempotent rebuild
    return root


def test_warehouse_contents(run_dir):
    con = duckdb.connect(str(run_dir / "data" / "warehouse.duckdb"), read_only=True)
    q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    assert q("select count(*) from silver.games where game_state = 'OFF'") == 6
    assert q("select count(*) from gold.team_games") == 12
    assert q("select count(*) from gold.shot_xg where xg not between 0 and 1") == 0
    assert q("select count(*) from gold.player_cards") == 8
    assert q("select count(*) from silver.shifts") > 0
    # the scoreboard in the warehouse matches the raw schedule
    det = con.execute(
        "select final_gf, final_ga from gold.team_games where game_id = 2026020090 and team = 'DET'"
    ).fetchone()
    assert det == (4, 5)


def test_quality_report_all_errors_pass(run_dir):
    report = json.loads((run_dir / "reports" / "quality.json").read_text())
    results = report["base"]["results"] + report["marts"]["results"]
    assert all(r["passed"] for r in results if r["severity"] == "error")


def test_deliverables_written(run_dir):
    for path in [
        "models/xg_model.json",
        "models/xg_metrics.json",
        "models/xg_calibration.png",
        "exports/team_games.parquet",
        "exports/shots.parquet",
        "exports/player_cards.parquet",
        "exports/meta.json",
        "reports/findings.md",
        "reports/figures/shot_map.png",
        "reports/figures/game_recap_xg.png",
        "docs/schema.md",
    ]:
        assert (run_dir / path).stat().st_size > 0, path
    readme = (run_dir / "README.md").read_text()
    assert "DET 2026-27 season to date" in readme and "Game recap" in readme
    assert json.loads((run_dir / "exports" / "meta.json").read_text())["data_through"]
