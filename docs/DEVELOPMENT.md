# Guia de Desenvolupament - Agent OCR

Guia completa per configurar l'entorn de desenvolupament de l'Agent OCR.

## Taula de continguts

- [Requisits](#requisits)
- [Configuració inicial](#configuració-inicial)
- [Estructura del projecte](#estructura-del-projecte)
- [Desenvolupament local](#desenvolupament-local)
- [Testing](#testing)
- [Debugging](#debugging)
- [Code Style](#code-style)
- [Contribuir](#contribuir)

---

## Requisits

### Sistema operatiu

- macOS 12+ (recomanat)
- Ubuntu 20.04+ / Debian 11+
- Windows 10+ amb WSL2

### Software requerit

| Software | Versió mínima | Instal·lació |
|----------|--------------|--------------|
| Python | 3.10+ | https://www.python.org/downloads/ |
| pip | 21.0+ | Inclòs amb Python |
| Tesseract OCR | 5.0+ | Veure instruccions |
| Git | 2.30+ | https://git-scm.com/downloads |

### Eines recomanades

- **IDE**: VS Code amb extensions Python
- **API Testing**: Postman o Insomnia
- **Terminal**: iTerm2 (macOS), Windows Terminal (Windows)
- **Git client**: GitKraken, SourceTree, o línia de comandes

---

## Configuració inicial

### 1. Clonar repositori

```bash
# SSH (recomanat)
git clone git@github.com:<username>/OCR.git
cd OCR

# o HTTPS
git clone https://github.com/<username>/OCR.git
cd OCR
```

### 2. Crear entorn virtual

```bash
# Crear venv
python3 -m venv venv

# Activar venv
source venv/bin/activate  # macOS/Linux
# o
venv\Scripts\activate  # Windows
```

**Important**: Sempre activa el venv abans de treballar!

### 3. Instal·lar dependències

```bash
# Actualitzar pip
pip install --upgrade pip

# Instal·lar dependencies
pip install -r requirements.txt

# Verificar instal·lació
pip list
```

### 4. Instal·lar Tesseract

#### macOS (Homebrew)

```bash
# Instal·lar Tesseract
brew install tesseract

# Instal·lar idiomes
brew install tesseract-lang

# Verificar
tesseract --version
tesseract --list-langs
```

#### Ubuntu/Debian

```bash
# Instal·lar Tesseract
sudo apt-get update
sudo apt-get install -y tesseract-ocr

# Instal·lar idiomes
sudo apt-get install -y \
  tesseract-ocr-spa \
  tesseract-ocr-cat \
  tesseract-ocr-eng

# Verificar
tesseract --version
tesseract --list-langs
```

#### Windows

1. Descarregar des de: https://github.com/UB-Mannheim/tesseract/wiki
2. Executar instal·lador
3. Afegir al PATH: `C:\Program Files\Tesseract-OCR`
4. Descarregar language packs durant la instal·lació

### 5. Configurar variables d'entorn

```bash
# Copiar .env.example
cp .env.example .env

# Editar .env
nano .env  # o vim, code, etc.
```

**Configuració mínima per desenvolupament**:

```env
# .env
GOOGLE_CLOUD_VISION_ENABLED=true
GOOGLE_CLOUD_CREDENTIALS_JSON='{"type":"service_account",...}'
GOOGLE_CLOUD_PROJECT_ID=gogestor-ocr-485718

TESSERACT_ENABLED=true
TESSERACT_LANG=spa+cat+eng
```

**Obtenir credencials de Google Cloud Vision**: Veure [DEPLOYMENT.md](DEPLOYMENT.md#com-obtenir-les-credencials-de-google-cloud-vision)

### 6. Verificar configuració

```bash
# Executar servidor
uvicorn app.main:app --reload --port 8000

# En una altra terminal
curl http://localhost:8000/health
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "services": {
    "tesseract": true,
    "google_vision": true
  }
}
```

---

## Estructura del projecte

```
OCR/
├── app/                        # Codi principal de l'aplicació
│   ├── __init__.py
│   ├── main.py                 # FastAPI app i configuració CORS
│   ├── config.py               # Configuració i variables d'entorn
│   │
│   ├── models/                 # Models Pydantic (request/response)
│   │   ├── __init__.py
│   │   ├── dni_response.py     # Model DNI
│   │   └── permis_response.py  # Model Permís
│   │
│   ├── services/               # Serveis (business logic)
│   │   ├── __init__.py
│   │   ├── tesseract_service.py      # Wrapper Tesseract
│   │   ├── google_vision_service.py  # Wrapper Google Vision
│   │   └── image_processor.py        # Preprocessament OpenCV
│   │
│   ├── parsers/                # Parsers de documents
│   │   ├── __init__.py
│   │   ├── dni_parser.py       # Parser DNI (MRZ + full text)
│   │   └── permis_parser.py    # Parser Permís
│   │
│   └── routes/                 # Endpoints API
│       ├── __init__.py
│       ├── dni.py              # POST /ocr/dni
│       ├── permis.py           # POST /ocr/permis
│       └── compare.py          # POST /ocr/compare
│
├── docs/                       # Documentació
│   ├── README.md
│   ├── API.md
│   ├── DEPLOYMENT.md
│   ├── DEVELOPMENT.md          # Aquest fitxer
│   ├── IMAGE_PROCESSING.md
│   └── OCR_COMPARISON.md
│
├── tests/                      # Tests unitaris i d'integració
│   ├── __init__.py
│   ├── test_dni_parser.py
│   ├── test_permis_parser.py
│   └── test_api.py
│
├── .env                        # Variables d'entorn (NO commitir)
├── .env.example                # Exemple de variables
├── .gitignore                  # Fitxers ignorats per Git
├── Dockerfile                  # Docker per producció
├── docker-compose.yml          # Docker Compose per local
├── requirements.txt            # Dependències Python
└── README.md                   # Documentació principal
```

### Convencions de codi

- **Idioma**: Català per noms de variables i comentaris (Castellà/Anglès opcional)
- **Quotes**: Cometes dobles `"` per strings
- **Indentació**: 4 espais (no tabs)
- **Línia màxima**: 100 caràcters
- **Docstrings**: Estil Google

---

## Desenvolupament local

### Executar servidor en mode desenvolupament

```bash
# Amb auto-reload
uvicorn app.main:app --reload --port 8000

# Amb logs detallats
uvicorn app.main:app --reload --port 8000 --log-level debug

# Especificar host (per accedir des d'altres dispositius)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Endpoints de desenvolupament

- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health**: http://localhost:8000/health

### Hot reload

El servidor detecta canvis automàticament i es reinicia. Canvis detectats:
- Fitxers `.py` dins de `app/`
- Models, serveis, parsers, routes

**No es detecten canvis en**:
- `.env` (requereix reinici manual)
- Fitxers fora de `app/`

### Workflow típic

1. **Activar venv**:
   ```bash
   source venv/bin/activate
   ```

2. **Executar servidor**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

3. **Fer canvis al codi**

4. **Testar amb Swagger UI**: http://localhost:8000/docs

5. **Verificar logs** a la terminal

6. **Commit canvis**:
   ```bash
   git add .
   git commit -m "feat: descripció del canvi"
   git push
   ```

---

## Testing

### Testar amb Swagger UI

1. Obrir http://localhost:8000/docs
2. Seleccionar endpoint (ex: POST /ocr/dni)
3. Clic a **"Try it out"**
4. Pujar imatge
5. Configurar paràmetres
6. Clic a **"Execute"**
7. Veure resposta

### Testar amb cURL

```bash
# Health check
curl http://localhost:8000/health

# DNI
curl -X POST "http://localhost:8000/ocr/dni" \
  -F "file=@test-images/dni-frontal.jpg" \
  -F "preprocess=true" \
  -F "preprocess_mode=standard"

# Permís
curl -X POST "http://localhost:8000/ocr/permis" \
  -F "file=@test-images/permis.jpg"

# Comparar
curl -X POST "http://localhost:8000/ocr/compare" \
  -F "file=@test-images/document.jpg" \
  -F "engines=tesseract" \
  -F "engines=google_vision" \
  -F "preprocess_modes=standard"
```

### Tests unitaris (pytest)

```bash
# Instal·lar pytest
pip install pytest pytest-cov

# Executar tots els tests
pytest

# Amb coverage
pytest --cov=app tests/

# Test específic
pytest tests/test_dni_parser.py

# Amb output detallat
pytest -v -s
```

**Exemple de test**:

```python
# tests/test_dni_parser.py
from app.parsers.dni_parser import DNIParser

def test_validate_dni_valid():
    assert DNIParser.validate_dni("77612097T") == True

def test_validate_dni_invalid():
    assert DNIParser.validate_dni("12345678A") == False

def test_parse_mrz():
    text = """
    IDESPBHV122738077612097T<<<<<<
    7301245M2808288ESP<<<<<<<<<<<6
    COLL<CEREZO<<JOAQUIN<<<<<<<<<<
    """
    result = DNIParser.parse_mrz(text)

    assert result is not None
    assert result.dni == "77612097T"
    assert result.nom == "JOAQUIN"
    assert result.cognoms == "COLL CEREZO"
```

### Tests d'integració

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_dni_endpoint():
    with open("test-images/dni.jpg", "rb") as f:
        response = client.post(
            "/ocr/dni",
            files={"file": ("dni.jpg", f, "image/jpeg")}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert "dni" in data["data"]
```

---

## Debugging

### VS Code

Crear `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--port",
        "8000"
      ],
      "jinja": true,
      "justMyCode": true,
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

**Ús**:
1. Posar breakpoints al codi
2. Press F5 o Run → Start Debugging
3. El debugger s'aturarà als breakpoints

### Print debugging

```python
# app/parsers/dni_parser.py
def parse_mrz(text: str):
    print(f"📥 Input text:\n{text}")

    lines = text.split('\n')
    print(f"📋 Lines: {len(lines)}")

    mrz_lines = [line for line in lines if line.startswith('ID')]
    print(f"🔍 MRZ lines found: {len(mrz_lines)}")
    print(f"📄 MRZ lines: {mrz_lines}")

    # ...
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# app/services/google_vision_service.py
def detect_text(self, image_path: str):
    logger.info(f"Processant imatge: {image_path}")

    try:
        result = self.client.text_detection(image)
        logger.info(f"Text detectat: {len(result.text_annotations)} annotations")
        return result
    except Exception as e:
        logger.error(f"Error OCR: {e}", exc_info=True)
        raise
```

### Verificar preprocessament

```python
# app/services/image_processor.py
def process_for_ocr(image_path: str, mode: str = "standard"):
    image = cv2.imread(image_path)

    # Guardar imatge intermèdia per debug
    if os.getenv("DEBUG_IMAGES") == "true":
        debug_dir = "debug_images"
        os.makedirs(debug_dir, exist_ok=True)

        # Abans
        cv2.imwrite(f"{debug_dir}/01_original.jpg", image)

        # Després de rotació
        image = detect_and_fix_rotation(image)
        cv2.imwrite(f"{debug_dir}/02_rotation.jpg", image)

        # Després de contrast
        image = enhance_contrast(image)
        cv2.imwrite(f"{debug_dir}/03_contrast.jpg", image)

    return output_path
```

Activar:
```bash
export DEBUG_IMAGES=true
uvicorn app.main:app --reload
```

---

## Code Style

### Formatació

```bash
# Instal·lar black i isort
pip install black isort

# Formatar tot el codi
black app/
isort app/

# Verificar sense canviar
black --check app/
```

**Configuració black** (`.pyproject.toml`):
```toml
[tool.black]
line-length = 100
target-version = ['py310']
include = '\.pyi?$'
```

### Linting

```bash
# Instal·lar flake8
pip install flake8

# Executar
flake8 app/

# Ignorar errors específics
flake8 app/ --ignore=E501,W503
```

### Type hints

Usar type hints sempre que sigui possible:

```python
from typing import Optional, List, Dict

def parse_mrz(text: str) -> Optional[DNIData]:
    """
    Parseja la zona MRZ del DNI

    Args:
        text: Text extret per OCR

    Returns:
        DNIData o None si no es pot parsejar
    """
    # ...
    return dni_data
```

### Docstrings

Estil Google:

```python
def detect_text(self, image_path: str, lang: Optional[str] = None) -> dict:
    """
    Detecta text en una imatge amb Tesseract.

    Args:
        image_path: Path absolut a la imatge
        lang: Idiomes (ex: "spa+cat+eng"). Si None, usa config.

    Returns:
        Dict amb:
            - text (str): Text extret
            - confidence (float): Confiança 0-100

    Raises:
        RuntimeError: Si Tesseract no està disponible
        FileNotFoundError: Si la imatge no existeix
        Exception: Errors generals de Tesseract

    Example:
        >>> service = TesseractService()
        >>> result = service.detect_text("dni.jpg", lang="spa")
        >>> print(result["text"])
    """
    # ...
```

---

## Contribuir

### Git workflow

1. **Crear branch**:
   ```bash
   git checkout -b feat/nova-funcionalitat
   ```

2. **Fer canvis i commits**:
   ```bash
   git add .
   git commit -m "feat: afegir detecció de NIE"
   ```

3. **Push**:
   ```bash
   git push origin feat/nova-funcionalitat
   ```

4. **Crear Pull Request** a GitHub

### Commit message format

Usar [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>

[optional body]
```

**Types**:
- `feat`: Nova funcionalitat
- `fix`: Bug fix
- `docs`: Documentació
- `style`: Formatació (no canvia funcionalitat)
- `refactor`: Refactorització
- `test`: Tests
- `chore`: Tasques de manteniment

**Exemples**:
```bash
git commit -m "feat: afegir suport per NIE"
git commit -m "fix: solucionar error en parse_mrz amb DNIs sense adreça"
git commit -m "docs: actualitzar README amb exemples d'ús"
git commit -m "refactor: simplificar lògica de preprocessament"
```

### Pre-commit hooks

```bash
# Instal·lar pre-commit
pip install pre-commit

# Configurar hooks
pre-commit install

# Executar manualment
pre-commit run --all-files
```

**`.pre-commit-config.yaml`**:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

---

## Recursos

### Documentació oficial

- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/)
- [OpenCV](https://docs.opencv.org/)
- [Tesseract](https://tesseract-ocr.github.io/)
- [Google Cloud Vision](https://cloud.google.com/vision/docs)

### Llibreries utilitzades

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `pytesseract` - Tesseract wrapper
- `google-cloud-vision` - Google Vision wrapper
- `opencv-python-headless` - Image processing
- `pillow` - Image manipulation
- `numpy` - Array operations

### Community

- [FastAPI Discord](https://discord.gg/fastapi)
- [Python Discord](https://discord.gg/python)

---

## Troubleshooting

### venv no s'activa

**macOS/Linux**:
```bash
# Verificar que existeix
ls venv/bin/activate

# Activar amb path complet
source $(pwd)/venv/bin/activate
```

**Windows**:
```powershell
# Si error "execution policy"
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Activar
.\venv\Scripts\activate
```

### Tesseract no es troba

**Error**: `TesseractNotFoundError: tesseract is not installed`

**Solució**:
```bash
# macOS
brew install tesseract

# Ubuntu
sudo apt-get install tesseract-ocr

# Verificar PATH
which tesseract

# Afegir al PATH si cal (macOS)
export PATH="/opt/homebrew/bin:$PATH"
```

### Google Vision error de credencials

**Error**: `DefaultCredentialsError`

**Solució**:
1. Verificar que `.env` té `GOOGLE_CLOUD_CREDENTIALS_JSON`
2. Verificar que el JSON és vàlid:
   ```bash
   echo $GOOGLE_CLOUD_CREDENTIALS_JSON | jq .
   ```
3. Verificar que el project_id és correcte

### Port 8000 ja en ús

```bash
# Trobar procés
lsof -i :8000

# Matar procés
kill -9 <PID>

# o usar un port diferent
uvicorn app.main:app --reload --port 8001
```

---

## Contacte

Per preguntes sobre desenvolupament:
- **Email**: kim@conekta.cat
- **GitHub**: https://github.com/<username>/OCR

---

**Happy coding!** 🚀
