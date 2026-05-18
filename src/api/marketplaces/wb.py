from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from api.exporters import load_wb_products_draft_rows, load_wb_template_rows, save_json, save_wb_products_draft_rows_xlsx
from api.marketplaces.base import MarketplaceBase

WB_CARDS_UPLOAD_BATCH_SIZE = 100
WB_CONTENT_RATE_LIMIT_DELAY_SECONDS = 0.7
WB_MEDIA_MAX_FILES = 30
WB_HTTP_RETRY_COUNT = 3
WB_HTTP_RETRY_DELAY_SECONDS = 1.5
WB_IMPORT_BATCH_DELAY_SECONDS = 10.0


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

    def import_products(self, draft_path: Path, batch_delay_seconds: float = WB_IMPORT_BATCH_DELAY_SECONDS) -> None:
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
            if batch_delay_seconds > 0:
                time.sleep(batch_delay_seconds)
        if responses:
            save_json(output_dir / "cards_upload_response.json", {"batches": responses})

    def build_products_draft_from_template(self, template_path: Path, output_path: Path) -> Path:
        rows = load_wb_template_rows(template_path)
        if not rows:
            raise RuntimeError("В WB-шаблоне нет строк с товарами")

        category_names = sorted({row.get("Категория продавца", "").strip() for row in rows if row.get("Категория продавца", "").strip()})
        subject_lookup = self._resolve_subjects_for_categories(category_names)
        missing_categories = [name for name in category_names if name not in subject_lookup]
        if missing_categories:
            raise RuntimeError(f"Не удалось найти WB subject для категорий: {', '.join(missing_categories)}")

        subject_characteristics: dict[int, list[dict]] = {}
        draft_rows: list[dict[str, str]] = []
        for row in rows:
            category_name = row.get("Категория продавца", "").strip()
            parent_id, subject_id, subject_name = subject_lookup[category_name]
            if subject_id not in subject_characteristics:
                subject_characteristics[subject_id] = self._load_subject_characteristics(subject_id)

            characteristics_json = json.dumps(
                _build_wb_characteristics_from_template_row(row, subject_characteristics[subject_id]),
                ensure_ascii=False,
            )
            images = _split_delimited(row.get("Фото", ""))
            draft_rows.append(
                {
                    "vendorCode": row.get("Артикул продавца", ""),
                    "title": row.get("Наименование", ""),
                    "description": row.get("Описание", ""),
                    "brand": row.get("Бренд", ""),
                    "price_rrc": row.get("Цена", ""),
                    "length": row.get("Длина упаковки", ""),
                    "width": row.get("Ширина упаковки", ""),
                    "height": row.get("Высота упаковки", ""),
                    "weightBrutto": row.get("Вес товара с упаковкой (г)", "") or _kg_to_grams(row.get("Вес с упаковкой (кг)", "")),
                    "barcode": _first_value(row.get("Баркоды", "")),
                    "images_json": json.dumps(images, ensure_ascii=False),
                    "supplier_group_name": category_name,
                    "supplier_group_tree": "",
                    "wb_parent_id": str(parent_id),
                    "wb_subject_id": str(subject_id),
                    "wb_subject_name": subject_name,
                    "characteristics_json": characteristics_json,
                    "comment": "built_from_wb_template",
                }
            )

        saved = save_wb_products_draft_rows_xlsx(output_path, draft_rows)
        print(f"[wb] Собран WB draft из шаблона: {saved.resolve()}")
        print(f"[wb] Строк в draft: {len(draft_rows)}")
        print(f"[wb] Уникальных категорий: {len(category_names)}")
        return saved

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
            barcodes = _split_delimited(row.get("barcode", ""))
            if barcodes:
                variant["barcodes"] = barcodes
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
        for attempt in range(1, WB_HTTP_RETRY_COUNT + 1):
            try:
                with httpx.Client(
                    base_url=self.settings.wb_content_api_base_url,
                    timeout=self.settings.timeout,
                    headers=headers,
                ) as client:
                    response = client.get(path, params=params)
                    print(f"[wb] GET {path} status: {response.status_code}")
                    print(f"[wb] GET {path} response: {response.text[:2000]}")
                    return response
            except httpx.HTTPError as exc:
                print(f"[wb] GET {path} attempt {attempt}/{WB_HTTP_RETRY_COUNT} failed: {exc}")
                if attempt == WB_HTTP_RETRY_COUNT:
                    return None
                time.sleep(WB_HTTP_RETRY_DELAY_SECONDS)
        return None

    def _content_post(self, path: str, json: dict | list) -> httpx.Response | None:
        if not self.settings.wb_api_key:
            print("[wb] Пропуск: не задан WB_API_KEY")
            return None
        headers = {"Authorization": self.settings.wb_api_key, "Content-Type": "application/json"}
        for attempt in range(1, WB_HTTP_RETRY_COUNT + 1):
            try:
                with httpx.Client(
                    base_url=self.settings.wb_content_api_base_url,
                    timeout=self.settings.timeout,
                    headers=headers,
                ) as client:
                    response = client.post(path, json=json)
                    return response
            except httpx.HTTPError as exc:
                print(f"[wb] POST {path} attempt {attempt}/{WB_HTTP_RETRY_COUNT} failed: {exc}")
                if attempt == WB_HTTP_RETRY_COUNT:
                    return None
                time.sleep(WB_HTTP_RETRY_DELAY_SECONDS)
        return None

    def _fetch_cards_index(self, vendor_codes: set[str]) -> dict[str, int]:
        found: dict[str, int] = {}
        for vendor_code in sorted(vendor_codes):
            nm_id = self._fetch_nm_id_by_vendor_code(vendor_code)
            if nm_id:
                found[vendor_code] = nm_id
            time.sleep(WB_CONTENT_RATE_LIMIT_DELAY_SECONDS)
        return found

    def _fetch_nm_id_by_vendor_code(self, vendor_code: str) -> int:
        payload = {
            "settings": {
                "cursor": {"limit": 100},
                "filter": {
                    "withPhoto": -1,
                    "textSearch": vendor_code,
                },
            }
        }
        response = self._content_post("/content/v2/get/cards/list", json=payload)
        if response is None:
            return 0
        print(f"[wb] Cards lookup {vendor_code} status: {response.status_code}")
        print(f"[wb] Cards lookup {vendor_code} response: {response.text[:2000]}")
        data = _safe_json(response)
        cards = data.get("cards") or []
        for card in cards:
            candidate_vendor_code = str(card.get("vendorCode") or "").strip()
            if candidate_vendor_code == vendor_code:
                return _int_or_zero(card.get("nmID", ""))
        return 0

    def _fetch_cards_index_via_pagination(self, vendor_codes: set[str]) -> dict[str, int]:
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

    def _resolve_subjects_for_categories(self, category_names: list[str]) -> dict[str, tuple[int, int, str]]:
        parent_response = self._content_get("/content/v2/object/parent/all")
        if parent_response is None:
            return {}
        parent_payload = _safe_json(parent_response)
        candidate_parents = [
            item for item in parent_payload.get("data", [])
            if isinstance(item, dict) and str(item.get("name", "")).strip().lower() in {"обувь", "спортивная обувь"}
        ]

        subjects: list[dict] = []
        for parent in candidate_parents:
            parent_id = _int_or_zero(parent.get("id", ""))
            if not parent_id:
                continue
            response = self._content_get("/content/v2/object/all", params={"limit": 1000, "parentID": parent_id})
            if response is None:
                continue
            payload = _safe_json(response)
            subjects.extend([item for item in payload.get("data", []) if isinstance(item, dict)])
            time.sleep(WB_CONTENT_RATE_LIMIT_DELAY_SECONDS)

        subject_by_name = {
            str(item.get("subjectName", "")).strip().lower(): (
                _int_or_zero(item.get("parentID", "")),
                _int_or_zero(item.get("subjectID", "")),
                str(item.get("subjectName", "")).strip(),
            )
            for item in subjects
            if item.get("subjectName")
        }

        result: dict[str, tuple[int, int, str]] = {}
        for category_name in category_names:
            key = category_name.strip().lower()
            direct = subject_by_name.get(key)
            if direct:
                result[category_name] = direct
                continue
            for subject_name, values in subject_by_name.items():
                if key in subject_name or subject_name in key:
                    result[category_name] = values
                    break
        return result

    def _load_subject_characteristics(self, subject_id: int) -> list[dict]:
        response = self._content_get(f"/content/v2/object/charcs/{subject_id}")
        if response is None:
            return []
        return _extract_wb_characteristics(_safe_json(response))


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


