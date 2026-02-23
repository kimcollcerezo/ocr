"""
Parser expert per Permís de Circulació (DGT / Directiva EU 1999/37/CE)

Arquitectura de cost zero (1 sol crèdit Vision per document):
  Phase 1 — Extracció raw: regex sobre text OCR
  Phase 2 — Validació i correcció: lògica Python pura (0 crèdits addicionals)

TODO (futur): si confianza_global < 85 → cridar Claude text-only per refinament
"""
import re
import logging
from datetime import date
from typing import Optional
from app.models.permis_response import PermisExtracted, PermisValidationResponse
from app.models.base_response import ValidationItem, RawOCR, MetaInfo, compute_confianza

log = logging.getLogger("ocr.parser")

# ---------------------------------------------------------------------------
# Taules de validació
# ---------------------------------------------------------------------------

# Lletra de control DNI/NIE  (taula oficial BNE)
DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

# Lletres vàlides en matrícula espanyola moderna (sense vocals A E I O U, ni Ñ Q)
MATRICULA_VALID_LETTERS = set("BCDFGHJKLMNPRSTVWXYZ")

# Transliteració per al dígit de control VIN (NHTSA)
_VIN_TRANS = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5,          "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
_VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

# Marques conegudes
MARQUES_CONEGUDES = [
    "SEAT", "VOLKSWAGEN", "VW", "RENAULT", "PEUGEOT", "CITROEN", "CITROËN",
    "FORD", "OPEL", "FIAT", "AUDI", "BMW", "MERCEDES", "MERCEDES-BENZ",
    "TOYOTA", "NISSAN", "HYUNDAI", "KIA", "MAZDA", "HONDA", "SUZUKI",
    "DACIA", "SKODA", "VOLVO", "LAND ROVER", "JEEP", "MITSUBISHI",
    "SUBARU", "LEXUS", "ALFA ROMEO", "LANCIA", "PORSCHE", "MINI",
    "SMART", "TESLA", "POLESTAR", "CUPRA",
]

# Models per marca (per validació creuada)
MODELS_PER_MARCA: dict[str, list[str]] = {
    "TOYOTA": ["YARIS", "COROLLA", "AURIS", "AVENSIS", "RAV4", "PRIUS", "HILUX", "C-HR", "CAMRY"],
    "SEAT":   ["IBIZA", "LEON", "ARONA", "ATECA", "TARRACO", "ALHAMBRA", "MII", "TOLEDO"],
    "VOLKSWAGEN": ["GOLF", "POLO", "PASSAT", "TIGUAN", "TOUAREG", "T-ROC", "ID.3", "ID.4"],
    "RENAULT": ["CLIO", "MEGANE", "CAPTUR", "KADJAR", "SCENIC", "ZOE", "ARKANA"],
    "PEUGEOT": ["208", "308", "3008", "5008", "107", "206", "207", "407", "508"],
    "FORD":   ["FIESTA", "FOCUS", "MONDEO", "KUGA", "PUMA", "MUSTANG", "TRANSIT"],
    "BMW":    ["SERIE 1", "SERIE 2", "SERIE 3", "SERIE 5", "X1", "X3", "X5"],
    "AUDI":   ["A1", "A3", "A4", "A6", "Q2", "Q3", "Q5", "Q7", "TT"],
    "MERCEDES": ["CLASE A", "CLASE B", "CLASE C", "CLASE E", "GLA", "GLB", "GLC"],
    "KIA":    ["PICANTO", "RIO", "CEED", "SPORTAGE", "SORENTO", "NIRO", "STONIC"],
    "HYUNDAI": ["I10", "I20", "I30", "TUCSON", "SANTA FE", "IONIQ", "KONA"],
    "HONDA":  ["JAZZ", "CIVIC", "CR-V", "HR-V", "ACCORD"],
    "NISSAN": ["MICRA", "JUKE", "QASHQAI", "X-TRAIL", "LEAF", "NAVARA"],
    "OPEL":   ["CORSA", "ASTRA", "INSIGNIA", "MOKKA", "CROSSLAND", "GRANDLAND"],
    "DACIA":  ["SANDERO", "DUSTER", "LOGAN", "SPRING", "JOGGER"],
    "SKODA":  ["FABIA", "OCTAVIA", "SUPERB", "KODIAQ", "KAROQ", "SCALA"],
    "FIAT":   ["PUNTO", "PANDA", "500", "TIPO", "BRAVO", "DUCATO"],
}


