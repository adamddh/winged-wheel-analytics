"""Winged Wheel Analytics dashboard. Reads only the pipeline's gold exports (exports/*.parquet)."""

import json
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

EXPORTS = Path(__file__).resolve().parent.parent / "exports"
REPO = "https://github.com/adamddh/winged-wheel-analytics"
TEAM = "DET"

RED = "#C8102E"  # Detroit
BLUE = "#1F6FB2"  # opponents
INK = "#1B1F24"
BOARD = "#6B7785"
ICE = "#F2F6F8"
LINE = "#D5DEE4"

TEAM_NAMES = {
    "ANA": "Anaheim",
    "BOS": "Boston",
    "BUF": "Buffalo",
    "CAR": "Carolina",
    "CBJ": "Columbus",
    "CGY": "Calgary",
    "CHI": "Chicago",
    "COL": "Colorado",
    "DAL": "Dallas",
    "DET": "Detroit",
    "EDM": "Edmonton",
    "FLA": "Florida",
    "LAK": "Los Angeles",
    "MIN": "Minnesota",
    "MTL": "Montréal",
    "NJD": "New Jersey",
    "NSH": "Nashville",
    "NYI": "the Islanders",
    "NYR": "the Rangers",
    "OTT": "Ottawa",
    "PHI": "Philadelphia",
    "PIT": "Pittsburgh",
    "SEA": "Seattle",
    "SJS": "San Jose",
    "STL": "St. Louis",
    "TBL": "Tampa Bay",
    "TOR": "Toronto",
    "UTA": "Utah",
    "VAN": "Vancouver",
    "VGK": "Vegas",
    "WPG": "Winnipeg",
    "WSH": "Washington",
}
DECIDED = {"OT": " in overtime", "SO": " in a shootout"}
SITUATIONS = {"5v5": "5 on 5", "PP": "Power play", "SH": "Shorthanded", "other": "Other"}

st.set_page_config(page_title="Winged Wheel Analytics", page_icon="🏒", layout="wide")

