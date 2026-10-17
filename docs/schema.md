# Warehouse schema

_Generated from the DuckDB catalog by `make pipeline`. Do not edit by hand._

## bronze

Raw payloads exactly as ingested (replayable source of truth).

### `bronze.moneypuck_shots`

Raw MoneyPuck shot-level CSVs (moneypuck.com/data.htm), all text.

~129,194 rows

### `bronze.nhl_pbp`

Raw play-by-play payloads from api-web.nhle.com/v1/gamecenter/{id}/play-by-play.

~2,744 rows

### `bronze.nhl_rosters`

Raw team roster payloads from api-web.nhle.com/v1/roster/{team}/{season}.

~2 rows

### `bronze.nhl_schedule`

Raw weekly schedule payloads from api-web.nhle.com/v1/schedule/{date}.

~68 rows

### `bronze.nhl_shifts`

Raw shift charts from api.nhle.com/stats/rest/en/shiftcharts (focus team games).

~86 rows

## silver

Cleaned, typed, deduplicated entities.

### `silver.game_rosters`

Players dressed per game (from play-by-play rosterSpots). Source of games played.

~109,751 rows

| column | type | description |
|---|---|---|
| `game_id` | BIGINT |  |
| `game_date` | DATE |  |
| `player_id` | INTEGER |  |
| `team_id` | INTEGER |  |
| `first_name` | VARCHAR |  |
| `last_name` | VARCHAR |  |
| `position` | VARCHAR |  |
| `sweater_number` | INTEGER |  |
| `headshot_url` | VARCHAR |  |

### `silver.games`

Regular-season games (scheduled and completed), deduplicated on game_id. game_state OFF = official final.

~2,811 rows

| column | type | description |
|---|---|---|
| `game_id` | BIGINT |  |
| `season` | INTEGER |  |
| `game_date` | DATE |  |
| `start_time_utc` | TIMESTAMP WITH TIME ZONE |  |
| `game_state` | VARCHAR |  |
| `home_team_id` | INTEGER |  |
| `home_team` | VARCHAR |  |
| `away_team_id` | INTEGER |  |
| `away_team` | VARCHAR |  |
| `home_score` | INTEGER |  |
| `away_score` | INTEGER |  |
| `last_period_type` | VARCHAR |  |
| `ingested_at` | TIMESTAMP WITH TIME ZONE |  |

### `silver.moneypuck_shots`

MoneyPuck unblocked shot attempts with their public xG (mp_xg), regular season only.

~121,700 rows

| column | type | description |
|---|---|---|
| `game_id` | INTEGER |  |
| `season` | INTEGER |  |
| `mp_shot_id` | INTEGER |  |
| `period` | INTEGER |  |
| `game_seconds` | INTEGER |  |
| `shooter_id` | INTEGER |  |
| `team` | VARCHAR |  |
| `event` | VARCHAR |  |
| `shot_type` | VARCHAR |  |
| `mp_xg` | DOUBLE |  |
| `is_goal` | BOOLEAN |  |
| `is_empty_net` | BOOLEAN |  |

### `silver.players`

Player dimension: latest known name, position and number per player_id.

~1,247 rows

| column | type | description |
|---|---|---|
| `player_id` | INTEGER |  |
| `first_name` | VARCHAR |  |
| `last_name` | VARCHAR |  |
| `full_name` | VARCHAR |  |
| `position` | VARCHAR |  |
| `sweater_number` | INTEGER |  |
| `headshot_url` | VARCHAR |  |

### `silver.plays`

Play-by-play events, one row per (game_id, event_id). game_seconds counts from opening faceoff.

~872,805 rows

| column | type | description |
|---|---|---|
| `game_id` | BIGINT |  |
| `season` | INTEGER |  |
| `event_id` | INTEGER |  |
| `sort_order` | INTEGER |  |
| `period` | INTEGER |  |
| `period_type` | VARCHAR |  |
| `game_seconds` | INTEGER |  |
| `situation_code` | VARCHAR |  |
| `event_type` | VARCHAR |  |
| `home_defending_side` | VARCHAR |  |
| `home_team_id` | INTEGER |  |
| `away_team_id` | INTEGER |  |
| `team_id` | INTEGER |  |
| `is_home` | BOOLEAN |  |
| `zone_code` | VARCHAR |  |
| `x` | DOUBLE |  |
| `y` | DOUBLE |  |
| `shot_type` | VARCHAR |  |
| `shooter_id` | INTEGER |  |
| `goalie_id` | INTEGER |  |
| `assist1_id` | INTEGER |  |
| `assist2_id` | INTEGER |  |

