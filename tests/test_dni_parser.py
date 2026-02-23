"""
Tests unitaris del DNIParser — Contracte unificat v1
"""
import pytest
from app.parsers.dni_parser import DNIParser, validate_doc_number, _expected_letter
from app.models.dni_response import DNIDatos, MRZData


# ---------------------------------------------------------------------------
# validate_doc_number
# ---------------------------------------------------------------------------

class TestValidateDocNumber:
    def test_dni_valid(self):
        assert validate_doc_number("77612097T") is True

    def test_dni_wrong_letter(self):
        assert validate_doc_number("77612097A") is False

    def test_dni_too_short(self):
        assert validate_doc_number("7612097T") is False

    def test_dni_lowercase_accepted(self):
        # La funció normalitza a majúscules internament (OCR pot retornar minúscules)
        assert validate_doc_number("77612097t") is True

    def test_nie_x_valid(self):
        assert validate_doc_number("X1234567L") is True

    def test_nie_y_valid(self):
        from app.parsers.dni_parser import DNI_LETTERS
        number = int("1" + "1234567")
        letter = DNI_LETTERS[number % 23]
        assert validate_doc_number(f"Y1234567{letter}") is True

    def test_nie_z_valid(self):
        from app.parsers.dni_parser import DNI_LETTERS
        number = int("2" + "1234567")
        letter = DNI_LETTERS[number % 23]
        assert validate_doc_number(f"Z1234567{letter}") is True

    def test_nie_wrong_letter(self):
        assert validate_doc_number("X1234567A") is False

    def test_empty_string(self):
        assert validate_doc_number("") is False

    def test_random_string(self):
        assert validate_doc_number("ABC") is False


# ---------------------------------------------------------------------------
# parse_mrz
# ---------------------------------------------------------------------------

def _mrz(line1, line2, line3):
    def pad(s): return s.ljust(30, "<")[:30]
    return f"{pad(line1)}\n{pad(line2)}\n{pad(line3)}"


class TestParseMrz:
    def test_basic_dni(self):
        mrz = _mrz(
            "IDESPBHV122738077612097T",
            "7301245M2808288ESP",
            "COLL<CEREZO<<JOAQUIN",
        )
        result = DNIParser.parse_mrz(mrz)
        assert result is not None
        data, raw = result
        assert data.numero_documento == "77612097T"
        assert data.nombre == "JOAQUIN"
        assert "COLL" in data.apellidos
        assert "CEREZO" in data.apellidos
        assert data.fecha_nacimiento == "1973-01-24"
        assert data.fecha_caducidad == "2028-08-28"
        assert data.sexo == "M"
        assert data.nacionalidad == "ESP"
        assert raw is not None

    def test_nie_in_mrz(self):
        mrz = _mrz(
            "IDESPX1234567L",
            "8901015M3112311ESP",
            "GARCIA<<LOPEZ<<MARIA",
        )
        result = DNIParser.parse_mrz(mrz)
        assert result is not None
        data, _ = result
        assert data.numero_documento == "X1234567L"
        assert data.tipo_numero == "NIE"

    def test_female_sex(self):
        mrz = _mrz(
            "IDESP38752127W",
            "5809285F2312288ESP",
            "CEREZO<BAS<<VICTORIA<MERCEDES",
        )
        result = DNIParser.parse_mrz(mrz)
        assert result is not None
        data, _ = result
        assert data.sexo == "F"

    def test_date_iso_format(self):
        mrz = _mrz(
            "IDESPBHV122738077612097T",
            "7301245M2808288ESP",
            "COLL<CEREZO<<JOAQUIN",
        )
        result = DNIParser.parse_mrz(mrz)
        data, _ = result
        # Dates en format ISO YYYY-MM-DD
        assert data.fecha_nacimiento.startswith("19") or data.fecha_nacimiento.startswith("20")
        assert len(data.fecha_nacimiento) == 10
        assert data.fecha_nacimiento[4] == "-" and data.fecha_nacimiento[7] == "-"

    def test_date_year_dynamic(self):
        """Anys de caducitat < current_yy+10 han de ser 20xx"""
        from datetime import date
        future_yy = date.today().year % 100 + 5
        mrz = _mrz(
            "IDESPBHV122738077612097T",
            f"7301245M{future_yy:02d}08288ESP",
            "COLL<CEREZO<<JOAQUIN",
        )
        result = DNIParser.parse_mrz(mrz)
        data, _ = result
        assert data.fecha_caducidad.startswith("20")

    def test_mrz_less_than_3_lines(self):
        result = DNIParser.parse_mrz("IDESPBHV12273807\n7301245M2808288ESP")
        assert result is None

    def test_mrz_ocr_spaces_around_chevron(self):
        mrz = _mrz(
            "IDESPBHV122738077612097T",
            "7301245M2808288ESP",
            "COLL < CEREZO << JOAQUIN",
        )
        result = DNIParser.parse_mrz(mrz)
        assert result is not None
        data, _ = result
        assert "COLL" in data.apellidos
        assert "CEREZO" in data.apellidos

    def test_mrz_raw_stored(self):
        mrz = _mrz(
            "IDESPBHV122738077612097T",
            "7301245M2808288ESP",
            "COLL<CEREZO<<JOAQUIN",
        )
        result = DNIParser.parse_mrz(mrz)
        data, raw = result
        assert data.mrz is not None
        assert data.mrz.raw is not None
        assert "IDESP" in data.mrz.raw


