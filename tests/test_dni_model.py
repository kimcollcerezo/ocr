"""
Tests del model DNIValidationResponse — Contracte unificat v1
"""
import pytest
from pydantic import ValidationError
from app.models.dni_response import DNIDatos, DNIValidationResponse
from app.models.base_response import ValidationItem, RawOCR, MetaInfo


class TestDNIDatos:
    def test_sexo_literal_valid(self):
        assert DNIDatos(sexo="M").sexo == "M"
        assert DNIDatos(sexo="F").sexo == "F"
        assert DNIDatos(sexo="X").sexo == "X"
        assert DNIDatos(sexo=None).sexo is None

    def test_sexo_invalid_raises(self):
        with pytest.raises(ValidationError):
            DNIDatos(sexo="H")  # era "Home", ara "M"

    def test_tipo_numero_literal(self):
        assert DNIDatos(tipo_numero="DNI").tipo_numero == "DNI"
        assert DNIDatos(tipo_numero="NIE").tipo_numero == "NIE"

    def test_tipo_numero_invalid_raises(self):
        with pytest.raises(ValidationError):
            DNIDatos(tipo_numero="PASSAPORT")


class TestValidationItem:
    def test_valid_item(self):
        item = ValidationItem(
            code="DNI_EXPIRED",
            severity="error",
            field="fecha_caducidad",
            message="Document caducat",
            evidence="2020-01-01",
            suggested_fix="Sol·licitar renovació",
        )
        assert item.code == "DNI_EXPIRED"
        assert item.severity == "error"

    def test_severity_invalid_raises(self):
        with pytest.raises(ValidationError):
            ValidationItem(code="X", severity="blocker", message="test")

    def test_optional_fields(self):
        item = ValidationItem(code="DNI_EXPIRED", severity="warning", message="Test")
        assert item.field is None
        assert item.evidence is None
        assert item.suggested_fix is None


class TestDNIValidationResponse:
    def _make(self, valido=True, errors=None, alerts=None):
        return DNIValidationResponse(
            valido=valido,
            confianza_global=90,
            datos=DNIDatos(
                numero_documento="77612097T",
                nombre="JOAQUIN",
                apellidos="COLL CEREZO",
            ),
            alertas=alerts or [],
            errores_detectados=errors or [],
            raw=RawOCR(ocr_engine="tesseract", ocr_confidence=75.0),
            meta=MetaInfo(success=valido, message="ok"),
        )

    def test_tipo_documento_is_dni(self):
        r = self._make()
        assert r.tipo_documento == "dni"

    def test_raw_fields(self):
        r = self._make()
        assert r.raw.ocr_engine == "tesseract"
        assert r.raw.ocr_confidence == 75.0

    def test_meta_fields(self):
        r = self._make()
        assert r.meta.success is True

    def test_serialization_has_all_keys(self):
        r = self._make()
        d = r.model_dump()
        for key in ("valido", "confianza_global", "tipo_documento", "datos",
                    "alertas", "errores_detectados", "raw", "meta"):
            assert key in d

    def test_ocr_engine_literal(self):
        with pytest.raises(ValidationError):
            RawOCR(ocr_engine="azure_vision", ocr_confidence=80.0)

    def test_errores_detectados_is_list_of_items(self):
        r = self._make(valido=False, errors=[
            ValidationItem(code="DNI_EXPIRED", severity="error", message="Caducat")
        ])
        assert len(r.errores_detectados) == 1
        assert r.errores_detectados[0].code == "DNI_EXPIRED"
