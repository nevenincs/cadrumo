"""Modelo 303/4T to Modelo 390 simplified-regime annual-summary bindings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import FilingPeriodCode
from .binding_selector_utils import selector_as_dict
from .binding_targets import bound_casilla_binding_ids
from .binding_temporal import BindingTemporalSelector, FiledCurrentPeriod
from .errors import RegistryValidationError
from .ids import BindingId, LegalRefId, ModeloId, SourceRefId
from .schema_input_kind import InputKind
from .schema_surfaces import CasillaDefinition

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "M303RegimenSimplificadoAnnualSummaryProvider",
    "M303RegimenSimplificadoAnnualSummaryRequirement",
    "m303_regimen_simplificado_annual_summary_requirement",
    "m303_regimen_simplificado_annual_summary_selector",
    "validate_m303_regimen_simplificado_annual_summary_revision",
]

_SOURCE_CASILLA_IDS: tuple[CasillaId, ...] = ("51", "53", "52", "54", "55", "56", "57", "58")
_ANNUAL_SUMMARY_SOURCE_PERIOD: FilingPeriodCode = "4T"
#: The ten official Modelo 390 boxes the simplified-regime annual summary fills.
#:
#: The set is closed by the official Modelo 390 record design, so it is stated
#: here as a set rather than derived by counting declarations: a revision that
#: authored nine bindings would otherwise check nine boxes and call the map
#: complete. Membership is what each endpoint is held to; position is not, which
#: is why the fragment merge order of the binding declarations cannot move a box
#: number from one endpoint to another.
_OFFICIAL_SUMMARY_CASILLA_NUMBERS: frozenset[str] = frozenset(str(number) for number in range(74, 84))


class M303RegimenSimplificadoAnnualSummaryProvider(BaseModel):
    """Strict selector for one immutable Modelo 303 4T annual-summary endpoint."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY] = (
        BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
    )

    source_modelo: Literal["303"]
    temporal: BindingTemporalSelector = FiledCurrentPeriod(source_period=_ANNUAL_SUMMARY_SOURCE_PERIOD)
    source_casilla_ids: tuple[CasillaId, ...]
    summary_casilla_id: CasillaId

    @model_validator(mode="after")
    def _temporal_is_the_filed_fourth_quarter(self) -> M303RegimenSimplificadoAnnualSummaryProvider:
        """Pin the source window to the already-filed 4T of the target's own year.

        The annual summary is legally the fourth-quarter declaration of the same
        filing year, so no other temporal member can produce it. The pin is a
        refusal rather than a default because a binding that silently read a
        different period would publish a complete-looking annual total built
        from the wrong quarter.
        """
        if (
            not isinstance(self.temporal, FiledCurrentPeriod)
            or self.temporal.source_period != _ANNUAL_SUMMARY_SOURCE_PERIOD
        ):
            raise RegistryValidationError(
                "m303_regimen_simplificado_annual_summary temporal must be the filed 4T period "
                "of the target's own filing year",
            )
        return self

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
        return dict(value)


def m303_regimen_simplificado_annual_summary_selector(
    binding: BindingDefinition,
) -> M303RegimenSimplificadoAnnualSummaryProvider:
    """Parse one declared simplified-regime annual-summary selector."""
    try:
        return M303RegimenSimplificadoAnnualSummaryProvider.model_validate(selector_as_dict(binding))
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
        source_period=_ANNUAL_SUMMARY_SOURCE_PERIOD,
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

    # The authoring revision is the authority at publish time. Runtime handoff
    # code deliberately never supplies a second endpoint catalogue.
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    return _endpoint_failures(requirement.binding_ids_by_summary_casilla_id, casillas_by_id)


def _annual_summary_bindings(revision: ModeloRevision) -> tuple[BindingDefinition, ...]:
    return tuple(
        binding
        for binding in revision.bindings
        if binding.source is BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
    )


def _collect_bindings(
    bindings: tuple[BindingDefinition, ...],
    first_selector: M303RegimenSimplificadoAnnualSummaryProvider,
) -> tuple[dict[CasillaId, BindingId], set[LegalRefId], set[SourceRefId]]:
    binding_ids_by_summary_casilla_id: dict[CasillaId, BindingId] = {}
    legal_refs: set[LegalRefId] = set()
    source_refs: set[SourceRefId] = set()
    for binding in bindings:
        selector = m303_regimen_simplificado_annual_summary_selector(binding)
        if (
            selector.source_modelo != first_selector.source_modelo
            or selector.temporal != first_selector.temporal
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


def _endpoint_failures(
    binding_ids_by_summary_casilla_id: Mapping[CasillaId, BindingId],
    casillas_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    """Hold every declared endpoint to its own official Modelo 390 box number.

    Each endpoint is checked against the closed official set, and the claimed
    numbers must cover that set exactly once. Nothing reads the declaration
    sequence, so permuting the binding fragments cannot reassign a box.
    """
    failures: list[str] = []
    claimants_by_number: dict[str, list[CasillaId]] = {}
    for casilla_id, binding_id in binding_ids_by_summary_casilla_id.items():
        casilla = casillas_by_id.get(casilla_id)
        if casilla is None:
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} is not declared as a Modelo 390 casilla",
            )
            continue
        if casilla.number not in _OFFICIAL_SUMMARY_CASILLA_NUMBERS:
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} declares Modelo 390 casilla number {casilla.number!r}, which is not one of the "
                f"official annual-summary boxes {sorted(_OFFICIAL_SUMMARY_CASILLA_NUMBERS, key=int)}",
            )
        else:
            claimants_by_number.setdefault(casilla.number, []).append(casilla_id)
        if casilla.input_kind is not InputKind.BOUND or bound_casilla_binding_ids(casilla) != (binding_id,):
            failures.append(
                "m303_regimen_simplificado_annual_summary endpoint "
                f"{casilla_id!r} must be bound only by {binding_id!r}",
            )
    failures.extend(_official_box_coverage_failures(claimants_by_number))
    return failures


def _official_box_coverage_failures(claimants_by_number: Mapping[str, list[CasillaId]]) -> list[str]:
    """Return the failures for an annual-summary map that misses or doubles a box."""
    failures = [
        "m303_regimen_simplificado_annual_summary declares multiple endpoints for official Modelo 390 "
        f"casilla number {number!r}: {sorted(claimants)}"
        for number, claimants in sorted(claimants_by_number.items(), key=lambda item: int(item[0]))
        if len(claimants) > 1
    ]
    missing = _OFFICIAL_SUMMARY_CASILLA_NUMBERS - claimants_by_number.keys()
    if missing:
        failures.append(
            "m303_regimen_simplificado_annual_summary declares no endpoint for official Modelo 390 "
            f"casilla numbers {sorted(missing, key=int)}",
        )
    return failures
