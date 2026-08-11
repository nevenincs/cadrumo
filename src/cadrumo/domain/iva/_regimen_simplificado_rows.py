"""Canonical filing-year rows for Modelo 303 regimen simplificado.

The annual Orden owns the activity and module taxonomy.  These models own only
taxpayer facts and their evidence; official record slots are a projection of
this collection and are never persisted as a second set of scalar inputs.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ._errors import IvaValidationError

_Token = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
_EvidenceReference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
_IaeEpigrafe = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
_NonNegative = Annotated[Decimal, Field(ge=Decimal("0"))]


class ModuloOrdenAnual(BaseModel):
    """One module identity and position established by an annual Orden."""

    model_config = STRICT_FROZEN_CONFIG

    identity: _Token
    order: int = Field(ge=1, le=7)
    coefficient: _NonNegative
    legal_refs: tuple[_Token, ...] = Field(min_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1)


class ActividadOrdenAnual(BaseModel):
    """Annual Orden taxonomy for one IAE simplified-regime activity."""

    model_config = STRICT_FROZEN_CONFIG

    ejercicio: int = Field(ge=2000, le=2099)
    kind: Literal["agricola", "no_agricola"]
    activity_code: _Token
    iae_epigrafe: _IaeEpigrafe | None = None
    modulos: tuple[ModuloOrdenAnual, ...] = ()
    applicable_fact_identities: tuple[_Token, ...] = Field(min_length=1)
    legal_refs: tuple[_Token, ...] = Field(min_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _kind_and_modules_are_coherent(self) -> ActividadOrdenAnual:
        if self.kind == "no_agricola" and self.iae_epigrafe is None:
            raise IvaValidationError("a non-agricultural Orden activity requires an IAE epigraph")
        if self.kind == "agricola" and self.iae_epigrafe is not None:
            raise IvaValidationError("an agricultural Orden activity must use its official activity code")
        identities = tuple(module.identity for module in self.modulos)
        orders = tuple(module.order for module in self.modulos)
        if len(set(identities)) != len(identities):
            raise IvaValidationError("an Orden activity contains duplicate module identities")
        if orders != tuple(range(1, len(self.modulos) + 1)):
            raise IvaValidationError("annual Orden modules must be complete and ordered from one")
        if len(set(self.applicable_fact_identities)) != len(self.applicable_fact_identities):
            raise IvaValidationError("an Orden activity contains duplicate applicable fact identities")
        return self


class HechoActividadSimplificado(BaseModel):
    """One declared or attested activity fact, keyed by Orden identity."""

    model_config = STRICT_FROZEN_CONFIG

    identity: _Token
    value: str | Decimal
    evidence_reference: _EvidenceReference

    @field_validator("value")
    @classmethod
    def _value_is_present(cls, value: str | Decimal) -> str | Decimal:
        if isinstance(value, str) and not value.strip():
            raise IvaValidationError("an applicable activity fact cannot be blank")
        if isinstance(value, Decimal) and value < 0:
            raise IvaValidationError("an activity fact cannot be negative")
        return value


class EntradaModuloSimplificado(BaseModel):
    """Taxpayer quantity and evidence-backed off-form result for one module."""

    model_config = STRICT_FROZEN_CONFIG

    module_identity: _Token
    declared_quantity: _NonNegative
    off_form_result: _NonNegative
    evidence_reference: _EvidenceReference


class ActividadAgricolaSimplificado(BaseModel):
    """One agricultural, livestock, or forestry simplified-regime activity."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["agricola"] = "agricola"
    ejercicio: int = Field(ge=2000, le=2099)
    activity_id: _Token
    activity_code: _Token
    facts: tuple[HechoActividadSimplificado, ...] = Field(min_length=1)
    evidence_reference: _EvidenceReference

    @model_validator(mode="after")
    def _facts_are_unique(self) -> ActividadAgricolaSimplificado:
        _require_unique_fact_identities(self.facts)
        return self


