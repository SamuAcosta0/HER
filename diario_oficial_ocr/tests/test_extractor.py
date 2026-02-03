from diario_oficial_ocr.extractor import extract_entities


def test_extract_entities_detects_deceased_and_called():
    text = "SUCESION DE JUAN PEREZ. SE CITA MARIA TERESA PARA COMPAREZCAN."
    result = extract_entities(text, "MARIA TERESA")
    assert result.deceased == "JUAN PEREZ"
    assert result.called_to_succession.startswith("MARIA TERESA")
    assert "MARIA TERESA" in result.snippet