### `silver.roster_players`

Official team rosters per season (focus team), latest fetch wins.

~42 rows

| column | type | description |
|---|---|---|
| `season` | INTEGER |  |
| `team` | VARCHAR |  |
| `player_id` | INTEGER |  |
| `first_name` | VARCHAR |  |
| `last_name` | VARCHAR |  |
| `position` | VARCHAR |  |
| `sweater_number` | INTEGER |  |
| `headshot_url` | VARCHAR |  |
| `ingested_at` | TIMESTAMP WITH TIME ZONE |  |

### `silver.shifts`

Player shifts from official shift charts; [start_seconds, end_seconds] in game time, overlapping duplicates merged.

~65,015 rows

| column | type | description |
|---|---|---|
| `shift_id` | BIGINT |  |
| `game_id` | BIGINT |  |
| `player_id` | INTEGER |  |
| `team_id` | INTEGER |  |
| `period` | INTEGER |  |
| `start_seconds` | INTEGER |  |
| `end_seconds` | INTEGER |  |
| `source_records` | BIGINT | Raw shift records merged into this interval (>1 means the feed repeated it). |

### `silver.teams`

NHL teams seen in the schedule, latest abbreviation per team_id.

~33 rows

| column | type | description |
|---|---|---|
| `team_id` | INTEGER |  |
| `abbrev` | VARCHAR |  |

## gold

Analytics-ready facts, features and marts.

### `gold.player_cards`

Player-card rows for the configured focus players, held-out and current season (null stats = did not play).

~8 rows

| column | type | description |
|---|---|---|
| `card_name` | VARCHAR |  |
| `player_id` | INTEGER |  |
| `season` | INTEGER |  |
| `sweater_number` | INTEGER |  |
| `position` | VARCHAR |  |
| `full_name` | VARCHAR |  |
| `team` | VARCHAR |  |
| `games_played` | BIGINT |  |
| `goals` | BIGINT |  |
| `assists` | BIGINT |  |
| `points` | BIGINT |  |
| `shots_on_goal` | BIGINT |  |
| `unblocked_attempts` | BIGINT |  |
| `ixg` | DECIMAL(38,8) |  |
| `ixg_5v5` | DECIMAL(38,8) |  |
| `ixg_pp` | DECIMAL(38,8) |  |
| `goals_above_ixg` | DECIMAL(38,8) |  |
| `games_with_shifts` | BIGINT |  |
| `toi_seconds` | HUGEINT |  |
| `toi_per_game_min` | DOUBLE |  |
| `ixg_per_60` | DOUBLE |  |
| `oi_xgf_5v5` | DECIMAL(38,8) |  |
| `oi_xga_5v5` | DECIMAL(38,8) |  |
| `oi_gf_5v5` | BIGINT |  |
| `oi_ga_5v5` | BIGINT |  |
| `oi_xgf_pct_5v5` | DOUBLE |  |
| `oi_xgf_all` | DECIMAL(38,8) |  |
| `oi_xga_all` | DECIMAL(38,8) |  |

### `gold.player_seasons`

Skater season stats: scoring, individual xG (ixg), and where shift data exists, TOI and 5v5 on-ice xG for/against.

~2,544 rows