class ActividadNoAgricolaSimplificado(BaseModel):
    """One non-agricultural simplified-regime IAE activity."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["no_agricola"] = "no_agricola"
    ejercicio: int = Field(ge=2000, le=2099)
    activity_id: _Token
    iae_epigrafe: _IaeEpigrafe
    modulos: tuple[EntradaModuloSimplificado, ...] = Field(min_length=1, max_length=7)
    facts: tuple[HechoActividadSimplificado, ...] = ()
    evidence_reference: _EvidenceReference

    @model_validator(mode="after")
    def _entries_are_unique(self) -> ActividadNoAgricolaSimplificado:
        identities = tuple(module.module_identity for module in self.modulos)
        if len(set(identities)) != len(identities):
            raise IvaValidationError("a filing activity contains duplicate module identities")
        _require_unique_fact_identities(self.facts)
        return self


RegimenSimplificadoActivity = Annotated[
    ActividadAgricolaSimplificado | ActividadNoAgricolaSimplificado,
    Field(discriminator="kind"),
]


class RegimenSimplificadoFilingRows(BaseModel):
    """Ordered canonical activity collection for one filing year."""

    model_config = STRICT_FROZEN_CONFIG

    ejercicio: int = Field(ge=2000, le=2099)
    activities: tuple[RegimenSimplificadoActivity, ...] = Field(max_length=12)

    @model_validator(mode="after")
    def _collection_is_ordered_and_conflict_free(self) -> RegimenSimplificadoFilingRows:
        if any(activity.ejercicio != self.ejercicio for activity in self.activities):
            raise IvaValidationError("every simplified-regime activity must match the filing year")
        ids = tuple(activity.activity_id for activity in self.activities)
        if len(set(ids)) != len(ids):
            raise IvaValidationError("simplified-regime activity identities must be unique")
        agricultural = tuple(activity for activity in self.activities if activity.kind == "agricola")
        non_agricultural = tuple(activity for activity in self.activities if activity.kind == "no_agricola")
        if len(agricultural) > 6 or len(non_agricultural) > 6:
            raise IvaValidationError("DP30302 permits at most six activities of each kind")
        if self.activities != agricultural + non_agricultural:
            raise IvaValidationError("activities must be ordered agricultural then non-agricultural")
        agricultural_codes = tuple(activity.activity_code for activity in agricultural)
        epigraphs = tuple(activity.iae_epigrafe for activity in non_agricultural)
        if len(set(agricultural_codes)) != len(agricultural_codes) or len(set(epigraphs)) != len(epigraphs):
            raise IvaValidationError("duplicate or conflicting simplified-regime activities are forbidden")
        return self

    def records(self) -> tuple[tuple[RegimenSimplificadoActivity, ...], ...]:
        """Pack exactly two activities of each kind into at most three records."""
        agricultural = tuple(activity for activity in self.activities if activity.kind == "agricola")
        non_agricultural = tuple(activity for activity in self.activities if activity.kind == "no_agricola")
        count = max((len(agricultural) + 1) // 2, (len(non_agricultural) + 1) // 2)
        return tuple(
            agricultural[index * 2 : index * 2 + 2] + non_agricultural[index * 2 : index * 2 + 2]
            for index in range(count)
        )


def validate_regimen_simplificado_rows(
    rows: RegimenSimplificadoFilingRows,
    *,
    orden: tuple[ActividadOrdenAnual, ...],
    applicable: bool,
    censo_iae_epigraphs: frozenset[str],
) -> None:
    """Fail closed on applicability, annual taxonomy, order, and censo conflicts."""
    if not applicable:
        if rows.activities:
            raise IvaValidationError("non-applicable regimen simplificado cannot carry activity rows")
        return
    if not rows.activities:
        raise IvaValidationError("applicable regimen simplificado requires activity rows")
    by_key = {(item.kind, item.activity_code if item.kind == "agricola" else item.iae_epigrafe): item for item in orden}
    if len(by_key) != len(orden) or any(item.ejercicio != rows.ejercicio for item in orden):
        raise IvaValidationError("annual Orden taxonomy is duplicate, conflicting, or for the wrong year")
    for row in rows.activities:
        key = (row.kind, row.activity_code if row.kind == "agricola" else row.iae_epigrafe)
        annual = by_key.get(key)
        if annual is None:
            raise IvaValidationError(f"activity {row.activity_id!r} is absent from the applicable annual Orden")
        if row.kind == "no_agricola":
            if row.iae_epigrafe not in censo_iae_epigraphs:
                raise IvaValidationError(f"IAE epigraph {row.iae_epigrafe!r} conflicts with censo")
            actual = tuple(module.module_identity for module in row.modulos)
            expected = tuple(module.identity for module in annual.modulos)
            if actual != expected:
                raise IvaValidationError(
                    f"activity {row.activity_id!r} module identities/order do not match the annual Orden",
                )
        actual_facts = frozenset(fact.identity for fact in row.facts)
        expected_facts = frozenset(annual.applicable_fact_identities)
        if actual_facts != expected_facts:
            raise IvaValidationError(
                f"activity {row.activity_id!r} applicable facts do not match the annual Orden",
            )


def _require_unique_fact_identities(facts: tuple[HechoActividadSimplificado, ...]) -> None:
    identities = tuple(fact.identity for fact in facts)
    if len(set(identities)) != len(identities):
        raise IvaValidationError("an activity contains duplicate or conflicting fact identities")


__all__ = [
    "ActividadAgricolaSimplificado",
    "ActividadNoAgricolaSimplificado",
    "ActividadOrdenAnual",
    "EntradaModuloSimplificado",
    "HechoActividadSimplificado",
    "ModuloOrdenAnual",
    "RegimenSimplificadoActivity",
    "RegimenSimplificadoFilingRows",
    "validate_regimen_simplificado_rows",
]
