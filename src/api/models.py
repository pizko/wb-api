from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CatalogItem:
    id: int
    article: str
    name: str
    discount: str
    price_base: str
    price: str
    qty: str
    image_url: str
    description: str
    material: str
    country: str
    producer: str
    vibration: str
    group_name: str
    barcode: str
    brief: str
    outlet: str
    is_anticrisis: str
    rrc: str
    qty_hr: str


@dataclass(slots=True)
class Group:
    id: int
    parent_id: int
    name: str


@dataclass(slots=True)
class GroupItemLink:
    item_id: int
    group_id: int


@dataclass(slots=True)
class NewItem:
    id: int
    article: str
    name: str
    price: str
    qty: str
    image_url: str
    description: str
    discount: str
    material: str
    country: str
    producer: str
    vibration: str
    arrival_date: str
