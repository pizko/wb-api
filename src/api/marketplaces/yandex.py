from __future__ import annotations

from pathlib import Path

from api.marketplaces.base import MarketplaceBase


class YandexMarketplace(MarketplaceBase):
    name = "yandex"

    def sync(self, feed_path: Path) -> None:
        if not self.settings.yandex_campaign_id or not self.settings.yandex_token:
            print("[yandex] Пропуск: не заданы YANDEX_CAMPAIGN_ID / YANDEX_TOKEN")
            return
        print(
            "[yandex] Заглушка синка готова. "
            f"Feed: {feed_path.resolve()} | Campaign: {self.settings.yandex_campaign_id}"
        )
