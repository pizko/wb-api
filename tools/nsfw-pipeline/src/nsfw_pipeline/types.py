from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DetectionBox:
    label: str
    score: float
    x1: int
    y1: int
    x2: int
    y2: int

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "score": self.score,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }
