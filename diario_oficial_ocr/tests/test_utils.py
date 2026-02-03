from diario_oficial_ocr.utils import normalize_text


def test_normalize_text_removes_accents_and_spaces():
    text = "María   Teresa\nAcuña"
    assert normalize_text(text) == "MARIA TERESA ACUNA"
