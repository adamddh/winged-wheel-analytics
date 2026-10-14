"""Generate docs/schema.md from the warehouse catalog, so schema docs never drift from the
SQL models: table and column descriptions come from COMMENT ON statements in the models."""

from pathlib import Path

import duckdb

LAYERS = {
    "bronze": "Raw payloads exactly as ingested (replayable source of truth).",
    "silver": "Cleaned, typed, deduplicated entities.",
    "gold": "Analytics-ready facts, features and marts.",
}


def write_schema_docs(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    lines = [
        "# Warehouse schema",
        "",
        "_Generated from the DuckDB catalog by `make pipeline`. Do not edit by hand._",
        "",
    ]
    for schema, blurb in LAYERS.items():
        lines += [f"## {schema}", "", blurb, ""]
        tables = con.execute(
            "select table_name, comment, estimated_size from duckdb_tables() "
            "where schema_name = ? order by table_name",
            [schema],
        ).fetchall()
        for table, comment, rows in tables:
            lines += [f"### `{schema}.{table}`", "", comment or "", "", f"~{rows:,} rows", ""]
            if schema == "bronze":
                continue
            lines += ["| column | type | description |", "|---|---|---|"]
            for col, dtype, ccomment in con.execute(
                "select column_name, data_type, comment from duckdb_columns() "
                "where schema_name = ? and table_name = ? order by column_index",
                [schema, table],
            ).fetchall():
                lines.append(f"| `{col}` | {dtype} | {ccomment or ''} |")
            lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
