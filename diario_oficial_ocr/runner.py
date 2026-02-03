from __future__ import annotations

import logging
from datetime import date
from typing import Iterable

from diario_oficial_ocr.config import AppConfig
from diario_oficial_ocr.navigator import DiarioOficialNavigator
from diario_oficial_ocr.processor import PageProcessor
from diario_oficial_ocr.storage import Database

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.db = Database(config.storage.db_path)
        self.processor = PageProcessor(config, self.db)

    def run_dates(self, dates: Iterable[date]) -> None:
        navigator = DiarioOficialNavigator(self.config.site, self.config.browser)
        for target_date in dates:
            for snapshot in navigator.iter_date_pages(target_date):
                existing = self.db.get_page(
                    snapshot.date.strftime("%d/%m/%Y"),
                    snapshot.section,
                    snapshot.carilla,
                    snapshot.image_hash,
                )
                if existing:
                    logger.info("Already processed %s %s", snapshot.date, snapshot.carilla)
                    continue

                try:
                    result = self.processor.process_page(snapshot)
                    page_id = self.db.insert_page(
                        date=snapshot.date.strftime("%d/%m/%Y"),
                        section=snapshot.section,
                        carilla=snapshot.carilla,
                        url=snapshot.url,
                        image_hash=snapshot.image_hash,
                        processed_at=date.today().isoformat(),
                        ocr_hash=None,
                        matched=result.matched,
                        error=None,
                    )
                    if result.matched:
                        full_path, evidence_path = self.processor.capture_evidence(
                            snapshot, result.boxes, result.matched_term
                        )
                        self.db.insert_match(
                            page_id=page_id,
                            matched_term=result.matched_term,
                            deceased=result.deceased,
                            called_to_succession=result.called_to_succession,
                            snippet=result.snippet,
                            confidence=result.confidence,
                            full_screenshot_path=full_path,
                            evidence_path=evidence_path or "",
                        )
                except Exception as exc:
                    logger.exception("Failed processing %s: %s", snapshot.date, exc)
                    self.db.insert_page(
                        date=snapshot.date.strftime("%d/%m/%Y"),
                        section=snapshot.section,
                        carilla=snapshot.carilla,
                        url=snapshot.url,
                        image_hash=snapshot.image_hash,
                        processed_at=date.today().isoformat(),
                        ocr_hash=None,
                        matched=False,
                        error=str(exc),
                    )
