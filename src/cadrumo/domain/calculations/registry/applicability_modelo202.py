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
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, ResolvedScalarFact, ScalarFactQuery
from .ids import LegalRefId
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority

type _OperatorReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

_MODELO_202_APPLICABILITY_FACT_ID = "modelo-202-applicability-catalogue"


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


def _modelo_202_applicability_declarations(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority,
) -> dict[str, str]:
    """Resolve the dated Modelo 202 applicability catalogue."""
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_MODELO_202_APPLICABILITY_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        from .errors import RegistryValidationError

        raise RegistryValidationError(
            f"Modelo 202 applicability fact {_MODELO_202_APPLICABILITY_FACT_ID!r} must resolve to a mapping",
        )
    declarations = {
        entry.key: entry.value
        for entry in resolved.payload.entries
        if isinstance(entry.key, str) and isinstance(entry.value, str)
    }
    required = {
        "threshold.fact_id",
        "reason.not_applicable",
        "reason.incomplete",
        f"reason.{Modelo202Modality.ART_40_3_MANDATORY.value}",
        f"reason.{Modelo202Modality.ART_40_2_OPTIONAL.value}",
        "legal_refs.not_applicable",
        "legal_refs.incomplete",
        f"legal_refs.{Modelo202Modality.ART_40_3_MANDATORY.value}",
        f"legal_refs.{Modelo202Modality.ART_40_2_OPTIONAL.value}",
    }
    missing = sorted(required - declarations.keys())
    if missing:
        from .errors import RegistryValidationError

        raise RegistryValidationError(
            f"Modelo 202 applicability fact {_MODELO_202_APPLICABILITY_FACT_ID!r} is missing {missing!r}",
        )
    return declarations


def _modelo_202_legal_refs(
    declarations: dict[str, str],
    outcome: str,
) -> tuple[LegalRefId, ...]:
    """Materialise the catalogue's legal-reference tuple for a verdict."""
    key = f"legal_refs.{outcome}"
    return tuple(cast(LegalRefId, item) for item in declarations[key].split("|") if item)


def resolve_modelo_202_art_40_3_incn_threshold(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedScalarFact:
    """Resolve the LIS art. 40.3 INCN threshold with complete authority provenance."""
    if authority is None:
        from .authority import bundled_authority

        authority = bundled_authority()
    declarations = _modelo_202_applicability_declarations(
        effective_date=effective_date,
        authority=authority,
    )
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=declarations["threshold.fact_id"],
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
    if authority is None:
        from .authority import bundled_authority

        authority = bundled_authority()
    declarations = _modelo_202_applicability_declarations(
        effective_date=effective_date,
        authority=authority,
    )
    if entity_type is None or entity_type is not EntityType.LEGAL_ENTITY:
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.INCOMPLETE,
            reason=declarations["reason.not_applicable"],
            legal_refs=_modelo_202_legal_refs(declarations, "not_applicable"),
        )
    if incn_prior_12_months is None:
        return Modelo202ModalityVerdict(
            modality=Modelo202Modality.INCOMPLETE,
            reason=declarations["reason.incomplete"],
            legal_refs=_modelo_202_legal_refs(declarations, "incomplete"),
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
            reason=declarations[f"reason.{Modelo202Modality.ART_40_3_MANDATORY.value}"],
            legal_refs=_modelo_202_legal_refs(
                declarations,
                Modelo202Modality.ART_40_3_MANDATORY.value,
            ),
            threshold_fact=threshold_fact,
        )
    return Modelo202ModalityVerdict(
        modality=Modelo202Modality.ART_40_2_OPTIONAL,
        reason=declarations[f"reason.{Modelo202Modality.ART_40_2_OPTIONAL.value}"],
        legal_refs=_modelo_202_legal_refs(declarations, Modelo202Modality.ART_40_2_OPTIONAL.value),
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
