-- Silver: who dressed in each game, plus a player dimension.
create or replace table silver.game_rosters as
with games as materialized (
    select
        (payload ->> '$.id')::bigint as game_id,
        (payload ->> '$.gameDate')::date as game_date,
        json_extract(payload, '$.rosterSpots[*]') as spots
    from bronze.nhl_pbp
),
spots as (
    select game_id, game_date, unnest(spots) as s from games
)
select
    game_id,
    game_date,
    (s ->> '$.playerId')::integer as player_id,
    (s ->> '$.teamId')::integer as team_id,
    s ->> '$.firstName.default' as first_name,
    s ->> '$.lastName.default' as last_name,
    s ->> '$.positionCode' as position,
    (s ->> '$.sweaterNumber')::integer as sweater_number,
    s ->> '$.headshot' as headshot_url
from spots
qualify row_number() over (partition by game_id, player_id order by team_id) = 1;

comment on table silver.game_rosters is 'Players dressed per game (from play-by-play rosterSpots). Source of games played.';

create or replace table silver.roster_players as
with r as (
    select
        regexp_extract(source_file, 'roster/(\d+)/', 1)::integer as season,
        regexp_extract(source_file, '/(\w+)\.json$', 1) as team,
        ingested_at,
        unnest(
            json_extract(payload, '$.forwards[*]')
            || json_extract(payload, '$.defensemen[*]')
            || json_extract(payload, '$.goalies[*]')
        ) as p
    from bronze.nhl_rosters
)
select
    season,
    team,
    (p ->> '$.id')::integer as player_id,
    p ->> '$.firstName.default' as first_name,
    p ->> '$.lastName.default' as last_name,
    p ->> '$.positionCode' as position,
    (p ->> '$.sweaterNumber')::integer as sweater_number,
    p ->> '$.headshot' as headshot_url,
    ingested_at
from r
qualify row_number() over (partition by season, team, player_id order by ingested_at desc) = 1;

comment on table silver.roster_players is 'Official team rosters per season (focus team), latest fetch wins.';

create or replace table silver.players as
select player_id, first_name, last_name, first_name || ' ' || last_name as full_name, position,
    sweater_number, headshot_url
from (
    select player_id, first_name, last_name, position, sweater_number, headshot_url,
        game_id // 1000000 as season_start, game_date::timestamptz as as_of
    from silver.game_rosters
    union all
    select player_id, first_name, last_name, position, sweater_number, headshot_url,
        season // 10000, ingested_at
    from silver.roster_players
)
-- latest season first, so a re-fetched old roster can never override newer game data
qualify row_number() over (partition by player_id order by season_start desc, as_of desc) = 1;

comment on table silver.players is 'Player dimension: latest known name, position and number per player_id.';
