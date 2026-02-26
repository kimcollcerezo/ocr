# Agent OCR — Documentació d'Implementació

> **Contracte unificat v1** — Tots els endpoints retornen la mateixa estructura base.
> Última actualització: 2026-02-26

---

## Taula de continguts

1. [Base URL i autenticació](#1-base-url-i-autenticació)
2. [Arquitectura i costos](#2-arquitectura-i-costos)
3. [Format de resposta unificat](#3-format-de-resposta-unificat)
4. [Endpoint: Health Check](#4-endpoint-health-check)
5. [Endpoint: DNI / NIE](#5-endpoint-dni--nie)
6. [Endpoint: Permís de Circulació](#6-endpoint-permís-de-circulació)
7. [Endpoint: NIF / TIF](#7-endpoint-nif--tif)
8. [Catàleg d'errors i alertes](#8-catàleg-derrors-i-alertes)
9. [Lògica de confianza_global](#9-lògica-de-confianza_global)
10. [Modes de preprocessament](#10-modes-de-preprocessament)
11. [Codis d'estat HTTP](#11-codis-destat-http)
12. [Exemples d'integració](#12-exemples-dintegració)
13. [Bones pràctiques](#13-bones-pràctiques)
14. [Límits del servei](#14-límits-del-servei)

---

## 1. Base URL i autenticació

```
Desenvolupament:  http://localhost:8000
Producció:        https://ocr-production-abec.up.railway.app
```

### Endpoints públics (sense autenticació)

| Mètode | Ruta      | Descripció                    |
|--------|-----------|-------------------------------|
| GET    | `/`       | Root (ping bàsic)             |
| GET    | `/health` | Estat del servei i motors OCR |

### Endpoints protegits (API Key)

| Mètode | Ruta          | Descripció                      |
|--------|---------------|---------------------------------|
| POST   | `/ocr/dni`    | Processar DNI o NIE             |
| POST   | `/ocr/permis` | Processar Permís de Circulació  |
| POST   | `/ocr/nif`    | Processar Targeta NIF/TIF       |
| GET    | `/docs`       | Swagger UI interactiu           |
| GET    | `/redoc`      | ReDoc interactiu                |

> **Nota**: L'autenticació per API Key no està activada en l'entorn de desenvolupament.
> En producció s'afegirà el header `X-API-Key: <your-api-key>`.

---

## 2. Arquitectura i costos

L'agent utilitza un sistema de **doble passada sense cost extra**:

```
Imatge rebuda
     │
     ▼
┌─────────────┐
│  Tesseract  │  (gratuït, local, ~0-16 s)
│  (intent 1) │
└──────┬──────┘
       │
       ├─ OK (matrícula/DNI vàlid + confiança ≥ 50) ──► Retorna resultat
       │
       └─ Fallback ──►
                    ┌──────────────────┐
                    │  Google Vision   │  (1 crèdit per document)
                    │  (intent 2)      │
                    └────────┬─────────┘
                             │
                    Extracció (Phase 1): Python regex
                             │
                    Validació (Phase 2): Python pur (0 crèdits extra)
                             │
                             ▼
                    Retorna resultat
```

**Garantia de cost**: Google Vision s'utilitza **com a màxim 1 cop per petició**.
La Phase 2 (validació creuada, coherència de camps, codis d'error) és lògica Python pura, sense crides addicionals a cap API externa.

### Fallback Tesseract → Vision

El sistema fa fallback a Vision si Tesseract troba:

| Document | Condicions de fallback |
|----------|------------------------|
| DNI/NIE  | `numero_documento` absent o check digit invàlid · `nombre` absent · confiança < 50 |
| Permís   | `matricula` absent o format invàlid · `marca` absent · confiança < 50 |

---

## 3. Format de resposta unificat

Tots els endpoints de processament retornen el mateix esquema base:

```json
{
  "valido": true,
  "confianza_global": 99,
  "tipo_documento": "dni",
  "datos": { ... },
  "alertas": [],
  "errores_detectados": [],
  "raw": {
    "ocr_engine": "google_vision",
    "ocr_confidence": 95.0
  },
  "meta": {
    "success": true,
    "message": "Document processat correctament"
  }
}
```

### Camps arrel

| Camp | Tipus | Descripció |
|------|-------|------------|
| `valido` | `boolean` | `true` si el document és vàlid (cap error crític, camps mínims presents) |
| `confianza_global` | `integer` 0–100 | Puntuació de qualitat composta (veure §8) |
| `tipo_documento` | `string` | `"dni"` o `"permiso_circulacion"` |
| `datos` | `object` | Dades específiques del document (veure §5 i §6) |
| `alertas` | `array<ValidationItem>` | Avisos no bloquejants (menor d'edat, soroll OCR…) |
| `errores_detectados` | `array<ValidationItem>` | Errors (poden fer `valido = false`) |
| `raw.ocr_engine` | `string` | `"tesseract"` o `"google_vision"` |
| `raw.ocr_confidence` | `float` | Confiança del motor OCR (0–100) |
| `meta.success` | `boolean` | Igual a `valido` (compatibilitat) |
| `meta.message` | `string \| null` | Missatge llegible per l'usuari |

### ValidationItem

Estructura comuna per a `alertas` i `errores_detectados`:

```json
{
  "code": "DNI_EXPIRED",
  "severity": "error",
  "field": "fecha_caducidad",
  "message": "Document caducat (2020-01-01)",
  "evidence": "2020-01-01",
  "suggested_fix": "Sol·licitar renovació del document"
}
```

| Camp | Tipus | Descripció |
|------|-------|------------|
| `code` | `string` | Codi únic (veure §7) |
| `severity` | `"warning" \| "error" \| "critical"` | Gravetat |
| `field` | `string \| null` | Camp afectat |
| `message` | `string` | Text llegible en català/castellà |
| `evidence` | `string \| null` | Valor llegit que genera el problema |
| `suggested_fix` | `string \| null` | Recomanació d'acció |

**Regla `valido`**: El document és invàlid si conté **almenys un error de severitat `"critical"`** o si falta algun camp mínim obligatori.
Les `alertas` (severity `"warning"`) **no invaliden** el document.

---

## 4. Endpoint: Health Check

```http
GET /health
```

### Resposta

```json
{
  "status": "healthy",
  "services": {
    "tesseract": true,
    "google_vision": true
  }
}
```

| Estat | HTTP | Descripció |
|-------|------|------------|
| Tot OK | 200 | Tots els motors disponibles |
| Parcial | 200 | Servei funciona però algun motor pot no estar disponible |
| Error | 503 | Servei no disponible |

---

## 5. Endpoint: DNI / NIE

### Request

```http
POST /ocr/dni
Content-Type: multipart/form-data
```

| Paràmetre | Tipus | Obligatori | Default | Descripció |
|-----------|-------|------------|---------|------------|
| `file` | File | Sí | — | Imatge del DNI (JPG, PNG, WEBP) |
| `preprocess` | boolean | No | `false` | Activar preprocessament d'imatge |
| `preprocess_mode` | string | No | `"standard"` | `standard` · `aggressive` · `document` |

### Resposta: camps `datos`

```json
{
  "datos": {
    "numero_documento": "77612097T",
    "tipo_numero": "DNI",
    "nombre": "JOAQUIN",
    "apellidos": "COLL CEREZO",
    "nombre_completo": "JOAQUIN COLL CEREZO",
    "sexo": "M",
    "nacionalidad": "ESP",
    "fecha_nacimiento": "1973-01-24",
    "fecha_expedicion": null,
    "fecha_caducidad": "2028-08-28",
    "domicilio": "CARRER VENDRELL 5",
    "calle": "CARRER VENDRELL",
    "numero": "5",
    "piso_puerta": null,
    "municipio": "CABRILS",
    "provincia": "BARCELONA",
    "codigo_postal": "08348",
    "nombre_padre": null,
    "nombre_madre": null,
    "lugar_nacimiento": null,
    "soporte_numero": null,
    "mrz": {
      "raw": "IDESPBHV122738077612097T\n7301245M2808288ESP\nCOLL<CEREZO<<JOAQUIN",
      "document_number": "77612097T",
      "surname": "COLL CEREZO",
      "name": "JOAQUIN",
      "nationality": "ESP",
      "birth_date": "730124",
      "expiry_date": "280828",
      "sex": "M"
    }
  }
}
```

### Descripció de camps `datos`

| Camp | Tipus | Font | Descripció |
|------|-------|------|------------|
| `numero_documento` | `string \| null` | Frontal / MRZ | DNI (8 dígits + lletra) o NIE (X/Y/Z + 7 dígits + lletra) |
| `tipo_numero` | `"DNI" \| "NIE" \| null` | Inferit | Tipus detectat automàticament |
| `nombre` | `string \| null` | Frontal / MRZ | Nom de pila |
| `apellidos` | `string \| null` | Frontal / MRZ | Cognoms (1 o 2) |
| `nombre_completo` | `string \| null` | Calculat | `nombre + " " + apellidos` |
| `sexo` | `"M" \| "F" \| "X" \| null` | Frontal / MRZ | `M` = mascle, `F` = femella, `X` = no binari |
| `nacionalidad` | `string \| null` | Frontal / MRZ | Codi ISO 3166-1 alpha-3 (p.ex. `"ESP"`) |
| `fecha_nacimiento` | `string \| null` | Frontal / MRZ | Format ISO `YYYY-MM-DD` |
| `fecha_expedicion` | `string \| null` | Frontal | Format ISO `YYYY-MM-DD` |
| `fecha_caducidad` | `string \| null` | Frontal / MRZ | Format ISO `YYYY-MM-DD` |
| `domicilio` | `string \| null` | Posterior | Adreça completa (deprecated, usa `calle` + `numero` + `piso_puerta`) |
| `calle` | `string \| null` | Posterior | Nom del carrer (ex: "C. ARTAIL", "CRER. VENDRELL") |
| `numero` | `string \| null` | Posterior | Número del carrer (ex: "9", "5") |
| `piso_puerta` | `string \| null` | Posterior | Pis i porta (ex: "P02 0001", "1º A", "2n B") |
| `municipio` | `string \| null` | Posterior | Municipi |
| `provincia` | `string \| null` | Posterior | Província |
| `codigo_postal` | `string \| null` | Posterior | Codi postal |
| `nombre_padre` | `string \| null` | Posterior | Nom del pare (DNI antics) |
| `nombre_madre` | `string \| null` | Posterior | Nom de la mare (DNI antics) |
| `lugar_nacimiento` | `string \| null` | Posterior | Lloc de naixement |
| `soporte_numero` | `string \| null` | Posterior | Número de suport (rere) |
| `mrz` | `object \| null` | Posterior (MRZ) | Dades MRZ per a validació creuada |

> **Nota dates**: Totes les dates estan en format **ISO 8601** (`YYYY-MM-DD`). Les dates `null` signifiquen que no s'han pogut llegir de la imatge.

> **Nota adreça**: L'adreça del DNI posterior es retorna en camps separats:
> - `calle`: Nom del carrer (ex: "CRER. SALVADOR ESPRIU")
> - `numero`: Número del carrer (ex: "45")
> - `piso_puerta`: Pis i porta (ex: "P02 0001", "1º A", "2n B") o `null` si no consta
> - `codigo_postal`, `municipio`, `provincia`: Completen l'adreça
>
> El camp `domicilio` conté l'adreça completa però està **deprecated**. Utilitzar els camps separats.

### Exemple de resposta completa (DNI vàlid)

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
    "fecha_expedicion": null,
    "fecha_caducidad": "2028-08-28",
    "domicilio": null,
    "calle": null,
    "numero": null,
    "piso_puerta": null,
    "municipio": null,
    "provincia": null,
    "codigo_postal": null,
    "nombre_padre": null,
    "nombre_madre": null,
    "lugar_nacimiento": null,
    "soporte_numero": null,
    "mrz": null
  },
  "alertas": [],
  "errores_detectados": [],
  "raw": {
    "ocr_engine": "google_vision",
    "ocr_confidence": 95.0
  },
  "meta": {
    "success": true,
    "message": "Document processat correctament"
  }
}
```

### Exemple de resposta (DNI caducat amb menor d'edat)

```json
{
  "valido": false,
  "confianza_global": 55,
  "tipo_documento": "dni",
  "datos": {
    "numero_documento": "77612097T",
    "nombre": "MARIA",
    "apellidos": "GARCIA LOPEZ",
    "fecha_nacimiento": "2012-03-15",
    "fecha_caducidad": "2020-01-01"
  },
  "alertas": [
    {
      "code": "DNI_UNDERAGE",
      "severity": "warning",
      "field": "fecha_nacimiento",
      "message": "Titular menor d'edat (13 anys)",
      "evidence": "2012-03-15",
      "suggested_fix": null
    }
  ],
  "errores_detectados": [
    {
      "code": "DNI_EXPIRED",
      "severity": "error",
      "field": "fecha_caducidad",
      "message": "Document caducat (2020-01-01)",
      "evidence": "2020-01-01",
      "suggested_fix": "Sol·licitar renovació del document"
    }
  ],
  "raw": {
    "ocr_engine": "google_vision",
    "ocr_confidence": 95.0
  },
  "meta": {
    "success": false,
    "message": "Document invàlid"
  }
}
```

---

## 6. Endpoint: Permís de Circulació

### Request

```http
POST /ocr/permis
Content-Type: multipart/form-data
```

| Paràmetre | Tipus | Obligatori | Default | Descripció |
|-----------|-------|------------|---------|------------|
| `file` | File | Sí | — | Imatge del permís (JPG, PNG, WEBP) |
| `preprocess` | boolean | No | `false` | Activar preprocessament d'imatge |
| `preprocess_mode` | string | No | `"standard"` | `standard` · `aggressive` · `document` |

### Resposta: camps `datos`

```json
{
  "datos": {
    "numero_permiso": null,
    "matricula": "1177MTM",
    "numero_bastidor": "YARKAAC3100018794",
    "marca": "TOYOTA",
    "modelo": "TOYOTA YARIS",
    "variante_version": null,
    "categoria": "M1",
    "fecha_matriculacion": "2024-08-08",
    "fecha_primera_matriculacion": null,
    "fecha_expedicion": null,
    "titular_nombre": "JOAQUIN COLL CEREZO",
    "titular_nif": null,
    "domicilio": null,
    "municipio": null,
    "provincia": null,
    "codigo_postal": null,
    "servicio": null,
    "cilindrada_cc": 1490,
    "potencia_kw": 92.0,
    "potencia_fiscal": 125.1,
    "combustible": "GASOLINA",
    "emissions_co2": 120.5,
    "masa_maxima": null,
    "masa_orden_marcha": null,
    "plazas": 5,
    "tipo_vehiculo": "Turisme",
    "fecha_ultima_transferencia": null,
    "proxima_itv": "2028-08-08",
    "observaciones": null
  }
}
```

### Descripció de camps `datos`

| Camp | Tipus | Codi EU | Descripció |
|------|-------|---------|------------|
| `numero_permiso` | `string \| null` | — | Número del permís (si en té) |
| `matricula` | `string \| null` | A | Matrícula (4 dígits + 3 consonants, sense vocals ni Q) |
| `numero_bastidor` | `string \| null` | E | VIN: 17 caràcters, sense I/O/Q |
| `marca` | `string \| null` | D.1 | Marca del vehicle |
| `modelo` | `string \| null` | D.3 | Nom comercial del model |
| `variante_version` | `string \| null` | D.2 | Codi de variant/versió |
| `categoria` | `string \| null` | J | Categoria EU (M1, N1, L…) |
| `fecha_matriculacion` | `string \| null` | I | Data de matriculació actual (ISO) |
| `fecha_primera_matriculacion` | `string \| null` | B | Data de primera matriculació (ISO) |
| `fecha_expedicion` | `string \| null` | — | Data d'expedició del document (ISO) |
| `titular_nombre` | `string \| null` | C.1.1 | Nom complet del titular |
| `titular_nif` | `string \| null` | C.1.3 | NIF/NIE/CIF del titular |
| `domicilio` | `string \| null` | C.1.2 | Adreça del titular |
| `municipio` | `string \| null` | — | Municipi del titular |
| `provincia` | `string \| null` | — | Província del titular |
| `codigo_postal` | `string \| null` | — | Codi postal del titular |
| `servicio` | `string \| null` | — | Tipus de servei (P, A, T…) |
| `cilindrada_cc` | `integer \| null` | P.1 | Cilindrada en cc |
| `potencia_kw` | `float \| null` | P.2 | Potència màxima en kW |
| `potencia_fiscal` | `float \| null` | — | Calculada: `kW × 1.36` (fórmula DGT) |
| `combustible` | `string \| null` | P.3 | `GASOLINA`, `DIÈSEL`, `ELÈCTRIC`, `HÍBRID`… |
| `masa_maxima` | `integer \| null` | F.1 | Massa màxima autoritzada (kg) |
| `masa_orden_marcha` | `integer \| null` | G | Massa en ordre de marxa (kg) |
| `plazas` | `integer \| null` | S.1 | Nombre de places (incl. conductor) |
| `proxima_itv` | `string \| null` | — | Data propera ITV (ISO) |
| `observaciones` | `string \| null` | — | Restriccions o notes del document |

> **Notes importants**:
> - `potencia_fiscal` es calcula automàticament quan `potencia_kw` és present (fórmula oficial DGT: kW × 1.36).
> - Totes les dates estan en format **ISO 8601** (`YYYY-MM-DD`).
> - La `matricula` segueix el format espanyol modern: 4 dígits + 3 consonants del conjunt `BCDFGHJKLMNPRSTVWXYZ` (sense vocals ni Q).

### Exemple de resposta completa (Permís vàlid)

```json
{
  "valido": true,
  "confianza_global": 99,
  "tipo_documento": "permiso_circulacion",
  "datos": {
    "numero_permiso": null,
    "matricula": "1177MTM",
    "numero_bastidor": "YARKAAC3100018794",
    "marca": "TOYOTA",
    "modelo": "TOYOTA YARIS",
    "variante_version": null,
    "categoria": "M1",
    "fecha_matriculacion": "2024-08-08",
    "fecha_primera_matriculacion": null,
    "fecha_expedicion": null,
    "titular_nombre": "JOAQUIN COLL CEREZO",
    "titular_nif": null,
    "domicilio": null,
    "municipio": null,
    "provincia": null,
    "codigo_postal": null,
    "servicio": null,
    "cilindrada_cc": 1490,
    "potencia_kw": 92.0,
    "potencia_fiscal": 125.1,
    "combustible": "GASOLINA",
    "emissions_co2": 120.5,
    "masa_maxima": null,
    "masa_orden_marcha": null,
    "plazas": 5,
    "tipo_vehiculo": "Turisme",
    "fecha_ultima_transferencia": null,
    "proxima_itv": "2028-08-08",
    "observaciones": null
  },
  "alertas": [],
  "errores_detectados": [],
  "raw": {
    "ocr_engine": "google_vision",
    "ocr_confidence": 95.0
  },
  "meta": {
    "success": true,
    "message": "Document processat correctament"
  }
}
```

---

## 7. Endpoint: NIF / TIF

### Request

```http
POST /ocr/nif
Content-Type: multipart/form-data
```

| Paràmetre | Tipus | Obligatori | Default | Descripció |
|-----------|-------|------------|---------|------------|
| `file` | File | Sí | — | Imatge de la Targeta NIF (JPG, PNG, WEBP) |
| `preprocess` | boolean | No | `false` | Activar preprocessament d'imatge |
| `preprocess_mode` | string | No | `"standard"` | `standard` · `aggressive` · `document` |

### Resposta: camps `datos`

```json
{
  "datos": {
    "numero_nif": "B76261874",
    "tipo_nif": "CIF",
    "denominacion": "CASAACTIVA GESTION, S.L.",
    "razon_social": "CASAACTIVA GESTION, S.L.",
    "anagrama_comercial": null,
    "domicilio_social": null,
    "domicilio_social_calle": null,
    "domicilio_social_numero": null,
    "domicilio_social_piso_puerta": null,
    "domicilio_social_municipio": null,
    "domicilio_social_provincia": null,
    "domicilio_social_codigo_postal": null,
    "domicilio_fiscal": "CALLE ORINOCO, NUM. 5 PLANTA 0, PUERTA 3 35014 PALMAS DE GRAN CANARIA (LAS) - (PALMAS, LAS)",
    "domicilio_fiscal_calle": "CALLE ORINOCO",
    "domicilio_fiscal_numero": "5",
    "domicilio_fiscal_piso_puerta": "PLANTA 0, PUERTA 3",
    "domicilio_fiscal_municipio": "PALMAS DE GRAN CANARIA",
    "domicilio_fiscal_provincia": "LAS",
    "domicilio_fiscal_codigo_postal": "35014",
    "fecha_nif_definitivo": "2016-07-26",
    "fecha_expedicion": null,
    "administracion_aeat": "35601 PALMAS G.C",
    "codigo_administracion": "35601",
    "nombre_administracion": "PALMAS G.C",
    "codigo_electronico": "2DCB113CA7F63DC2"
  }
}
```

### Descripció de camps `datos`

| Camp | Tipus | Descripció |
|------|-------|------------|
| `numero_nif` | `string \| null` | NIF/CIF (1 lletra + 7 dígits + control) |
| `tipo_nif` | `"CIF" \| null` | Tipus de NIF (sempre "CIF" per entitats) |
| `denominacion` | `string \| null` | Denominació o raó social |
| `razon_social` | `string \| null` | Raó social (alias de `denominacion`) |
| `anagrama_comercial` | `string \| null` | Nom comercial de l'entitat |
| **Domicili Social** | | |
| `domicilio_social` | `string \| null` | Adreça completa del domicili social (registral) |
| `domicilio_social_calle` | `string \| null` | Carrer del domicili social |
| `domicilio_social_numero` | `string \| null` | Número del carrer |
| `domicilio_social_piso_puerta` | `string \| null` | Pis i porta |
| `domicilio_social_municipio` | `string \| null` | Municipi |
| `domicilio_social_provincia` | `string \| null` | Província |
| `domicilio_social_codigo_postal` | `string \| null` | Codi postal |
| **Domicili Fiscal (AEAT)** | | |
| `domicilio_fiscal` | `string \| null` | **Adreça completa del domicili fiscal (OBLIGATORI)** |
| `domicilio_fiscal_calle` | `string \| null` | Carrer del domicili fiscal |
| `domicilio_fiscal_numero` | `string \| null` | Número del carrer |
| `domicilio_fiscal_piso_puerta` | `string \| null` | Pis i porta |
| `domicilio_fiscal_municipio` | `string \| null` | Municipi |
| `domicilio_fiscal_provincia` | `string \| null` | Província |
| `domicilio_fiscal_codigo_postal` | `string \| null` | Codi postal |
| **Dates i AEAT** | | |
| `fecha_nif_definitivo` | `string \| null` | Data del NIF definitiu (ISO `YYYY-MM-DD`) |
| `fecha_expedicion` | `string \| null` | Data d'expedició del document (ISO) |
| `administracion_aeat` | `string \| null` | Administració AEAT completa (ex: "35601 PALMAS G.C") |
| `codigo_administracion` | `string \| null` | Codi de l'administració (ex: "35601") |
| `nombre_administracion` | `string \| null` | Nom de l'administració (ex: "PALMAS G.C") |
| `codigo_electronico` | `string \| null` | Codi electrònic de verificació (hex) |

> **Notes importants**:
> - El **domicili fiscal** és obligatori per a la validesa del document (`valido: true`).
> - El **domicili social** és opcional (només en alguns tipus de targetes).
> - La **validació CIF** utilitza l'**algoritme oficial AEAT** amb dígit de control calculat.
> - Totes les dates estan en format **ISO 8601** (`YYYY-MM-DD`).
> - Els tipus de NIF per la primera lletra:
>   - A = Societat Anònima
>   - B = Societat Limitada
>   - G = Associació o Fundació
>   - (veure [NIF_PARSER.md](./NIF_PARSER.md) per la llista completa)

### Exemple de resposta completa (NIF vàlid)

```json
{
  "valido": true,
  "confianza_global": 99,
  "tipo_documento": "nif",
  "datos": {
    "numero_nif": "B76261874",
    "tipo_nif": "CIF",
    "denominacion": "CASAACTIVA GESTION, S.L.",
    "razon_social": "CASAACTIVA GESTION, S.L.",
    "anagrama_comercial": null,
    "domicilio_social": null,
    "domicilio_social_calle": null,
    "domicilio_social_numero": null,
    "domicilio_social_piso_puerta": null,
    "domicilio_social_municipio": null,
    "domicilio_social_provincia": null,
    "domicilio_social_codigo_postal": null,
    "domicilio_fiscal": "CALLE ORINOCO, NUM. 5 PLANTA 0, PUERTA 3 35014 PALMAS DE GRAN CANARIA (LAS) - (PALMAS, LAS)",
    "domicilio_fiscal_calle": "CALLE ORINOCO",
    "domicilio_fiscal_numero": "5",
    "domicilio_fiscal_piso_puerta": "PLANTA 0, PUERTA 3",
    "domicilio_fiscal_municipio": "PALMAS DE GRAN CANARIA",
    "domicilio_fiscal_provincia": "LAS",
    "domicilio_fiscal_codigo_postal": "35014",
    "fecha_nif_definitivo": "2016-07-26",
    "fecha_expedicion": null,
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
  },
  "meta": {
    "success": true,
    "message": "[google_vision] Validació correcta"
  }
}
```

### Exemple de resposta (NIF invàlid - checkdigit incorrecte)

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
  "alertas": [],
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
  "raw": {
    "ocr_engine": "google_vision",
    "ocr_confidence": 90.0
  },
  "meta": {
    "success": false,
    "message": "[google_vision] Errors detectats"
  }
}
```

---

## 8. Catàleg d'errors i alertes

### Errors DNI/NIE

| Codi | Severitat | Camp | Descripció |
|------|-----------|------|------------|
| `DNI_MISSING_FIELD` | `critical` / `error` | Variable | Camp mínim absent (`numero_documento`, `nombre`, `apellidos`) |
| `DNI_NUMBER_INVALID` | `critical` | `numero_documento` | Format de DNI/NIE no reconegut |
| `DNI_CHECKLETTER_MISMATCH` | `critical` | `numero_documento` | Lletra de control incorrecta |
| `DNI_MRZ_MISMATCH` | `critical` | `mrz` | El número del document no coincideix entre text i MRZ |
| `DNI_BIRTHDATE_INVALID` | `critical` | `fecha_nacimiento` | Data de naixement fora de rang (1900–avui) |
| `DNI_EXPIRED` | `error` | `fecha_caducidad` | Document caducat |
| `DNI_UNDERAGE` | `warning` | `fecha_nacimiento` | Titular menor d'edat (< 18 anys) |
| `DNI_NAME_OCR_NOISE` | `warning` | `nombre` / `apellidos` | Caràcters estranys al nom (soroll OCR) |

### Errors Permís de Circulació

| Codi | Severitat | Camp | Descripció |
|------|-----------|------|------------|
| `VEH_MISSING_FIELD` | `critical` / `error` | Variable | Camp mínim absent (`matricula`, `marca`) |
| `VEH_PLATE_INVALID` | `critical` | `matricula` | Format de matrícula espanyola invàlid |
| `VEH_VIN_INVALID_LENGTH` | `critical` | `numero_bastidor` | VIN sense els 17 caràcters requerits |
| `VEH_VIN_INVALID_CHARS` | `critical` | `numero_bastidor` | VIN conté caràcters prohibits (I, O, Q) |
| `VEH_OWNER_ID_INVALID` | `error` | `titular_nif` | NIF/NIE/CIF del titular no vàlid |
| `VEH_DATES_INCONSISTENT` | `error` / `warning` | Dates | Primera matriculació posterior a la matriculació actual |
| `VEH_MASSES_INCONSISTENT` | `warning` | `masa_orden_marcha` | Massa en ordre de marxa ≥ massa màxima autoritzada |
| `VEH_POWER_RATIO_SUSPECT` | `warning` | `potencia_kw` | Ràtio kW/cc fora de rang plausible (0.02–0.20) |
| `VEH_VIN_CHECKDIGIT` | `warning` | `numero_bastidor` | Dígit de control VIN (NHTSA) no coincideix |
| `VEH_OCR_SUSPECT` | `warning` | Variable | Caràcters estranys en un camp (soroll OCR) |

### Errors NIF/TIF

| Codi | Severitat | Camp | Descripció |
|------|-----------|------|------------|
| `NIF_MISSING_FIELD` | `critical` | `numero_nif` | NIF/CIF no detectat |
| `NIF_MISSING_FIELD` | `error` | `razon_social`, `domicilio_fiscal` | Camps mínims absents |
| `NIF_CHECKDIGIT_MISMATCH` | `critical` | `numero_nif` | Dígit de control CIF incorrecte (algoritme AEAT) |
| `NIF_INVALID_FORMAT` | `critical` | `numero_nif` | Format NIF no reconegut |
| `NIF_DATE_INVALID` | `error` | `fecha_nif_definitivo`, `fecha_expedicion` | Data fora de rang (1980–avui) o en el futur |
| `NIF_OCR_NOISE` | `warning` | diversos | Caràcters inesperats (soroll OCR) |

> **Nota validació CIF**: El parser NIF utilitza l'**algoritme oficial AEAT** per validar el dígit de control del CIF, que és diferent de la validació DNI/NIE. Aquest algoritme calcula el dígit control segons la suma ponderada dels 7 dígits centrals i valida segons la primera lletra (A/B/E/H només dígit, K/P/Q/S només lletra, altres ambdós). Veure [NIF_PARSER.md](./NIF_PARSER.md) per més detalls.

### Criteris d'invalidació

```
valido = false  si:
  • qualsevol error de severitat "critical"
  • camp mínim absent (numero_documento/matricula + almenys un nom/marca)

valido = true   si:
  • cap error "critical"
  • camps mínims presents
  • pot tenir "warning" o "error" (no crítics) i seguir sent vàlid
```

---

## 9. Lògica de confianza_global

La puntuació final és una combinació de la lògica de validació i la confiança del motor OCR:

```
base = 100
  − 35 × (nombre d'errors "critical")
  − 15 × (nombre d'errors "error")
  −  5 × (nombre de "warning")
  − 20 × (nombre de camps mínims absents)

confianza_global = round(base × 0.85 + ocr_confidence × 0.15)
confianza_global = max(0, min(100, confianza_global))
```

**Interpretació orientativa**:

| Rang | Significat |
|------|------------|
| 90–100 | Excel·lent — document llegit amb alta fiabilitat |
| 70–89 | Bo — alguns camps poden ser imprecisos |
| 50–69 | Acceptable — revisió manual recomanable |
| 0–49 | Baix — molt probable que el document necessiti revisió |

> `confianza_global` no depèn de `valido`. Un document pot ser `valido: false` (p.ex. caducat) amb `confianza_global: 99` perquè s'ha llegit perfectament.

---

## 10. Modes de preprocessament

| Mode | Descripció | Cas d'ús | Velocitat |
|------|------------|----------|-----------|
| `standard` | Correcció de rotació + millora de contrast (CLAHE) | Ús general | Ràpid |
| `aggressive` | Eliminació de soroll + contrast + nitidesa | Imatges de baixa qualitat, poca llum | Moderat |
| `document` | Detecció de vores + transformació de perspectiva | Documents inclinats, fotos amb perspectiva | Lent |

> **Per defecte `preprocess=false`** (imatge original enviada directament a l'OCR).
> El preprocessament millora Tesseract en imatges difícils però és innecessari per a imatges netes.
> Google Vision tolera molt bé imatges sense preprocessar.

---

## 11. Codis d'estat HTTP

| HTTP | Situació |
|------|----------|
| `200 OK` | Document processat (pot ser `valido: false` per errors de contingut) |
| `400 Bad Request` | Format de fitxer no acceptat (no és JPG/PNG/WEBP) o magic bytes invàlids |
| `413 Payload Too Large` | Imatge > 5 MB |
| `422 Unprocessable Entity` | Paràmetres de query malformats |
| `500 Internal Server Error` | Error inesperat del servidor |
| `503 Service Unavailable` | Cap motor OCR disponible |
| `504 Gateway Timeout` | Timeout de 30 s procesant el document |

**Format d'error HTTP** (FastAPI estàndard):

```json
{
  "detail": "Format no suportat. Acceptem JPG, PNG o WEBP."
}
```

---

## 12. Exemples d'integració

### cURL

```bash
# DNI
curl -X POST "http://localhost:8000/ocr/dni" \
  -F "file=@dni_frontal.jpg"

# Permís de Circulació
curl -X POST "http://localhost:8000/ocr/permis" \
  -F "file=@permis.jpg"

# Amb preprocessament
curl -X POST "http://localhost:8000/ocr/dni" \
  -F "file=@dni.jpg" \
  -F "preprocess=true" \
  -F "preprocess_mode=aggressive"
```

### JavaScript / TypeScript

```typescript
// types.ts
interface ValidationItem {
  code: string;
  severity: 'warning' | 'error' | 'critical';
  field: string | null;
  message: string;
  evidence: string | null;
  suggested_fix: string | null;
}

interface RawOCR {
  ocr_engine: 'tesseract' | 'google_vision';
  ocr_confidence: number;
}

interface DNIDatos {
  numero_documento: string | null;
  tipo_numero: 'DNI' | 'NIE' | null;
  nombre: string | null;
  apellidos: string | null;
  nombre_completo: string | null;
  sexo: 'M' | 'F' | 'X' | null;
  nacionalidad: string | null;
  fecha_nacimiento: string | null;   // YYYY-MM-DD
  fecha_expedicion: string | null;
  fecha_caducidad: string | null;
  domicilio: string | null;          // Deprecated: usar calle + numero + piso_puerta
  calle: string | null;
  numero: string | null;
  piso_puerta: string | null;
  municipio: string | null;
  provincia: string | null;
  codigo_postal: string | null;
  nombre_padre: string | null;
  nombre_madre: string | null;
  lugar_nacimiento: string | null;
  soporte_numero: string | null;
}

interface DNIResponse {
  valido: boolean;
  confianza_global: number;
  tipo_documento: 'dni';
  datos: DNIDatos;
  alertas: ValidationItem[];
  errores_detectados: ValidationItem[];
  raw: RawOCR;
  meta: { success: boolean; message: string | null } | null;
}

interface PermisExtracted {
  numero_permiso: string | null;
  matricula: string | null;
  numero_bastidor: string | null;
  marca: string | null;
  modelo: string | null;
  variante_version: string | null;
  categoria: string | null;
  fecha_matriculacion: string | null;
  fecha_primera_matriculacion: string | null;
  fecha_expedicion: string | null;
  titular_nombre: string | null;
  titular_nif: string | null;
  domicilio: string | null;
  municipio: string | null;
  provincia: string | null;
  codigo_postal: string | null;
  servicio: string | null;
  cilindrada_cc: number | null;
  potencia_kw: number | null;
  potencia_fiscal: number | null;
  combustible: string | null;
  emissions_co2: number | null;          // V.7 g/km
  masa_maxima: number | null;
  masa_orden_marcha: number | null;
  plazas: number | null;
  tipo_vehiculo: string | null;          // Inferit: Turisme, Furgoneta...
  fecha_ultima_transferencia: string | null;
  proxima_itv: string | null;
  observaciones: string | null;
}

interface PermisResponse {
  valido: boolean;
  confianza_global: number;
  tipo_documento: 'permiso_circulacion';
  datos: PermisExtracted;
  alertas: ValidationItem[];
  errores_detectados: ValidationItem[];
  raw: RawOCR;
  meta: { success: boolean; message: string | null } | null;
}
```

```typescript
// ocr-client.ts
const OCR_BASE_URL = process.env.NEXT_PUBLIC_OCR_URL ?? 'http://localhost:8000';

async function processarDNI(file: File, preprocess = false): Promise<DNIResponse> {
  const form = new FormData();
  form.append('file', file);
  if (preprocess) {
    form.append('preprocess', 'true');
    form.append('preprocess_mode', 'standard');
  }

  const res = await fetch(`${OCR_BASE_URL}/ocr/dni`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(`OCR error ${res.status}: ${err.detail}`);
  }

  return res.json() as Promise<DNIResponse>;
}

async function processarPermis(file: File): Promise<PermisResponse> {
  const form = new FormData();
  form.append('file', file);

  const res = await fetch(`${OCR_BASE_URL}/ocr/permis`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(`OCR error ${res.status}: ${err.detail}`);
  }

  return res.json() as Promise<PermisResponse>;
}

// Ús
const dniResult = await processarDNI(fileInput.files[0]);

if (!dniResult.valido) {
  const criticals = dniResult.errores_detectados
    .filter(e => e.severity === 'critical')
    .map(e => e.message);
  console.error('Document invàlid:', criticals);
} else {
  console.log('DNI:', dniResult.datos.numero_documento);
  console.log('Nom:', dniResult.datos.nombre_completo);
  console.log('Qualitat:', dniResult.confianza_global, '/100');
}
```

### Python

```python
import httpx

OCR_BASE_URL = "http://localhost:8000"

def processar_dni(image_path: str) -> dict:
    with open(image_path, "rb") as f:
        response = httpx.post(
            f"{OCR_BASE_URL}/ocr/dni",
            files={"file": (image_path, f, "image/jpeg")},
        )
    response.raise_for_status()
    return response.json()

def processar_permis(image_path: str) -> dict:
    with open(image_path, "rb") as f:
        response = httpx.post(
            f"{OCR_BASE_URL}/ocr/permis",
            files={"file": (image_path, f, "image/jpeg")},
        )
    response.raise_for_status()
    return response.json()

# Ús
result = processar_dni("dni_frontal.jpg")

if result["valido"]:
    datos = result["datos"]
    print(f"DNI: {datos['numero_documento']}")
    print(f"Nom: {datos['nombre_completo']}")
    print(f"Qualitat: {result['confianza_global']}/100")
    print(f"Motor OCR: {result['raw']['ocr_engine']}")
else:
    errors = result["errores_detectados"]
    for e in errors:
        print(f"[{e['severity'].upper()}] {e['code']}: {e['message']}")

# Permís
permis = processar_permis("permis.jpg")
print(f"Matrícula: {permis['datos']['matricula']}")
print(f"Titular: {permis['datos']['titular_nombre']}")
print(f"ITV: {permis['datos']['proxima_itv']}")
```

### PHP

```php
<?php
function processarDNI(string $imagePath, string $baseUrl = 'http://localhost:8000'): array {
    $curl = curl_init();
    curl_setopt_array($curl, [
        CURLOPT_URL            => $baseUrl . '/ocr/dni',
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => ['file' => new CURLFile($imagePath)],
    ]);

    $response = curl_exec($curl);
    $httpCode = curl_getinfo($curl, CURLINFO_HTTP_CODE);
    curl_close($curl);

    if ($httpCode !== 200) {
        throw new RuntimeException("OCR error $httpCode");
    }

    return json_decode($response, true);
}

// Ús
$result = processarDNI('/tmp/dni.jpg');

if ($result['valido']) {
    $datos = $result['datos'];
    echo "DNI: " . $datos['numero_documento'] . "\n";
    echo "Nom: " . $datos['nombre_completo'] . "\n";
} else {
    foreach ($result['errores_detectados'] as $error) {
        echo "[{$error['severity']}] {$error['code']}: {$error['message']}\n";
    }
}
```

---

## 13. Bones pràctiques

### Qualitat d'imatge

- Resolució mínima recomanada: **300 dpi** (o ≥ 1000 px d'amplada)
- Formats preferits: **JPG** (qualitat ≥ 85) o **PNG** sense compressió
- Evitar: imatges borroses, fosques, amb reflexos o molt inclinades
- Límit de mida: **5 MB** per imatge

### Gestió de la resposta

```typescript
// Comprovar primer valido, després confianza_global
function avaluarOCR(result: DNIResponse | PermisResponse) {
  if (!result.valido) {
    // Hi ha errors crítics — mostrar a l'usuari
    const criticals = result.errores_detectados
      .filter(e => e.severity === 'critical');
    return { ok: false, reason: criticals[0]?.message ?? 'Document invàlid' };
  }

  if (result.confianza_global < 70) {
    // Vàlid però qualitat baixa — recomanar revisió manual
    return { ok: true, warning: 'Recomanem verificar les dades manualment' };
  }

  return { ok: true };
}
```

### Retry amb backoff

```typescript
async function ocrWithRetry<T>(fn: () => Promise<T>, maxRetries = 2): Promise<T> {
  for (let i = 0; i <= maxRetries; i++) {
    try {
      return await fn();
    } catch (err: any) {
      if (i === maxRetries || err.message.includes('400') || err.message.includes('413')) {
        throw err;  // No reintentar errors de client
      }
      await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i)));
    }
  }
  throw new Error('Max retries exceeded');
}

// Ús
const result = await ocrWithRetry(() => processarDNI(file));
```

### Optimitzar mida al client

```javascript
async function redimensionarImatge(file, maxPx = 2000) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const ratio = Math.min(1, maxPx / Math.max(img.width, img.height));
      const canvas = document.createElement('canvas');
      canvas.width  = Math.round(img.width  * ratio);
      canvas.height = Math.round(img.height * ratio);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(blob => resolve(new File([blob], file.name, { type: 'image/jpeg' })),
                    'image/jpeg', 0.92);
    };
    img.src = URL.createObjectURL(file);
  });
}

const optimitzat = await redimensionarImatge(originalFile);
const result = await processarDNI(optimitzat);
```

---

## 14. Límits del servei

| Paràmetre | Valor |
|-----------|-------|
| Mida màxima per imatge | 5 MB |
| Formats acceptats | `image/jpeg`, `image/png`, `image/webp` |
| Timeout per petició | 30 s |
| Concurrència Tesseract | 2 peticions simultànies |
| Concurrència Vision | Il·limitada (depenent de quota GCP) |
| Rate limiting | No implementat (pendent) |

---

## Changelog

| Versió | Data | Canvis |
|--------|------|--------|
| v1.1 — NIF/TIF | 2026-02-26 | Nou endpoint POST /ocr/nif · Parser NIF amb validació CIF completa (algoritme AEAT) · 2 domicilis (social + fiscal) amb components separats · Dates ISO · Contracte unificat v1 |
| v1.0 — Contracte unificat | 2026-02-18 | Resposta unificada (valido, confianza_global, ValidationItem) · Dates ISO · DNI+Permís paritat de funcions |
| v0.3 | 2026-01 | Tesseract-first + Vision fallback · Semàfor concurrència · JSON logging |
| v0.2 | 2026-01 | Parsers DNI millorats · MRZ parsing · VIN/matrícula validació |
| v0.1 | 2026-01 | Release inicial · Google Vision · 4 modes preprocessament |

---

**Suport**: kim@conekta.cat
