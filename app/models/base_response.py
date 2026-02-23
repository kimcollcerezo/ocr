"""
Contracte unificat de resposta OCR (v1)

Tots els endpoints (DNI, Permís, futurs) retornen aquest format:
{
  "valido": bool,
  "confianza_global": 0-100,
  "tipo_documento": "dni|permiso_circulacion|...",
  "datos": { <document-specific> },
  "alertas": [ ValidationItem, ... ],
  "errores_detectados": [ ValidationItem, ... ],
  "raw": { "ocr_engine": "...", "ocr_confidence": 0-100 },
  "meta": { "success": bool, "message": "..." }
}

Regles:
  valido = True si i només si:
    - tots els camps mínims del document estan presents
    - cap error de severitat "critical" a errores_detectados

Càlcul confianza_global:
  base 100 - (critical × 35) - (error × 15) - (warning × 5) - (camp_mínim_absent × 20)
  clamped a [0, 100]
"""
from pydantic import BaseModel
from typing import Optional, Literal


class ValidationItem(BaseModel):
    """Ítem normalitzat d'error o alerta."""
    code: str                                          # p.ex. "DNI_EXPIRED"
    severity: Literal["warning", "error", "critical"]
    field: Optional[str] = None                        # camp afectat
    message: str                                       # text llegible
    evidence: Optional[str] = None                     # valor llegit que genera el problema
    suggested_fix: Optional[str] = None                # recomanació


class RawOCR(BaseModel):
    """Metadades del motor OCR que ha processat el document."""
    ocr_engine: Literal["tesseract", "google_vision"]
    ocr_confidence: float  # 0-100


class MetaInfo(BaseModel):
    """Informació de transport (backward-compat amb success/message anterior)."""
    success: bool
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: càlcul de confianza_global (fórmula del contracte)
# ---------------------------------------------------------------------------

def compute_confianza(
    alertas: list[ValidationItem],
    errores: list[ValidationItem],
    camps_minims_absents: int,
    ocr_confidence: float,
) -> int:
    """
    Fórmula contracte v1:
      base 100
      − critical × 35
      − error × 15
      − warning × 5
      − camp_mínim_absent × 20
      ajust OCR (pes 15%): base × 0.85 + ocr_confidence × 0.15
      clamped [0, 100]
    """
    score = 100
    for item in errores + alertas:
        if item.severity == "critical":
            score -= 35
        elif item.severity == "error":
            score -= 15
        else:
            score -= 5
    score -= camps_minims_absents * 20

    # Ajust suau per la qualitat del motor OCR
    score = round(score * 0.85 + ocr_confidence * 0.15)
    return max(0, min(100, score))
