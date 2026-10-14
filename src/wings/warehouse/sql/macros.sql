-- Reusable scalar transforms shared by the silver and gold models.
-- Each macro is unit-tested in tests/test_transforms.py.

-- "MM:SS" clock string -> seconds.
create or replace macro mmss_to_seconds(t) as
    cast(split_part(t, ':', 1) as integer) * 60 + cast(split_part(t, ':', 2) as integer);

-- Does the event-owning team attack the net at x = -89? NHL coordinates are fixed to the rink,
-- so we use the home team's defending side; if missing, assume the shot came from the
-- offensive half of the ice.
create or replace macro attacks_left(is_home, home_defending_side, x) as
    case
        when home_defending_side = 'right' then is_home
        when home_defending_side = 'left' then not is_home
        else x < 0
    end;

-- Distance (ft) and angle (degrees off the goal line normal) to the attacked net at (89, 0),
-- given coordinates already normalized so the shooter attacks +x.
create or replace macro shot_distance(x_norm, y_norm) as
    sqrt(power(89 - x_norm, 2) + power(y_norm, 2));
create or replace macro shot_angle(x_norm, y_norm) as
    degrees(atan2(abs(y_norm), 89 - x_norm));

-- situationCode "ABCD": A = away goalie in net, B = away skaters, C = home skaters,
-- D = home goalie in net. Everything below is from the shooting team's perspective.
create or replace macro skaters_for(code, is_home) as
    cast(substr(code, case when is_home then 3 else 2 end, 1) as integer);
create or replace macro skaters_against(code, is_home) as
    cast(substr(code, case when is_home then 2 else 3 end, 1) as integer);
create or replace macro own_goalie_in_net(code, is_home) as
    substr(code, case when is_home then 4 else 1 end, 1) = '1';
create or replace macro opp_goalie_in_net(code, is_home) as
    substr(code, case when is_home then 1 else 4 end, 1) = '1';

-- Manpower bucket: 5v5, PP (skater advantage), SH (skater disadvantage), other
-- (4v4, 3v3, own goalie pulled for an extra attacker).
create or replace macro manpower(code, is_home) as
    case
        when skaters_for(code, is_home) = 5 and skaters_against(code, is_home) = 5 then '5v5'
        when not own_goalie_in_net(code, is_home) then 'other'
        when skaters_for(code, is_home) > skaters_against(code, is_home) then 'PP'
        when skaters_for(code, is_home) < skaters_against(code, is_home) then 'SH'
        else 'other'
    end;

-- The same game state seen from the other bench.
create or replace macro flip_manpower(m) as
    case m when 'PP' then 'SH' when 'SH' then 'PP' else m end;

-- Zone codes are recorded from the event owner's perspective.
create or replace macro flip_zone(z) as
    case z when 'O' then 'D' when 'D' then 'O' else z end;

-- Collapse rare shot types (bat, poke, between-legs, cradle, unknown) into "other".
create or replace macro shot_type_group(t) as
    case
        when t in ('wrist', 'snap', 'slap', 'backhand', 'tip-in', 'deflected', 'wrap-around') then t
        else 'other'
    end;