# ---------------------------------------------------------------------------
# parse_full_text
# ---------------------------------------------------------------------------

class TestParseFullText:
    def test_frontal_basic(self):
        text = """APELLIDOS
COLL CEREZO
NOMBRE
JOAQUIN
DNI
77612097T
SEXO
H
NACIONALIDAD
ESP"""
        data = DNIParser.parse_full_text(text)
        assert data.apellidos == "COLL CEREZO"
        assert data.nombre == "JOAQUIN"
        assert data.numero_documento == "77612097T"
        assert data.sexo == "M"
        assert data.nacionalidad == "ESP"

    def test_catalan_labels(self):
        text = """COGNOMS
GARCIA LOPEZ
NOM
MARIA
SEXE
D
NACIONALITAT
ESP"""
        data = DNIParser.parse_full_text(text)
        assert data.apellidos == "GARCIA LOPEZ"
        assert data.nombre == "MARIA"
        assert data.sexo == "F"

    def test_nie_detection(self):
        text = """APELLIDOS
GARCIA LOPEZ
NOMBRE
MARIA
NIE
X1234567L"""
        data = DNIParser.parse_full_text(text)
        assert data.numero_documento == "X1234567L"
        assert data.tipo_numero == "NIE"

    def test_nacimiento_without_fecha(self):
        text = """APELLIDOS
COLL CARRERAS
NOMBRE
MARTI
NACIMIENTO
15/06/2010
VALIDEZ
01/01/2015 21/03/2030"""
        data = DNIParser.parse_full_text(text)
        assert data.fecha_nacimiento == "2010-06-15"

    def test_validez_iso_format(self):
        text = """NOMBRE
JOAN
APELLIDOS
PUIG
VALIDEZ
01/01/2015 01/01/2025"""
        data = DNIParser.parse_full_text(text)
        assert data.fecha_caducidad == "2025-01-01"

    def test_sexe_not_captured_from_long_line(self):
        text = """SEXO
NACIONALIDAD
ESP"""
        data = DNIParser.parse_full_text(text)
        assert data.sexo is None

    def test_cognoms_artifact_filtered(self):
        text = """APELLIDOS
CEREZO JG17787 BAS
NOMBRE
VICTORIA"""
        data = DNIParser.parse_full_text(text)
        assert "JG17787" not in (data.apellidos or "")

    def test_nom_single_letter_prefix_removed(self):
        text = """NOMBRE
J IVAN"""
        data = DNIParser.parse_full_text(text)
        assert data.nombre == "IVAN"


# ---------------------------------------------------------------------------
# validate_and_build_response
# ---------------------------------------------------------------------------

