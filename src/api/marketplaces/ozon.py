from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

from api.exporters import (
    export_ozon_sync_report_xlsx,
    load_marketplace_feed_rows,
    load_ozon_products_draft_rows,
    save_json,
)
from api.marketplaces.base import MarketplaceBase


class OzonMarketplace(MarketplaceBase):
    name = "ozon"

    def fetch_category_tree(self, output_path: Path | None = None) -> Path | None:
        if not self.settings.ozon_client_id or not self.settings.ozon_api_key:
            print("[ozon] Пропуск: не заданы OZON_CLIENT_ID / OZON_API_KEY")
            return None

        headers = {
            "Client-Id": self.settings.ozon_client_id,
            "Api-Key": self.settings.ozon_api_key,
            "Content-Type": "application/json",
        }
        with httpx.Client(
            base_url=self.settings.ozon_api_base_url,
            timeout=self.settings.timeout,
            headers=headers,
        ) as client:
            response = client.post("/v1/description-category/tree", json={"language": "DEFAULT"})
            print(f"[ozon] Category tree status: {response.status_code}")
            print(f"[ozon] Category tree response: {response.text[:2000]}")
            if output_path is None:
                output_path = Path(self.settings.data_dir) / "ozon" / "category_tree.json"
            saved = save_json(output_path, response.json())
            print(f"[ozon] Дерево категорий сохранено: {saved.resolve()}")
            return saved

    def fetch_category_attributes(
        self,
        category_id: int,
        type_id: int,
        output_path: Path | None = None,
    ) -> Path | None:
        if not self.settings.ozon_client_id or not self.settings.ozon_api_key:
            print("[ozon] Пропуск: не заданы OZON_CLIENT_ID / OZON_API_KEY")
            return None

        headers = {
            "Client-Id": self.settings.ozon_client_id,
            "Api-Key": self.settings.ozon_api_key,
            "Content-Type": "application/json",
        }
        with httpx.Client(
            base_url=self.settings.ozon_api_base_url,
            timeout=self.settings.timeout,
            headers=headers,
        ) as client:
            payload = {
                "attribute_type": "ALL",
                "description_category_id": category_id,
                "type_id": type_id,
                "language": "DEFAULT",
            }
            response = None
            for endpoint in ("/v1/description-category/attribute", "/v3/category/attribute"):
                candidate = client.post(endpoint, json=payload)
                print(f"[ozon] Category attributes endpoint {endpoint} status: {candidate.status_code}")
                print(f"[ozon] Category attributes endpoint {endpoint} response: {candidate.text[:2000]}")
                if candidate.status_code < 400:
                    response = candidate
                    break
            if response is None:
                print("[ozon] Не удалось получить атрибуты категории ни через один endpoint")
                return None
            if output_path is None:
                output_path = (
                    Path(self.settings.data_dir)
                    / "ozon"
                    / f"category_attributes_{category_id}_{type_id}.json"
                )
            saved = save_json(output_path, _safe_json(response))
            print(f"[ozon] Атрибуты категории сохранены: {saved.resolve()}")
            return saved

    def sync(self, feed_path: Path) -> None:
        if not self.settings.ozon_client_id or not self.settings.ozon_api_key:
            print("[ozon] Пропуск: не заданы OZON_CLIENT_ID / OZON_API_KEY")
            return
        rows = load_marketplace_feed_rows(feed_path)
        if not rows:
            print("[ozon] Пропуск: marketplace feed пуст")
            return

        prices_payload = self._build_prices_payload(rows)
        stocks_payload = self._build_stocks_payload(rows)

        output_dir = feed_path.parent / "ozon"
        prices_path = save_json(output_dir / "prices_payload.json", prices_payload)
        stocks_path = save_json(output_dir / "stocks_payload.json", stocks_payload)

        print(f"[ozon] Подготовлен payload цен: {prices_path.resolve()}")
        print(f"[ozon] Подготовлен payload остатков: {stocks_path.resolve()}")
        print(
            f"[ozon] Строк для цен: {len(prices_payload['prices'])} | "
            f"строк для остатков: {len(stocks_payload['stocks'])}"
        )
        print(
            f"[ozon] Цена берётся из поля '{self.settings.marketplace_price_field}'"
            + (
                f", старая цена из '{self.settings.marketplace_old_price_field}'"
                if self.settings.marketplace_old_price_field
                else ""
            )
        )
        print(
            f"[ozon] Остатки считаются из поля '{self.settings.marketplace_stock_field}', "
            f"резерв: {self.settings.marketplace_stock_reserve}, "
            f"лимит: {self.settings.marketplace_stock_cap or 'без лимита'}"
        )

        if self.settings.ozon_dry_run:
            print("[ozon] DRY RUN включён: запросы в Ozon не отправлялись")
            return

        headers = {
            "Client-Id": self.settings.ozon_client_id,
            "Api-Key": self.settings.ozon_api_key,
            "Content-Type": "application/json",
        }

        with httpx.Client(
            base_url=self.settings.ozon_api_base_url,
            timeout=self.settings.timeout,
            headers=headers,
        ) as client:
            price_results = self._post_prices_in_batches(client, prices_payload["prices"])
            stock_results: list[dict] = []

            if not self.settings.ozon_warehouse_id:
                print("[ozon] Остатки пропущены: не задан OZON_WAREHOUSE_ID")
                print("[ozon] Цены уже отправлены. Для остатков понадобится ID склада Ozon.")
            else:
                stock_results = self._post_stocks_in_batches(client, stocks_payload["stocks"])

            report_path = export_ozon_sync_report_xlsx(
                output_dir / "sync_report.xlsx",
                prices_results=price_results,
                stocks_results=stock_results,
                metadata={
                    "stock_field": self.settings.marketplace_stock_field,
                    "stock_reserve": self.settings.marketplace_stock_reserve,
                    "stock_cap": self.settings.marketplace_stock_cap,
                    "warehouse_id": self.settings.ozon_warehouse_id or "",
                },
            )
            print(f"[ozon] Отчёт синка: {report_path.resolve()}")

    def import_products(self, draft_path: Path) -> None:
        if not self.settings.ozon_client_id or not self.settings.ozon_api_key:
            print("[ozon] Пропуск: не заданы OZON_CLIENT_ID / OZON_API_KEY")
            return

        rows = load_ozon_products_draft_rows(draft_path)
        items = self._build_product_items(rows)
        if not items:
            print("[ozon] Нет готовых товаров для импорта. Заполни ozon_category_id и attributes_json в draft.")
            return

        payload = {"items": items}
        output_dir = draft_path.parent / "ozon"
        payload_path = save_json(output_dir / "products_import_payload.json", payload)
        print(f"[ozon] Подготовлен payload карточек: {payload_path.resolve()}")
        print(f"[ozon] Готово к импорту карточек: {len(items)}")

        if self.settings.ozon_dry_run:
            print("[ozon] DRY RUN включён: карточки в Ozon не отправлялись")
            return

        headers = {
            "Client-Id": self.settings.ozon_client_id,
            "Api-Key": self.settings.ozon_api_key,
            "Content-Type": "application/json",
        }
        with httpx.Client(
            base_url=self.settings.ozon_api_base_url,
            timeout=self.settings.timeout,
            headers=headers,
        ) as client:
            for index, batch in enumerate(_chunked(items, 100), start=1):
                response = client.post("/v2/product/import", json={"items": batch})
                print(f"[ozon] Product import batch {index} status: {response.status_code}")
                print(f"[ozon] Product import batch {index} response: {response.text[:2000]}")

    def _build_prices_payload(self, rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
        prices: list[dict[str, str]] = []
        for row in rows:
            offer_id = _offer_id(row)
            price = _decimal_string(row.get(self.settings.marketplace_price_field, ""))
            if not offer_id or not price:
                continue
            entry: dict[str, str] = {
                "offer_id": offer_id,
                "price": price,
                "currency_code": self.settings.ozon_currency_code,
            }
            old_price = ""
            if self.settings.marketplace_old_price_field:
                old_price = _decimal_string(row.get(self.settings.marketplace_old_price_field, ""))
            if old_price and Decimal(old_price) > Decimal(price):
                entry["old_price"] = old_price
            prices.append(entry)
        return {"prices": prices}

    def _build_stocks_payload(self, rows: list[dict[str, str]]) -> dict[str, list[dict[str, int | str]]]:
        stocks: list[dict[str, int | str]] = []
        for row in rows:
            offer_id = _offer_id(row)
            if not offer_id:
                continue
            stock_value = self._resolve_stock_value(row)
            entry: dict[str, int | str] = {
                "offer_id": offer_id,
                "stock": stock_value,
            }
            if self.settings.ozon_warehouse_id:
                entry["warehouse_id"] = self.settings.ozon_warehouse_id
            stocks.append(entry)
        return {"stocks": stocks}

    def _build_product_items(self, rows: list[dict[str, str]]) -> list[dict]:
        items: list[dict] = []
        for row in rows:
            offer_id = (row.get("offer_id") or "").strip()
            category_id = _int_string(row.get("ozon_category_id", ""))
            type_id = _int_string(row.get("ozon_type_id", ""))
            name = (row.get("ozon_name") or row.get("name") or "").strip()
            attributes = _json_list(row.get("attributes_json", "[]"))
            images = _json_list(row.get("images_json", "[]"))
            price = _decimal_string(row.get("price_rrc", ""))

            if not offer_id or not category_id or not type_id or not name or not attributes:
                continue

            item = {
                "offer_id": offer_id,
                "description_category_id": category_id,
                "type_id": type_id,
                "name": name[:500],
                "description": (row.get("description") or "").strip(),
                "attributes": attributes,
                "images": [str(image).strip() for image in images if str(image).strip()],
                "price": price or "0.00",
                "currency_code": self.settings.ozon_currency_code,
                "vat": (row.get("vat") or "0").strip(),
            }
            barcode = (row.get("barcode") or "").strip()
            if barcode:
                item["barcode"] = barcode
            if item["images"]:
                item["primary_image"] = item["images"][0]
            items.append(item)
        return items

    def _post_prices_in_batches(self, client: httpx.Client, prices: list[dict[str, str]]) -> list[dict]:
        results: list[dict] = []
        for index, batch in enumerate(_chunked(prices, 1000), start=1):
            response = client.post("/v1/product/import/prices", json={"prices": batch})
            print(f"[ozon] Prices batch {index} status: {response.status_code}")
            print(f"[ozon] Prices batch {index} response: {response.text[:2000]}")
            results.extend(_flatten_batch_results(index, response.json(), "prices"))
        return results

    def _post_stocks_in_batches(
        self,
        client: httpx.Client,
        stocks: list[dict[str, int | str]],
    ) -> list[dict]:
        results: list[dict] = []
        for index, batch in enumerate(_chunked(stocks, 100), start=1):
            response = client.post("/v2/products/stocks", json={"stocks": batch})
            print(f"[ozon] Stocks batch {index} status: {response.status_code}")
            print(f"[ozon] Stocks batch {index} response: {response.text[:2000]}")
            results.extend(_flatten_batch_results(index, response.json(), "stocks"))
        return results

    def _resolve_stock_value(self, row: dict[str, str]) -> int:
        source_field = self.settings.marketplace_stock_field
        stock = _int_string(row.get(source_field, ""))
        stock = max(stock - self.settings.marketplace_stock_reserve, 0)
        if self.settings.marketplace_stock_cap > 0:
            stock = min(stock, self.settings.marketplace_stock_cap)
        return stock


def _offer_id(row: dict[str, str]) -> str:
    return (row.get("offer_id") or row.get("article") or row.get("supplier_item_id") or "").strip()[:100]


def _decimal_string(value: str) -> str:
    candidate = value.replace(" ", "").replace(",", ".").strip()
    if not candidate:
        return ""
    try:
        normalized = Decimal(candidate)
    except (InvalidOperation, AttributeError):
        return ""
    return f"{normalized:.2f}"


def _int_string(value: str) -> int:
    candidate = value.replace(" ", "").replace(",", ".").strip()
    if not candidate:
        return 0
    try:
        number = Decimal(candidate)
    except (InvalidOperation, AttributeError):
        return 0
    return max(int(number), 0)


def _chunked(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _json_list(value: str) -> list:
    candidate = (value or "").strip()
    if not candidate:
        return []
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _safe_json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = {
            "status_code": response.status_code,
            "text": response.text,
        }
    return payload if isinstance(payload, dict) else {"result": payload}


def _flatten_batch_results(batch_index: int, payload: dict, kind: str) -> list[dict]:
    rows: list[dict] = []
    for item in payload.get("result", []):
        errors = item.get("errors") or []
        warnings = item.get("warnings") or []
        rows.append(
            {
                "batch": batch_index,
                "warehouse_id": item.get("warehouse_id", ""),
                "product_id": item.get("product_id", ""),
                "offer_id": item.get("offer_id", ""),
                "updated": bool(item.get("updated")),
                "error_codes": " | ".join(str(err.get("code", "")) for err in errors),
                "error_messages": " | ".join(str(err.get("message", "")) for err in errors),
                "warning_codes": " | ".join(str(warn.get("code", "")) for warn in warnings),
                "warning_messages": " | ".join(str(warn.get("message", "")) for warn in warnings),
                "kind": kind,
            }
        )
    return rows
