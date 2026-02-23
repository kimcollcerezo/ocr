# Agent OCR — Document Processing API

API REST per processar documents espanyols (DNI/NIE i Permís de Circulació) amb OCR expert i validació automàtica.

**Versió**: Contracte unificat v1 · **Desplegament**: Railway

---

## Característiques

- **Tesseract-first + Google Vision fallback** — 1 sol crèdit Vision per document
- **Validació expert automàtica** — check digit DNI/NIE, format matrícula, VIN, NIF titular
- **Resposta unificada** (`valido`, `confianza_global`, `ValidationItem`) per tots els documents
- **Dates ISO 8601** (`YYYY-MM-DD`) a tots els camps
- **JSON structured logging** amb latència i motor OCR usat
- **PII redactat** als logs (DNI: `7761****T`)
- **131 tests unitaris** (DNI parser + model + Permís parser)
- **Stateless** — cap base de dades, les imatges s'eliminen immediatament

## Documents suportats

| Document | Camps extrets | Motors |
|----------|---------------|--------|
| DNI espanyol (frontal) | número, nom, cognoms, sexe, nacionalitat, dates | Tesseract + Vision |
| DNI espanyol (posterior) | domicili, lloc de naixement, pare/mare, MRZ | Tesseract + Vision |
| NIE (X/Y/Z) | identificació NIE, mateixos camps que DNI | Tesseract + Vision |
| Permís de Circulació | matrícula, VIN, marca, model, potència, titular, ITV... | Vision (Tesseract fallback rar) |

## Arquitectura de cost

```
Imatge
  │
  ▼
Tesseract (gratuït)
  ├─ OK (confiança ≥ 50, camps mínims vàlids) ──► Retorna resultat
  └─ Fallback ──► Google Vision (1 crèdit) ──► Validació Python ──► Retorna resultat
```

**Garantia**: Cap document consumeix més d'1 crèdit Vision.
La validació creuada (Phase 2) és Python pur, sense crides externes.

---

## Instal·lació (desenvolupament local)

```bash
# 1. Clonar i entrar
git clone <repository-url>
cd OCR

# 2. Entorn virtual
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 3. Dependències
pip install -r requirements.txt

# 4. Tesseract (opcional)
brew install tesseract tesseract-lang  # macOS
# apt-get install tesseract-ocr tesseract-ocr-spa  # Ubuntu

# 5. Variables d'entorn
cp .env.example .env
# Editar .env amb les credencials Google Cloud Vision

# 6. Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

---

## Ús ràpid

### Health check

```bash
curl http://localhost:8000/health
```

```json
{"status": "healthy", "services": {"tesseract": true, "google_vision": true}}
```

### Processar DNI

```bash
curl -X POST "http://localhost:8000/ocr/dni" \
  -F "file=@dni_frontal.jpg"
```

**Resposta (contracte v1)**:

```json
{
  "valido": true,
  "confianza_global": 99,
  "tipo_documento": "dni",
  "datos": {
    "numero_documento": "77612097T",
    "tipo_numero": "DNI",
    "nombre": "JOAQUIN",
    "apellidos": "COLL CEREZO",
    "nombre_completo": "JOAQUIN COLL CEREZO",
    "sexo": "M",
    "nacionalidad": "ESP",
    "fecha_nacimiento": "1973-01-24",
    "fecha_caducidad": "2028-08-28"
  },
  "alertas": [],
  "errores_detectados": [],
  "raw": {"ocr_engine": "google_vision", "ocr_confidence": 95.0},
  "meta": {"success": true, "message": "Document processat correctament"}
}
```

### Processar Permís de Circulació

```bash
curl -X POST "http://localhost:8000/ocr/permis" \
  -F "file=@permis.jpg"
