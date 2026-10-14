-- Silver: player shifts (focus team games) on the same game_seconds clock as silver.plays.
-- The NHL feed repeats some shifts under different ids (exact copies and nested fragments),
-- which double-counted TOI and put 7+ skaters on the ice. Overlapping intervals for the same
-- player are merged with gaps-and-islands, so every second of ice time is counted once.
create or replace table silver.shifts as
with s as (
    select unnest(json_extract(payload, '$.data[*]')) as d from bronze.nhl_shifts
),
typed as (
    select
        (d ->> '$.id')::bigint as shift_id,
        (d ->> '$.gameId')::bigint as game_id,
        (d ->> '$.playerId')::integer as player_id,
        (d ->> '$.teamId')::integer as team_id,
        (d ->> '$.period')::integer as period,
        ((d ->> '$.period')::integer - 1) * 1200 + mmss_to_seconds(d ->> '$.startTime')
            as start_seconds,
        ((d ->> '$.period')::integer - 1) * 1200 + mmss_to_seconds(d ->> '$.endTime')
            as end_seconds
    from s
    where (d ->> '$.typeCode')::integer = 517  -- 517 = shift; other codes are goal markers
        and (d ->> '$.endTime') is not null
        and mmss_to_seconds(d ->> '$.endTime') > mmss_to_seconds(d ->> '$.startTime')
),
flagged as (
    select
        *,
        -- a new island starts unless this shift overlaps an earlier one for the same player
        coalesce(
            start_seconds >= max(end_seconds) over (
                partition by game_id, player_id order by start_seconds, end_seconds, shift_id
                rows between unbounded preceding and 1 preceding
            ),
            true
        )::int as new_island
    from typed
),
islands as (
    select
        *,
        sum(new_island) over (
            partition by game_id, player_id order by start_seconds, end_seconds, shift_id
        ) as island
    from flagged
)
select
    min(shift_id) as shift_id,
    game_id,
    player_id,
    any_value(team_id) as team_id,
    min(period) as period,
    min(start_seconds) as start_seconds,
    max(end_seconds) as end_seconds,
    count(*) as source_records
from islands
group by game_id, player_id, island;

comment on table silver.shifts is 'Player shifts from official shift charts; [start_seconds, end_seconds] in game time, overlapping duplicates merged.';
comment on column silver.shifts.source_records is 'Raw shift records merged into this interval (>1 means the feed repeated it).';
