-- Gold: our xG vs MoneyPuck's public xG, per team-game, for every season MoneyPuck covers.
create or replace table gold.xg_validation_team_games as
with mp as (
    select m.game_id, t.team_id, sum(m.mp_xg) as mp_xgf
    from silver.moneypuck_shots m
    join silver.teams t on t.abbrev = replace(m.team, '.', '')
    where not m.is_empty_net
    group by all
)
select tg.season, tg.game_id, tg.team, tg.xgf, mp.mp_xgf, tg.gf
from gold.team_games tg
join mp using (game_id, team_id);

comment on table gold.xg_validation_team_games is 'Team-game xGF from our model next to MoneyPuck''s xGF for the same games.';
