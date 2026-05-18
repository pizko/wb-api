from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from api.client import AstkolClient
from api.config import Settings
from api.exporters import export_catalog_xlsx, export_groups_xlsx, export_marketplace_feed_xlsx
from api.marketplaces import OzonMarketplace, WildberriesMarketplace, YandexMarketplace


def run_sync_once(settings: Settings, output_dir: Path | None = None) -> Path:
    base_dir = output_dir or Path(settings.data_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"[sync] Старт синка: {datetime.now(timezone.utc).isoformat()}")
    with AstkolClient(settings) as client:
        items = client.fetch_catalog()
        groups = client.fetch_groups()
        links = client.fetch_group_links()

    catalog_path = export_catalog_xlsx(base_dir / "catalog.xlsx", items)
    groups_path = export_groups_xlsx(base_dir / "groups.xlsx", groups, links)
    feed_path = export_marketplace_feed_xlsx(base_dir / "marketplace_feed.xlsx", items, groups, links)

    print(f"[sync] Каталог сохранён: {catalog_path.resolve()}")
    print(f"[sync] Группы сохранены: {groups_path.resolve()}")
    print(f"[sync] Feed сохранён: {feed_path.resolve()}")
    print(f"[sync] Товаров: {len(items)} | Групп: {len(groups)} | Привязок: {len(links)}")

    for marketplace in (
        OzonMarketplace(settings),
        WildberriesMarketplace(settings),
        YandexMarketplace(settings),
    ):
        if marketplace.is_enabled():
            marketplace.sync(feed_path)

    print(f"[sync] Финиш синка: {datetime.now(timezone.utc).isoformat()}")
    return feed_path


def run_sync_loop(settings: Settings, output_dir: Path | None = None) -> None:
    interval = max(settings.sync_interval_seconds, 60)
    print(f"[sync-loop] Интервал: {interval} сек")
    while True:
        try:
            run_sync_once(settings, output_dir=output_dir)
        except Exception as exc:
            print(f"[sync-loop] Ошибка: {exc}")
        print(f"[sync-loop] Сон {interval} сек")
        time.sleep(interval)
