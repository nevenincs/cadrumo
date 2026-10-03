"""Application service for the cross-period IVA prorrata register.

Thin orchestration over the application-owned
:class:`~application.prorrata_register.ports.ProrrataRegisterServiceRepositoryProtocol`:
the caller declares a per-ejercicio prorrata entry, lists the register, and reads
one entry by ``(ejercicio, sector)`` key. The register is authoritative
profile-scoped state; this service owns no calculation, only the declare/list/get
surface. The LIVA arts. 102-106 compute substrate lives in the pure domain module
:mod:`domain.iva`, and the precedence-ladder resolution lives in
:mod:`domain.prorrata_register`.

The seed from the stamped prior settlement observation (art. 105.Uno), the
provenance-tagged art. 105.Dos/Tres overrides, and the settlement write-back are
built on top of this facade in later waves; this module is only the persistence
surface they compose over.

See Also:
    :mod:`domain.prorrata_register`
        Pure register records and the precedence-ladder resolver.
    :mod:`adapters.persistence.profile.prorrata_register`
        FINANCIAL secure-object repository that stores the profile-scoped
        register singleton.
    :mod:`domain.iva`
        Legal IVA prorrata substrate that supplies the definitive percentage
        and the art. 105.Cuatro regularisation cuota.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from ...core.prorrata_register import (
    ProrrataProvisionalProvenance,
)
from ...core.prorrata_register import (
    ProrrataRegisterRegime as _ProrrataRegisterRegime,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.prorrata_register_catalogue import (
    aeat_autorizada_prorrata_provenance as _aeat_autorizada_provenance,
)
from ...domain.calculations.registry.prorrata_register_catalogue import carried_prior_definitiva_prorrata_provenance
from ...domain.calculations.registry.prorrata_register_catalogue import (
    general_prorrata_register_regime as _general_regime,
)
from ...domain.calculations.registry.prorrata_register_catalogue import (
    inicio_actividad_prorrata_provenance as _inicio_actividad_provenance,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.prorrata_register.register import (
    ProrrataProvisionalResolution,
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterValidationError,
    SectorDefinition,
    resolve_provisional_percentage,
)
from ..ledger.persistence_ports import LedgerPersistenceConflictError
from .ports import (
    ProrrataPriorSettlementSnapshotRepositoryProtocol,
    ProrrataPriorSettlementSourceSnapshot,
    ProrrataRegisterServiceRepositoryProtocol,
)
from .seed import (
    ProrrataPriorDefinitivaSeed,
    ProrrataPriorDefinitivaSeedEvaluation,
    ProrrataSeedFinding,
    cross_check_prorrata_entry_against_observations,
    evaluate_carried_prior_definitiva_seed_from_observations,
)

ProrrataWholeSeedUnavailableReason = Literal[
    "source_absent", "source_blocked", "existing_blocked", "regulated_override_standing"
]


class ProrrataWholeSeedUnavailableError(ProrrataRegisterValidationError):
    """A whole-entity carry lacks a safe, current canonical source or target."""

    reason: ProrrataWholeSeedUnavailableReason
    findings: tuple[ProrrataSeedFinding, ...]
    existing_provenance: ProrrataProvisionalProvenance | None

    def __init__(
        self,
        reason: ProrrataWholeSeedUnavailableReason,
        *,
        findings: tuple[ProrrataSeedFinding, ...] = (),
        existing_provenance: ProrrataProvisionalProvenance | None = None,
    ) -> None:
        """Record the finite refusal reason and canonical source findings."""
        self.reason = reason
        self.findings = findings
        self.existing_provenance = existing_provenance
        super().__init__(f"whole-entity prorrata carry refused: {reason}")


@dataclass(frozen=True, slots=True)
class ProrrataWholeSeedCommit:
    """The source and register facts that actually passed the atomic commit."""

    register: ProrrataRegister
    seed: ProrrataPriorDefinitivaSeed
    findings: tuple[ProrrataSeedFinding, ...]


def require_prorrata_register_coordinates_current(
    register: ProrrataRegister,
    *,
    operation: PinnedAuthorityOperation,
) -> ProrrataRegister:
    """Re-confirm every registry-derived coordinate before register values are read."""
    for entry in register.entries:
        require_prorrata_entry_coordinates_current(entry, operation=operation)
    return register


def require_prorrata_entry_coordinates_current(
    entry: ProrrataRegisterEntry,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Re-confirm one entry's registry coordinates before it joins the register.

    Checked on the entry alone: wrapping it in a one-entry register would run
    the register's cross-year lifecycle rules without the stored prior years.
    """
    # Lazy to keep the aggregation package's import spine acyclic: aggregation
    # consumes this prorrata service while calculations also consumes aggregation.
    from ..calculations.revision_carry_gate import revision_carry_outcome

    for snapshot_ref in entry.source_registry_snapshot_refs:
        outcome = revision_carry_outcome(snapshot_ref, operation=operation)
        if outcome.refused:
            raise ProrrataRegisterValidationError(
                "prorrata register source registry coordinate cannot be re-confirmed: "
                f"{snapshot_ref.revision_id}: {outcome.detail}"
            )


