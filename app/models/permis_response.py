"""
Model de resposta per Permís de Circulació — Contracte unificat v1
"""
from pydantic import BaseModel
from typing import Optional, Literal, List
from app.models.base_response import ValidationItem, RawOCR, MetaInfo


class PermisExtracted(BaseModel):
    """Dades extretes del Permís de Circulació. Dates en format ISO (YYYY-MM-DD)."""

    # Identificació del document
    numero_permiso: Optional[str] = None

    # Vehicle
    matricula: Optional[str] = None
    numero_bastidor: Optional[str] = None    # VIN (camp E)
    marca: Optional[str] = None              # D.1
    modelo: Optional[str] = None             # D.3 nom comercial
    variante_version: Optional[str] = None   # D.3 codi tècnic
    categoria: Optional[str] = None          # M1, N1…

    # Dates (ISO YYYY-MM-DD)
    fecha_matriculacion: Optional[str] = None         # camp I
    fecha_primera_matriculacion: Optional[str] = None # camp B
    fecha_expedicion: Optional[str] = None

    # Titular (C.1.x)
    titular_nombre: Optional[str] = None
    titular_nif: Optional[str] = None
    domicilio: Optional[str] = None
    municipio: Optional[str] = None
    provincia: Optional[str] = None
    codigo_postal: Optional[str] = None

    # Ús
    servicio: Optional[str] = None

    # Motor
    cilindrada_cc: Optional[int] = None
    potencia_kw: Optional[float] = None
    potencia_fiscal: Optional[float] = None
    combustible: Optional[str] = None
    emissions_co2: Optional[float] = None   # V.7 (g/km)

    # Masses i capacitat
    masa_maxima: Optional[int] = None
    masa_orden_marcha: Optional[int] = None
    plazas: Optional[int] = None

    # Tipus vehicle (descriptiu)
    tipo_vehiculo: Optional[str] = None      # Turisme, Furgoneta, Motocicleta...

    # Dates transferència
    fecha_ultima_transferencia: Optional[str] = None

    # Altres
    proxima_itv: Optional[str] = None
    observaciones: Optional[str] = None


class PermisValidationResponse(BaseModel):
    """Resposta de l'endpoint /ocr/permis — Contracte unificat v1."""
    valido: bool
    confianza_global: int                                              # 0-100
    tipo_documento: Literal["permiso_circulacion"] = "permiso_circulacion"
    datos: PermisExtracted
    alertas: List[ValidationItem] = []
    errores_detectados: List[ValidationItem] = []
    raw: RawOCR
    meta: Optional[MetaInfo] = None
