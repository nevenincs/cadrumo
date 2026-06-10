"""Clean-state proof for filing-grade cross-period modelo dependencies.

Used by: :mod:`~aeat.application.calculations._calculate` to verify cross-period requirements before filing.

Use of :class:`~aeat.domain.calculations.registry.RegistrySnapshot` and
:class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority` for
compliance. Reads filed :class:`ModeloRecord` rows from the record catalogue
to prove a dependent period's upstream filings carry official evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Final, NamedTuple, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ...core.resources import resources as _resources
from ...domain.calculations.registry import (
    RegistryModeloObservation,
    RegistryModeloObservationRequirement,
    RegistryRelationSourceRequirement,
    RegistrySnapshot,
    ValidatedRegistryAuthority,
    previous_filing_observation_requirements,
    relation_source_requirements,
)
from ...domain.justificante import JustificanteRepository
from ...domain.modelos import (
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepositoryProtocol,
    ModeloRecordStatus,
    VerificationCompletenessStatus,
    VerificationReportCatalogue,
    VerificationReportCatalogueRepositoryProtocol,
)
from ._observations_repository import CalculationObservationRepository

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")
_OFFICIAL_SOURCE_KINDS: Final = frozenset(
    {
        "aeat_sede_justificante",
        "aeat_sede_live_capture",
        "aeat_csv_register",
    }
)
_JUSTIFICANTE_VERIFIED_EXTERNAL_EVIDENCE_KINDS: Final = frozenset(
    {
        "aeat_justificante_pdf",
        # A live-captured justificante is the authentic AEAT-signed receipt
        # pulled read-only from the sede (the same PDF an operator would
        # download and import as aeat_justificante_pdf), so it satisfies the
        # justificante-verification gate. See the live-justificante-reconcile ADR.
        "aeat_live_capture",
    }
)


class _ObservationPayload(Protocol):
    """Structural interface for the observation envelope payload consumed here.

    Matches the public attribute surface of
    :class:`~aeat.application.calculations._observations_repository._ObservationPayload`
    without importing its private name.
    """

    observation: RegistryModeloObservation
    source_kind: str
    member_nif: str | None
    stamped_revision_id: str | None


class CrossPeriodDependencyOrigin(StrEnum):
    """Registry source family that created a cross-period dependency."""

    PREVIOUS_FILING_BINDING = "previous_filing_binding"
    REGISTRY_RELATION = "registry_relation"


class CrossPeriodCleanStateBlocker(StrEnum):
    """Blocking reason codes for a cross-period clean-state verdict."""

    MISSING_OBSERVATION = "missing_observation"
    MISSING_OBSERVED_CASILLA = "missing_observed_casilla"
    MISSING_CURRENT_FILING_RECORD = "missing_current_filing_record"
    DUPLICATE_CURRENT_FILING_RECORD = "duplicate_current_filing_record"
    SUPERSEDED_DEPENDENCY = "superseded_dependency"
    MISSING_CALCULATION_REVISION = "missing_calculation_revision"
    UNFILED_CALCULATION_REVISION = "unfiled_calculation_revision"
    MISSING_COMPLETE_VERIFICATION_REPORT = "missing_complete_verification_report"
    LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE = "local_filing_missing_external_evidence"
    MISSING_AEAT_ACCEPTANCE = "missing_aeat_acceptance"
    MISSING_EXTERNAL_EVIDENCE = "missing_external_evidence"
    MISSING_EXTERNAL_EVIDENCE_RECORD = "missing_external_evidence_record"
    MISSING_JUSTIFICANTE_VERIFICATION = "missing_justificante_verification"
    OBSERVATION_REVISION_VALUE_DIVERGENCE = "observation_revision_value_divergence"
    OPERATOR_MANUAL_SOURCE = "operator_manual_source"
    INCOMPLETE_GROUP_MEMBER_COVERAGE = "incomplete_group_member_coverage"
    MISSING_EXPECTED_GROUP_MEMBER_ROSTER = "missing_expected_group_member_roster"
    UNEXPECTED_GROUP_MEMBER_SOURCE = "unexpected_group_member_source"
    REGISTRY_REVISION_DIVERGENCE = "registry_revision_divergence"
    """Stamped revision id does not match the law-determined revision for the source (modelo, filing_year, period).

    ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2: a prior
    observation captured under a revision that is no longer the law-determined
    revision for its source context must not silently propagate its norms. The
    carry is refused until the operator re-files and re-stamps under the correct
    revision.
    """


class CrossPeriodDependencyRequirement(BaseModel):
    """One upstream filed declaration required by a target registry snapshot."""

    model_config = _STRICT_FROZEN

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    source_casillas: tuple[str, ...] = Field(min_length=1)
    origin: CrossPeriodDependencyOrigin
    origin_ids: tuple[str, ...] = Field(min_length=1)
    requires_member_fan_in: bool = False

    @property
    def key(self) -> tuple[str, int, str, CrossPeriodDependencyOrigin, tuple[str, ...]]:
        return (self.source_modelo, self.filing_year, self.period, self.origin, self.origin_ids)


class CrossPeriodExpectedMemberSet(BaseModel):
    """Expected grupo-de-entidades members for one member fan-in dependency."""

    model_config = _STRICT_FROZEN

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    member_nifs: tuple[str, ...] = Field(min_length=1)

    @property
    def requirement_key(self) -> tuple[str, int, str]:
        """Return the dependency key this expected member roster proves."""
        return (self.source_modelo, self.filing_year, self.period)


class CrossPeriodDependencyInventoryItem(BaseModel):
    """Registry-derived cross-period dependency coverage for one target snapshot."""

    model_config = _STRICT_FROZEN

    target_modelo: str = Field(min_length=1, max_length=8)
    target_revision_id: str = Field(min_length=1)
    target_filing_year: int = Field(ge=2000, le=2099)
    target_period: str = Field(min_length=1, max_length=8)
    dependencies: tuple[CrossPeriodDependencyRequirement, ...] = Field(min_length=1)

    @property
    def source_modelos(self) -> tuple[str, ...]:
        """Return the upstream modelos required by this target snapshot."""
        return tuple(sorted({requirement.source_modelo for requirement in self.dependencies}))


class CrossPeriodDependencyInventory(BaseModel):
    """Registry-derived inventory of all cross-period target snapshots for a filing year."""

    model_config = _STRICT_FROZEN

    filing_year: int = Field(ge=2000, le=2099)
    items: tuple[CrossPeriodDependencyInventoryItem, ...] = ()

    @property
    def target_modelos(self) -> tuple[str, ...]:
        """Return target modelos that declare filing-history dependencies."""
        return tuple(sorted({item.target_modelo for item in self.items}))

    @property
    def source_modelos(self) -> tuple[str, ...]:
        """Return upstream modelos required by the inventory."""
        return tuple(sorted({source_modelo for item in self.items for source_modelo in item.source_modelos}))


class CrossPeriodDependencyEvidence(BaseModel):
    """Observed filing-state evidence for one dependency requirement."""

    model_config = _STRICT_FROZEN

    requirement: CrossPeriodDependencyRequirement
    observation_source_kind: str | None = None
    filing_record_id: str | None = None
    calculation_revision_id: str | None = None
    member_filing_record_ids: tuple[str, ...] = ()
    member_calculation_revision_ids: tuple[str, ...] = ()
    calculation_revision_state: CalculationRevisionState | None = None
    verification_status: VerificationCompletenessStatus | None = None
    aeat_accepted: bool | None = None
    external_evidence_kind: str | None = None
    observed_member_nifs: tuple[str, ...] = ()
    expected_member_nifs: tuple[str, ...] = ()
    missing_member_nifs: tuple[str, ...] = ()
    unexpected_member_nifs: tuple[str, ...] = ()
    blockers: tuple[CrossPeriodCleanStateBlocker, ...] = ()
    unstamped_revision_advisory: bool = False
    """Non-blocking advisory: the source observation has no revision stamp (legacy record).

    The carry proceeds but this flag is ``True`` when the persisted observation
    predates the revision-provenance field (ADR 2026-06-10-period-revision-resolution-adr,
    Ruling 3 / R2). Operators should re-file the source period to obtain a stamped
    record. A divergent stamp produces ``REGISTRY_REVISION_DIVERGENCE`` in
    :attr:`blockers` instead.
    """

    @property
    def clean(self) -> bool:
        return not self.blockers


class CrossPeriodCleanStateVerdict(BaseModel):
    """Clean-state result for every cross-period dependency in a target snapshot."""

    model_config = _STRICT_FROZEN

    bucket_id: str = Field(min_length=1)
    target_modelo: str = Field(min_length=1, max_length=8)
    target_filing_year: int = Field(ge=2000, le=2099)
    target_period: str = Field(min_length=1, max_length=8)
    dependencies: tuple[CrossPeriodDependencyEvidence, ...] = ()

    @property
    def requires_clean_state(self) -> bool:
        return bool(self.dependencies)

    @property
    def clean(self) -> bool:
        return all(item.clean for item in self.dependencies)

    @property
    def blockers(self) -> tuple[CrossPeriodCleanStateBlocker, ...]:
        return tuple(dict.fromkeys(blocker for item in self.dependencies for blocker in item.blockers))

    @property
    def has_unstamped_revision_advisory(self) -> bool:
        """True when any dependency carries a legacy unstamped-revision advisory."""
        return any(item.unstamped_revision_advisory for item in self.dependencies)


def cross_period_dependency_requirements(snapshot: RegistrySnapshot) -> tuple[CrossPeriodDependencyRequirement, ...]:
    """Return the :class:`CrossPeriodDependencyRequirement` records for ``snapshot``.

    Derives filed-history requirements from :class:`RegistrySnapshot`.
    """
    requirements: dict[
        tuple[str, int, str, CrossPeriodDependencyOrigin, tuple[str, ...]],
        CrossPeriodDependencyRequirement,
    ] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for item in _requirements_from_previous_filing(requirement, snapshot=snapshot):
            requirements.setdefault(item.key, item)
    for requirement in relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for item in _requirements_from_relation(requirement):
            requirements.setdefault(item.key, item)
    return tuple(requirements.values())


def cross_period_dependency_inventory(
    authority: ValidatedRegistryAuthority,
    *,
    filing_year: int,
    modelos: Iterable[str] | None = None,
) -> CrossPeriodDependencyInventory:
    """Return a :class:`CrossPeriodDependencyInventory` of snapshots with cross-period dependencies.

    The inventory is a backend coverage surface. It lets callers prove which
    modelos and periods are in scope for the clean-state guard before they wire
    model-specific workflow tests or operator diagnostics.

    Uses :class:`ValidatedRegistryAuthority` for snapshot resolution.
    """
    selected_modelos = authority.modelos if modelos is None else tuple(authority.modelo(modelo) for modelo in modelos)
    items: list[CrossPeriodDependencyInventoryItem] = []
    for modelo in selected_modelos:
        for revision in modelo.revisions.values():
            if not revision.period_selector.includes_year(filing_year):
                continue
            for period in revision.period_selector.periods:
                snapshot = authority.snapshot(
                    str(modelo.id),
                    filing_year=filing_year,
                    period=period,
                    revision_id=str(revision.id),
                )
                dependencies = cross_period_dependency_requirements(snapshot)
                if not dependencies:
                    continue
                items.append(
                    CrossPeriodDependencyInventoryItem(
                        target_modelo=str(snapshot.modelo.id),
                        target_revision_id=str(snapshot.revision.id),
                        target_filing_year=snapshot.filing_year,
                        target_period=snapshot.period,
                        dependencies=dependencies,
                    )
                )
    return CrossPeriodDependencyInventory(
        filing_year=filing_year,
        items=tuple(
            sorted(
                items,
                key=lambda item: (
                    item.target_modelo,
                    item.target_revision_id,
                    item.target_period,
                ),
            )
        ),
    )


def evaluate_cross_period_clean_state(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepository | None = None,
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
) -> CrossPeriodCleanStateVerdict:
    """Evaluate cross-period dependencies and return a :class:`CrossPeriodCleanStateVerdict`.

    Uses :class:`RegistrySnapshot` to derive the dependency requirements.
    """
    filing_catalogue = filing_repository.load()
    calculation_catalogue = calculation_repository.load()
    verification_catalogue = verification_repository.load()
    resolved_justificante_repository = justificante_repository or JustificanteRepository()
    expected_member_sets_by_key = _expected_member_sets_by_key(expected_member_sets)
    dependencies = tuple(
        _evaluate_requirement(
            requirement,
            bucket_id=bucket_id,
            observation_repository=observation_repository,
            filing_catalogue=filing_catalogue,
            calculation_catalogue=calculation_catalogue,
            verification_catalogue=verification_catalogue,
            justificante_repository=resolved_justificante_repository,
            expected_member_set=expected_member_sets_by_key.get(
                (requirement.source_modelo, requirement.filing_year, requirement.period)
            ),
        )
        for requirement in cross_period_dependency_requirements(snapshot)
    )
    return CrossPeriodCleanStateVerdict(
        bucket_id=bucket_id,
        target_modelo=str(snapshot.modelo.id),
        target_filing_year=snapshot.filing_year,
        target_period=snapshot.period,
        dependencies=dependencies,
    )


def _requirements_from_previous_filing(
    requirement: RegistryModeloObservationRequirement,
    *,
    snapshot: RegistrySnapshot,
) -> Iterable[CrossPeriodDependencyRequirement]:
    grouped_keys = _per_grupo_member_requirement_keys(snapshot)
    yield CrossPeriodDependencyRequirement(
        source_modelo=requirement.modelo,
        filing_year=requirement.filing_year,
        period=requirement.period,
        source_casillas=requirement.source_casillas,
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=requirement.binding_ids,
        requires_member_fan_in=(requirement.modelo, requirement.filing_year, requirement.period) in grouped_keys,
    )


def _requirements_from_relation(
    requirement: RegistryRelationSourceRequirement,
) -> Iterable[CrossPeriodDependencyRequirement]:
    for period in requirement.periods:
        yield CrossPeriodDependencyRequirement(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=period,
            source_casillas=(requirement.source_output,),
            origin=CrossPeriodDependencyOrigin.REGISTRY_RELATION,
            origin_ids=requirement.relation_ids,
        )


def _per_grupo_member_requirement_keys(snapshot: RegistrySnapshot) -> set[tuple[str, int, str]]:
    grouped_binding_ids = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source == "previous_filing" and _selector_grouping(binding.selector) == "per_grupo_member"
    }
    if not grouped_binding_ids:
        return set()
    keys: set[tuple[str, int, str]] = set()
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        if any(binding_id in grouped_binding_ids for binding_id in requirement.binding_ids):
            keys.add((requirement.modelo, requirement.filing_year, requirement.period))
    return keys


def _selector_grouping(selector: object) -> object:
    if isinstance(selector, Mapping):
        return next((v for k, v in selector.items() if k == "grouping"), None)
    return getattr(selector, "grouping", None)


class _CrossPeriodSource(NamedTuple):
    value_member_payloads: tuple[_ObservationPayload, ...]
    observed_member_nifs: tuple[str, ...]
    expected_member_nifs: tuple[str, ...]
    missing_member_nifs: tuple[str, ...]
    unexpected_member_nifs: tuple[str, ...]
    payload: _ObservationPayload | None
    blockers: tuple[CrossPeriodCleanStateBlocker, ...]
    unstamped_revision_advisory: bool = False


class _MemberHistory(NamedTuple):
    member_filing_record_ids: tuple[str, ...]
    member_calculation_revision_ids: tuple[str, ...]
    calculation_revision_state: CalculationRevisionState | None
    verification_status: VerificationCompletenessStatus | None
    aeat_accepted: bool | None
    external_evidence_kind: str | None
    blockers: list[CrossPeriodCleanStateBlocker]


def _revision_carry_check(
    stamped_revision_id: str | None,
    source_modelo: str,
    source_filing_year: int,
    source_period: str,
) -> tuple[list[CrossPeriodCleanStateBlocker], bool]:
    """Return (blockers, unstamped_advisory) for a carry-read revision check.

    ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2:

    - Divergent stamp → [REGISTRY_REVISION_DIVERGENCE] blocker, False advisory.
    - Missing stamp (legacy record) → [] blockers, True advisory (carry proceeds loudly).
    - Matching stamp → [] blockers, False advisory.
    - Indeterminate (source context fails to resolve) → [] blockers, True advisory.
      The carry proceeds but the operator MUST be told the stamp could not be
      re-confirmed against the law-determined revision; a silent clean carry on
      an unverifiable stamp would defeat the gate.
    """
    if stamped_revision_id is None:
        # Legacy record: no stamp — carry proceeds, but surface a non-blocking advisory.
        return [], True
    try:
        snapshot = _resources().modelos.authority.snapshot(
            source_modelo,
            filing_year=source_filing_year,
            period=source_period,
        )
        law_determined_id = snapshot.revision.id
    except Exception:
        # Indeterminate: the source context will not resolve, so the stamp cannot be
        # re-confirmed. Surface the non-blocking advisory rather than carrying silently.
        return [], True
    if stamped_revision_id != law_determined_id:
        return [CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE], False
    return [], False


def _resolve_cross_period_source(
    requirement: CrossPeriodDependencyRequirement,
    observation_repository: CalculationObservationRepository,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
) -> _CrossPeriodSource:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    unstamped_advisory = False
    value_member_payloads: tuple[_ObservationPayload, ...] = ()
    observed_member_nifs: tuple[str, ...] = ()
    expected_member_nifs: tuple[str, ...] = ()
    missing_member_nifs: tuple[str, ...] = ()
    unexpected_member_nifs: tuple[str, ...] = ()
    payload: _ObservationPayload | None = None
    if requirement.requires_member_fan_in:
        member_payloads = tuple(
            item
            for item in observation_repository.iter_modelo(requirement.source_modelo)
            if item.observation.filing_year == requirement.filing_year
            and item.observation.period == requirement.period
            and item.member_nif is not None
        )
        observed_member_nifs = tuple(sorted({str(item.member_nif) for item in member_payloads}))
        if expected_member_set is None:
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER)
            blockers.append(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE)
            value_member_payloads = member_payloads
        else:
            expected_member_nifs = tuple(sorted(set(expected_member_set.member_nifs)))
            expected_member_nif_set = set(expected_member_nifs)
            observed_member_nif_set = set(observed_member_nifs)
            missing_member_nifs = tuple(sorted(expected_member_nif_set - observed_member_nif_set))
            unexpected_member_nifs = tuple(sorted(observed_member_nif_set - expected_member_nif_set))
            if missing_member_nifs:
                blockers.append(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE)
            if unexpected_member_nifs:
                blockers.append(CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE)
            value_member_payloads = tuple(
                item for item in member_payloads if str(item.member_nif) in expected_member_nif_set
            )
        # R2 carry gate: check revision stamp on each member payload.
        for item in value_member_payloads:
            extra_blockers, item_advisory = _revision_carry_check(
                item.stamped_revision_id,
                requirement.source_modelo,
                requirement.filing_year,
                requirement.period,
            )
            blockers.extend(extra_blockers)
            unstamped_advisory = unstamped_advisory or item_advisory
    else:
        payload = observation_repository.load_observation(
            requirement.source_modelo,
            requirement.filing_year,
            requirement.period,
        )
        # R2 carry gate: re-confirm stamped revision == law-determined revision.
        if payload is not None:
            extra_blockers, unstamped_advisory = _revision_carry_check(
                payload.stamped_revision_id,
                requirement.source_modelo,
                requirement.filing_year,
                requirement.period,
            )
            blockers.extend(extra_blockers)
    return _CrossPeriodSource(
        value_member_payloads,
        observed_member_nifs,
        expected_member_nifs,
        missing_member_nifs,
        unexpected_member_nifs,
        payload,
        tuple(blockers),
        unstamped_advisory,
    )


def _resolve_observation_values(
    requirement: CrossPeriodDependencyRequirement,
    value_member_payloads: tuple[_ObservationPayload, ...],
    payload: _ObservationPayload | None,
) -> tuple[str | None, dict[str, object], list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    observation_source_kind: str | None = None
    observation_values: dict[str, object] = {}
    if requirement.requires_member_fan_in and value_member_payloads:
        observation_source_kind = _combined_source_kind(item.source_kind for item in value_member_payloads)
        if any(item.source_kind == "operator_manual" for item in value_member_payloads):
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        for item in value_member_payloads:
            for casilla_id in requirement.source_casillas:
                if casilla_id not in item.observation.casilla_values:
                    blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    elif payload is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION)
    else:
        observation_source_kind = payload.source_kind
        observation_values = dict(payload.observation.casilla_values)
        if payload.source_kind == "operator_manual":
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        for casilla_id in requirement.source_casillas:
            if casilla_id not in observation_values:
                blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    return observation_source_kind, observation_values, blockers


def _aggregate_member_history(
    requirement: CrossPeriodDependencyRequirement,
    *,
    bucket_id: str,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepository,
    observation_source_kind: str | None,
    value_member_payloads: tuple[_ObservationPayload, ...],
    expected_member_nifs: tuple[str, ...],
    observed_member_nifs: tuple[str, ...],
) -> _MemberHistory:
    member_payload_by_nif = {str(item.member_nif): item for item in value_member_payloads}
    members_to_check = expected_member_nifs or observed_member_nifs
    blockers: list[CrossPeriodCleanStateBlocker] = []
    member_filing_record_ids: list[str] = []
    member_calculation_revision_ids: list[str] = []
    revision_state: CalculationRevisionState | None = None
    verification_status: VerificationCompletenessStatus | None = None
    aeat_accepted: bool | None = None
    external_evidence_kind: str | None = None
    for member_nif in members_to_check:
        member_payload = member_payload_by_nif.get(member_nif)
        member_values = dict(member_payload.observation.casilla_values) if member_payload is not None else {}
        member_result = _evaluate_filing_history(
            requirement,
            bucket_id=bucket_id,
            filing_catalogue=filing_catalogue,
            calculation_catalogue=calculation_catalogue,
            verification_catalogue=verification_catalogue,
            justificante_repository=justificante_repository,
            observation_source_kind=observation_source_kind,
            observation_values=member_values,
            member_nif=member_nif,
        )
        blockers.extend(member_result.blockers)
        if member_result.filing_record_id is not None:
            member_filing_record_ids.append(member_result.filing_record_id)
        if member_result.calculation_revision_id is not None:
            member_calculation_revision_ids.append(member_result.calculation_revision_id)
        revision_state = member_result.calculation_revision_state or revision_state
        verification_status = member_result.verification_status or verification_status
        aeat_accepted = member_result.aeat_accepted if member_result.aeat_accepted is not None else aeat_accepted
        external_evidence_kind = member_result.external_evidence_kind or external_evidence_kind
    return _MemberHistory(
        tuple(member_filing_record_ids),
        tuple(member_calculation_revision_ids),
        revision_state,
        verification_status,
        aeat_accepted,
        external_evidence_kind,
        blockers,
    )


def _evaluate_requirement(
    requirement: CrossPeriodDependencyRequirement,
    *,
    bucket_id: str,
    observation_repository: CalculationObservationRepository,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepository,
    expected_member_set: CrossPeriodExpectedMemberSet | None,
) -> CrossPeriodDependencyEvidence:
    source = _resolve_cross_period_source(requirement, observation_repository, expected_member_set)
    observation_source_kind, observation_values, value_blockers = _resolve_observation_values(
        requirement, source.value_member_payloads, source.payload
    )
    blockers: list[CrossPeriodCleanStateBlocker] = [*source.blockers, *value_blockers]

    if requirement.requires_member_fan_in:
        history = _aggregate_member_history(
            requirement,
            bucket_id=bucket_id,
            filing_catalogue=filing_catalogue,
            calculation_catalogue=calculation_catalogue,
            verification_catalogue=verification_catalogue,
            justificante_repository=justificante_repository,
            observation_source_kind=observation_source_kind,
            value_member_payloads=source.value_member_payloads,
            expected_member_nifs=source.expected_member_nifs,
            observed_member_nifs=source.observed_member_nifs,
        )
        blockers.extend(history.blockers)
        return CrossPeriodDependencyEvidence(
            requirement=requirement,
            observation_source_kind=observation_source_kind,
            observed_member_nifs=source.observed_member_nifs,
            expected_member_nifs=source.expected_member_nifs,
            missing_member_nifs=source.missing_member_nifs,
            unexpected_member_nifs=source.unexpected_member_nifs,
            member_filing_record_ids=history.member_filing_record_ids,
            member_calculation_revision_ids=history.member_calculation_revision_ids,
            calculation_revision_state=history.calculation_revision_state,
            verification_status=history.verification_status,
            aeat_accepted=history.aeat_accepted,
            external_evidence_kind=history.external_evidence_kind,
            blockers=_unique_blockers(blockers),
            unstamped_revision_advisory=source.unstamped_revision_advisory,
        )

    filing_result = _evaluate_filing_history(
        requirement,
        bucket_id=bucket_id,
        filing_catalogue=filing_catalogue,
        calculation_catalogue=calculation_catalogue,
        verification_catalogue=verification_catalogue,
        justificante_repository=justificante_repository,
        observation_source_kind=observation_source_kind,
        observation_values=observation_values,
        member_nif=None,
    )
    blockers.extend(filing_result.blockers)

    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        observation_source_kind=observation_source_kind,
        filing_record_id=filing_result.filing_record_id,
        calculation_revision_id=filing_result.calculation_revision_id,
        calculation_revision_state=filing_result.calculation_revision_state,
        verification_status=filing_result.verification_status,
        aeat_accepted=filing_result.aeat_accepted,
        external_evidence_kind=filing_result.external_evidence_kind,
        observed_member_nifs=source.observed_member_nifs,
        expected_member_nifs=source.expected_member_nifs,
        missing_member_nifs=source.missing_member_nifs,
        unexpected_member_nifs=source.unexpected_member_nifs,
        blockers=_unique_blockers(blockers),
        unstamped_revision_advisory=source.unstamped_revision_advisory,
    )


def _filing_external_evidence_blockers(
    filing: ModeloRecord,
    observation_source_kind: str | None,
    justificante_repository: JustificanteRepository,
) -> list[CrossPeriodCleanStateBlocker]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if filing.status is not ModeloRecordStatus.VIGENTE:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD)
    if not filing.aeat_accepted:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE)
    if filing.external_evidence is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE)
        if observation_source_kind not in _OFFICIAL_SOURCE_KINDS:
            blockers.append(CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE)
    elif filing.external_evidence.kind.value not in _JUSTIFICANTE_VERIFIED_EXTERNAL_EVIDENCE_KINDS:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION)
    elif justificante_repository.load(filing.external_evidence.reference_id) is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD)
    return blockers


def _filing_revision_blockers(
    filing: ModeloRecord,
    requirement: CrossPeriodDependencyRequirement,
    calculation_catalogue: CalculationRevisionCatalogue,
    observation_values: Mapping[str, object],
) -> tuple[CalculationRevisionState | None, list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    revision = calculation_catalogue.get(filing.calculation_revision_id)
    revision_state: CalculationRevisionState | None = None
    if revision is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CALCULATION_REVISION)
    else:
        revision_state = revision.state
        if revision.state is not CalculationRevisionState.PRESENTADO:
            blockers.append(CrossPeriodCleanStateBlocker.UNFILED_CALCULATION_REVISION)
        for casilla_id in requirement.source_casillas:
            observed = observation_values.get(casilla_id)
            if observed is None:
                continue
            if revision.casilla_values.get(casilla_id) != observed:
                blockers.append(CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE)
    return revision_state, blockers


def _filing_verification_blockers(
    filing: ModeloRecord,
    verification_catalogue: VerificationReportCatalogue,
) -> tuple[VerificationCompletenessStatus | None, list[CrossPeriodCleanStateBlocker]]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    verification_status: VerificationCompletenessStatus | None = None
    if filing.external_evidence is None:
        complete_reports = tuple(
            report
            for report in verification_catalogue.for_calculation_revision(filing.calculation_revision_id)
            if report.granted_verificado_completo
            and report.completeness_status is VerificationCompletenessStatus.COMPLETE
        )
        if complete_reports:
            verification_status = complete_reports[-1].completeness_status
        else:
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT)
    return verification_status, blockers


class _FilingHistory(NamedTuple):
    filing_record_id: str | None
    calculation_revision_id: str | None
    calculation_revision_state: CalculationRevisionState | None
    verification_status: VerificationCompletenessStatus | None
    aeat_accepted: bool | None
    external_evidence_kind: str | None
    blockers: list[CrossPeriodCleanStateBlocker]


def _evaluate_filing_history(
    requirement: CrossPeriodDependencyRequirement,
    *,
    bucket_id: str,
    filing_catalogue: ModeloRecordCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    verification_catalogue: VerificationReportCatalogue,
    justificante_repository: JustificanteRepository,
    observation_source_kind: str | None,
    observation_values: Mapping[str, object],
    member_nif: str | None,
) -> _FilingHistory:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    filing_history = filing_catalogue.history_for(
        bucket_id=bucket_id,
        modelo=requirement.source_modelo,
        filing_year=requirement.filing_year,
        period=requirement.period,
        member_nif=member_nif,
    )
    current_filings = tuple(record for record in filing_history if record.status is ModeloRecordStatus.VIGENTE)
    superseded_filings = tuple(record for record in filing_history if record.status is ModeloRecordStatus.SUPERSEDIDO)
    if len(current_filings) > 1:
        blockers.append(CrossPeriodCleanStateBlocker.DUPLICATE_CURRENT_FILING_RECORD)
    filing = current_filings[-1] if current_filings else None
    if filing is None:
        if superseded_filings:
            blockers.append(CrossPeriodCleanStateBlocker.SUPERSEDED_DEPENDENCY)
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD)
        return _FilingHistory(None, None, None, None, None, None, blockers)

    blockers.extend(_filing_external_evidence_blockers(filing, observation_source_kind, justificante_repository))
    revision_state, revision_blockers = _filing_revision_blockers(
        filing, requirement, calculation_catalogue, observation_values
    )
    blockers.extend(revision_blockers)
    verification_status, verification_blockers = _filing_verification_blockers(filing, verification_catalogue)
    blockers.extend(verification_blockers)

    return _FilingHistory(
        filing.filing_record_id,
        filing.calculation_revision_id,
        revision_state,
        verification_status,
        filing.aeat_accepted,
        filing.external_evidence.kind.value if filing.external_evidence is not None else None,
        blockers,
    )


def _expected_member_sets_by_key(
    expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
) -> Mapping[tuple[str, int, str], CrossPeriodExpectedMemberSet]:
    return {item.requirement_key: item for item in expected_member_sets}


def _unique_blockers(
    blockers: Iterable[CrossPeriodCleanStateBlocker],
) -> tuple[CrossPeriodCleanStateBlocker, ...]:
    return tuple(dict.fromkeys(blockers))


def _combined_source_kind(source_kinds: Iterable[str]) -> str:
    unique = tuple(dict.fromkeys(source_kinds))
    if len(unique) == 1:
        return unique[0]
    return "mixed"


__all__ = [
    "CrossPeriodCleanStateBlocker",
    "CrossPeriodCleanStateVerdict",
    "CrossPeriodDependencyEvidence",
    "CrossPeriodDependencyInventory",
    "CrossPeriodDependencyInventoryItem",
    "CrossPeriodDependencyOrigin",
    "CrossPeriodDependencyRequirement",
    "CrossPeriodExpectedMemberSet",
    "cross_period_dependency_inventory",
    "cross_period_dependency_requirements",
    "evaluate_cross_period_clean_state",
]
