import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from wings.models import xg


def synthetic_shots(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "distance": rng.uniform(5, 70, n),
            "angle": rng.uniform(0, 85, n),
            "shot_type": rng.choice(xg.CATEGORICAL["shot_type"], n),
            "manpower": rng.choice(xg.CATEGORICAL["manpower"], n),
            "score_state": rng.choice(xg.CATEGORICAL["score_state"], n),
            "rebound": rng.choice(["none"] * 10 + ["quick", "delayed"], n),
            "is_rush": rng.random(n) < 0.05,
        }
    )
    logit = -1.0 - 0.06 * df.distance - 0.01 * df.angle + 1.0 * (df.rebound == "delayed")
    df["is_goal"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return df


def test_json_spec_reproduces_sklearn_predictions():
    df = synthetic_shots()
    spec = xg.fit(df)
    reference = LogisticRegression(C=1.0, max_iter=5000).fit(xg.design_matrix(df, spec), df.is_goal)
    expected = reference.predict_proba(xg.design_matrix(df, spec))[:, 1]
    np.testing.assert_allclose(xg.predict(df, spec), expected, rtol=1e-6)


def test_model_learns_distance_and_rebound_effects():
    spec = xg.fit(synthetic_shots())
    assert spec["coef"]["distance"] + spec["coef"]["log_distance"] < 0  # farther = worse
    assert spec["coef"]["rebound=delayed"] > 0.5
    assert set(spec["coef"]) == set(xg.feature_names())


def test_unseen_category_falls_back_to_reference():
    df = synthetic_shots(200)
    spec = xg.fit(df)
    row = df.iloc[[0]].assign(shot_type="wrist")
    odd = df.iloc[[0]].assign(shot_type="cradle")  # not a modeled level
    np.testing.assert_allclose(xg.predict(odd, spec), xg.predict(row, spec))
