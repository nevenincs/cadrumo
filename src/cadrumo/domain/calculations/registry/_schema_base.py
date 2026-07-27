"""Shared base classes and aliases for registry schema models.

The ``SensitivityClassField`` alias coerces registry ``output_sensitivity``
tokens into :class:`SensitivityClass` members before strict schema validation.
``RevisionReviewStatusField`` does the same for the per-revision governance
stamp's ``review_status`` token.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG, RevisionReviewStatus
from ....core.classification import SensitivityClass
from ._errors import RegistryValidationError
from ._ids import LegalRefId, SourceRefId

__all__ = [
    "CalculationClass",
    "ContinuidadId",
    "DateAxis",
    "EvidenceTier",
    "FormulaOperator",
    "LegalRefs",
    "ModeloFilingCapability",
    "RegistryModel",
    "ReviewStatus",
    "RevisionReviewStatusField",
    "SensitivityClassField",
    "SourceCitation",
    "SourceCitationText",
    "SourceRefs",
]


def _coerce_sensitivity_class(value: object) -> object:
    if isinstance(value, SensitivityClass):
        return value
    if isinstance(value, str):
        return SensitivityClass(value)
    return value


SensitivityClassField = Annotated[SensitivityClass, BeforeValidator(_coerce_sensitivity_class)]


def _coerce_revision_review_status(value: object) -> object:
    if isinstance(value, RevisionReviewStatus):
        return value
    if isinstance(value, str):
        return RevisionReviewStatus(value)
    return value


RevisionReviewStatusField = Annotated[RevisionReviewStatus, BeforeValidator(_coerce_revision_review_status)]
"""Registry ``review_status`` token coerced into a :class:`RevisionReviewStatus` member.

Registry schema models validate under ``strict=True``, which refuses a bare TOML
string for an enum-typed field, so the governance stamp needs this coercion hop
exactly as ``output_sensitivity`` does. An unknown token raises out of the enum
constructor and surfaces as a registry load failure naming the offending value.

Distinct from :data:`ReviewStatus` below, which is the legal catalogue's own
single-valued review vocabulary and governs a different subject.
"""

CalculationClass = Literal["filing", "informative", "summary"]
ModeloFilingCapability = Literal["borrador", "renta_ledger_default"]
"""Discriminator for the calculation role of a ModeloDefinition.

- ``filing``: The modelo computes and submits filing-grade amounts.
  Most modelos fall into this class.
- ``informative``: The modelo collects and reports data but does not
  compute filing-grade amounts. Revisions must have empty ``formulas``
  and empty ``relations``; every casilla must be ``manual`` or
  ``informational``. Modelo 232 is the canonical example.
- ``summary``: The modelo aggregates other modelos (e.g. 390 over 303)
  and may declare cross-model relations but is not a filing modelo.
"""

ReviewStatus = Literal["reviewed"]
DateAxis = Literal["filing_period", "devengo_date", "transaction_date", "invoice_date", "submission_date"]
EvidenceTier = Literal[
    "legal_authority",
    "official_source_guidance",
    "executable_parity_evidence",
    "layout_authority",
]
LegalRefs = Annotated[tuple[LegalRefId, ...], Field(min_length=1)]
SourceRefs = Annotated[tuple[SourceRefId, ...], Field(min_length=1)]
SourceCitationText = Annotated[tuple[str, ...], Field(min_length=1)]
ContinuidadId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$",
    ),
]
FormulaOperator = Literal[
    "add",
    "subtract",
    "multiply",
    "divide",
    "percent",
    "less_than",
    "less_equal",
    "greater_than",
    "greater_equal",
    "equal",
    "sum",
    "min",
    "max",
    "clamp",
    "negate",
    "copy",
    "if_then_else",
    "lookup_parameter",
    "lookup_bracket",
    "lookup_bracket_by_ccaa",
    "m100_resolve_renta_inmobiliaria_imputada",
    "irnr_resolve_tipo_gravamen",
    "m210_resolve_base_imponible",
    "lookup_parameter_by_entity_type",
    "lookup_bracket_by_entity_type",
    "previous_period_value",
    "previous_period_sum",
    "cross_model_sum",
    "age_at_year_end",
    "m131_resolve_modulos_previo",
    "m131_resolve_modulos_minoracion_empleo",
    "m131_resolve_modulos_indice_exceso",
    "m131_resolve_modulos_indices_generales",
    "m131_resolve_modulos_pequena_dimension_ignorado_flag",
    "m131_resolve_modulos_temporada_inicio_conflicto_flag",
    "m100_resolve_eo_agraria_indices_correctores",
    "m303_resolve_modulos_iva_cuota_devengada",
    "m303_resolve_modulos_iva_cuota_minima_pct",
]


class RegistryModel(BaseModel):
    """Strict frozen base for registry schema objects."""

    model_config = STRICT_FROZEN_CONFIG


class SourceCitation(RegistryModel):
    source_ref: SourceRefId
    required_text: SourceCitationText

    @field_validator("required_text")
    @classmethod
    def _required_text_non_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise RegistryValidationError("source citation required_text entries must be non-empty")
        if len(set(value)) != len(value):
            raise RegistryValidationError("source citation required_text entries must be unique")
        return value
