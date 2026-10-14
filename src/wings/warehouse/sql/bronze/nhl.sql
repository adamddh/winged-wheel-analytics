-- Bronze: raw API payloads exactly as fetched, one row per cached file.
-- Nothing is parsed or filtered here; this is the replayable source of truth.

create or replace table bronze.nhl_schedule as
select filename as source_file, content::json as payload, last_modified as ingested_at
from read_text('{{raw_dir}}/nhl/schedule/*/*.json');

create or replace table bronze.nhl_pbp as
select filename as source_file, content::json as payload, last_modified as ingested_at
from read_text('{{raw_dir}}/nhl/pbp/*/*.json');

create or replace table bronze.nhl_shifts as
select filename as source_file, content::json as payload, last_modified as ingested_at
from read_text('{{raw_dir}}/nhl/shifts/*/*.json');

create or replace table bronze.nhl_rosters as
select filename as source_file, content::json as payload, last_modified as ingested_at
from read_text('{{raw_dir}}/nhl/roster/*/*.json');

comment on table bronze.nhl_schedule is 'Raw weekly schedule payloads from api-web.nhle.com/v1/schedule/{date}.';
comment on table bronze.nhl_pbp is 'Raw play-by-play payloads from api-web.nhle.com/v1/gamecenter/{id}/play-by-play.';
comment on table bronze.nhl_shifts is 'Raw shift charts from api.nhle.com/stats/rest/en/shiftcharts (focus team games).';
comment on table bronze.nhl_rosters is 'Raw team roster payloads from api-web.nhle.com/v1/roster/{team}/{season}.';
