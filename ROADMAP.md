# Roadmap — OCR Agent

**Última actualització**: 2026-02-24

---

## Estat actual (v1.0 — Contracte unificat)

### Implementat i en producció

| Funcionalitat | Estat | Notes |
|---------------|-------|-------|
| Parser DNI/NIE (frontal + posterior) | ✅ | MRZ + full-text, check digit, NIE X/Y/Z |
| Camps `calle`, `numero` i `piso_puerta` separats | ✅ | DNI posterior, auto-split adreça amb pis/porta |
| Parser Permís de Circulació | ✅ | Codis EU D.1, P.1, C.1.x, VIN, matrícula |
| Google Vision (únic motor OCR) | ✅ | 50% més ràpid (~630ms), Tesseract eliminat |
| Contracte unificat v1 | ✅ | `valido`, `confianza_global`, `ValidationItem` |
| Dates ISO 8601 (YYYY-MM-DD) | ✅ | Tots els endpoints |
| JSON structured logging | ✅ | `ts`, `level`, `logger`, `durada_ms`... |
| PII redaction als logs | ✅ | DNI redactat: `7761****T` |
| Tests unitaris DNI (55 tests) | ✅ | Parser + model |
| Tests unitaris Permís (76 tests) | ✅ | Parser + validadors + fallback |
| Documentació API v1 | ✅ | `docs/API.md` actualitzat |
| Desplegament Railway | ✅ | https://ocr-production-abec.up.railway.app |

---

## Prioritat Alta — Pròxims passos

### 1. 🚀 Migració de Railway → Google Cloud Platform

**Objectiu**: Desplegar l'agent OCR a Google Cloud en comptes de Railway

**Per què?**
- ✅ **Mateix ecosistema** que Google Vision (millor integració)
- ✅ **Menys latència** (APIs internes de Google Cloud)
- ✅ **Millor pricing** per a volums alts
- ✅ **Escalabilitat automàtica** (Cloud Run)
- ✅ **Més control** sobre infraestructura i logs

**Opcions de desplegament:**

| Servei | Pros | Contras | Recomanat |
|--------|------|---------|-----------|
| **Cloud Run** | Serverless, autoscaling, pay-per-use | Cold starts | ✅ **SÍ** |
| App Engine | Managed, zero config | Menys flexible | No |
| Compute Engine | Control total | Gestió manual | No |

**Tasques:**
1. Crear projecte GCP (o usar `gogestor-ocr-485718` existent)
2. `Dockerfile` optimitzat per Cloud Run
3. Configurar Cloud Build (auto-deploy des de GitHub)
4. Variables d'entorn (`GOOGLE_CLOUD_CREDENTIALS_JSON`)
5. Configurar custom domain
6. Health checks i monitoring

**Esforç estimat**: 1 dia · **Prioritat**: 🔥 **ALTA**

---

### 2. ~~Actualitzar OcrService.php (GoGestor)~~

✅ **En curs** - GoGestor ja està integrant el contracte v1

---

### 3. Sistema de tracking d'ús

**Objectiu**: Saber quants documents processa cada projecte i calcular costos reals.

El middleware de logging ja escriu JSON. El pas següent és persistir les mètriques
(motor OCR usat, `durada_ms`, `valido`) per projecte.

**Implementació mínima (SQLite o Cloud SQL)**:

```
ocr_usage.db
├── timestamp
├── project_id      (header X-Project-ID)
├── document_type   (dni | permiso_circulacion)
├── ocr_engine      (google_vision)
├── confianza_global
├── valido
├── durada_ms
└── cost_usd        (calculat: Vision $0.0015/doc)
```

Nous endpoints: `GET /metrics/usage`, `GET /metrics/costs`

**Esforç estimat**: 1 dia · **Prioritat**: Alta (necessari per facturar)

---

### 4. Passaport espanyol

