"""Unit tests for the SQL transforms (macros + the gold.shots feature model)."""

import math

import pytest

from wings.warehouse.build import SQL_DIR


def one(con, sql):
    return con.execute(f"select {sql}").fetchone()[0]


def test_clock_parsing(con):
    assert one(con, "mmss_to_seconds('00:00')") == 0
    assert one(con, "mmss_to_seconds('19:59')") == 1199


@pytest.mark.parametrize(
    ("is_home", "side", "x", "expected"),
    [
        (True, "right", 50, True),  # home defends right -> attacks the left net
        (False, "right", -50, False),
        (True, "left", -50, False),
        (False, "left", 50, True),
        (True, None, -70, True),  # side missing: infer from the shot's half
    ],
)
def test_attacking_direction(con, is_home, side, x, expected):
    side_sql = "null" if side is None else f"'{side}'"
    assert one(con, f"attacks_left({is_home}, {side_sql}, {x})") is expected


def test_distance_and_angle(con):
    assert one(con, "shot_distance(89, 0)") == 0
    assert one(con, "shot_distance(59, 0)") == 30
    assert one(con, "shot_angle(59, 0)") == 0
    assert math.isclose(one(con, "shot_angle(79, 10)"), 45)
    assert math.isclose(one(con, "shot_angle(79, -10)"), 45)  # symmetric
    assert one(con, "shot_angle(95, 5)") > 90  # behind the goal line


@pytest.mark.parametrize(
    ("code", "is_home", "expected"),
    [
        ("1551", True, "5v5"),
        ("1451", True, "PP"),  # away 4 skaters, home 5
        ("1451", False, "SH"),
        ("1441", True, "other"),  # 4v4
        ("0651", False, "other"),  # away pulled goalie for a 6th attacker
        ("1560", False, "SH"),  # home pulled its goalie: 5 skaters vs 6 (an empty-net shot)
    ],
)
def test_manpower_from_situation_code(con, code, is_home, expected):
    assert one(con, f"manpower('{code}', {is_home})") == expected


def test_flips_and_groups(con):
    assert one(con, "flip_manpower('PP')") == "SH"
    assert one(con, "flip_manpower('5v5')") == "5v5"
    assert one(con, "flip_zone('O')") == "D"
    assert one(con, "flip_zone('N')") == "N"
    assert one(con, "shot_type_group('wrist')") == "wrist"
    assert one(con, "shot_type_group('between-legs')") == "other"
    assert one(con, "shot_type_group(null)") == "other"


def _play(event_id, event_type, team_id, secs, zone="O", x=70.0, y=0.0, sc="1551"):
    return (
        1,
        20262027,
        event_id,
        event_id,
        1,
        "REG",
        secs,
        sc,
        event_type,
        "right",
        10,
        20,
        team_id,
        team_id == 10,
        zone,
        x,
        y,
        "wrist",
        99,
        98,
        None,
        None,
    )


PLAYS_DDL = """
create table silver.plays (game_id bigint, season int, event_id int, sort_order int,
    period int, period_type varchar, game_seconds int, situation_code varchar,
    event_type varchar, home_defending_side varchar, home_team_id int, away_team_id int,
    team_id int, is_home boolean, zone_code varchar, x double, y double, shot_type varchar,
    shooter_id int, goalie_id int, assist1_id int, assist2_id int)
"""


def build_shots(con, plays):
    con.execute(PLAYS_DDL)
    con.executemany(f"insert into silver.plays values ({', '.join(['?'] * 22)})", plays)
    con.execute((SQL_DIR / "gold_features" / "01_shots.sql").read_text())
    return con.execute("select * from gold.shots order by event_id").df().set_index("event_id")


def test_shot_features(con):
    shots = build_shots(
        con,
        [
            _play(1, "shot-on-goal", 10, 100, x=-60),  # home attacks left: normalized x = 60
            _play(2, "missed-shot", 10, 102, x=-80),  # 2s after own shot -> rebound
            _play(3, "takeaway", 20, 200, zone="O"),  # away's O zone = home's D zone
            _play(4, "goal", 10, 203, x=-75),  # rush: prior event in shooter's D zone
            _play(5, "shot-on-goal", 20, 300, x=80),  # away shooting, home leads 1-0
            _play(6, "blocked-shot", 10, 400),  # blocked: not in the unblocked set
        ],
    )
    assert list(shots.index) == [1, 2, 4, 5]
    assert shots.loc[1, "x_norm"] == 60 and shots.loc[1, "distance"] == 29
    assert not shots.loc[1, "is_rebound"] and shots.loc[2, "is_rebound"]
    assert shots.loc[2, "rebound_seconds"] == 2
    assert shots.loc[4, "is_rush"] and not shots.loc[2, "is_rush"]
    assert shots.loc[4, "is_goal"] and shots.loc[4, "score_state"] == 0  # score before the goal
    assert shots.loc[5, "score_state"] == -1 and shots.loc[5, "x_norm"] == 80
    assert shots.loc[5, "shot_id"] == 1 * 100000000 + 5


def test_empty_net_and_shootout(con):
    shots = build_shots(
        con,
        [
            _play(1, "goal", 10, 3500, x=-60, sc="0651"),  # away goalie pulled
            (*_play(2, "goal", 10, 3900, x=-60)[:5], "SO", *_play(2, "goal", 10, 3900)[6:]),
        ],
    )
    assert list(shots.index) == [1]
    assert shots.loc[1, "is_empty_net"]
