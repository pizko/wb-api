from __future__ import annotations

from pathlib import Path

from nsfw_pipeline.types import DetectionBox


DEFAULT_NSFW_LABELS = {
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
}


class NudeNetDetector:
    def __init__(self, labels: set[str] | None = None, min_score: float = 0.25) -> None:
        self.labels = labels or set(DEFAULT_NSFW_LABELS)
        self.min_score = min_score
        self._detector = None

    def detect(self, image_path: Path) -> list[DetectionBox]:
        detector = self._lazy_detector()
        raw = detector.detect(str(image_path))
        result: list[DetectionBox] = []
        for item in raw:
            label = str(item.get("class") or "").strip()
            score = float(item.get("score") or 0.0)
            if label not in self.labels or score < self.min_score:
                continue
            box = item.get("box") or []
            if len(box) != 4:
                continue
            x1, y1, w, h = [int(value) for value in box]
            result.append(
                DetectionBox(
                    label=label,
                    score=score,
                    x1=x1,
                    y1=y1,
                    x2=x1 + w,
                    y2=y1 + h,
                )
            )
        return result

    def _lazy_detector(self):
        if self._detector is not None:
            return self._detector
        try:
            from nudenet import NudeDetector
        except ImportError as exc:
            raise RuntimeError(
                "NudeNet не установлен. Активируй окружение и выполни `python3 -m pip install -e .`"
            ) from exc
        self._detector = NudeDetector()
        return self._detector
