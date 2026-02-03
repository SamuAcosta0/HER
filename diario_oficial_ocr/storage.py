from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Iterable, Optional

from diario_oficial_ocr.ocr.base import OCRBox

logger = logging.getLogger(__name__)


@dataclass
class PageRecord:
    id: int
    date: str
    section: str
    carilla: str
    url: str
    image_hash: str


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    section TEXT NOT NULL,
                    carilla TEXT NOT NULL,
                    url TEXT NOT NULL,
                    image_hash TEXT NOT NULL,
                    processed_at TEXT,
                    ocr_hash TEXT,
                    matched INTEGER DEFAULT 0,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id INTEGER NOT NULL,
                    matched_term TEXT,
                    deceased TEXT,
                    called_to_succession TEXT,
                    snippet TEXT,
                    confidence TEXT,
                    full_screenshot_path TEXT,
                    evidence_path TEXT,
                    FOREIGN KEY(page_id) REFERENCES pages(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ocr_cache (
                    image_hash TEXT PRIMARY KEY,
                    text TEXT,
                    boxes_json TEXT
                )
                """
            )

    def get_page(self, date: str, section: str, carilla: str, image_hash: str) -> Optional[PageRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pages WHERE date=? AND section=? AND carilla=? AND image_hash=?",
                (date, section, carilla, image_hash),
            ).fetchone()
        if not row:
            return None
        return PageRecord(
            id=row["id"],
            date=row["date"],
            section=row["section"],
            carilla=row["carilla"],
            url=row["url"],
            image_hash=row["image_hash"],
        )

    def insert_page(
        self,
        date: str,
        section: str,
        carilla: str,
        url: str,
        image_hash: str,
        processed_at: str,
        ocr_hash: Optional[str],
        matched: bool,
        error: Optional[str],
    ) -> int:
        def _insert() -> int:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO pages (date, section, carilla, url, image_hash, processed_at, ocr_hash, matched, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (date, section, carilla, url, image_hash, processed_at, ocr_hash, int(matched), error),
                )
                return int(cursor.lastrowid)

        return self._retry_result(_insert)

    def insert_match(
        self,
        page_id: int,
        matched_term: str,
        deceased: str,
        called_to_succession: str,
        snippet: str,
        confidence: str,
        full_screenshot_path: str,
        evidence_path: Optional[str],
    ) -> None:
        def _insert() -> None:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO matches
                    (page_id, matched_term, deceased, called_to_succession, snippet, confidence, full_screenshot_path, evidence_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        page_id,
                        matched_term,
                        deceased,
                        called_to_succession,
                        snippet,
                        confidence,
                        full_screenshot_path,
                        evidence_path,
                    ),
                )

        self._retry_result(_insert)

    def get_cached_ocr(self, image_hash: str) -> Optional[tuple[str, list[OCRBox]]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT text, boxes_json FROM ocr_cache WHERE image_hash=?", (image_hash,)
            ).fetchone()
        if not row:
            return None
        boxes = [OCRBox(**item) for item in json.loads(row["boxes_json"] or "[]")]
        return row["text"], boxes

    def cache_ocr(self, image_hash: str, text: str, boxes: Iterable[OCRBox]) -> None:
        boxes_payload = json.dumps([box.__dict__ for box in boxes])
        def _insert() -> None:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO ocr_cache (image_hash, text, boxes_json) VALUES (?, ?, ?)",
                    (image_hash, text, boxes_payload),
                )

        self._retry_result(_insert)

    def export_matches(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT pages.date, pages.section, pages.carilla, pages.url, matches.*
                FROM matches
                JOIN pages ON matches.page_id = pages.id
                ORDER BY pages.date
                """
            ).fetchall()
        return rows

    def coverage_report(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date, COUNT(*) AS pages, SUM(matched) AS matches, SUM(error IS NOT NULL) AS errors
                FROM pages
                GROUP BY date
                ORDER BY date
                """
            ).fetchall()
        return rows

    def retry_transaction(self, func, max_attempts: int = 5) -> None:
        attempt = 0
        while True:
            try:
                func()
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt >= max_attempts:
                    raise
                time.sleep(0.2 * (attempt + 1))
                attempt += 1

    def _retry_result(self, func, max_attempts: int = 5):
        attempt = 0
        while True:
            try:
                return func()
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt >= max_attempts:
                    raise
                time.sleep(0.2 * (attempt + 1))
                attempt += 1
