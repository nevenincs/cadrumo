"""Canonical filing-year rows for Modelo 303 regimen simplificado.

The annual Orden owns the activity and module taxonomy.  These models own only
taxpayer facts and their evidence; official record slots are a projection of
this collection and are never persisted as a second set of scalar inputs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_projection_ref import M303_MESA_FACTS, M303_REPEATING_FACTS, M303RegimenSimplificadoFact
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.registry_token import StrictRegistryToken
from ..filing_evidence import FilingEvidenceReference
from .errors import IvaValidationError
from .schema import validate_orden_module_identities

_Token = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
_OfficialActivityName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
ActividadOrdenAnualId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$",
    ),
]
"""Identifier for one filing activity row."""

IaeEpigrafe = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
IndicadorAuxiliarActividad = Literal["1", "2"]
_NonNegative = Annotated[Decimal, Field(ge=Decimal("0"))]

#: An Orden coefficient, which cannot be zero.
#:
#: Separate from :data:`_NonNegative` because for both fields that use it the
#: reachable rule always was stricter and the type did not say so. That is the
#: inverse of a bound hiding outside the annotation: here the annotation claimed
#: a permission nothing could grant.
#:
#: The evidence differs by field and both were checked. A module coefficient is
#: refused by ``validate_orden_module_identities``, and every ``ModuloOrdenAnual``
#: is built straight into an ``ActividadOrdenAnual`` that runs it, so a zero was
#: never constructible. A seasonal index coefficient is compiled from
#: ``M303AnnualOrdenRawSeasonalIndex``, whose own field is ``gt=0``, so a zero
#: could never arrive from the only source there is.
#:
#: The downstream module check stays. It guards a Protocol, so it governs any
#: future implementer rather than only this class.
_PositiveCoefficient = Annotated[Decimal, Field(gt=Decimal("0"))]


def _require_unique_identities(identities: tuple[str, ...], message: str) -> None:
    if len(set(identities)) != len(identities):
        raise IvaValidationError(message)


class ModuloOrdenAnual(BaseModel):
    """One module identity and position established by an annual Orden."""

    model_config = STRICT_FROZEN_CONFIG

    identity: _Token
    order: int = Field(ge=1, le=7)
    coefficient: _PositiveCoefficient
    legal_refs: tuple[_Token, ...] = Field(min_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1)


class ActividadOrdenAnual(BaseModel):
    """Annual Orden taxonomy for one IAE simplified-regime activity."""

    model_config = STRICT_FROZEN_CONFIG

    orden_id: ActividadOrdenAnualId
    ejercicio: FilingYear
    kind: Literal["agricola", "no_agricola"]
    activity_code: _Token
    iae_epigrafe: IaeEpigrafe | None = None
    auxiliary_activity_indicator: IndicadorAuxiliarActividad | None
    modulos: tuple[ModuloOrdenAnual, ...] = ()
    cuota_minima_pct: _NonNegative
    applicable_fact_identities: tuple[_Token, ...] = Field(min_length=1)
    legal_refs: tuple[_Token, ...] = Field(min_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _kind_and_modules_are_coherent(self) -> ActividadOrdenAnual:
        if self.kind == "no_agricola" and self.iae_epigrafe is None:
            raise IvaValidationError("a non-agricultural Orden activity requires an IAE epigraph")
        if self.kind == "agricola" and self.iae_epigrafe is not None:
            raise IvaValidationError("an agricultural Orden activity must use its official activity code")
        validate_orden_module_identities(self.modulos)
        _require_unique_identities(
            self.applicable_fact_identities,
            "an Orden activity contains duplicate applicable fact identities",
        )
        return self


class IndiceCuotaDevengadaAgricolaOrdenAnual(BaseModel):
    """One published agricultural quota index, deliberately not a filing code."""

    model_config = STRICT_FROZEN_CONFIG

    activity_name: _OfficialActivityName
    cuota_devengada_index: _NonNegative
    legal_refs: tuple[_Token, ...] = Field(min_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1)


class PorcentajeIngresoCuentaAgricolaOrdenAnual(BaseModel):
    """One agricultural ingreso-a-cuenta rate, before an official code crosswalk exists."""

    model_config = STRICT_FROZEN_CONFIG

    activity_name: _OfficialActivityName
    percentage: _NonNegative
    legal_refs: tuple[_Token, ...] = Field(min_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1)


class PorcentajeIngresoCuentaIaeOrdenAnual(BaseModel):
    """One source-published IAE ingreso-a-cuenta rate, retained outside filing identity selection."""

    model_config = STRICT_FROZEN_CONFIG

    iae_epigrafe: IaeEpigrafe
    activity_name: _OfficialActivityName
    percentage: _NonNegative
    legal_refs: tuple[_Token, ...] = Field(min_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1)


class IndiceTemporadaOrdenAnual(BaseModel):
    """One contiguous source-published seasonal day band."""

    model_config = STRICT_FROZEN_CONFIG

    minimum_days: int = Field(ge=1, le=180)
    maximum_days: int = Field(ge=1, le=180)
    coefficient: _PositiveCoefficient
    legal_refs: tuple[_Token, ...] = Field(min_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _range_is_ordered(self) -> IndiceTemporadaOrdenAnual:
        if self.minimum_days > self.maximum_days:
            raise IvaValidationError("an annual seasonal index day range must be ordered")
        if self.coefficient <= 0:
            raise IvaValidationError("an annual seasonal index coefficient must be positive")
        return self


class DificilJustificacionOrdenAnual(BaseModel):
    """The single annually sourced IVA difficult-justification percentage."""

    model_config = STRICT_FROZEN_CONFIG

    percentage: _NonNegative
    legal_refs: tuple[_Token, ...] = Field(min_length=2, max_length=2)
    source_refs: tuple[_Token, ...] = Field(min_length=1)


class ReduccionLorcaOrdenAnual(BaseModel):
    """One registry-projected municipal IVA reduction before activity calculation."""

    model_config = STRICT_FROZEN_CONFIG

    ejercicio: FilingYear
    municipality: _Token
    annex_scope: _Token
    percentage: _NonNegative
    calculation_periods: tuple[_Token, ...] = Field(min_length=1)
    legal_refs: tuple[_Token, ...] = Field(min_length=1, max_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1, max_length=1)
    source_content_digest: _Token

    @classmethod
    def from_registry_source(
        cls,
        *,
        ejercicio: FilingYear,
        municipality: str,
        percentage: Decimal,
        legal_ref: str,
        source_ref: str,
        source_content_digest: str,
    ) -> Self:
        """Build the projection only after matching the selected facts authority."""
        from ..calculations.registry.lorca_reduction import resolve_lorca_reduction

        declared = resolve_lorca_reduction(effective_date=date(int(ejercicio), 12, 31))
        if (
            municipality != declared.municipality
            or percentage != declared.percentage
            or legal_ref != declared.legal_ref
            or source_ref != declared.source_ref
            or source_content_digest != declared.source_content_digest
        ):
            raise IvaValidationError("annual Orden reduction source disagrees with fact authority")
        return cls(
            ejercicio=declared.ejercicio,
            municipality=declared.municipality,
            annex_scope=declared.annex_scope,
            percentage=declared.percentage,
            calculation_periods=declared.calculation_periods,
            legal_refs=(declared.legal_ref,),
            source_refs=(declared.source_ref,),
            source_content_digest=declared.source_content_digest,
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _matches_registry_reduction(self) -> Self:
        from ..calculations.registry.lorca_reduction import resolve_lorca_reduction

        declared = resolve_lorca_reduction(effective_date=date(int(self.ejercicio), 12, 31))
        if (
            self.ejercicio != declared.ejercicio
            or self.municipality != declared.municipality
            or self.annex_scope != declared.annex_scope
            or self.percentage != declared.percentage
            or self.calculation_periods != declared.calculation_periods
            or self.legal_refs != (declared.legal_ref,)
            or self.source_refs != (declared.source_ref,)
            or self.source_content_digest != declared.source_content_digest
        ):
            raise IvaValidationError("annual Orden reduction does not match fact authority")
        return self


class AutoridadAgricolaOrdenAnualNoResuelta(BaseModel):
    """Published agricultural axes whose official two-digit filing-code crosswalk is absent."""

    model_config = STRICT_FROZEN_CONFIG

    status: Literal["official_code_crosswalk_unavailable"] = "official_code_crosswalk_unavailable"
    quota_indexes: tuple[IndiceCuotaDevengadaAgricolaOrdenAnual, ...] = Field(min_length=1)
    ingreso_a_cuenta_percentages: tuple[PorcentajeIngresoCuentaAgricolaOrdenAnual, ...] = Field(min_length=1)
    annual_orden_source_ref: _Token
    record_design_source_ref: _Token
    record_design_source_content_digest: _Token
    filing_record: Literal["DP30302"] = "DP30302"
    filing_code_digits: Literal[2] = 2
    refusal_reason: Literal["annual_orden_does_not_publish_dp30302_two_digit_agricultural_crosswalk"] = (
        "annual_orden_does_not_publish_dp30302_two_digit_agricultural_crosswalk"
    )


class M303RegimenSimplificadoScope(StrictRegistryToken):
    """Opaque simplified-regime scope projected from the 0098 composition fact."""

    __slots__ = ()

    _vocabulary_label = "M303 simplified-regime scope"
    _projection_source = "registry"


class M303RegimenSimplificadoScopeDecision(BaseModel):
    """Explicit registry-projected scope input for the M303 simplified branch."""

    model_config = STRICT_FROZEN_CONFIG

    scope: M303RegimenSimplificadoScope

    @property
    def is_not_claimed(self) -> bool:
        """Whether the registry-declared scope excludes the simplified branch."""
        return self.scope.value == "not_claimed"


class HechoActividadSimplificado(BaseModel):
    """One declared or attested activity fact at its closed semantic coordinate."""

    model_config = STRICT_FROZEN_CONFIG

    fact: M303RegimenSimplificadoFact
    sub_index: int | None = Field(default=None, ge=1, le=4)
    value: str | Decimal
    evidence_reference: FilingEvidenceReference

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_closed_fact_multiplicity(self) -> HechoActividadSimplificado:
        if self.fact in M303_MESA_FACTS and self.sub_index is None:
            raise IvaValidationError("a Mesa simplified-regime fact requires sub_index")
        if self.fact not in M303_REPEATING_FACTS and self.sub_index is not None:
            raise IvaValidationError("a singleton simplified-regime fact must not carry sub_index")
        return self

    @field_validator("value")
    @classmethod
    @pydantic_validation_boundary
    def _value_is_present(cls, value: str | Decimal) -> str | Decimal:
        if isinstance(value, str) and not value.strip():
            raise IvaValidationError("an applicable activity fact cannot be blank")
        if isinstance(value, Decimal) and value < 0:
            raise IvaValidationError("an activity fact cannot be negative")
        return value


class EntradaModuloSimplificado(BaseModel):
    """One taxpayer-declared module quantity and its filing evidence."""

    model_config = STRICT_FROZEN_CONFIG

    module_identity: _Token
    declared_quantity: _NonNegative
    evidence_reference: FilingEvidenceReference


class ActividadAgricolaSimplificado(BaseModel):
    """One agricultural, livestock, or forestry simplified-regime activity."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["agricola"] = "agricola"
    orden_id: ActividadOrdenAnualId
    ejercicio: FilingYear
    activity_id: _Token
    activity_code: _Token
    facts: tuple[HechoActividadSimplificado, ...] = Field(min_length=1)
    evidence_reference: FilingEvidenceReference

    @model_validator(mode="after")
    def _facts_are_unique(self) -> ActividadAgricolaSimplificado:
        _require_unique_fact_identities(self.facts)
        return self


