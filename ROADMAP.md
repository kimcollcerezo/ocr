# Roadmap — OCR Agent

**Última actualització**: 2026-02-18

---

## Estat actual (v1.0 — Contracte unificat)

### Implementat i en producció

| Funcionalitat | Estat | Notes |
|---------------|-------|-------|
| Parser DNI/NIE (frontal + posterior) | ✅ | MRZ + full-text, check digit, NIE X/Y/Z |
| Parser Permís de Circulació | ✅ | Codis EU D.1, P.1, C.1.x, VIN, matrícula |
| Tesseract-first → Vision fallback | ✅ | 1 sol crèdit Vision per document |
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

### 1. Actualitzar OcrService.php (GoGestor)

El servei de client PHP a GoGestor usa el format antic (`success/data`, camps en català).
Cal actualitzar-lo al contracte v1 (`valido`, `datos.numero_documento`, dates ISO).
**Veure**: `docs/GOGESTOR_INTEGRATION.md`

**Esforç estimat**: 2-4 hores · **Impacte**: Bloquejant per a integració GoGestor

---

### 2. Sistema de tracking d'ús

**Objectiu**: Saber quants documents processa cada projecte i calcular costos reals.

El middleware de logging ja escriu JSON a `/tmp/ocr_server.log`. El pas següent és
persistir les mètriques (motor OCR usat, `durada_ms`, `valido`) per projecte.

**Implementació mínima (SQLite)**:

```
ocr_usage.db
├── timestamp
├── project_id      (header X-Project-ID)
├── document_type   (dni | permiso_circulacion)
├── ocr_engine      (tesseract | google_vision)
├── confianza_global
├── valido
├── durada_ms
└── cost_usd        (calculat: Vision $0.0015/doc, Tesseract $0)
```

Nous endpoints: `GET /metrics/usage`, `GET /metrics/costs`

**Esforç estimat**: 1 dia · **Prioritat**: Alta (necessari per facturar)

---

### 3. Passaport espanyol

Estructura similar al DNI però amb MRZ de 2 línies (TD3):
- Número de passaport (format `AAA000000`)
- Dates ISO
- Mateixa arquitectura contracte v1

**Esforç estimat**: 1-2 dies

---

### 4. Permís de conduir espanyol

Camps: número permís, data expedició/caducitat, classes (A, B, C...), titular.
Atenció: el format varia molt entre generacions.

**Esforç estimat**: 2-3 dies

---

## Prioritat Mitjana

### 5. Endpoint `/ocr/auto` — Detecció automàtica de document

```http
POST /ocr/auto
```

El servei detecta automàticament si la imatge és un DNI, Permís, Passaport, etc.
i aplica el parser corresponent. Resposta idèntica al contracte v1 però sense
que el client hagi de saber el tipus prèviament.

**Implementació**: heurística per keywords ("PERMISO DE CIRCULACIÓN", "IDESP", etc.)

---

### 6. Refinament Claude text-only (confiança < 85)

**TODO** ja marcat al codi (`permis.py:146`, `dni.py:149`):

```python
# TODO: si result.confianza_global < 85 → Claude text-only per refinament
```

Quan un document passa Vision però té `confianza_global < 85`, enviar el text
OCR extret (no la imatge) a Claude per corregir/completar camps.
**Cost**: ~0.001$ per doc (text-only, molt econòmic).
**Impacte**: Milloraria el 5-10% de documents "difícils".

---

### 7. Documents internacionals

- Passaports internacionals (MRZ TD3 universal)
- ID Cards europees (MRZ TD1/TD2)
- NIE (tarjeta de residència) — ja parcialment suportat

---

## Prioritat Baixa

### 8. Cache de resultats

Evitar processar la mateixa imatge dues vegades:
- Hash SHA-256 de la imatge com a clau
- TTL 24h
- Storage: Redis o SQLite

**Cost estimat Vision sense cache** (1000 docs/mes): ~$1.5/mes
**Millora potencial**: 10-20% si els usuaris pugen la mateixa imatge

---

### 9. Documents empresarials

- **Factures**: número, import, IVA, data, proveïdor
- **Albarans**: número, productes, quantitats
- **Contractes**: dates, parts contractants (extracció parcial)

Requereix un enfocament diferent (documents variables, no formularis fixos).
Candidat ideal per al **refinament Claude text-only** (punt 6).

---

### 10. Dashboard d'estadístiques

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

# Estalvi Tesseract
Si Tesseract resol el 25% dels casos (DNI posterior amb MRZ net):
  1.000 docs → 750 Vision + 250 Tesseract = $1.125 en lloc de $1.50
```

---

## KPIs a mesurar

| KPI | Objectiu |
|-----|----------|
| `confianza_global` mig | ≥ 90 |
| Taxa `valido: true` | ≥ 95% |
| Temps resposta mig | ≤ 5s |
| % docs resolts per Tesseract | ≥ 20% (estalvi cost) |
| Cost per 1.000 docs | ≤ $1.20 |

---

## Notes tècniques

- **Backward compatibility**: Contracte v1 és el nou estàndard. No mantenir v0.
- **Stateless**: El servei no guarda imatges ni dades de documents (RGPD).
- **Security first**: Logs no contenen PII (redactat al nivell del route).
- **Test coverage**: Qualsevol nou parser ha de tenir tests unitaris abans de fer-lo servir en producció.
