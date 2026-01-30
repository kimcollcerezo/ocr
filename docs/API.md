# Documentació API - Agent OCR

Aquesta és la documentació completa de l'API REST de l'Agent OCR.

## Base URL

```
Desenvolupament: http://localhost:8000
Producció: https://ocr-production-abec.up.railway.app
```

## Autenticació

Tots els endpoints de processament (DNI, Permís) requereixen autenticació amb API Key.

### API Key Header

```http
X-API-Key: your-api-key-here
```

### Endpoints públics (sense autenticació)

- `GET /` - Root endpoint
- `GET /health` - Health check

### Endpoints protegits amb API Key

- `GET /docs` - Documentació Swagger (requereix API Key)
- `GET /redoc` - Documentació ReDoc (requereix API Key)
- `POST /ocr/dni` - Processar DNI
- `POST /ocr/permis` - Processar Permís de Circulació

## Documentació interactiva

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

---

## Endpoints

### 1. Health Check

Verifica l'estat del servei i la disponibilitat dels motors OCR.

#### Request

```http
GET /health
```

#### Response

```json
{
  "status": "healthy",
  "services": {
    "tesseract": true,
    "google_vision": true
  }
}
```

#### Status Codes

| Code | Description |
|------|-------------|
| 200 | Servei funcionant correctament |
| 503 | Un o més serveis no disponibles |

#### Example

```bash
curl http://localhost:8000/health
```

---

### 2. Processar DNI

Processa una imatge de DNI (frontal o posterior) i extreu les dades estructurades.

#### Request

```http
POST /ocr/dni
Content-Type: multipart/form-data
X-API-Key: your-api-key-here
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| file | File | ✅ Sí | - | Imatge del DNI (JPG, PNG) |
| preprocess | Boolean | ❌ No | true | Activar preprocessament |
| preprocess_mode | String | ❌ No | standard | Mode de preprocessament: `standard`, `aggressive`, `document`, `none` |

#### Response

```json
{
  "success": true,
  "message": "DNI processat correctament",
  "data": {
    "dni": "77612097T",
    "nom": "JOAQUIN",
    "cognoms": "COLL CEREZO",
    "nom_complet": "JOAQUIN COLL CEREZO",
    "data_naixement": "24/01/1973",
    "data_caducitat": "28/08/2028",
    "sexe": "Home",
    "nacionalitat": "ESP",
    "carrer": "CARRER VENDRELL",
    "numero": "5",
    "poblacio": "CABRILS",
    "provincia": "BARCELONA",
    "adreca_completa": "CARRER VENDRELL 5, CABRILS, BARCELONA",
    "lloc_naixement": "BARCELONA",
    "pare": "COLL BATLLE RAMON",
    "mare": "CEREZO MARTINEZ MARIA ISABEL",
    "confidence": 95.0,
    "ocr_engine": "google_vision"
  }
}
```

#### Camps de resposta

| Camp | Type | Description |
|------|------|-------------|
| dni | String | DNI amb lletra (8 dígits + 1 lletra) |
| nom | String | Nom de la persona |
| cognoms | String | Cognoms de la persona |
| nom_complet | String | Nom complet (nom + cognoms) |
| data_naixement | String | Data de naixement (DD/MM/YYYY) |
| data_caducitat | String | Data de caducitat del DNI (DD/MM/YYYY) |
| sexe | String | "Home" o "Dona" |
| nacionalitat | String | Codi de nacionalitat (normalment "ESP") |
| carrer | String | Nom del carrer |
| numero | String | Número del carrer |
| poblacio | String | Població/ciutat |
| provincia | String | Província |
| adreca_completa | String | Adreça completa formatada |
| lloc_naixement | String | Lloc de naixement |
| pare | String | Nom complet del pare |
| mare | String | Nom complet de la mare |
| confidence | Float | Confiança del OCR (0-100) |
| ocr_engine | String | Motor OCR usat: "google_vision" o "tesseract" |

**Nota**: Alguns camps poden ser `null` si no es poden extreure de la imatge.

#### Error Response

```json
{
  "success": false,
  "message": "No s'han pogut extreure dades del DNI",
  "data": {
    "dni": null,
    "nom": null,
    ...
  }
}
```

#### Status Codes

| Code | Description |
|------|-------------|
| 200 | DNI processat correctament |
| 400 | Fitxer invàlid (no és una imatge) |
| 401 | API key invàlida o no proporcionada |
| 500 | Error intern del servidor |
| 503 | Google Vision no disponible |

#### Examples

**cURL:**
```bash
curl -X POST "http://localhost:8000/ocr/dni" \
  -H "X-API-Key: your-api-key-here" \
  -F "file=@dni_frontal.jpg" \
  -F "preprocess=true" \
  -F "preprocess_mode=standard"
