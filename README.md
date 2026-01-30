# Agent OCR - Document Processing API

API REST per processar documents espanyols (DNI i Permís de Circulació) utilitzant OCR amb Google Cloud Vision i Tesseract.

## Característiques

- **OCR d'alta precisió** amb Google Cloud Vision API (95% confidence)
- **Processament d'imatges** amb OpenCV (8 tècniques de preprocessament)
- **Parsers especialitzats** per DNI i Permís de Circulació
- **Comparació d'engines** OCR (Tesseract vs Google Vision)
- **API REST** amb FastAPI i documentació automàtica (Swagger)
- **Múltiples modes** de preprocessament: standard, aggressive, document
- **Stateless** - No requereix base de dades

## Documents suportats

### DNI Espanyol (Frontal i Posterior)
Extreu:
- DNI, nom complet, cognoms
- Data de naixement, data de caducitat
- Sexe, nacionalitat
- **Adreça completa**: carrer, número, població, província
- Lloc de naixement
- Pare, mare

### Permís de Circulació
Extreu:
- Matrícula
- Marca i model
- Cilindrada
- Número de bastidor
- Data de matriculació
- Titular

## Resultats de precisió

### Google Cloud Vision (Recomanat per producció)
- **Precisió**: 95% confidence
- **DNI**: 11/11 camps extrets correctament
- **Permís**: 7/7 camps extrets correctament
- **Ideal per**: Tots els documents

### Tesseract (PSM 6)
- **Precisió**: 66% confidence
- **DNI**: 6/11 camps (només MRZ, sense adreça ni dades familiars)
- **Permís**: Resultats inconsistents
- **Ideal per**: Testing/desenvolupament local

## Requisits

- Python 3.10+
- Tesseract OCR (opcional, per desenvolupament)
- **Google Cloud Vision API** (credencials obligatòries per producció)
- OpenCV

## Instal·lació

### 1. Clonar repositori

```bash
git clone <repository-url>
cd OCR
```

### 2. Crear entorn virtual

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# o
venv\Scripts\activate  # Windows
```

### 3. Instal·lar dependències

```bash
pip install -r requirements.txt
```

### 4. Instal·lar Tesseract (opcional)

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-spa tesseract-ocr-cat
```

**Windows:**
Descarregar i instal·lar des de: https://github.com/UB-Mannheim/tesseract/wiki

### 5. Configurar variables d'entorn

Copiar `.env.example` a `.env` i configurar:

```bash
cp .env.example .env
```

Editar `.env` amb les teves credencials de Google Cloud Vision (OBLIGATORI).

## Ús

### Iniciar servidor

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

El servidor estarà disponible a: http://localhost:8000

### Documentació API interactiva

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Exemples d'ús

#### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Resposta:**
```json
{
  "status": "healthy",
  "services": {
    "tesseract": true,
    "google_vision": true
  }
}
```

#### 2. Processar DNI

```bash
curl -X POST "http://localhost:8000/ocr/dni" \
  -F "file=@dni_frontal.jpg" \
  -F "preprocess=true" \
  -F "preprocess_mode=standard"
```

**Resposta:**
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

#### 3. Processar Permís de Circulació

```bash
curl -X POST "http://localhost:8000/ocr/permis" \
  -F "file=@permis.jpg"
```

**Resposta:**
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

#### 4. Comparar engines OCR

```bash
curl -X POST "http://localhost:8000/ocr/compare" \
  -F "file=@document.jpg" \
  -F "engines=tesseract" \
  -F "engines=google_vision" \
  -F "preprocess_modes=standard" \
  -F "preprocess_modes=aggressive"
```