class TestValidateAndBuildResponse:
    def _base(self):
        return DNIDatos(
            numero_documento="77612097T",
            nombre="JOAQUIN",
            apellidos="COLL CEREZO",
            fecha_nacimiento="1973-01-24",
            fecha_caducidad="2028-08-28",
        )

    def test_valid_document(self):
        result = DNIParser.validate_and_build_response(self._base(), None, "tesseract", 75.0)
        assert result.valido is True
        assert result.confianza_global > 60
        assert result.errores_detectados == []

    def test_invalid_check_letter(self):
        data = DNIDatos(numero_documento="77612097A", nombre="X", apellidos="Y",
                        fecha_nacimiento="1973-01-24")
        result = DNIParser.validate_and_build_response(data, None, "tesseract", 75.0)
        assert result.valido is False
        codes = [e.code for e in result.errores_detectados]
        assert "DNI_CHECKLETTER_MISMATCH" in codes

    def test_missing_documento(self):
        data = DNIDatos(nombre="X", apellidos="Y")
        result = DNIParser.validate_and_build_response(data, None, "tesseract", 75.0)
        assert result.valido is False
        codes = [e.code for e in result.errores_detectados]
        assert "DNI_MISSING_FIELD" in codes

    def test_expired_document(self):
        data = self._base()
        data.fecha_caducidad = "2020-01-01"
        result = DNIParser.validate_and_build_response(data, None, "google_vision", 90.0)
        codes = [e.code for e in result.errores_detectados]
        assert "DNI_EXPIRED" in codes

    def test_underage_is_alert(self):
        from datetime import date, timedelta
        birth = (date.today() - timedelta(days=365 * 15)).isoformat()
        data = self._base()
        data.fecha_nacimiento = birth
        result = DNIParser.validate_and_build_response(data, None, "google_vision", 90.0)
        codes = [a.code for a in result.alertas]
        assert "DNI_UNDERAGE" in codes
        # No és error crític, el document pot ser vàlid
        assert result.valido is True

    def test_mrz_mismatch_is_critical(self):
        data = self._base()
        data.mrz = MRZData(document_number="12345678Z")  # diferent del texto
        result = DNIParser.validate_and_build_response(data, None, "google_vision", 90.0)
        codes = [e.code for e in result.errores_detectados]
        assert "DNI_MRZ_MISMATCH" in codes
        assert result.valido is False

    def test_ocr_noise_generates_alert(self):
        data = self._base()
        data.nombre = "JO@QUIN"
        result = DNIParser.validate_and_build_response(data, None, "tesseract", 40.0)
        codes = [a.code for a in result.alertas]
        assert "DNI_NAME_OCR_NOISE" in codes

    def test_confianza_decreases_with_errors(self):
        good = DNIParser.validate_and_build_response(self._base(), None, "google_vision", 95.0)
        bad = DNIDatos(numero_documento="12345678A")
        bad_result = DNIParser.validate_and_build_response(bad, None, "tesseract", 30.0)
        assert good.confianza_global > bad_result.confianza_global

    def test_response_has_raw_and_meta(self):
        result = DNIParser.validate_and_build_response(self._base(), None, "tesseract", 75.0)
        assert result.raw.ocr_engine == "tesseract"
        assert result.raw.ocr_confidence == 75.0
        assert result.meta is not None
        assert result.meta.success == result.valido

    def test_tipo_documento_is_dni(self):
        result = DNIParser.validate_and_build_response(self._base(), None, "tesseract", 75.0)
        assert result.tipo_documento == "dni"

    def test_validation_item_has_required_fields(self):
        data = DNIDatos(nombre="X", apellidos="Y")
        result = DNIParser.validate_and_build_response(data, None, "tesseract", 50.0)
        for item in result.errores_detectados:
            assert item.code
            assert item.severity in ("warning", "error", "critical")
            assert item.message


# ---------------------------------------------------------------------------
# should_fallback_to_vision
# ---------------------------------------------------------------------------

class TestShouldFallback:
    def _base(self):
        return DNIDatos(
            numero_documento="77612097T",
            nombre="JOAQUIN",
            apellidos="COLL CEREZO",
            fecha_nacimiento="1973-01-24",
            fecha_caducitat="2028-08-28",
        )

    def test_no_fallback_when_ok(self):
        fallback, motiu = DNIParser.should_fallback_to_vision(self._base(), 75.0)
        assert fallback is False

    def test_fallback_when_no_document(self):
        data = self._base()
        data.numero_documento = None
        fallback, _ = DNIParser.should_fallback_to_vision(data, 75.0)
        assert fallback is True

    def test_fallback_when_invalid_document(self):
        data = self._base()
        data.numero_documento = "12345678A"
        fallback, _ = DNIParser.should_fallback_to_vision(data, 75.0)
        assert fallback is True

    def test_fallback_when_no_nombre(self):
        data = self._base()
        data.nombre = None
        fallback, _ = DNIParser.should_fallback_to_vision(data, 75.0)
        assert fallback is True

    def test_fallback_when_low_confidence(self):
        fallback, motiu = DNIParser.should_fallback_to_vision(self._base(), 30.0)
        assert fallback is True
        assert "confidence" in motiu
