# Guia Ràpida d'Integració — OCR Agent

> Connecta el teu projecte a l'API d'OCR per DNI i Permís de Circulació en 5 minuts.

---

## 1. URL Base

```
Producció: https://ocr-production-abec.up.railway.app
Local:     http://localhost:8000
```

---

## 2. Endpoints principals

### Processar DNI

```bash
POST /ocr/dni
Content-Type: multipart/form-data

Paràmetres:
  - file: <imatge JPG/PNG/WEBP>
  - preprocess: false (opcional)
  - preprocess_mode: "standard" (opcional)
```

### Processar Permís de Circulació

```bash
POST /ocr/permis
Content-Type: multipart/form-data

Paràmetres:
  - file: <imatge JPG/PNG/WEBP>
  - preprocess: false (opcional)
  - preprocess_mode: "standard" (opcional)
```

---

## 3. Resposta (contracte unificat v1)

**Tots els endpoints retornen el mateix format:**

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

### Camps clau

| Camp | Descripció |
|------|------------|
| `valido` | `true` si el document és vàlid (sense errors crítics) |
| `confianza_global` | Puntuació 0-100 de qualitat de lectura |
| `datos` | Objecte amb les dades extretes (veure §4 i §5) |
| `errores_detectados` | Llista d'errors trobats |
| `alertas` | Llista d'avisos (no bloquegen la validesa) |

---

## 4. Camps DNI (`datos`)

```typescript
{
  numero_documento: string | null;      // "77612097T"
  tipo_numero: "DNI" | "NIE" | null;    // "DNI"
  nombre: string | null;                // "JOAQUIN"
  apellidos: string | null;             // "COLL CEREZO"
  nombre_completo: string | null;       // "JOAQUIN COLL CEREZO"
  sexo: "M" | "F" | "X" | null;         // "M"
  nacionalidad: string | null;          // "ESP"
  fecha_nacimiento: string | null;      // "1973-01-24" (ISO)
  fecha_caducidad: string | null;       // "2028-08-28" (ISO)
  domicilio: string | null;             // "CARRER VENDRELL 5"
  municipio: string | null;             // "CABRILS"
  provincia: string | null;             // "BARCELONA"
  codigo_postal: string | null;         // "08348"
}
```

---

## 5. Camps Permís de Circulació (`datos`)

```typescript
{
  matricula: string | null;                    // "1177MTM"
  numero_bastidor: string | null;              // "YARKAAC3100018794" (VIN)
  marca: string | null;                        // "TOYOTA"
  modelo: string | null;                       // "TOYOTA YARIS"
  categoria: string | null;                    // "M1"
  tipo_vehiculo: string | null;                // "Turisme" (inferit)

  // Titular
  titular_nombre: string | null;               // "JOAQUIN COLL CEREZO"
  titular_nif: string | null;                  // "77612097T"

  // Motor
  cilindrada_cc: number | null;                // 1490
  potencia_kw: number | null;                  // 92.0
  potencia_fiscal: number | null;              // 125.1 (calculat)
  combustible: string | null;                  // "GASOLINA"
  emissions_co2: number | null;                // 120.5 (g/km)

  // Masses i capacitat
  masa_maxima: number | null;                  // kg
  masa_orden_marcha: number | null;            // kg
  plazas: number | null;                       // 5

  // Dates (totes en format ISO: YYYY-MM-DD)
  fecha_matriculacion: string | null;          // "2024-08-08"
  fecha_primera_matriculacion: string | null;  // "2024-07-01"
  fecha_ultima_transferencia: string | null;   // "2024-08-01"
  proxima_itv: string | null;                  // "2028-08-08"

  // Altres
  observaciones: string | null;                // Restriccions
}
```

---

## 6. Exemples d'integració

### JavaScript / TypeScript

```typescript
async function processarDNI(file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('https://ocr-production-abec.up.railway.app/ocr/dni', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }

  return response.json();
}

// Ús
const result = await processarDNI(fileInput.files[0]);

if (result.valido) {
  console.log('DNI:', result.datos.numero_documento);
  console.log('Nom:', result.datos.nombre_completo);
  console.log('Qualitat:', result.confianza_global);
} else {
  console.error('Errors:', result.errores_detectados);
}
```

### Python