# ---------------------------------------------------------------------------
# Helpers de validació
# ---------------------------------------------------------------------------

def _to_iso(text: str) -> Optional[str]:
    """Converteix DD-MM-YYYY / DD/MM/YYYY a ISO YYYY-MM-DD. Retorna None si invàlid."""
    m = re.search(r"(\d{2})[-/.](\d{2})[-/.](\d{4})", text)
    if not m:
        return None
    dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= dd <= 31 and 1 <= mm <= 12 and 1970 <= yyyy <= 2050):
        return None
    return f"{yyyy}-{mm:02d}-{dd:02d}"


def _validate_matricula(m: str) -> list[str]:
    """Retorna llista d'errors (buida = vàlida)."""
    errors = []
    if not re.match(r"^\d{4}[A-Z]{3}$", m):
        errors.append(f"Format invàlid '{m}' (esperat: 4 dígits + 3 lletres)")
        return errors
    bad = [c for c in m[4:] if c not in MATRICULA_VALID_LETTERS]
    if bad:
        errors.append(f"Lletres no permeses en matrícula: {bad} (vocals i Q excloses)")
    return errors


def _correct_matricula(raw: str) -> str:
    """Aplica correccions OCR típiques a la matrícula."""
    raw = re.sub(r"[\s\-]", "", raw.upper())
    if len(raw) != 7:
        return raw
    # Part numèrica: O→0, I→1, S→5, B→8, Z→2, G→6
    nums = raw[:4].translate(str.maketrans("OISBZG", "015826"))
    # Part de lletres: 0→O, 1→I→filtrar després, 8→B
    lets = raw[4:].translate(str.maketrans("081", "OBI"))
    return nums + lets


def _validate_vin(vin: str) -> tuple[list[str], list[str]]:
    """Retorna (errors_crítics, alertes)."""
    errors, alerts = [], []
    vin = vin.upper().replace(" ", "").replace("-", "")

    if len(vin) != 17:
        errors.append(f"VIN ha de tenir 17 caràcters (té {len(vin)}): '{vin}'")
        return errors, alerts

    invalid = [c for c in vin if c in "IOQ"]
    if invalid:
        errors.append(f"VIN conté caràcters prohibits (I/O/Q): {set(invalid)}")

    if not re.match(r"^[A-HJ-NPR-Z0-9]{17}$", vin):
        errors.append("VIN conté caràcters no alfanumèrics vàlids")
        return errors, alerts

    # Dígit de control (posició 9, índex 8) — NHTSA
    # Nota: vehicles EU no sempre segueixen NHTSA, és alerta, no error
    total = sum(
        (int(c) if c.isdigit() else _VIN_TRANS.get(c, 0)) * _VIN_WEIGHTS[i]
        for i, c in enumerate(vin)
    )
    remainder = total % 11
    expected = "X" if remainder == 10 else str(remainder)
    if vin[8] != expected:
        alerts.append(
            f"Dígit de control VIN no coincideix (posició 9: trobat '{vin[8]}', esperat '{expected}'). "
            f"Normal en vehicles EU/asiàtics."
        )

    return errors, alerts


def _validate_nif(nif: str) -> tuple[bool, list[str]]:
    """Valida DNI, NIE o CIF. Retorna (vàlid, errors)."""
    nif = nif.upper().strip()

    # DNI: 8 dígits + lletra
    if re.match(r"^\d{8}[A-Z]$", nif):
        expected = DNI_LETTERS[int(nif[:8]) % 23]
        if nif[-1] != expected:
            return False, [f"Lletra de control DNI incorrecta: '{nif[-1]}' (esperada '{expected}')"]
        return True, []

    # NIE: X/Y/Z + 7 dígits + lletra
    if re.match(r"^[XYZ]\d{7}[A-Z]$", nif):
        prefix = {"X": "0", "Y": "1", "Z": "2"}[nif[0]]
        expected = DNI_LETTERS[int(prefix + nif[1:8]) % 23]
        if nif[-1] != expected:
            return False, [f"Lletra de control NIE incorrecta: '{nif[-1]}' (esperada '{expected}')"]
        return True, []

    # CIF: lletra + 7 dígits + lletra o dígit
    if re.match(r"^[ABCDEFGHJKLMNPQRSUVW]\d{7}[A-J0-9]$", nif):
        return True, []  # validació simplificada del format

    return False, [f"Format NIF/DNI/NIE/CIF no reconegut: '{nif}'"]


