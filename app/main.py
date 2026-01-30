"""
OCR Agent - API FastAPI

Agent independent per OCR de documents (DNI, Permís de Circulació, etc.)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import dni, permis, compare

# Crear app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Agent OCR per documents espanyols (DNI, Permís de Circulació)",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producció, especificar origins concrets
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(dni.router, prefix="/ocr", tags=["DNI"])
app.include_router(permis.router, prefix="/ocr", tags=["Permís"])
app.include_router(compare.router, prefix="/ocr", tags=["Comparació"])


@app.get("/")
async def root():
    """Health check"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "endpoints": {
            "dni": "/ocr/dni",
            "permis": "/ocr/permis",
            "compare": "/ocr/compare",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health():
    """Endpoint de health check"""
    from app.services.tesseract_service import tesseract_service
    from app.services.google_vision_service import google_vision_service

    return {
        "status": "healthy",
        "services": {
            "tesseract": tesseract_service.is_available(),
            "google_vision": google_vision_service.is_available()
        }
    }
