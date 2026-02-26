"""
Parser expert per Targeta d'Identificació Fiscal (NIF/TIF) — Contracte unificat v1

Phase 1 — parse():          extracció raw del text OCR
Phase 2 — validate_and_build_response(): validació + codis normalitzats

COST: 1 sol crèdit Vision per document. Phase 1 i 2 son Python pur.
"""
import re
import logging
from datetime import date
from typing import Optional, Dict
from app.models.nif_response import NIFDatos, NIFValidationResponse
from app.models.base_response import ValidationItem, RawOCR, MetaInfo, compute_confianza

log = logging.getLogger("ocr.nif")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Lletres vàlides per CIF organitzacions
CIF_LETTERS = "ABCDEFGHJKLMNPQRSUVW"

# Mapeig dígit control → lletra (per CIF que requereixen lletra)
CIF_CONTROL_LETTERS = "JABCDEFGHI"  # índex 0-9

# Camps mínims NIF
_CAMPS_MINIMS = ["numero_nif", "razon_social", "domicilio_fiscal"]

# Províncies espanyoles completes (reutilitzades del DNI parser)
PROVINCIES = [
    "BARCELONA", "TARRAGONA", "LLEIDA", "GIRONA",  # Catalunya
    "MADRID", "VALENCIA", "ALICANTE", "CASTELLON", "CASTELLÓ",
    "SEVILLA", "MALAGA", "MÁLAGA", "CADIZ", "CÁDIZ", "HUELVA",
    "CORDOBA", "CÓRDOBA", "GRANADA", "JAEN", "JAÉN", "ALMERIA", "ALMERÍA",
    "ZARAGOZA", "HUESCA", "TERUEL",
    "A CORUÑA", "LA CORUÑA", "CORUÑA", "PONTEVEDRA", "OURENSE", "LUGO",
    "VIZCAYA", "BIZKAIA", "GUIPUZCOA", "GIPUZKOA", "ALAVA", "ARABA",
    "NAVARRA", "LA RIOJA", "RIOJA", "CANTABRIA", "ASTURIAS",
    "MURCIA", "BADAJOZ", "CACERES", "CÁCERES",
    "SALAMANCA", "ZAMORA", "VALLADOLID", "LEON", "LEÓN",
    "PALENCIA", "BURGOS", "SORIA", "SEGOVIA", "AVILA", "ÁVILA",
    "TOLEDO", "CIUDAD REAL", "CUENCA", "GUADALAJARA", "ALBACETE",
    "PALMAS, LAS", "SANTA CRUZ DE TENERIFE", "TENERIFE",
    "BALEARES", "BALEARS", "ILLES BALEARS",
]


# ---------------------------------------------------------------------------
# Helpers de data
# ---------------------------------------------------------------------------

def _dmy_to_iso(date_str: str) -> Optional[str]:
    """DD/MM/YYYY o DD-MM-YYYY → YYYY-MM-DD. Retorna None si format o rang invàlid."""
    m = re.match(r"^(\d{2})[-/](\d{2})[-/](\d{4})$", date_str)
    if not m:
        return None
    dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return None
    return f"{yyyy}-{mm:02d}-{dd:02d}"


def _validate_date(date_str: str, min_year: int, max_year: int) -> Optional[str]:
    """Valida DD/MM/YYYY o DD-MM-YYYY en rang i retorna ISO, o None si invàlid."""
    iso = _dmy_to_iso(date_str)
    if not iso:
        return None
    yyyy = int(iso[:4])
    if not (min_year <= yyyy <= max_year):
        return None
    return iso


# ---------------------------------------------------------------------------
# Validació CIF completa (CRÍTICA)
# ---------------------------------------------------------------------------

