-- Bronze: MoneyPuck shot CSVs, all columns kept as text. Typing happens in silver.
create or replace table bronze.moneypuck_shots as
select *
from read_csv('{{raw_dir}}/moneypuck/shots_*.csv', all_varchar = true, union_by_name = true, filename = true);

comment on table bronze.moneypuck_shots is 'Raw MoneyPuck shot-level CSVs (moneypuck.com/data.htm), all text.';
