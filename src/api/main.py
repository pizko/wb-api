from __future__ import annotations

import argparse
from pathlib import Path

from api.client import AstkolClient
from api.config import Settings
from api.exporters import (
    apply_wb_mapping_to_products_draft_xlsx,
    autofill_wb_mapping_draft_xlsx,
    autofill_wb_products_characteristics_xlsx,
    collect_wb_subject_ids_from_products_draft,
    export_catalog_xlsx,
    export_groups_xlsx,
    export_marketplace_feed_xlsx,
    export_new_items_xlsx,
    export_ozon_products_draft_xlsx,
    export_wb_mapping_draft_xlsx,
    export_wb_products_draft_xlsx,
    load_json_file,
    load_marketplace_feed_rows,
)
from api.marketplaces.ozon import OzonMarketplace
from api.marketplaces.wb import WildberriesMarketplace
from api.sync_service import run_sync_loop, run_sync_once


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Astkol API tools for marketplace integration")
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog = subparsers.add_parser("fetch-catalog", help="Fetch catalog with stock and prices")
    catalog.add_argument("--output", type=Path, default=Path("data/catalog.xlsx"))
    catalog.add_argument("--item-id", type=int, default=None)

    groups = subparsers.add_parser("fetch-groups", help="Fetch groups and item-group links")
    groups.add_argument("--output", type=Path, default=Path("data/groups.xlsx"))

    new_items = subparsers.add_parser("fetch-new", help="Fetch new items for the last 30 days")
    new_items.add_argument("--output", type=Path, default=Path("data/new_items.xlsx"))

    feed = subparsers.add_parser(
        "build-marketplace-feed",
        help="Build one consolidated Excel for Ozon, Yandex and Wildberries mapping",
    )
    feed.add_argument("--output", type=Path, default=Path("data/marketplace_feed.xlsx"))

    sync_once = subparsers.add_parser(
        "sync-once",
        help="Fetch supplier data, rebuild feed and call enabled marketplace adapters once",
    )
    sync_once.add_argument("--output-dir", type=Path, default=Path("data"))

    sync_loop = subparsers.add_parser(
        "sync-loop",
        help="Run continuous sync loop for VPS container deployment",
    )
    sync_loop.add_argument("--output-dir", type=Path, default=Path("data"))

    ozon_sync = subparsers.add_parser(
        "ozon-sync",
        help="Build and optionally push Ozon price and stock payloads from marketplace feed",
    )
    ozon_sync.add_argument("--input", type=Path, default=Path("data/marketplace_feed.xlsx"))

    ozon_products_draft = subparsers.add_parser(
        "build-ozon-products-draft",
        help="Build Ozon product import draft from marketplace feed",
    )
    ozon_products_draft.add_argument("--input", type=Path, default=Path("data/marketplace_feed.xlsx"))
    ozon_products_draft.add_argument("--output", type=Path, default=Path("data/ozon/products_draft.xlsx"))

    ozon_import_products = subparsers.add_parser(
        "ozon-import-products",
        help="Import Ozon product cards from prepared draft file",
    )
    ozon_import_products.add_argument("--input", type=Path, default=Path("data/ozon/products_draft.xlsx"))

    ozon_category_tree = subparsers.add_parser(
        "ozon-category-tree",
        help="Fetch Ozon category tree and save it to JSON",
    )
    ozon_category_tree.add_argument("--output", type=Path, default=Path("data/ozon/category_tree.json"))

    ozon_category_attributes = subparsers.add_parser(
        "ozon-category-attributes",
        help="Fetch Ozon category attributes by category_id",
    )
    ozon_category_attributes.add_argument("--category-id", type=int, required=True)
    ozon_category_attributes.add_argument("--type-id", type=int, required=True)
    ozon_category_attributes.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    wb_limits = subparsers.add_parser(
        "wb-limits",
        help="Fetch Wildberries card creation limits",
    )
    wb_limits.add_argument("--output", type=Path, default=Path("data/wb/limits.json"))

    wb_parent_categories = subparsers.add_parser(
        "wb-parent-categories",
        help="Fetch Wildberries parent categories",
    )
    wb_parent_categories.add_argument("--output", type=Path, default=Path("data/wb/parent_categories.json"))

    wb_subjects = subparsers.add_parser(
        "wb-subjects",
        help="Fetch Wildberries subjects",
    )
    wb_subjects.add_argument("--parent-id", type=int, default=None)
    wb_subjects.add_argument("--output", type=Path, default=None)

    wb_subject_characteristics = subparsers.add_parser(
        "wb-subject-characteristics",
        help="Fetch Wildberries subject characteristics",
    )
    wb_subject_characteristics.add_argument("--subject-id", type=int, required=True)
    wb_subject_characteristics.add_argument("--output", type=Path, default=None)

    wb_products_draft = subparsers.add_parser(
        "build-wb-products-draft",
        help="Build Wildberries product import draft from marketplace feed",
    )
    wb_products_draft.add_argument("--input", type=Path, default=Path("data/marketplace_feed.xlsx"))
    wb_products_draft.add_argument("--output", type=Path, default=Path("data/wb/products_draft.xlsx"))

    wb_template_products_draft = subparsers.add_parser(
        "build-wb-products-draft-from-template",
        help="Build Wildberries products draft from already filled WB Excel template",
    )
    wb_template_products_draft.add_argument("--input", type=Path, required=True)
    wb_template_products_draft.add_argument("--output", type=Path, default=Path("data/wb/template_products_draft.xlsx"))

    wb_import_products = subparsers.add_parser(
        "wb-import-products",
        help="Import Wildberries product cards from prepared draft file",
    )
    wb_import_products.add_argument("--input", type=Path, default=Path("data/wb/products_draft.xlsx"))
    wb_import_products.add_argument("--batch-delay-seconds", type=float, default=10.0)

    wb_upload_media_links = subparsers.add_parser(
        "wb-upload-media-links",
        help="Upload Wildberries product photos by URL for cards already created",
    )
    wb_upload_media_links.add_argument("--input", type=Path, default=Path("data/wb/products_draft.xlsx"))

    wb_mapping_draft = subparsers.add_parser(
        "build-wb-mapping-draft",
        help="Build Excel mapping draft between supplier groups and WB subjects",
    )
    wb_mapping_draft.add_argument("--feed-input", type=Path, default=Path("data/marketplace_feed.xlsx"))
    wb_mapping_draft.add_argument("--subjects-input", type=Path, default=Path("data/wb/subjects_5038.json"))
    wb_mapping_draft.add_argument("--output", type=Path, default=Path("data/wb/wb_mapping_draft.xlsx"))

    wb_mapping_autofill = subparsers.add_parser(
        "autofill-wb-mapping-draft",
        help="Autofill WB mapping draft with subject guesses by keywords",
    )
    wb_mapping_autofill.add_argument("--input", type=Path, default=Path("data/wb/wb_mapping_draft.xlsx"))

    wb_apply_mapping = subparsers.add_parser(
        "apply-wb-mapping-to-products-draft",
        help="Apply WB mapping draft to WB products draft",
    )
    wb_apply_mapping.add_argument("--mapping-input", type=Path, default=Path("data/wb/wb_mapping_draft.xlsx"))
    wb_apply_mapping.add_argument("--products-input", type=Path, default=Path("data/wb/products_draft.xlsx"))

    wb_fetch_used_characteristics = subparsers.add_parser(
        "wb-fetch-used-subject-characteristics",
        help="Fetch WB characteristics for all subject IDs already used in products draft",
    )
    wb_fetch_used_characteristics.add_argument("--products-input", type=Path, default=Path("data/wb/products_draft.xlsx"))
    wb_fetch_used_characteristics.add_argument("--output-dir", type=Path, default=Path("data/wb/characteristics"))

    wb_autofill_characteristics = subparsers.add_parser(
        "autofill-wb-products-characteristics",
        help="Autofill WB products draft characteristics_json from supplier data and WB characteristic schemas",
    )
    wb_autofill_characteristics.add_argument("--products-input", type=Path, default=Path("data/wb/products_draft.xlsx"))
    wb_autofill_characteristics.add_argument("--characteristics-dir", type=Path, default=Path("data/wb/characteristics"))

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings.from_env()

    with AstkolClient(settings) as client:
        if args.command == "fetch-catalog":
            items = client.fetch_catalog(item_id=args.item_id)
            output = export_catalog_xlsx(args.output, items)
            print(f"Готово. Каталог: {output.resolve()}")
            print(f"Позиций: {len(items)}")
            return

        if args.command == "fetch-groups":
            groups = client.fetch_groups()
            links = client.fetch_group_links()
            output = export_groups_xlsx(args.output, groups, links)
            print(f"Готово. Группы: {output.resolve()}")
            print(f"Групп: {len(groups)}")
            print(f"Привязок: {len(links)}")
            return

        if args.command == "fetch-new":
            items = client.fetch_new_items()
            output = export_new_items_xlsx(args.output, items)
            print(f"Готово. Новинки: {output.resolve()}")
            print(f"Новинок: {len(items)}")
            return

        if args.command == "build-marketplace-feed":
            items = client.fetch_catalog()
            groups = client.fetch_groups()
            links = client.fetch_group_links()
            output = export_marketplace_feed_xlsx(args.output, items, groups, links)
            print(f"Готово. Marketplace feed: {output.resolve()}")
            print(f"Позиций: {len(items)}")
            print(f"Групп: {len(groups)}")
            print(f"Привязок: {len(links)}")
            return

    if args.command == "sync-once":
        run_sync_once(settings, output_dir=args.output_dir)
        return

    if args.command == "sync-loop":
        run_sync_loop(settings, output_dir=args.output_dir)
        return

    if args.command == "ozon-sync":
        OzonMarketplace(settings).sync(args.input)
        return

    if args.command == "build-ozon-products-draft":
        rows = load_marketplace_feed_rows(args.input)
        output = export_ozon_products_draft_xlsx(args.output, rows)
        print(f"Готово. Ozon draft: {output.resolve()}")
        print(f"Строк в draft: {len(rows)}")
        return

    if args.command == "ozon-import-products":
        OzonMarketplace(settings).import_products(args.input)
        return

    if args.command == "ozon-category-tree":
        OzonMarketplace(settings).fetch_category_tree(args.output)
        return

    if args.command == "ozon-category-attributes":
        OzonMarketplace(settings).fetch_category_attributes(args.category_id, args.type_id, args.output)
        return

    if args.command == "wb-limits":
        WildberriesMarketplace(settings).fetch_limits(args.output)
        return

    if args.command == "wb-parent-categories":
        WildberriesMarketplace(settings).fetch_parent_categories(args.output)
        return

    if args.command == "wb-subjects":
        WildberriesMarketplace(settings).fetch_subjects(args.parent_id, args.output)
        return

    if args.command == "wb-subject-characteristics":
        WildberriesMarketplace(settings).fetch_subject_characteristics(args.subject_id, args.output)
        return

    if args.command == "build-wb-products-draft":
        rows = load_marketplace_feed_rows(args.input)
        output = export_wb_products_draft_xlsx(args.output, rows)
        print(f"Готово. WB draft: {output.resolve()}")
        print(f"Строк в draft: {len(rows)}")
        return

    if args.command == "build-wb-products-draft-from-template":
        WildberriesMarketplace(settings).build_products_draft_from_template(args.input, args.output)
        return

    if args.command == "wb-import-products":
        WildberriesMarketplace(settings).import_products(args.input, args.batch_delay_seconds)
        return

    if args.command == "wb-upload-media-links":
        WildberriesMarketplace(settings).upload_media_links(args.input)
        return

    if args.command == "build-wb-mapping-draft":
        rows = load_marketplace_feed_rows(args.feed_input)
        wb_subjects_payload = load_json_file(args.subjects_input)
        output = export_wb_mapping_draft_xlsx(args.output, rows, wb_subjects_payload)
        print(f"Готово. WB mapping draft: {output.resolve()}")
        print(f"Строк групп поставщика: {len({((row.get('group_name') or '').strip(), (row.get('group_tree_candidates') or '').strip()) for row in rows})}")
        print(f"Предметов WB: {len(wb_subjects_payload.get('data', []))}")
        return

    if args.command == "autofill-wb-mapping-draft":
        output = autofill_wb_mapping_draft_xlsx(args.input)
        print(f"Готово. WB mapping draft обновлён: {output.resolve()}")
        return

    if args.command == "apply-wb-mapping-to-products-draft":
        output = apply_wb_mapping_to_products_draft_xlsx(args.mapping_input, args.products_input)
        print(f"Готово. WB products draft обновлён: {output.resolve()}")
        return

    if args.command == "wb-fetch-used-subject-characteristics":
        subject_ids = collect_wb_subject_ids_from_products_draft(args.products_input)
        WildberriesMarketplace(settings).fetch_characteristics_for_subject_ids(subject_ids, args.output_dir)
        print(f"Готово. SubjectID для характеристик: {len(subject_ids)}")
        return

    if args.command == "autofill-wb-products-characteristics":
        output = autofill_wb_products_characteristics_xlsx(args.products_input, args.characteristics_dir)
        print(f"Готово. WB products draft characteristics обновлены: {output.resolve()}")
        return


if __name__ == "__main__":
    main()