Estructura similar al DNI però amb MRZ de 2 línies (TD3):
- Número de passaport (format `AAA000000`)
- Dates ISO
- Mateixa arquitectura contracte v1

**Esforç estimat**: 1-2 dies

---

### 5. Permís de conduir espanyol

Camps: número permís, data expedició/caducitat, classes (A, B, C...), titular.
Atenció: el format varia molt entre generacions.

**Esforç estimat**: 2-3 dies

---

## Prioritat Mitjana

### 6. Endpoint `/ocr/auto` — Detecció automàtica de document

```http
POST /ocr/auto
```

El servei detecta automàticament si la imatge és un DNI, Permís, Passaport, etc.
i aplica el parser corresponent. Resposta idèntica al contracte v1 però sense
que el client hagi de saber el tipus prèviament.

**Implementació**: heurística per keywords ("PERMISO DE CIRCULACIÓN", "IDESP", etc.)

---

### 7. Refinament Claude text-only (confiança < 85)

**TODO** ja marcat al codi:

```python
# TODO: si result.confianza_global < 85 → Claude text-only per refinament
```

Quan un document passa Vision però té `confianza_global < 85`, enviar el text
OCR extret (no la imatge) a Claude per corregir/completar camps.
**Cost**: ~0.001$ per doc (text-only, molt econòmic).
**Impacte**: Milloraria el 5-10% de documents "difícils".

---

### 8. Documents internacionals

- Passaports internacionals (MRZ TD3 universal)
- ID Cards europees (MRZ TD1/TD2)
- NIE (tarjeta de residència) — ja parcialment suportat

---

## Prioritat Baixa

### 9. Cache de resultats

Evitar processar la mateixa imatge dues vegades:
- Hash SHA-256 de la imatge com a clau
- TTL 24h
- Storage: Redis, Cloud Memorystore o SQLite

**Cost estimat Vision sense cache** (1000 docs/mes): ~$1.5/mes
**Millora potencial**: 10-20% si els usuaris pugen la mateixa imatge

---

### 10. Documents empresarials

- **Factures**: número, import, IVA, data, proveïdor
- **Albarans**: número, productes, quantitats
- **Contractes**: dates, parts contractants (extracció parcial)

Requereix un enfocament diferent (documents variables, no formularis fixos).
Candidat ideal per al **refinament Claude text-only** (punt 7).

---

### 11. Dashboard d'estadístiques

```
GET /dashboard
```

Pàgina HTML simple amb:
- Requests per dia
- Cost per projecte (Google Vision vs Tesseract)
- Taux d'èxit per tipus de document
- Temps de resposta mig

---

## Costos Google Cloud Vision

```python
# Tarifes 2026
Primer 1.000 docs/mes:  GRATUÏT
1.001 – 5.000.000:      $1.50 per 1.000 docs  ($0.0015/doc)
5.000.001+:             $0.60 per 1.000 docs

# Arquitectura actual (només Vision)
1.000 docs/mes:   $0 (dins quota gratuïta)
2.000 docs/mes:   $1.50 (1.000 de pagament)
10.000 docs/mes:  $13.50
```

---

## KPIs a mesurar

| KPI | Objectiu | Actual |
|-----|----------|--------|
| `confianza_global` mig | ≥ 90 | ~95 ✅ |
| Taxa `valido: true` | ≥ 95% | ~98% ✅ |
| Temps resposta mig | ≤ 1s | ~0.6s ✅ |
| Cost per 1.000 docs | ≤ $1.50 | $1.50 ✅ |
| Uptime | ≥ 99% | - |

---

## Notes tècniques

- **Backward compatibility**: Contracte v1 és el nou estàndard. No mantenir v0.
- **Stateless**: El servei no guarda imatges ni dades de documents (RGPD).
- **Security first**: Logs no contenen PII (redactat al nivell del route).
- **Test coverage**: Qualsevol nou parser ha de tenir tests unitaris abans de fer-lo servir en producció.
