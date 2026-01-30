# Guia de Desplegament - Agent OCR

Aquesta guia cobreix el desplegament de l'Agent OCR a Railway, així com altres opcions de desplegament.

## Taula de continguts

- [Desplegament a Railway](#desplegament-a-railway)
- [Desplegament amb Docker](#desplegament-amb-docker)
- [Variables d'entorn](#variables-dentorn)
- [Verificació del desplegament](#verificació-del-desplegament)
- [Integració amb GoGestor](#integració-amb-gogestor)
- [Solució de problemes](#solució-de-problemes)

---

## Desplegament a Railway

Railway és la plataforma recomanada per desplegar l'Agent OCR. Ofereix desplegaments automàtics des de GitHub i és fàcil de configurar.

### Requisits previs

1. Compte de Railway: https://railway.app
2. Compte de GitHub amb el repositori de l'Agent OCR
3. Credencials de Google Cloud Vision (fitxer JSON)

### Arquitectura a Railway

```
Railway Project: ocr-production
│
├── Service: ocr-agent
│   ├── Source: GitHub repository
│   ├── Build: Dockerfile (auto-detectat)
│   ├── Port: 8000 (auto-detectat des de Dockerfile)
│   └── Public URL: https://ocr-production-abec.up.railway.app
│
└── Variables d'entorn:
    ├── GOOGLE_CLOUD_CREDENTIALS_JSON
    ├── GOOGLE_CLOUD_VISION_ENABLED
    ├── TESSERACT_ENABLED
    ├── TESSERACT_LANG
    ├── API_KEY_ENABLED
    └── API_KEY
```

**Important**: No cal base de dades - l'agent és completament stateless.

### Pas a pas

#### 1. Crear projecte a Railway

1. Anar a https://railway.app
2. Clic a **"New Project"**
3. Seleccionar **"Deploy from GitHub repo"**
4. Autoritzar Railway per accedir a GitHub (si és la primera vegada)
5. Seleccionar el repositori de l'Agent OCR

#### 2. Configuració automàtica

Railway detectarà automàticament:
- El `Dockerfile` al directori arrel
- El port 8000 exposat
- Els requisits del sistema

#### 3. Configurar variables d'entorn

Al dashboard de Railway:

1. Anar a la pestanya **"Variables"**
2. Afegir les següents variables:

```bash
# Google Cloud Vision (OBLIGATORI)
GOOGLE_CLOUD_CREDENTIALS_JSON='{"type":"service_account","project_id":"gogestor-ocr-485718","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"ocr-service@gogestor-ocr-485718.iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"...","universe_domain":"googleapis.com"}'
GOOGLE_CLOUD_VISION_ENABLED=true

# Tesseract (OPCIONAL)
TESSERACT_ENABLED=true
TESSERACT_LANG=spa+cat+eng

# API Security (OBLIGATORI per producció)
API_KEY_ENABLED=true
API_KEY=your-secure-api-key-here

# Google Cloud Project ID (OPCIONAL)
GOOGLE_CLOUD_PROJECT_ID=gogestor-ocr-485718
```

**IMPORTANT**:
- El JSON ha d'estar en **una sola línia**
- Mantenir les cometes simples exteriors: `'{"type":"service_account",...}'`
- No afegir espais ni salts de línia dins del JSON

#### 4. Desplegar

1. Railway començarà el build automàticament
2. Espereu ~3-5 minuts per al primer desplegament
3. Podreu veure els logs en temps real al dashboard

#### 5. Obtenir URL pública

Un cop desplegat:
1. Railway assignarà una URL pública automàticament
2. URL actual: `https://ocr-production-abec.up.railway.app`
3. Copiar aquesta URL per usar-la al GoGestor (variable `OCR_AGENT_URL`)

### Desplegaments futurs

Cada cop que facis `git push` a la branca principal (master/main):
1. Railway detectarà els canvis automàticament
2. Construirà una nova imatge Docker
3. Desplegarà la nova versió sense downtime

---

## Desplegament amb Docker

Si prefereixes desplegar a altres plataformes (AWS, GCP, Azure, DigitalOcean, etc.):

### Build local

```bash
cd /Users/kim/Sites/Agents/OCR

# Build
docker build -t ocr-agent:1.0.0 .

# Test local
docker run -p 8000:8000 \
  -e GOOGLE_CLOUD_CREDENTIALS_JSON='{"type":"service_account",...}' \
  -e TESSERACT_ENABLED=true \
  -e TESSERACT_LANG=spa+cat+eng \
  ocr-agent:1.0.0

# Verificar
curl http://localhost:8000/health
```

### Push a Docker Hub

```bash
# Tag
docker tag ocr-agent:1.0.0 <username>/ocr-agent:1.0.0
docker tag ocr-agent:1.0.0 <username>/ocr-agent:latest

# Login
docker login

# Push
docker push <username>/ocr-agent:1.0.0
docker push <username>/ocr-agent:latest
```

### Desplegament a altres plataformes

#### AWS ECS

```bash
# Crear cluster, task definition i service
aws ecs create-cluster --cluster-name ocr-agent-cluster
aws ecs register-task-definition --cli-input-json file://task-definition.json
aws ecs create-service --cluster ocr-agent-cluster --service-name ocr-agent --task-definition ocr-agent
```

#### Google Cloud Run

```bash
# Build i push a GCR
gcloud builds submit --tag gcr.io/gogestor-ocr-485718/ocr-agent

# Deploy
gcloud run deploy ocr-agent \
  --image gcr.io/gogestor-ocr-485718/ocr-agent \
  --platform managed \
  --region europe-west1 \
  --set-env-vars GOOGLE_CLOUD_CREDENTIALS_JSON='...',TESSERACT_ENABLED=true
```

#### DigitalOcean App Platform

1. Connectar repositori GitHub
2. Seleccionar Dockerfile com a build method
3. Configurar variables d'entorn
4. Deploy

---

## Variables d'entorn

### Variables obligatòries

| Variable | Descripció | Exemple |
|----------|-----------|---------|
| `GOOGLE_CLOUD_CREDENTIALS_JSON` | Credencials de Google Cloud Vision (JSON en una línia) | `'{"type":"service_account",...}'` |

### Variables opcionals

| Variable | Descripció | Valor per defecte |
|----------|-----------|-------------------|
| `TESSERACT_ENABLED` | Activar Tesseract OCR | `true` |
| `TESSERACT_LANG` | Idiomes de Tesseract | `spa+cat+eng` |
| `GOOGLE_CLOUD_PROJECT_ID` | Project ID de Google Cloud | Auto-detectat des del JSON |
| `PORT` | Port del servidor | `8000` |

### Com obtenir les credencials de Google Cloud Vision

1. Anar a https://console.cloud.google.com
2. Crear/seleccionar projecte
3. Activar API de Cloud Vision:
   - **APIs & Services** → **Library**
   - Cercar "Cloud Vision API"
   - Clic a **"Enable"**
4. Crear Service Account:
   - **IAM & Admin** → **Service Accounts**
   - Clic a **"Create Service Account"**
   - Nom: `ocr-service`
   - Role: **Cloud Vision AI Service Agent**
5. Crear clau:
   - Seleccionar el service account creat
   - **Keys** → **Add Key** → **Create new key**
   - Tipus: **JSON**
   - Descarregar el fitxer
6. Convertir JSON a una línia:
   ```bash
   cat credentials.json | jq -c
   ```
7. Copiar el resultat i afegir-lo a Railway entre cometes simples

---

## Verificació del desplegament

### 1. Health Check

```bash
curl https://ocr-agent-production.up.railway.app/health
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

### 2. Test amb DNI

```bash
curl -X POST "https://ocr-agent-production.up.railway.app/ocr/dni" \
  -F "file=@test-dni.jpg"
```

**Resposta esperada:**
```json
{
  "success": true,
  "message": "DNI processat correctament",
  "data": {
    "dni": "77612097T",
    "nom_complet": "JOAQUIN COLL CEREZO",
    ...
  }
}
```

### 3. Test amb Permís

```bash
curl -X POST "https://ocr-agent-production.up.railway.app/ocr/permis" \
  -F "file=@test-permis.jpg"
```

### 4. Verificar logs

Al dashboard de Railway:
1. Anar a **"Deployments"**
2. Seleccionar el deployment actiu
3. Veure logs en temps real

Logs esperats:
```
✅ Tesseract disponible (v5.x.x)
✅ Google Vision: Credencials carregades des de variable d'entorn
✅ Client Google Vision creat (Project: gogestor-ocr-485718)
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Integració amb GoGestor

Un cop desplegat l'Agent OCR a Railway, pots integrar-lo amb el backend de GoGestor.

### 1. Afegir variables d'entorn al GoGestor (Railway)

Al projecte de GoGestor a Railway, afegir les següents variables:

```bash
OCR_AGENT_URL=https://ocr-production-abec.up.railway.app
OCR_AGENT_API_KEY=your-ocr-agent-api-key-here
OCR_AGENT_TIMEOUT=30
OCR_AGENT_ENABLED=true
```

### 2. Implementar al backend de GoGestor (PHP/Laravel)

Per a la integració completa amb exemples de codi PHP/Laravel, consulta:

📖 **[GOGESTOR_INTEGRATION.md](./GOGESTOR_INTEGRATION.md)** - Guia completa d'integració amb GoGestor

Aquesta guia inclou:
- Service layer complet (`OcrService.php`)
- Exemples d'ús en controllers
- Gestió d'errors
- Validacions
- Testing
- Best practices
- Jobs asíncrons
- Cache de resultats

**Exemple ràpid:**

```php
// app/Services/OcrService.php
use Illuminate\Support\Facades\Http;

public function processarDNI($file) {
    $response = Http::timeout(30)
        ->withHeaders(['X-API-Key' => config('services.ocr_agent.api_key')])
        ->attach('file', file_get_contents($file->getRealPath()), $file->getClientOriginalName())
        ->post(config('services.ocr_agent.url') . '/ocr/dni', [
            'preprocess' => true,
            'preprocess_mode' => 'standard'
        ]);

    return $response->successful() ? $response->json()['data'] : null;
}
```

**Ús al controller:**

```php
// app/Http/Controllers/DocumentController.php
public function uploadDNI(Request $request) {
    $dniData = app(OcrService::class)->processarDNI($request->file('dni'));

    if (!$dniData) {
        return response()->json(['error' => 'Error processant DNI'], 500);
    }

    return response()->json(['success' => true, 'data' => $dniData]);
}
```

---

## Solució de problemes

### Error: "Google Vision no disponible"

**Causa**: Credencials mal configurades o incorrectes

**Solució**:
1. Verificar que `GOOGLE_CLOUD_CREDENTIALS_JSON` està configurat a Railway
2. Assegurar que el JSON està en una sola línia
3. Verificar que el Service Account té permisos de Cloud Vision API
4. Revisar logs a Railway per veure el missatge d'error específic

```bash
# Verificar format del JSON
echo $GOOGLE_CLOUD_CREDENTIALS_JSON | jq .
```

### Error: Build falla a Railway

**Causa**: Dockerfile incorrecte o dependències fallant

**Solució**:
1. Revisar logs de build a Railway
2. Testar build localment:
   ```bash
   docker build -t ocr-agent .
   ```
3. Verificar que el Dockerfile és al directori arrel

### Error: 503 Service Unavailable

**Causa**: Servei no ha arrencat correctament

**Solució**:
1. Revisar logs a Railway
2. Verificar que les variables d'entorn estan configurades
3. Comprovar health endpoint:
   ```bash
   curl https://ocr-agent-production.up.railway.app/health
   ```

### Error: "ModuleNotFoundError: No module named 'cv2'"

**Causa**: OpenCV no instal·lat al contenidor

**Solució**:
1. Verificar que el Dockerfile té `opencv-python-headless`
2. Rebuild a Railway:
   - **Settings** → **Redeploy**

### Error: Imatges no es processen correctament

**Causa**: Preprocessament massa agressiu o insuficient

**Solució**:
1. Provar diferents modes de preprocessament:
   - `standard` - Ús general
   - `aggressive` - Imatges de baixa qualitat
   - `document` - Documents inclinats
   - `none` - Imatges d'alta qualitat
2. Usar l'endpoint `/ocr/compare` per trobar la millor configuració

### Error: Timeout o resposta lenta

**Causa**: Processament d'imatges grans o connexió lenta amb Google Vision

**Solució**:
1. Redimensionar imatges al client abans d'enviar (màx. 2000px)
2. Augmentar timeout al client:
   ```typescript
   const response = await fetch(url, {
     method: 'POST',
     body: formData,
     timeout: 30000, // 30 segons
   });
   ```

### Cost massa elevat de Google Cloud Vision

**Causa**: Massa peticions per mes

**Solució**:
1. Implementar cache de resultats al GoGestor
2. Evitar processar la mateixa imatge múltiples vegades
3. Usar Tesseract per desenvolupament/testing
4. Monitoritzar ús a Google Cloud Console:
   - https://console.cloud.google.com/apis/api/vision.googleapis.com/metrics

---

## Monitorització i logs

### Logs a Railway

1. Anar al dashboard de Railway
2. Seleccionar el servei **ocr-agent**
3. Clic a **"Deployments"**
4. Seleccionar deployment actiu
5. Veure logs en temps real

### Mètriques a Google Cloud

1. Anar a https://console.cloud.google.com
2. Seleccionar el projecte
3. **APIs & Services** → **Dashboard**
4. Seleccionar **Cloud Vision API**
5. Veure gràfiques de:
   - Peticions per dia
   - Errors
   - Latència

### Configurar alertes

#### Railway

1. **Settings** → **Notifications**
2. Configurar webhook per Slack/Discord
3. Alertes de:
   - Deploy fallat
   - Servei caigut
   - Límit de recursos

#### Google Cloud

1. **Monitoring** → **Alerting**
2. Crear alerta de quota:
   - Mètrica: `vision.googleapis.com/quota/rate/net_usage`
   - Condició: > 900 peticions/mes (90% del tier gratuït)
   - Notificació: Email

---

## Costos estimats

### Railway

| Plan | Cost | Inclou |
|------|------|--------|
| Hobby | $5/mes | 500h execució, 100GB bandwidth |
| Pro | $20/mes | 2000h execució, 100GB bandwidth |

**Recomanat**: Hobby Plan (suficient per producció petita/mitjana)

### Google Cloud Vision

| Ús mensual | Cost |
|------------|------|
| 0 - 1.000 unitats | **GRATUÏT** ✅ |
| 1.001 - 5.000.000 | $1.50 per 1.000 |
| > 5.000.000 | $0.60 per 1.000 |

**Estimació**:
- 100 DNI/dia × 30 dies = 3.000 DNI/mes
- Cost: (3.000 - 1.000) × $1.50 / 1.000 = **$3/mes**

**Total estimat**: ~$8-10/mes per producció

---

## Seguretat

### Checklist de seguretat

- [ ] Les credencials de Google Cloud estan com a variable d'entorn (NO al codi)
- [ ] El repositori GitHub és privat o les credencials estan al `.gitignore`
- [ ] Les variables d'entorn a Railway són privades (no visibles als logs)
- [ ] El Service Account de Google Cloud té **només** permisos de Cloud Vision
- [ ] CORS està configurat correctament a l'API
- [ ] Les imatges temporals s'eliminen després del processament
- [ ] No es loggen dades sensibles (DNI, dades personals)

### Bones pràctiques

1. **Rotar credencials periòdicament**:
   - Crear nou Service Account key cada 3-6 mesos
   - Eliminar keys antics

2. **Monitoritzar accessos**:
   - Revisar logs de Google Cloud per accessos no autoritzats

3. **Limitar accés**:
   - Implementar API keys per cridar l'Agent OCR
   - Rate limiting per prevenir abús

---

## Actualitzacions i manteniment

### Actualitzar dependencies

```bash
# Al repositori local
pip list --outdated
pip install --upgrade <package>
pip freeze > requirements.txt

# Commit i push
git add requirements.txt
git commit -m "Update dependencies"
git push

# Railway desplegarà automàticament
```

### Rollback

Si un desplegament falla:

1. Anar a Railway dashboard
2. **Deployments** → Seleccionar deployment anterior funcional
3. Clic a **"Redeploy"**

---

## Suport

Per problemes o preguntes:
- **GitHub Issues**: https://github.com/<username>/OCR/issues
- **Email**: kim@conekta.cat
- **Railway Support**: https://railway.app/help

---

## Referències

- [Railway Docs](https://docs.railway.app)
- [Google Cloud Vision Docs](https://cloud.google.com/vision/docs)
- [Docker Docs](https://docs.docker.com)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
