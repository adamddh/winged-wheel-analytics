-- Silver: one row per regular-season game, latest schedule snapshot wins.
create or replace table silver.games as
with days as (
    select ingested_at, unnest(json_extract(payload, '$.gameWeek[*]')) as d
    from bronze.nhl_schedule
),
games as (
    select ingested_at, (d ->> '$.date')::date as game_date, unnest(json_extract(d, '$.games[*]')) as g
    from days
)
select
    (g ->> '$.id')::bigint as game_id,
    (g ->> '$.season')::integer as season,
    game_date,
    (g ->> '$.startTimeUTC')::timestamptz as start_time_utc,
    g ->> '$.gameState' as game_state,
    (g ->> '$.homeTeam.id')::integer as home_team_id,
    g ->> '$.homeTeam.abbrev' as home_team,
    (g ->> '$.awayTeam.id')::integer as away_team_id,
    g ->> '$.awayTeam.abbrev' as away_team,
    (g ->> '$.homeTeam.score')::integer as home_score,
    (g ->> '$.awayTeam.score')::integer as away_score,
    g ->> '$.gameOutcome.lastPeriodType' as last_period_type,
    ingested_at
from games
where (g ->> '$.gameType')::integer = 2
qualify row_number() over (partition by game_id order by ingested_at desc) = 1;

comment on table silver.games is 'Regular-season games (scheduled and completed), deduplicated on game_id. game_state OFF = official final.';

create or replace table silver.teams as
select team_id, abbrev
from (
    select home_team_id as team_id, home_team as abbrev, start_time_utc from silver.games
    union all
    select away_team_id, away_team, start_time_utc from silver.games
)
qualify row_number() over (partition by team_id order by start_time_utc desc) = 1;

comment on table silver.teams is 'NHL teams seen in the schedule, latest abbreviation per team_id.';
