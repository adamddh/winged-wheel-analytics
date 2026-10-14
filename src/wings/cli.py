import argparse
import logging
import sys
import time

from wings.analysis import report
from wings.config import Settings, load_settings
from wings.ingest import moneypuck, nhl
from wings.models import xg
from wings.quality import checks
from wings.warehouse import docs
from wings.warehouse.build import build, connect

log = logging.getLogger("wings")


def ingest(settings: Settings) -> None:
    if settings.offline:
        log.info("offline mode: skipping ingest, using cached data/raw")
        return
    nhl.run(settings)
    moneypuck.run(settings)


def pipeline(settings: Settings) -> dict:
    out = settings.output_dir
    steps = []

    def step(name, fn):
        t = time.perf_counter()
        result = fn()
        steps.append((name, time.perf_counter() - t))
        log.info("step %-22s %6.1fs", name, steps[-1][1])
        return result

    step("ingest", lambda: ingest(settings))
    con = connect(settings)
    try:
        step("build bronze/silver/gold", lambda: build(con, settings, "base"))
        quality_report = out / "reports" / "quality.json"
        step(
            "quality (base)",
            lambda: checks.run(con, checks.base_checks(settings), quality_report, "base"),
        )
        metrics = step("train + score xG", lambda: xg.run(con, settings, out / "models"))
        step("build gold marts", lambda: build(con, settings, "marts"))
        step(
            "quality (marts)",
            lambda: checks.run(con, checks.mart_checks(settings), quality_report, "marts"),
        )
        step("schema docs", lambda: docs.write_schema_docs(con, out / "docs" / "schema.md"))
        step("reports + exports", lambda: report.run(con, settings, metrics))
    finally:
        con.close()
    log.info("pipeline complete in %.1fs", sum(s for _, s in steps))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(prog="wings", description="Red Wings hockey-ops pipeline")
    parser.add_argument("command", choices=["ingest", "pipeline"])
    parser.add_argument("--config", default=None, help="path to TOML config (default wings.toml)")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = load_settings(args.config)
    try:
        if args.command == "ingest":
            ingest(settings)
        else:
            pipeline(settings)
    except checks.QualityError as exc:
        log.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
