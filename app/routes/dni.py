"""
Ruta per processar DNI
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from app.models.dni_response import DNIResponse, DNIData
from app.services.tesseract_service import tesseract_service
from app.services.google_vision_service import google_vision_service
from app.services.image_processor import image_processor
from app.parsers.dni_parser import dni_parser
import tempfile
import os

router = APIRouter()


@router.post("/dni", response_model=DNIResponse)
async def process_dni(
    file: UploadFile = File(...),
    preprocess: bool = Query(default=True, description="Pre-processar imatge per millorar OCR"),
    preprocess_mode: str = Query(default="standard", description="Mode: standard, aggressive, document")
):
    """
    Processa un DNI (frontal o posterior) i extreu les dades

    - **file**: Imatge del DNI (JPG, PNG)

    Returns:
        DNIResponse amb les dades extretes
    """
    # Validar fitxer
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El fitxer ha de ser una imatge")

    # Guardar temporalment
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        # Pre-processar imatge si cal
        ocr_input_path = temp_path
        if preprocess:
            try:
                ocr_input_path = image_processor.process_for_ocr(
                    temp_path,
                    mode=preprocess_mode
                )
            except Exception as e:
                print(f"⚠️  Error pre-processant imatge: {e}")
                # Si falla, usar imatge original
                ocr_input_path = temp_path

        # OCR amb Google Vision (millor precisió)
        if not google_vision_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="Google Vision no disponible"
            )

        ocr_result = google_vision_service.detect_document_text(ocr_input_path)

        # Parser DNI
        dni_data = dni_parser.parse(ocr_result["text"])
        dni_data.confidence = ocr_result["confidence"]
        dni_data.ocr_engine = "google_vision"

        # Verificar que s'ha extret alguna dada
        if not dni_data.dni and not dni_data.nom:
            return DNIResponse(
                success=False,
                message="No s'han pogut extreure dades del DNI",
                data=dni_data
            )

        return DNIResponse(
            success=True,
            message="DNI processat correctament",
            data=dni_data
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processant DNI: {str(e)}"
        )

    finally:
        # Netejar fitxers temporals
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        if preprocess and ocr_input_path != temp_path and os.path.exists(ocr_input_path):
            os.unlink(ocr_input_path)