```

**Resposta (contracte v1)**:

```json
{
  "valido": true,
  "confianza_global": 99,
  "tipo_documento": "permiso_circulacion",
  "datos": {
    "matricula": "1177MTM",
    "numero_bastidor": "YARKAAC3100018794",
    "marca": "TOYOTA",
    "modelo": "TOYOTA YARIS",
    "categoria": "M1",
    "fecha_matriculacion": "2024-08-08",
    "titular_nombre": "JOAQUIN COLL CEREZO",
    "cilindrada_cc": 1490,
    "potencia_kw": 92.0,
    "potencia_fiscal": 125.1,
    "combustible": "GASOLINA",
    "plazas": 5,
    "proxima_itv": "2028-08-08"
  },
  "alertas": [],
  "errores_detectados": [],
  "raw": {"ocr_engine": "google_vision", "ocr_confidence": 95.0},
  "meta": {"success": true, "message": "Permís processat correctament"}
}
```

---

## Estructura del projecte

```
OCR/
├── app/
│   ├── main.py                  # FastAPI app + JSON logging + middleware
│   ├── config.py                # Variables d'entorn
│   ├── models/
│   │   ├── base_response.py     # ValidationItem, RawOCR, MetaInfo, compute_confianza()
│   │   ├── dni_response.py      # DNIDatos, DNIValidationResponse
│   │   └── permis_response.py   # PermisExtracted, PermisValidationResponse
│   ├── parsers/
│   │   ├── dni_parser.py        # MRZ + full-text, check digit, NIE
│   │   └── permis_parser.py     # EU field codes, VIN, matrícula, NIF
│   ├── routes/
│   │   ├── dni.py               # POST /ocr/dni
│   │   └── permis.py            # POST /ocr/permis
│   └── services/
│       ├── tesseract_service.py
│       ├── google_vision_service.py
│       └── image_processor.py   # OpenCV: rotació, CLAHE, denoise, perspectiva
├── tests/
│   ├── test_dni_parser.py       # 44 tests parser DNI
│   ├── test_dni_model.py        # 11 tests model DNI
│   └── test_permis_parser.py    # 76 tests parser Permís
├── docs/
│   ├── API.md                   # Documentació completa contracte v1
│   ├── GOGESTOR_INTEGRATION.md  # Integració PHP/Laravel
│   ├── DEPLOYMENT.md
│   ├── DEVELOPMENT.md
│   └── IMAGE_PROCESSING.md
├── ROADMAP.md
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Tests

```bash
source venv/bin/activate
pytest tests/ -v
# 131 passed
```

---

## Modes de preprocessament

| Mode | Ús | Velocitat |
|------|-----|-----------|
| `standard` (default) | Ús general — rotació + CLAHE | Ràpid |
| `aggressive` | Imatges fosques o de baixa qualitat | Moderat |
| `document` | Documents inclinats, perspectiva | Lent |

```bash
curl -X POST "http://localhost:8000/ocr/dni" \
  -F "file=@dni.jpg" \
  -F "preprocess=true" \
  -F "preprocess_mode=aggressive"
```

---

## Desplegament

### Railway (producció)

```bash
# Railway auto-detecta el Dockerfile
# Variables d'entorn a configurar:
#   GOOGLE_CLOUD_CREDENTIALS_JSON  (obligatori)
#   TESSERACT_ENABLED=true
```

### Docker local

```bash
docker build -t ocr-agent .
docker run -p 8000:8000 \
  -e GOOGLE_CLOUD_CREDENTIALS_JSON='{"type":"service_account",...}' \
  ocr-agent
```

---

## Costos estimats

| Servei | Cost |
|--------|------|
| Google Vision (tier gratuït) | Primers 1.000 docs/mes gratuïts |
| Google Vision (pagament) | $1.50 / 1.000 docs |
| Tesseract | Gratuït (local) |
| Railway Hobby Plan | $5/mes |
| **Total estimat** | **~$5-10/mes** per ús moderat |

---

## Documentació

- **[docs/API.md](docs/API.md)** — Contracte v1 complet, tots els camps, catàleg d'errors, exemples JS/TS/Python/PHP
- **[docs/GOGESTOR_INTEGRATION.md](docs/GOGESTOR_INTEGRATION.md)** — Integració PHP/Laravel per a GoGestor
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — Guia Railway + Docker
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** — Entorn de desenvolupament
- **[ROADMAP.md](ROADMAP.md)** — Estat actual i pròxims passos

**Swagger UI interactiu**: http://localhost:8000/docs

---

## Seguretat i RGPD

- Les imatges s'eliminen immediatament després del processament (fitxers temporals)
- Els logs no contenen dades personals (DNI, noms) — redactats al route layer
- CORS configurat (tots els orígens en dev, limitar en producció)
- Credencials Google Cloud com a variable d'entorn (mai al codi)

---

© 2026 Kim Coll · kim@conekta.cat