**Resposta:**
```json
{
  "success": true,
  "message": "Comparació completada: 4 combinacions testades",
  "results": [
    {
      "engine": "tesseract",
      "preprocess_mode": "standard",
      "text": "Text extret...",
      "confidence": 66.8,
      "processing_time": 0.842,
      "success": true
    },
    {
      "engine": "google_vision",
      "preprocess_mode": "standard",
      "text": "Text extret amb millor precisió...",
      "confidence": 95.0,
      "processing_time": 1.234,
      "success": true
    }
  ],
  "recommendations": {
    "best_accuracy": "google_vision + standard (95.0% confiança)",
    "best_speed": "tesseract + standard (0.842s)",
    "best_balance": "google_vision + standard",
    "recommended_engine": "google_vision"
  }
}
```

## Modes de preprocessament

| Mode | Tècniques aplicades | Ús recomanat |
|------|-------------------|--------------|
| **none** | Cap preprocessament | Imatges d'alta qualitat |
| **standard** | Rotació + Contrast (CLAHE) | **Ús general (recomanat)** |
| **aggressive** | Rotació + Denoise + Contrast + Sharpen | Imatges de baixa qualitat |
| **document** | Detecció de límits + Perspectiva + Rotació | Documents inclinats o amb perspectiva |

## Tècniques de preprocessament (OpenCV)

1. **Detecció i correcció de rotació** - Hough Transform per detectar línies i calcular angle
2. **Millora de contrast** - CLAHE (Contrast Limited Adaptive Histogram Equalization)
3. **Eliminació de soroll** - fastNlMeansDenoisingColored
4. **Binarització adaptativa** - Adaptive Threshold amb Gaussian
5. **Millora de nitidesa** - Sharpening kernel convolucional
6. **Redimensionament intel·ligent** - Resize màx. 2000px amb LANCZOS4
7. **Detecció de límits del document** - Canny Edge Detection + Contour detection
8. **Transformació de perspectiva** - Perspective Transform per enderreçar

Més detalls: [docs/IMAGE_PROCESSING.md](docs/IMAGE_PROCESSING.md)

## Exemples d'integració

### Des de JavaScript/TypeScript (Next.js, React, Node.js)

```javascript
async function processarDNI(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('preprocess', 'true');
  formData.append('preprocess_mode', 'standard');

  const response = await fetch('https://ocr-agent.up.railway.app/ocr/dni', {
    method: 'POST',
    body: formData
  });

  const result = await response.json();

  if (result.success) {
    console.log('DNI:', result.data.dni);
    console.log('Nom:', result.data.nom_complet);
    console.log('Adreça:', result.data.adreca_completa);
  }

  return result.data;
}
```

### Des de PHP (Laravel)

```php
use Illuminate\Support\Facades\Http;

$response = Http::attach(
    'file',
    file_get_contents($filePath),
    'dni.jpg'
)->post('https://ocr-agent.up.railway.app/ocr/dni', [
    'preprocess' => true,
    'preprocess_mode' => 'standard'
]);

$dniData = $response->json()['data'];
```

### Des de Python

```python
import requests

with open('dni.jpg', 'rb') as f:
    response = requests.post(
        'https://ocr-agent.up.railway.app/ocr/dni',
        files={'file': f},
        data={'preprocess': 'true', 'preprocess_mode': 'standard'}
    )

if response.json()['success']:
    dni_data = response.json()['data']
    print(f"DNI: {dni_data['dni']}")
    print(f"Nom: {dni_data['nom_complet']}")
```

## Estructura del projecte

```
OCR/
├── app/
│   ├── main.py                 # FastAPI app principal
│   ├── config.py               # Configuració i variables d'entorn
│   ├── models/                 # Models Pydantic
│   │   ├── dni_response.py
│   │   └── permis_response.py
│   ├── services/               # Serveis OCR i processament
│   │   ├── tesseract_service.py
│   │   ├── google_vision_service.py
│   │   └── image_processor.py
│   ├── parsers/                # Parsers de documents
│   │   ├── dni_parser.py
│   │   └── permis_parser.py
│   └── routes/                 # Endpoints API
│       ├── dni.py
│       ├── permis.py
│       └── compare.py
├── docs/                       # Documentació
│   ├── API.md
│   ├── DEPLOYMENT.md
│   ├── DEVELOPMENT.md
│   ├── IMAGE_PROCESSING.md
│   └── OCR_COMPARISON.md
├── tests/                      # Tests
├── Dockerfile                  # Docker per desplegament
├── docker-compose.yml          # Docker Compose per local
├── requirements.txt            # Dependències Python
├── .env.example               # Exemple de configuració
├── .gitignore                 # Fitxers ignorats per Git
└── README.md                  # Aquesta documentació
```

