# AI log

How AI tools were used to build, debug and refactor this pipeline. The Red Wings posting asks
for "experience utilizing AI tools to analyze, refine, and refactor existing pipelines", so this
log is a deliverable in its own right. It records what the AI did, what was verified by running
code, and where the AI got things wrong.

**Tooling:** [Claude Code](https://claude.com/claude-code) (Claude Opus 5.5) as an agentic pair
programmer in the terminal: it ran commands, read data, wrote code and opened PRs, under my
direction and review. Every PR in this repo was produced this way; commits carry a
`Co-Authored-By` trailer.

**Ground rule:** AI output is a hypothesis until a query, test or chart confirms it. Each entry
below says what the check was.

---

## 2026-10-14: Source reconnaissance before writing code

- **Task:** confirm what the public NHL APIs and MoneyPuck actually return for the 2026-27 season.
- **AI did:** probed `api-web.nhle.com` (schedule, play-by-play, roster), `api.nhle.com/stats/rest`
  (shift charts) and MoneyPuck's shot zips, then printed the payload keys and sample events.
- **Findings that shaped the design:**
  - The weekly `/schedule/{date}` endpoint returns `nextStartDate` and `regularSeasonEndDate`,
    which gives clean pagination for a whole season (about 27 calls) instead of 32 team calls.
  - MoneyPuck's `game_id` is `20090` for NHL game `2026020090`, and its "2025" file is the 2025-26
    season. Join key: `season_start_year * 1e6 + game_id`.
  - Simon Edvinsson is missing from the current DET roster endpoint but active in player search,
    so player cards must handle a focus player with zero games rather than crash or drop him.

## Ingest: cache policy and idempotency

- **AI did:** proposed the "fetch once, never again" rule for anything immutable (past seasons;
  games with `gameState == "OFF"`, which is official; `FINAL` games can still get scoring
  corrections), plus atomic temp-file-and-rename writes and a throttled client with backoff.
- **Verified:** unit tests with a mocked transport prove a second run makes zero HTTP calls.
  The real backfill (2,729 games, 88 shift charts, 2 MoneyPuck seasons) took about 11 minutes
  at roughly 4 requests/s. Re-runs take seconds.

## Debug: `silver.plays` took 280 s to build

- **Symptom:** the first warehouse build took 190 s on half a season, and profiling the models
  one by one put 280 s in `silver.plays` once more data landed.
- **AI-driven analysis:**
  1. Hypothesis 1 was "JSON is parsed once per `->>` extraction". It benchmarked
     `json_extract` against `from_json` struct parsing on 200 games: same time (4.3 s), so rejected.
  2. Microbenchmarks then isolated each step: reading payloads 0.01 s, unnesting 0.03 s,
     extracting five fields from unnested plays 0.1 s. All fast.
  3. That left the combination: selecting `payload ->> '$.id'` *in the same SELECT as*
     `unnest(...)` took 4.28 s. Moving game-level fields into a materialized CTE first took
     0.05 s, an **85x** speedup.
- **Fix:** both affected models now extract game-level fields before unnesting, and there's a
  comment in the SQL explaining why.
- **Result:** a full build of 2.7k games went from minutes to about **7 s**, and the whole
  pipeline (build, checks, model, marts, reports) runs in about 10 s on cached data.

## Debug: operator precedence in DuckDB JSON SQL

- **Symptom:** `Conversion Error: Failed to cast value to numerical: {"id":...}`, but only after
  shift charts started landing.
- **Root cause:** `d ->> '$.endTime' is not null` parses as `d ->> ('$.endTime' is not null)`.
  A per-expression bisect passed (each expression was fine alone), which pointed to the
  `WHERE` clause.
- **Fix:** parenthesize `(d ->> '$.endTime') is not null`.

## Data quality gate caught a real bug

- **Symptom:** the first full run failed the `gold.shots unique on (shot_id)` check (6 duplicates).
- **Root cause:** the surrogate key `game_id * 10000 + event_id` assumed small event ids, but
  NHL event ids reach about 2.4 million, so different games collided.
- **Fix:** multiplier `1e8` (still fits a BIGINT), with the uniqueness check kept as the guard.
  The bug was caught because the pipeline refuses to continue on a failed check.

## Analysis: shift charts are missing for some games

- **AI did:** traced a warn-level completeness check (3 DET games without shifts) back to the
  source. The NHL stats API returns `total: 0` for those games, and the only alternative is
  scraping HTML reports, which is out of scope.
- **Impact caught:** TOI per game divided season TOI by *all* games played, which would have
  understated TOI/GP by about half. Rates now use a `games_with_shifts` denominator, with ixG
  restricted to the same games, and the README discloses the coverage.

## Refine: the xG features failed a sanity check

- **Symptom:** fitted coefficients for rebound (−0.22) and rush (−0.41) were *negative*, which
  contradicts published hockey research.
- **AI-driven analysis:** goal rates by previous-event type, zone and time gap, then rates
  within distance bands:
  - Blocked shots: 91% are coded zone `D` while 94% of shots on goal are `O`. So `zoneCode` on
    a block is the *blocker's* perspective even though the event owner is the shooting team.
    The rush logic was counting in-zone point shots as rush chances.
  - "Rush" also caught 90–190 ft dump-ins right after neutral-zone faceoffs.
  - Rebounds split sharply by timing: 0–1 s follow-ups score far below baseline (the goalie
    smothers the jam play) while 2–3 s rebounds score about 3x baseline (the goalie is moving).
- **Fixes:** a zone-perspective correction for blocks, a blue-line requirement for rush shots,
  and rebound as a timing category instead of a flag.
- **Result:** held-out log loss 0.2261 → 0.2227 and ROC AUC 0.741 → 0.754 (the current values are
  in `models/MODEL_CARD.md`). Rush stays negative after the fixes; that's documented as a
  finding about location-only public data, not tuned away.

## Refactor: independent AI review of the finished pipeline

- **Setup:** once the pipeline worked end to end, a *separate* Claude Code subagent got
  read-only access to the code and a copy of the warehouse. Its brief: find performance, correctness
  and simplification issues, and back every claim with a timing or a query. It was not allowed to
  edit code.
- **Highest-value finding, a real bug:** the NHL shift-chart feed repeats some shifts under different
  ids (147 overlapping pairs: exact copies plus nested fragments). Deduplicating on `shift_id`
  could never catch that. Effects: focus-player TOI inflated by about 5 minutes per season, one
  team-game summing 23,777 s of skater time (normal is about 21k), and 87 shots showing 7–12
  skaters on the ice.
  - **Verified** by re-running the overlap query myself before changing anything.
  - **Fix:** a gaps-and-islands interval merge in `silver.shifts`, a new quality check (no
    overlapping shifts), and a unit test for duplicates, nested fragments and touching shifts.
    After the fix the same game sums to 21,290 s.
- **Also applied:**
  - a clock-label bug (20:00 of P1 shown as "P2 0:00")
  - MoneyPuck team mapping that would fan out for `UTA` (two franchise ids)
  - a season-first ordering for the player dimension
  - BIGINT running-score windows
  - an enriched `gold.shots_scored` that removed three duplicated joins
  - removal of dead parameters
- **Rejected or confirmed fine (also from the review):** a `from_json` rewrite of `silver.plays`
  (same speed), and dropping its `QUALIFY` (measured slower). It also confirmed that OT/SO results
  reconcile with the play-by-play for all 2,729 games and that on-ice attribution at shift changes
  is correct (99.3% of 5v5 shots show exactly 6 per side).
- **Lesson:** the review found the bug through a *physical* invariant (a team can't have more than 6
  skaters on the ice). Invariants like that are now quality checks instead of one-off queries.

## Reproducibility: byte-identical reruns

- **Symptom:** the fresh-clone acceptance run produced a different `models/xg_model.json` than the
  committed one, on identical data. The differences were in the 15th significant digit.
- **Root cause:** parallel scans and hash aggregation add floating-point numbers in a different
  order each run. That's harmless numerically, but every daily refresh would have committed noise.
- **What didn't work:** single-threading the marts, then ordering the materialized table. Both
  were tested, and checksums still differed across runs.
- **Fix:** model input rows are ordered by `shot_id` and coefficients are rounded to 10 places.
  xG is carried through the marts as `DECIMAL(10,8)`, so every sum is exact and
  order-independent. Exports are sorted.
- **Verified:** three consecutive runs give identical MD5s for every model artifact, export and
  figure.

## Dashboard: design and visual QA loop

- **Design:** the AI drafted a design plan, checked it against generic "AI dashboard" defaults
  (cream backgrounds, card grids, all-caps eyebrow labels), then built around the subject itself:
  - a to-scale NHL rink in SVG as the hero
  - rink red for Detroit and blue-line blue for opponents, the same two colors already
    validated for color-vision deficiency in the README charts
  - one variable typeface (Archivo) with condensed widths for jersey numerals
- **Visual QA:** every iteration was screenshotted headlessly with Playwright, driving the
  installed Chrome, at desktop and phone widths, and reviewed as images. That loop caught:
  - `st.html` silently sanitizing inline SVG away (the hero rendered as nothing); the rink now
    renders through markdown, which keeps the hover titles
  - a missing chart legend
  - Edvinsson's card losing his jersey number because he has no stats row yet
  - oversized half-rinks
  - player cards stacking out of order on phones
- **Guard in CI:** `tests/test_app.py` renders the app headlessly against the committed exports,
  so a broken dashboard fails the PR.

## Mistakes the AI made, and how they were caught

| Mistake | Caught by |
|---|---|
| Unit test expected `PP` for an away shot vs. a pulled home goalie (it's 5 vs 6 skaters, so `SH`) | the test run; the macro was right and the expectation was wrong |
| `row_number()` window in the same SELECT as `GROUP BY ALL` | DuckDB binder error; split into a CTE |
| `git stash -u` silently dropped a new, still-empty `gold_marts/` directory | file writes failed; directory recreated |
| Merged a PR whose new commit hadn't registered CI yet (`gh pr checks --watch` exited on "no checks reported") | noticed in the output; confirmed CI passed on `main` afterwards; the merge procedure now polls until every check reports SUCCESS |
| Plotted faceoff dots in team red, which read as Detroit shots on the opponent panel | visual review of the rendered PNG |

## Guardrails

Claude Code's permission system blocked the agent from merging its own PRs and from editing its
own permission settings. I granted `gh pr merge` explicitly. Irreversible or outward-facing
actions (merging, publishing, deploying) stay human-approved.
