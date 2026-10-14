-- Gold: our xG vs MoneyPuck's public xG, per team-game, for every season MoneyPuck covers.
-- MoneyPuck identifies teams by abbreviation, which is not unique over time (UTA has two
-- franchise ids), so map it through that game's home/away abbreviations.
create or replace table gold.xg_validation_team_games as
with mp as (
    select
        m.game_id,
        case replace(m.team, '.', '')
            when g.home_team then g.home_team_id
            when g.away_team then g.away_team_id
        end as team_id,
        sum(m.mp_xg) as mp_xgf
    from silver.moneypuck_shots m
    join silver.games g using (game_id)
    where not m.is_empty_net
    group by all
)
select tg.season, tg.game_id, tg.team, tg.xgf, mp.mp_xgf, tg.gf
from gold.team_games tg
join mp using (game_id, team_id);

comment on table gold.xg_validation_team_games is 'Team-game xGF from our model next to MoneyPuck''s xGF for the same games.';
