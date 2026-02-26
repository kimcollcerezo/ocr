"""
OCR Agent - API FastAPI

Agent independent per OCR de documents (DNI, Permís de Circulació, etc.)
"""
import time
import logging
import json
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.routes import dni, permis, nif


class _JsonFormatter(logging.Formatter):
    """Format JSON per logs estructurats (compatible amb Datadog, Loki, etc.)"""
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Afegir camps extra (mètriques, context)
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = val
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger("ocr")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.propagate = False


_configure_logging()
log = logging.getLogger("ocr.request")
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


# Middleware de latència i logging de peticions
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Registra mètrica de latència per a cada petició."""
    t0 = time.monotonic()
    response = await call_next(request)
    durada_ms = round((time.monotonic() - t0) * 1000)
    log.info(
        "http_request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "durada_ms": durada_ms,
        }
    )
    return response


# Middleware de validació d'API Key
@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    """
    Valida l'API key en cada petició (excepte endpoints públics)
    """
    # Endpoints públics (sense autenticació)
    public_paths = ["/", "/health"]

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
app.include_router(nif.router, prefix="/ocr", tags=["NIF"])
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
