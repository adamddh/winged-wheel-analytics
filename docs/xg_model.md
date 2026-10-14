# Expected goals (xG) model

**What it estimates:** the probability that an unblocked, non-empty-net shot attempt becomes a
goal, given only what the public NHL play-by-play records about it.

**Where the numbers live:** this page explains the *choices*. Every metric, coefficient and
evidence table is regenerated on each run in [`models/MODEL_CARD.md`](../models/MODEL_CARD.md),
with the fitted model itself in [`models/xg_model.json`](../models/xg_model.json).

## Setup

| | |
|---|---|
| Unit | Unblocked shot attempts (Fenwick: shots on goal, misses, goals). Blocked shots are excluded because the NHL records the *block* location, not the shot location. |
| Excluded | Shootout attempts; shots at an empty net (opponent goalie not in, read from `situationCode`); shots without coordinates. |
| Train / test | Fit on 2024-25 league-wide, evaluated on held-out 2025-26 (configurable in `wings.toml`). A season split, not a random split, because the job is to score a *future* season. |
| Model | L2-regularized logistic regression (scikit-learn, `C=1`). Simple on purpose: coefficients are inspectable and the model scores in microseconds. |
| Artifact | A plain-JSON spec (standardization stats, category levels, coefficients). No pickles: it is diffable in code review, and `wings.models.xg.predict` reproduces scikit-learn's probabilities exactly (unit-tested). |

## Features and why

All features are computed in SQL (`src/wings/warehouse/sql/gold_features/01_shots.sql`) from
coordinates normalized so every shooter attacks the net at (89, 0).

| Feature | Encoding | Why |
|---|---|---|
| Distance | feet to the goal center, plus `log1p(distance)` | The dominant signal in every public xG model. The log term lets the effect flatten at range without binning. |
| Angle | degrees off the net's center line (>90° = behind the goal line) | Sharp angles shrink the net the shooter can see. |
| Shot type | wrist (reference), snap, slap, backhand, tip-in, deflected, wrap-around, other | Release type carries information that location doesn't (one-timer slap shots, redirections). Rare types (bat, poke, between-legs, cradle) are pooled into `other` to avoid unstable coefficients. |
| Rebound | `none` (reference), `quick` (0–1 s), `delayed` (2–3 s) after the same team's shot on goal or miss | A plain rebound flag came out *negative*. Splitting by timing showed why: 0–1 s follow-ups are mostly jam plays the goalie smothers, while 2–3 s rebounds catch the goalie moving laterally and score far above baseline. See "Rebound timing" in the model card. |
| Rush | previous event within 4 s was in the shooter's neutral or defensive zone, and the shot is from inside the offensive blue line | Kept because the hockey-analytics literature treats rush chances as a distinct shot class. In this location-only data the conditional effect is *negative* (see the model card): without pre-shot puck movement (passes, lateral movement), "rush" mostly marks quick, lower-quality shots off the zone entry. That's an honest finding, and the case for tracking data. |
| Manpower | 5v5 (reference), PP, SH, other (4v4, 3v3, extra attacker), from `situationCode` | Defenses are stretched with fewer skaters. |
| Score state | shooter's goal differential before the shot, clipped to [−2, +2] | Score effects: trailing teams shoot more, from worse places, against defenses that protect the middle. |

## Data-engineering details that changed the model

These came out of data validation, not modeling, and each one moved the metrics:

1. **Blocked-shot zone perspective.** On `blocked-shot` events the NHL API's
   `eventOwnerTeamId` is the shooting team, but `zoneCode` is recorded from the *blocker's*
   perspective (about 91% are coded `D`). Treating it like other events labelled thousands of
   in-zone shots as "rush" shots.
2. **Dump-ins as "shots".** Shots from 90–190 ft after neutral-zone faceoffs met the original
   rush definition. Requiring the shot to come from inside the blue line removed them.
3. **Rebound definition.** Blocked shots don't reach the goalie, so they no longer count as the
   shot being rebounded.

## Limitations

- **Season drift.** The held-out season's goal rate and shot mix differ from training, so
  season totals over-predict (see the train vs. test xG rows in the model card). In production
  I'd retrain on a rolling window and recalibrate (isotonic or Platt) on the most recent season.
- **No pre-shot movement.** Public play-by-play has no passes or puck tracking. Cross-ice
  passes and screens are the biggest missing signals, and why MoneyPuck's richer model still
  has lower log loss on the same shots.
- **Shooter and goalie talent are not modeled.** This is shot quality, not finishing or
  save ability: `goals - xG` is where talent shows up.