def _correct_ocr_nif(raw: str) -> str:
    """Correccions OCR típiques en DNI/NIE."""
    raw = raw.upper().strip().replace(" ", "").replace("-", "")
    # En la part numèrica: O→0, I→1, S→5, B→8, Z→2
    if raw and raw[0].isdigit():  # DNI
        digits = raw[:8].translate(str.maketrans("OISBZ", "01582"))
        return digits + raw[8:]
    if raw and raw[0] in "XYZ":  # NIE
        digits = raw[1:8].translate(str.maketrans("OISBZ", "01582"))
        return raw[0] + digits + raw[8:]
    return raw


def _inferir_tipus_vehicle(categoria: str) -> str:
    """Infereix tipus de vehicle llegible a partir de la categoria EU."""
    categoria = categoria.upper().strip()

    # Categories vehicles de motor (Directiva 2007/46/CE)
    tipus_map = {
        "M1": "Turisme",              # ≤ 9 places (incl. conductor)
        "M2": "Autobús lleuger",      # > 9 places, ≤ 5000 kg
        "M3": "Autobús pesant",       # > 9 places, > 5000 kg
        "N1": "Furgoneta",            # mercaderies ≤ 3500 kg
        "N2": "Camió mitjà",          # 3500 kg < pes ≤ 12000 kg
        "N3": "Camió pesant",         # > 12000 kg
        "L1E": "Ciclomotor",          # ≤ 50 cc
        "L2E": "Ciclomotor 3 rodes",
        "L3E": "Motocicleta",         # > 50 cc, 2 rodes
        "L4E": "Motocicleta sidecar",
        "L5E": "Tricicle motor",
        "L6E": "Quadricicle lleuger",
        "L7E": "Quadricicle pesant",
    }

    return tipus_map.get(categoria, categoria)


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

