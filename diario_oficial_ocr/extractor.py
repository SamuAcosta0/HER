from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from diario_oficial_ocr.utils import extract_snippet

DECEASED_PATTERNS = [
    r"SUCESION DE\s+([^\.\n]+)",
    r"CAUSANTE\s+([^\.\n]+)",
    r"FALLECIDO[A]?\s+([^\.\n]+)",
    r"DE:\s*([^\.\n]+)",
]

CALLED_PATTERNS = [
    r"SE CITA\s+([^\.\n]+)",
    r"SE LLAMA\s+([^\.\n]+)",
    r"HEREDEROS\s+([^\.\n]+)",
    r"INTERESADOS\s+([^\.\n]+)",
    r"COMPAREZCAN\s+([^\.\n]+)",
]


@dataclass
class ExtractionResult:
    deceased: str
    called_to_succession: str
    snippet: str


def extract_entities(text: str, matched_term: str) -> ExtractionResult:
    deceased = _find_match(text, DECEASED_PATTERNS)
    called = _find_match(text, CALLED_PATTERNS)
    snippet = extract_snippet(text, matched_term)
    return ExtractionResult(deceased=deceased, called_to_succession=called, snippet=snippet)


def _find_match(text: str, patterns: list[str]) -> str:
    if not text:
        return ""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.sub(r"\s+", " ", value)
            return value
    return ""
