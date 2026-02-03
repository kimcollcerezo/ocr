"""
Servei de Google Cloud Vision
"""
import json
from google.cloud import vision
from google.oauth2 import service_account
from app.config import settings
from typing import Optional


class GoogleVisionService:
    """Wrapper per Google Cloud Vision API"""

    def __init__(self):
        self.client: Optional[vision.ImageAnnotatorClient] = None
        self._initialize_client()

    def _initialize_client(self):
        """Inicialitza el client de Google Vision"""
        if not settings.google_cloud_vision_enabled:
            print("⚠️  Google Cloud Vision deshabilitat")
            return

        try:
            # Credencials des de variable d'entorn JSON
            if settings.google_cloud_credentials_json:
                credentials_dict = json.loads(settings.google_cloud_credentials_json)
                credentials = service_account.Credentials.from_service_account_info(credentials_dict)
                self.client = vision.ImageAnnotatorClient(credentials=credentials)
                print("✅ Google Vision: Credencials carregades des de variable d'entorn")
            else:
                # Usar Application Default Credentials
                self.client = vision.ImageAnnotatorClient()
                print("⚠️  Google Vision: Usant Application Default Credentials")

            print(f"✅ Client Google Vision creat (Project: {settings.google_cloud_project_id or 'N/A'})")

        except Exception as e:
            print(f"❌ Error inicialitzant Google Vision: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Verifica si Google Vision està disponible"""
        return self.client is not None

    def detect_text(self, image_path: str) -> dict:
        """
        Detecta text en una imatge

        Args:
            image_path: Path a la imatge

        Returns:
            dict amb 'text', 'confidence' i 'annotations'
        """
        if not self.is_available():
            raise RuntimeError("Google Vision no està disponible")

        with open(image_path, "rb") as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = self.client.text_detection(image=image)

        if response.error.message:
            raise Exception(f"Google Vision API error: {response.error.message}")

        if not response.text_annotations:
            return {"text": "", "confidence": 0.0, "annotations": []}

        # Primer annotation conté tot el text
        full_text = response.text_annotations[0].description

        # Retornar també les annotations amb bounding boxes
        annotations = []
        for annotation in response.text_annotations[1:]:  # Saltar el primer (full text)
            vertices = [(vertex.x, vertex.y) for vertex in annotation.bounding_poly.vertices]
            annotations.append({
                "text": annotation.description,
                "vertices": vertices
            })

        return {
            "text": full_text,
            "confidence": 95.0,
            "annotations": annotations
        }

    def detect_document_text(self, image_path: str) -> dict:
        """
        Detecta text de documents (millor per documents estructurats)

        Args:
            image_path: Path a la imatge

        Returns:
            dict amb 'text' i 'confidence'
        """
        if not self.is_available():
            raise RuntimeError("Google Vision no està disponible")

        with open(image_path, "rb") as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = self.client.document_text_detection(image=image)

        if response.error.message:
            raise Exception(f"Google Vision API error: {response.error.message}")

        if not response.full_text_annotation:
            return {"text": "", "confidence": 0.0}

        full_text = response.full_text_annotation.text

        return {
            "text": full_text,
            "confidence": 95.0
        }


# Singleton
google_vision_service = GoogleVisionService()
