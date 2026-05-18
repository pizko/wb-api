from __future__ import annotations

import argparse
from pathlib import Path

from nsfw_pipeline.detectors import DEFAULT_NSFW_LABELS, NudeNetDetector
from nsfw_pipeline.processor import censor_image, list_images, render_final_image, save_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local NSFW image pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    censor = subparsers.add_parser("censor-folder", help="Detect and censor NSFW zones in a folder")
    censor.add_argument("--input", type=Path, required=True)
    censor.add_argument("--output", type=Path, required=True)
    censor.add_argument("--effect", choices=["blur", "pixelate", "block"], default="blur")
    censor.add_argument("--blur-kernel", type=int, default=61)
    censor.add_argument("--pixel-size", type=int, default=18)
    censor.add_argument("--padding-ratio", type=float, default=0.08)
    censor.add_argument("--min-score", type=float, default=0.25)
    censor.add_argument("--labels", nargs="*", default=sorted(DEFAULT_NSFW_LABELS))

    render = subparsers.add_parser("render-final", help="Build final store images from censored photos")
    render.add_argument("--input", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--format", choices=["jpg", "webp"], default="webp")
    render.add_argument("--max-width", type=int, default=1200)
    render.add_argument("--max-height", type=int, default=1200)
    render.add_argument("--white-background", action="store_true", default=True)
    render.add_argument("--watermark-text", default="")
    render.add_argument("--watermark-font-size", type=int, default=28)
    render.add_argument("--watermark-image", type=Path, default=None)
    render.add_argument("--jpeg-quality", type=int, default=92)
    render.add_argument("--webp-quality", type=int, default=92)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "censor-folder":
        run_censor_folder(
            input_dir=args.input,
            output_dir=args.output,
            effect=args.effect,
            blur_kernel=args.blur_kernel,
            pixel_size=args.pixel_size,
            padding_ratio=args.padding_ratio,
            min_score=args.min_score,
            labels=set(args.labels),
        )
        return

    if args.command == "render-final":
        run_render_final(
            input_dir=args.input,
            output_dir=args.output,
            output_format=args.format,
            max_width=args.max_width,
            max_height=args.max_height,
            white_background=args.white_background,
            watermark_text=args.watermark_text,
            watermark_font_size=args.watermark_font_size,
            watermark_image=args.watermark_image,
            jpeg_quality=args.jpeg_quality,
            webp_quality=args.webp_quality,
        )
        return


def run_censor_folder(
    *,
    input_dir: Path,
    output_dir: Path,
    effect: str,
    blur_kernel: int,
    pixel_size: int,
    padding_ratio: float,
    min_score: float,
    labels: set[str],
) -> None:
    detector = NudeNetDetector(labels=labels, min_score=min_score)
    images = list_images(input_dir)
    if not images:
        print(f"Изображения не найдены: {input_dir}")
        return

    report: list[dict] = []
    for image_path in images:
        relative = image_path.relative_to(input_dir)
        output_path = output_dir / relative
        detections = detector.detect(image_path)
        payload = censor_image(
            image_path,
            output_path,
            detections,
            effect=effect,
            blur_kernel=blur_kernel,
            pixel_size=pixel_size,
            padding_ratio=padding_ratio,
        )
        report.append(payload)
        print(f"Обработано: {relative} | зон: {len(detections)}")

    report_path = save_report(output_dir / "detections_report.json", report)
    print(f"Готово. Изображений: {len(report)}")
    print(f"Отчёт: {report_path.resolve()}")


def run_render_final(
    *,
    input_dir: Path,
    output_dir: Path,
    output_format: str,
    max_width: int,
    max_height: int,
    white_background: bool,
    watermark_text: str,
    watermark_font_size: int,
    watermark_image: Path | None,
    jpeg_quality: int,
    webp_quality: int,
) -> None:
    images = list_images(input_dir)
    if not images:
        print(f"Изображения не найдены: {input_dir}")
        return

    report: list[dict] = []
    extension = ".webp" if output_format == "webp" else ".jpg"
    for image_path in images:
        relative = image_path.relative_to(input_dir)
        output_path = (output_dir / relative).with_suffix(extension)
        render_final_image(
            image_path,
            output_path,
            max_width=max_width,
            max_height=max_height,
            white_background=white_background,
            output_format=output_format,
            watermark_text=watermark_text,
            watermark_font_size=watermark_font_size,
            watermark_image=watermark_image,
            jpeg_quality=jpeg_quality,
            webp_quality=webp_quality,
        )
        report.append({"input": str(image_path), "output": str(output_path)})
        print(f"Собрано: {relative}")

    report_path = save_report(output_dir / "render_report.json", report)
    print(f"Готово. Финальных изображений: {len(report)}")
    print(f"Отчёт: {report_path.resolve()}")


if __name__ == "__main__":
    main()
