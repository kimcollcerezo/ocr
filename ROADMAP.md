# Roadmap - OCR Agent

Pròxims desenvolupaments planificats per l'Agent OCR.

---

## 📊 Prioritat Alta

### 1. Sistema de Tracking d'Ús (Logging & Metrics)

**Objectiu**: Controlar la quantitat d'escaneixos realitzats per usuari/projecte per calcular costos reals.

#### Funcionalitat mínima viable (MVP)
- Registrar cada petició OCR amb:
  - Timestamp
  - Usuari/Projecte (identificat per API key o header personalitzat)
  - Tipus de document (DNI, Permís, etc.)
  - Motor OCR utilitzat (Google Vision, Tesseract)
  - Confiança del resultat
  - Temps de processament
  - Èxit/Error
  - Cost estimat (segons tarifes de Google Vision)

#### Implementació proposada

**Opció A: SQLite simple (Recomanada per començar)**
```
logs/
├── ocr_usage.db (SQLite)
└── Schema:
    - id (autoincrement)
    - timestamp
    - project_id (extret de X-Project-ID header)
    - api_key_prefix (primers 10 caràcters)
    - document_type (dni, permis, passaport, etc.)
    - ocr_engine (google_vision, tesseract)
    - confidence (float)
    - processing_time (float)
    - success (boolean)
    - error_message (text)
    - cost_usd (float calculat)
```

**Opció B: Fitxers JSON (més simple però menys escalable)**
```
logs/
├── 2026-01/
│   ├── 2026-01-30.json
│   └── 2026-01-31.json
└── Format:
    [
      {
        "timestamp": "2026-01-30T10:30:45Z",
        "project": "gogestor",
        "document_type": "dni",
        "engine": "google_vision",
        "success": true,
        "cost": 0.0015
      }
    ]
```

#### API Endpoints nous

```
GET /metrics/usage
  - Paràmetres: start_date, end_date, project_id
  - Retorna: Resum d'ús per projecte/dia/document

GET /metrics/costs
  - Paràmetres: start_date, end_date, project_id
  - Retorna: Costos per projecte/motor OCR

GET /metrics/health
  - Estadístiques generals: total requests, success rate, avg confidence
```

#### Identificació de projectes

**Opció 1: Header personalitzat (Recomanada)**
```http
X-API-Key: ocr_c1ZKEHfJmYeacPGIWML6ldO5xVAZLYY-9d3Wdcx5Kv0
X-Project-ID: gogestor
```

**Opció 2: Múltiples API keys (una per projecte)**
```
gogestor_ocr_abc123...
conekta_ocr_def456...
altres_ocr_ghi789...
```

#### Dashboard simple (Fase 2)

```
GET /dashboard
  - Pàgina HTML amb gràfics de:
    - Requests per dia (Chart.js)
    - Cost per projecte
    - Success rate
    - Documents més processats
```

---

## 📄 Prioritat Mitjana

### 2. Suport per més tipus de documents

#### Fase 1: Documents espanyols
- [x] DNI Espanyol (frontal i posterior)
- [x] Permís de Circulació
- [ ] **Passaport espanyol**
  - MRZ (Machine Readable Zone)
  - Dades personals
  - Data d'expedició i caducitat
  - Número de passaport

- [ ] **Permís de conduir espanyol**
  - Número de permís
  - Data d'expedició i caducitat
  - Classes de permisos (A, B, C, D, etc.)
  - Titular

- [ ] **NIE (Número d'Identificació d'Estranger)**
  - Similar al DNI però per estrangers
  - Format: X1234567A, Y1234567B, Z1234567C

#### Fase 2: Documents internacionals
- [ ] **Passaport internacional (MRZ estàndard)**
  - Suport per passaports de qualsevol país
  - Parser MRZ universal

- [ ] **DNI/ID Card europees**
  - Format estàndard UE
  - MRZ si n'hi ha

- [ ] **Carnet de conducir internacional**
  - Format estàndard internacional

#### Fase 3: Documents empresarials
- [ ] **Factures**
  - Número de factura
  - Import total
  - IVA
  - Data d'emissió
  - Proveïdor

- [ ] **Contractes**
  - Extracció de camps clau
  - Dates
  - Parts contractants

- [ ] **Albarans**
  - Número d'albarà
  - Data
  - Productes/quantitats

---

## 🔧 Prioritat Baixa

### 3. Millores tècniques

#### Cache de resultats
- Evitar processar la mateixa imatge dues vegades
- Usar hash MD5 de la imatge com a clau
- TTL configurable (per defecte 24h)
- Storage: Redis o SQLite

#### Rate limiting avançat
- Per projecte/API key
- Configurar límits diferents per tipus de compte
- Retornar headers `X-RateLimit-*`

#### Webhooks
- Notificar quan un document s'ha processat
- Processar documents de manera asíncrona
- Callbacks amb resultat OCR

#### Comparació d'engines OCR
- Reactivar endpoint `/ocr/compare`
- Comparar Tesseract vs Google Vision
- Recomanacions automàtiques segons tipus de document

#### Detecció automàtica de document
- Detectar automàticament si és DNI, Permís, Passaport, etc.
- Aplicar parser corresponent automàticament
- Endpoint: `POST /ocr/auto`

#### Multi-idioma
- Suport per més idiomes a Tesseract
- Detecció automàtica d'idioma
- Documents en francès, alemany, italià, etc.

---

## 📋 Implementació Fase 1: Sistema de Tracking

