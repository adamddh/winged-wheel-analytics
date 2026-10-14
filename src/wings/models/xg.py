"""Expected-goals model: logistic regression on unblocked, non-empty-net shot attempts.

The fitted model is exported as a plain JSON spec (standardization stats, category levels,
coefficients) so it is human-readable, diffable in git, and scoreable without pickles.
"""

import json
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score  # noqa: E402

NUMERIC = ["distance", "log_distance", "angle"]
BINARY = ["is_rush"]
# First level of each list is the reference category (absorbed by the intercept).
CATEGORICAL = {
    "shot_type": [
        "wrist",
        "snap",
        "slap",
        "backhand",
        "tip-in",
        "deflected",
        "wrap-around",
        "other",
    ],
    "manpower": ["5v5", "PP", "SH", "other"],
    "score_state": [0, -2, -1, 1, 2],
    # Rebound timing matters more than the flag: 0-1s jam plays rarely score, 2-3s rebounds
    # catch the goalie moving (see docs/xg_model.md).
    "rebound": ["none", "quick", "delayed"],
}

SHOTS_SQL = """
    select shot_id, season, is_goal::integer as is_goal, distance, angle, shot_type, manpower,
        score_state, is_rush,
        case when rebound_seconds is null then 'none'
            when rebound_seconds <= 1 then 'quick' else 'delayed' end as rebound
    from gold.shots
    where not is_empty_net and distance is not null and angle is not null
"""


def load_shots(con: duckdb.DuckDBPyConnection, seasons: list[int] | None = None) -> pd.DataFrame:
    df = con.execute(SHOTS_SQL).df()
    return df[df.season.isin(seasons)] if seasons is not None else df


