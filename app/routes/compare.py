"""
Ruta per comparar resultats entre diferents motors OCR i modes de preprocessament
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from app.services.tesseract_service import tesseract_service
from app.services.google_vision_service import google_vision_service
from app.services.image_processor import image_processor
import tempfile
import os
import time
from typing import List, Dict, Any
from pydantic import BaseModel

router = APIRouter()


class OCRComparison(BaseModel):
    """Resultat de comparació d'un motor OCR"""
    engine: str
    preprocess_mode: str
    text: str
    confidence: float
    processing_time: float
    success: bool
    error: str = None


class ComparisonResponse(BaseModel):
    """Resposta amb comparacions de diferents motors"""
    success: bool
    message: str
    results: List[OCRComparison]
    recommendations: Dict[str, str]


@router.post("/compare", response_model=ComparisonResponse)
async def compare_ocr_engines(
    file: UploadFile = File(...),
    engines: List[str] = Query(default=["tesseract", "google_vision"], description="Motors a comparar"),
    preprocess_modes: List[str] = Query(default=["standard", "aggressive"], description="Modes de preprocessament")
):
    """
    Compara resultats de diferents motors OCR i modes de preprocessament

    - **file**: Imatge del document (JPG, PNG)
    - **engines**: Motors a testejar (tesseract, google_vision)
    - **preprocess_modes**: Modes a provar (standard, aggressive, document, none)

    Returns:
        Comparació de tots els resultats amb recomanacions
    """
    # Validar fitxer
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El fitxer ha de ser una imatge")

    # Guardar temporalment
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    results = []
    processed_images = {}

    try:
        # Processar imatge amb cada mode
        for mode in preprocess_modes:
            if mode == "none":
                processed_images[mode] = temp_path
            else:
                try:
                    processed_path = image_processor.process_for_ocr(
                        temp_path,
                        mode=mode
                    )
                    processed_images[mode] = processed_path
                except Exception as e:
                    print(f"⚠️  Error preprocessant amb mode {mode}: {e}")
                    processed_images[mode] = temp_path

        # Testejar cada combinació de motor + mode
        for engine in engines:
            for mode in preprocess_modes:
                start_time = time.time()

                try:
                    image_path = processed_images.get(mode, temp_path)

                    # Executar OCR segons motor
                    if engine == "tesseract":
                        if not tesseract_service.is_available():
                            results.append(OCRComparison(
                                engine=engine,
                                preprocess_mode=mode,
                                text="",
                                confidence=0.0,
                                processing_time=0.0,
                                success=False,
                                error="Tesseract no disponible"
                            ))
                            continue

                        ocr_result = tesseract_service.detect_text(image_path)

                    elif engine == "google_vision":
                        if not google_vision_service.is_available():
                            results.append(OCRComparison(
                                engine=engine,
                                preprocess_mode=mode,
                                text="",
                                confidence=0.0,
                                processing_time=0.0,
                                success=False,
                                error="Google Vision no disponible"
                            ))
                            continue

                        ocr_result = google_vision_service.detect_document_text(image_path)

                    else:
                        continue

                    processing_time = time.time() - start_time

                    results.append(OCRComparison(
                        engine=engine,
                        preprocess_mode=mode,
                        text=ocr_result["text"],
                        confidence=ocr_result["confidence"],
                        processing_time=round(processing_time, 3),
                        success=True
                    ))

                except Exception as e:
                    processing_time = time.time() - start_time
                    results.append(OCRComparison(
                        engine=engine,
                        preprocess_mode=mode,
                        text="",
                        confidence=0.0,
                        processing_time=round(processing_time, 3),
                        success=False,
                        error=str(e)
                    ))

        # Generar recomanacions
        recommendations = generate_recommendations(results)

        return ComparisonResponse(
            success=True,
            message=f"Comparació completada: {len(results)} resultats",
            results=results,
            recommendations=recommendations
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error durant la comparació: {str(e)}"
        )

    finally:
        # Netejar fitxers temporals
        if os.path.exists(temp_path):
            os.unlink(temp_path)

        for mode, path in processed_images.items():
            if path != temp_path and os.path.exists(path):
                os.unlink(path)


def generate_recommendations(results: List[OCRComparison]) -> Dict[str, str]:
    """
    Genera recomanacions basades en els resultats
    """
    if not results:
        return {"error": "No hi ha resultats per analitzar"}

    # Filtrar només resultats exitosos
    successful = [r for r in results if r.success]

    if not successful:
        return {"error": "Cap motor OCR ha funcionat correctament"}

    # Trobar millor per confiança
    best_confidence = max(successful, key=lambda x: x.confidence)

    # Trobar millor per velocitat
    best_speed = min(successful, key=lambda x: x.processing_time)

    # Trobar millor balanç (confiança alta + velocitat)
    best_balance = max(successful, key=lambda x: x.confidence / (x.processing_time + 0.1))

    # Analitzar quin motor és millor
    tesseract_avg = sum(r.confidence for r in successful if r.engine == "tesseract") / max(len([r for r in successful if r.engine == "tesseract"]), 1)
    google_avg = sum(r.confidence for r in successful if r.engine == "google_vision") / max(len([r for r in successful if r.engine == "google_vision"]), 1)

    return {
        "best_accuracy": f"{best_confidence.engine} + {best_confidence.preprocess_mode} ({best_confidence.confidence}% confiança)",
        "best_speed": f"{best_speed.engine} + {best_speed.preprocess_mode} ({best_speed.processing_time}s)",
        "best_balance": f"{best_balance.engine} + {best_balance.preprocess_mode}",
        "recommended_engine": "google_vision" if google_avg > tesseract_avg else "tesseract",
        "tesseract_avg_confidence": f"{round(tesseract_avg, 2)}%",
        "google_vision_avg_confidence": f"{round(google_avg, 2)}%"
    }
