"""
Parser expert per DNI/NIE espanyol — Contracte unificat v1

Phase 1 — parse():          extracció raw del text OCR
Phase 2 — validate_and_build_response(): validació + codis normalitzats

COST: 1 sol crèdit Vision per document. Phase 1 i 2 son Python pur.
TODO (futur): si confianza_global < 85 → Claude text-only per refinament
"""
import re
import logging
from datetime import date
from typing import Optional
from app.models.dni_response import DNIDatos, MRZData, DNIValidationResponse
from app.models.base_response import ValidationItem, RawOCR, MetaInfo, compute_confianza

log = logging.getLogger("ocr.parser")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

# Camps mínims DNI (per calcular absents i decidir valido)
_CAMPS_MINIMS = ["numero_documento", "nombre", "apellidos", "fecha_nacimiento"]


# ---------------------------------------------------------------------------
# Helpers de data
# ---------------------------------------------------------------------------

def _dmy_to_iso(date_str: str) -> Optional[str]:
    """DD/MM/YYYY → YYYY-MM-DD. Retorna None si format o rang invàlid."""
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", date_str)
    if not m:
        return None
    dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return None
    return f"{yyyy}-{mm:02d}-{dd:02d}"


def _validate_dmy(date_str: str, min_year: int, max_year: int) -> Optional[str]:
    """Valida DD/MM/YYYY en rang i retorna ISO, o None si invàlid."""
    iso = _dmy_to_iso(date_str)
    if not iso:
        return None
    yyyy = int(iso[:4])
    if not (min_year <= yyyy <= max_year):
        return None
    return iso


# ---------------------------------------------------------------------------
# Helpers de validació documental
# ---------------------------------------------------------------------------

def validate_doc_number(doc: str) -> bool:
    """Valida DNI (8d+lletra) o NIE (X/Y/Z+7d+lletra) amb lletra control."""
    doc = doc.upper().strip()
    if re.match(r"^\d{8}[A-Z]$", doc):
        return doc[-1] == DNI_LETTERS[int(doc[:8]) % 23]
    if re.match(r"^[XYZ]\d{7}[A-Z]$", doc):
        prefix = {"X": "0", "Y": "1", "Z": "2"}[doc[0]]
        return doc[-1] == DNI_LETTERS[int(prefix + doc[1:8]) % 23]
    return False


def _doc_type(doc: str) -> Optional[str]:
    if re.match(r"^\d{8}[A-Z]$", doc):
        return "DNI"
    if re.match(r"^[XYZ]\d{7}[A-Z]$", doc):
        return "NIE"
    return None


