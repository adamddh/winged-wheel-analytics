-- Gold: season-level team splits by strength, with league ranks.
create or replace table gold.team_season_splits as
with by_strength as (
    select season, team_id, strength, count(distinct game_id) as games,
        sum(shots_for) as shots_for, sum(shots_against) as shots_against,
        sum(xgf) as xgf, sum(xga) as xga, sum(gf) as gf, sum(ga) as ga
    from gold.team_game_strength
    group by all
),
all_sit as (
    select season, team_id, 'all' as strength, count(distinct game_id) as games,
        sum(shots_for), sum(shots_against), sum(xgf), sum(xga), sum(gf), sum(ga)
    from gold.team_game_strength
    group by all
),
unioned as (
    select * from by_strength union all select * from all_sit
)
select
    u.*,
    t.abbrev as team,
    xgf / nullif(xgf + xga, 0) as xgf_pct,
    gf - xgf as finishing_above_xg,
    xga - ga as goaltending_above_xg,
    rank() over (partition by season, strength order by xgf / nullif(xgf + xga, 0) desc)
        as xgf_pct_rank
from unioned u
join silver.teams t using (team_id);

comment on table gold.team_season_splits is 'Team season totals by strength (5v5, PP, SH, other, all). finishing_above_xg = GF - xGF; goaltending_above_xg = xGA - GA.';
