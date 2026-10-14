import json
import logging
import os
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

USER_AGENT = (
    "winged-wheel-analytics/0.1 (portfolio project; github.com/adamddh/winged-wheel-analytics)"
)


class ThrottledClient:
    """httpx client with a minimum interval between requests and backoff on 429/5xx."""

    def __init__(self, interval_s: float = 0.1, transport: httpx.BaseTransport | None = None):
        self.interval_s = interval_s
        self._last = 0.0
        self.http = httpx.Client(
            timeout=60,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )

    def get(self, url: str, retries: int = 5) -> httpx.Response:
        for attempt in range(retries):
            wait = self._last + self.interval_s - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self.http.get(url)
            except httpx.TransportError as exc:
                log.warning("transport error on %s (%s), retrying", url, exc)
            else:
                if resp.status_code != 429 and resp.status_code < 500:
                    resp.raise_for_status()
                    return resp
                log.warning("HTTP %s on %s, backing off", resp.status_code, url)
            time.sleep(min(2**attempt, 30))
        raise RuntimeError(f"giving up on {url} after {retries} attempts")

    def get_json(self, url: str):
        return self.get(url).json()


def write_atomic(path: Path, data: bytes) -> None:
    """Write via temp file + rename so a crash never leaves a half-written cache file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_json(path: Path, obj) -> None:
    write_atomic(path, json.dumps(obj).encode())
