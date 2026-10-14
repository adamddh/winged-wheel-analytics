-- Silver: player shifts (focus team games) on the same game_seconds clock as silver.plays.
create or replace table silver.shifts as
with s as (
    select unnest(json_extract(payload, '$.data[*]')) as d from bronze.nhl_shifts
)
select
    (d ->> '$.id')::bigint as shift_id,
    (d ->> '$.gameId')::bigint as game_id,
    (d ->> '$.playerId')::integer as player_id,
    (d ->> '$.teamId')::integer as team_id,
    (d ->> '$.period')::integer as period,
    ((d ->> '$.period')::integer - 1) * 1200 + mmss_to_seconds(d ->> '$.startTime') as start_seconds,
    ((d ->> '$.period')::integer - 1) * 1200 + mmss_to_seconds(d ->> '$.endTime') as end_seconds
from s
where (d ->> '$.typeCode')::integer = 517  -- 517 = shift; other codes are goal markers
    and (d ->> '$.endTime') is not null
    and mmss_to_seconds(d ->> '$.endTime') > mmss_to_seconds(d ->> '$.startTime')
qualify row_number() over (partition by shift_id order by shift_id) = 1;

comment on table silver.shifts is 'Player shifts from official shift charts; [start_seconds, end_seconds] in game time.';
