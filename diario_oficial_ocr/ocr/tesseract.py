from __future__ import annotations

import io
from typing import List

from PIL import Image
import pytesseract

from diario_oficial_ocr.ocr.base import OCRBackend, OCRBox, OCRResult


class TesseractOCR(OCRBackend):
    name = "tesseract"

    def __init__(self, tesseract_cmd: str | None = None) -> None:
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extract(self, image_bytes: bytes) -> OCRResult:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang="spa")
        boxes: List[OCRBox] = []
        return OCRResult(text=text, boxes=boxes)
