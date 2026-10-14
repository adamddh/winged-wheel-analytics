import json

import httpx

from wings.ingest import http as http_mod
from wings.ingest import nhl
from wings.ingest.http import ThrottledClient, write_json


def _schedule(games):
    return {"gameWeek": [{"date": "2026-10-13", "games": games}]}


def _game(gid, state="OFF", gtype=2, home="DET", away="NJD", season=20262027):
    return {
        "id": gid,
        "season": season,
        "gameType": gtype,
        "gameState": state,
        "homeTeam": {"abbrev": home},
        "awayTeam": {"abbrev": away},
    }


def test_completed_games_keeps_only_official_regular_season(tmp_path):
    games = [
        _game(1),
        _game(2, state="FUT"),
        _game(3, gtype=1),
        _game(4, state="FINAL"),
        _game(5, home="BOS", away="TOR"),
    ]
    write_json(tmp_path / "nhl/schedule/20262027/2026-10-13.json", _schedule(games))
    assert nhl.completed_games(tmp_path, 20262027) == [1, 5]
    assert nhl.completed_games(tmp_path, 20262027, team="DET") == [1]


def test_play_by_play_ingest_is_incremental(tmp_path):
    write_json(tmp_path / "nhl/schedule/20262027/w.json", _schedule([_game(10), _game(11)]))
    write_json(tmp_path / "nhl/pbp/20262027/10.json", {"id": 10})  # already cached
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"id": 11, "plays": []})

    client = ThrottledClient(0, transport=httpx.MockTransport(handler))
    assert nhl.ingest_play_by_play(client, tmp_path, 20262027) == 1
    assert calls == ["/v1/gamecenter/11/play-by-play"]
    # second run is a no-op: idempotent
    assert nhl.ingest_play_by_play(client, tmp_path, 20262027) == 0
    assert json.loads((tmp_path / "nhl/pbp/20262027/11.json").read_text())["id"] == 11


def test_client_retries_server_errors(monkeypatch):
    monkeypatch.setattr(http_mod.time, "sleep", lambda s: None)
    responses = iter(
        [httpx.Response(503), httpx.Response(429), httpx.Response(200, json={"ok": 1})]
    )
    client = ThrottledClient(0, transport=httpx.MockTransport(lambda r: next(responses)))
    assert client.get_json("https://example.test/x") == {"ok": 1}


def test_write_json_leaves_no_temp_files(tmp_path):
    write_json(tmp_path / "a/b.json", {"x": 1})
    assert [p.name for p in (tmp_path / "a").iterdir()] == ["b.json"]
