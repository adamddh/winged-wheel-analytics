-- Gold: player season stats. Individual stats league-wide; TOI and on-ice stats only where
-- shift charts were ingested (focus team, analysis seasons).
create or replace table gold.player_seasons as
with gp as (
    select g.season, r.player_id, arg_max(r.team_id, g.game_date) as team_id,
        count(distinct r.game_id) as games_played
    from silver.game_rosters r
    join silver.games g using (game_id)
    group by all
),
goals as (
    select season, shooter_id, assist1_id, assist2_id from silver.plays
    where event_type = 'goal' and period_type <> 'SO'  -- shootout goals aren't credited
),
points as (
    select season, player_id, count(*) filter (where role = 'G') as goals,
        count(*) filter (where role = 'A') as assists
    from (
        select season, shooter_id as player_id, 'G' as role from goals
        union all
        select season, assist1_id, 'A' from goals
        union all
        select season, assist2_id, 'A' from goals
    )
    where player_id is not null
    group by all
),
individual as (
    select season, shooter_id as player_id,
        count(*) filter (where event_type in ('shot-on-goal', 'goal')) as shots_on_goal,
        count(*) as unblocked_attempts,
        sum(xg) as ixg,
        sum(xg) filter (where manpower = '5v5') as ixg_5v5,
        sum(xg) filter (where manpower = 'PP') as ixg_pp,
        count(*) filter (where is_goal) as goals_xg_set
    from gold.shots_scored
    group by all
),
-- The NHL does not publish shift charts for every game, so TOI-based rates use only the
-- games that have them, with ixG restricted to the same games.
toi as (
    select g.season, sh.player_id, count(distinct sh.game_id) as games_with_shifts,
        sum(sh.end_seconds - sh.start_seconds) as toi_seconds
    from silver.shifts sh
    join silver.games g using (game_id)
    group by all
),
ixg_shift_games as (
    select s.season, s.shooter_id as player_id, sum(s.xg) as ixg
    from gold.shots_scored s
    where exists (
        select 1 from silver.shifts sh where sh.game_id = s.game_id and sh.player_id = s.shooter_id
    )
    group by all
),
-- A shot at time t is on-ice for a player when start_seconds < t <= end_seconds.
on_ice as (
    select s.season, sh.player_id,
        sum(s.xg) filter (where s.team_id = sh.team_id and s.manpower = '5v5') as oi_xgf_5v5,
        sum(s.xg) filter (where s.team_id <> sh.team_id and s.manpower = '5v5') as oi_xga_5v5,
        count(*) filter (where s.team_id = sh.team_id and s.manpower = '5v5' and s.is_goal)
            as oi_gf_5v5,
        count(*) filter (where s.team_id <> sh.team_id and s.manpower = '5v5' and s.is_goal)
            as oi_ga_5v5,
        sum(s.xg) filter (where s.team_id = sh.team_id) as oi_xgf_all,
        sum(s.xg) filter (where s.team_id <> sh.team_id) as oi_xga_all
    from gold.shots_scored s
    join silver.shifts sh
        on sh.game_id = s.game_id
        and s.game_seconds > sh.start_seconds and s.game_seconds <= sh.end_seconds
    group by all
)
select
    gp.season, gp.player_id, p.full_name, p.position, t.abbrev as team, gp.games_played,
    coalesce(pt.goals, 0) as goals, coalesce(pt.assists, 0) as assists,
    coalesce(pt.goals, 0) + coalesce(pt.assists, 0) as points,
    coalesce(i.shots_on_goal, 0) as shots_on_goal,
    coalesce(i.unblocked_attempts, 0) as unblocked_attempts,
    coalesce(i.ixg, 0) as ixg, coalesce(i.ixg_5v5, 0) as ixg_5v5, coalesce(i.ixg_pp, 0) as ixg_pp,
    coalesce(i.goals_xg_set, 0) - coalesce(i.ixg, 0) as goals_above_ixg,
    toi.games_with_shifts,
    toi.toi_seconds,
    toi.toi_seconds / 60.0 / toi.games_with_shifts as toi_per_game_min,
    3600.0 * coalesce(isg.ixg, 0) / nullif(toi.toi_seconds, 0) as ixg_per_60,
    oi.oi_xgf_5v5, oi.oi_xga_5v5, oi.oi_gf_5v5, oi.oi_ga_5v5,
    oi.oi_xgf_5v5 / nullif(oi.oi_xgf_5v5 + oi.oi_xga_5v5, 0) as oi_xgf_pct_5v5,
    oi.oi_xgf_all, oi.oi_xga_all
from gp
join silver.players p using (player_id)
join silver.teams t on t.team_id = gp.team_id
left join points pt using (season, player_id)
left join individual i using (season, player_id)
left join toi using (season, player_id)
left join ixg_shift_games isg using (season, player_id)
left join on_ice oi using (season, player_id)
where p.position <> 'G';

comment on table gold.player_seasons is 'Skater season stats: scoring, individual xG (ixg), and where shift data exists, TOI and 5v5 on-ice xG for/against.';
comment on column gold.player_seasons.games_with_shifts is 'Games with published NHL shift charts; denominator for TOI and on-ice stats.';
comment on column gold.player_seasons.oi_xgf_pct_5v5 is 'Share of 5v5 xG that was for the player''s team while he was on the ice.';

-- Focus players always get a card for both analysis seasons, even with zero games played.
create or replace table gold.player_cards as
select f.name as card_name, f.player_id, s.season, ps.* exclude (player_id, season)
from meta.focus_players f
cross join (select unnest([getvariable('test_season'), getvariable('current_season')]) as season) s
left join gold.player_seasons ps on ps.player_id = f.player_id and ps.season = s.season;

comment on table gold.player_cards is 'Player-card rows for the configured focus players, held-out and current season (null stats = did not play).';
