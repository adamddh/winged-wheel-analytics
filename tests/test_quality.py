import json

import pytest

from wings.quality.checks import Check, QualityError, run


def test_error_checks_fail_the_run_and_warnings_do_not(con, tmp_path):
    con.execute("create table t as select * from (values (1), (1), (2)) v(id)")
    report = tmp_path / "quality.json"
    dup = Check(
        "t unique",
        "duplicate_keys",
        "select count(*) from (select id from t group by id having count(*) > 1)",
    )
    warn = Check("t has 10 rows", "row_count", "select 10 - count(*) from t", severity="warn")

    run(con, [warn], report, "base")  # warning only: passes
    with pytest.raises(QualityError, match="t unique"):
        run(con, [dup, warn], report, "base")

    results = json.loads(report.read_text())["base"]["results"]
    assert [(r["name"], r["violations"], r["passed"]) for r in results] == [
        ("t unique", 1, False),
        ("t has 10 rows", 7, False),
    ]
