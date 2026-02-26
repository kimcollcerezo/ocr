"""
Models per la resposta de validació de Targeta d'Identificació Fiscal (NIF/TIF).
"""

from pydantic import BaseModel
from typing import Optional, Literal, List
from app.models.base_response import ValidationItem, RawOCR, MetaInfo


class NIFDatos(BaseModel):
    """Dades extretes d'una Targeta Identificació Fiscal"""

    # Identificació
    numero_nif: Optional[str] = None              # "B76261874"
    tipo_nif: Optional[str] = None                # "CIF"

    # Entitat
    denominacion: Optional[str] = None            # Raó Social
    razon_social: Optional[str] = None            # Alias de denominacion
    anagrama_comercial: Optional[str] = None      # Nom comercial

    # Domicili Social (registral)
    domicilio_social: Optional[str] = None        # Adreça completa
    domicilio_social_calle: Optional[str] = None
    domicilio_social_numero: Optional[str] = None
    domicilio_social_piso_puerta: Optional[str] = None
    domicilio_social_municipio: Optional[str] = None
    domicilio_social_provincia: Optional[str] = None
    domicilio_social_codigo_postal: Optional[str] = None

    # Domicili Fiscal (AEAT)
    domicilio_fiscal: Optional[str] = None
    domicilio_fiscal_calle: Optional[str] = None
    domicilio_fiscal_numero: Optional[str] = None
    domicilio_fiscal_piso_puerta: Optional[str] = None
    domicilio_fiscal_municipio: Optional[str] = None
    domicilio_fiscal_provincia: Optional[str] = None
    domicilio_fiscal_codigo_postal: Optional[str] = None

    # Dates (ISO YYYY-MM-DD)
    fecha_nif_definitivo: Optional[str] = None
    fecha_expedicion: Optional[str] = None

    # Administració AEAT
    administracion_aeat: Optional[str] = None
    codigo_administracion: Optional[str] = None   # "35601"
    nombre_administracion: Optional[str] = None   # "PALMAS G.C"

    # Altres
    codigo_electronico: Optional[str] = None


class NIFValidationResponse(BaseModel):
    """Resposta endpoint /ocr/nif — Contracte unificat v1"""
    valido: bool
    confianza_global: int                         # 0-100
    tipo_documento: Literal["nif"] = "nif"
    datos: NIFDatos
    alertas: List[ValidationItem] = []
    errores_detectados: List[ValidationItem] = []
    raw: RawOCR
    meta: Optional[MetaInfo] = None