class ProrrataRegisterService:
    """Declare, list, and read cross-period prorrata entries on the active profile."""

    def __init__(
        self,
        *,
        repository: ProrrataRegisterServiceRepositoryProtocol,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """Bind the required bucket-scoped register capability."""
        self._repository = repository
        self._operation = operation

    def declare(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        """Atomically add or replace ``entry`` by its ``(ejercicio, sector)`` key.

        Args:
            entry: The per-ejercicio prorrata entry to persist.

        Returns:
            The updated :class:`ProrrataRegister`.
        """
        require_prorrata_entry_coordinates_current(entry, operation=self._operation)
        return self._repository.upsert_entry(entry)

    def declare_especial_transition(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        """Persist one current-period prorrata-especial option or revocation.

        The typed evidence is mandatory for this authoring path.  The register
        model enforces its regime, same-ejercicio mutual-exclusion, reference,
        and prior-especial lifecycle invariants during the repository's atomic
        singleton rebuild.
        """
        if entry.especial_transition is None:
            raise ProrrataRegisterValidationError("prorrata especial transition declaration requires typed evidence")
        require_prorrata_entry_coordinates_current(entry, operation=self._operation)
        return self._repository.upsert_entry(entry)

    def record_aeat_autorizada(
        self,
        *,
        ejercicio: int,
        provisional_percentage: Decimal,
        authorisation_reference: str,
        sector_id: str | None = None,
        regime: _ProrrataRegisterRegime | None = None,
    ) -> ProrrataRegister:
        """Record an art. 105.Dos AEAT-authorised provisional prorrata override.

        Args:
            ejercicio: Filing year whose provisional prorrata is authorised.
            provisional_percentage: AEAT-authorised provisional deduction percentage.
            authorisation_reference: Operator-held reference for the AEAT authorisation.
            sector_id: Optional sector identifier for sectores diferenciados.
            regime: Prorrata regime in force for the entry. Defaults to general.

        Returns:
            The updated :class:`ProrrataRegister`.
        """
        if regime is None:
            regime = _general_regime()
        entry = ProrrataRegisterEntry(
            ejercicio=ejercicio,
            regime=regime,
            especial_transition=None,
            sector_id=sector_id,
            provisional_percentage=provisional_percentage,
            provisional_provenance=_aeat_autorizada_provenance(),
            authorisation_reference=authorisation_reference,
            source_registry_snapshot_refs=(),
        )
        return self.declare(entry)

    def record_inicio_actividad(
        self,
        *,
        ejercicio: int,
        provisional_percentage: Decimal,
        proposal_reference: str,
        sector_id: str | None = None,
        regime: _ProrrataRegisterRegime | None = None,
    ) -> ProrrataRegister:
        """Record an art. 105.Tres start-of-activity provisional override.

        ``proposal_reference`` identifies the operator-held proposal or filing
        evidence supporting the declared percentage.  The registry supplies
        the typed provenance token so callers cannot manufacture a vocabulary
        value outside the pinned authority.
        """
        if regime is None:
            regime = _general_regime()
        entry = ProrrataRegisterEntry(
            ejercicio=ejercicio,
            regime=regime,
            especial_transition=None,
            sector_id=sector_id,
            provisional_percentage=provisional_percentage,
            provisional_provenance=_inicio_actividad_provenance(),
            authorisation_reference=proposal_reference,
            source_registry_snapshot_refs=(),
        )
        return self.declare(entry)

    def declare_sector(self, definition: SectorDefinition) -> ProrrataRegister:
        """Atomically add or replace a differentiated-sector definition by ``sector_id``.

        The operator's art. 9.1.c partition is a legal judgment the ledger cannot
        infer, so it is declared here; once at least one sector is declared the
        register is sectorized and the per-sector apportionment routing applies
        (LIVA arts. 9.1.c / 101). Existing per-ejercicio entries are preserved.

        Args:
            definition: The differentiated-sector partition entry to persist.

        Returns:
            The updated :class:`ProrrataRegister`.
        """
        return self._repository.upsert_sector_definition(definition)

    def seed_sector_carried(self, ejercicio: int, sector_id: str) -> tuple[ProrrataRegister, ProrrataRegisterEntry]:
        """Commit a sector carry derived from its latest prior definitive entry."""
        return self._repository.seed_sector_carried(
            ejercicio,
            sector_id,
            validate_entry=lambda entry: require_prorrata_entry_coordinates_current(entry, operation=self._operation),
        )

    def seed_whole_carried(
        self,
        ejercicio: int,
        *,
        observation_repository: ProrrataPriorSettlementSnapshotRepositoryProtocol,
    ) -> ProrrataWholeSeedCommit:
        """Carry the prior 303 definitive under source and register revision fences."""
        for attempt in range(4):
            current, register_revision = self._repository.load_revisioned()
            source, evaluation = _load_whole_seed_evaluation(
                ejercicio=ejercicio,
                observation_repository=observation_repository,
                operation=self._operation,
            )
            seed = _require_available_whole_seed(evaluation)
            findings = _whole_seed_findings_for_register(
                current,
                ejercicio=ejercicio,
                evaluation=evaluation,
                source=source,
                operation=self._operation,
            )
            require_prorrata_entry_coordinates_current(seed.entry, operation=self._operation)
            next_register = _register_with_whole_seed(current, ejercicio=ejercicio, seed=seed)
            if not _commit_whole_seed_candidate(
                self._repository,
                next_register,
                ejercicio=ejercicio,
                expected_revision_id=register_revision,
                source=source,
                attempt=attempt,
            ):
                continue
            return ProrrataWholeSeedCommit(register=next_register, seed=seed, findings=findings)
        raise AssertionError("prorrata seed retry loop exited without a result")

    def settle_sector(
        self,
        ejercicio: int,
        sector_id: str,
        *,
        con_derecho_volume: Decimal,
        sin_derecho_volume: Decimal,
        producing_snapshot_ref: RegistrySnapshotRef,
    ) -> tuple[ProrrataRegister, ProrrataRegisterEntry]:
        """Commit a definitive sector result against the latest provisional entry."""
        return self._repository.settle_sector(
            ejercicio,
            sector_id,
            con_derecho_volume=con_derecho_volume,
            sin_derecho_volume=sin_derecho_volume,
            producing_snapshot_ref=producing_snapshot_ref,
            validate_entry=lambda entry: require_prorrata_entry_coordinates_current(entry, operation=self._operation),
        )

    def list_all(self) -> ProrrataRegister:
        """Return the full active-profile register.

        Returns:
            A :class:`ProrrataRegister`; empty when nothing has been declared.
        """
        return require_prorrata_register_coordinates_current(
            self._repository.load(),
            operation=self._operation,
        )

    def get(self, ejercicio: int, *, sector_id: str | None = None) -> ProrrataRegisterEntry | None:
        """Return the entry for a ``(ejercicio, sector)`` key, or ``None`` when absent.

        Args:
            ejercicio: Filing year to look up.
            sector_id: Sector identifier, or ``None`` for the whole-entity entry.

        Returns:
            The matching :class:`ProrrataRegisterEntry`, or ``None``.
        """
        return self.list_all().entry_for(ejercicio, sector_id=sector_id)

    def resolve_provisional(
        self,
        ejercicio: int,
        *,
        sector_id: str | None = None,
        candidate_entries: Iterable[ProrrataRegisterEntry] = (),
    ) -> ProrrataProvisionalResolution:
        """Resolve the in-force provisional percentage through the single declared ladder.

        The persisted register carries at most one entry per ``(ejercicio,
        sector)``. Seed and override flows can supply same-key transient
        candidates so the application lookup still resolves through the domain
        ladder (`AEAT_AUTORIZADA` > `INICIO_ACTIVIDAD` >
        `CARRIED_PRIOR_DEFINITIVA`) rather than open-coding precedence here.

        Args:
            ejercicio: Filing year to resolve.
            sector_id: Sector identifier, or ``None`` for the whole-entity entry.
            candidate_entries: Additional same-key entries from seed/override
                resolution that have not necessarily been persisted yet.

        Returns:
            The domain :class:`ProrrataProvisionalResolution`.
        """
        register = self.list_all()
        persisted = tuple(
            entry for entry in register.entries if entry.ejercicio == ejercicio and entry.sector_id == sector_id
        )
        transient = tuple(
            entry for entry in candidate_entries if entry.ejercicio == ejercicio and entry.sector_id == sector_id
        )
        return resolve_provisional_percentage((*persisted, *transient))


def _load_whole_seed_evaluation(
    *,
    ejercicio: int,
    observation_repository: ProrrataPriorSettlementSnapshotRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[ProrrataPriorSettlementSourceSnapshot, ProrrataPriorDefinitivaSeedEvaluation]:
    source = observation_repository.load_prior_m303_settlement_snapshot(ejercicio - 1)
    evaluation = evaluate_carried_prior_definitiva_seed_from_observations(
        ejercicio=ejercicio,
        observations=source.observations,
        operation=operation,
    )
    return source, evaluation


def _require_available_whole_seed(
    evaluation: ProrrataPriorDefinitivaSeedEvaluation,
) -> ProrrataPriorDefinitivaSeed:
    if evaluation.blocked:
        raise ProrrataWholeSeedUnavailableError("source_blocked", findings=evaluation.findings)
    if evaluation.seed is None:
        raise ProrrataWholeSeedUnavailableError("source_absent", findings=evaluation.findings)
    return evaluation.seed


def _whole_seed_findings_for_register(
    current: ProrrataRegister,
    *,
    ejercicio: int,
    evaluation: ProrrataPriorDefinitivaSeedEvaluation,
    source: ProrrataPriorSettlementSourceSnapshot,
    operation: PinnedAuthorityOperation,
) -> tuple[ProrrataSeedFinding, ...]:
    existing = current.entry_for(ejercicio, sector_id=None)
    if existing is None:
        return evaluation.findings
    cross_findings = cross_check_prorrata_entry_against_observations(
        existing,
        observations=source.observations,
        operation=operation,
    )
    if any(finding.blocking for finding in cross_findings):
        raise ProrrataWholeSeedUnavailableError("existing_blocked", findings=cross_findings)
    if (
        existing.provisional_provenance is not None
        and existing.provisional_provenance != carried_prior_definitiva_prorrata_provenance()
    ):
        raise ProrrataWholeSeedUnavailableError(
            "regulated_override_standing",
            findings=cross_findings,
            existing_provenance=existing.provisional_provenance,
        )
    return (*evaluation.findings, *cross_findings)


def _register_with_whole_seed(
    current: ProrrataRegister,
    *,
    ejercicio: int,
    seed: ProrrataPriorDefinitivaSeed,
) -> ProrrataRegister:
    retained = tuple(entry for entry in current.entries if (entry.ejercicio, entry.sector_id) != (ejercicio, None))
    return ProrrataRegister(
        entries=(*retained, seed.entry),
        sector_definitions=current.sector_definitions,
        activity_rows=current.activity_rows,
    )


def _commit_whole_seed_candidate(
    repository: ProrrataRegisterServiceRepositoryProtocol,
    next_register: ProrrataRegister,
    *,
    ejercicio: int,
    expected_revision_id: str,
    source: ProrrataPriorSettlementSourceSnapshot,
    attempt: int,
) -> bool:
    try:
        repository.commit_whole_carried_seed(
            next_register,
            ejercicio=ejercicio,
            expected_revision_id=expected_revision_id,
            source_snapshot=source,
        )
    except LedgerPersistenceConflictError:
        if attempt == 3:
            raise
        return False
    return True


__all__ = [
    "ProrrataRegisterService",
    "ProrrataWholeSeedCommit",
    "ProrrataWholeSeedUnavailableError",
    "require_prorrata_entry_coordinates_current",
    "require_prorrata_register_coordinates_current",
]
