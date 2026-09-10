"""Modelo 202 applicability modality gate.

The full-profile entry point reads :class:`TaxpayerProfile` entity type and
INCN facts, then delegates to the raw-input modality rule used by calculation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, cast

from pydantic import BaseModel, Field, StringConstraints

from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...contribuyente.entity_type import EntityType
from ...deadlines.models import TaxpayerProfile
from .errors import RegistryFailureClassification, RegistryFailureCondition
from .facts.resolution import ResolvedScalarFact, ScalarFactQuery
from .ids import LegalRefId
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority

type _OperatorReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

_MODELO_202_MODALITY_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-27-2014:art-40",
    "ley-27-2014:art-40-3",
)
"""Scoped registry citation keys grounding the Modelo 202 modality gate."""

_MODELO_202_ART_40_3_INCN_THRESHOLD_FACT_ID = "lis-art-40-3-incn-threshold"


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
    threshold_fact: ResolvedScalarFact | None = None
    """Resolved statutory threshold, including the authority provenance used."""


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


def resolve_modelo_202_art_40_3_incn_threshold(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedScalarFact:
    """Resolve the LIS art. 40.3 INCN threshold with complete authority provenance."""
    if authority is None:
        from .authority import bundled_authority

        authority = bundled_authority()
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=_MODELO_202_ART_40_3_INCN_THRESHOLD_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    return cast("ResolvedScalarFact", resolved)


def modelo_202_incn_threshold_decimal(threshold: ResolvedScalarFact) -> Decimal:
    """Return the Modelo 202 INCN threshold only when the governed payload is decimal."""
    value = threshold.payload.value
    if not isinstance(value, Decimal):
        from .errors import RegistryValidationError

        raise RegistryValidationError(
            f"Modelo 202 INCN threshold fact {threshold.fact_id!r} resolved non-decimal payload {value!r}",
        )
    return value


def modelo_202_modality_from_inputs(
    *,
    entity_type: EntityType | None,
    incn_prior_12_months: Decimal | None,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
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
    threshold_fact = resolve_modelo_202_art_40_3_incn_threshold(
        effective_date=effective_date,
        authority=authority,
    )
    if incn_prior_12_months > modelo_202_incn_threshold_decimal(threshold_fact):
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.ART_40_3_MANDATORY,
            reason=_MODELO_202_ART_40_3_MANDATORY_REASON,
            legal_refs=_MODELO_202_MODALITY_LEGAL_REFS,
            threshold_fact=threshold_fact,
        )
    return Modelo202ModalityVerdict(
        modality=Modelo202Modality.ART_40_2_OPTIONAL,
        reason=_MODELO_202_ART_40_2_OPTIONAL_REASON,
        legal_refs=_MODELO_202_MODALITY_LEGAL_REFS,
        threshold_fact=threshold_fact,
    )


def derive_modelo_202_modality(
    profile: TaxpayerProfile,
    *,
    effective_date: date,
) -> Modelo202ModalityVerdict:
    """Derive the Modelo 202 pago-fraccionado modality and return a :class:`Modelo202ModalityVerdict`.

    Reads :class:`TaxpayerProfile` entity type and INCN, then delegates the rule
    to :func:`modelo_202_modality_from_inputs` (the single definition).
    """
    return modelo_202_modality_from_inputs(
        entity_type=profile.entity_type,
        incn_prior_12_months=profile.incn_prior_12_months,
        effective_date=effective_date,
    )


__all__ = [
    "Modelo202Modality",
    "Modelo202ModalityVerdict",
    "derive_modelo_202_modality",
    "modelo_202_incn_threshold_decimal",
    "modelo_202_modality_from_inputs",
    "resolve_modelo_202_art_40_3_incn_threshold",
]
