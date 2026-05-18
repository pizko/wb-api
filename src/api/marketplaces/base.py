from __future__ import annotations

from pathlib import Path

from api.config import Settings


class MarketplaceBase:
    name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_enabled(self) -> bool:
        return self.name in self.settings.enabled_marketplaces

    def sync(self, feed_path: Path) -> None:
        raise NotImplementedError
