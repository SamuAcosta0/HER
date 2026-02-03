from __future__ import annotations

import json
import logging
import os
from io import BytesIO
from dataclasses import dataclass
from datetime import date
from typing import Optional

from PIL import Image

from diario_oficial_ocr.config import AppConfig, MATCH_TERMS
from diario_oficial_ocr.extractor import extract_entities
from diario_oficial_ocr.storage import Database
from diario_oficial_ocr.utils import find_first_match, normalize_text

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    matched: bool
    matched_term: str
    confidence: str
    deceased: str
    called_to_succession: str
    snippet: str
    boxes: list


class PageProcessor:
    def __init__(self, config: AppConfig, db: Database) -> None:
        self.config = config
        self.db = db
        self.ocr = self._init_ocr_backend()
        self.normalized_terms = [normalize_text(term) for term in MATCH_TERMS]

    def _init_ocr_backend(self):
        if self.config.ocr.backend == "google":
            from diario_oficial_ocr.ocr.google_vision import GoogleVisionOCR

            return GoogleVisionOCR()
        if self.config.ocr.backend == "tesseract":
            from diario_oficial_ocr.ocr.tesseract import TesseractOCR

            return TesseractOCR(self.config.ocr.tesseract_cmd)
        raise ValueError(f"Unsupported OCR backend: {self.config.ocr.backend}")

    def process_page(self, snapshot) -> ProcessResult:
        cached = self.db.get_cached_ocr(snapshot.image_hash)
        if cached:
            ocr_text, boxes = cached
        else:
            ocr_result = self.ocr.extract(snapshot.image_bytes)
            ocr_text = ocr_result.text
            boxes = ocr_result.boxes
            self.db.cache_ocr(snapshot.image_hash, ocr_text, boxes)

        normalized_text = normalize_text(ocr_text)
        matched_term = find_first_match(normalized_text, self.normalized_terms) or ""
        if matched_term:
            result = extract_entities(ocr_text, matched_term)
            confidence = "high" if len(matched_term) > 6 else "medium"
            return ProcessResult(
                matched=True,
                matched_term=matched_term,
                confidence=confidence,
                deceased=result.deceased,
                called_to_succession=result.called_to_succession,
                snippet=result.snippet,
                boxes=boxes,
            )
        return ProcessResult(
            matched=False,
            matched_term="",
            confidence="low",
            deceased="",
            called_to_succession="",
            snippet="",
            boxes=boxes,
        )

    def capture_evidence(self, snapshot, boxes, matched_term: str) -> tuple[str, Optional[str]]:
        os.makedirs(self.config.browser.screenshot_dir, exist_ok=True)
        os.makedirs(self.config.browser.evidence_dir, exist_ok=True)
        base_name = f"{snapshot.date.strftime('%Y%m%d')}_{snapshot.carilla}"
        full_path = os.path.join(self.config.browser.screenshot_dir, f"{base_name}.png")
        with open(full_path, "wb") as handle:
            handle.write(snapshot.full_screenshot)

        evidence_path = None
        if boxes:
            evidence_path = os.path.join(self.config.browser.evidence_dir, f"{base_name}_evidence.png")
            crop = self._crop_evidence(snapshot.image_bytes, boxes, matched_term)
            if crop:
                crop.save(evidence_path)
        return full_path, evidence_path

    def _crop_evidence(self, image_bytes, boxes, matched_term: str) -> Optional[Image.Image]:
        if not boxes:
            return None
        matched = [box for box in boxes if matched_term.upper() in box.text.upper()]
        if not matched:
            matched = boxes[:1]
        x_min = min(box.bounding_box[0] for box in matched)
        y_min = min(box.bounding_box[1] for box in matched)
        x_max = max(box.bounding_box[2] for box in matched)
        y_max = max(box.bounding_box[3] for box in matched)
        image = Image.open(BytesIO(image_bytes))
        x_min = max(0, x_min - 10)
        y_min = max(0, y_min - 10)
        x_max = min(image.width, x_max + 10)
        y_max = min(image.height, y_max + 10)
        return image.crop((x_min, y_min, x_max, y_max))


@dataclass
class PageOutput:
    date: str
    section: str
    carilla: str
    url: str
    image_hash: str
    matched: bool
    matched_term: str
    deceased: str
    called_to_succession: str
    snippet: str
    confidence: str
    full_screenshot_path: str
    evidence_path: str


@dataclass
class PageState:
    date: date
    carilla: str
    image_hash: str
