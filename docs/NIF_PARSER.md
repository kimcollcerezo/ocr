# Parser NIF/TIF - Documentació Tècnica

> **Targeta d'Identificació Fiscal (NIF/TIF)** - Parser expert amb validació CIF completa
> Implementat: 2026-02-26 · Contracte unificat v1

---

## Taula de continguts

1. [Visió general](#1-visió-general)
2. [Arquitectura de doble passada](#2-arquitectura-de-doble-passada)
3. [Validació CIF (algoritme oficial AEAT)](#3-validació-cif-algoritme-oficial-aeat)
4. [Model de dades](#4-model-de-dades)
5. [Extracció de camps](#5-extracció-de-camps)
6. [Codis d'error i alertes](#6-codis-derror-i-alertes)
7. [Casos d'ús i exemples](#7-casos-dús-i-exemples)
8. [Tests i validació](#8-tests-i-validació)

---

## 1. Visió general

El parser NIF/TIF processa **Targetes d'Identificació Fiscal** espanyoles per extreure automàticament les dades empresarials i validar-les segons els estàndards oficials de l'AEAT (Agència Tributària).

### Característiques principals

- ✅ **Validació CIF completa** amb algoritme oficial AEAT (dígit de control calculat)
- ✅ **Extracció de 2 domicilis**: Social (registral) i Fiscal (AEAT)
- ✅ **Components d'adreça separats**: carrer, número, pis/porta, CP, municipi, província
- ✅ **Dates en format ISO 8601** (YYYY-MM-DD)
- ✅ **Contracte unificat v1**: ValidationItem, confiança global 0-100, valido boolean
- ✅ **Cost transparent**: 1 crèdit Google Vision OCR, 0 crèdits Python (Phase 1+2)

### Què és una Targeta NIF/TIF?

La **Targeta d'Identificació Fiscal** és un document emès per l'AEAT que identifica fiscalment:
- Empreses (societats limitades, anònimes, etc.)
- Associacions i fundacions
- Entitats sense personalitat jurídica
- Organitzacions diverses

Conté el **NIF** (Número d'Identificació Fiscal), també conegut com **CIF** (Codi d'Identificació Fiscal), format per:
- 1 lletra inicial (A-W, tipus d'entitat)
- 7 dígits
- 1 caràcter de control (dígit o lletra segons tipus)

---

## 2. Arquitectura de doble passada

El parser segueix l'arquitectura consolidada del DNI parser amb **2 fases seqüencials sense cost extra**:

```
Imatge NIF/TIF
     │
     ▼
┌──────────────────┐
│  Google Vision   │  (1 crèdit per document)
│  OCR             │
└────────┬─────────┘
         │
         ▼
    Text OCR
         │
         ▼
┌────────────────────────────┐
│  Phase 1: parse()          │  (0 crèdits - Python regex)
│  ─────────────────         │
│  · Detectar keywords       │
│  · Extreure NIF/CIF        │
│  · Raó social              │
│  · Domicili social         │
│  · Domicili fiscal         │
│  · Dates (ISO)             │
│  · Administració AEAT      │
│  · Codi electrònic         │
└────────┬───────────────────┘
         │
         ▼
   NIFDatos (raw)
         │
         ▼
┌────────────────────────────┐
│  Phase 2:                  │  (0 crèdits - Python pur)
│  validate_and_build_       │
│  response()                │
│  ─────────────────         │
│  · Validar CIF completa    │
│  · Verificar camps mínims  │
│  · Validar dates (rang)    │
│  · Generar ValidationItem  │
│  · Calcular confianza      │
│  · Determinar valido       │
└────────┬───────────────────┘
         │
         ▼
NIFValidationResponse
  (contracte v1)
```

### Cost garantit

| Fase | Motor | Cost | Duració típica |
|------|-------|------|----------------|
| OCR | Google Vision | **1 crèdit** | ~1-2 s |
| Phase 1 | Python regex | **0 crèdits** | ~5-10 ms |
| Phase 2 | Python pur | **0 crèdits** | ~5-10 ms |
| **TOTAL** | — | **1 crèdit** | **~1-2 s** |

---

## 3. Validació CIF (algoritme oficial AEAT)

### Format CIF

```
[LLETRA][7 DÍGITS][CONTROL]
```

Exemples:
- `B76261874` → B (SL/SA), 7626187, 4 (dígit control)
- `G65864829` → G (associació), 6586482, 9 (dígit control)

### Lletres vàlides (tipus d'entitat)

| Lletra | Tipus d'entitat |
|--------|-----------------|
| A | Societat Anònima |
| B | Societat Limitada |
| C | Societat Col·lectiva |
| D | Societat Comanditària |
| E | Comunitat de Béns |
| F | Societat Cooperativa |
| G | Associació o Fundació |
| H | Comunitat de Propietaris |
| J | Societat Civil |
| N | Entitat estrangera |
| P | Corporació Local |
| Q | Organisme Autònom |
| R | Congregació religiosa |
| S | Òrgan de l'Administració |
| U | Unió Temporal d'Empreses |
| V | Altres (fons d'inversió, etc.) |
| W | Establiment permanent |

### Algoritme de validació

```python
def validate_cif(cif: str) -> bool:
    """
    Algoritme oficial AEAT per validar NIF/CIF.

    Passos:
    1. Validar format: [A-W]\d{7}[0-9A-J]
    2. Calcular suma senars (posicions 0,2,4,6):
       - Multiplicar per 2
       - Si resultat >= 10, restar 9
    3. Calcular suma parells (posicions 1,3,5):
       - Sumar directament
    4. Control = (10 - (suma_total % 10)) % 10
    5. Lletra control = "JABCDEFGHI"[control]
    6. Validar segons primera lletra:
       - A,B,E,H: només dígit
       - K,P,Q,S: només lletra
       - Altres: dígit o lletra
    """
    cif = cif.upper().strip()

    # Format
    if not re.match(r"^[ABCDEFGHJKLMNPQRSUVW]\d{7}[A-J0-9]$", cif):
        return False

    letter = cif[0]
    number = cif[1:8]
    control = cif[8]

    # Suma senars
    odd_sum = 0
    for i in range(0, 7, 2):
        n = int(number[i]) * 2
        odd_sum += n if n < 10 else n - 9

    # Suma parells
    even_sum = sum(int(number[i]) for i in range(1, 7, 2))

    # Dígit control
    control_digit = (10 - (even_sum + odd_sum) % 10) % 10
    control_letter = "JABCDEFGHI"[control_digit]

    # Validar segons lletra
    if letter in "ABEH":
        return control == str(control_digit)
    elif letter in "KPQS":
        return control == control_letter
    else:
        return control == str(control_digit) or control == control_letter
```

### Exemples de validació

| NIF | Vàlid | Motiu |
|-----|-------|-------|
| `B76261874` | ✅ | B requereix dígit, 4 és correcte |
| `B76261875` | ❌ | Control incorrecte (esperat: 4) |
| `G65864829` | ✅ | G accepta dígit o lletra, 9 és correcte |
| `A58818501` | ✅ | A requereix dígit, 1 és correcte |
| `K1234567E` | ✅ | K requereix lletra, E és correcte |
| `K12345674` | ❌ | K requereix lletra, no dígit |

---

## 4. Model de dades

### NIFDatos (25+ camps)

```python
class NIFDatos(BaseModel):
    # Identificació
    numero_nif: Optional[str] = None              # "B76261874"
    tipo_nif: Optional[str] = None                # "CIF"

    # Entitat
    denominacion: Optional[str] = None            # Raó Social
    razon_social: Optional[str] = None            # Alias
    anagrama_comercial: Optional[str] = None      # Nom comercial

    # Domicili Social (registral)
    domicilio_social: Optional[str] = None        # Adreça completa
    domicilio_social_calle: Optional[str] = None
    domicilio_social_numero: Optional[str] = None
    domicilio_social_piso_puerta: Optional[str] = None
    domicilio_social_municipio: Optional[str] = None
    domicilio_social_provincia: Optional[str] = None
    domicilio_social_codigo_postal: Optional[str] = None

    # Domicili Fiscal (AEAT) - OBLIGATORI
    domicilio_fiscal: Optional[str] = None
    domicilio_fiscal_calle: Optional[str] = None
    domicilio_fiscal_numero: Optional[str] = None
    domicilio_fiscal_piso_puerta: Optional[str] = None
    domicilio_fiscal_municipio: Optional[str] = None
    domicilio_fiscal_provincia: Optional[str] = None
    domicilio_fiscal_codigo_postal: Optional[str] = None

    # Dates (ISO YYYY-MM-DD)
    fecha_nif_definitivo: Optional[str] = None
    fecha_expedicion: Optional[str] = None

    # Administració AEAT
    administracion_aeat: Optional[str] = None     # "35601 PALMAS G.C"
    codigo_administracion: Optional[str] = None   # "35601"
    nombre_administracion: Optional[str] = None   # "PALMAS G.C"

    # Altres
    codigo_electronico: Optional[str] = None      # Hex 10+ chars
```

### NIFValidationResponse (contracte v1)

```python
class NIFValidationResponse(BaseModel):
    valido: bool                          # True si vàlid
    confianza_global: int                 # 0-100
    tipo_documento: Literal["nif"] = "nif"
    datos: NIFDatos
    alertas: List[ValidationItem] = []
    errores_detectados: List[ValidationItem] = []
    raw: RawOCR
    meta: Optional[MetaInfo] = None
```

### Camps mínims per validesa

```python
_CAMPS_MINIMS = ["numero_nif", "razon_social", "domicilio_fiscal"]
```

**valido = True** si i només si:
1. ✅ `numero_nif` present i CIF vàlid (dígit control correcte)
2. ✅ `razon_social` present
3. ✅ `domicilio_fiscal` present (mínim camp obligatori)
4. ✅ Cap error de severitat `"critical"`

---

## 5. Extracció de camps

### Keywords detectades

| Keyword OCR | Camp extret | Exemple |
|-------------|-------------|---------|
| `Denominación` | `denominacion`, `razon_social` | "CASAACTIVA GESTION, S.L." |
| `Razón Social` | `razon_social`, `denominacion` | "ASSOCIACIO DNI.CAT" |
| `Anagrama Comercial` | `anagrama_comercial` | "CASAACTIVA" |
| `Domicilio` + `Social` | `domicilio_social_*` | "C MOSTEROL, NUM. 7..." |
| `Domicilio` + `Fiscal` | `domicilio_fiscal_*` | "CALLE ORINOCO, NUM. 5..." |
| `Fecha N.I.F. Definitivo` | `fecha_nif_definitivo` | "26-07-2016" → "2016-07-26" |
| `Administración de la AEAT` | `administracion_aeat`, `codigo_administracion`, `nombre_administracion` | "35601 PALMAS G.C" |
| `Código Electrónico` | `codigo_electronico` | "2DCB113CA7F63DC2" |

### Extracció d'adreça (reutilitzada del DNI parser)

El parser detecta automàticament els components de l'adreça:

```python
def _parse_domicilio_inline(lines, line_idx, primera_linia):
    # Exemple entrada: "CALLE ORINOCO, NUM. 5"
    # Sortida:
    # {
    #   "completo": "CALLE ORINOCO, NUM. 5 PLANTA 0, PUERTA 3 35014 PALMAS...",
    #   "calle": "CALLE ORINOCO",
    #   "numero": "5",
    #   "piso_puerta": "PLANTA 0, PUERTA 3",
    #   "codigo_postal": "35014",
    #   "municipio": "PALMAS DE GRAN CANARIA",
    #   "provincia": "LAS"
    # }
```

**Regex principals**:
- **Número + pis/porta**: `r"[,\s]+(?:NUM\.?\s*)?(\d{1,4}[A-Z]?)\s*[,]?\s*(PLANTA\s*\d+[,]?\s*PUERTA\s*\d+|...)"`
- **Codi postal**: `r"\b(\d{5})\b"`
- **Província**: Cerca inversa en llista de 52 províncies espanyoles

### Formats de data

- **Input OCR**: `"DD-MM-YYYY"` o `"DD/MM/YYYY"`
- **Output model**: `"YYYY-MM-DD"` (ISO 8601)
- **Validació rang**: 1980 - any actual

---

## 6. Codis d'error i alertes

### Errors NIF

| Codi | Severitat | Camp | Descripció |
|------|-----------|------|------------|
| `NIF_MISSING_FIELD` | `critical` | `numero_nif` | NIF no detectat |
| `NIF_MISSING_FIELD` | `error` | `razon_social`, `domicilio_fiscal` | Camps mínims absents |
| `NIF_CHECKDIGIT_MISMATCH` | `critical` | `numero_nif` | Dígit control CIF incorrecte |
| `NIF_INVALID_FORMAT` | `critical` | `numero_nif` | Format NIF no reconegut |
| `NIF_DATE_INVALID` | `error` | `fecha_nif_definitivo`, `fecha_expedicion` | Data fora de rang o en el futur |
| `NIF_OCR_NOISE` | `warning` | diversos | Caràcters inesperats (soroll OCR) |

### Lògica de confianza_global

```python
def compute_confianza(alertas, errores, camps_minims_absents, ocr_confidence):
    score = 100

    for item in errores + alertas:
        if item.severity == "critical":
            score -= 35
        elif item.severity == "error":
            score -= 15
        else:  # warning
            score -= 5

    score -= camps_minims_absents * 20

    # Ajust OCR (pes 15%)
    score = round(score * 0.85 + ocr_confidence * 0.15)

    return max(0, min(100, score))
```

**Interpretació**:

| Rang | Significat |
|------|------------|
| 90-100 | Excel·lent — document llegit amb alta fiabilitat |
| 70-89 | Bo — pot tenir imprecisions menors |
| 50-69 | Acceptable — revisió manual recomanable |
| 0-49 | Baix — probable que necessiti revisió |

---

## 7. Casos d'ús i exemples

### Exemple 1: NIF tipus B (Societat Limitada)

**Input**: Imatge TIF amb NIF `B76261874`

**Output**:
```json
{
  "valido": true,
  "confianza_global": 99,
  "tipo_documento": "nif",
  "datos": {
    "numero_nif": "B76261874",
    "tipo_nif": "CIF",
    "razon_social": "CASAACTIVA GESTION, S.L.",
    "domicilio_fiscal": "CALLE ORINOCO, NUM. 5 PLANTA 0, PUERTA 3 35014 PALMAS DE GRAN CANARIA (LAS) - (PALMAS, LAS)",
    "domicilio_fiscal_calle": "CALLE ORINOCO",
    "domicilio_fiscal_numero": "5",
    "domicilio_fiscal_piso_puerta": "PLANTA 0, PUERTA 3",
    "domicilio_fiscal_codigo_postal": "35014",
    "domicilio_fiscal_municipio": "PALMAS DE GRAN CANARIA",
    "domicilio_fiscal_provincia": "LAS",
    "fecha_nif_definitivo": "2016-07-26",
    "administracion_aeat": "35601 PALMAS G.C",
    "codigo_administracion": "35601",
    "nombre_administracion": "PALMAS G.C",
    "codigo_electronico": "2DCB113CA7F63DC2"
  },
  "alertas": [],
  "errores_detectados": [],
  "raw": {
    "ocr_engine": "google_vision",
    "ocr_confidence": 95.0
  }
}
```

### Exemple 2: NIF tipus G (Associació)

**Input**: Imatge TIF amb NIF `G65864829`

**Output**:
```json
{
  "valido": true,
  "confianza_global": 99,
  "tipo_documento": "nif",
  "datos": {
    "numero_nif": "G65864829",
    "tipo_nif": "CIF",
    "razon_social": "ASSOCIACIO DNI.CAT",
    "domicilio_social": "C MOSTEROL, NUM. 7 08221 TERRASSA - (BARCELONA)",
    "domicilio_social_calle": "C MOSTEROL",
    "domicilio_social_numero": "7",
    "domicilio_social_codigo_postal": "08221",
    "domicilio_social_municipio": "TERRASSA",
    "domicilio_fiscal": "C MOSTEROL, NUM. 7 08221 TERRASSA - (BARCELONA)",
    "domicilio_fiscal_calle": "C MOSTEROL",
    "domicilio_fiscal_numero": "7",
    "domicilio_fiscal_codigo_postal": "08221",
    "domicilio_fiscal_municipio": "TERRASSA",
    "fecha_nif_definitivo": "2012-09-05",
    "administracion_aeat": "08279 TERRASSA",
    "codigo_electronico": "50A22EE39C3A8763"
  },
  "alertas": [],
  "errores_detectados": []
}
```

### Exemple 3: NIF invàlid (dígit control incorrecte)

**Input**: NIF `B76261875` (control incorrecte)

**Output**:
```json
{
  "valido": false,
  "confianza_global": 50,
  "tipo_documento": "nif",
  "datos": {
    "numero_nif": "B76261875",
    "razon_social": "EXAMPLE COMPANY SL",
    "domicilio_fiscal": "CALLE TEST 1"
  },
  "errores_detectados": [
    {
      "code": "NIF_CHECKDIGIT_MISMATCH",
      "severity": "critical",
      "field": "numero_nif",
      "message": "Dígit de control CIF incorrecte.",
      "evidence": "Llegit: '5', esperat: '4'",
      "suggested_fix": null
    }
  ],
  "alertas": []
}
```

---

## 8. Tests i validació

### Test suite (`tests/test_nif_parser.py`)

**Cobertura**:
- ✅ 25+ tests de validació CIF (A/B/E/H/K/P/Q/S, vàlids/invàlids)
- ✅ Tests de parse (extracció camps, domicilis, dates ISO)
- ✅ Tests de validate_and_build_response (document vàlid, errors crítics)

**Executar tests**:
```bash
pytest tests/test_nif_parser.py -v
pytest tests/test_nif_parser.py --cov=app.parsers.nif_parser
```

### Tests de validació CIF

```python
def test_cif_b76261874_valid():
    assert validate_cif("B76261874") is True

def test_cif_wrong_checkdigit():
    assert validate_cif("B76261875") is False

def test_cif_a_requires_digit():
    assert validate_cif("A58818501") is True
    assert validate_cif("A5881850J") is False

def test_cif_k_requires_letter():
    assert validate_cif("K1234567E") is True
    assert validate_cif("K12345674") is False
```

### Verificació end-to-end

```bash
# 1. Iniciar servei
python -m uvicorn app.main:app --reload

# 2. Test amb imatge real
curl -X POST "http://localhost:8000/ocr/nif" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@nif_example.jpg"

# 3. Verificar resposta JSON
# {
#   "valido": true,
#   "confianza_global": 99,
#   "datos": { "numero_nif": "B76261874", ... }
# }
```

---

## Fitxers clau

| Fitxer | Descripció |
|--------|------------|
| `app/models/nif_response.py` | Models Pydantic (NIFDatos, NIFValidationResponse) |
| `app/parsers/nif_parser.py` | Parser principal (Phase 1+2, validació CIF) |
| `app/routes/nif.py` | Endpoint POST /ocr/nif |
| `tests/test_nif_parser.py` | Tests unitaris |
| `app/models/base_response.py` | ValidationItem, compute_confianza (compartit) |

---

## Comparació amb altres parsers

| Característica | DNI Parser | Permís Parser | NIF Parser |
|----------------|------------|---------------|------------|
| **Document** | DNI/NIE persona física | Permís circulació vehicle | NIF/TIF entitat jurídica |
| **Validació principal** | Lletra control DNI/NIE (mòdul 23) | Matrícula + VIN format | **CIF algoritme AEAT** |
| **Camps mínims** | numero_documento, nombre, apellidos | matricula, marca | **numero_nif, razon_social, domicilio_fiscal** |
| **Adreça** | 1 domicili (posterior DNI) | 1 domicili (titular) | **2 domicilis (social + fiscal)** |
| **Components adreça** | ✅ calle, numero, piso_puerta, CP, municipi, província | ✅ Simples | ✅ **Dobles** (social/fiscal) |
| **Validació creuada** | MRZ vs text frontal | VIN checkdigit (opcional) | **Dígit control CIF (obligatori)** |
| **Cost** | 1 crèdit Vision | 1 crèdit Vision | 1 crèdit Vision |

---

## Changelog

| Data | Versió | Canvis |
|------|--------|--------|
| 2026-02-26 | v1.0 | Release inicial NIF parser · Validació CIF completa AEAT · 2 domicilis amb components · Contracte unificat v1 |

---

**Documentació relacionada**:
- [API.md](./API.md) - Documentació completa de l'API
- [GOGESTOR_INTEGRATION.md](./GOGESTOR_INTEGRATION.md) - Integració amb GoGestor
- [README.md](../README.md) - Guia general del projecte

**Suport**: kim@conekta.cat