def validate_cif(cif: str) -> bool:
    """
    Valida CIF espanyol amb dígit de control calculat.

    Format: [ABCDEFGHJKLMNPQRSUVW]\\d{7}[A-J0-9]

    Algoritme AEAT oficial:
    1. Senars (pos 0,2,4,6): multiplicar per 2, si >=10 restar 9
    2. Parells (pos 1,3,5): sumar directament
    3. Control = (10 - últim_dígit_suma_total) % 10
    4. Lletra control = "JABCDEFGHI"[control_digit]
    5. Validar segons primera lletra:
       - A,B,E,H: només dígit
       - K,P,Q,S: només lletra
       - Altres: dígit o lletra
    """
    cif = cif.upper().strip()

    if not re.match(r"^[ABCDEFGHJKLMNPQRSUVW]\d{7}[A-J0-9]$", cif):
        return False

    letter = cif[0]
    number = cif[1:8]
    control = cif[8]

    # Calcular suma posicions senars (índexs 0,2,4,6)
    odd_sum = 0
    for i in range(0, 7, 2):
        n = int(number[i]) * 2
        odd_sum += n if n < 10 else n - 9

    # Calcular suma posicions parells (índexs 1,3,5)
    even_sum = sum(int(number[i]) for i in range(1, 7, 2))

    # Dígit de control
    control_digit = (10 - (even_sum + odd_sum) % 10) % 10
    control_letter = CIF_CONTROL_LETTERS[control_digit]

    # Validar segons lletra inicial
    if letter in "ABEH":
        return control == str(control_digit)
    elif letter in "KPQS":
        return control == control_letter
    else:
        return control == str(control_digit) or control == control_letter


def _expected_cif_control(cif: str) -> str:
    """Retorna el caràcter de control esperat per un CIF (per evidència d'error)."""
    if not cif or len(cif) < 8:
        return "?"

    cif = cif.upper().strip()
    if not re.match(r"^[ABCDEFGHJKLMNPQRSUVW]\d{7}", cif):
        return "?"

    letter = cif[0]
    number = cif[1:8]

    # Calcular control
    odd_sum = 0
    for i in range(0, 7, 2):
        n = int(number[i]) * 2
        odd_sum += n if n < 10 else n - 9
    even_sum = sum(int(number[i]) for i in range(1, 7, 2))
    control_digit = (10 - (even_sum + odd_sum) % 10) % 10
    control_letter = CIF_CONTROL_LETTERS[control_digit]

    # Retornar segons tipus
    if letter in "ABEH":
        return str(control_digit)
    elif letter in "KPQS":
        return control_letter
    else:
        return f"{control_digit}/{control_letter}"


# ---------------------------------------------------------------------------
# Extracció d'adreça (reutilitzada del DNI parser)
# ---------------------------------------------------------------------------

def _parse_domicilio_inline(lines: list[str], line_idx: int, primera_linia: str) -> Dict[str, Optional[str]]:
    """
    Extreu components d'un domicili quan la primera línia ja està extreta.

    Args:
        lines: Totes les línies del text
        line_idx: Índex de la línia actual (keyword)
        primera_linia: Primera línia del domicili (ex: "CALLE ORINOCO, NUM. 5")

    Retorna: {completo, calle, numero, piso_puerta, municipio, provincia, codigo_postal}
    """
    adreca_lines = [primera_linia]
    STOP_KEYWORDS = ["DOMICILIO", "FECHA", "ADMINISTRACIÓN", "ADMINISTRACION",
                     "CÓDIGO", "CODIGO", "ANAGRAMA", "N.I.F", "NIF", "B762"]

    # Llegir línies següents per CP, municipi, província
    for j in range(line_idx + 1, min(line_idx + 5, len(lines))):
        nl = lines[j].strip()
        if not nl:
            break
        # Aturar si trobem keywords (però permetre "Social" o "Fiscal" amb info addicional)
        if any(kw in nl.upper() for kw in STOP_KEYWORDS):
            break

        # Si la línia comença amb "Social" o "Fiscal", extreure la part després
        if nl.upper().startswith("SOCIAL") or nl.upper().startswith("FISCAL"):
            # Ex: "Social 35016 PALMAS..." → agafar "35016 PALMAS..."
            # Ex: "Fiscal PLANTA 0, PUERTA 3" → agafar "PLANTA 0, PUERTA 3"
            rest = nl.split(None, 1)
            if len(rest) > 1:
                adreca_lines.append(rest[1])
        else:
            adreca_lines.append(nl)

    result = {}
    domicilio_completo = " ".join(adreca_lines)
    result["completo"] = domicilio_completo

    # Separar número + pis/porta de la primera línia
    full_match = re.search(
        r"[,\s]+(?:NUM\.?\s*)?(\d{1,4}[A-Z]?)\s*[,]?\s*(PLANTA\s*\d+[,]?\s*PUERTA\s*\d+|P[O0]?\d+\s*\d*|[PB]\d+|\d+[ºª°]?\s*[A-Z]?)?",
        primera_linia,
        re.IGNORECASE
    )

    if full_match:
        result["numero"] = full_match.group(1).strip()
        if full_match.group(2):
            result["piso_puerta"] = full_match.group(2).strip()
        result["calle"] = primera_linia[:full_match.start()].strip()
        # Netejar "NUM." del carrer si hi és
        result["calle"] = re.sub(r",?\s*NUM\.?\s*$", "", result["calle"], flags=re.IGNORECASE)
    else:
        # No hem trobat número, tot és carrer
        result["calle"] = primera_linia

    # Buscar pis/porta en altres línies si no l'hem trobat a la primera
    if not result.get("piso_puerta"):
        for line in adreca_lines[1:]:
            piso_match = re.search(r"(PLANTA\s*\d+[,]?\s*PUERTA\s*\d+|PLANTA\s*\d+|PUERTA\s*\d+|P[O0]?\d+\s*\d*)", line, re.IGNORECASE)
            if piso_match:
                result["piso_puerta"] = piso_match.group(1).strip()
                break

    # Buscar codi postal, municipi, província en les línies següents
    for line in adreca_lines:
        cp_match = re.search(r"\b(\d{5})\b", line)
        if cp_match:
            result["codigo_postal"] = cp_match.group(1)
            # La resta de la línia després del CP pot ser municipi + província
            rest = line[cp_match.end():].strip()
            if rest:
                # Separar per guió o parèntesis: "PALMAS DE GRAN CANARIA (LAS) - (PALMAS, LAS)"
                parts = re.split(r'\s*-\s*|\s*\(\s*', rest)
                if parts:
                    result["municipio"] = parts[0].strip().rstrip(")")
                if len(parts) > 1:
                    result["provincia"] = parts[1].strip().rstrip(")")
            break

    return result


