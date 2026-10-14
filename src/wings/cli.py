import argparse
import logging

from wings.config import load_settings
from wings.ingest import moneypuck, nhl


def ingest(settings) -> None:
    if settings.offline:
        logging.info("offline mode: skipping ingest")
        return
    nhl.run(settings)
    moneypuck.run(settings)


def main() -> None:
    parser = argparse.ArgumentParser(prog="wings")
    parser.add_argument("command", choices=["ingest", "pipeline"])
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = load_settings(args.config)
    ingest(settings)


if __name__ == "__main__":
    main()