### Pas 1: Crear model de base de dades

```python
# app/models/usage_log.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UsageLog(BaseModel):
    timestamp: datetime
    project_id: Optional[str] = None
    api_key_prefix: str
    document_type: str
    ocr_engine: str
    confidence: Optional[float] = None
    processing_time: float
    success: bool
    error_message: Optional[str] = None
    cost_usd: float
```

### Pas 2: Crear servei de logging

```python
# app/services/usage_logger.py
import sqlite3
from datetime import datetime
from app.models.usage_log import UsageLog

class UsageLogger:
    def __init__(self, db_path="logs/ocr_usage.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        # Crear taula si no existeix
        pass

    def log_request(self, log: UsageLog):
        # Guardar a SQLite
        pass

    def get_usage(self, start_date, end_date, project_id=None):
        # Query per obtenir estadístiques
        pass

    def get_costs(self, start_date, end_date, project_id=None):
        # Calcular costos
        pass
```

### Pas 3: Integrar al middleware

```python
# app/main.py
from app.services.usage_logger import usage_logger

@app.middleware("http")
async def log_usage(request: Request, call_next):
    if request.url.path.startswith("/ocr/"):
        start_time = time.time()
        response = await call_next(request)
        processing_time = time.time() - start_time

        # Extreure info de la request
        project_id = request.headers.get("X-Project-ID")
        api_key_prefix = request.headers.get("X-API-Key", "")[:10]

        # Log
        usage_logger.log_request(UsageLog(
            timestamp=datetime.now(),
            project_id=project_id,
            api_key_prefix=api_key_prefix,
            document_type=extract_doc_type(request.url.path),
            ocr_engine="google_vision",
            processing_time=processing_time,
            success=response.status_code == 200,
            cost_usd=calculate_cost("google_vision")
        ))

        return response

    return await call_next(request)
```

### Pas 4: Crear endpoints de mètriques

```python
# app/routes/metrics.py
from fastapi import APIRouter, Query
from datetime import date

router = APIRouter()

@router.get("/usage")
async def get_usage(
    start_date: date = Query(...),
    end_date: date = Query(...),
    project_id: str = Query(None)
):
    usage = usage_logger.get_usage(start_date, end_date, project_id)
    return {
        "total_requests": usage.total,
        "by_project": usage.by_project,
        "by_document_type": usage.by_document_type,
        "success_rate": usage.success_rate
    }

@router.get("/costs")
async def get_costs(
    start_date: date = Query(...),
    end_date: date = Query(...),
    project_id: str = Query(None)
):
    costs = usage_logger.get_costs(start_date, end_date, project_id)
    return {
        "total_cost_usd": costs.total,
        "by_project": costs.by_project,
        "by_engine": costs.by_engine,
        "estimated_monthly": costs.estimated_monthly
    }
```

---

## 💰 Càlcul de costos

### Google Cloud Vision

```python
def calculate_google_vision_cost(requests: int) -> float:
    """
    Tarifa Google Vision API (2026):
    - Primers 1.000: Gratuït
    - 1.001 - 5.000.000: $1.50 per 1.000 unitats
    - 5.000.001+: $0.60 per 1.000 unitats
    """
    if requests <= 1000:
        return 0.0
    elif requests <= 5_000_000:
        return ((requests - 1000) / 1000) * 1.50
    else:
        cost_tier2 = (4_999_000 / 1000) * 1.50
        cost_tier3 = ((requests - 5_000_000) / 1000) * 0.60
        return cost_tier2 + cost_tier3
```

### Tesseract
```python
def calculate_tesseract_cost() -> float:
    """Tesseract és gratuït (open source)"""
    return 0.0
```

---

## 📅 Timeline estimat

### Mes 1 (Febrer 2026)
- ✅ Sistema de tracking bàsic (SQLite)
- ✅ API endpoints `/metrics/usage` i `/metrics/costs`
- ✅ Header `X-Project-ID` per identificar projectes

### Mes 2 (Març 2026)
- ✅ Passaport espanyol
- ✅ Permís de conduir espanyol
- ✅ NIE

### Mes 3 (Abril 2026)
- ✅ Dashboard simple HTML
- ✅ Exportació de logs (CSV/Excel)
- ✅ Alertes de cost (email quan supera X€)

### Mes 4+ (Maig 2026 endavant)
- Passaports internacionals
- Factures i contractes
- Cache de resultats
- Webhooks

---

## 🎯 KPIs a mesurar

1. **Volum**
   - Requests totals per dia/mes
   - Requests per projecte
   - Requests per tipus de document

2. **Qualitat**
   - Success rate (%)
   - Confiança mitjana (%)
   - Temps de resposta mitjà

3. **Costos**
   - Cost total mensual ($)
   - Cost per projecte ($)
   - Cost per request ($)
   - Percentatge Google Vision vs Tesseract

4. **Errors**
   - Taxa d'error per tipus de document
   - Errors més comuns
   - Temps de downtime

---

## 📝 Notes

- Mantenir el sistema **stateless** fins que s'implementi SQLite per logs
- Prioritzar **simplicitat** sobre funcionalitats avançades
- **Backward compatibility**: Nous features no han de trencar API existent
- **Security first**: Logs no han de contenir dades sensibles (DNIs, noms, etc.)

---

**Última actualització**: 30 Gener 2026
**Autor**: Kim Coll
**Projecte**: OCR Agent v1.0.0
