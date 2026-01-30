# 📚 Documentació OCR Agent

Documentació completa de l'OCR Agent amb Python, FastAPI, Tesseract i Google Cloud Vision.

---

## 📖 Guies Disponibles

### 1. [IMAGE_PROCESSING.md](IMAGE_PROCESSING.md)
**Pre-processament d'Imatges amb OpenCV**

Aprèn a millorar la qualitat de les imatges abans de l'OCR amb tècniques avançades:

- ✅ **8 Tècniques de Processament**
  - Detecció i correcció de rotació (Hough Transform)
  - Millora de contrast (CLAHE)
  - Eliminació de soroll (fastNlMeansDenoising)
  - Binarització adaptativa
  - Millora de nitidesa
  - Redimensionament intel·ligent
  - Detecció de límits del document
  - Transformació de perspectiva

- ✅ **3 Modes Predefinits**
  - `standard`: Ràpid, per imatges normals
  - `aggressive`: Màxima qualitat, per imatges dolentes
  - `document`: Per fotografies amb angle

- ✅ **Resultats Demostrats**
  - Fins a +40% de millora en precisió
  - Comparatives amb DNI i Permís
  - Recomanacions per cada tipus de document

**Quan llegir-ho:**
- Vols entendre com funciona el preprocessament
- Necessites decidir quin mode usar
- Vols saber quines millores esperar

---

### 2. [OCR_COMPARISON.md](OCR_COMPARISON.md)
**Comparació de Motors OCR i Configuracions**

Guia completa per comparar diferents motors OCR i trobar la millor configuració:

- ✅ **Endpoint `/ocr/compare`**
  - Compara Tesseract vs Google Vision
  - Prova múltiples modes de preprocessament
  - Obté recomanacions automàtiques

- ✅ **Mètriques Analitzades**
  - Confiança (accuracy)
  - Temps de processament
  - Relació qualitat/velocitat
  - Cost per 1,000 peticions

- ✅ **Casos d'Ús Pràctics**
  - Trobar millor configuració per DNI
  - Optimitzar processament de Permís
  - Decidir entre gratuït vs pagament

- ✅ **Experiments i Benchmarks**
  - DNI Frontal: Tesseract 98% vs Google 99%
  - Permís: Tesseract 45% vs Google 99%
  - Estratègia òptima cost/qualitat

**Quan llegir-ho:**
- No estàs segur de quin motor usar
- Vols optimitzar cost vs qualitat
- Necessites justificar decisions tècniques
- Vols comparar amb dades reals

---

## 🎯 Flux de Treball Recomanat

### Per Desenvolupadors

1. **Llegeix el README principal** per entendre l'arquitectura
2. **Llegeix IMAGE_PROCESSING.md** per entendre el preprocessament
3. **Llegeix OCR_COMPARISON.md** per saber com comparar
4. **Executa comparacions** amb les teves imatges reals
5. **Decideix la configuració** basant-te en resultats

### Per Integració

1. **Testa amb `/ocr/compare`** per trobar millor configuració
2. **Analitza les recomanacions** automàtiques
3. **Implementa l'endpoint específic** (`/ocr/dni` o `/ocr/permis`)
4. **Usa els paràmetres òptims** descoberts

---

## 📊 Resum Ràpid

| Document | Motor Recomanat | Mode | Precisió | Cost |
|----------|----------------|------|----------|------|
| **DNI Frontal (MRZ)** | Tesseract | standard | 98% | 0€ |
| **DNI Posterior** | Google Vision | aggressive | 95% | 0.0015€ |
| **Permís** | Google Vision | document | 99% | 0.0015€ |
| **Foto Mòbil** | Google Vision | document | 85-95% | 0.0015€ |

---

## 🔗 Enllaços Útils

- [README Principal](../README.md) - Guia d'instal·lació i ús bàsic
- [Swagger UI](http://localhost:8000/docs) - Documentació interactiva API
- [ReDoc](http://localhost:8000/redoc) - Documentació API alternativa
- [OpenCV Docs](https://docs.opencv.org/) - Referència OpenCV
- [Tesseract Wiki](https://github.com/tesseract-ocr/tesseract/wiki) - Documentació Tesseract
- [Google Vision API](https://cloud.google.com/vision/docs) - Documentació Google Cloud Vision

---

## 💡 Consells

### ⚡ Per Màxima Velocitat
```bash
POST /ocr/dni?preprocess=true&preprocess_mode=standard
```
- Mode standard és el més ràpid
- Tesseract per DNI és gratuït i ràpid

### 🎯 Per Màxima Precisió
```bash
POST /ocr/permis?preprocess=true&preprocess_mode=aggressive
```
- Mode aggressive aplica totes les millores
- Google Vision per documents complexos

### 💰 Per Mínim Cost
```bash
POST /ocr/dni?preprocess=true&preprocess_mode=standard
```
- Tesseract és 100% gratuït
- Preprocessament millora resultats sense cost

### 🔬 Per Experimentar
```bash
POST /ocr/compare
```
- Compara TOTES les opcions
- Rep recomanacions automàtiques
- Decideix amb dades reals

---

## 🚀 Exemples Ràpids

### Comparar Tot
```bash
curl -X POST "http://localhost:8000/ocr/compare" \
  -F "file=@document.jpg" \
  -F "engines=tesseract" \
  -F "engines=google_vision" \
  -F "preprocess_modes=none" \
  -F "preprocess_modes=standard" \
  -F "preprocess_modes=aggressive" \
  -F "preprocess_modes=document"
```

### DNI Optimitzat
```bash
curl -X POST "http://localhost:8000/ocr/dni?preprocess=true&preprocess_mode=standard" \
  -F "file=@dni.jpg"
```

### Permís Optimitzat
```bash
curl -X POST "http://localhost:8000/ocr/permis?preprocess=true&preprocess_mode=aggressive" \
  -F "file=@permis.jpg"
```

---

## 📞 Suport

Per dubtes o suggeriments sobre la documentació:
- **Email**: kim@conekta.cat
- **Autor**: Kim Coll
- **Desenvolupador Independent**

---

**Última actualització**: 2026-01-30
