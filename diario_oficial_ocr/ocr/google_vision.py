from __future__ import annotations

from typing import List

from google.cloud import vision

from diario_oficial_ocr.ocr.base import OCRBackend, OCRBox, OCRResult


class GoogleVisionOCR(OCRBackend):
    name = "google"

    def __init__(self) -> None:
        self.client = vision.ImageAnnotatorClient()

    def extract(self, image_bytes: bytes) -> OCRResult:
        image = vision.Image(content=image_bytes)
        response = self.client.document_text_detection(image=image)
        annotations = response.text_annotations
        full_text = annotations[0].description if annotations else ""
        boxes: List[OCRBox] = []
        for annotation in annotations[1:]:
            vertices = annotation.bounding_poly.vertices
            xs = [v.x for v in vertices]
            ys = [v.y for v in vertices]
            boxes.append(
                OCRBox(
                    text=annotation.description,
                    bounding_box=[min(xs), min(ys), max(xs), max(ys)],
                    confidence=None,
                )
            )
        return OCRResult(text=full_text, boxes=boxes)