def _clean_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    # Eliminar prefixos comuns d'error OCR (bdr, nif, dni, etc.)
    value = re.sub(r"^(bdr|nif|dni|nie|doc)\s+", "", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ \-']", "", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _has_ocr_noise(value: Optional[str]) -> bool:
    """Cert si el camp té caràcters no esperats en un nom propi."""
    if not value:
        return False
    return bool(re.search(r"[^A-Za-zÀ-ÖØ-öø-ÿ \-']", value))


# ---------------------------------------------------------------------------
# Parser — Phase 1: extracció raw
# ---------------------------------------------------------------------------

class DNIParser:

    @staticmethod
    def parse_mrz(text: str) -> Optional[tuple[DNIDatos, str]]:
        """
        Intenta parsejar l'MRZ de 3 línies.
        Retorna (DNIDatos, raw_mrz_text) o None si no es troba.
        """
        lines = text.split("\n")
        mrz_lines: list[str] = []
        for line in lines:
            clean = line.strip().upper()
            if clean.startswith("ID") and len(clean) >= 30:
                mrz_lines.append(clean)
            elif mrz_lines and len(clean) >= 30:
                mrz_lines.append(clean)
            if len(mrz_lines) >= 3:
                break

        if len(mrz_lines) < 3:
            return None

        try:
            # Línia 1: DNI/NIE
            line1 = mrz_lines[0].replace(" ", "")
            doc_m = re.search(r"(\d{8}[A-Z]|[XYZ]\d{7}[A-Z])", line1)
            numero_documento = doc_m.group(1) if doc_m else None

            # Línia 2: dates + sexe + nacionalitat
            line2 = mrz_lines[1].replace(" ", "")
            raw_naix = f"{line2[4:6]}/{line2[2:4]}/{line2[0:2]}"
            raw_cad  = f"{line2[12:14]}/{line2[10:12]}/{line2[8:10]}"
            sexe_mrz = line2[7] if len(line2) > 7 else None
            nac = line2[15:18].replace("<", "").strip() if len(line2) >= 18 else None

            current_yy = date.today().year % 100

            def convert_yy(yy: int) -> str:
                return f"19{yy:02d}" if yy > current_yy + 10 else f"20{yy:02d}"

            def mrz_date_to_iso(ddmmyy: str) -> Optional[str]:
                parts = ddmmyy.split("/")
                if len(parts) != 3:
                    return None
                dd, mm, yy = parts
                yyyy = convert_yy(int(yy))
                return f"{yyyy}-{mm}-{dd}"

            # Línia 3: cognoms << nom
            line3 = re.sub(r" *< *", "<", mrz_lines[2]).replace(" ", "<")
            if "<<" in line3:
                parts = line3.split("<<", 1)
                cognoms_mrz = parts[0].replace("<", " ").strip()
                nom_mrz = parts[1].replace("<", " ").strip() if len(parts) > 1 else None
            else:
                cognoms_mrz = line3.replace("<", " ").strip()
                nom_mrz = None

            raw_mrz = "\n".join(mrz_lines[:3])

            data = DNIDatos(
                numero_documento=numero_documento,
                tipo_numero=_doc_type(numero_documento) if numero_documento else None,
                nombre=nom_mrz,
                apellidos=cognoms_mrz,
                nombre_completo=f"{nom_mrz} {cognoms_mrz}" if nom_mrz and cognoms_mrz else None,
                sexo="M" if sexe_mrz == "M" else "F" if sexe_mrz == "F" else None,
                nacionalidad=nac or "ESP",
                fecha_nacimiento=mrz_date_to_iso(raw_naix),
                fecha_caducidad=mrz_date_to_iso(raw_cad),
                mrz=MRZData(
                    raw=raw_mrz,
                    document_number=numero_documento,
                    surname=cognoms_mrz,
                    name=nom_mrz,
                    nationality=nac,
                    birth_date=f"{line2[0:6]}" if len(line2) >= 6 else None,
                    expiry_date=f"{line2[8:14]}" if len(line2) >= 14 else None,
                    sex=sexe_mrz,
                ),
            )
            return data, raw_mrz

        except Exception as e:
            log.debug("mrz_parse_error: %s", type(e).__name__)
            return None

    @staticmethod
    def parse_full_text(text: str) -> DNIDatos:
        """Phase 1: extracció raw per keywords del text complet."""
        data = DNIDatos()

        # Número de document
        doc_m = re.search(r"\b(\d{8}[A-Z]|[XYZ]\d{7}[A-Z])\b", text)
        if doc_m:
            data.numero_documento = doc_m.group(1)
            data.tipo_numero = _doc_type(data.numero_documento)

        FIELD_KEYWORDS = [
            "APELLIDOS", "COGNOMS", "NOMBRE", "NOM", "SEXO", "SEXE",
            "NACIONALIDAD", "NACIONALITAT", "FECHA", "DATA",
            "DOMICILIO", "DOMICILI", "LUGAR", "LLOC", "PADRE", "PARE",
            "MADRE", "MARE", "DNI", "EQUIPO", "EQUIP", "IDNUM",
        ]

        def read_field(lines, start):
            parts = []
            for j in range(start, len(lines)):
                lc = lines[j].strip()
                if not lc:
                    break
                lu = lc.upper()
                if j > start and any(kw in lu for kw in FIELD_KEYWORDS):
                    break
                parts.append(lc)
            return " ".join(parts)

        lines = text.split("\n")
        for i, line in enumerate(lines):
            lu = line.upper()

            if "APELLIDOS" in lu or "COGNOMS" in lu:
                if i + 1 < len(lines):
                    val = read_field(lines, i + 1)
                    # Filtrar tokens alfanumèrics mixtos (artifacts OCR)
                    tokens = [t for t in val.split()
                              if not (any(c.isdigit() for c in t) and any(c.isalpha() for c in t))]
                    data.apellidos = " ".join(tokens).strip() or None

            elif "NOMBRE" in lu or "NOM" in lu:
                if "PADRE" in lu or "PARE" in lu or "MADRE" in lu or "MARE" in lu:
                    continue
                if i + 1 < len(lines):
                    val = read_field(lines, i + 1)
                    # Eliminar token d'una sola lletra al principi (artifact OCR)
                    tokens = val.split()
                    if tokens and len(tokens[0]) == 1:
                        tokens = tokens[1:]
                    data.nombre = " ".join(tokens).strip() or None

            elif re.search(r"D[O0]MICILI[O0]", lu) or "DOMICILI" in lu:  # Més flexible amb OCR errors
                # Comprovar si l'adreça està a la MATEIXA línia (després de DOMICILIO/DOMICILI)
                same_line_match = re.search(r"D[O0]MICILI[O0]/D[O0]MICILI\s+(.+)$", lines[i], re.IGNORECASE)
                if not same_line_match:
                    same_line_match = re.search(r"D[O0]MICILI[O0]\s+(.+)$", lines[i], re.IGNORECASE)
                if not same_line_match:
                    same_line_match = re.search(r"DOMICILI\s+(.+)$", lines[i], re.IGNORECASE)

                adreca_lines = []

                if same_line_match:
                    # Adreça a la mateixa línia! Dividir per espais múltiples o números de 5 dígits
                    rest_of_line = same_line_match.group(1).strip()

                    # Intentar dividir per CP (5 dígits) o províncies
                    parts = re.split(r'(\d{5})', rest_of_line)
                    for part in parts:
                        part = part.strip()
                        if part:
                            adreca_lines.append(part)
                else:
                    # Llegir línies següents (comportament original)
                    for j in range(i + 1, min(i + 9, len(lines))):
                        nl = lines[j].strip()
                        # Aturar si línia buida
                        if not nl:
                            break
                        # Aturar si trobem keywords NO relacionades amb adreça
                        if any(kw in nl.upper() for kw in
                               ["FECHA", "DATA", "LUGAR", "LLOC", "PADRE", "PARE",
                                "MADRE", "MARE", "EQUIPO", "EQUIP", "HIJO", "FILL",
                                "IDNUM", "TEAM"]):
                            break
                        adreca_lines.append(nl)

                if adreca_lines:
                    # Províncies espanyoles completes
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
                    ]

                    # Primera línia: domicilio (carrer + número)
                    data.domicilio = adreca_lines[0]

                    # Separar carrer i número (ex: "C. ARTAIL 9" → calle="C. ARTAIL", numero="9")
                    if data.domicilio:
                        # Buscar número al final (amb/sense coma): "CRER. VENDRELL, 5" o "C. ARTAIL 9"
                        numero_match = re.search(r"[,\s]+(\d+[A-Z]?)\s*$", data.domicilio)
                        if numero_match:
                            data.numero = numero_match.group(1).strip()
                            data.calle = data.domicilio[:numero_match.start()].strip()
                        else:
                            # Si no hi ha número, tot és carrer
                            data.calle = data.domicilio

                    # Buscar codi postal (5 dígits) en TOTES les línies
                    for line in adreca_lines:
                        cp_match = re.search(r"\b(\d{5})\b", line)
                        if cp_match and not data.codigo_postal:
                            data.codigo_postal = cp_match.group(1)

                    # Detectar província (normalment a la darrera línia)
                    provincia_idx = None
                    for idx in range(len(adreca_lines) - 1, 0, -1):
                        line_upper = adreca_lines[idx].upper().strip()
                        if any(prov in line_upper for prov in PROVINCIES):
                            provincia_idx = idx
                            data.provincia = adreca_lines[idx].strip()
                            break

                    # Si hem trobat província, la línia anterior és població
                    if provincia_idx and provincia_idx > 0:
                        poblacio_line = adreca_lines[provincia_idx - 1]
                        # Treure codi postal si està davant
                        poblacio_line = re.sub(r"^\d{5}\s+", "", poblacio_line)
                        data.municipio = poblacio_line.strip() or None

                    # Si no hem trobat província, segona línia pot ser població
                    elif len(adreca_lines) > 1 and not data.municipio:
                        pob = adreca_lines[1]
                        pob = re.sub(r"^\d{5}\s+", "", pob)
                        data.municipio = pob.strip() or None

            elif ("FECHA" in lu and "NACIMIENTO" in lu) or ("DATA" in lu and "NAIXEMENT" in lu):
                if i + 1 < len(lines):
                    dm = re.search(r"(\d{2})[\s/](\d{2})[\s/](\d{4})", lines[i + 1])
                    if dm:
                        raw = f"{dm.group(1)}/{dm.group(2)}/{dm.group(3)}"
                        data.fecha_nacimiento = _validate_dmy(raw, 1900, date.today().year)

            elif ("NACIMIENTO" in lu or "NAIXEMENT" in lu) and \
                 "FECHA" not in lu and "DATA" not in lu and \
                 "LUGAR" not in lu and "LLOC" not in lu:
                if i + 1 < len(lines) and not data.fecha_nacimiento:
                    dm = re.search(r"(\d{2})[\s/](\d{2})[\s/](\d{4})", lines[i + 1])
                    if dm:
                        raw = f"{dm.group(1)}/{dm.group(2)}/{dm.group(3)}"
                        data.fecha_nacimiento = _validate_dmy(raw, 1900, date.today().year)

            elif "VALIDEZ" in lu or "VALIDESA" in lu:
                if i + 1 < len(lines):
                    dates = re.findall(r"(\d{2})[\s/](\d{2})[\s/](\d{4})", lines[i + 1])
                    if dates:
                        dd, mm, yyyy = dates[-1]
                        raw = f"{dd}/{mm}/{yyyy}"
                        data.fecha_caducidad = _validate_dmy(raw, 2000, 2060)

            elif "SEXO" in lu or "SEXE" in lu:
                if i + 1 < len(lines):
                    sv = lines[i + 1].strip().upper()
                    if len(sv) <= 6:
                        if sv in ("M", "H", "HOME", "HOMBRE"):
                            data.sexo = "M"
                        elif sv in ("F", "D", "V", "DONA", "MUJER"):
                            data.sexo = "F"

            elif "NACIONALIDAD" in lu or "NACIONALITAT" in lu:
                if i + 1 < len(lines):
                    nv = lines[i + 1].strip()
                    if len(nv) <= 3 and nv.isalpha():
                        data.nacionalidad = nv.upper()
                    elif "ESPA" in nv.upper():
                        data.nacionalidad = "ESP"

            elif ("LUGAR" in lu and "NACIMIENTO" in lu) or ("LLOC" in lu and "NAIXEMENT" in lu):
                if i + 1 < len(lines):
                    data.lugar_nacimiento = lines[i + 1].strip()

            elif "PADRE" in lu or "PARE" in lu:
                if i + 1 < len(lines):
                    data.nombre_padre = lines[i + 1].strip()

            elif "MADRE" in lu or "MARE" in lu:
                if i + 1 < len(lines):
                    data.nombre_madre = lines[i + 1].strip()

        # Nom complet
        if data.nombre and data.apellidos:
            data.nombre_completo = f"{data.nombre} {data.apellidos}"

        return data

    @staticmethod
    def parse(text: str) -> tuple[DNIDatos, Optional[str]]:
        """
        Parse principal: MRZ primer, complementat amb full_text.
        Retorna (DNIDatos, raw_mrz_text | None).
        """
        # 🔍 LOG TEMPORAL: Text OCR complet per debug (sempre si té MRZ = posterior)
        has_mrz = "IDESP" in text or "<<<" in text
        has_domicilio = "DOMICILIO" in text.upper() or "DOMICILI" in text.upper()
        if has_mrz:
            log.info("🔍 POSTERIOR OCR TEXT", extra={
                "text_length": len(text),
                "lines_count": len(text.split('\n')),
                "has_domicilio_keyword": has_domicilio,
                "text_preview": text[:800] if len(text) <= 800 else text[:800] + "...",
            })

        mrz_result = DNIParser.parse_mrz(text)

        if mrz_result:
            mrz_data, raw_mrz = mrz_result
            if mrz_data.numero_documento:
                # Complementar amb full_text
                ft_data = DNIParser.parse_full_text(text)

                # Copiar camps addicionals que MRZ no té
                for attr in ("domicilio", "calle", "numero", "municipio", "provincia", "lugar_nacimiento",
                             "nombre_padre", "nombre_madre"):
                    if getattr(ft_data, attr):
                        setattr(mrz_data, attr, getattr(ft_data, attr))

                # Preferir cognoms full_text si té espai (MRZ pot perdre < entre cognoms)
                if ft_data.apellidos and " " in ft_data.apellidos:
                    if not mrz_data.apellidos or " " not in mrz_data.apellidos:
                        mrz_data.apellidos = ft_data.apellidos
                        if mrz_data.nombre:
                            mrz_data.nombre_completo = f"{mrz_data.nombre} {mrz_data.apellidos}"

                return mrz_data, raw_mrz

        # Fallback: full_text
        return DNIParser.parse_full_text(text), None

    # ------------------------------------------------------------------
    # Phase 2 — Validació i construcció resposta
    # ------------------------------------------------------------------

    @staticmethod
    def validate_and_build_response(
        data: DNIDatos,
        raw_mrz: Optional[str],
        ocr_engine: str,
        ocr_confidence: float,
    ) -> DNIValidationResponse:
        """
        Phase 2: valida tots els camps, genera ValidationItems normalitzats.
        0 crèdits addicionals — Python pur.
        """
        errors: list[ValidationItem] = []
        alerts: list[ValidationItem] = []
        today = date.today()

        # --- Netejar noms ---
        for attr in ("nombre", "apellidos", "nombre_completo", "lugar_nacimiento",
                     "nombre_padre", "nombre_madre"):
            val = getattr(data, attr)
            if val and _has_ocr_noise(val):
                alerts.append(ValidationItem(
                    code="DNI_NAME_OCR_NOISE",
                    severity="warning",
                    field=attr,
                    message=f"El camp '{attr}' conté caràcters inesperats (possible soroll OCR).",
                    evidence=val,
                    suggested_fix="Verificar manualment el valor llegit.",
                ))
            setattr(data, attr, _clean_name(val))

        # Recalcular nom complet
        if data.nombre and data.apellidos:
            data.nombre_completo = f"{data.nombre} {data.apellidos}"

        # --- Validar número de document ---
        if not data.numero_documento:
            errors.append(ValidationItem(
                code="DNI_MISSING_FIELD",
                severity="critical",
                field="numero_documento",
                message="Número de document no detectat.",
                suggested_fix="Revisar la qualitat de la imatge o orientació.",
            ))
        elif not validate_doc_number(data.numero_documento):
            # Determinar el tipus de format
            tipo = _doc_type(data.numero_documento)
            if tipo:
                # Format correcte però lletra de control incorrecta
                expected = _expected_letter(data.numero_documento)
                errors.append(ValidationItem(
                    code="DNI_CHECKLETTER_MISMATCH",
                    severity="critical",
                    field="numero_documento",
                    message=f"Lletra de control incorrecta per {tipo}.",
                    evidence=f"Llegit: '{data.numero_documento[-1]}', esperat: '{expected}'",
                    suggested_fix="Possible error OCR en la lletra final. Verificar manualment.",
                ))
            else:
                errors.append(ValidationItem(
                    code="DNI_NUMBER_INVALID",
                    severity="critical",
                    field="numero_documento",
                    message=f"Format de document no reconegut: '{data.numero_documento}'.",
                    suggested_fix="Ha de ser DNI (8 dígits + lletra) o NIE (X/Y/Z + 7 dígits + lletra).",
                ))
            data.numero_documento = None  # descartar

        # --- Validar camps mínims absents ---
        camps_minims_absents = 0
        for camp in _CAMPS_MINIMS:
            if not getattr(data, camp):
                camps_minims_absents += 1
                if camp != "numero_documento":  # ja gestionat
                    errors.append(ValidationItem(
                        code="DNI_MISSING_FIELD",
                        severity="error",
                        field=camp,
                        message=f"Camp mínim no detectat: '{camp}'.",
                        suggested_fix="Verificar que la imatge mostra la cara correcta del document.",
                    ))

        # --- Validar dates ---
        if data.fecha_nacimiento:
            if data.fecha_nacimiento > today.isoformat():
                errors.append(ValidationItem(
                    code="DNI_BIRTHDATE_INVALID",
                    severity="critical",
                    field="fecha_nacimiento",
                    message="Data de naixement en el futur.",
                    evidence=data.fecha_nacimiento,
                ))
                data.fecha_nacimiento = None
            else:
                birth = date.fromisoformat(data.fecha_nacimiento)
                age = (today - birth).days // 365
                if age < 18:
                    alerts.append(ValidationItem(
                        code="DNI_UNDERAGE",
                        severity="warning",
                        field="fecha_nacimiento",
                        message=f"El titular és menor d'edat ({age} anys).",
                        evidence=data.fecha_nacimiento,
                        suggested_fix="Verificar si el tràmit requereix majoria d'edat.",
                    ))

        if data.fecha_caducidad:
            if data.fecha_caducidad < today.isoformat():
                errors.append(ValidationItem(
                    code="DNI_EXPIRED",
                    severity="error",
                    field="fecha_caducidad",
                    message=f"Document caducat ({data.fecha_caducidad}).",
                    evidence=data.fecha_caducidad,
                    suggested_fix="Sol·licitar renovació o document vigent.",
                ))

        # --- Coherència creuada MRZ vs text ---
        if data.mrz and data.mrz.document_number and data.numero_documento:
            if data.mrz.document_number != data.numero_documento:
                errors.append(ValidationItem(
                    code="DNI_MRZ_MISMATCH",
                    severity="critical",
                    field="numero_documento",
                    message="El número del document no coincideix entre el text i la zona MRZ.",
                    evidence=f"Text: '{data.numero_documento}', MRZ: '{data.mrz.document_number}'",
                    suggested_fix="Possible error OCR crític o document alterat. Verificació manual obligatòria.",
                ))

        # --- Nationalitat: format 2-3 lletres ---
        if data.nacionalidad and not re.match(r"^[A-Z]{2,3}$", data.nacionalidad):
            data.nacionalidad = None

        # --- Calcular confiança ---
        confianza = compute_confianza(alerts, errors, camps_minims_absents, ocr_confidence)

        # --- valido: cap critical i camps mínims presents ---
        has_critical = any(e.severity == "critical" for e in errors)
        has_minimums = bool(data.numero_documento and data.nombre and data.apellidos)
        valido = not has_critical and has_minimums

        message = "Document processat correctament." if valido else "Document amb errors que requereixen revisió."

        return DNIValidationResponse(
            valido=valido,
            confianza_global=confianza,
            datos=data,
            alertas=alerts,
            errores_detectados=errors,
            raw=RawOCR(ocr_engine=ocr_engine, ocr_confidence=round(ocr_confidence, 1)),
            meta=MetaInfo(success=valido, message=f"[{ocr_engine}] {message}"),
        )

    # ------------------------------------------------------------------
    # Decisió Tesseract → Vision
    # ------------------------------------------------------------------

    @staticmethod
    def should_fallback_to_vision(data: DNIDatos, tess_confidence: float, text: str = "") -> tuple[bool, str]:
        """
        Decideix si cal Vision. Treballa sobre DNIDatos de Phase 1.
        """
        if not data.numero_documento or not validate_doc_number(data.numero_documento):
            return True, "document_invalid_o_absent"
        if not data.nombre:
            return True, "nom_absent"
        if not data.apellidos:
            return True, "apellidos_absents"

        # Si el text sembla un posterior (conté keywords) però no té adreça, fer fallback
        text_upper = text.upper()
        posterior_keywords = ["DOMICILIO", "DOMICILI", "EQUIPO", "EQUIP", "HIJO", "FILL", "PADRE", "PARE", "MADRE", "MARE", "LUGAR DE NACIMIENTO"]
        sembla_posterior = any(kw in text_upper for kw in posterior_keywords)
        no_te_adreca = not data.domicilio and not data.municipio and not data.provincia

        if sembla_posterior and no_te_adreca and tess_confidence < 70:
            return True, "posterior_sense_adreca"

        # Si text molt curt (< 200 chars) amb MRZ però sense camps frontal típics, és posterior mal llegit
        frontal_keywords = ["APELLIDOS", "COGNOMS", "SEXO", "SEXE", "NACIONALIDAD", "NACIONALITAT"]
        te_frontal = any(kw in text_upper for kw in frontal_keywords)
        te_mrz = "IDESP" in text or "<<<" in text

        if te_mrz and not te_frontal and len(text) < 250 and tess_confidence < 70:
            return True, "mrz_sols_posterior_mal_llegit"

        # Estimació de qualitat ràpida: comptar camps principals
        principals = [data.numero_documento, data.nombre, data.apellidos,
                      data.fecha_nacimiento, data.fecha_caducidad]
        score = sum(20 for v in principals if v)
        if score < 60:
            return True, f"qualitat_baixa:{score}"
        if tess_confidence < 35.0:
            return True, f"confidence_baixa:{tess_confidence:.0f}"
        return False, "tesseract_acceptat"


# ---------------------------------------------------------------------------
# Helper intern
# ---------------------------------------------------------------------------

def _expected_letter(doc: str) -> str:
    doc = doc.upper()
    if doc[0] in "XYZ":
        prefix = {"X": "0", "Y": "1", "Z": "2"}[doc[0]]
        number = int(prefix + doc[1:8])
    else:
        number = int(doc[:8])
    return DNI_LETTERS[number % 23]


# Singleton
dni_parser = DNIParser()
