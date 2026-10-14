"""MoneyPuck public shot data (https://moneypuck.com/data.htm), used to validate our xG.

MoneyPuck labels seasons by start year: shots_2025.zip is the 2025-26 season.
"""

import io
import logging
import time
import zipfile

from wings.config import Settings
from wings.ingest.http import ThrottledClient, write_atomic

log = logging.getLogger(__name__)

URL = "https://moneypuck.com/moneypuck/playerData/shots/shots_{year}.zip"
CURRENT_MAX_AGE_S = 12 * 3600  # MoneyPuck refreshes nightly


def run(settings: Settings, client: ThrottledClient | None = None) -> None:
    client = client or ThrottledClient(settings.request_interval_s)
    for season in settings.analysis_seasons:
        year = season // 10000
        path = settings.raw_dir / "moneypuck" / f"shots_{year}.csv"
        current = season == settings.current_season
        if path.exists() and (
            not current or time.time() - path.stat().st_mtime < CURRENT_MAX_AGE_S
        ):
            continue
        resp = client.get(URL.format(year=year))
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            write_atomic(path, zf.read(f"shots_{year}.csv"))
        log.info("moneypuck: refreshed %s", path)
