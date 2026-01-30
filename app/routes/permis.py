"""
Ruta per processar Permís de Circulació
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from app.models.permis_response import PermisResponse
from app.services.google_vision_service import google_vision_service
from app.services.image_processor import image_processor
from app.parsers.permis_parser import permis_parser
import tempfile
import os

router = APIRouter()


@router.post("/permis", response_model=PermisResponse)
async def process_permis(
    file: UploadFile = File(...),
    preprocess: bool = Query(default=True, description="Pre-processar imatge per millorar OCR"),
    preprocess_mode: str = Query(default="standard", description="Mode: standard, aggressive, document")
):
    """
    Processa un Permís de Circulació i extreu les dades

    - **file**: Imatge del Permís (JPG, PNG)

    Returns:
        PermisResponse amb les dades extretes
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

        # OCR amb Google Vision (millor per permís)
        if not google_vision_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="Google Vision no disponible"
            )

        ocr_result = google_vision_service.detect_document_text(ocr_input_path)

        # Parser Permís
        permis_data = permis_parser.parse(ocr_result["text"])
        permis_data.confidence = ocr_result["confidence"]
        permis_data.ocr_engine = "google_vision"

        # Verificar que s'ha extret alguna dada
        if not permis_data.matricula and not permis_data.marca:
            return PermisResponse(
                success=False,
                message="No s'han pogut extreure dades del permís",
                data=permis_data
            )

        return PermisResponse(
            success=True,
            message="Permís processat correctament",
            data=permis_data
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processant permís: {str(e)}"
        )

    finally:
        # Netejar fitxers temporals
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        if preprocess and ocr_input_path != temp_path and os.path.exists(ocr_input_path):
            os.unlink(ocr_input_path)