```

**JavaScript/TypeScript:**
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('preprocess', 'true');
formData.append('preprocess_mode', 'standard');

const response = await fetch('http://localhost:8000/ocr/dni', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your-api-key-here'
  },
  body: formData
});

const result = await response.json();
console.log(result.data);
```

**Python:**
```python
import requests

headers = {'X-API-Key': 'your-api-key-here'}

with open('dni.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/ocr/dni',
        headers=headers,
        files={'file': f},
        data={'preprocess': 'true', 'preprocess_mode': 'standard'}
    )

data = response.json()['data']
print(f"DNI: {data['dni']}")
```

---

### 3. Processar Permís de Circulació

Processa una imatge del Permís de Circulació i extreu les dades del vehicle.

#### Request

```http
POST /ocr/permis
Content-Type: multipart/form-data
X-API-Key: your-api-key-here
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| file | File | ✅ Sí | - | Imatge del permís (JPG, PNG) |
| preprocess | Boolean | ❌ No | true | Activar preprocessament |
| preprocess_mode | String | ❌ No | standard | Mode de preprocessament |

#### Response

```json
{
  "success": true,
  "message": "Permís processat correctament",
  "data": {
    "matricula": "1177MTM",
    "marca": "TOYOTA",
    "model": "YARIS",
    "cilindrada": "1490",
    "bastidor": "YARKAAC3100018794",
    "data_matriculacio": "08/08/2024",
    "titular": "COLL CEREZO JOAQUIN",
    "confidence": 95.0,
    "ocr_engine": "google_vision"
  }
}
```

#### Camps de resposta

| Camp | Type | Description |
|------|------|-------------|
| matricula | String | Matrícula del vehicle |
| marca | String | Marca del vehicle |
| model | String | Model del vehicle |
| cilindrada | String | Cilindrada en cc |
| bastidor | String | Número de bastidor (VIN) |
| data_matriculacio | String | Data de primera matriculació (DD/MM/YYYY) |
| titular | String | Nom del titular |
| confidence | Float | Confiança del OCR (0-100) |
| ocr_engine | String | Motor OCR usat |

#### Status Codes

| Code | Description |
|------|-------------|
| 200 | Permís processat correctament |
| 400 | Fitxer invàlid |
| 500 | Error intern |
| 503 | Google Vision no disponible |

#### Examples

**cURL:**
```bash
curl -X POST "http://localhost:8000/ocr/permis" \
  -H "X-API-Key: your-api-key-here" \
  -F "file=@permis.jpg"
```

**JavaScript:**
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('http://localhost:8000/ocr/permis', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your-api-key-here'
  },
  body: formData
});

const result = await response.json();
console.log(result.data);
```

---

## Modes de preprocessament

### none
- **Descripció**: Cap preprocessament, imatge original
- **Ús**: Imatges d'alta qualitat, documents escanejats professionals
- **Velocitat**: ⚡⚡⚡ Molt ràpid
- **Precisió**: Depèn de la qualitat de la imatge

### standard (Recomanat)
- **Descripció**: Correcció de rotació + millora de contrast (CLAHE)
- **Ús**: Ús general, la majoria de documents
- **Velocitat**: ⚡⚡ Ràpid
- **Precisió**: ⭐⭐⭐ Alta

### aggressive
- **Descripció**: Eliminació de soroll + contrast + nitidesa
- **Ús**: Imatges de baixa qualitat, fotos amb poca llum
- **Velocitat**: ⚡ Més lent
- **Precisió**: ⭐⭐⭐⭐ Molt alta per imatges dolentes

### document
- **Descripció**: Detecció de límits + transformació de perspectiva
- **Ús**: Documents inclinats, fotos amb perspectiva
- **Velocitat**: ⚡ Més lent
- **Precisió**: ⭐⭐⭐⭐ Excel·lent per documents deformats

---

## Error Handling

### Error Response Format

Tots els errors segueixen aquest format:

```json
{
  "detail": "Error message"
}
```

o per errors de l'API custom:

```json
{
  "success": false,
  "message": "Error message",
  "data": null
}
```

### Common Errors

#### 400 Bad Request

**Causa**: Fitxer no vàlid

```json
{
  "detail": "El fitxer ha de ser una imatge"
}
```

**Solució**: Enviar una imatge vàlida (JPG, PNG, etc.)

#### 413 Request Entity Too Large

**Causa**: Imatge massa gran

**Solució**: Redimensionar la imatge a menys de 10MB

#### 422 Unprocessable Entity

**Causa**: Paràmetres incorrectes

```json
{
  "detail": [
    {
      "loc": ["body", "preprocess_mode"],
      "msg": "value is not a valid enumeration member; permitted: 'none', 'standard', 'aggressive', 'document'",
      "type": "type_error.enum"
    }
  ]
}
```

