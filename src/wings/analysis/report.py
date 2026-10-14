"""Turn gold tables into reproducible deliverables: parquet exports for the dashboard, README
charts, a game recap, and the generated findings section of the README. No number in these
outputs is typed by hand; every one is queried from the warehouse on each run."""

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from wings.analysis.style import INK, MUTED, RED, STEEL, draw_half_rink, plt
from wings.config import Settings
from wings.markdown import md_table

log = logging.getLogger(__name__)

DECIDED = {"OT": " in overtime", "SO": " in a shootout"}
MARKER = re.compile(r"(<!-- findings:start -->)(.*?)(<!-- findings:end -->)", re.S)


def season_label(season: int) -> str:
    return f"{season // 10000}-{str(season % 10000)[2:]}"


def clock(period: int, game_seconds: int) -> str:
    rem = int(game_seconds) - (int(period) - 1) * 1200
    return f"{'OT' if period > 3 else f'P{period}'} {rem // 60}:{rem % 60:02d}"


# --------------------------------------------------------------------------- exports


def export_tables(con: duckdb.DuckDBPyConnection, settings: Settings, out: Path) -> None:
    seasons = ", ".join(map(str, settings.analysis_seasons))
    team = settings.team
    tables = {
        "team_games": f"select * from gold.team_games where season in ({seasons})",
        "team_season_splits": f"select * from gold.team_season_splits where season in ({seasons})",
        "player_cards": "select * from gold.player_cards",
        "team_players": f"select * from gold.player_seasons where team = '{team}' "
        f"and season in ({seasons})",
        "shots": f"""
            select season, game_id, game_date, shot_id, period, game_seconds, team, opponent,
                shooter, event_type, is_goal, shot_type, manpower, is_rebound, is_rush,
                distance, x_norm, y_norm, xg
            from gold.shots_scored
            where season in ({seasons}) and '{team}' in (team, opponent)
        """,
    }
    out.mkdir(parents=True, exist_ok=True)
    for name, sql in tables.items():
        con.execute(f"copy ({sql}) to '{(out / name).as_posix()}.parquet' (format parquet)")
    if settings.export_uri:
        publish(con, tables, settings.export_uri)


def publish(con: duckdb.DuckDBPyConnection, tables: dict[str, str], uri: str) -> None:
    """Mirror the gold exports to object storage (e.g. s3://bucket/prefix) with DuckDB httpfs,
    using the standard AWS credential chain."""
    # ponytail: S3 only; Azure Blob would use DuckDB's azure extension the same way.
    con.execute("install httpfs; load httpfs")
    con.execute("create secret if not exists (type s3, provider credential_chain)")
    for name, sql in tables.items():
        con.execute(f"copy ({sql}) to '{uri.rstrip('/')}/{name}.parquet' (format parquet)")
    log.info("published %d tables to %s", len(tables), uri)


# --------------------------------------------------------------------------- charts


