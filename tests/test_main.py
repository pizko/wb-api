from api.main import build_parser


def test_parser_has_feed_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["build-marketplace-feed", "--output", "data/out.xlsx"])
    assert args.command == "build-marketplace-feed"
    assert str(args.output) == "data/out.xlsx"


def test_parser_has_sync_loop_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["sync-loop", "--output-dir", "data"])
    assert args.command == "sync-loop"
    assert str(args.output_dir) == "data"


def test_parser_has_ozon_sync_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["ozon-sync", "--input", "data/marketplace_feed.xlsx"])
    assert args.command == "ozon-sync"
    assert str(args.input) == "data/marketplace_feed.xlsx"


def test_parser_has_ozon_products_draft_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["build-ozon-products-draft", "--input", "data/marketplace_feed.xlsx", "--output", "data/ozon/products_draft.xlsx"]
    )
    assert args.command == "build-ozon-products-draft"
    assert str(args.input) == "data/marketplace_feed.xlsx"
    assert str(args.output) == "data/ozon/products_draft.xlsx"


def test_parser_has_ozon_import_products_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["ozon-import-products", "--input", "data/ozon/products_draft.xlsx"])
    assert args.command == "ozon-import-products"
    assert str(args.input) == "data/ozon/products_draft.xlsx"


def test_parser_has_ozon_category_tree_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["ozon-category-tree", "--output", "data/ozon/category_tree.json"])
    assert args.command == "ozon-category-tree"
    assert str(args.output) == "data/ozon/category_tree.json"


def test_parser_has_ozon_category_attributes_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["ozon-category-attributes", "--category-id", "123", "--type-id", "456"])
    assert args.command == "ozon-category-attributes"
    assert args.category_id == 123
    assert args.type_id == 456


def test_parser_has_wb_limits_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["wb-limits", "--output", "data/wb/limits.json"])
    assert args.command == "wb-limits"
    assert str(args.output) == "data/wb/limits.json"


def test_parser_has_wb_products_draft_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["build-wb-products-draft", "--input", "data/marketplace_feed.xlsx", "--output", "data/wb/products_draft.xlsx"]
    )
    assert args.command == "build-wb-products-draft"
    assert str(args.input) == "data/marketplace_feed.xlsx"
    assert str(args.output) == "data/wb/products_draft.xlsx"


def test_parser_has_wb_products_draft_from_template_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-wb-products-draft-from-template",
            "--input",
            "data/input.xlsx",
            "--output",
            "data/wb/template_products_draft.xlsx",
        ]
    )
    assert args.command == "build-wb-products-draft-from-template"
    assert str(args.input) == "data/input.xlsx"
    assert str(args.output) == "data/wb/template_products_draft.xlsx"


def test_parser_has_wb_upload_media_links_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["wb-upload-media-links", "--input", "data/wb/products_draft.xlsx"])
    assert args.command == "wb-upload-media-links"
    assert str(args.input) == "data/wb/products_draft.xlsx"


def test_parser_has_wb_import_products_batch_delay_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["wb-import-products", "--input", "data/wb/products_draft.xlsx", "--batch-delay-seconds", "10"]
    )
    assert args.command == "wb-import-products"
    assert str(args.input) == "data/wb/products_draft.xlsx"
    assert args.batch_delay_seconds == 10.0


def test_parser_has_wb_mapping_draft_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-wb-mapping-draft",
            "--feed-input",
            "data/marketplace_feed.xlsx",
            "--subjects-input",
            "data/wb/subjects_5038.json",
            "--output",
            "data/wb/wb_mapping_draft.xlsx",
        ]
    )
    assert args.command == "build-wb-mapping-draft"
    assert str(args.feed_input) == "data/marketplace_feed.xlsx"
    assert str(args.subjects_input) == "data/wb/subjects_5038.json"
    assert str(args.output) == "data/wb/wb_mapping_draft.xlsx"


def test_parser_has_wb_mapping_autofill_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["autofill-wb-mapping-draft", "--input", "data/wb/wb_mapping_draft.xlsx"])
    assert args.command == "autofill-wb-mapping-draft"
    assert str(args.input) == "data/wb/wb_mapping_draft.xlsx"


def test_parser_has_apply_wb_mapping_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "apply-wb-mapping-to-products-draft",
            "--mapping-input",
            "data/wb/wb_mapping_draft.xlsx",
            "--products-input",
            "data/wb/products_draft.xlsx",
        ]
    )
    assert args.command == "apply-wb-mapping-to-products-draft"
    assert str(args.mapping_input) == "data/wb/wb_mapping_draft.xlsx"
    assert str(args.products_input) == "data/wb/products_draft.xlsx"


def test_parser_has_wb_fetch_used_characteristics_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "wb-fetch-used-subject-characteristics",
            "--products-input",
            "data/wb/products_draft.xlsx",
            "--output-dir",
            "data/wb/characteristics",
        ]
    )
    assert args.command == "wb-fetch-used-subject-characteristics"
    assert str(args.products_input) == "data/wb/products_draft.xlsx"
    assert str(args.output_dir) == "data/wb/characteristics"


def test_parser_has_wb_autofill_characteristics_command() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "autofill-wb-products-characteristics",
            "--products-input",
            "data/wb/products_draft.xlsx",
            "--characteristics-dir",
            "data/wb/characteristics",
        ]
    )
    assert args.command == "autofill-wb-products-characteristics"
    assert str(args.products_input) == "data/wb/products_draft.xlsx"
    assert str(args.characteristics_dir) == "data/wb/characteristics"
