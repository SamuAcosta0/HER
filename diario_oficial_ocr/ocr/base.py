from __future__ import annotations

import dataclasses
from typing import List, Optional


@dataclasses.dataclass
class OCRBox:
    text: str
    bounding_box: List[int]  # [x_min, y_min, x_max, y_max]
    confidence: Optional[float] = None


@dataclasses.dataclass
class OCRResult:
    text: str
    boxes: List[OCRBox]


class OCRBackend:
    name: str = "base"

    def extract(self, image_bytes: bytes) -> OCRResult:
        raise NotImplementedError
