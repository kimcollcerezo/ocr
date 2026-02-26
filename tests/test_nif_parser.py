"""
Tests unitaris per NIF parser.
"""
import pytest
from app.parsers.nif_parser import validate_cif, nif_parser, NIFParser
from app.models.nif_response import NIFDatos


# ---------------------------------------------------------------------------
# Tests de validació CIF
# ---------------------------------------------------------------------------

class TestValidateCif:
    """Tests per la validació CIF amb algoritme AEAT oficial"""

    def test_cif_b76261874_valid(self):
        """CIF real de la imatge: B76261874"""
        assert validate_cif("B76261874") is True

    def test_cif_wrong_checkdigit(self):
        """CIF amb dígit de control incorrecte"""
        assert validate_cif("B76261875") is False
        assert validate_cif("B76261873") is False

    def test_cif_case_insensitive(self):
        """CIF en minúscules hauria de validar"""
        assert validate_cif("b76261874") is True
        assert validate_cif("B76261874") is True

    def test_cif_a_requires_digit(self):
        """Lletra A requereix dígit de control, no lletra"""
        # A58818501 és un CIF vàlid amb dígit
        assert validate_cif("A58818501") is True
        # Si posem una lletra, hauria de fallar
        assert validate_cif("A5881850J") is False

    def test_cif_b_requires_digit(self):
        """Lletra B requereix dígit de control"""
        assert validate_cif("B76261874") is True
        # Amb lletra en lloc de dígit hauria de fallar
        assert validate_cif("B7626187D") is False

    def test_cif_e_requires_digit(self):
        """Lletra E requereix dígit de control"""
        # E78476350 és un exemple vàlid
        assert validate_cif("E78476350") is True

    def test_cif_k_requires_letter(self):
        """Lletra K requereix lletra de control, no dígit"""
        # K0000000E és un exemple (cal calcular control correcte)
        # Per ara, test amb format correcte
        # K requereix lletra, així que amb dígit hauria de fallar
        # Primer calculem un K vàlid: K1234567 → control calculat
        # Suma senars: 1*2=2, 3*2=6, 5*2=10→1, 7*2=14→5 = 2+6+1+5=14
        # Suma parells: 2+4+6=12
        # Total: 14+12=26 → 26%10=6 → control=(10-6)%10=4 → lletra='E'
        assert validate_cif("K1234567E") is True
        assert validate_cif("K12345674") is False  # dígit no permès per K

    def test_cif_p_requires_letter(self):
        """Lletra P requereix lletra de control"""
        # P calculat: P1234567
        # Senars: 1*2=2, 3*2=6, 5*2=10→1, 7*2=14→5 = 14
        # Parells: 2+4+6=12
        # Total: 26 → control=4 → 'E'
        assert validate_cif("P1234567E") is True
        assert validate_cif("P12345674") is False

    def test_cif_q_requires_letter(self):
        """Lletra Q requereix lletra de control"""
        assert validate_cif("Q1234567E") is True
        assert validate_cif("Q12345674") is False

    def test_cif_s_requires_letter(self):
        """Lletra S requereix lletra de control"""
        assert validate_cif("S1234567E") is True
        assert validate_cif("S12345674") is False

    def test_cif_other_letters_allow_both(self):
        """Altres lletres (C,D,F,G,J,N,R,U,V,W) accepten dígit o lletra"""
        # C1234567 → control 4 o 'E'
        assert validate_cif("C1234567E") is True
        assert validate_cif("C12345674") is True
        assert validate_cif("C12345675") is False  # control incorrecte

    def test_cif_invalid_format(self):
        """Formats invàlids"""
        assert validate_cif("123456789") is False
        assert validate_cif("Z1234567A") is False  # Z no és lletra CIF
        assert validate_cif("B762618") is False    # massa curt
        assert validate_cif("B76261874X") is False  # massa llarg
        assert validate_cif("") is False
        assert validate_cif("ABCDEFGHI") is False

    def test_cif_with_spaces(self):
        """CIF amb espais hauria de validar (es neteja automàticament)"""
        assert validate_cif(" B76261874 ") is True
        assert validate_cif("B 76261874") is False  # espai dins no és vàlid


# ---------------------------------------------------------------------------
# Tests de parse (Phase 1)
# ---------------------------------------------------------------------------

def _text_tif_basic():
    """Text OCR sintètic d'una TIF bàsica"""
    return """\
TARJETA DE IDENTIFICACIÓN FISCAL
Número de Identificación Fiscal Definitivo
B76261874
Denominación
CASAACTIVA GESTION, S.L.
Domicilio Fiscal
CALLE ORINOCO, NUM. 5, PLANTA 0, PUERTA 3
35014 PALMAS DE GRAN CANARIA (LAS)
PALMAS, LAS
Fecha N.I.F. Definitivo
26-07-2016
Administración
35601 PALMAS G.C
"""


