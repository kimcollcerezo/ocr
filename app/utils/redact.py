"""
Utilitats de redacció de PII per a logs (RGPD)

Cap dada personal ha d'aparèixer en clar als logs de producció.
"""
from typing import Optional


def redact_dni(dni: Optional[str]) -> str:
    """
    Redacta un DNI/NIE per a logs.
    "12345678A" → "1234****A"
    "X1234567L" → "X123****L"
    """
    if not dni or len(dni) < 3:
        return "***"
    return dni[:4] + "****" + dni[-1]


def redact_name(name: Optional[str]) -> str:
    """
    Redacta un nom per a logs.
    "JOAQUIN" → "J******"
    "VICTORIA MERCEDES" → "V****************"
    """
    if not name:
        return "***"
    return name[0] + "*" * (len(name) - 1)


def redact_doc_info(dni: Optional[str], qualitat: Optional[int], engine: Optional[str]) -> dict:
    """
    Retorna un dict segur per a logging: dades tècniques sense PII.
    """
    return {
        "dni_redacted": redact_dni(dni),
        "qualitat": qualitat,
        "engine": engine,
    }