| column | type | description |
|---|---|---|
| `season` | INTEGER |  |
| `player_id` | INTEGER |  |
| `full_name` | VARCHAR |  |
| `position` | VARCHAR |  |
| `sweater_number` | INTEGER |  |
| `team` | VARCHAR |  |
| `games_played` | BIGINT |  |
| `goals` | BIGINT |  |
| `assists` | BIGINT |  |
| `points` | BIGINT |  |
| `shots_on_goal` | BIGINT |  |
| `unblocked_attempts` | BIGINT |  |
| `ixg` | DECIMAL(38,8) |  |
| `ixg_5v5` | DECIMAL(38,8) |  |
| `ixg_pp` | DECIMAL(38,8) |  |
| `goals_above_ixg` | DECIMAL(38,8) |  |
| `games_with_shifts` | BIGINT | Games with published NHL shift charts; denominator for TOI and on-ice stats. |
| `toi_seconds` | HUGEINT |  |
| `toi_per_game_min` | DOUBLE |  |
| `ixg_per_60` | DOUBLE |  |
| `oi_xgf_5v5` | DECIMAL(38,8) |  |
| `oi_xga_5v5` | DECIMAL(38,8) |  |
| `oi_gf_5v5` | BIGINT |  |
| `oi_ga_5v5` | BIGINT |  |
| `oi_xgf_pct_5v5` | DOUBLE | Share of 5v5 xG that was for the player's team while he was on the ice. |
| `oi_xgf_all` | DECIMAL(38,8) |  |
| `oi_xga_all` | DECIMAL(38,8) |  |

### `gold.shot_xg`

Model xG per scored shot (see models/xg_model.json).

~232,250 rows

| column | type | description |
|---|---|---|
| `shot_id` | BIGINT |  |
| `xg` | DOUBLE |  |

### `gold.shots`

Unblocked shot attempts with xG features. Coordinates normalized so the shooter attacks the net at (89, 0).

~234,263 rows

| column | type | description |
|---|---|---|
| `shot_id` | BIGINT | Surrogate key: game_id * 1e8 + event_id (NHL event ids reach the millions). |
| `game_id` | BIGINT |  |
| `event_id` | INTEGER |  |
| `season` | INTEGER |  |
| `period` | INTEGER |  |
| `game_seconds` | INTEGER |  |
| `team_id` | INTEGER |  |
| `opponent_id` | INTEGER |  |
| `is_home` | BOOLEAN |  |
| `shooter_id` | INTEGER |  |
| `goalie_id` | INTEGER |  |
| `event_type` | VARCHAR |  |
| `is_goal` | BOOLEAN |  |
| `x_norm` | DOUBLE |  |
| `y_norm` | DOUBLE |  |
| `distance` | DOUBLE | Feet from the attacked goal at (89, 0). |
| `angle` | DOUBLE | Degrees off the line through the center of the net; >90 means behind the goal line. |
| `shot_type` | VARCHAR |  |
| `is_rebound` | BOOLEAN | Same team had a shot on goal or miss within the previous 3 seconds of the same period. |
| `rebound_seconds` | INTEGER | Seconds since the shot being rebounded (null if not a rebound). 0-1s jam plays score far less than 2-3s rebounds. |
| `is_rush` | BOOLEAN | Previous event within 4s was in the shooter's neutral/defensive zone, and the shot is from inside the offensive blue line. |
| `situation_code` | VARCHAR |  |
| `manpower` | VARCHAR | 5v5, PP, SH, or other (4v4, 3v3, extra attacker), shooter perspective. |
| `score_diff` | BIGINT |  |
| `score_state` | BIGINT | Shooter score differential before the shot, clipped to [-2, 2]. |
| `is_empty_net` | BOOLEAN | Opponent goalie not in net. Excluded from the xG model. |

### `gold.shots_scored`

gold.shots joined to model xG (non-empty-net, located shots only) plus team, opponent and shooter names.

~232,250 rows

| column | type | description |
|---|---|---|
| `shot_id` | BIGINT |  |
| `game_id` | BIGINT |  |
| `event_id` | INTEGER |  |
| `season` | INTEGER |  |
| `period` | INTEGER |  |
| `game_seconds` | INTEGER |  |
| `team_id` | INTEGER |  |
| `opponent_id` | INTEGER |  |
| `is_home` | BOOLEAN |  |
| `shooter_id` | INTEGER |  |
| `goalie_id` | INTEGER |  |
| `event_type` | VARCHAR |  |
| `is_goal` | BOOLEAN |  |
| `x_norm` | DOUBLE |  |
| `y_norm` | DOUBLE |  |
| `distance` | DOUBLE |  |
| `angle` | DOUBLE |  |
| `shot_type` | VARCHAR |  |
| `is_rebound` | BOOLEAN |  |
| `rebound_seconds` | INTEGER |  |
| `is_rush` | BOOLEAN |  |
| `situation_code` | VARCHAR |  |
| `manpower` | VARCHAR |  |
| `score_diff` | BIGINT |  |
| `score_state` | BIGINT |  |
| `is_empty_net` | BOOLEAN |  |
| `xg` | DECIMAL(10,8) |  |
| `game_date` | DATE |  |
| `team` | VARCHAR |  |
| `opponent` | VARCHAR |  |
| `shooter` | VARCHAR |  |

