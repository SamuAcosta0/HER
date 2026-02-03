# Diario Oficial OCR Automation

Production-grade automation to navigate IMPO Diario Oficial, capture scanned pages, run OCR at scale, and extract succession notices.

## Features
- Playwright + Chromium automation with anti-stuck controls.
- Robust handling of empty days, holidays, and multi-carilla days.
- Pluggable OCR backends (Google Vision + Tesseract fallback).
- OCR caching by image hash to avoid redundant processing.
- Resume-safe checkpoints with SQLite.
- Evidence capture (full-page screenshots + cropped evidence when bounding boxes exist).
- Results export to JSONL + Excel with coverage report.

## Quick Start

```bash
python -m diario_oficial_ocr run --start 1983-01-01 --end 1983-01-03
```

The navigator targets **“Imágenes del Diario Oficial”** (historical scanned images). If the site opens in the modern PDF/HTML view, it will switch automatically.

If you see `sqlite3.OperationalError: unable to open database file`, create the output directory:

```bash
mkdir -p output
```

### Environment
Copy `.env.example` and adjust values:

```bash
cp .env.example .env
```

Key variables:
- `OCR_BACKEND=google` or `tesseract`
- `GOOGLE_APPLICATION_CREDENTIALS=/path/to/creds.json`
- `WORKERS=2`
- `SECTION_VALUE=9` (required for **Avisos Publicados** in the images view)

## Output
- `output/checkpoints.sqlite`
- `output/results.jsonl`
- `output/results.xlsx`
- `output/coverage_report.json`
- `output/screenshots/` full page captures
- `output/evidence/` cropped evidence images

## Notes
- For large ranges, increase `WORKERS` to parallelize by date blocks. SQLite is configured for WAL + retry.
- Ensure Playwright browsers are installed.

## Tests
```bash
pytest
```
