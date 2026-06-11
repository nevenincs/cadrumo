"""Modelo 202 applicability modality gate.

Use of :class:`TaxpayerProfile` for compliance.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...deadlines.taxpayer_model import EntityType, TaxpayerProfile

_MODELO_202_MODALITY_LEGAL_REFS: tuple[str, ...] = (
    "ley-27-2014:art-40",
    "ley-27-2014:art-40-3",
)
"""Scoped registry citation keys grounding the Modelo 202 modality gate."""

_MODELO_202_ART_40_3_INCN_THRESHOLD: Decimal = Decimal("6000000")


class Modelo202Modality(StrEnum):
    """The pago-fraccionado modality available to a Modelo 202 filer."""

    ART_40_2_OPTIONAL = "art_40_2_optional"
    ART_40_3_MANDATORY = "art_40_3_mandatory"
    INCOMPLETE = "incomplete"


class Modelo202ModalityVerdict(BaseModel):
    """The derived Modelo 202 modality verdict and its grounding."""

    model_config = _STRICT_FROZEN

    modality: Modelo202Modality
    reason: str = Field(min_length=1)
    legal_refs: tuple[str, ...] = Field(min_length=1)


_MODELO_202_ART_40_3_MANDATORY_REASON = (
    "Modelo 202 modalidad obligatoria: el artículo 40.3 de la LIS impone "
    "el método de la base imponible (3 / 9 / 11 primeros meses) cuando el "
    "importe neto de la cifra de negocios de los doce meses anteriores ha "
    "superado los 6.000.000 €. La modalidad del artículo 40.2 (cuota) no "
    "está disponible."
)

_MODELO_202_ART_40_2_OPTIONAL_REASON = (
    "Modelo 202 modalidad por defecto: el artículo 40.2 de la LIS permite "
    "el método de la cuota (18 %) cuando el importe neto de la cifra de "
    "negocios de los doce meses anteriores no ha superado los 6.000.000 €. "
    "La modalidad del artículo 40.3 sigue siendo opcional."
)

_MODELO_202_INCOMPLETE_REASON = (
    "No se puede determinar la modalidad del Modelo 202: el importe neto "
    "de la cifra de negocios de los doce meses anteriores no está "
    "declarado. Sin este dato el motor no infiere modalidad — un pago "
    "fraccionado equivocado es peor que una respuesta incompleta. Declare "
    "el INCN con 'aeat config profile edit'."
)

_MODELO_202_NOT_APPLICABLE_REASON = (
    "Modalidad del Modelo 202 no aplicable: el perfil declarado no es un "
    "contribuyente del Impuesto sobre Sociedades. La modalidad solo se "
    "deriva para entidades jurídicas obligadas al pago fraccionado del IS."
)


def derive_modelo_202_modality(profile: TaxpayerProfile) -> Modelo202ModalityVerdict:
    """Derive the Modelo 202 pago-fraccionado modality and return a :class:`Modelo202ModalityVerdict`.

    Uses :class:`TaxpayerProfile` for entity-type classification.
    """
    if profile.entity_type is None or profile.entity_type is not EntityType.LEGAL_ENTITY:
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.INCOMPLETE,
            reason=_MODELO_202_NOT_APPLICABLE_REASON,
            legal_refs=_MODELO_202_MODALITY_LEGAL_REFS,
        )
    incn = profile.incn_prior_12_months
    if incn is None:
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.INCOMPLETE,
            reason=_MODELO_202_INCOMPLETE_REASON,
            legal_refs=_MODELO_202_MODALITY_LEGAL_REFS,
        )
    if incn > _MODELO_202_ART_40_3_INCN_THRESHOLD:
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.ART_40_3_MANDATORY,
            reason=_MODELO_202_ART_40_3_MANDATORY_REASON,
            legal_refs=_MODELO_202_MODALITY_LEGAL_REFS,
        )
    return Modelo202ModalityVerdict(
        modality=Modelo202Modality.ART_40_2_OPTIONAL,
        reason=_MODELO_202_ART_40_2_OPTIONAL_REASON,
        legal_refs=_MODELO_202_MODALITY_LEGAL_REFS,
    )


__all__ = [
    "Modelo202Modality",
    "Modelo202ModalityVerdict",
    "derive_modelo_202_modality",
]
