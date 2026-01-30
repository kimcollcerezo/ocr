"""
Models de resposta per Permís de Circulació
"""
from pydantic import BaseModel
from typing import Optional


class PermisData(BaseModel):
    """Dades extretes d'un Permís de Circulació"""

    # Identificació del vehicle
    matricula: Optional[str] = None
    numero_bastidor: Optional[str] = None  # VIN

    # Característiques
    marca: Optional[str] = None
    model: Optional[str] = None
    cilindrada: Optional[int] = None  # cc
    potencia: Optional[float] = None  # CV o kW

    # Dates
    data_matriculacio: Optional[str] = None  # Format: DD/MM/YYYY
    data_primera_matriculacio: Optional[str] = None

    # Titular
    titular_nom: Optional[str] = None
    titular_nif: Optional[str] = None

    # Metadades
    confidence: Optional[float] = None
    ocr_engine: Optional[str] = None  # "tesseract" o "google_vision"


class PermisResponse(BaseModel):
    """Resposta de l'endpoint /ocr/permis"""

    success: bool
    message: Optional[str] = None
    data: Optional[PermisData] = None
    error: Optional[str] = None
