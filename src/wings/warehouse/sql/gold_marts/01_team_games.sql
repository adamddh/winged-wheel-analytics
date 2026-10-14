-- Gold: team-game facts. Every completed game appears twice, once from each bench.
-- xG and "goals" here are measured on the same shot set: unblocked, non-empty-net,
-- non-shootout attempts. final_gf / final_ga are the scoreboard.
create or replace table gold.shots_scored as
select s.*, x.xg, g.game_date, t.abbrev as team, o.abbrev as opponent, p.full_name as shooter
from gold.shots s
join gold.shot_xg x using (shot_id)
join silver.games g using (game_id)
join silver.teams t on t.team_id = s.team_id
join silver.teams o on o.team_id = s.opponent_id
left join silver.players p on p.player_id = s.shooter_id;

comment on table gold.shots_scored is 'gold.shots joined to model xG (non-empty-net, located shots only) plus team, opponent and shooter names.';

create or replace table gold.team_game_strength as
with sides as (
    select game_id, season, game_date, home_team_id as team_id, away_team_id as opponent_id,
        true as is_home
    from silver.games where game_state = 'OFF'
    union all
    select game_id, season, game_date, away_team_id, home_team_id, false
    from silver.games where game_state = 'OFF'
),
-- every shot attributed to both benches, strength from that bench's perspective
perspective as (
    select game_id, team_id, manpower as strength, xg, is_goal, true as is_for
    from gold.shots_scored
    union all
    select game_id, opponent_id, flip_manpower(manpower), xg, is_goal, false
    from gold.shots_scored
)
select
    sides.season, sides.game_id, sides.game_date, sides.team_id, sides.opponent_id,
    sides.is_home, p.strength,
    count(*) filter (where is_for) as shots_for,
    count(*) filter (where not is_for) as shots_against,
    coalesce(sum(xg) filter (where is_for), 0) as xgf,
    coalesce(sum(xg) filter (where not is_for), 0) as xga,
    count(*) filter (where is_for and is_goal) as gf,
    count(*) filter (where not is_for and is_goal) as ga
from sides
join perspective p using (game_id, team_id)
group by all;

comment on table gold.team_game_strength is 'Per team, game and strength (5v5/PP/SH/other from that team''s bench): unblocked shots, xG and goals for/against.';

create or replace table gold.team_games as
with per_game as (
select
    s.season, s.game_id, s.game_date, s.team_id, t.abbrev as team, s.opponent_id,
    o.abbrev as opponent, s.is_home,
    case when s.is_home then g.home_score else g.away_score end as final_gf,
    case when s.is_home then g.away_score else g.home_score end as final_ga,
    case
        when (case when s.is_home then g.home_score > g.away_score
            else g.away_score > g.home_score end) then 'W'
        when g.last_period_type in ('OT', 'SO') then 'OTL'
        else 'L'
    end as result,
    g.last_period_type as decided_in,
    sum(s.shots_for) as shots_for, sum(s.shots_against) as shots_against,
    sum(s.xgf) as xgf, sum(s.xga) as xga, sum(s.gf) as gf, sum(s.ga) as ga,
    coalesce(sum(s.xgf) filter (where strength = '5v5'), 0) as xgf_5v5,
    coalesce(sum(s.xga) filter (where strength = '5v5'), 0) as xga_5v5,
    coalesce(sum(s.gf) filter (where strength = '5v5'), 0) as gf_5v5,
    coalesce(sum(s.ga) filter (where strength = '5v5'), 0) as ga_5v5
from gold.team_game_strength s
join silver.games g using (game_id)
join silver.teams t on t.team_id = s.team_id
join silver.teams o on o.team_id = s.opponent_id
group by all
)
select
    *,
    row_number() over (partition by season, team_id order by game_date, game_id)
        as team_game_number
from per_game;

comment on table gold.team_games is 'One row per team per completed game: result, scoreboard, and xG/goals for and against (all situations and 5v5).';
comment on column gold.team_games.gf is 'Goals on the xG shot set (excludes empty-net and shootout goals).';
comment on column gold.team_games.final_gf is 'Scoreboard goals for, including shootout winner.';
