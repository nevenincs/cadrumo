"""Modelo 303/4T to Modelo 390 simplified-regime annual-summary bindings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import FilingPeriodCode
from .binding_selector_utils import selector_as_dict
from .binding_targets import bound_casilla_binding_ids
from .errors import RegistryValidationError
from .ids import BindingId, LegalRefId, ModeloId, SourceRefId
from .schema import DataBindingDefinition, ModeloRevision
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition

__all__ = [
    "M303RegimenSimplificadoAnnualSummaryRequirement",
    "M303RegimenSimplificadoAnnualSummarySelector",
    "m303_regimen_simplificado_annual_summary_requirement",
    "m303_regimen_simplificado_annual_summary_selector",
    "validate_m303_regimen_simplificado_annual_summary_revision",
]

_SOURCE_CASILLA_IDS: tuple[CasillaId, ...] = ("51", "53", "52", "54", "55", "56", "57", "58")


class M303RegimenSimplificadoAnnualSummarySelector(BaseModel):
    """Strict selector for one immutable Modelo 303 4T annual-summary endpoint."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: Literal["303"]
    source_period: Literal["4T"]
    source_casilla_ids: tuple[CasillaId, ...]
    summary_casilla_id: CasillaId

    @field_validator("source_casilla_ids")
    @classmethod
    def _source_casilla_ids_are_exact_annual_summary_inputs(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if value != _SOURCE_CASILLA_IDS:
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary selector must declare Modelo 303 "
                "casillas 51, 53, 52, 54, 55, 56, 57, 58 in official semantic order",
            )
        return value


class M303RegimenSimplificadoAnnualSummaryRequirement(BaseModel):
    """Revision-owned target map for the one persisted 303 4T handoff."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: ModeloId
    source_period: FilingPeriodCode
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    binding_ids_by_summary_casilla_id: Mapping[CasillaId, BindingId] = Field(min_length=1)
    dependency_treatment: str = ""
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

    @field_validator("binding_ids_by_summary_casilla_id")
    @classmethod
    def _freeze_endpoint_bindings(cls, value: Mapping[CasillaId, BindingId]) -> Mapping[CasillaId, BindingId]:
        return dict(sorted(value.items()))


def m303_regimen_simplificado_annual_summary_selector(
    binding: DataBindingDefinition,
) -> M303RegimenSimplificadoAnnualSummarySelector:
    """Parse one declared simplified-regime annual-summary selector."""
    try:
        return M303RegimenSimplificadoAnnualSummarySelector.model_validate(selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed m303_regimen_simplificado_annual_summary selector: {exc}",
        ) from exc


def m303_regimen_simplificado_annual_summary_requirement(
    revision: ModeloRevision,
) -> M303RegimenSimplificadoAnnualSummaryRequirement | None:
    """Project the revision's typed Modelo 303 4T annual-summary bindings once."""
    bindings = _annual_summary_bindings(revision)
    if not bindings:
        return None
    first_selector = m303_regimen_simplificado_annual_summary_selector(bindings[0])
    binding_ids_by_summary_casilla_id, legal_refs, source_refs = _collect_bindings(bindings, first_selector)
    return M303RegimenSimplificadoAnnualSummaryRequirement(
        source_modelo=first_selector.source_modelo,
        source_period=first_selector.source_period,
        source_casilla_ids=first_selector.source_casilla_ids,
        binding_ids_by_summary_casilla_id=binding_ids_by_summary_casilla_id,
        dependency_treatment=_dependency_treatment(revision, first_selector.source_modelo),
        legal_refs=tuple(sorted(legal_refs)),
        source_refs=tuple(sorted(source_refs)),
    )


def validate_m303_regimen_simplificado_annual_summary_revision(revision: ModeloRevision) -> list[str]:
    """Return build-time failures for the complete 303/4T -> 390/0A target map."""
    try:
        requirement = m303_regimen_simplificado_annual_summary_requirement(revision)
    except RegistryValidationError as exc:
        return [str(exc)]
    if requirement is None:
        return []

    from ...modelos.calculation_revision import M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS

    expected_casilla_ids = M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS
    expected_set = set(expected_casilla_ids)
    declared_set = set(requirement.binding_ids_by_summary_casilla_id)
    failures = _target_failures(expected_set, declared_set)
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    failures.extend(
        _endpoint_failures(
            expected_casilla_ids,
            requirement.binding_ids_by_summary_casilla_id,
            casillas_by_id,
        )
    )
    return failures


def _annual_summary_bindings(revision: ModeloRevision) -> tuple[DataBindingDefinition, ...]:
    return tuple(
        binding
        for binding in revision.bindings
        if binding.source is BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
    )


def _collect_bindings(
    bindings: tuple[DataBindingDefinition, ...],
    first_selector: M303RegimenSimplificadoAnnualSummarySelector,
) -> tuple[dict[CasillaId, BindingId], set[LegalRefId], set[SourceRefId]]:
    binding_ids_by_summary_casilla_id: dict[CasillaId, BindingId] = {}
    legal_refs: set[LegalRefId] = set()
    source_refs: set[SourceRefId] = set()
    for binding in bindings:
        selector = m303_regimen_simplificado_annual_summary_selector(binding)
        if (
            selector.source_modelo != first_selector.source_modelo
            or selector.source_period != first_selector.source_period
            or selector.source_casilla_ids != first_selector.source_casilla_ids
        ):
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary bindings must share one exact source selector",
            )
        existing = binding_ids_by_summary_casilla_id.get(selector.summary_casilla_id)
        if existing is not None:
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary declares multiple bindings for "
                f"summary casilla {selector.summary_casilla_id!r}: {existing!r}, {binding.id!r}",
            )
        binding_ids_by_summary_casilla_id[selector.summary_casilla_id] = binding.id
        legal_refs.update(binding.legal_refs)
        source_refs.update(binding.source_refs)
    return binding_ids_by_summary_casilla_id, legal_refs, source_refs


def _dependency_treatment(revision: ModeloRevision, source_modelo: ModeloId) -> str:
    classification = next(
        (candidate for candidate in revision.dependency_classifications if candidate.source_modelo == source_modelo),
        None,
    )
    return "" if classification is None else str(classification.treatment)


def _target_failures(expected_set: set[CasillaId], declared_set: set[CasillaId]) -> list[str]:
    if declared_set == expected_set:
        return []
    return [
        "m303_regimen_simplificado_annual_summary bindings must target exactly "
        f"the canonical Modelo 390 74-83 endpoints; missing={sorted(expected_set - declared_set)!r}, "
        f"unexpected={sorted(declared_set - expected_set)!r}",
    ]


def _endpoint_failures(
    expected_casilla_ids: tuple[CasillaId, ...],
    binding_ids_by_summary_casilla_id: Mapping[CasillaId, BindingId],
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    failures: list[str] = []
    for ordinal, casilla_id in enumerate(expected_casilla_ids, start=74):
        casilla = casillas_by_id.get(casilla_id)
        binding_id = binding_ids_by_summary_casilla_id.get(casilla_id)
        if casilla is None:
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} is not declared as Modelo 390 casilla {ordinal}",
            )
            continue
        if casilla.number != str(ordinal):
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} must retain official Modelo 390 casilla number {ordinal}",
            )
        if binding_id is not None and (
            casilla.input_kind is not InputKind.BOUND or bound_casilla_binding_ids(casilla) != (binding_id,)
        ):
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} must be bound only by {binding_id!r}",
            )
    return failures