def chart_xg_by_game(games: pd.DataFrame, team: str, path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    x = games.team_game_number
    ax.plot(x, games.xgf, "-o", color=RED, ms=7, label=f"{team} xG for")
    ax.plot(x, games.xga, "-o", color=STEEL, ms=7, label=f"{team} xG against")
    ax.scatter(
        x,
        games.gf,
        s=70,
        facecolors="none",
        edgecolors=RED,
        lw=1.8,
        zorder=3,
        label="actual goals for",
    )
    ax.scatter(
        x,
        games.ga,
        s=70,
        marker="s",
        facecolors="none",
        edgecolors=STEEL,
        lw=1.8,
        zorder=3,
        label="actual goals against",
    )
    ax.set_xticks(
        x,
        [
            f"{'vs' if h else '@'} {o}\n{d:%b %d}"
            for h, o, d in zip(games.is_home, games.opponent, games.game_date, strict=True)
        ],
        fontsize=8,
    )
    top = max(games[["xgf", "xga", "gf", "ga"]].max()) * 1.35
    ax.set(ylabel="Goals / expected goals", title=title, ylim=(0, top))
    ax.legend(frameon=False, ncol=4, fontsize=8, loc="upper center")
    fig.savefig(path)
    plt.close(fig)


def chart_league_scatter(splits: pd.DataFrame, team: str, path: Path, title: str) -> None:
    df = splits.assign(gf_pct=splits.gf / (splits.gf + splits.ga))
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    other = df[df.team != team]
    ax.scatter(other.xgf_pct, other.gf_pct, s=40, color=MUTED, alpha=0.7, label="other teams")
    me = df[df.team == team]
    ax.scatter(me.xgf_pct, me.gf_pct, s=110, color=RED, edgecolors=INK, zorder=3, label=team)
    for _, r in me.iterrows():
        ax.annotate(
            team,
            (r.xgf_pct, r.gf_pct),
            xytext=(8, -4),
            textcoords="offset points",
            color=INK,
            fontweight="bold",
        )
    lo, hi = df[["xgf_pct", "gf_pct"]].min().min() - 0.01, df[["xgf_pct", "gf_pct"]].max().max()
    ax.plot([lo, hi + 0.01], [lo, hi + 0.01], ls="--", color=MUTED, lw=1)
    ax.axhline(0.5, color="#e0dcd7", lw=1)
    ax.axvline(0.5, color="#e0dcd7", lw=1)
    ax.set(xlabel="xG share (xGF%)", ylabel="Goal share (GF%)", title=title)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.legend(frameon=False, loc="upper left")
    fig.savefig(path)
    plt.close(fig)


def chart_shot_map(shots: pd.DataFrame, team: str, path: Path, title: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, (label, df, color) in zip(
        axes,
        [
            (f"{team} shots", shots[shots.team == team], RED),
            (f"Opponent shots vs {team}", shots[shots.team != team], STEEL),
        ],
        strict=True,
    ):
        draw_half_rink(ax)
        miss = df[~df.is_goal]
        goal = df[df.is_goal]
        ax.scatter(miss.x_norm, miss.y_norm, s=miss.xg * 600 + 6, color=color, alpha=0.35, lw=0)
        ax.scatter(
            goal.x_norm,
            goal.y_norm,
            s=goal.xg * 600 + 6,
            color=color,
            edgecolors=INK,
            lw=1.2,
            alpha=0.95,
        )
        ax.set_title(
            f"{label}: {len(df)} unblocked, {df.xg.sum():.1f} xG, {int(df.is_goal.sum())} goals",
            fontsize=10,
        )
    fig.suptitle(title, x=0.02, ha="left", fontweight="bold")
    fig.text(0.02, 0.01, "Marker area ∝ xG. Outlined = goal.", color=MUTED, fontsize=8)
    fig.savefig(path)
    plt.close(fig)


def chart_recap(shots: pd.DataFrame, teams: list[str], path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    end = max(3600, int(shots.game_seconds.max()) + 30)
    for team, color in zip(teams, [RED, STEEL], strict=True):
        df = shots[shots.team == team].sort_values("game_seconds")
        xs = [0, *df.game_seconds.tolist(), end]
        ys = [0, *df.xg.cumsum().tolist(), df.xg.sum()]
        ax.step(xs, ys, where="post", color=color, label=f"{team} ({df.xg.sum():.2f} xG)")
        g = df[df.is_goal]
        ax.scatter(
            g.game_seconds, df.xg.cumsum()[df.is_goal], s=80, color=color, edgecolors=INK, zorder=3
        )
    for p in (1200, 2400, 3600):
        ax.axvline(p, color="#e0dcd7", lw=1)
    ax.set_xticks(
        [0, 1200, 2400, 3600][: 1 + end // 1200], ["0:00", "P2", "P3", "OT"][: 1 + end // 1200]
    )
    ax.set(ylabel="Cumulative xG", title=title, xlim=(0, end))
    ax.legend(frameon=False, loc="upper left")
    fig.text(0.02, -0.02, "Dots mark goals.", color=MUTED, fontsize=8)
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- markdown


def fmt(v, spec: str = ".1f", empty: str = "–") -> str:
    return empty if v is None or pd.isna(v) else format(v, spec)


def game_recap(con, settings: Settings, figs: Path, rel: str) -> str:
    team, cur = settings.team, settings.current_season
    game = con.execute(
        "select * from gold.team_games where team = ? and season = ? "
        "order by game_date desc, game_id desc limit 1",
        [team, cur],
    ).df()
    if game.empty:
        return ""
    g = game.iloc[0]
    shots = con.execute("select * from gold.shots_scored where game_id = ?", [int(g.game_id)]).df()
    venue = "vs" if g.is_home else "@"
    score = f"{g.result} {g.final_gf}-{g.final_ga}"
    title = f"{team} {venue} {g.opponent}, {g.game_date:%b %d, %Y}: {score}"
    chart_recap(shots, [team, g.opponent], figs / "game_recap_xg.png", title)

    periods = (
        shots.assign(period=shots.period.map(lambda p: "OT" if p > 3 else f"P{p}"))
        .pivot_table(index="team", columns="period", values="xg", aggfunc="sum", fill_value=0)
        .reindex([team, g.opponent])
    )
    periods = periods[sorted(periods.columns, key=lambda c: (c == "OT", c))]
    periods["Total"] = periods.sum(axis=1)
    period_table = periods.map(lambda v: f"{v:.2f}").reset_index().rename(columns={"team": "xG"})

    top = shots.sort_values("xg", ascending=False).head(5)
    chances = pd.DataFrame(
        {
            "Time": [clock(p, t) for p, t in zip(top.period, top.game_seconds, strict=True)],
            "Team": top.team,
            "Shooter": top.shooter,
            "Type": top.shot_type,
            "Dist (ft)": top.distance.map(lambda d: f"{d:.0f}"),
            "Situation": top.manpower,
            "xG": top.xg.map(lambda v: f"{v:.2f}"),
            "Result": top.is_goal.map({True: "GOAL", False: ""}),
        }
    )
    det = shots[shots.team == team]
    opp = shots[shots.team == g.opponent]
    verdict = (
        f"{team} {'won' if det.xg.sum() > opp.xg.sum() else 'lost'} the expected-goals battle "
        f"{det.xg.sum():.2f}-{opp.xg.sum():.2f} on {len(det)}-{len(opp)} unblocked attempts "
        f"and {'won' if g.result == 'W' else 'lost'} the game {g.final_gf}-{g.final_ga}"
        f"{DECIDED.get(g.decided_in, '')}."
    )
    md = f"""### Game recap: {title}

{verdict}

![xG timeline]({rel}/game_recap_xg.png)

{md_table(period_table)}

**Top chances**

{md_table(chances)}
"""
    return md


def findings(con, settings: Settings, metrics: dict, figs: Path, rel: str) -> str:
    team, cur, test = settings.team, settings.current_season, settings.test_season
    games = con.execute(
        "select * from gold.team_games where team = ? and season = ? order by team_game_number",
        [team, cur],
    ).df()
    splits = (
        con.execute(
            "select * from gold.team_season_splits where team = ? and season = ?", [team, cur]
        )
        .df()
        .set_index("strength")
    )
    if games.empty:
        return f"_No completed {season_label(cur)} games for {team} yet._"

    n_teams = con.execute(
        "select count(*) from gold.team_season_splits where season = ? and strength = 'all'", [cur]
    ).fetchone()[0]
    rec = games.result.value_counts()
    a = splits.loc["all"]
    s5 = splits.loc["5v5"] if "5v5" in splits.index else None

    chart_xg_by_game(
        games,
        team,
        figs / "xg_by_game.png",
        f"{team} {season_label(cur)}: expected vs actual goals, game by game",
    )
    league = con.execute(
        "select * from gold.team_season_splits where season = ? and strength = 'all'", [test]
    ).df()
    chart_league_scatter(
        league,
        team,
        figs / "league_xg_vs_goals.png",
        f"{season_label(test)}: xG share vs goal share, all 32 teams",
    )
    shots = con.execute(
        "select * from gold.shots_scored where season = ? and ? in (team, opponent)", [cur, team]
    ).df()
    chart_shot_map(
        shots, team, figs / "shot_map.png", f"{team} games, {season_label(cur)} season to date"
    )

    def split_row(name: str, label: str) -> list:
        if name not in splits.index:
            return [label, "0", "–", "–", "–", "–", "–"]
        r = splits.loc[name]
        return [
            label,
            int(r.games),
            fmt(r.xgf),
            int(r.gf),
            fmt(r.xga),
            int(r.ga),
            fmt(r.xgf_pct * 100) + "%",
        ]

    split_table = pd.DataFrame(
        [
            split_row("5v5", "5v5"),
            split_row("PP", "Power play"),
            split_row("SH", "Shorthanded"),
            split_row("other", "Other (4v4, 3v3, EA)"),
            split_row("all", "All situations"),
        ],
        columns=["Situation", "GP", "xGF", "GF", "xGA", "GA", "xGF%"],
    )

    cards = con.execute("select * from gold.player_cards order by card_name, season desc").df()
    card_rows = []
    for r in cards.itertuples():
        if pd.isna(r.games_played):
            card_rows.append([r.card_name, season_label(r.season), 0, *["–"] * 6])
            continue
        card_rows.append(
            [
                r.card_name,
                season_label(r.season),
                int(r.games_played),
                f"{int(r.goals)}-{int(r.assists)}-{int(r.points)}",
                fmt(r.toi_per_game_min),
                int(r.shots_on_goal),
                fmt(r.ixg, ".2f"),
                fmt(r.goals_above_ixg, "+.2f"),
                fmt(r.oi_xgf_pct_5v5 * 100) + "%",
            ]
        )
    card_table = pd.DataFrame(
        card_rows,
        columns=[
            "Player",
            "Season",
            "GP",
            "G-A-P",
            "TOI/GP",
            "SOG",
            "ixG",
            "G − ixG",
            "5v5 on-ice xGF%",
        ],
    )

    test_m = metrics["test"]
    mp = metrics.get("moneypuck_benchmark_test") or {}
    recap = game_recap(con, settings, figs, rel)
    me_league = league[league.team == team]
    league_line = ""
    if not me_league.empty:
        r = me_league.iloc[0]
        league_line = (
            f"For context, in {season_label(test)} {team} posted a {r.xgf_pct:.1%} xG share "
            f"(rank {int(r.xgf_pct_rank)} of {len(league)}), "
            f"scored {abs(r.finishing_above_xg):.1f} "
            f"{'fewer' if r.finishing_above_xg < 0 else 'more'} goals than its xG, and allowed "
            f"{abs(r.goaltending_above_xg):.1f} "
            f"{'fewer' if r.goaltending_above_xg > 0 else 'more'} than its xGA.\n\n"
        )

    finishing = a.gf - a.xgf
    shift_games = con.execute(
        "select count(distinct s.game_id) from silver.shifts s join silver.games g using (game_id) "
        "where g.season = ? and ? in (g.home_team, g.away_team)",
        [cur, team],
    ).fetchone()[0]
    five_line = f" At 5v5 the xG share is {s5.xgf_pct:.1%}." if s5 is not None else ""
    mp_line = (
        f"On {mp['matched_shots']:,} shots matched to MoneyPuck, shot-level correlation with "
        f"their public xG is **{mp['shot_level_correlation']:.2f}** (our log loss "
        f"{mp['ours_log_loss']:.4f} vs. MoneyPuck {mp['moneypuck_log_loss']:.4f})."
        if mp
        else ""
    )
    allowed_vs_xg = a.ga - a.xga
    return f"""_Generated by `make pipeline` from data through {games.game_date.max():%B %d, %Y}.
Every number below is queried from the warehouse; none are typed by hand._

#### {team} {season_label(cur)} season to date

**{len(games)} GP, {rec.get("W", 0)}-{rec.get("L", 0)}-{rec.get("OTL", 0)}.**
{team} has generated **{a.xgf:.1f} xG** and allowed **{a.xga:.1f} xGA**
({a.xgf_pct:.1%} xG share, rank {int(a.xgf_pct_rank)} of {n_teams}). On those same shots they've
scored **{int(a.gf)}** goals against {a.xgf:.1f} expected ({finishing:+.1f}) and allowed
**{int(a.ga)}** against {a.xga:.1f} expected ({allowed_vs_xg:+.1f}).{five_line}

![xG by game]({rel}/xg_by_game.png)

{md_table(split_table)}

![Shot map]({rel}/shot_map.png)

#### Player cards

{md_table(card_table)}

_TOI and on-ice numbers come from official NHL shift charts, joined to every shot by game clock.
The NHL has published shift charts for {shift_games} of {team}'s {len(games)} games this season, so
TOI/GP and 5v5 on-ice xGF% use those games only. "–" means the player has not dressed._

#### League context and the xG model

{league_line}![League xG vs goals]({rel}/league_xg_vs_goals.png)

On the held-out {season_label(test)} season ({test_m["shots"]:,} unblocked shots), the model
scores **log loss {test_m["log_loss"]:.4f}** vs. a {test_m["baseline_log_loss"]:.4f}
constant-rate baseline, **ROC AUC {test_m["roc_auc"]:.3f}**, and predicts
{test_m["expected_goals"]:,.0f} goals against {test_m["goals"]:,} actual.
{mp_line}

![Calibration](models/xg_calibration.png)

{recap}"""


def update_readme(readme: Path, section: str) -> None:
    if not readme.exists():
        return
    text = readme.read_text()
    if MARKER.search(text):
        readme.write_text(MARKER.sub(lambda m: f"{m[1]}\n{section}\n{m[3]}", text))


def run(con: duckdb.DuckDBPyConnection, settings: Settings, metrics: dict) -> None:
    out = settings.output_dir
    export_tables(con, settings, out / "exports")
    figs = out / "reports" / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    section = findings(con, settings, metrics, figs, "reports/figures")
    (out / "reports" / "findings.md").write_text(
        "# Findings\n\n"
        + section.replace("](reports/figures/", "](figures/").replace("](models/", "](../models/")
        + "\n"
    )
    update_readme(out / "README.md", section)
    data_through = con.execute(
        "select max(game_date) from gold.team_games where team = ? and season = ?",
        [settings.team, settings.current_season],
    ).fetchone()[0]
    meta = {
        "refreshed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_through": str(data_through) if data_through else None,
        "team": settings.team,
        "current_season": settings.current_season,
        "test_season": settings.test_season,
        "model_test_metrics": metrics["test"],
        "moneypuck_benchmark": metrics.get("moneypuck_benchmark_test"),
    }
    (out / "exports" / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
