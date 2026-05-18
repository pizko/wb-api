from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from api.exporters import load_wb_products_draft_rows, save_json
from api.marketplaces.base import MarketplaceBase

WB_CARDS_UPLOAD_BATCH_SIZE = 100
WB_CONTENT_RATE_LIMIT_DELAY_SECONDS = 0.7
WB_MEDIA_MAX_FILES = 30


class WildberriesMarketplace(MarketplaceBase):
    name = "wb"

    def sync(self, feed_path: Path) -> None:
        if not self.settings.wb_api_key:
            print("[wb] Пропуск: не задан WB_API_KEY")
            return
        print(f"[wb] Заглушка синка готова. Feed: {feed_path.resolve()}")

    def fetch_limits(self, output_path: Path | None = None) -> Path | None:
        response = self._content_get("/content/v2/cards/limits")
        if response is None:
            return None
        if output_path is None:
            output_path = Path(self.settings.data_dir) / "wb" / "limits.json"
        saved = save_json(output_path, _safe_json(response))
        print(f"[wb] Лимиты карточек сохранены: {saved.resolve()}")
        return saved

    def fetch_parent_categories(self, output_path: Path | None = None) -> Path | None:
        response = self._content_get("/content/v2/object/parent/all")
        if response is None:
            return None
        if output_path is None:
            output_path = Path(self.settings.data_dir) / "wb" / "parent_categories.json"
        saved = save_json(output_path, _safe_json(response))
        print(f"[wb] Родительские категории сохранены: {saved.resolve()}")
        return saved

    def fetch_subjects(self, parent_id: int | None = None, output_path: Path | None = None) -> Path | None:
        params = {"limit": 1000}
        if parent_id:
            params["parentID"] = parent_id
        response = self._content_get("/content/v2/object/all", params=params)
        if response is None:
            return None
        if output_path is None:
            suffix = f"_{parent_id}" if parent_id else ""
            output_path = Path(self.settings.data_dir) / "wb" / f"subjects{suffix}.json"
        saved = save_json(output_path, _safe_json(response))
        print(f"[wb] Предметы сохранены: {saved.resolve()}")
        return saved

    def fetch_subject_characteristics(self, subject_id: int, output_path: Path | None = None) -> Path | None:
        response = self._content_get(f"/content/v2/object/charcs/{subject_id}")
        if response is None:
            return None
        if output_path is None:
            output_path = Path(self.settings.data_dir) / "wb" / f"subject_characteristics_{subject_id}.json"
        saved = save_json(output_path, _safe_json(response))
        print(f"[wb] Характеристики предмета сохранены: {saved.resolve()}")
        return saved

    def fetch_characteristics_for_subject_ids(self, subject_ids: list[int], output_dir: Path | None = None) -> None:
        if output_dir is None:
            output_dir = Path(self.settings.data_dir) / "wb" / "characteristics"
        output_dir.mkdir(parents=True, exist_ok=True)
        for subject_id in sorted(set(subject_ids)):
            self.fetch_subject_characteristics(
                subject_id,
                output_dir / f"subject_characteristics_{subject_id}.json",
            )

    def import_products(self, draft_path: Path) -> None:
        rows = load_wb_products_draft_rows(draft_path)
        cards = self._build_cards(rows)
        if not cards:
            print("[wb] Нет готовых карточек для импорта. Заполни wb_parent_id, wb_subject_id и characteristics_json.")
            return

        payload = cards
        output_dir = draft_path.parent / "wb"
        payload_path = save_json(output_dir / "cards_upload_payload.json", payload)
        print(f"[wb] Подготовлен payload карточек: {payload_path.resolve()}")
        print(f"[wb] Готово к импорту карточек: {len(cards)}")
        responses: list[dict] = []
        for idx, batch in enumerate(_chunked(cards, WB_CARDS_UPLOAD_BATCH_SIZE), start=1):
            response = self._content_post("/content/v2/cards/upload", json=batch)
            if response is None:
                continue
            print(f"[wb] Upload batch {idx} status: {response.status_code}")
            print(f"[wb] Upload batch {idx} response: {response.text[:2000]}")
            responses.append(
                {
                    "batch": idx,
                    "cards_count": len(batch),
                    "response": _safe_json(response),
                }
            )
        if responses:
            save_json(output_dir / "cards_upload_response.json", {"batches": responses})

    def upload_media_links(self, draft_path: Path) -> None:
        rows = load_wb_products_draft_rows(draft_path)
        vendor_code_to_images = self._build_vendor_code_to_images(rows)
        if not vendor_code_to_images:
            print("[wb] Нет карточек с images_json для загрузки фото.")
            return

        output_dir = draft_path.parent / "wb"
        cards_index = self._fetch_cards_index(set(vendor_code_to_images))
        if not cards_index:
            print("[wb] Не удалось получить nmID карточек для загрузки фото.")
            return

        responses: list[dict] = []
        missing_vendor_codes: list[str] = []
        uploaded = 0
        for idx, (vendor_code, image_urls) in enumerate(vendor_code_to_images.items(), start=1):
            nm_id = cards_index.get(vendor_code)
            if not nm_id:
                missing_vendor_codes.append(vendor_code)
                continue

            payload = {"nmId": nm_id, "data": image_urls[:WB_MEDIA_MAX_FILES]}
            response = self._content_post("/content/v3/media/save", json=payload)
            if response is None:
                continue
            uploaded += 1
            print(f"[wb] Media batch {idx} nmID {nm_id} status: {response.status_code}")
            print(f"[wb] Media batch {idx} response: {response.text[:2000]}")
            responses.append(
                {
                    "vendorCode": vendor_code,
                    "nmId": nm_id,
                    "images_count": len(payload["data"]),
                    "response": _safe_json(response),
                }
            )
            time.sleep(WB_CONTENT_RATE_LIMIT_DELAY_SECONDS)

        save_json(
            output_dir / "media_upload_response.json",
            {
                "uploaded": uploaded,
                "missing_vendor_codes": missing_vendor_codes,
                "items": responses,
            },
        )
        print(f"[wb] Отправлено карточек на загрузку фото: {uploaded}")
        if missing_vendor_codes:
            print(f"[wb] Не найдено nmID для карточек: {len(missing_vendor_codes)}")

    def _build_cards(self, rows: list[dict[str, str]]) -> list[dict]:
        cards: list[dict] = []
        for row in rows:
            subject_id = _int_or_zero(row.get("wb_subject_id", ""))
            parent_id = _int_or_zero(row.get("wb_parent_id", ""))
            vendor_code = (row.get("vendorCode") or "").strip()
            title = (row.get("title") or "").strip()
            characteristics = _json_list(row.get("characteristics_json", "[]"))
            images = _json_list(row.get("images_json", "[]"))
            if not subject_id or not parent_id or not vendor_code or not title or not characteristics:
                continue
            dimensions = {
                "length": _int_or_zero(row.get("length", "")),
                "width": _int_or_zero(row.get("width", "")),
                "height": _int_or_zero(row.get("height", "")),
            }
            card = {
                "subjectID": subject_id,
                "variants": [
                    {
                        "vendorCode": vendor_code,
                        "title": title[:60],
                        "description": (row.get("description") or "").strip(),
                        "brand": (row.get("brand") or "").strip(),
                        "dimensions": dimensions,
                        "characteristics": characteristics,
                    }
                ],
            }
            variant = card["variants"][0]
            barcode = (row.get("barcode") or "").strip()
            if barcode:
                variant["barcodes"] = [barcode]
            weight = _int_or_zero(row.get("weightBrutto", ""))
            if weight:
                variant["weightBrutto"] = weight
            clean_images = [str(item).strip() for item in images if str(item).strip()]
            if clean_images:
                variant["mediaFiles"] = clean_images
            cards.append(card)
        return cards

    def _content_get(self, path: str, params: dict | None = None) -> httpx.Response | None:
        if not self.settings.wb_api_key:
            print("[wb] Пропуск: не задан WB_API_KEY")
            return None
        headers = {"Authorization": self.settings.wb_api_key}
        with httpx.Client(
            base_url=self.settings.wb_content_api_base_url,
            timeout=self.settings.timeout,
            headers=headers,
        ) as client:
            response = client.get(path, params=params)
            print(f"[wb] GET {path} status: {response.status_code}")
            print(f"[wb] GET {path} response: {response.text[:2000]}")
            return response

    def _content_post(self, path: str, json: dict | list) -> httpx.Response | None:
        if not self.settings.wb_api_key:
            print("[wb] Пропуск: не задан WB_API_KEY")
            return None
        headers = {"Authorization": self.settings.wb_api_key, "Content-Type": "application/json"}
        with httpx.Client(
            base_url=self.settings.wb_content_api_base_url,
            timeout=self.settings.timeout,
            headers=headers,
        ) as client:
            response = client.post(path, json=json)
            return response

    def _fetch_cards_index(self, vendor_codes: set[str]) -> dict[str, int]:
        found: dict[str, int] = {}
        cursor: dict[str, str | int] = {"limit": 100}

        while True:
            payload = {
                "settings": {
                    "sort": {"ascending": True},
                    "filter": {"withPhoto": -1},
                    "cursor": cursor,
                }
            }
            response = self._content_post("/content/v2/get/cards/list", json=payload)
            if response is None:
                break
            print(f"[wb] Cards list status: {response.status_code}")
            print(f"[wb] Cards list response: {response.text[:2000]}")
            data = _safe_json(response)
            cards = data.get("cards") or []
            next_cursor = data.get("cursor") or {}
            for card in cards:
                vendor_code = str(card.get("vendorCode") or "").strip()
                nm_id = _int_or_zero(card.get("nmID", ""))
                if vendor_code and nm_id and vendor_code in vendor_codes:
                    found[vendor_code] = nm_id

            total = int(next_cursor.get("total") or 0)
            if len(found) >= len(vendor_codes) or total < int(cursor["limit"]):
                break

            updated_at = next_cursor.get("updatedAt")
            nm_id_cursor = next_cursor.get("nmID")
            if not updated_at or not nm_id_cursor:
                break
            cursor = {"limit": 100, "updatedAt": updated_at, "nmID": nm_id_cursor}
            time.sleep(WB_CONTENT_RATE_LIMIT_DELAY_SECONDS)

        return found

    def _build_vendor_code_to_images(self, rows: list[dict[str, str]]) -> dict[str, list[str]]:
        vendor_code_to_images: dict[str, list[str]] = {}
        for row in rows:
            vendor_code = (row.get("vendorCode") or "").strip()
            if not vendor_code or vendor_code in vendor_code_to_images:
                continue
            images = _json_list(row.get("images_json", "[]"))
            clean_images = [str(item).strip() for item in images if str(item).strip()]
            if clean_images:
                vendor_code_to_images[vendor_code] = clean_images
        return vendor_code_to_images


def _json_list(value: str) -> list:
    candidate = (value or "").strip()
    if not candidate:
        return []
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _int_or_zero(value: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _safe_json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = {"status_code": response.status_code, "text": response.text}
    return payload if isinstance(payload, dict) else {"result": payload}


def _chunked(items: list[dict], chunk_size: int) -> list[list[dict]]:
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]
