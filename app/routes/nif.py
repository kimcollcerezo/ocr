"""
Ruta per processar Targeta Identificació Fiscal (NIF/TIF) — Contracte unificat v1
"""
import asyncio
import logging
import tempfile
import os
import time
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from app.models.nif_response import NIFValidationResponse
from app.services.google_vision_service import google_vision_service
from app.services.image_processor import image_processor
from app.parsers.nif_parser import nif_parser

log = logging.getLogger("ocr.nif")

OCR_TIMEOUT_SECONDS = 30
MAX_FILE_SIZE = 5 * 1024 * 1024
VALID_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG":      "image/png",
    b"RIFF":         "image/webp",
}


def _detect_image_type(content: bytes) -> str | None:
    for magic, mime in _MAGIC.items():
        if content[: len(magic)] == magic:
            return mime
    return None


router = APIRouter()


@router.post("/nif", response_model=NIFValidationResponse)
async def process_nif(
    file: UploadFile = File(...),
    preprocess: bool = Query(default=False, description="Pre-processar imatge per millorar OCR"),
    preprocess_mode: str = Query(default="standard", description="Mode: standard, aggressive, document"),
):
    """
    Processa una Targeta d'Identificació Fiscal (NIF/TIF) i retorna validació experta (contracte unificat v1).

    - **file**: Imatge de la TIF (JPG, PNG, WEBP)

    Sistema de doble passada — 1 sol crèdit Vision per document:
    - Phase 1: extracció raw (regex Python)
    - Phase 2: validació creuada + codis normalitzats (Python pur, 0 crèdits)
    """
    if file.content_type not in VALID_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Format no suportat. Acceptem JPG, PNG o WEBP.")

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Imatge massa gran. Màxim {MAX_FILE_SIZE // 1024 // 1024}MB.")

    if _detect_image_type(content) is None:
        raise HTTPException(status_code=400, detail="El fitxer no és una imatge vàlida.")

    temp_path: str | None = None
    ocr_input_path: str | None = None

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(content)
        temp_path = tmp.name
    del content

    try:
        ocr_input_path = temp_path
        if preprocess:
            try:
                ocr_input_path = image_processor.process_for_ocr(temp_path, mode=preprocess_mode)
            except Exception:
                log.warning("preprocess_failed")
                ocr_input_path = temp_path

        # --- Google Vision OCR (únic motor) ---
        if not google_vision_service.is_available():
            raise HTTPException(status_code=503, detail="Motor OCR no disponible")

        t0 = time.monotonic()
        vision_result = await asyncio.wait_for(
            run_in_threadpool(google_vision_service.detect_document_text, ocr_input_path),
            timeout=OCR_TIMEOUT_SECONDS,
        )
        vision_ms = round((time.monotonic() - t0) * 1000)

        # Phase 1: extracció raw
        nif_data = nif_parser.parse(vision_result["text"])

        # Phase 2: validació i construcció resposta
        result = nif_parser.validate_and_build_response(
            nif_data, "google_vision", vision_result["confidence"]
        )

        log.info("ocr_vision_used", extra={
            "nif_redacted": _redact(result.datos.numero_nif),
            "confianza": result.confianza_global,
            "valido": result.valido,
            "errors": len(result.errores_detectados),
            "alerts": len(result.alertas),
            "durada_ms": vision_ms,
            "confidence": round(vision_result["confidence"], 1),
        })

        # TODO: si result.confianza_global < 85 → Claude text-only per refinament

        log.info("ocr_success", extra={
            "nif_redacted": _redact(result.datos.numero_nif),
            "confianza": result.confianza_global,
            "valido": result.valido,
            "engine": result.raw.ocr_engine,
        })
        return result

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout processant el document.")
    except Exception:
        log.exception("ocr_unexpected_error")
        raise HTTPException(status_code=500, detail="Error intern processant el document.")

    finally:
        def _unlink(path: str | None) -> None:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
        _unlink(temp_path)
        if ocr_input_path != temp_path:
            _unlink(ocr_input_path)


def _redact(nif: str | None) -> str:
    """Redacta NIF per logs (mostra només primers 4 caràcters + últim)"""
    if not nif or len(nif) < 3:
        return "***"
    return nif[:4] + "****" + nif[-1]
