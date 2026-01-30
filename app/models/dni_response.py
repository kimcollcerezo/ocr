"""
Models de resposta per DNI
"""
from pydantic import BaseModel
from typing import Optional
from datetime import date


class DNIData(BaseModel):
    """Dades extretes d'un DNI"""

    # Dades personals
    dni: Optional[str] = None
    nom: Optional[str] = None
    cognoms: Optional[str] = None
    nom_complet: Optional[str] = None

    # Dates
    data_naixement: Optional[str] = None  # Format: DD/MM/YYYY
    data_caducitat: Optional[str] = None

    # Altres
    nacionalitat: Optional[str] = None
    sexe: Optional[str] = None

    # Adreça (part posterior)
    carrer: Optional[str] = None
    numero: Optional[str] = None
    poblacio: Optional[str] = None
    provincia: Optional[str] = None
    adreca_completa: Optional[str] = None

    # Filiació
    pare: Optional[str] = None
    mare: Optional[str] = None
    lloc_naixement: Optional[str] = None

    # Metadades
    confidence: Optional[float] = None
    ocr_engine: Optional[str] = None  # "tesseract" o "google_vision"


class DNIResponse(BaseModel):
    """Resposta de l'endpoint /ocr/dni"""

    success: bool
    message: Optional[str] = None
    data: Optional[DNIData] = None
    error: Optional[str] = None
