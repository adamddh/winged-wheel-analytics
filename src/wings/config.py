import os
import tomllib
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    data_dir: Path = Path("data")
    team: str = "DET"
    train_seasons: list[int]
    test_season: int
    current_season: int
    request_interval_s: float = 0.1
    focus_players: dict[str, int]
    min_games: dict[int, int]
    freshness_hours: int = 36
    output_dir: Path = Path(".")
    export_uri: str | None = None  # e.g. s3://bucket/wings to mirror gold exports
    offline: bool = False

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "warehouse.duckdb"

    @property
    def seasons(self) -> list[int]:
        """Every season the pipeline ingests, oldest first."""
        return sorted({*self.train_seasons, self.test_season, self.current_season})

    @property
    def analysis_seasons(self) -> list[int]:
        """Seasons with focus-team depth (shifts, rosters, MoneyPuck validation)."""
        return sorted({self.test_season, self.current_season})


def load_settings(path: str | Path | None = None) -> Settings:
    path = Path(path or os.environ.get("WINGS_CONFIG", "wings.toml"))
    settings = Settings(**tomllib.loads(path.read_text()))
    if os.environ.get("WINGS_OFFLINE") == "1":
        settings.offline = True
    return settings
