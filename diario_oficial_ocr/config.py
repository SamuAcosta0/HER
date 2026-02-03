from __future__ import annotations

import dataclasses
import os
from datetime import date, timedelta
from typing import List


@dataclasses.dataclass
class OCRConfig:
    backend: str = "google"  # google or tesseract
    google_credentials_path: str | None = None
    tesseract_cmd: str | None = None
    cache_dir: str = "output/ocr_cache"


@dataclasses.dataclass
class BrowserConfig:
    headless: bool = True
    slow_mo_ms: int = 0
    navigation_timeout_ms: int = 30000
    action_delay_ms: int = 800
    max_action_retries: int = 5
    end_of_carillas_attempts: int = 3
    screenshot_dir: str = "output/screenshots"
    evidence_dir: str = "output/evidence"
    viewport_width: int = 1400
    viewport_height: int = 900


@dataclasses.dataclass
class SiteConfig:
    base_url: str = "https://www.impo.com.uy/diariooficial"
    section_name: str = "Avisos Publicados"
    section_value: str = "9"
    selectors: dict = dataclasses.field(
        default_factory=lambda: {
            "images_view_link": "a:has-text('Imágenes del Diario Oficial')",
            "date_input": "input[name='fecha'], input#fecha, input[type='text'][placeholder*='dd']",
            "section_select": "select[name='seccion'], select#seccion, select[name='Seccion']",
            "apply_button": "button:has-text('Buscar'), input[type='submit'][value*='Buscar']",
            "carilla_label": ".carilla-number, #carilla, .carilla",
            "image": "img#pagina, img#imagen, img[src*='carilla'], img[src*='imagen']",
            "next_carilla": "button[aria-label='Siguiente'], button:has-text('>'), a[title*='Siguiente']",
            "prev_carilla": "button[aria-label='Anterior'], button:has-text('<'), a[title*='Anterior']",
            "no_content": "text=No se encontraron resultados, text=No existe, text=Sin resultados",
        }
    )


@dataclasses.dataclass
class StorageConfig:
    db_path: str = "output/checkpoints.sqlite"
    output_dir: str = "output"


@dataclasses.dataclass
class AppConfig:
    ocr: OCRConfig
    browser: BrowserConfig
    site: SiteConfig
    storage: StorageConfig
    workers: int = 1


@dataclasses.dataclass
class DateRange:
    start: date
    end: date


MATCH_TERMS = [
    "ACUNA",
    "MARIA TERESA",
    "MARIA ZULMA",
    "MARIA CELIA",
]


def load_config() -> AppConfig:
    ocr_backend = os.getenv("OCR_BACKEND", "google")
    return AppConfig(
        ocr=OCRConfig(
            backend=ocr_backend,
            google_credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            tesseract_cmd=os.getenv("TESSERACT_CMD"),
            cache_dir=os.getenv("OCR_CACHE_DIR", "output/ocr_cache"),
        ),
        browser=BrowserConfig(
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            slow_mo_ms=int(os.getenv("SLOW_MO_MS", "0")),
            navigation_timeout_ms=int(os.getenv("NAV_TIMEOUT_MS", "30000")),
            action_delay_ms=int(os.getenv("ACTION_DELAY_MS", "800")),
            max_action_retries=int(os.getenv("MAX_ACTION_RETRIES", "5")),
            end_of_carillas_attempts=int(os.getenv("END_CARILLAS_ATTEMPTS", "3")),
            screenshot_dir=os.getenv("SCREENSHOT_DIR", "output/screenshots"),
            evidence_dir=os.getenv("EVIDENCE_DIR", "output/evidence"),
            viewport_width=int(os.getenv("VIEWPORT_WIDTH", "1400")),
            viewport_height=int(os.getenv("VIEWPORT_HEIGHT", "900")),
        ),
        site=SiteConfig(
            base_url=os.getenv("BASE_URL", "https://www.impo.com.uy/diariooficial"),
            section_name=os.getenv("SECTION_NAME", "Avisos Publicados"),
            section_value=os.getenv("SECTION_VALUE", "9"),
        ),
        storage=StorageConfig(
            db_path=os.getenv("DB_PATH", "output/checkpoints.sqlite"),
            output_dir=os.getenv("OUTPUT_DIR", "output"),
        ),
        workers=int(os.getenv("WORKERS", "1")),
    )


def split_date_range(date_range: DateRange, chunks: int) -> List[DateRange]:
    total_days = (date_range.end - date_range.start).days + 1
    if chunks <= 1 or total_days <= 1:
        return [date_range]
    chunk_size = max(1, total_days // chunks)
    ranges = []
    current = date_range.start
    for _ in range(chunks):
        end = min(date_range.end, current + timedelta(days=chunk_size - 1))
        ranges.append(DateRange(current, end))
        current = end + timedelta(days=1)
        if current > date_range.end:
            break
    if ranges[-1].end < date_range.end:
        ranges[-1] = DateRange(ranges[-1].start, date_range.end)
    return ranges
