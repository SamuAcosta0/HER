from __future__ import annotations

import hashlib
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Iterator, Optional

logger = logging.getLogger(__name__)


@dataclass
class Backoff:
    base_delay: float = 0.5
    max_delay: float = 10.0

    def sleep(self, attempt: int) -> None:
        delay = min(self.max_delay, self.base_delay * (2**attempt))
        time.sleep(delay)


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.upper()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_dates(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def find_first_match(normalized_text: str, normalized_terms: Iterable[str]) -> Optional[str]:
    if not normalized_text:
        return None
    compact_text = re.sub(r"[^A-Z0-9]+", "", normalized_text.upper())
    for term in normalized_terms:
        if term in normalized_text:
            return term
        compact_term = re.sub(r"[^A-Z0-9]+", "", term.upper())
        if compact_term and compact_term in compact_text:
            return term
    return None


def extract_snippet(text: str, term: str, window: int = 80) -> str:
    if not text or not term:
        return ""
    idx = text.upper().find(term.upper())
    if idx == -1:
        return text[: window * 2]
    start = max(0, idx - window)
    end = min(len(text), idx + len(term) + window)
    return text[start:end].strip()