st.html(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,300..900&display=swap');
:root { --red: #C8102E; --blue: #1F6FB2; --ink: #1B1F24; --board: #6B7785; --line: #D5DEE4; }
html, body, .stApp, .stMarkdown, .stHtml, p, li, td, th, label, input, button,
[data-testid="stWidgetLabel"], [data-baseweb="select"], [data-baseweb="tab"] {
  font-family: 'Archivo', system-ui, sans-serif;
}
.stApp { background: #F2F6F8; color: var(--ink); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.5rem; max-width: 1180px; }
.ww-top { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem;
  flex-wrap: wrap; color: var(--board); font-size: .85rem; }
.ww-mark { font-stretch: 62%; font-weight: 800; font-size: 1.15rem; color: var(--ink);
  letter-spacing: .01em; }
.ww-mark b { color: var(--red); font-weight: 800; }
.ww-h1 { font-stretch: 62%; font-weight: 900; font-size: clamp(2.6rem, 7vw, 5.2rem);
  line-height: .9; margin: 1.4rem 0 .6rem; color: var(--ink); }
.ww-lede { font-size: 1.12rem; line-height: 1.5; max-width: 62ch; margin: 0 0 1rem; }
.ww-lede strong { font-weight: 700; }
.ww-for { color: var(--red); font-weight: 700; }
.ww-against { color: var(--blue); font-weight: 700; }
.ww-caption { color: var(--board); font-size: .85rem; max-width: 72ch; line-height: 1.45; }
.ww-rink svg { width: 100%; height: auto; display: block; }
.ww-h2 { font-stretch: 75%; font-weight: 800; font-size: 1.7rem; margin: .4rem 0 .2rem; }
.ww-table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums;
  font-size: .95rem; }
.ww-table th { white-space: nowrap; text-align: right; font-weight: 600; color: var(--board);
  padding: .35rem .6rem;
  border-bottom: 2px solid var(--ink); }
.ww-table td { text-align: right; padding: .4rem .6rem; border-bottom: 1px solid var(--line); }
.ww-table .t { text-align: left; }
.ww-half svg { max-width: 340px; }
.ww-map svg { max-width: 640px; }
.ww-card { display: grid; grid-template-columns: auto 1fr; gap: 0 1.1rem; align-items: start;
  padding: 1.1rem 0 1.4rem; border-top: 2px solid var(--ink); }
.ww-num { font-stretch: 62%; font-weight: 900; font-size: 6.5rem; line-height: .8;
  color: transparent; -webkit-text-stroke: 2px var(--red); min-width: 1.2ch; }
.ww-name { font-stretch: 75%; font-weight: 800; font-size: 1.6rem; line-height: 1.05; }
.ww-pos { color: var(--board); font-size: .9rem; margin-bottom: .5rem; }
.ww-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .55rem 1rem;
  margin: 0; }
.ww-stats div { min-width: 0; }
.ww-stats dt { color: var(--board); font-size: .78rem; }
.ww-stats dd { margin: 0; font-stretch: 75%; font-weight: 700; font-size: 1.35rem;
  font-variant-numeric: tabular-nums; }
.ww-dnp { color: var(--board); font-size: .95rem; padding-top: .3rem; }
.ww-foot { color: var(--board); font-size: .85rem; line-height: 1.6; border-top: 1px solid
  var(--line); margin-top: 2.5rem; padding-top: 1rem; }
.ww-foot a, .ww-caption a { color: var(--ink); }
[data-baseweb="tab-list"] { gap: 1.4rem; }
[data-baseweb="tab"] p { font-stretch: 75%; font-weight: 700; font-size: 1.1rem; }
@media (max-width: 640px) { .ww-num { font-size: 4.5rem; } .ww-stats { grid-template-columns:
  repeat(2, minmax(0, 1fr)); } }
</style>
"""
)


# --------------------------------------------------------------------------- data


@st.cache_data(ttl=3600)
def load() -> tuple[dict[str, pd.DataFrame], dict]:
    names = ["team_games", "team_season_splits", "player_cards", "shots"]
    tables = {n: pd.read_parquet(EXPORTS / f"{n}.parquet") for n in names}
    return tables, json.loads((EXPORTS / "meta.json").read_text())


def season_label(season: int) -> str:
    return f"{season // 10000}-{str(season % 10000)[2:]}"


def fmt(v, spec: str = ".1f", empty: str = "–") -> str:
    return empty if v is None or pd.isna(v) else format(v, spec)


def table_html(rows: list[list], header: list[str], text_cols: int = 1) -> str:
    """The first `text_cols` columns are left-aligned text; the rest are right-aligned numbers."""

    def cell(tag: str, i: int, v) -> str:
        cls = ' class="t"' if i < text_cols else ""
        return f"<{tag}{cls}>{escape(str(v))}</{tag}>"

    head = "".join(cell("th", i, h) for i, h in enumerate(header))
    body = "".join(
        "<tr>" + "".join(cell("td", i, c) for i, c in enumerate(r)) + "</tr>" for r in rows
    )
    return f'<table class="ww-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


# --------------------------------------------------------------------------- rink


def _rink_lines() -> str:
    """NHL rink to scale in feet: 200 x 85, 28 ft corner radius, origin at center ice."""
    faceoff = "".join(
        f'<circle cx="{x}" cy="{y}" r="15" fill="none" stroke="{RED}" stroke-opacity=".28" '
        f'stroke-width=".5"/><circle cx="{x}" cy="{y}" r="1" fill="{RED}" fill-opacity=".35"/>'
        for x in (-69, 69)
        for y in (-22, 22)
    )
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="1" fill="{RED}" fill-opacity=".35"/>'
        for x in (-20, 20)
        for y in (-22, 22)
    )
    goals = "".join(
        f'<line x1="{s * 89}" y1="-36.75" x2="{s * 89}" y2="36.75" stroke="{RED}" '
        f'stroke-opacity=".4" stroke-width=".35"/>'
        f'<path d="M{s * 89},-6 A6,6 0 0,{0 if s > 0 else 1} {s * 89},6 Z" fill="#DCEBF5"/>'
        f'<rect x="{89 if s > 0 else -92.3}" y="-3" width="3.3" height="6" fill="none" '
        f'stroke="{INK}" stroke-opacity=".55" stroke-width=".4"/>'
        for s in (1, -1)
    )
    return (
        f'<rect x="-100" y="-42.5" width="200" height="85" rx="28" fill="#FBFDFE" '
        f'stroke="#AAB8C2" stroke-width=".8"/>'
        f'<rect x="-.5" y="-42.5" width="1" height="85" fill="{RED}" fill-opacity=".3"/>'
        f'<rect x="-25.5" y="-42.5" width="1" height="85" fill="{BLUE}" fill-opacity=".3"/>'
        f'<rect x="24.5" y="-42.5" width="1" height="85" fill="{BLUE}" fill-opacity=".3"/>'
        f'<circle cx="0" cy="0" r="15" fill="none" stroke="{BLUE}" stroke-opacity=".3" '
        f'stroke-width=".5"/>{faceoff}{dots}{goals}'
    )


def _shot_marks(shots: pd.DataFrame, color: str, mirror: bool) -> str:
    marks = []
    for s in shots.sort_values("is_goal").itertuples():
        x, y = (-s.x_norm, s.y_norm) if mirror else (s.x_norm, -s.y_norm)
        r = 0.7 + 4.5 * s.xg**0.5
        tip = escape(
            f"{s.shooter or 'Unknown'}, {s.shot_type} from {s.distance:.0f} ft "
            f"({SITUATIONS.get(s.manpower, s.manpower)}): {s.xg:.2f} xG"
            f"{', goal' if s.is_goal else ''}"
        )
        style = (
            f'fill="{color}" fill-opacity=".95" stroke="{INK}" stroke-width=".45"'
            if s.is_goal
            else f'fill="{color}" fill-opacity=".3"'
        )
        marks.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" {style}><title>{tip}</title></circle>'
        )
    return "".join(marks)


def rink(right: pd.DataFrame, left: pd.DataFrame | None = None, color: str = RED) -> str:
    """Full rink: `right` attacks the right net, `left` (rotated 180°) attacks the left net.
    Without `left`, only the offensive half is shown."""
    box = "-101 -43.5 202 87" if left is not None else "-1 -43.5 102 87"
    body = _rink_lines() + _shot_marks(right, color, mirror=False)
    if left is not None:
        body += _shot_marks(left, BLUE, mirror=True)
    svg = f'<svg viewBox="{box}" role="img" aria-label="Shot map">{body}</svg>'
    return f'<div class="ww-rink">{svg}</div>'


def show_rink(*args, **kwargs) -> None:
    # st.html sanitizes SVG away; markdown keeps inline SVG (and its hover <title>s).
    st.markdown(rink(*args, **kwargs), unsafe_allow_html=True)


# --------------------------------------------------------------------------- charts


def chart_style(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure(font="Archivo", background="transparent")
        .configure_view(stroke=None)
        .configure_axis(
            labelColor=BOARD,
            titleColor=BOARD,
            gridColor="#E3EAEE",
            domainColor="#AAB8C2",
            labelFontSize=12,
            titleFontSize=12,
            titleFontWeight=500,
            tickColor="#AAB8C2",
        )
        .configure_legend(
            labelColor=INK,
            titleColor=BOARD,
            labelFontSize=12,
            orient="top",
            symbolStrokeWidth=2,
        )
    )


def xg_by_game_chart(games: pd.DataFrame) -> alt.Chart:
    long = pd.concat(
        [
            games.assign(series="Detroit expected goals", value=games.xgf, kind="xG"),
            games.assign(series="Opponent expected goals", value=games.xga, kind="xG"),
            games.assign(series="Detroit goals", value=games.gf, kind="goals"),
            games.assign(series="Opponent goals", value=games.ga, kind="goals"),
        ]
    )
    long["value"] = long.value.round(2)
    color = alt.Color(
        "series:N",
        legend=alt.Legend(title=None),
        scale=alt.Scale(
            domain=[
                "Detroit expected goals",
                "Opponent expected goals",
                "Detroit goals",
                "Opponent goals",
            ],
            range=[RED, BLUE, RED, BLUE],
        ),
    )
    x = alt.X("label:N", sort=list(games.label), title=None, axis=alt.Axis(labelAngle=0))
    tooltip = [
        alt.Tooltip("label:N", title="Game"),
        alt.Tooltip("series:N", title=""),
        alt.Tooltip("value:Q", title="Value", format=".2f"),
    ]
    lines = (
        alt.Chart(long[long.kind == "xG"])
        .mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=70, filled=True))
        .encode(
            x=x, y=alt.Y("value:Q", title="Goals and expected goals"), color=color, tooltip=tooltip
        )
    )
    goals = (
        alt.Chart(long[long.kind == "goals"])
        .mark_point(size=110, filled=False, strokeWidth=2)
        .encode(
            x=x,
            y="value:Q",
            color=color,
            shape=alt.Shape("series:N", legend=None, scale=alt.Scale(range=["circle", "square"])),
            tooltip=tooltip,
        )
    )
    return chart_style((lines + goals).properties(height=320))


def league_chart(splits: pd.DataFrame) -> alt.Chart:
    df = splits[splits.strength == "all"].assign(
        gf_pct=lambda d: d.gf / (d.gf + d.ga), is_det=lambda d: d.team == TEAM
    )
    base = alt.Chart(df).encode(
        x=alt.X(
            "xgf_pct:Q",
            title="Share of expected goals",
            axis=alt.Axis(format=".0%"),
            scale=alt.Scale(zero=False),
        ),
        y=alt.Y(
            "gf_pct:Q",
            title="Share of actual goals",
            axis=alt.Axis(format=".0%"),
            scale=alt.Scale(zero=False),
        ),
        tooltip=[
            alt.Tooltip("team:N", title="Team"),
            alt.Tooltip("xgf_pct:Q", title="xG share", format=".1%"),
            alt.Tooltip("gf_pct:Q", title="Goal share", format=".1%"),
            alt.Tooltip("games:Q", title="Games"),
        ],
    )
    others = base.transform_filter("!datum.is_det").mark_circle(
        size=70, color="#9AA7B1", opacity=0.8
    )
    det = base.transform_filter("datum.is_det").mark_circle(
        size=200, color=RED, stroke=INK, strokeWidth=1, opacity=1
    )
    label = (
        base.transform_filter("datum.is_det")
        .mark_text(align="left", dx=10, fontWeight=700, color=INK, fontSize=13)
        .encode(text="team:N")
    )
    lo = float(min(df.xgf_pct.min(), df.gf_pct.min())) - 0.01
    hi = float(max(df.xgf_pct.max(), df.gf_pct.max())) + 0.01
    diag = (
        alt.Chart(pd.DataFrame({"a": [lo, hi]}))
        .mark_line(strokeDash=[4, 4], color="#AAB8C2", strokeWidth=1)
        .encode(x="a:Q", y="a:Q")
    )
    return chart_style((diag + others + det + label).properties(height=360))


def timeline_chart(shots: pd.DataFrame, teams: list[str]) -> alt.Chart:
    end = max(3600, int(shots.game_seconds.max()) + 30)
    rows = []
    for team in teams:
        df = shots[shots.team == team].sort_values("game_seconds")
        cum = df.xg.cumsum()
        rows.append(
            pd.DataFrame({"team": team, "t": 0, "cum": 0.0, "goal": False, "who": ""}, index=[0])
        )
        rows.append(
            pd.DataFrame(
                {
                    "team": team,
                    "t": df.game_seconds,
                    "cum": cum,
                    "goal": df.is_goal,
                    "who": df.shooter.fillna(""),
                }
            )
        )
        rows.append(
            pd.DataFrame(
                {
                    "team": team,
                    "t": end,
                    "cum": float(cum.iloc[-1]) if len(cum) else 0.0,
                    "goal": False,
                    "who": "",
                },
                index=[0],
            )
        )
    df = pd.concat(rows, ignore_index=True)
    df["minute"] = df.t / 60
    color = alt.Color(
        "team:N", legend=alt.Legend(title=None), scale=alt.Scale(domain=teams, range=[RED, BLUE])
    )
    x = alt.X(
        "minute:Q",
        title="Game minute",
        scale=alt.Scale(domain=[0, end / 60], nice=False),
        axis=alt.Axis(values=[0, 20, 40, 60, 65][: 3 + (end > 3600) + 1]),
    )
    line = (
        alt.Chart(df)
        .mark_line(interpolate="step-after", strokeWidth=2.5)
        .encode(x=x, y=alt.Y("cum:Q", title="Cumulative expected goals"), color=color)
    )
    goals = (
        alt.Chart(df[df.goal])
        .mark_circle(size=140, stroke=INK, strokeWidth=1, opacity=1)
        .encode(
            x=x,
            y="cum:Q",
            color=color,
            tooltip=[
                alt.Tooltip("who:N", title="Goal"),
                alt.Tooltip("minute:Q", format=".1f", title="Minute"),
            ],
        )
    )
    rules = alt.Chart(pd.DataFrame({"m": [20, 40, 60]})).mark_rule(color="#D5DEE4").encode(x="m:Q")
    return chart_style((rules + line + goals).properties(height=300))


# --------------------------------------------------------------------------- page

tables, meta = load()
games_all = tables["team_games"]
shots_all = tables["shots"]
cur, test = meta["current_season"], meta["test_season"]
det_games = games_all[(games_all.team == TEAM)].sort_values(["season", "team_game_number"])

refreshed = datetime.fromisoformat(meta["refreshed_at"]).astimezone(ZoneInfo("America/Detroit"))
through = pd.Timestamp(meta["data_through"]) if meta.get("data_through") else None

st.html(
    f"""<div class="ww-top"><span class="ww-mark">Winged Wheel <b>Analytics</b></span>
<span>Games through {through:%B %-d, %Y}. Last data refresh {refreshed:%b %-d, %-I:%M %p} ET;
refreshed every morning.</span></div>"""
    if through is not None
    else '<div class="ww-top"><span class="ww-mark">Winged Wheel <b>Analytics</b></span></div>'
)

season_games = det_games[det_games.season == cur]
splits_all = tables["team_season_splits"]
cur_split = splits_all[(splits_all.season == cur) & (splits_all.team == TEAM)].set_index("strength")

if season_games.empty:
    st.html(f'<h1 class="ww-h1">Detroit, {season_label(cur)}</h1>')
    st.info("No completed Red Wings games this season yet. The next refresh picks them up.")
    st.stop()

rec = season_games.result.value_counts()
record = f"{rec.get('W', 0)}-{rec.get('L', 0)}-{rec.get('OTL', 0)}"
a = cur_split.loc["all"]
n_teams = int((splits_all[(splits_all.season == cur) & (splits_all.strength == "all")]).shape[0])
cur_shots = shots_all[shots_all.season == cur]
det_shots = cur_shots[cur_shots.team == TEAM]
opp_shots = cur_shots[cur_shots.opponent == TEAM]

st.html(
    f"""<h1 class="ww-h1">Detroit, {season_label(cur)} so far</h1>
<p class="ww-lede">{len(season_games)} games, {record}.
Detroit has created <span class="ww-for">{a.xgf:.1f} expected goals</span> and allowed
<span class="ww-against">{a.xga:.1f}</span>, a {a.xgf_pct:.1%} share that ranks
{int(a.xgf_pct_rank)} of {n_teams}. On those shots they've scored <strong>{int(a.gf)}</strong>
and allowed <strong>{int(a.ga)}</strong>.</p>"""
)
show_rink(det_shots, opp_shots)
st.html(
    """<p class="ww-caption">Every unblocked shot of the season on one sheet of ice. Detroit
shoots right, opponents shoot left at Detroit's net. Dot area is expected goals; outlined dots
went in. Hover a dot for the shooter.</p>"""
)

tab_season, tab_games, tab_players, tab_maps = st.tabs(
    ["Season", "Game by game", "Players", "Shot maps"]
)

with tab_season:
    sg = season_games.copy()
    sg["label"] = [
        f"{d:%b %-d} {'vs' if h else '@'} {o}"
        for d, h, o in zip(sg.game_date, sg.is_home, sg.opponent, strict=True)
    ]
    st.html('<h2 class="ww-h2">Expected and actual goals, game by game</h2>')
    st.altair_chart(xg_by_game_chart(sg), use_container_width=True, theme=None)

    left, right = st.columns([1, 1], gap="large")
    with left:
        st.html('<h2 class="ww-h2">By situation</h2>')
        rows = []
        for key, name in [
            ("5v5", "5 on 5"),
            ("PP", "Power play"),
            ("SH", "Shorthanded"),
            ("other", "4v4, 3v3, 6v5"),
            ("all", "All"),
        ]:
            if key in cur_split.index:
                r = cur_split.loc[key]
                rows.append(
                    [name, fmt(r.xgf), int(r.gf), fmt(r.xga), int(r.ga), fmt(r.xgf_pct * 100) + "%"]
                )
        st.html(
            table_html(
                rows,
                ["Situation", "xG for", "Goals for", "xG against", "Goals against", "xG share"],
            )
        )
        st.html(
            '<p class="ww-caption">On the power play the useful numbers are xG for and goals '
            "for; shorthanded, xG against and goals against. The share column is most "
            "meaningful at 5 on 5.</p>"
        )
    with right:
        which = st.segmented_control(
            "League view",
            [season_label(cur), season_label(test)],
            default=season_label(cur),
            key="league_season",
        )
        season_pick = cur if which != season_label(test) else test
        st.html(f'<h2 class="ww-h2">Where Detroit sits, {season_label(season_pick)}</h2>')
        st.altair_chart(
            league_chart(splits_all[splits_all.season == season_pick]),
            use_container_width=True,
            theme=None,
        )
        st.html(
            '<p class="ww-caption">Above the dashed line, a team is scoring more of the goals '
            "than its share of chances predicts (finishing, goaltending, or luck).</p>"
        )

with tab_games:
    options = det_games[det_games.season == cur].sort_values("game_date", ascending=False)
    labels = {
        r.game_id: f"{r.game_date:%b %-d} {'vs' if r.is_home else '@'} "
        f"{TEAM_NAMES.get(r.opponent, r.opponent)}: {r.result} {r.final_gf}-{r.final_ga}"
        for r in options.itertuples()
    }
    gid = st.selectbox("Game", list(labels), format_func=labels.get)
    g = options[options.game_id == gid].iloc[0]
    gshots = shots_all[shots_all.game_id == gid]
    d_xg = gshots[gshots.team == TEAM].xg.sum()
    o_xg = gshots[gshots.team == g.opponent].xg.sum()
    verb = {"W": "Won", "L": "Lost", "OTL": "Lost"}[g.result]
    st.html(
        f"""<h2 class="ww-h2">{verb} {g.final_gf}-{g.final_ga}{DECIDED.get(g.decided_in, "")}
{"against" if g.is_home else "at"} {TEAM_NAMES.get(g.opponent, g.opponent)}</h2>
<p class="ww-lede">Detroit <span class="ww-for">{d_xg:.2f} xG</span> on
{(gshots.team == TEAM).sum()} unblocked shots, {g.opponent}
<span class="ww-against">{o_xg:.2f} xG</span> on {(gshots.team == g.opponent).sum()}.</p>"""
    )
    c1, c2 = st.columns([1.15, 1], gap="large")
    with c1:
        st.altair_chart(
            timeline_chart(gshots, [TEAM, g.opponent]), use_container_width=True, theme=None
        )
    with c2:
        show_rink(gshots[gshots.team == TEAM], gshots[gshots.team == g.opponent])
    top = gshots.sort_values("xg", ascending=False).head(6)
    rows = [
        [
            f"{'OT' if r.period > 3 else f'P{r.period}'} "
            f"{(r.game_seconds - (r.period - 1) * 1200) // 60}:"
            f"{(r.game_seconds - (r.period - 1) * 1200) % 60:02d}",
            r.team,
            r.shooter or "",
            r.shot_type,
            SITUATIONS.get(r.manpower, r.manpower),
            "Goal" if r.is_goal else "",
            f"{r.distance:.0f} ft",
            f"{r.xg:.2f}",
        ]
        for r in top.itertuples()
    ]
    st.html('<h2 class="ww-h2">Best chances</h2>')
    st.html(
        table_html(
            rows,
            ["Time", "Team", "Shooter", "Shot", "Situation", "Result", "Distance", "xG"],
            text_cols=6,
        )
    )

with tab_players:
    pick = st.segmented_control(
        "Season",
        [season_label(cur), season_label(test)],
        default=season_label(cur),
        key="player_season",
    )
    p_season = test if pick == season_label(test) else cur
    cards = tables["player_cards"]
    cards = cards[cards.season == p_season].sort_values("card_name")
    for i, c in enumerate(cards.itertuples()):
        if i % 2 == 0:  # a new row per pair keeps reading order when columns stack on phones
            cols = st.columns(2, gap="large")
        with cols[i % 2]:
            num = "" if pd.isna(c.sweater_number) else int(c.sweater_number)
            pos = {"C": "Center", "L": "Left wing", "R": "Right wing", "D": "Defense"}.get(
                c.position, ""
            )
            if pd.isna(c.games_played):
                body = (
                    f'<div class="ww-dnp">Hasn\'t dressed in {season_label(p_season)} '
                    "yet. Switch seasons to see last year.</div>"
                )
            else:
                stats = [
                    ("Games", int(c.games_played)),
                    ("Goals-assists", f"{int(c.goals)}-{int(c.assists)}"),
                    ("Points", int(c.points)),
                    (
                        "Ice time per game",
                        fmt(c.toi_per_game_min) + " min"
                        if not pd.isna(c.toi_per_game_min)
                        else "–",
                    ),
                    ("Individual xG", fmt(c.ixg, ".2f")),
                    ("Goals vs. xG", fmt(c.goals_above_ixg, "+.2f")),
                    ("Shots on goal", int(c.shots_on_goal)),
                    ("xG per 60", fmt(c.ixg_per_60, ".2f")),
                    (
                        "5v5 on-ice xG share",
                        fmt(c.oi_xgf_pct_5v5 * 100) + "%" if not pd.isna(c.oi_xgf_pct_5v5) else "–",
                    ),
                ]
                body = (
                    '<dl class="ww-stats">'
                    + "".join(
                        f"<div><dt>{escape(k)}</dt><dd>{escape(str(v))}</dd></div>"
                        for k, v in stats
                    )
                    + "</dl>"
                )
            st.html(
                f"""<div class="ww-card"><div class="ww-num" aria-hidden="true">{num}</div>
<div><div class="ww-name">{escape(c.card_name)}</div><div class="ww-pos">{pos}{
                    f", #{num}" if num != "" else ""
                }</div>{body}</div></div>"""
            )
            mine = shots_all[(shots_all.season == p_season) & (shots_all.shooter == c.card_name)]
            if len(mine):
                st.markdown(f'<div class="ww-half">{rink(mine)}</div>', unsafe_allow_html=True)
    st.html(
        '<p class="ww-caption">Ice time and on-ice numbers come from official NHL shift charts, '
        "matched to every shot by game clock. The NHL hasn't published shift charts for every "
        "game, so those columns cover only games that have them.</p>"
    )

with tab_maps:
    f1, f2, f3 = st.columns([1, 1, 2])
    m_pick = f1.segmented_control(
        "Season",
        [season_label(cur), season_label(test)],
        default=season_label(cur),
        key="map_season",
    )
    m_season = test if m_pick == season_label(test) else cur
    side = f2.segmented_control(
        "Shots by", ["Detroit", "Opponents"], default="Detroit", key="map_side"
    )
    sits = f3.pills(
        "Situation",
        list(SITUATIONS.values()),
        selection_mode="multi",
        default=list(SITUATIONS.values()),
        key="map_sits",
    )
    pool = shots_all[shots_all.season == m_season]
    pool = pool[pool.team == TEAM] if side != "Opponents" else pool[pool.opponent == TEAM]
    wanted = [k for k, v in SITUATIONS.items() if v in (sits or [])]
    pool = pool[pool.manpower.isin(wanted)]
    if side != "Opponents":
        shooters = ["Everyone"] + sorted(pool.shooter.dropna().unique())
        who = st.selectbox("Shooter", shooters)
        if who != "Everyone":
            pool = pool[pool.shooter == who]
    map_color = BLUE if side == "Opponents" else RED
    if pool.empty:
        st.html(
            '<p class="ww-caption">No shots match these filters. Add a situation or pick '
            "another shooter.</p>"
        )
    else:
        st.html(
            f"""<p class="ww-lede">{len(pool)} unblocked shots, {pool.xg.sum():.1f} expected
goals, {int(pool.is_goal.sum())} goals.</p>"""
        )
        st.markdown(
            f'<div class="ww-map">{rink(pool, color=map_color)}</div>', unsafe_allow_html=True
        )

st.html(
    f"""<div class="ww-foot">Data: official NHL API (api-web.nhle.com) for schedules,
play-by-play and rosters; NHL shift charts (api.nhle.com); shot data courtesy of
<a href="https://moneypuck.com">MoneyPuck.com</a>, used only to validate the expected-goals
model. Expected goals come from this project's own logistic-regression model, trained on
2024-25 and tested on 2025-26. A GitHub Actions job rebuilds everything every morning at
12:00 UTC (7 a.m. Eastern in winter). Code, methods and data-quality checks are in the
<a href="{REPO}">repository</a>.</div>"""
)
