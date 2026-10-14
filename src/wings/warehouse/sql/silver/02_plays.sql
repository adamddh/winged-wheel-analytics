-- Silver: one row per play-by-play event, typed and flattened.
create or replace table silver.plays as
-- Perf: extract game-level fields in their own materialized CTE before unnesting. Selecting
-- payload ->> ... next to unnest() re-evaluates it against the full payload for every
-- unnested row (measured 85x slower). See ai-log.md, entry "silver.plays build time".
with games as materialized (
    select
        (payload ->> '$.id')::bigint as game_id,
        (payload ->> '$.season')::integer as season,
        (payload ->> '$.homeTeam.id')::integer as home_team_id,
        (payload ->> '$.awayTeam.id')::integer as away_team_id,
        json_extract(payload, '$.plays[*]') as plays
    from bronze.nhl_pbp
),
g as (
    select game_id, season, home_team_id, away_team_id, unnest(plays) as p from games
)
select
    game_id,
    season,
    (p ->> '$.eventId')::integer as event_id,
    (p ->> '$.sortOrder')::integer as sort_order,
    (p ->> '$.periodDescriptor.number')::integer as period,
    p ->> '$.periodDescriptor.periodType' as period_type,
    ((p ->> '$.periodDescriptor.number')::integer - 1) * 1200
        + mmss_to_seconds(p ->> '$.timeInPeriod') as game_seconds,
    p ->> '$.situationCode' as situation_code,
    p ->> '$.typeDescKey' as event_type,
    p ->> '$.homeTeamDefendingSide' as home_defending_side,
    home_team_id,
    away_team_id,
    (p ->> '$.details.eventOwnerTeamId')::integer as team_id,
    (p ->> '$.details.eventOwnerTeamId')::integer = home_team_id as is_home,
    p ->> '$.details.zoneCode' as zone_code,
    (p ->> '$.details.xCoord')::double as x,
    (p ->> '$.details.yCoord')::double as y,
    p ->> '$.details.shotType' as shot_type,
    coalesce(
        (p ->> '$.details.shootingPlayerId')::integer, (p ->> '$.details.scoringPlayerId')::integer
    ) as shooter_id,
    (p ->> '$.details.goalieInNetId')::integer as goalie_id,
    (p ->> '$.details.assist1PlayerId')::integer as assist1_id,
    (p ->> '$.details.assist2PlayerId')::integer as assist2_id
from g
qualify row_number() over (partition by game_id, event_id order by sort_order) = 1;

comment on table silver.plays is 'Play-by-play events, one row per (game_id, event_id). game_seconds counts from opening faceoff.';
