"""
Ruta per processar DNI/NIE — Contracte unificat v1
"""
import asyncio
import logging
import tempfile
import os
import time
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from app.models.dni_response import DNIValidationResponse
from app.services.tesseract_service import tesseract_service
from app.services.google_vision_service import google_vision_service
from app.services.image_processor import image_processor
from app.parsers.dni_parser import dni_parser

log = logging.getLogger("ocr.dni")

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


@router.post("/dni", response_model=DNIValidationResponse)
async def process_dni(
    file: UploadFile = File(...),
    preprocess: bool = Query(default=False, description="Pre-processar imatge per millorar OCR"),
    preprocess_mode: str = Query(default="standard", description="Mode: standard, aggressive, document"),
):
    """
    Processa un DNI/NIE i retorna validació experta (contracte unificat v1).

    - **file**: Imatge del DNI (JPG, PNG, WEBP)

    Sistema de doble passada — 1 sol crèdit Vision per document:
    - Phase 1: extracció raw (regex Python)
    - Phase 2: validació creuada + codis normalitzats (Python pur, 0 crèdits)
    """
    content = await file.read()

    # 🔍 LOG TEMPORAL: Petició rebuda
    log.info("🔍 DNI REQUEST", extra={
        "uploaded_filename": file.filename,
        "mime_type": file.content_type,
        "file_size_bytes": len(content),
        "file_size_kb": round(len(content) / 1024, 2),
        "preprocess_enabled": preprocess,
    })

    if file.content_type not in VALID_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Format no suportat. Acceptem JPG, PNG o WEBP.")

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
        result: DNIValidationResponse | None = None

        if tesseract_service.is_available():
            try:
                t0 = time.monotonic()
                async with _tesseract_semaphore:
                    tess_result = await asyncio.wait_for(
                        run_in_threadpool(tesseract_service.detect_text, ocr_input_path),
                        timeout=OCR_TIMEOUT_SECONDS,
                    )
                tess_ms = round((time.monotonic() - t0) * 1000)
                tess_text = tess_result["text"]
                tess_data, raw_mrz = dni_parser.parse(tess_text)
                tess_confidence = tess_result["confidence"]

                cal_fallback, motiu = dni_parser.should_fallback_to_vision(tess_data, tess_confidence, tess_text)

                if not cal_fallback:
                    result = dni_parser.validate_and_build_response(
                        tess_data, raw_mrz, "tesseract", tess_confidence
                    )
                    log.info("ocr_tesseract_ok", extra={
                        "doc_redacted": _redact(result.datos.numero_documento),
                        "confianza": result.confianza_global,
                        "valido": result.valido,
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
            vision_data, raw_mrz = dni_parser.parse(vision_result["text"])
            result = dni_parser.validate_and_build_response(
                vision_data, raw_mrz, "google_vision", vision_result["confidence"]
            )
            log.info("ocr_vision_used", extra={
                "doc_redacted": _redact(result.datos.numero_documento),
                "confianza": result.confianza_global,
                "valido": result.valido,
                "errors": len(result.errores_detectados),
                "alerts": len(result.alertas),
                "durada_ms": vision_ms,
                "confidence": round(vision_result["confidence"], 1),
            })

        # TODO: si result.confianza_global < 85 → Claude text-only per refinament

        log.info("ocr_success", extra={
            "doc_redacted": _redact(result.datos.numero_documento),
            "confianza": result.confianza_global,
            "valido": result.valido,
            "engine": result.raw.ocr_engine,
        })

        # 🔍 LOG TEMPORAL: Resposta enviada
        te_mrz = result.datos.mrz is not None
        te_adreca = result.datos.domicilio or result.datos.municipio or result.datos.provincia
        log.info("🔍 DNI RESPONSE", extra={
            "doc_redacted": _redact(result.datos.numero_documento),
            "domicilio": result.datos.domicilio,
            "municipio": result.datos.municipio,
            "provincia": result.datos.provincia,
            "codigo_postal": result.datos.codigo_postal,
            "te_mrz": te_mrz,
            "te_adreca": bool(te_adreca),
            "tipus_dni": "posterior" if te_mrz or te_adreca else "frontal",
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


def _redact(doc: str | None) -> str:
    if not doc or len(doc) < 3:
        return "***"
    return doc[:4] + "****" + doc[-1]
