"""
Ruta per processar Permís de Circulació
"""
import asyncio
import logging
import tempfile
import os
import time
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from app.models.permis_response import PermisValidationResponse
from app.services.tesseract_service import tesseract_service
from app.services.google_vision_service import google_vision_service
from app.services.image_processor import image_processor
from app.parsers.permis_parser import permis_parser

log = logging.getLogger("ocr.permis")

_tesseract_semaphore = asyncio.Semaphore(2)

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


@router.post("/permis", response_model=PermisValidationResponse)
async def process_permis(
    file: UploadFile = File(...),
    preprocess: bool = Query(default=False, description="Pre-processar imatge"),
    preprocess_mode: str = Query(default="standard", description="Mode: standard, aggressive, document"),
):
    """
    Processa un Permís de Circulació i retorna validació experta.

    Sistema de doble passada (1 sol crèdit Vision per document):
    - Phase 1: extracció raw per regex
    - Phase 2: validació creuada + correcció OCR (Python pur, 0 crèdits addicionals)
    """
    # 🔍 LOG TEMPORAL: Petició rebuda
    log.info("🔍 PERMIS REQUEST", extra={
        "uploaded_filename": file.filename,
        "mime_type": file.content_type,
        "preprocess_enabled": preprocess,
    })

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

        # --- INTENT 1: Tesseract (gratuït) ---
        result: PermisValidationResponse | None = None

        if tesseract_service.is_available():
            try:
                t0 = time.monotonic()
                async with _tesseract_semaphore:
                    tess_result = await asyncio.wait_for(
                        run_in_threadpool(tesseract_service.detect_text, ocr_input_path),
                        timeout=OCR_TIMEOUT_SECONDS,
                    )
                tess_ms = round((time.monotonic() - t0) * 1000)
                tess_data = permis_parser.parse(tess_result["text"])
                tess_confidence = tess_result["confidence"]

                cal_fallback, motiu = permis_parser.should_fallback_to_vision(tess_data, tess_confidence)

                if not cal_fallback:
                    result = permis_parser.validate_and_build_response(
                        tess_data, "tesseract", tess_confidence
                    )
                    log.info("ocr_tesseract_ok", extra={
                        "matricula": result.datos.matricula,
                        "qualitat": result.confianza_global,
                        "durada_ms": tess_ms,
                        "confidence": round(tess_confidence, 1),
                    })
                else:
                    log.info("ocr_tesseract_fallback", extra={
                        "motiu": motiu,
                        "durada_ms": tess_ms,
                        "confidence": round(tess_confidence, 1),
                    })
            except asyncio.TimeoutError:
                log.warning("ocr_tesseract_timeout")
            except Exception as e:
                log.warning("ocr_tesseract_error", extra={"error_type": type(e).__name__})

        # --- INTENT 2: Google Vision (fallback) ---
        if result is None:
            if not google_vision_service.is_available():
                raise HTTPException(status_code=503, detail="Cap motor OCR disponible")

            t0 = time.monotonic()
            vision_result = await asyncio.wait_for(
                run_in_threadpool(google_vision_service.detect_document_text, ocr_input_path),
                timeout=OCR_TIMEOUT_SECONDS,
            )
            vision_ms = round((time.monotonic() - t0) * 1000)
            vision_data = permis_parser.parse(vision_result["text"])
            result = permis_parser.validate_and_build_response(
                vision_data, "google_vision", vision_result["confidence"]
            )
            log.info("ocr_vision_used", extra={
                "matricula": result.datos.matricula,
                "confianza_global": result.confianza_global,
                "valido": result.valido,
                "durada_ms": vision_ms,
                "confidence": round(vision_result["confidence"], 1),
                "errors": len(result.errores_detectados),
                "alerts": len(result.alertas),
            })

        # TODO: si result.confianza_global < 85 → Claude text-only per refinament

        log.info("ocr_success", extra={
            "matricula": result.datos.matricula,
            "valido": result.valido,
            "confianza_global": result.confianza_global,
            "engine": result.raw.ocr_engine,
        })

        # 🔍 LOG TEMPORAL: Resposta enviada
        log.info("🔍 PERMIS RESPONSE", extra={
            "matricula": result.datos.matricula,
            "marca": result.datos.marca,
            "modelo": result.datos.modelo,
            "tipo_vehiculo": result.datos.tipo_vehiculo,
            "emissions_co2": result.datos.emissions_co2,
            "contracte": "v1",
            "valido": result.valido,
            "confianza": result.confianza_global,
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