class LorcaActivityEligibility(BaseModel):
    """Evidence that this Annex II activity is, or is not, carried out in Lorca."""

    model_config = STRICT_FROZEN_CONFIG

    eligible: bool
    evidence_reference: FilingEvidenceReference


class ActividadNoAgricolaSimplificado(BaseModel):
    """One non-agricultural simplified-regime IAE activity."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["no_agricola"] = "no_agricola"
    orden_id: ActividadOrdenAnualId
    ejercicio: FilingYear
    activity_id: _Token
    iae_epigrafe: IaeEpigrafe
    auxiliary_activity_indicator: IndicadorAuxiliarActividad | None
    lorca_eligibility: LorcaActivityEligibility | None = None
    modulos: tuple[EntradaModuloSimplificado, ...] = Field(min_length=1, max_length=7)
    facts: tuple[HechoActividadSimplificado, ...] = ()
    evidence_reference: FilingEvidenceReference

    @model_validator(mode="after")
    def _entries_are_unique(self) -> ActividadNoAgricolaSimplificado:
        _require_unique_identities(
            tuple(module.module_identity for module in self.modulos),
            "a filing activity contains duplicate module identities",
        )
        _require_unique_fact_identities(self.facts)
        return self


RegimenSimplificadoActivity = Annotated[
    ActividadAgricolaSimplificado | ActividadNoAgricolaSimplificado,
    Field(discriminator="kind"),
]


class RegimenSimplificadoFilingRows(BaseModel):
    """Ordered canonical activity collection for one filing year."""

    model_config = STRICT_FROZEN_CONFIG

    ejercicio: FilingYear
    activities: tuple[RegimenSimplificadoActivity, ...] = Field(max_length=12)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _collection_is_ordered_and_conflict_free(self) -> RegimenSimplificadoFilingRows:
        if any(activity.ejercicio != self.ejercicio for activity in self.activities):
            raise IvaValidationError("every simplified-regime activity must match the filing year")
        _require_unique_identities(
            tuple(activity.activity_id for activity in self.activities),
            "simplified-regime activity identities must be unique",
        )
        agricultural, non_agricultural = _activities_by_kind(self.activities)
        if len(agricultural) > 6 or len(non_agricultural) > 6:
            raise IvaValidationError("DP30302 permits at most six activities of each kind")
        if self.activities != agricultural + non_agricultural:
            raise IvaValidationError("activities must be ordered agricultural then non-agricultural")
        return self

    def records(self) -> tuple[tuple[RegimenSimplificadoActivity, ...], ...]:
        """Pack exactly two activities of each kind into at most three records."""
        agricultural, non_agricultural = _activities_by_kind(self.activities)
        count = max((len(agricultural) + 1) // 2, (len(non_agricultural) + 1) // 2)
        return tuple(
            agricultural[index * 2 : index * 2 + 2] + non_agricultural[index * 2 : index * 2 + 2]
            for index in range(count)
        )


def _activities_by_kind(
    activities: tuple[RegimenSimplificadoActivity, ...],
) -> tuple[tuple[ActividadAgricolaSimplificado, ...], tuple[ActividadNoAgricolaSimplificado, ...]]:
    return (
        tuple(activity for activity in activities if activity.kind == "agricola"),
        tuple(activity for activity in activities if activity.kind == "no_agricola"),
    )


def validate_regimen_simplificado_rows(
    rows: RegimenSimplificadoFilingRows,
    *,
    orden: tuple[ActividadOrdenAnual, ...],
    agricultural_authority: AutoridadAgricolaOrdenAnualNoResuelta,
    applicable: bool,
    censo_iae_epigraphs: frozenset[str],
    orden_ejercicio: int | None = None,
) -> None:
    """Fail closed on applicability, annual taxonomy, order, and censo conflicts."""
    if not applicable:
        if rows.activities:
            raise IvaValidationError("non-applicable regimen simplificado cannot carry activity rows")
        return
    if not rows.activities:
        raise IvaValidationError("applicable regimen simplificado requires activity rows")
    by_id = {item.orden_id: item for item in orden}
    source_year = rows.ejercicio if orden_ejercicio is None else orden_ejercicio
    if len(by_id) != len(orden) or any(item.ejercicio != source_year for item in orden):
        raise IvaValidationError("annual Orden taxonomy is duplicate, conflicting, or for the wrong year")
    for row in rows.activities:
        if isinstance(row, ActividadAgricolaSimplificado):
            raise IvaValidationError(
                "agricultural annual Orden authority cannot resolve DP30302 activity code: "
                f"{agricultural_authority.refusal_reason}",
            )
        _validate_regimen_simplificado_activity(row, by_id, orden, censo_iae_epigraphs)


def _validate_regimen_simplificado_activity(
    row: RegimenSimplificadoActivity,
    orden_by_id: dict[ActividadOrdenAnualId, ActividadOrdenAnual],
    orden: tuple[ActividadOrdenAnual, ...],
    censo_iae_epigraphs: frozenset[str],
) -> None:
    annual = orden_by_id.get(row.orden_id)
    if annual is None:
        raise IvaValidationError(f"activity {row.activity_id!r} is absent from the applicable annual Orden")
    if annual.kind != row.kind:
        raise IvaValidationError(f"activity {row.activity_id!r} kind conflicts with its annual Orden identity")
    if isinstance(row, ActividadAgricolaSimplificado) and row.activity_code != annual.activity_code:
        raise IvaValidationError(f"activity {row.activity_id!r} code conflicts with its annual Orden identity")
    if row.kind == "no_agricola":
        _validate_non_agricultural_activity(row, annual, orden, censo_iae_epigraphs)


def _validate_non_agricultural_activity(
    row: ActividadNoAgricolaSimplificado,
    annual: ActividadOrdenAnual,
    orden: tuple[ActividadOrdenAnual, ...],
    censo_iae_epigraphs: frozenset[str],
) -> None:
    if row.iae_epigrafe != annual.iae_epigrafe:
        raise IvaValidationError(f"activity {row.activity_id!r} IAE conflicts with its annual Orden identity")
    resolved = _resolve_non_agricultural_orden_activity(row, orden)
    if resolved.orden_id != annual.orden_id:
        raise IvaValidationError(
            f"activity {row.activity_id!r} Orden identity conflicts with its exact IAE discriminator"
        )
    if row.iae_epigrafe not in censo_iae_epigraphs:
        raise IvaValidationError(f"IAE epigraph {row.iae_epigrafe!r} conflicts with censo")
    actual = tuple(module.module_identity for module in row.modulos)
    expected = tuple(module.identity for module in annual.modulos)
    if actual != expected:
        raise IvaValidationError(
            f"activity {row.activity_id!r} module identities/order do not match the annual Orden",
        )


def _resolve_non_agricultural_orden_activity(
    row: ActividadNoAgricolaSimplificado,
    orden: tuple[ActividadOrdenAnual, ...],
) -> ActividadOrdenAnual:
    candidates = tuple(
        activity
        for activity in orden
        if activity.kind == "no_agricola"
        and activity.iae_epigrafe == row.iae_epigrafe
        and activity.auxiliary_activity_indicator == row.auxiliary_activity_indicator
    )
    if len(candidates) != 1:
        raise IvaValidationError(f"activity {row.activity_id!r} does not resolve to exactly one annual Orden activity")
    return candidates[0]


def _require_unique_fact_identities(facts: tuple[HechoActividadSimplificado, ...]) -> None:
    identities = tuple((fact.fact, fact.sub_index) for fact in facts)
    if len(set(identities)) != len(identities):
        raise IvaValidationError("an activity contains duplicate or conflicting fact identities")


__all__ = [
    "ActividadAgricolaSimplificado",
    "ActividadNoAgricolaSimplificado",
    "ActividadOrdenAnual",
    "ActividadOrdenAnualId",
    "AutoridadAgricolaOrdenAnualNoResuelta",
    "DificilJustificacionOrdenAnual",
    "EntradaModuloSimplificado",
    "HechoActividadSimplificado",
    "IaeEpigrafe",
    "IndicadorAuxiliarActividad",
    "IndiceCuotaDevengadaAgricolaOrdenAnual",
    "IndiceTemporadaOrdenAnual",
    "ModuloOrdenAnual",
    "PorcentajeIngresoCuentaAgricolaOrdenAnual",
    "PorcentajeIngresoCuentaIaeOrdenAnual",
    "ReduccionLorcaOrdenAnual",
    "RegimenSimplificadoActivity",
    "RegimenSimplificadoFilingRows",
    "validate_regimen_simplificado_rows",
]