def _split_delimited(value: str) -> list[str]:
    parts = [item.strip() for item in str(value or "").replace("\n", ";").split(";")]
    return [item for item in parts if item]


def _first_value(value: str) -> str:
    values = _split_delimited(value)
    return values[0] if values else ""


def _kg_to_grams(value: str) -> str:
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return ""
    try:
        return str(int(float(text) * 1000))
    except ValueError:
        return ""


def _extract_wb_characteristics(payload: dict) -> list[dict]:
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _build_wb_characteristics_from_template_row(row: dict[str, str], available: list[dict]) -> list[dict]:
    excluded = {
        "Группа",
        "Артикул продавца",
        "Артикул WB",
        "Наименование",
        "Категория продавца",
        "Бренд",
        "Описание",
        "Фото",
        "Видео",
        "Баркоды",
        "Размер",
        "Рос. размер",
        "Цена",
        "Вес с упаковкой (кг)",
        "Вес (г)",
        "Вес товара с упаковкой (г)",
        "Высота упаковки",
        "Длина упаковки",
        "Ширина упаковки",
    }
    meta_by_name = {
        str(item.get("name", "")).strip().lower(): item
        for item in available
        if str(item.get("name", "")).strip()
    }
    result: list[dict] = []
    for key, value in row.items():
        clean_key = str(key or "").strip()
        clean_value = str(value or "").strip()
        if not clean_key or not clean_value or clean_key in excluded:
            continue
        meta = meta_by_name.get(clean_key.lower())
        if not meta:
            continue
        result.append(
            {
                "id": meta.get("charcID") or meta.get("id"),
                "name": meta.get("name"),
                "value": clean_value,
            }
        )
    return _dedupe_characteristics(result)


def _dedupe_characteristics(items: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for item in items:
        key = (str(item.get("id", "")), str(item.get("value", "")))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
