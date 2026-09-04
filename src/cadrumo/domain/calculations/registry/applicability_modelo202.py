"""Modelo 202 applicability modality gate.

The full-profile entry point reads :class:`TaxpayerProfile` entity type and
INCN facts, then delegates to the raw-input modality rule used by calculation.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ....core.external_constants import MODELO_202_ART_40_3_INCN_THRESHOLD_EUR
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...contribuyente.entity_type import EntityType
from ...deadlines.models import TaxpayerProfile
from .errors import RegistryFailureClassification, RegistryFailureCondition
from .ids import LegalRefId

type _OperatorReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

_MODELO_202_MODALITY_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-27-2014:art-40",
    "ley-27-2014:art-40-3",
)
"""Scoped registry citation keys grounding the Modelo 202 modality gate."""


class Modelo202Modality(StrEnum):
    """The pago-fraccionado modality available to a Modelo 202 filer."""

    ART_40_2_OPTIONAL = "art_40_2_optional"
    ART_40_3_MANDATORY = "art_40_3_mandatory"
    INCOMPLETE = "incomplete"


class Modelo202ModalityVerdict(BaseModel):
    """The derived Modelo 202 modality verdict and its grounding."""

    model_config = _STRICT_FROZEN

    modality: Modelo202Modality
    reason: _OperatorReason
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    failure: RegistryFailureClassification | None = None
    """Domain facts for a boundary to project when the modality is incomplete."""


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
    "fraccionado equivocado es peor que una respuesta incompleta."
)

_MODELO_202_NOT_APPLICABLE_REASON = (
    "Modalidad del Modelo 202 no aplicable: el perfil declarado no es un "
    "contribuyente del Impuesto sobre Sociedades. La modalidad solo se "
    "deriva para entidades jurídicas obligadas al pago fraccionado del IS."
)


def modelo_202_modality_from_inputs(
    *,
    entity_type: EntityType | None,
    incn_prior_12_months: Decimal | None,
) -> Modelo202ModalityVerdict:
    """Derive the Modelo 202 modality from the two raw inputs (entity type + INCN).

    The SINGLE modality definition, callable WITHOUT a full
    :class:`TaxpayerProfile` so the calculation engine can evaluate it off the
    wizard-free profile projection (``record_to_path_values``) in a non-CLI
    context where the wizard ``SETUP_FLOW`` catalogue is not registered. No
    fork: :func:`derive_modelo_202_modality` delegates here.

    Returns:
        :class:`Modelo202ModalityVerdict`: Derived modality, explanation, and
        legal grounding.
    """
    if entity_type is None or entity_type is not EntityType.LEGAL_ENTITY:
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.INCOMPLETE,
            reason=_MODELO_202_NOT_APPLICABLE_REASON,
            legal_refs=_MODELO_202_MODALITY_LEGAL_REFS,
        )
    if incn_prior_12_months is None:
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.INCOMPLETE,
            reason=_MODELO_202_INCOMPLETE_REASON,
            legal_refs=_MODELO_202_MODALITY_LEGAL_REFS,
            failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.MODELO_202_INCN_DECLARED,
                facts={
                    "modelo": Modelo.M202.value,
                    "incn_prior_12_months_declared": False,
                    "entity_type_legal": True,
                },
            ),
        )
    if incn_prior_12_months > MODELO_202_ART_40_3_INCN_THRESHOLD_EUR:
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


def derive_modelo_202_modality(profile: TaxpayerProfile) -> Modelo202ModalityVerdict:
    """Derive the Modelo 202 pago-fraccionado modality and return a :class:`Modelo202ModalityVerdict`.

    Reads :class:`TaxpayerProfile` entity type and INCN, then delegates the rule
    to :func:`modelo_202_modality_from_inputs` (the single definition).
    """
    return modelo_202_modality_from_inputs(
        entity_type=profile.entity_type,
        incn_prior_12_months=profile.incn_prior_12_months,
    )


__all__ = [
    "Modelo202Modality",
    "Modelo202ModalityVerdict",
    "derive_modelo_202_modality",
]
