import os
import tempfile

from diario_oficial_ocr.storage import Database


def test_database_insert_page_and_match():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite")
        db = Database(db_path)
        page_id = db.insert_page(
            date="01/01/1983",
            section="Avisos Publicados",
            carilla="1",
            url="https://example.com",
            image_hash="hash",
            processed_at="2020-01-01",
            ocr_hash=None,
            matched=True,
            error=None,
        )
        db.insert_match(
            page_id=page_id,
            matched_term="MARIA TERESA",
            deceased="JUAN PEREZ",
            called_to_succession="MARIA TERESA",
            snippet="snippet",
            confidence="high",
            full_screenshot_path="/tmp/screenshot.png",
            evidence_path="/tmp/evidence.png",
        )
        rows = db.export_matches()
        assert rows