**Solució**: Revisar els paràmetres enviats

#### 500 Internal Server Error

**Causa**: Error intern del servidor

```json
{
  "detail": "Error processant DNI: ..."
}
```

**Solució**: Revisar logs del servidor, contactar suport

#### 503 Service Unavailable

**Causa**: Google Vision no disponible

```json
{
  "detail": "Google Vision no disponible"
}
```

**Solució**: Verificar credencials, revisar configuració

---

## Rate Limiting

**Actualment no implementat**

Recomanacions futures:
- 100 peticions/minut per IP
- 1.000 peticions/dia per API key

---

## Authentication

**Actualment no implementat**

Recomanacions futures:
- API keys per autenticar clients
- Header: `X-API-Key: <your-api-key>`

---

## CORS

CORS està activat per permetre peticions des de qualsevol origen.

**Configuració actual:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Per producció**, es recomana limitar els orígens:
```python
allow_origins=["https://gogestor.com", "https://app.gogestor.com"]
```

---

## Limits

| Límit | Valor |
|-------|-------|
| Mida màxima d'imatge | 10 MB |
| Formats acceptats | JPG, PNG, JPEG, WEBP |
| Timeout per petició | 30 segons |
| Concurrent requests | Il·limitat (limitat per recursos del servidor) |

---

## Best Practices

### 1. Optimitzar mida d'imatge

```javascript
// Redimensionar al client abans d'enviar
function resizeImage(file, maxWidth = 2000) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const ratio = maxWidth / img.width;
      canvas.width = maxWidth;
      canvas.height = img.height * ratio;

      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      canvas.toBlob((blob) => {
        resolve(new File([blob], file.name, { type: 'image/jpeg' }));
      }, 'image/jpeg', 0.9);
    };
    img.src = URL.createObjectURL(file);
  });
}

// Ús
const optimizedFile = await resizeImage(originalFile);
```

### 2. Gestionar errors

```typescript
async function processarDNISafe(file: File) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/ocr/dni', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error desconegut');
    }

    const result = await response.json();

    if (!result.success) {
      throw new Error(result.message);
    }

    return result.data;
  } catch (error) {
    console.error('Error processant DNI:', error);
    throw error;
  }
}
```

### 3. Cache de resultats

```typescript
// Cache al client per evitar processar la mateixa imatge múltiples vegades
const cache = new Map<string, any>();

async function processarDNIWithCache(file: File) {
  // Generar hash del fitxer
  const fileHash = await hashFile(file);

  // Comprovar cache
  if (cache.has(fileHash)) {
    console.log('Cache hit!');
    return cache.get(fileHash);
  }

  // Processar i guardar a cache
  const result = await processarDNI(file);
  cache.set(fileHash, result);

  return result;
}

async function hashFile(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
```

### 4. Retry amb backoff

```typescript
async function processarDNIWithRetry(file: File, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await processarDNI(file);
    } catch (error) {
      if (i === maxRetries - 1) throw error;

      // Exponential backoff
      const delay = Math.pow(2, i) * 1000;
      console.log(`Retry ${i + 1}/${maxRetries} després de ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
}
```

---

## SDK Clients

### TypeScript/JavaScript

```typescript
// ocr-client.ts
export class OCRClient {
  constructor(private baseURL: string) {}

  async processarDNI(file: File, options?: {
    preprocess?: boolean;
    preprocess_mode?: 'none' | 'standard' | 'aggressive' | 'document';
  }) {
    const formData = new FormData();
    formData.append('file', file);

    if (options?.preprocess !== undefined) {
      formData.append('preprocess', String(options.preprocess));
    }
    if (options?.preprocess_mode) {
      formData.append('preprocess_mode', options.preprocess_mode);
    }

    const response = await fetch(`${this.baseURL}/ocr/dni`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();

    if (!result.success) {
      throw new Error(result.message);
    }

    return result.data;
  }

  async processarPermis(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseURL}/ocr/permis`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();

    if (!result.success) {
      throw new Error(result.message);
    }

    return result.data;
  }

  async health() {
    const response = await fetch(`${this.baseURL}/health`);
    return response.json();
  }
}

// Ús
const client = new OCRClient('https://ocr-agent.up.railway.app');

const dniData = await client.processarDNI(file, {
  preprocess: true,
  preprocess_mode: 'standard'
});

console.log(dniData.dni);
```

---

## Changelog

### v1.0.0 (2026-01-30)
- Inicial release
- Suport per DNI espanyol (11 camps)
- Suport per Permís de Circulació (7 camps)
- 4 modes de preprocessament
- Comparació de motors OCR
- Google Cloud Vision + Tesseract

---

## Suport

Per problemes o preguntes sobre l'API:
- **Email**: kim@conekta.cat
- **GitHub Issues**: https://github.com/<username>/OCR/issues