def _text_tif_complete():
    """Text OCR sintètic amb tots els camps"""
    return """\
TARJETA DE IDENTIFICACIÓN FISCAL
Número de Identificación Fiscal Definitivo
B76261874
Denominación
CASAACTIVA GESTION, S.L.
Anagrama Comercial
CASAACTIVA
Domicilio Social
CALLE EXAMPLE 123
28001 MADRID
MADRID
Domicilio Fiscal
CALLE ORINOCO, NUM. 5, PLANTA 0, PUERTA 3
35014 PALMAS DE GRAN CANARIA (LAS)
PALMAS, LAS
Fecha N.I.F. Definitivo
26-07-2016
Fecha de Expedición
15-01-2020
Administración
35601 PALMAS G.C
Código Electrónico
A1B2C3D4E5F6
"""


class TestNIFParserParse:
    """Tests per Phase 1 (extracció raw)"""

    def test_numero_nif_extret(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.numero_nif == "B76261874"
        assert data.tipo_nif == "CIF"

    def test_razon_social_extreta(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.razon_social is not None
        assert "CASAACTIVA" in data.razon_social

    def test_denominacion_alias_razon_social(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.denominacion == data.razon_social

    def test_domicilio_fiscal_components(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.domicilio_fiscal is not None
        assert "ORINOCO" in data.domicilio_fiscal
        assert data.domicilio_fiscal_calle is not None
        assert "ORINOCO" in data.domicilio_fiscal_calle
        assert data.domicilio_fiscal_numero == "5"
        assert data.domicilio_fiscal_piso_puerta is not None
        assert "PLANTA 0" in data.domicilio_fiscal_piso_puerta
        assert "PUERTA 3" in data.domicilio_fiscal_piso_puerta

    def test_domicilio_fiscal_cp(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.domicilio_fiscal_codigo_postal == "35014"

    def test_domicilio_fiscal_municipio(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.domicilio_fiscal_municipio is not None
        assert "PALMAS" in data.domicilio_fiscal_municipio

    def test_domicilio_fiscal_provincia(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.domicilio_fiscal_provincia is not None
        assert "PALMAS" in data.domicilio_fiscal_provincia

    def test_fecha_iso_format(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.fecha_nif_definitivo == "2016-07-26"

    def test_administracion_aeat(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.administracion_aeat is not None
        assert "35601" in data.administracion_aeat
        assert data.codigo_administracion == "35601"
        assert data.nombre_administracion == "PALMAS G.C"

    def test_anagrama_comercial(self):
        data = nif_parser.parse(_text_tif_complete())
        assert data.anagrama_comercial == "CASAACTIVA"

    def test_domicilio_social_vs_fiscal(self):
        data = nif_parser.parse(_text_tif_complete())
        # Social
        assert data.domicilio_social is not None
        assert "EXAMPLE" in data.domicilio_social
        assert data.domicilio_social_codigo_postal == "28001"
        # Fiscal
        assert data.domicilio_fiscal is not None
        assert "ORINOCO" in data.domicilio_fiscal
        assert data.domicilio_fiscal_codigo_postal == "35014"
        # No s'han barrejat
        assert data.domicilio_social != data.domicilio_fiscal

    def test_fecha_expedicion(self):
        data = nif_parser.parse(_text_tif_complete())
        assert data.fecha_expedicion == "2020-01-15"

    def test_codigo_electronico(self):
        data = nif_parser.parse(_text_tif_complete())
        assert data.codigo_electronico == "A1B2C3D4E5F6"

    def test_campos_opcionales_none_si_absents(self):
        data = nif_parser.parse(_text_tif_basic())
        assert data.anagrama_comercial is None
        assert data.domicilio_social is None
        assert data.fecha_expedicion is None
        assert data.codigo_electronico is None


# ---------------------------------------------------------------------------
# Tests de validate_and_build_response (Phase 2)
# ---------------------------------------------------------------------------

class TestValidateAndBuildResponse:
    """Tests per Phase 2 (validació creuada)"""

    def test_document_valid(self):
        data = NIFDatos(
            numero_nif="B76261874",
            razon_social="CASAACTIVA GESTION, S.L.",
            domicilio_fiscal="CALLE ORINOCO, NUM. 5",
        )
        result = nif_parser.validate_and_build_response(data, "google_vision", 95.0)
        assert result.valido is True
        assert result.tipo_documento == "nif"
        assert result.confianza_global > 80
        assert len(result.errores_detectados) == 0

    def test_nif_missing(self):
        data = NIFDatos(
            razon_social="CASAACTIVA GESTION, S.L.",
            domicilio_fiscal="CALLE ORINOCO, NUM. 5",
        )
        result = nif_parser.validate_and_build_response(data, "google_vision", 90.0)
        assert result.valido is False
        codes = [e.code for e in result.errores_detectados]
        assert "NIF_MISSING_FIELD" in codes
        # Buscar l'error específic de numero_nif
        nif_errors = [e for e in result.errores_detectados if e.field == "numero_nif"]
        assert len(nif_errors) == 1
        assert nif_errors[0].severity == "critical"

    def test_nif_checkdigit_error(self):
        data = NIFDatos(
            numero_nif="B76261875",  # control incorrecte
            razon_social="CASAACTIVA GESTION, S.L.",
            domicilio_fiscal="CALLE ORINOCO, NUM. 5",
        )
        result = nif_parser.validate_and_build_response(data, "google_vision", 90.0)
        assert result.valido is False
        codes = [e.code for e in result.errores_detectados]
        assert "NIF_CHECKDIGIT_MISMATCH" in codes
        # Verificar severitat critical
        checkdigit_errors = [e for e in result.errores_detectados if e.code == "NIF_CHECKDIGIT_MISMATCH"]
        assert len(checkdigit_errors) == 1
        assert checkdigit_errors[0].severity == "critical"
        assert "esperat" in checkdigit_errors[0].evidence.lower()

    def test_razon_social_missing(self):
        data = NIFDatos(
            numero_nif="B76261874",
            domicilio_fiscal="CALLE ORINOCO, NUM. 5",
        )
        result = nif_parser.validate_and_build_response(data, "google_vision", 90.0)
        assert result.valido is False
        # Hauria de tenir error de razon_social
        razon_errors = [e for e in result.errores_detectados if e.field == "razon_social"]
        assert len(razon_errors) == 1
        assert razon_errors[0].severity == "error"  # no critical

    def test_domicilio_fiscal_missing(self):
        data = NIFDatos(
            numero_nif="B76261874",
            razon_social="CASAACTIVA GESTION, S.L.",
        )
        result = nif_parser.validate_and_build_response(data, "google_vision", 90.0)
        assert result.valido is False
        # Hauria de tenir error de domicilio_fiscal
        dom_errors = [e for e in result.errores_detectados if e.field == "domicilio_fiscal"]
        assert len(dom_errors) == 1
        assert dom_errors[0].severity == "error"

    def test_fecha_future_invalid(self):
        data = NIFDatos(
            numero_nif="B76261874",
            razon_social="CASAACTIVA GESTION, S.L.",
            domicilio_fiscal="CALLE ORINOCO, NUM. 5",
            fecha_nif_definitivo="2099-12-31",  # futur
        )
        result = nif_parser.validate_and_build_response(data, "google_vision", 90.0)
        # No és critical, però hi ha error
        date_errors = [e for e in result.errores_detectados if e.code == "NIF_DATE_INVALID"]
        assert len(date_errors) == 1
        assert date_errors[0].severity == "error"

    def test_confianza_global_calculation(self):
        """Verificar que la confiança es calcula correctament"""
        # Document perfecte
        data = NIFDatos(
            numero_nif="B76261874",
            razon_social="CASAACTIVA GESTION, S.L.",
            domicilio_fiscal="CALLE ORINOCO, NUM. 5",
        )
        result = nif_parser.validate_and_build_response(data, "google_vision", 100.0)
        assert result.confianza_global == 100

        # Document amb error no critical
        data2 = NIFDatos(
            numero_nif="B76261874",
            razon_social="CASAACTIVA GESTION, S.L.",
            # domicilio_fiscal absent → error severity="error"
        )
        result2 = nif_parser.validate_and_build_response(data2, "google_vision", 100.0)
        # base 100 - 15 (error) - 20 (camp mínim absent) = 65
        # amb ajust OCR: 65*0.85 + 100*0.15 = 55.25 + 15 = 70.25 → 70
        assert result2.confianza_global < 100
        assert result2.confianza_global > 0

    def test_raw_ocr_metadata(self):
        data = NIFDatos(
            numero_nif="B76261874",
            razon_social="CASAACTIVA GESTION, S.L.",
            domicilio_fiscal="CALLE ORINOCO, NUM. 5",
        )
        result = nif_parser.validate_and_build_response(data, "google_vision", 87.3)
        assert result.raw.ocr_engine == "google_vision"
        assert result.raw.ocr_confidence == 87.3

    def test_meta_info(self):
        data = NIFDatos(
            numero_nif="B76261874",
            razon_social="CASAACTIVA GESTION, S.L.",
            domicilio_fiscal="CALLE ORINOCO, NUM. 5",
        )
        result = nif_parser.validate_and_build_response(data, "google_vision", 95.0)
        assert result.meta is not None
        assert result.meta.success is True
        assert "google_vision" in result.meta.message
