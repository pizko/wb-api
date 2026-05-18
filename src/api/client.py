from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from api.config import Settings
from api.models import CatalogItem, Group, GroupItemLink, NewItem


class AstkolClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.require_credentials()
        self._client = httpx.Client(timeout=settings.timeout, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AstkolClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def fetch_catalog(self, item_id: int | None = None) -> list[CatalogItem]:
        params = self._auth_params()
        if item_id is not None:
            params["t"] = str(item_id)
        root = self._get_xml("/xml/", params=params)
        items = self._iter_payload_rows(root, "item")
        return [self._parse_catalog_item(item) for item in items]

    def fetch_groups(self) -> list[Group]:
        root = self._get_xml("/xml_agr/", params=self._auth_params())
        rows = self._iter_payload_rows(root, "grupp")
        return [
            Group(
                id=_as_int(_text(row, "id")),
                parent_id=_as_int(_text(row, "parent_id")),
                name=_text(row, "name"),
            )
            for row in rows
        ]

    def fetch_group_links(self) -> list[GroupItemLink]:
        root = self._get_xml("/xml_agr_itm/", params=self._auth_params())
        rows = self._iter_payload_rows(root, "grupp_item")
        return [
            GroupItemLink(
                item_id=_as_int(_text(row, "item_id")),
                group_id=_as_int(_text(row, "grupp_id")),
            )
            for row in rows
        ]

    def fetch_new_items(self) -> list[NewItem]:
        root = self._get_xml("/xml_new/", params=self._auth_params())
        rows = self._iter_payload_rows(root, "item")
        return [
            NewItem(
                id=_as_int(_text(row, "id")),
                article=_text(row, "art"),
                name=_text(row, "name"),
                price=_text(row, "price"),
                qty=_text(row, "qty"),
                image_url=_text(row, "img"),
                description=_text(row, "descr"),
                discount=_text(row, "discount"),
                material=_text(row, "matherial"),
                country=_text(row, "country"),
                producer=_text(row, "producer"),
                vibration=_text(row, "vibration"),
                arrival_date=_text(row, "data"),
            )
            for row in rows
        ]

    def _get_xml(self, path: str, params: dict[str, str]) -> ET.Element:
        response = self._client.get(f"{self.settings.base_url}{path}", params=params)
        response.raise_for_status()
        return ET.fromstring(response.text)

    def _auth_params(self) -> dict[str, str]:
        return {
            "u": self.settings.user,
            "p": self.settings.password_md5,
        }

    def _iter_payload_rows(self, root: ET.Element, tag_name: str) -> list[ET.Element]:
        if root.tag == tag_name:
            return [root]
        return list(root.findall(f".//{tag_name}"))

    def _parse_catalog_item(self, row: ET.Element) -> CatalogItem:
        return CatalogItem(
            id=_as_int(_text(row, "id")),
            article=_text(row, "art"),
            name=_text(row, "name"),
            discount=_text(row, "discount"),
            price_base=_text(row, "price_base"),
            price=_text(row, "price"),
            qty=_text(row, "qty"),
            image_url=_text(row, "img"),
            description=_text(row, "descr"),
            material=_text(row, "matherial"),
            country=_text(row, "country"),
            producer=_text(row, "producer"),
            vibration=_text(row, "vibration"),
            group_name=_text(row, "gruppa"),
            barcode=_text(row, "chipher"),
            brief=_text(row, "brief"),
            outlet=_text(row, "outlet"),
            is_anticrisis=_text(row, "is_anticrisis"),
            rrc=_text(row, "rrc"),
            qty_hr=_text(row, "qty_hr"),
        )


def _text(row: ET.Element, name: str) -> str:
    node = row.find(name)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _as_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
