"""Canonical filing-year rows for Modelo 303 regimen simplificado.

The annual Orden owns the activity and module taxonomy.  These models own only
taxpayer facts and their evidence; official record slots are a projection of
this collection and are never persisted as a second set of scalar inputs.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, M303RegimenSimplificadoFact
from ..filing_evidence import FilingEvidenceReference
from ._schema import validate_orden_module_identities
from .errors import IvaValidationError

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
"""Canonical identifier for one annual-Orden activity row."""

IaeEpigrafe = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
IndicadorAuxiliarActividad = Literal["1", "2"]
_NonNegative = Annotated[Decimal, Field(ge=Decimal("0"))]


def _require_unique_identities(identities: tuple[str, ...], message: str) -> None:
    if len(set(identities)) != len(identities):
        raise IvaValidationError(message)


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

    orden_id: ActividadOrdenAnualId
    ejercicio: int = Field(ge=2000, le=2099)
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
    coefficient: _NonNegative
    legal_refs: tuple[_Token, ...] = Field(min_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1)

    @model_validator(mode="after")
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
    """The 2022 Annex-II Lorca IVA reduction before any activity calculation."""

    model_config = STRICT_FROZEN_CONFIG

    ejercicio: Literal[2022] = 2022
    municipality: Literal["Lorca"] = "Lorca"
    annex_scope: Literal["ANEXO II"] = "ANEXO II"
    percentage: _NonNegative
    calculation_periods: tuple[Literal["trimestral", "anual"], Literal["trimestral", "anual"]] = (
        "trimestral",
        "anual",
    )
    legal_refs: tuple[_Token, ...] = Field(min_length=1, max_length=1)
    source_refs: tuple[_Token, ...] = Field(min_length=1, max_length=1)
    source_content_digest: _Token

    @model_validator(mode="after")
    def _is_the_exact_lorca_2022_reduction(self) -> ReduccionLorcaOrdenAnual:
        if self.percentage != Decimal("20"):
            raise IvaValidationError("the Lorca 2022 annual Orden reduction must be exactly 20 percent")
        if self.calculation_periods != ("trimestral", "anual"):
            raise IvaValidationError("the Lorca 2022 reduction must cover quarterly and annual calculations")
        if self.legal_refs != ("orden-hfp-1335-2021:da-4-lorca-2022-reduction:lorca-2022-reduction",):
            raise IvaValidationError("the Lorca 2022 reduction must retain its exact HFP/1335 legal reference")
        if self.source_refs != ("boe-orden-hfp-1335-2021-iva-authority",):
            raise IvaValidationError("the Lorca 2022 reduction must retain its exact HFP/1335 source reference")
        if self.source_content_digest != "3fda96dcf2dcb3b3f0863bc07b0eabd45e21c6850d4b611e635627befb450c46":
            raise IvaValidationError("the Lorca 2022 reduction must retain its exact HFP/1335 source digest")
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


class M303RegimenSimplificadoScope(StrEnum):
    """Closed M303 simplified-regime scope outcomes available before S58 evidence."""

    REGIMEN_SIMPLIFICADO_NOT_CLAIMED = "regimen_simplificado_not_claimed"
    REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED = "regimen_simplificado_evidence_required"


class M303RegimenSimplificadoScopeDecision(BaseModel):
    """Explicit closed scope input for the M303 simplified branch."""

    model_config = STRICT_FROZEN_CONFIG

    scope: M303RegimenSimplificadoScope

    @property
    def is_not_claimed(self) -> bool:
        """Whether the explicit general-regime decision excludes the branch."""
        return self.scope is M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED


class HechoActividadSimplificado(BaseModel):
    """One declared or attested activity fact at its closed semantic coordinate."""

    model_config = STRICT_FROZEN_CONFIG

    fact: M303RegimenSimplificadoFact
    sub_index: int | None = Field(default=None, ge=1, le=4)
    value: str | Decimal
    evidence_reference: FilingEvidenceReference

    @model_validator(mode="after")
    def _require_closed_fact_multiplicity(self) -> HechoActividadSimplificado:
        mesa_facts = {
            M303RegimenSimplificadoFact.MESAS_CAPACIDAD,
            M303RegimenSimplificadoFact.MESAS_DIAS_CUARTO_TRIMESTRE,
            M303RegimenSimplificadoFact.MESAS_NUMERO,
        }
        repeating_facts = mesa_facts | {
            M303RegimenSimplificadoFact.SUPERFICIE_HORNO_DIAS_CUARTO_TRIMESTRE,
            M303RegimenSimplificadoFact.SUPERFICIE_HORNO_CUARTO_TRIMESTRE,
        }
        if self.fact in mesa_facts and self.sub_index is None:
            raise IvaValidationError("a Mesa simplified-regime fact requires sub_index")
        if self.fact not in repeating_facts and self.sub_index is not None:
            raise IvaValidationError("a singleton simplified-regime fact must not carry sub_index")
        return self

    @field_validator("value")
    @classmethod
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
    ejercicio: int = Field(ge=2000, le=2099)
    activity_id: _Token
    activity_code: _Token
    facts: tuple[HechoActividadSimplificado, ...] = Field(min_length=1)
    evidence_reference: FilingEvidenceReference

    @model_validator(mode="after")
    def _facts_are_unique(self) -> ActividadAgricolaSimplificado:
        _require_unique_fact_identities(self.facts)
        return self


class ActividadNoAgricolaSimplificado(BaseModel):
    """One non-agricultural simplified-regime IAE activity."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["no_agricola"] = "no_agricola"
    orden_id: ActividadOrdenAnualId
    ejercicio: int = Field(ge=2000, le=2099)
    activity_id: _Token
    iae_epigrafe: IaeEpigrafe
    auxiliary_activity_indicator: IndicadorAuxiliarActividad | None
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

    ejercicio: int = Field(ge=2000, le=2099)
    activities: tuple[RegimenSimplificadoActivity, ...] = Field(max_length=12)

    @model_validator(mode="after")
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
) -> None:
    """Fail closed on applicability, annual taxonomy, order, and censo conflicts."""
    if not applicable:
        if rows.activities:
            raise IvaValidationError("non-applicable regimen simplificado cannot carry activity rows")
        return
    if not rows.activities:
        raise IvaValidationError("applicable regimen simplificado requires activity rows")
    by_id = {item.orden_id: item for item in orden}
    if len(by_id) != len(orden) or any(item.ejercicio != rows.ejercicio for item in orden):
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
