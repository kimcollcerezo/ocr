"""
Servei de Tesseract OCR
"""
import pytesseract
from PIL import Image
from app.config import settings
from typing import Optional


class TesseractService:
    """Wrapper per Tesseract OCR"""

    def __init__(self):
        self.lang = settings.tesseract_lang
        self._check_availability()

    def _check_availability(self):
        """Verifica que Tesseract està instal·lat"""
        try:
            version = pytesseract.get_tesseract_version()
            print(f"✅ Tesseract disponible (v{version})")
        except Exception as e:
            print(f"⚠️  Tesseract no disponible: {e}")

    def is_available(self) -> bool:
        """Verifica si Tesseract està disponible"""
        if not settings.tesseract_enabled:
            return False

        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def detect_text(self, image_path: str, lang: Optional[str] = None) -> dict:
        """
        Detecta text en una imatge

        Args:
            image_path: Path a la imatge
            lang: Idiomes (per defecte usa config)

        Returns:
            dict amb 'text' i 'confidence'
        """
        if not self.is_available():
            raise RuntimeError("Tesseract no està disponible")

        lang = lang or self.lang

        try:
            # Carregar imatge
            image = Image.open(image_path)

            # Configuració Tesseract
            # PSM 6: Assume a single uniform block of text (millor per DNIs)
            # PSM 3: Fully automatic page segmentation (default)
            custom_config = r'--psm 6'

            # OCR
            text = pytesseract.image_to_string(image, lang=lang, config=custom_config)

            # Obtenir confidence
            data = pytesseract.image_to_data(image, lang=lang, config=custom_config, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            return {
                "text": text,
                "confidence": round(avg_confidence, 2)
            }

        except Exception as e:
            raise Exception(f"Error en Tesseract OCR: {str(e)}")


# Singleton
tesseract_service = TesseractService()
