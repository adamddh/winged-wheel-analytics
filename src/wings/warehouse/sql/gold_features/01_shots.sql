-- Gold: one row per unblocked shot attempt (Fenwick: shots on goal, misses, goals), with the
-- engineered features the xG model uses. Shootout attempts are excluded.
create or replace table gold.shots as
with ordered as (
    select
        p.*,
        lag(event_type) over w as prev_event_type,
        lag(team_id) over w as prev_team_id,
        lag(zone_code) over w as prev_zone_code,
        lag(game_seconds) over w as prev_game_seconds,
        lag(period) over w as prev_period,
        coalesce(sum(case when event_type = 'goal' and is_home then 1 end) over before, 0)
            as home_goals_before,
        coalesce(sum(case when event_type = 'goal' and not is_home then 1 end) over before, 0)
            as away_goals_before
    from silver.plays p
    window
        w as (partition by game_id order by sort_order),
        before as (partition by game_id order by sort_order
            rows between unbounded preceding and 1 preceding)
),
shots as (
    select
        *,
        case when attacks_left(is_home, home_defending_side, x) then -x else x end as x_norm,
        case when attacks_left(is_home, home_defending_side, x) then -y else y end as y_norm,
        game_seconds - prev_game_seconds as seconds_since_prev,
        case when is_home then home_goals_before - away_goals_before
            else away_goals_before - home_goals_before end as score_diff
    from ordered
    where event_type in ('shot-on-goal', 'missed-shot', 'goal')
        and period_type <> 'SO'
        and team_id is not null
)
select
    game_id * 100000000 + event_id as shot_id,
    game_id,
    event_id,
    season,
    period,
    game_seconds,
    team_id,
    case when is_home then away_team_id else home_team_id end as opponent_id,
    is_home,
    shooter_id,
    goalie_id,
    event_type,
    event_type = 'goal' as is_goal,
    x_norm,
    y_norm,
    shot_distance(x_norm, y_norm) as distance,
    shot_angle(x_norm, y_norm) as angle,
    shot_type_group(shot_type) as shot_type,
    coalesce(
        prev_period = period and seconds_since_prev <= 3
        and (
            (prev_event_type in ('shot-on-goal', 'missed-shot') and prev_team_id = team_id)
            or prev_event_type = 'blocked-shot'
        ),
        false
    ) as is_rebound,
    coalesce(
        prev_period = period and seconds_since_prev <= 4
        and (case when prev_team_id = team_id then prev_zone_code
            else flip_zone(prev_zone_code) end) in ('N', 'D'),
        false
    ) as is_rush,
    situation_code,
    manpower(situation_code, is_home) as manpower,
    score_diff,
    greatest(least(score_diff, 2), -2) as score_state,
    not opp_goalie_in_net(situation_code, is_home) as is_empty_net
from shots;

comment on table gold.shots is 'Unblocked shot attempts with xG features. Coordinates normalized so the shooter attacks the net at (89, 0).';
comment on column gold.shots.shot_id is 'Surrogate key: game_id * 1e8 + event_id (NHL event ids reach the millions).';
comment on column gold.shots.distance is 'Feet from the attacked goal at (89, 0).';
comment on column gold.shots.angle is 'Degrees off the line through the center of the net; >90 means behind the goal line.';
comment on column gold.shots.is_rebound is 'Previous event was a shot attempt within 3 seconds in the same period.';
comment on column gold.shots.is_rush is 'Previous event was in the neutral or defensive zone (shooter perspective) within 4 seconds.';
comment on column gold.shots.manpower is '5v5, PP, SH, or other (4v4, 3v3, extra attacker), shooter perspective.';
comment on column gold.shots.score_state is 'Shooter score differential before the shot, clipped to [-2, 2].';
comment on column gold.shots.is_empty_net is 'Opponent goalie not in net. Excluded from the xG model.';