def _parse_domicilio(lines: list[str], start_idx: int) -> Dict[str, Optional[str]]:
    """
    Extreu components d'un domicili des de start_idx.

    Retorna: {
        completo, calle, numero, piso_puerta,
        municipio, provincia, codigo_postal
    }

    Reutilitza lògica del dni_parser.py amb adaptacions per TIF.
    """
    adreca_lines = []
    STOP_KEYWORDS = ["DOMICILIO", "FECHA", "ADMINISTRACIÓN", "ADMINISTRACION",
                     "CÓDIGO", "CODIGO", "ANAGRAMA", "N.I.F", "NIF"]

    # Llegir línies següents fins keyword o línia buida
    for j in range(start_idx + 1, min(start_idx + 8, len(lines))):
        nl = lines[j].strip()
        if not nl:
            break
        # Aturar si trobem keywords NO relacionades amb adreça
        if any(kw in nl.upper() for kw in STOP_KEYWORDS):
            break
        adreca_lines.append(nl)

    if not adreca_lines:
        return {}

    result = {}
    domicilio_completo = " ".join(adreca_lines)
    result["completo"] = domicilio_completo

    # Primera línia: carrer + número + pis/porta
    primera_linia = adreca_lines[0]

    # Separar número + pis/porta (regex DNI reutilitzat)
    # Ex: "CALLE ORINOCO, NUM. 5, PLANTA 0, PUERTA 3"
    full_match = re.search(
        r"[,\s]+(?:NUM\.?\s*)?(\d{1,4}[A-Z]?)\s*[,]?\s*(PLANTA\s*\d+[,]?\s*PUERTA\s*\d+|P[O0]?\d+\s*\d*|[PB]\d+|\d+[ºª°]?\s*[A-Z]?)?",
        primera_linia,
        re.IGNORECASE
    )

    if full_match:
        result["numero"] = full_match.group(1).strip()
        if full_match.group(2):
            result["piso_puerta"] = full_match.group(2).strip()
        result["calle"] = primera_linia[:full_match.start()].strip()
        # Netejar "NUM." del carrer si hi és
        result["calle"] = re.sub(r",?\s*NUM\.?\s*$", "", result["calle"], flags=re.IGNORECASE)
    else:
        # No hem trobat piso/puerta, només número al final
        numero_match = re.search(r"[,\s]+(\d+[A-Z]?)\s*$", primera_linia)
        if numero_match:
            result["numero"] = numero_match.group(1).strip()
            result["calle"] = primera_linia[:numero_match.start()].strip()
        else:
            # Si no hi ha número, tot és carrer
            result["calle"] = primera_linia

    # Buscar codi postal (5 dígits) en TOTES les línies
    for line in adreca_lines:
        cp_match = re.search(r"\b(\d{5})\b", line)
        if cp_match:
            result["codigo_postal"] = cp_match.group(1)
            break

    # Detectar província (normalment a les darreres línies)
    provincia_idx = None
    for idx in range(len(adreca_lines) - 1, -1, -1):
        line_upper = adreca_lines[idx].upper().strip()
        for prov in PROVINCIES:
            if prov in line_upper:
                provincia_idx = idx
                result["provincia"] = adreca_lines[idx].strip()
                # Netejar codi postal de la província si hi és
                result["provincia"] = re.sub(r"^\d{5}\s+", "", result["provincia"])
                break
        if provincia_idx is not None:
            break

    # Detectar municipi (normalment abans de província o en segona línia)
    if provincia_idx is not None and provincia_idx > 0:
        # La línia anterior a província és municipi
        poblacio_line = adreca_lines[provincia_idx - 1]
        # Treure codi postal si està davant
        poblacio_line = re.sub(r"^\d{5}\s+", "", poblacio_line)
        result["municipio"] = poblacio_line.strip() or None
    elif len(adreca_lines) > 1:
        # Si no hem trobat província, segona línia pot ser municipi
        pob = adreca_lines[1]
        pob = re.sub(r"^\d{5}\s+", "", pob)
        result["municipio"] = pob.strip() or None

    return result


