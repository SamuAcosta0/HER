from __future__ import annotations

import json
import os
from typing import Iterable

import pandas as pd

from diario_oficial_ocr.storage import Database


def export_results(db: Database, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    matches = db.export_matches()
    rows = []
    for row in matches:
        rows.append(dict(row))

    jsonl_path = os.path.join(output_dir, "results.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    if rows:
        df = pd.DataFrame(rows)
        df.to_excel(os.path.join(output_dir, "results.xlsx"), index=False)

    coverage_rows = [dict(row) for row in db.coverage_report()]
    with open(os.path.join(output_dir, "coverage_report.json"), "w", encoding="utf-8") as handle:
        json.dump(coverage_rows, handle, ensure_ascii=False, indent=2)
