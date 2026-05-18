from nsfw_pipeline.main import build_parser


def test_parser_has_censor_folder_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["censor-folder", "--input", "data/raw", "--output", "data/censored"])
    assert args.command == "censor-folder"
    assert str(args.input) == "data/raw"
    assert str(args.output) == "data/censored"


def test_parser_has_render_final_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["render-final", "--input", "data/censored", "--output", "data/final"])
    assert args.command == "render-final"
    assert str(args.input) == "data/censored"
    assert str(args.output) == "data/final"