# ---------------------------------------------------------------------------
# Parser — Phase 1: extracció raw
# ---------------------------------------------------------------------------

class NIFParser:

    @staticmethod
    def parse(text: str) -> NIFDatos:
        """Phase 1: extracció raw per keywords (0 crèdits)"""
        data = NIFDatos()
        lines = text.split("\n")

        # Número NIF (CIF)
        cif_m = re.search(r"\b([ABCDEFGHJKLMNPQRSUVW]\d{7}[A-J0-9])\b", text)
        if cif_m:
            data.numero_nif = cif_m.group(1).upper()
            data.tipo_nif = "CIF"

        # Recórrer línies detectant keywords
        i = 0
        while i < len(lines):
            line = lines[i]
            lu = line.upper()

            if ("DENOMINACIÓN" in lu or "DENOMINACION" in lu) and "FISCAL" not in lu:
                # Primer intentar extreure de la mateixa línia
                val_match = re.search(r"(?:DENOMINACIÓN|DENOMINACION)[:\s]+(.+)", line, re.IGNORECASE)
                if val_match:
                    val = val_match.group(1).strip()
                elif i + 1 < len(lines):
                    val = lines[i + 1].strip()
                else:
                    val = None

                if val and val not in ["0", "o", "O"] and ":" not in val:  # Evitar keywords com "Anagrama Comercial:"
                    data.denominacion = val
                    data.razon_social = val

            elif ("RAZÓN SOCIAL" in lu or "RAZON SOCIAL" in lu) and not data.razon_social:
                # Només processar si encara no tenim raó social (prioritat a Denominación)
                val_match = re.search(r"(?:RAZÓN SOCIAL|RAZON SOCIAL)[:\s]+(.+)", line, re.IGNORECASE)
                if val_match:
                    val = val_match.group(1).strip()
                    if val and ":" not in val:
                        data.razon_social = val
                        data.denominacion = val

            elif "ANAGRAMA COMERCIAL" in lu:
                # Primer intentar extreure de la mateixa línia
                val_match = re.search(r"ANAGRAMA COMERCIAL[:\s]+(.+)", line, re.IGNORECASE)
                if val_match:
                    val = val_match.group(1).strip()
                    if val:
                        data.anagrama_comercial = val
                elif i + 1 < len(lines):
                    val = lines[i + 1].strip()
                    if val:
                        data.anagrama_comercial = val

            elif "DOMICILIO" in lu and "SOCIAL" not in lu and "FISCAL" not in lu:
                # "Domicilio" sol, pot ser social o fiscal segons línia següent
                val_match = re.search(r"DOMICILIO\s+(.+)", line, re.IGNORECASE)
                if val_match:
                    primera_linia = val_match.group(1).strip()
                    # Mirar línia següent per determinar tipus
                    es_social = False
                    es_fiscal = False

                    if i + 1 < len(lines):
                        next_line = lines[i + 1].upper()
                        if "SOCIAL" in next_line and "DOMICILIO" not in next_line:
                            es_social = True
                        elif "FISCAL" in next_line and "DOMICILIO" not in next_line:
                            es_fiscal = True

                    if es_social and not data.domicilio_social:
                        domicilio = _parse_domicilio_inline(lines, i, primera_linia)
                        data.domicilio_social = domicilio.get("completo")
                        data.domicilio_social_calle = domicilio.get("calle")
                        data.domicilio_social_numero = domicilio.get("numero")
                        data.domicilio_social_piso_puerta = domicilio.get("piso_puerta")
                        data.domicilio_social_municipio = domicilio.get("municipio")
                        data.domicilio_social_provincia = domicilio.get("provincia")
                        data.domicilio_social_codigo_postal = domicilio.get("codigo_postal")
                    elif es_fiscal and not data.domicilio_fiscal:
                        domicilio = _parse_domicilio_inline(lines, i, primera_linia)
                        data.domicilio_fiscal = domicilio.get("completo")
                        data.domicilio_fiscal_calle = domicilio.get("calle")
                        data.domicilio_fiscal_numero = domicilio.get("numero")
                        data.domicilio_fiscal_piso_puerta = domicilio.get("piso_puerta")
                        data.domicilio_fiscal_municipio = domicilio.get("municipio")
                        data.domicilio_fiscal_provincia = domicilio.get("provincia")
                        data.domicilio_fiscal_codigo_postal = domicilio.get("codigo_postal")

            elif "DOMICILIO" in lu and ("SOCIAL" in lu or "FISCAL" in lu):
                # "Domicilio Social" o "Domicilio Fiscal" a la mateixa línia
                val_match = re.search(r"DOMICILIO\s+(?:SOCIAL|FISCAL)?\s*(.+)", line, re.IGNORECASE)
                if val_match:
                    val = val_match.group(1).strip()
                    if val and "SOCIAL" not in val.upper() and "FISCAL" not in val.upper():
                        # Hi ha adreça a la mateixa línia
                        domicilio = _parse_domicilio_inline(lines, i, val)
                    else:
                        # Adreça a les línies següents
                        domicilio = _parse_domicilio(lines, i)

                    if "SOCIAL" in lu:
                        data.domicilio_social = domicilio.get("completo")
                        data.domicilio_social_calle = domicilio.get("calle")
                        data.domicilio_social_numero = domicilio.get("numero")
                        data.domicilio_social_piso_puerta = domicilio.get("piso_puerta")
                        data.domicilio_social_municipio = domicilio.get("municipio")
                        data.domicilio_social_provincia = domicilio.get("provincia")
                        data.domicilio_social_codigo_postal = domicilio.get("codigo_postal")
                    elif "FISCAL" in lu:
                        data.domicilio_fiscal = domicilio.get("completo")
                        data.domicilio_fiscal_calle = domicilio.get("calle")
                        data.domicilio_fiscal_numero = domicilio.get("numero")
                        data.domicilio_fiscal_piso_puerta = domicilio.get("piso_puerta")
                        data.domicilio_fiscal_municipio = domicilio.get("municipio")
                        data.domicilio_fiscal_provincia = domicilio.get("provincia")
                        data.domicilio_fiscal_codigo_postal = domicilio.get("codigo_postal")

            elif ("ADMINISTRACIÓN" in lu or "ADMINISTRACION" in lu) and "AEAT" in lu:
                # Primer intentar extreure de la mateixa línia
                val_match = re.search(r"ADMINISTRACI[OÓ]N\s+(?:DE\s+LA\s+)?AEAT\s+(.+)", line, re.IGNORECASE)
                if val_match:
                    val = val_match.group(1).strip()
                elif i + 1 < len(lines):
                    val = lines[i + 1].strip()
                else:
                    val = None

                if val:
                    data.administracion_aeat = val
                    # Separar: "35601 PALMAS G.C" → codigo="35601", nombre="PALMAS G.C"
                    parts = val.split(None, 1)
                    if len(parts) == 2 and parts[0].isdigit():
                        data.codigo_administracion = parts[0]
                        data.nombre_administracion = parts[1]

            elif "FECHA N.I.F. DEFINITIVO" in lu or "FECHA NIF DEFINITIVO" in lu:
                if i + 1 < len(lines):
                    date_m = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", lines[i + 1])
                    if date_m:
                        raw = f"{date_m.group(1)}/{date_m.group(2)}/{date_m.group(3)}"
                        data.fecha_nif_definitivo = _validate_date(raw, 1980, date.today().year)

            elif "FECHA DE EXPEDICIÓN" in lu or "FECHA DE EXPEDICION" in lu:
                if i + 1 < len(lines):
                    date_m = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", lines[i + 1])
                    if date_m:
                        raw = f"{date_m.group(1)}/{date_m.group(2)}/{date_m.group(3)}"
                        data.fecha_expedicion = _validate_date(raw, 1980, date.today().year)

            elif "CÓDIGO ELECTRÓNICO" in lu or "CODIGO ELECTRONICO" in lu:
                if i + 1 < len(lines):
                    val = lines[i + 1].strip()
                    # Validar format (hex)
                    if re.match(r"^[A-F0-9]{10,}$", val, re.IGNORECASE):
                        data.codigo_electronico = val.upper()

            i += 1

        return data


    @staticmethod
    def validate_and_build_response(
        data: NIFDatos,
        ocr_engine: str,
        ocr_confidence: float,
    ) -> NIFValidationResponse:
        """Phase 2: validació creuada (0 crèdits)"""
        errors: list[ValidationItem] = []
        alerts: list[ValidationItem] = []

        # Validar NIF (CIF)
        if not data.numero_nif:
            errors.append(ValidationItem(
                code="NIF_MISSING_FIELD",
                severity="critical",
                field="numero_nif",
                message="Número NIF (CIF) no detectat.",
            ))
        elif not validate_cif(data.numero_nif):
            expected = _expected_cif_control(data.numero_nif)
            errors.append(ValidationItem(
                code="NIF_CHECKDIGIT_MISMATCH",
                severity="critical",
                field="numero_nif",
                message="Dígit de control CIF incorrecte.",
                evidence=f"Llegit: '{data.numero_nif[-1]}', esperat: '{expected}'",
            ))

        # Validar camps mínims
        camps_minims_absents = 0
        for camp in _CAMPS_MINIMS:
            val = getattr(data, camp, None)
            if not val:
                camps_minims_absents += 1
                errors.append(ValidationItem(
                    code="NIF_MISSING_FIELD",
                    severity="critical" if camp == "numero_nif" else "error",
                    field=camp,
                    message=f"Camp mínim '{camp}' no detectat.",
                ))

        # Validar dates
        if data.fecha_nif_definitivo:
            if data.fecha_nif_definitivo > date.today().isoformat():
                errors.append(ValidationItem(
                    code="NIF_DATE_INVALID",
                    severity="error",
                    field="fecha_nif_definitivo",
                    message="Data NIF Definitiu en el futur.",
                ))

        if data.fecha_expedicion:
            if data.fecha_expedicion > date.today().isoformat():
                errors.append(ValidationItem(
                    code="NIF_DATE_INVALID",
                    severity="error",
                    field="fecha_expedicion",
                    message="Data expedició en el futur.",
                ))

        # Calcular confiança (fórmula contracte v1)
        confianza = compute_confianza(alerts, errors, camps_minims_absents, ocr_confidence)

        # Decidir valido
        has_critical = any(e.severity == "critical" for e in errors)
        has_minimums = bool(data.numero_nif and data.razon_social and data.domicilio_fiscal)
        valido = not has_critical and has_minimums

        return NIFValidationResponse(
            valido=valido,
            confianza_global=confianza,
            datos=data,
            alertas=alerts,
            errores_detectados=errors,
            raw=RawOCR(ocr_engine=ocr_engine, ocr_confidence=round(ocr_confidence, 1)),
            meta=MetaInfo(
                success=valido,
                message=f"[{ocr_engine}] {'Validació correcta' if valido else 'Errors detectats'}"
            ),
        )


# Singleton
nif_parser = NIFParser()