def _raw_features(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(log_distance=np.log1p(df.distance))


def design_matrix(df: pd.DataFrame, spec: dict) -> np.ndarray:
    df = _raw_features(df)
    cols = [(df[c].to_numpy(float) - spec["mean"][c]) / spec["scale"][c] for c in NUMERIC]
    cols += [df[c].to_numpy(float) for c in BINARY]
    for col, levels in CATEGORICAL.items():
        cols += [(df[col] == level).to_numpy(float) for level in levels[1:]]
    return np.column_stack(cols)


def feature_names() -> list[str]:
    names = NUMERIC + BINARY
    for col, levels in CATEGORICAL.items():
        names += [f"{col}={level}" for level in levels[1:]]
    return names


def fit(train: pd.DataFrame) -> dict:
    raw = _raw_features(train)
    spec = {
        "features": feature_names(),
        "reference": {c: levels[0] for c, levels in CATEGORICAL.items()},
        "mean": {c: float(raw[c].mean()) for c in NUMERIC},
        "scale": {c: float(raw[c].std()) for c in NUMERIC},
    }
    model = LogisticRegression(C=1.0, max_iter=5000)
    model.fit(design_matrix(train, spec), train.is_goal)
    spec["intercept"] = float(model.intercept_[0])
    spec["coef"] = dict(zip(spec["features"], map(float, model.coef_[0]), strict=True))
    return spec


def predict(df: pd.DataFrame, spec: dict) -> np.ndarray:
    coef = np.array([spec["coef"][f] for f in spec["features"]])
    z = design_matrix(df, spec) @ coef + spec["intercept"]
    return 1 / (1 + np.exp(-z))


def evaluate(y: np.ndarray, p: np.ndarray, base_rate: float) -> dict:
    return {
        "shots": int(len(y)),
        "goals": int(y.sum()),
        "expected_goals": round(float(p.sum()), 1),
        "log_loss": round(float(log_loss(y, p)), 5),
        "baseline_log_loss": round(float(log_loss(y, np.full(len(y), base_rate))), 5),
        "brier": round(float(brier_score_loss(y, p)), 5),
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
    }


def moneypuck_benchmark(con: duckdb.DuckDBPyConnection, season: int) -> dict | None:
    """Our xG vs MoneyPuck's public xG on the exact same matched shots of a season."""
    df = con.execute(
        """
        select x.xg, m.mp_xg, s.is_goal::integer as is_goal
        from gold.shots s
        join gold.shot_xg x using (shot_id)
        join silver.moneypuck_shots m
            on m.game_id = s.game_id and m.period = s.period
            and m.game_seconds = s.game_seconds and m.shooter_id = s.shooter_id
        where s.season = ?
        qualify count(*) over (partition by s.shot_id) = 1
        """,
        [season],
    ).df()
    if len(df) < 100 or df.is_goal.nunique() < 2:
        return None
    total = con.execute(
        "select count(*) from gold.shot_xg join gold.shots using (shot_id) where season = ?",
        [season],
    ).fetchone()[0]
    return {
        "matched_shots": int(len(df)),
        "match_rate": round(len(df) / total, 4),
        "shot_level_correlation": round(float(df.xg.corr(df.mp_xg)), 4),
        "ours_log_loss": round(float(log_loss(df.is_goal, df.xg)), 5),
        "moneypuck_log_loss": round(float(log_loss(df.is_goal, df.mp_xg)), 5),
    }


def plot_calibration(y: np.ndarray, p: np.ndarray, path: Path, title: str) -> list[dict]:
    obs, pred = calibration_curve(y, p, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(5.5, 5))
    hi = max(pred.max(), obs.max()) * 1.05
    ax.plot([0, hi], [0, hi], color="#9a9a9a", lw=1, ls="--", label="perfect calibration")
    ax.plot(pred, obs, "o-", color="#C8102E", lw=2, label="xG model (deciles)")
    ax.set(xlabel="Predicted goal probability", ylabel="Observed goal rate", title=title)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return [
        {"predicted": round(float(a), 4), "observed": round(float(b), 4)}
        for a, b in zip(pred, obs, strict=True)
    ]


def _table(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns)
    return head + "".join("\n| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(False))


def write_model_card(con: duckdb.DuckDBPyConnection, spec: dict, metrics: dict, path: Path):
    """Generated companion to docs/xg_model.md: every number here comes from this run."""
    seasons = ", ".join(map(str, spec["train_seasons"]))
    coefs = pd.DataFrame(
        [(f, round(c, 3), round(float(np.exp(c)), 2)) for f, c in spec["coef"].items()],
        columns=["feature", "coefficient", "odds ratio"],
    )
    evidence = con.execute(
        f"""
        select
            case when rebound_seconds is null then 'not a rebound'
                when rebound_seconds <= 1 then 'rebound, 0-1s (quick)'
                else 'rebound, 2-3s (delayed)' end as shot,
            count(*) as shots,
            round(avg(is_goal::int), 3) as goal_rate,
            round(avg(distance), 1) as avg_distance_ft
        from gold.shots
        where not is_empty_net and season in ({seasons})
        group by 1 order by 1
        """
    ).df()
    rush = con.execute(
        f"""
        select least(floor(distance / 15) * 15, 45)::int as distance_band_ft,
            round(avg(is_goal::int) filter (where is_rush), 3) as rush_goal_rate,
            round(avg(is_goal::int) filter (where not is_rush), 3) as other_goal_rate,
            count(*) filter (where is_rush) as rush_shots
        from gold.shots
        where not is_empty_net and season in ({seasons})
        group by 1 order by 1
        """
    ).df()
    calib = pd.DataFrame(metrics["calibration_test"])
    mp = metrics.get("moneypuck_benchmark_test")
    mp_table = _table(pd.DataFrame([mp])) if mp else "_not enough matched shots_"
    path.write_text(f"""# xG model card (generated)

_Written by `make pipeline`; see [docs/xg_model.md](../docs/xg_model.md) for the rationale._

Trained on {seasons}; evaluated on held-out {spec["test_season"]}.

## Metrics

{_table(pd.DataFrame([{"split": k, **metrics[k]} for k in ("train", "test")]))}

## Benchmark against MoneyPuck (held-out season, identical matched shots)

{mp_table}

## Coefficients

Numeric features are standardized (per 1 SD). Reference levels: {spec["reference"]}.
Intercept {spec["intercept"]:.3f}.

{_table(coefs)}

## Feature evidence (training seasons)

Rebound timing:

{_table(evidence)}

Rush vs. other shots at the same distance:

{_table(rush)}

## Calibration (held-out deciles)

{_table(calib)}

![calibration](xg_calibration.png)
""")


def run(con: duckdb.DuckDBPyConnection, settings, models_dir: Path) -> dict:
    shots = load_shots(con)
    train = shots[shots.season.isin(settings.train_seasons)]
    test = shots[shots.season == settings.test_season]
    if train.empty or test.empty:
        raise RuntimeError("xG model needs shots in both the train and test seasons")
    spec = fit(train)
    spec["train_seasons"] = settings.train_seasons
    spec["test_season"] = settings.test_season

    shots["xg"] = predict(shots, spec)
    con.register("scored", shots[["shot_id", "xg"]])
    con.execute("create or replace table gold.shot_xg as select shot_id, xg from scored")
    con.execute(
        "comment on table gold.shot_xg is 'Model xG per scored shot (see models/xg_model.json).'"
    )
    con.unregister("scored")

    base_rate = float(train.is_goal.mean())
    scored_test = shots[shots.season == settings.test_season]
    y, p = scored_test.is_goal.to_numpy(), scored_test.xg.to_numpy()
    metrics = {
        "train": evaluate(
            train.is_goal.to_numpy(), shots.loc[train.index, "xg"].to_numpy(), base_rate
        ),
        "test": evaluate(y, p, base_rate),
        "calibration_test": plot_calibration(
            y,
            p,
            models_dir / "xg_calibration.png",
            f"xG calibration, held-out {settings.test_season}",
        ),
        "moneypuck_benchmark_test": moneypuck_benchmark(con, settings.test_season),
    }
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "xg_model.json").write_text(json.dumps(spec, indent=2) + "\n")
    (models_dir / "xg_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    write_model_card(con, spec, metrics, models_dir / "MODEL_CARD.md")
    return metrics