## Desplegament

### Railway (Recomanat)

Consulta la guia completa: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

```bash
# 1. Crear projecte a railway.app
# 2. Connectar repositori GitHub
# 3. Railway auto-detecta el Dockerfile
# 4. Configurar variables d'entorn al dashboard:
#    - GOOGLE_CLOUD_CREDENTIALS_JSON
#    - TESSERACT_ENABLED
#    - TESSERACT_LANG
# 5. Deploy automàtic
```

### Docker local

```bash
# Build
docker build -t ocr-agent .

# Run
docker run -p 8000:8000 \
  -e GOOGLE_CLOUD_CREDENTIALS_JSON='{"type":"service_account",...}' \
  ocr-agent
```

### Docker Compose

```bash
docker-compose up -d
```

## Desenvolupament

Consulta [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) per configurar l'entorn de desenvolupament.

## Documentació completa

- **[API.md](docs/API.md)** - Documentació completa de l'API REST
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Guia de desplegament a Railway
- **[DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Guia per desenvolupadors
- **[IMAGE_PROCESSING.md](docs/IMAGE_PROCESSING.md)** - Tècniques de preprocessament
- **[OCR_COMPARISON.md](docs/OCR_COMPARISON.md)** - Comparació de motors OCR

## Costos estimats

### Google Cloud Vision
- **Tier gratuït**: 1.000 unitats/mes ✅
- **Després del tier gratuït**: $1.50 per 1.000 unitats
- **Estimació per ús moderat**: ~$5-10/mes

### Railway (Hosting)
- **Hobby Plan**: $5/mes
- Inclou: 500 hores d'execució, desplegaments il·limitats

**Total estimat**: ~$10-15/mes per producció

## Seguretat

- Les credencials de Google Cloud Vision es guarden com a variable d'entorn
- **No es guarden imatges** - Tot el processament és en memòria
- Les imatges temporals s'eliminen automàticament després del processament
- CORS configurat per seguretat
- Servei completament stateless (sense base de dades)

## Tecnologies utilitzades

- **FastAPI** - Framework web modern i ràpid per Python
- **Google Cloud Vision API** - OCR avançat amb IA
- **Tesseract OCR** - Motor OCR open-source
- **OpenCV** - Processament d'imatges (cv2)
- **Pillow (PIL)** - Manipulació d'imatges
- **NumPy & SciPy** - Càlculs científics i processament de matrius
- **Pydantic** - Validació de dades i models
- **Uvicorn** - Servidor ASGI
- **Docker** - Containerització

## Roadmap

- [ ] Suport per més documents (NIE, Passaport, Factures, Contractes)
- [ ] Detecció automàtica del tipus de document
- [ ] Cache de resultats per optimitzar costos
- [ ] Dashboard d'estadístiques i mètriques
- [ ] Autenticació amb API keys
- [ ] Rate limiting avançat
- [ ] Webhooks per processos asíncrons
- [ ] Suport multi-idioma (actualment CAT/SPA/ENG)

## Llicència

© 2026 Kim Coll - Tots els drets reservats

## Autor

**Kim Coll**
Desenvolupador Independent
GoGestor

## Contacte

Per dubtes, suggeriments o col·laboracions:
- Email: kim@conekta.cat
- GitHub: Issues al repositori
# ocr
