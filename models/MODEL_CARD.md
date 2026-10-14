# xG model card (generated)

_Written by `make pipeline`; see [docs/xg_model.md](../docs/xg_model.md) for the rationale._

Trained on 20242025; evaluated on held-out 20252026.

## Metrics

| split | shots | goals | expected_goals | log_loss | baseline_log_loss | brier | roc_auc |
|---|---|---|---|---|---|---|---|
| train | 111304 | 7377 | 7376.4 | 0.21474 | 0.2439 | 0.05778 | 0.7657 |
| test | 111099 | 7578 | 7927.8 | 0.22265 | 0.24901 | 0.06013 | 0.754 |

## Benchmark against MoneyPuck (held-out season, identical matched shots)

| matched_shots | match_rate | shot_level_correlation | ours_log_loss | moneypuck_log_loss |
|---|---|---|---|---|
| 110269 | 0.9925 | 0.595 | 0.22299 | 0.21778 |

## Coefficients

Numeric features are standardized (per 1 SD). Reference levels: {'shot_type': 'wrist', 'manpower': '5v5', 'score_state': 0, 'rebound': 'none'}.
Intercept -3.140.

| feature | coefficient | odds ratio |
|---|---|---|
| distance | -1.252 | 0.29 |
| log_distance | -0.164 | 0.85 |
| angle | -0.378 | 0.69 |
| is_rush | -0.547 | 0.58 |
| shot_type=snap | 0.348 | 1.42 |
| shot_type=slap | 0.457 | 1.58 |
| shot_type=backhand | -0.472 | 0.62 |
| shot_type=tip-in | -0.879 | 0.42 |
| shot_type=deflected | -0.65 | 0.52 |
| shot_type=wrap-around | -0.944 | 0.39 |
| shot_type=other | -0.203 | 0.82 |
| manpower=PP | 0.344 | 1.41 |
| manpower=SH | 0.364 | 1.44 |
| manpower=other | 0.271 | 1.31 |
| score_state=-2 | -0.107 | 0.9 |
| score_state=-1 | -0.054 | 0.95 |
| score_state=1 | 0.003 | 1.0 |
| score_state=2 | 0.025 | 1.03 |
| rebound=quick | -1.717 | 0.18 |
| rebound=delayed | 0.585 | 1.8 |

## Feature evidence (training seasons)

Rebound timing:

| shot | shots | goal_rate | avg_distance_ft |
|---|---|---|---|
| not a rebound | 102944 | 0.062 | 37.5 |
| rebound, 0-1s (quick) | 3913 | 0.037 | 10.5 |
| rebound, 2-3s (delayed) | 4447 | 0.187 | 19.6 |

Rush vs. other shots at the same distance:

| distance_band_ft | rush_goal_rate | other_goal_rate | rush_shots |
|---|---|---|---|
| 0 | 0.124 | 0.128 | 421 |
| 15 | 0.064 | 0.095 | 500 |
| 30 | 0.014 | 0.05 | 566 |
| 45 | 0.003 | 0.015 | 380 |

## Calibration (held-out deciles)

| predicted | observed |
|---|---|
| 0.0068 | 0.0059 |
| 0.016 | 0.0126 |
| 0.0243 | 0.0201 |
| 0.0335 | 0.0279 |
| 0.0441 | 0.0392 |
| 0.0564 | 0.0595 |
| 0.0716 | 0.0762 |
| 0.0933 | 0.1092 |
| 0.1309 | 0.1354 |
| 0.2366 | 0.1963 |

![calibration](xg_calibration.png)
