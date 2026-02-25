"""
Model de resposta per DNI/NIE — Contracte unificat v1
"""
from pydantic import BaseModel
from typing import Optional, Literal, List
from app.models.base_response import ValidationItem, RawOCR, MetaInfo


class MRZData(BaseModel):
    """Dades extretes de la zona MRZ (Machine Readable Zone)."""
    raw: Optional[str] = None              # 3 línies raw per auditoria
    document_number: Optional[str] = None
    surname: Optional[str] = None
    name: Optional[str] = None
    nationality: Optional[str] = None
    birth_date: Optional[str] = None       # YYMMDD (format MRZ original)
    expiry_date: Optional[str] = None      # YYMMDD (format MRZ original)
    sex: Optional[str] = None             # M | F | < | null


class DNIDatos(BaseModel):
    """Dades extretes d'un DNI/NIE. Dates en format ISO (YYYY-MM-DD)."""

    # Identificació
    numero_documento: Optional[str] = None
    tipo_numero: Optional[Literal["DNI", "NIE"]] = None

    # Persona
    nombre: Optional[str] = None
    apellidos: Optional[str] = None
    nombre_completo: Optional[str] = None
    sexo: Optional[Literal["M", "F", "X"]] = None
    nacionalidad: Optional[str] = None

    # Dates (ISO YYYY-MM-DD)
    fecha_nacimiento: Optional[str] = None
    fecha_expedicion: Optional[str] = None
    fecha_caducidad: Optional[str] = None

    # Domicili (part posterior)
    domicilio: Optional[str] = None  # Adreça completa (deprecated, usa calle + numero)
    calle: Optional[str] = None  # Nom del carrer (ex: "C. ARTAIL", "CRER. VENDRELL")
    numero: Optional[str] = None  # Número del carrer (ex: "9", "5")
    piso_puerta: Optional[str] = None  # Pis i porta (ex: "P02 0001", "1º A", "2n B")
    municipio: Optional[str] = None
    provincia: Optional[str] = None
    codigo_postal: Optional[str] = None

    # Filiació
    nombre_padre: Optional[str] = None
    nombre_madre: Optional[str] = None
    lugar_nacimiento: Optional[str] = None

    # Número de suport (rere del document)
    soporte_numero: Optional[str] = None

    # MRZ (per coherència creuada)
    mrz: Optional[MRZData] = None


class DNIValidationResponse(BaseModel):
    """Resposta de l'endpoint /ocr/dni — Contracte unificat v1."""
    valido: bool
    confianza_global: int                                    # 0-100
    tipo_documento: Literal["dni"] = "dni"
    datos: DNIDatos
    alertas: List[ValidationItem] = []
    errores_detectados: List[ValidationItem] = []
    raw: RawOCR
    meta: Optional[MetaInfo] = None