### `gold.team_game_strength`

Per team, game and strength (5v5/PP/SH/other from that team's bench): unblocked shots, xG and goals for/against.

~20,766 rows

| column | type | description |
|---|---|---|
| `season` | INTEGER |  |
| `game_id` | BIGINT |  |
| `game_date` | DATE |  |
| `team_id` | INTEGER |  |
| `opponent_id` | INTEGER |  |
| `is_home` | BOOLEAN |  |
| `strength` | VARCHAR |  |
| `shots_for` | BIGINT |  |
| `shots_against` | BIGINT |  |
| `xgf` | DECIMAL(38,8) |  |
| `xga` | DECIMAL(38,8) |  |
| `gf` | BIGINT |  |
| `ga` | BIGINT |  |

### `gold.team_games`

One row per team per completed game: result, scoreboard, and xG/goals for and against (all situations and 5v5).

~5,488 rows

| column | type | description |
|---|---|---|
| `season` | INTEGER |  |
| `game_id` | BIGINT |  |
| `game_date` | DATE |  |
| `team_id` | INTEGER |  |
| `team` | VARCHAR |  |
| `opponent_id` | INTEGER |  |
| `opponent` | VARCHAR |  |
| `is_home` | BOOLEAN |  |
| `final_gf` | INTEGER | Scoreboard goals for, including shootout winner. |
| `final_ga` | INTEGER |  |
| `result` | VARCHAR |  |
| `decided_in` | VARCHAR |  |
| `shots_for` | HUGEINT |  |
| `shots_against` | HUGEINT |  |
| `xgf` | DECIMAL(38,8) |  |
| `xga` | DECIMAL(38,8) |  |
| `gf` | HUGEINT | Goals on the xG shot set (excludes empty-net and shootout goals). |
| `ga` | HUGEINT |  |
| `xgf_5v5` | DECIMAL(38,8) |  |
| `xga_5v5` | DECIMAL(38,8) |  |
| `gf_5v5` | HUGEINT |  |
| `ga_5v5` | HUGEINT |  |
| `team_game_number` | BIGINT |  |

### `gold.team_season_splits`

Team season totals by strength (5v5, PP, SH, other, all). finishing_above_xg = GF - xGF; goaltending_above_xg = xGA - GA.

~480 rows

| column | type | description |
|---|---|---|
| `season` | INTEGER |  |
| `team_id` | INTEGER |  |
| `strength` | VARCHAR |  |
| `games` | BIGINT |  |
| `shots_for` | HUGEINT |  |
| `shots_against` | HUGEINT |  |
| `xgf` | DECIMAL(38,8) |  |
| `xga` | DECIMAL(38,8) |  |
| `gf` | HUGEINT |  |
| `ga` | HUGEINT |  |
| `team` | VARCHAR |  |
| `xgf_pct` | DOUBLE |  |
| `finishing_above_xg` | DECIMAL(38,8) |  |
| `goaltending_above_xg` | DECIMAL(38,8) |  |
| `xgf_pct_rank` | BIGINT |  |

### `gold.xg_validation_team_games`

Team-game xGF from our model next to MoneyPuck's xGF for the same games.

~2,858 rows

| column | type | description |
|---|---|---|
| `season` | INTEGER |  |
| `game_id` | BIGINT |  |
| `team` | VARCHAR |  |
| `xgf` | DECIMAL(38,8) |  |
| `mp_xgf` | DOUBLE |  |
| `gf` | HUGEINT |  |
