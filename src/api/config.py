from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    base_url: str = "https://astkol.com/catalog"
    user: str = ""
    password_md5: str = ""
    timeout: float = 60.0
    sync_interval_seconds: int = 3600
    enabled_marketplaces: tuple[str, ...] = ("ozon", "wb", "yandex")
    data_dir: str = "data"
    marketplace_price_field: str = "rrc"
    marketplace_old_price_field: str = ""
    marketplace_stock_field: str = "qty"
    marketplace_stock_reserve: int = 0
    marketplace_stock_cap: int = 0
    ozon_client_id: str = ""
    ozon_api_key: str = ""
    ozon_api_base_url: str = "https://api-seller.ozon.ru"
    ozon_warehouse_id: int = 0
    ozon_currency_code: str = "RUB"
    ozon_dry_run: bool = True
    wb_api_key: str = ""
    wb_content_api_base_url: str = "https://content-api.wildberries.ru"
    wb_prices_api_base_url: str = "https://discounts-prices-api.wildberries.ru"
    wb_marketplace_api_base_url: str = "https://marketplace-api.wildberries.ru"
    yandex_campaign_id: str = ""
    yandex_token: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        user = os.getenv("ASTKOL_USER", "").strip()
        password_md5 = os.getenv("ASTKOL_PASSWORD_MD5", "").strip().lower()
        raw_password = os.getenv("ASTKOL_PASSWORD", "")
        if not password_md5 and raw_password:
            password_md5 = hashlib.md5(raw_password.encode("utf-8")).hexdigest()
        timeout = float(os.getenv("ASTKOL_TIMEOUT", "60"))
        sync_interval_seconds = int(os.getenv("SYNC_INTERVAL_SECONDS", "3600"))
        enabled_marketplaces = tuple(
            item.strip().lower()
            for item in os.getenv("ENABLED_MARKETPLACES", "ozon,wb,yandex").split(",")
            if item.strip()
        )
        data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
        return cls(
            user=user,
            password_md5=password_md5,
            timeout=timeout,
            sync_interval_seconds=sync_interval_seconds,
            enabled_marketplaces=enabled_marketplaces,
            data_dir=data_dir,
            marketplace_price_field=os.getenv("MARKETPLACE_PRICE_FIELD", "rrc").strip() or "rrc",
            marketplace_old_price_field=os.getenv("MARKETPLACE_OLD_PRICE_FIELD", "").strip(),
            marketplace_stock_field=os.getenv("MARKETPLACE_STOCK_FIELD", "qty").strip() or "qty",
            marketplace_stock_reserve=int(os.getenv("MARKETPLACE_STOCK_RESERVE", "0")),
            marketplace_stock_cap=int(os.getenv("MARKETPLACE_STOCK_CAP", "0")),
            ozon_client_id=os.getenv("OZON_CLIENT_ID", "").strip(),
            ozon_api_key=os.getenv("OZON_API_KEY", "").strip(),
            ozon_api_base_url=os.getenv("OZON_API_BASE_URL", "https://api-seller.ozon.ru").strip(),
            ozon_warehouse_id=int(os.getenv("OZON_WAREHOUSE_ID", "0")),
            ozon_currency_code=os.getenv("OZON_CURRENCY_CODE", "RUB").strip() or "RUB",
            ozon_dry_run=_as_bool(os.getenv("OZON_DRY_RUN", "1")),
            wb_api_key=os.getenv("WB_API_KEY", "").strip(),
            wb_content_api_base_url=os.getenv(
                "WB_CONTENT_API_BASE_URL", "https://content-api.wildberries.ru"
            ).strip(),
            wb_prices_api_base_url=os.getenv(
                "WB_PRICES_API_BASE_URL", "https://discounts-prices-api.wildberries.ru"
            ).strip(),
            wb_marketplace_api_base_url=os.getenv(
                "WB_MARKETPLACE_API_BASE_URL", "https://marketplace-api.wildberries.ru"
            ).strip(),
            yandex_campaign_id=os.getenv("YANDEX_CAMPAIGN_ID", "").strip(),
            yandex_token=os.getenv("YANDEX_TOKEN", "").strip(),
        )

    def require_credentials(self) -> None:
        if not self.user or not self.password_md5:
            raise RuntimeError(
                "Не заданы ASTKOL_USER и ASTKOL_PASSWORD или ASTKOL_PASSWORD_MD5."
            )


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
