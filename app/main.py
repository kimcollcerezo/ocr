"""
OCR Agent - API FastAPI

Agent independent per OCR de documents (DNI, Permís de Circulació, etc.)
"""
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.routes import dni, permis
# from app.routes import compare  # TODO: Implementar més endavant

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


# Middleware de validació d'API Key
@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    """
    Valida l'API key en cada petició (excepte endpoints públics)
    """
    # Endpoints públics (sense autenticació)
    public_paths = ["/", "/health", "/docs", "/redoc", "/openapi.json"]

    # Si l'endpoint és públic, permetre accés
    if request.url.path in public_paths:
        return await call_next(request)

    # Si l'API key està desactivada, permetre accés
    if not settings.api_key_enabled:
        return await call_next(request)

    # Comprovar que hi ha API key configurada
    if not settings.api_key:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "API key no configurada al servidor"}
        )

    # Obtenir API key del header
    api_key = request.headers.get("X-API-Key")

    # Validar API key
    if not api_key or api_key != settings.api_key:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "API key invàlida o no proporcionada"},
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # API key vàlida, continuar amb la petició
    return await call_next(request)


# Routes
app.include_router(dni.router, prefix="/ocr", tags=["DNI"])
app.include_router(permis.router, prefix="/ocr", tags=["Permís"])
# app.include_router(compare.router, prefix="/ocr", tags=["Comparació"])  # TODO: Implementar més endavant


@app.get("/")
async def root():
    """Root endpoint - retorna només estat bàsic"""
    return {"status": "ok"}


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