```python
import httpx

def processar_dni(image_path: str) -> dict:
    with open(image_path, "rb") as f:
        response = httpx.post(
            "https://ocr-production-abec.up.railway.app/ocr/dni",
            files={"file": (image_path, f, "image/jpeg")},
        )
    response.raise_for_status()
    return response.json()

# Ús
result = processar_dni("dni.jpg")

if result["valido"]:
    print(f"DNI: {result['datos']['numero_documento']}")
    print(f"Nom: {result['datos']['nombre_completo']}")
else:
    for error in result["errores_detectados"]:
        print(f"[{error['severity']}] {error['message']}")
```

### PHP

```php
<?php
function processarDNI(string $imagePath): array {
    $curl = curl_init();
    curl_setopt_array($curl, [
        CURLOPT_URL            => 'https://ocr-production-abec.up.railway.app/ocr/dni',
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
    echo "DNI: " . $result['datos']['numero_documento'] . "\n";
    echo "Nom: " . $result['datos']['nombre_completo'] . "\n";
} else {
    foreach ($result['errores_detectados'] as $error) {
        echo "[{$error['severity']}] {$error['message']}\n";
    }
}
```

### cURL (testing ràpid)

```bash
# DNI
curl -X POST "https://ocr-production-abec.up.railway.app/ocr/dni" \
  -F "file=@dni.jpg" | jq

# Permís
curl -X POST "https://ocr-production-abec.up.railway.app/ocr/permis" \
  -F "file=@permis.jpg" | jq

# Amb preprocessament
curl -X POST "https://ocr-production-abec.up.railway.app/ocr/dni" \
  -F "file=@dni.jpg" \
  -F "preprocess=true" \
  -F "preprocess_mode=aggressive" | jq
```

---

## 7. Validació de resultats

```typescript
function avaluarOCR(result: any): string {
  if (!result.valido) {
    return 'INVÀLID';
  }

  if (result.confianza_global >= 90) {
    return 'EXCEL·LENT';
  } else if (result.confianza_global >= 70) {
    return 'BON - Revisar manualment';
  } else {
    return 'BAIX - Requerit revisió';
  }
}
```

---

## 8. Codis d'error comuns

### DNI

| Codi | Significat |
|------|------------|
| `DNI_NUMBER_INVALID` | Format DNI/NIE invàlid |
| `DNI_CHECKLETTER_MISMATCH` | Lletra de control incorrecta |
| `DNI_EXPIRED` | Document caducat |
| `DNI_UNDERAGE` | Titular menor d'edat |

### Permís

| Codi | Significat |
|------|------------|
| `VEH_PLATE_INVALID` | Format matrícula invàlid |
| `VEH_VIN_INVALID_LENGTH` | VIN sense 17 caràcters |
| `VEH_MISSING_FIELD` | Camp obligatori absent |
| `VEH_DATES_INCONSISTENT` | Dates incoherents |

---

## 9. Límits del servei

| Paràmetre | Valor |
|-----------|-------|
| Mida màxima per imatge | 5 MB |
| Formats acceptats | JPG, PNG, WEBP |
| Timeout | 30 segons |
| Resolució mínima recomanada | 1000px amplada o 300 dpi |

---

## 10. Bones pràctiques

✅ **Fes:**
- Comprovar sempre `valido` abans de processar les dades
- Revisar `confianza_global` per decidir si cal revisió manual
- Gestionar errors HTTP (400, 413, 504) amb retry logic
- Redimensionar imatges grans al client abans d'enviar

❌ **No facis:**
- Assumir que tots els camps estaran presents (poden ser `null`)
- Ignorar els `errores_detectados` encara que `valido: true`
- Enviar imatges > 5 MB sense redimensionar
- Processar dates sense validar que no siguin `null`

---

## 11. Health Check

```bash
GET /health

Response:
{
  "status": "healthy",
  "services": {
    "tesseract": true,
    "google_vision": true
  }
}
```

---

## Suport i documentació completa

- **Documentació completa**: [docs/API.md](./API.md)
- **Integració Laravel/PHP**: [docs/GOGESTOR_INTEGRATION.md](./GOGESTOR_INTEGRATION.md)
- **Suport tècnic**: kim@conekta.cat
- **Swagger UI**: https://ocr-production-abec.up.railway.app/docs

---

## Changelog

| Data | Canvis |
|------|--------|
| 2026-02-23 | Afegits camps: `emissions_co2`, `tipo_vehiculo`, `fecha_ultima_transferencia` |
| 2026-02-18 | v1.0 — Contracte unificat amb `valido` i `confianza_global` |