class PermisParser:
    """
    Sistema expert de doble passada per Permís de Circulació.

    COST: 1 sol crèdit Vision per document.
    Phase 1 i Phase 2 son Python pur (0 crèdits addicionals).

    TODO: si confianza_global < 85 → Claude text-only per refinament (1 crèdit text)
    """

    @staticmethod
    def _next_val(lines: list[str], idx: int, skip: int = 1) -> Optional[str]:
        """Retorna la primera línia no buida a partir de idx+skip."""
        for j in range(idx + skip, min(idx + skip + 4, len(lines))):
            v = lines[j].strip()
            if v:
                return v
        return None

    # ------------------------------------------------------------------
    # PHASE 1 — Extracció raw
    # ------------------------------------------------------------------

    @staticmethod
    def parse(text: str) -> PermisExtracted:
        """
        Phase 1: extreu valors tal com apareixen al text OCR.
        Aplica correccions OCR bàsiques però NO valida coherència creuada.
        """
        data = PermisExtracted()
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # --- MATRÍCULA (camp A) ---
        for pattern in [r"\b(\d{4}[A-Z]{3})\b", r"\b([A-Z]{1,2}\d{4}[A-Z]{2})\b"]:
            m = re.search(pattern, text)
            if m:
                data.matricula = _correct_matricula(m.group(1))
                break

        # --- VIN / BASTIDOR (camp E) ---
        vin_m = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", text)
        if vin_m:
            data.numero_bastidor = vin_m.group(1).upper()

        # --- Recorregut per camps etiquetats ---
        i = 0
        while i < len(lines):
            lu = lines[i].upper()

            # D.1 — Marca
            if re.search(r"\bD\.?\s*1\b", lu):
                v = PermisParser._next_val(lines, i)
                if v:
                    for marca in MARQUES_CONEGUDES:
                        if marca in v.upper():
                            data.marca = marca
                            break

            # D.2 — Variant/versió (codi tècnic, sol contenir '/')
            if re.search(r"\bD\.?\s*2\b", lu):
                v = PermisParser._next_val(lines, i)
                if v and re.search(r"[/(]", v):
                    data.variante_version = v.strip()

            # D.3 — Model comercial (nom llegible, sense '/' ni '*')
            if re.search(r"\bD\.?\s*3\b", lu):
                for j in range(i + 1, min(i + 6, len(lines))):
                    candidate = lines[j].strip()
                    if candidate and not re.search(r"[/(*]", candidate):
                        if re.match(r"^[A-Za-z0-9 \-\.]{3,40}$", candidate):
                            if data.marca and data.marca.upper() in candidate.upper():
                                data.modelo = candidate
                                break
                            elif not data.modelo:
                                data.modelo = candidate

            # P.1 — Cilindrada (cc)
            if re.search(r"\bP\.?\s*1\b", lu):
                v = PermisParser._next_val(lines, i)
                if v:
                    # Saltar sub-etiqueta (1.2) si apareix
                    if re.match(r"^\(?\d\.\d\)?$", v):
                        v = PermisParser._next_val(lines, i + 1) or v
                    nm = re.match(r"^(\d{3,5})$", v)
                    if nm:
                        val = int(nm.group(1))
                        if 50 <= val <= 10000:
                            data.cilindrada_cc = val

            # P.2 — Potència (kW) - Variants: P.2, P2, P 2, P. 2
            if re.search(r"\bP\.?\s*2\b", lu) or re.search(r"\bP\s*\.?\s*2\b", lu):
                v = PermisParser._next_val(lines, i)
                if v:
                    # Acceptar formats: "92", "92.0", "92 kW", "92.0 kW"
                    nm = re.match(r"^(\d+\.?\d*)\s*(kW|KW)?$", v, re.IGNORECASE)
                    if nm:
                        val = float(nm.group(1))
                        if 1 <= val <= 1000:  # Rang plausible kW
                            data.potencia_kw = val

            # Potència en CV (cavalls de vapor) - Fallback si no hi ha kW
            if not data.potencia_kw and re.search(r"\b(CV|HP)\b", lu, re.IGNORECASE):
                v = PermisParser._next_val(lines, i)
                if v:
                    nm = re.match(r"^(\d+\.?\d*)\s*(CV|HP)?$", v, re.IGNORECASE)
                    if nm:
                        cv = float(nm.group(1))
                        if 1 <= cv <= 1500:
                            # Convertir CV a kW (1 CV ≈ 0.7355 kW)
                            data.potencia_kw = round(cv * 0.7355, 1)

            # P.3 — Combustible
            if re.search(r"\bP\.?\s*3\b", lu):
                v = PermisParser._next_val(lines, i)
                if v and re.match(r"^[A-ZÁÉÍÓÚÜ/ ]{3,20}$", v.upper()):
                    data.combustible = v.upper().strip()

            # V.7 — Emissions CO2 (g/km) - Variants: V.7, V7, V 7, V. 7
            if re.search(r"\bV\.?\s*7\b", lu) or re.search(r"\bV\s*\.?\s*7\b", lu):
                v = PermisParser._next_val(lines, i)
                if v:
                    # Acceptar formats: "120", "120.5", "120 g/km"
                    nm = re.match(r"^(\d+\.?\d*)\s*(g/km|g\/km)?$", v, re.IGNORECASE)
                    if nm:
                        val = float(nm.group(1))
                        if 0 <= val <= 999:
                            data.emissions_co2 = val

            # F.1 — Massa màxima tècnica (kg)
            if re.search(r"\bF\.?\s*1\b", lu):
                v = PermisParser._next_val(lines, i)
                if v:
                    # Pot tenir etiqueta "B" intercalada (camp B del form)
                    if v.upper() == "B":
                        v = PermisParser._next_val(lines, i, skip=2)
                    if v:
                        nm = re.match(r"^(\d{3,5})$", v)
                        if nm:
                            val = int(nm.group(1))
                            if 500 <= val <= 50000:
                                data.masa_maxima = val

            # G — Massa en ordre de marxa (kg)
            if re.match(r"^G\s*$", lu) or re.search(r"\bG\s+I\b", lu):
                v = PermisParser._next_val(lines, i)
                # Pot portar "I" com a sub-etiqueta
                if v and v.upper() in ("I", "1"):
                    v = PermisParser._next_val(lines, i, skip=2)
                if v:
                    nm = re.match(r"^(\d{3,5})$", v)
                    if nm:
                        val = int(nm.group(1))
                        if 300 <= val <= 20000:
                            data.masa_orden_marcha = val

            # S.1 — Places assegudes
            if re.search(r"\bS\.?\s*1\b", lu):
                v = PermisParser._next_val(lines, i)
                if v:
                    nm = re.match(r"^(\d{1,2})$", v)
                    if nm:
                        val = int(nm.group(1))
                        if 1 <= val <= 100:
                            data.plazas = val

            # C.1.1 — Cognoms titular
            if re.search(r"\bC\.?\s*1\.?\s*1\b", lu):
                v = PermisParser._next_val(lines, i)
                if v and not re.search(r"\bC\.?\s*1\b", v.upper()):
                    _cognoms = v.strip()
                    # Guardem temporalment per construir titular_nombre al final
                    data.__dict__["_cognoms"] = _cognoms

            # C.1.2 — Nom titular
            if re.search(r"\bC\.?\s*1\.?\s*2\b", lu):
                v = PermisParser._next_val(lines, i)
                if v and not re.search(r"\bC\.?\s*1\b", v.upper()):
                    data.__dict__["_nom"] = v.strip()

            # C.1.3 — NIF titular (si és DNI/NIE)
            if re.search(r"\bC\.?\s*1\.?\s*3\b", lu):
                v = PermisParser._next_val(lines, i)
                if v:
                    corrected = _correct_ocr_nif(v)
                    if re.match(r"^(\d{8}[A-Z]|[XYZ]\d{7}[A-Z])$", corrected):
                        data.titular_nif = corrected

            # Pròxima ITV
            if "PROXIMA ITV" in lu or "PRÓXIMA ITV" in lu:
                d = _to_iso(lines[i])
                if d:
                    data.proxima_itv = d

            # OBSERVACIONES
            if "OBSERVACION" in lu or "OBSERVACIÓ" in lu:
                obs_parts = []
                for j in range(i + 1, min(i + 6, len(lines))):
                    obs_parts.append(lines[j].strip())
                if obs_parts:
                    data.observaciones = " ".join(obs_parts)

            # Provincia (RIOJA, BARCELONA, etc. apareix sol en algunes posicions)
            if not data.provincia:
                prov_m = re.match(
                    r"^(BARCELONA|MADRID|RIOJA \(LA\)|LA RIOJA|TARRAGONA|GIRONA|LLEIDA|"
                    r"VALENCIA|ALICANTE|SEVILLA|MALAGA|CADIZ|ZARAGOZA|BILBAO|"
                    r"VIZCAYA|GUIPUZCOA|NAVARRA|MURCIA|ASTURIAS|CANTABRIA)$",
                    lu
                )
                if prov_m:
                    data.provincia = lines[i].strip()

            i += 1

        # Construir titular_nombre des dels fragments
        nom = data.__dict__.pop("_nom", None)
        cognoms = data.__dict__.pop("_cognoms", None)
        if nom and cognoms:
            data.titular_nombre = f"{nom} {cognoms}"
        elif cognoms:
            data.titular_nombre = cognoms
        elif nom:
            data.titular_nombre = nom

        # Dates: treure totes les vàlides del text
        dates_iso = [
            _to_iso(d)
            for d in re.findall(r"\d{2}[-/.]\d{2}[-/.]\d{4}", text)
        ]
        dates_iso = [d for d in dates_iso if d]

        if dates_iso and not data.fecha_matriculacion:
            data.fecha_matriculacion = dates_iso[0]

        # Fallback marca per llista
        if not data.marca:
            for marca in MARQUES_CONEGUDES:
                if re.search(rf"\b{re.escape(marca)}\b", text, re.IGNORECASE):
                    data.marca = marca
                    break

        # Fallback model: línia "MARCA MODEL" sense caràcters especials
        if not data.modelo and data.marca:
            for line in lines:
                if data.marca.upper() in line.upper() and len(line) > len(data.marca) + 2:
                    if not re.search(r"[/()*]", line):
                        data.modelo = line.strip()
                        break

        # Categoria inferida (M1 = turisme ≤8 places)
        if not data.categoria and data.plazas:
            if data.plazas <= 9:
                data.categoria = "M1"
            elif data.plazas <= 16:
                data.categoria = "M2"

        # Tipus vehicle descriptiu (inferit de categoria)
        if data.categoria:
            data.tipo_vehiculo = _inferir_tipus_vehicle(data.categoria)

        # Servei per defecte (si no apareix explícitament)
        if not data.servicio:
            data.servicio = "PARTICULAR"

        return data

    # ------------------------------------------------------------------
    # PHASE 2 — Validació i correcció creuada
    # ------------------------------------------------------------------

    @staticmethod
    def validate_and_build_response(
        data: PermisExtracted,
        ocr_engine: str,
        ocr_confidence: float,
    ) -> PermisValidationResponse:
        """
        Phase 2: valida tots els camps amb ValidationItem normalitzats.
        Fórmula confiança: contracte unificat v1.
        Cap crida a API externa — 0 crèdits addicionals.
        """
        errors: list[ValidationItem] = []
        alerts: list[ValidationItem] = []

        # Camps mínims permís
        _CAMPS_MINIMS = ["matricula", "numero_bastidor", "marca", "modelo", "titular_nombre"]
        camps_minims_absents = sum(1 for c in _CAMPS_MINIMS if not getattr(data, c))

        # --- Matrícula ---
        if data.matricula:
            mat_errors = _validate_matricula(data.matricula)
            for msg in mat_errors:
                errors.append(ValidationItem(
                    code="VEH_PLATE_INVALID",
                    severity="critical",
                    field="matricula",
                    message=msg,
                    evidence=data.matricula,
                    suggested_fix="Verificar format: 4 dígits + 3 consonants (sense vocals ni Q).",
                ))
        else:
            errors.append(ValidationItem(
                code="VEH_MISSING_FIELD",
                severity="critical",
                field="matricula",
                message="Matrícula no detectada.",
                suggested_fix="Verificar qualitat de la imatge o orientació.",
            ))

        # --- VIN ---
        if data.numero_bastidor:
            vin_errors_raw, vin_alerts_raw = _validate_vin(data.numero_bastidor)
            for msg in vin_errors_raw:
                code = "VEH_VIN_INVALID_CHARS" if "caràcters" in msg else "VEH_VIN_INVALID_LENGTH"
                errors.append(ValidationItem(
                    code=code,
                    severity="critical",
                    field="numero_bastidor",
                    message=msg,
                    evidence=data.numero_bastidor,
                ))
            for msg in vin_alerts_raw:
                alerts.append(ValidationItem(
                    code="VEH_VIN_CHECKDIGIT",
                    severity="warning",
                    field="numero_bastidor",
                    message=msg,
                    evidence=data.numero_bastidor,
                ))
        else:
            alerts.append(ValidationItem(
                code="VEH_MISSING_FIELD",
                severity="error",
                field="numero_bastidor",
                message="Número de bastidor (VIN) no detectat.",
            ))

        # --- NIF titular ---
        if data.titular_nif:
            nif_valid, nif_errors_raw = _validate_nif(data.titular_nif)
            if not nif_valid:
                for msg in nif_errors_raw:
                    errors.append(ValidationItem(
                        code="VEH_OWNER_ID_INVALID",
                        severity="error",
                        field="titular_nif",
                        message=msg,
                        evidence=data.titular_nif,
                        suggested_fix="Verificar NIF/CIF del titular manualment.",
                    ))

        # --- Dates ---
        today_iso = date.today().isoformat()
        if data.fecha_matriculacion:
            if data.fecha_matriculacion < "1970-01-01" or data.fecha_matriculacion > today_iso:
                errors.append(ValidationItem(
                    code="VEH_DATES_INCONSISTENT",
                    severity="error",
                    field="fecha_matriculacion",
                    message=f"Data de matriculació fora de rang.",
                    evidence=data.fecha_matriculacion,
                ))

        if data.fecha_primera_matriculacion and data.fecha_matriculacion:
            if data.fecha_primera_matriculacion > data.fecha_matriculacion:
                alerts.append(ValidationItem(
                    code="VEH_DATES_INCONSISTENT",
                    severity="warning",
                    field="fecha_primera_matriculacion",
                    message="Data 1a matriculació posterior a data del permís.",
                    evidence=f"1a: {data.fecha_primera_matriculacion}, permís: {data.fecha_matriculacion}",
                ))

        if data.fecha_expedicion and data.fecha_matriculacion:
            if data.fecha_expedicion < data.fecha_matriculacion:
                alerts.append(ValidationItem(
                    code="VEH_DATES_INCONSISTENT",
                    severity="warning",
                    field="fecha_expedicion",
                    message="Data d'expedició anterior a la matriculació.",
                    evidence=f"Expedició: {data.fecha_expedicion}, Matriculació: {data.fecha_matriculacion}",
                ))

        # --- Coherència marca / model ---
        if data.marca and data.modelo:
            known_models = MODELS_PER_MARCA.get(data.marca.upper(), [])
            if known_models:
                if not any(m in data.modelo.upper() for m in known_models):
                    alerts.append(ValidationItem(
                        code="VEH_OCR_SUSPECT",
                        severity="warning",
                        field="modelo",
                        message=f"Model '{data.modelo}' no figura a la llista coneguda per {data.marca}.",
                        evidence=data.modelo,
                        suggested_fix="Model poc comú o possible error OCR. Verificar manualment.",
                    ))

        # --- Coherència física cilindrada / potència ---
        if data.cilindrada_cc and data.potencia_kw:
            ratio = data.potencia_kw / data.cilindrada_cc
            if not (0.02 <= ratio <= 0.20):
                alerts.append(ValidationItem(
                    code="VEH_OCR_SUSPECT",
                    severity="warning",
                    field="potencia_kw",
                    message=f"Relació potència/cilindrada inusual ({ratio:.3f} kW/cc).",
                    evidence=f"{data.potencia_kw} kW / {data.cilindrada_cc} cc",
                ))

        # --- Potència fiscal calculada ---
        if data.potencia_kw and not data.potencia_fiscal:
            data.potencia_fiscal = round(data.potencia_kw * 1.36, 1)

        # --- Massa màxima vs massa en ordre de marxa ---
        if data.masa_maxima and data.masa_orden_marcha:
            if data.masa_orden_marcha > data.masa_maxima:
                errors.append(ValidationItem(
                    code="VEH_DATES_INCONSISTENT",
                    severity="error",
                    field="masa_orden_marcha",
                    message=f"Massa en ordre de marxa ({data.masa_orden_marcha} kg) superior a massa màxima ({data.masa_maxima} kg).",
                    evidence=f"{data.masa_orden_marcha} > {data.masa_maxima}",
                ))

        # --- Titular absent ---
        if not data.titular_nombre:
            alerts.append(ValidationItem(
                code="VEH_MISSING_FIELD",
                severity="error",
                field="titular_nombre",
                message="Nom del titular no detectat.",
            ))

        # --- Marca absent ---
        if not data.marca:
            errors.append(ValidationItem(
                code="VEH_MISSING_FIELD",
                severity="critical",
                field="marca",
                message="Marca del vehicle no detectada.",
            ))

        # --- Confiança — fórmula contracte v1 ---
        confianza = compute_confianza(alerts, errors, camps_minims_absents, ocr_confidence)

        # valido: cap critical + camps mínims presents
        has_critical = any(e.severity == "critical" for e in errors)
        valido = not has_critical and bool(data.matricula) and bool(data.marca)

        message = "Permís processat correctament." if valido else "Permís amb errors que requereixen revisió."

        return PermisValidationResponse(
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
    def should_fallback_to_vision(data: PermisExtracted, tess_confidence: float) -> tuple[bool, str]:
        """
        Per permís, Tesseract rarament funciona (soroll gràfic).
        Camps mínims necessaris: matrícula + marca.
        """
        if not data.matricula:
            return True, "matricula_absent"
        if not data.marca:
            return True, "marca_absent"
        if tess_confidence < 50.0:
            return True, f"confidence_baixa:{tess_confidence:.0f}"
        # Validar matrícula extreta
        if _validate_matricula(data.matricula):
            return True, "matricula_invalida"
        return False, "tesseract_acceptat"


# Singleton
permis_parser = PermisParser()
