-- Silver: typed MoneyPuck regular-season shots keyed to NHL game ids, for xG validation.
create or replace table silver.moneypuck_shots as
with typed as (
    select
        season::integer * 1000000 + game_id::integer as game_id,
        season::integer * 10001 + 1 as season,  -- MoneyPuck 2025 -> NHL 20252026
        shotID::integer as mp_shot_id,
        period::integer as period,
        time::integer as game_seconds,
        try_cast(try_cast(shooterPlayerId as double) as integer) as shooter_id,
        teamCode as team,
        event,
        shotType as shot_type,
        xGoal::double as mp_xg,
        goal::integer = 1 as is_goal,
        shotOnEmptyNet::integer = 1 as is_empty_net
    from bronze.moneypuck_shots
    where isPlayoffGame = '0'
)
select * from typed
qualify row_number() over (partition by season, mp_shot_id order by game_id) = 1;

comment on table silver.moneypuck_shots is 'MoneyPuck unblocked shot attempts with their public xG (mp_xg), regular season only.';
