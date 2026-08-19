"""Lifecycle mutations for modelo work units.

This module creates, lists, renames, and discards
:class:`cadrumo.domain.modelos.WorkUnit` records in the
:class:`adapters.persistence.profile.modelos_work_units.WorkUnitCatalogueRepository`.
Each mutating action emits a typed event through
:class:`BucketEventHistoryRepository`, giving
:func:`cadrumo.application.modelo.assemble_work_unit_history` a complete
timeline from creation through discard.

The lifecycle layer mutates the work-unit catalogue only. It does not choose
visible filing targets (see :mod:`cadrumo.application.modelo._work_addressing`),
does not decide unsupported-modelo or applicability policy (see
:mod:`cadrumo.application.modelo._work_create_policy`), and does not persist
calculation revisions or filing records. Creation still performs the profile
readiness and registry revision/period gates before inserting the work unit, so
programmatic callers observe the same safety boundary as the CLI.

See Also:
    :mod:`cadrumo.application.modelo._work_addressing`:
        Resolves natural or exact operator targets before lifecycle mutation.
    :func:`cadrumo.application.modelo.assemble_work_unit_history`:
        Reads the emitted bucket events into a chronological work-unit timeline.
    :class:`CalculationRevision`:
        Defines calculation attempts and current/filed pointers under a work unit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, Field, field_validator, model_validator

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core import (
    STRICT_FROZEN_CONFIG,
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
    Period,
)
from ...core.identity import CalculationRevisionId
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepositoryProtocol, BucketEventObjectType, BucketEventType
from ...domain.calculations.registry import RevisionId
from ...domain.contribuyente import CCAA
from ...domain.modelos import (
    ModeloCode,
    WorkUnit,
    WorkUnitCatalogue,
    WorkUnitCatalogueRepositoryProtocol,
    WorkUnitState,
    derive_work_unit_id,
    upsert_work_unit,
)
from ..operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
)
from ._action_errors import (
    CalculationRevisionNotFoundError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ._preconditions import build_modelo_precondition_failure_for_scenario
from ._registry_resources import reject_unknown_period_for_revision, reject_unknown_revision
from ._revision_persistence import build_modelo_bucket_event as _build_bucket_event
from ._revision_persistence import modelo_bucket_event_write as _bucket_event_write

_CONTINUATION_ID_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"


class ActiveWorkUnitUse(StrEnum):
    """Application operations that require a mutable work-unit lifecycle state."""

    CALCULATE = "calculate"
    IMPORT = "import"


class RevisionParentOperation(StrEnum):
    """Revision operations that require an active parent work unit."""

    VERIFY = "verify"
    FILE = "file"


@dataclass(frozen=True)
class _ActiveWorkUnitRefusal:
    """Canonical command-specific projection for one rejected discarded state."""

    subject_leaf_key: str
    scenario_id: str
    evidence_id: str
    translated_message: str


_ACTIVE_WORK_UNIT_REFUSALS: Mapping[ActiveWorkUnitUse, _ActiveWorkUnitRefusal] = MappingProxyType(
    {
        ActiveWorkUnitUse.CALCULATE: _ActiveWorkUnitRefusal(
            subject_leaf_key="modelo.work.calculate",
            scenario_id="modelo.work.calculate.lifecycle.discarded",
            evidence_id="modelo.work.calculate.lifecycle.observation",
            translated_message="application.modelo.errors.work_unit_discarded_cannot_calculate",
        ),
        ActiveWorkUnitUse.IMPORT: _ActiveWorkUnitRefusal(
            subject_leaf_key="modelo.filing_record.import",
            scenario_id="modelo.filing_record.import.lifecycle.discarded",
            evidence_id="modelo.filing_record.import.lifecycle.observation",
            translated_message="application.modelo.errors.work_unit_discarded_cannot_import",
        ),
    }
)


_REVISION_PARENT_DISCARDED_REFUSALS: Mapping[RevisionParentOperation, _ActiveWorkUnitRefusal] = MappingProxyType(
    {
        RevisionParentOperation.VERIFY: _ActiveWorkUnitRefusal(
            subject_leaf_key="modelo.work.verify",
            scenario_id="modelo.work.verify.calculation_revision.work_unit_target_discarded",
            evidence_id="modelo.work.verify.calculation_revision.addressing",
            translated_message="application.modelo.errors.calculation_revision_parent_work_unit_discarded",
        ),
        RevisionParentOperation.FILE: _ActiveWorkUnitRefusal(
            subject_leaf_key="modelo.work.file",
            scenario_id="modelo.work.file.calculation_revision.work_unit_target_discarded",
            evidence_id="modelo.work.file.calculation_revision.addressing",
            translated_message="application.modelo.errors.calculation_revision_parent_work_unit_discarded",
        ),
    }
)


class ModeloWorkLifecycleContinuation(BaseModel):
    """Application-owned forward path for one observed work-unit lifecycle state.

    The lifecycle service owns whether an observed work-unit state admits a
    concrete following action. The CLI only localizes this record and resolves
    its declared action through the live operator surface; it cannot choose a
    different action or manufacture a target argument.
    """

    model_config = STRICT_FROZEN_CONFIG

    notice_code: str = Field(pattern=_CONTINUATION_ID_PATTERN, min_length=3, max_length=160)
    summary_locale_key: str = Field(pattern=_CONTINUATION_ID_PATTERN, min_length=3, max_length=160)
    evidence: ConditionEvidence
    action: ActionReference | None = None
    argument_bindings: tuple[ActionArgumentBinding, ...] = ()
    no_recovery_outcome: NoRecoveryOutcome | None = None

    @field_validator("argument_bindings")
    @classmethod
    def _canonicalize_argument_bindings(
        cls,
        value: tuple[ActionArgumentBinding, ...],
    ) -> tuple[ActionArgumentBinding, ...]:
        """Require a unique, fully materialized continuation target."""
        names = tuple(item.argument_name for item in value)
        if len(set(names)) != len(names):
            raise ValueError("lifecycle continuation action argument names must be unique")
        if any(item.status is not ActionArgumentStatus.RESOLVED for item in value):
            raise ValueError("lifecycle continuation actions require resolved argument bindings")
        return tuple(sorted(value, key=lambda item: item.argument_name))

    @model_validator(mode="after")
    def _validate_action_or_explicit_outcome(self) -> ModeloWorkLifecycleContinuation:
        """Keep each observed continuation either executable or explicitly closed."""
        if (self.action is None) == (self.no_recovery_outcome is None):
            raise ValueError("lifecycle continuation requires exactly one action or no_recovery_outcome")
        if self.action is None:
            if self.argument_bindings:
                raise ValueError("closed lifecycle continuations cannot carry action arguments")
            return self

        _validate_continuation_argument_bindings(self)
        return self


def _validate_continuation_argument_bindings(continuation: ModeloWorkLifecycleContinuation) -> None:
    for binding in continuation.argument_bindings:
        if binding.source is not ActionArgumentSource.VERDICT_CONTEXT:
            raise ValueError("lifecycle continuation arguments must derive from continuation evidence")
        assert binding.source_key is not None
        evidence_value = continuation.evidence.values.get(binding.source_key)
        if evidence_value is None and binding.source_key not in continuation.evidence.values:
            raise ValueError("lifecycle continuation arguments must reference an evidence fact")
        if type(binding.value) is not type(evidence_value) or binding.value != evidence_value:
            raise ValueError("lifecycle continuation argument value must match its evidence fact")


def _continuation_evidence(
    *,
    condition_id: str,
    evidence_id: str,
    values: Mapping[str, str | int | bool],
) -> ConditionEvidence:
    """Build the strictly factual state observation behind one continuation."""
    return ConditionEvidence(
        condition_id=condition_id,
        evidence_id=evidence_id,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        values=values,
    )


def lifecycle_continuation_for_work_list(
    work_units: Sequence[WorkUnit],
) -> ModeloWorkLifecycleContinuation:
    """Return the only honest continuation for a work-unit list observation."""
    work_unit_count = len(work_units)
    evidence = _continuation_evidence(
        condition_id="modelo.work.list.selection",
        evidence_id="modelo.work.list.observation",
        values={"work_unit_count": work_unit_count},
    )
    if work_unit_count == 0:
        return ModeloWorkLifecycleContinuation(
            notice_code="modelo.work.list.selection_required",
            summary_locale_key="cli.app.modelo.work.list_no_active_work_summary",
            evidence=evidence,
            no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    if work_unit_count != 1:
        return ModeloWorkLifecycleContinuation(
            notice_code="modelo.work.list.selection_required",
            summary_locale_key="cli.app.modelo.work.list_selection_required_summary",
            evidence=evidence,
            no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )

    work_unit = work_units[0]
    evidence = _continuation_evidence(
        condition_id="modelo.work.list.selection",
        evidence_id="modelo.work.list.observation",
        values={"work_unit_count": work_unit_count, "work_unit_id": work_unit.work_unit_id},
    )
    return ModeloWorkLifecycleContinuation(
        notice_code="modelo.work.list.next_action",
        summary_locale_key="cli.app.modelo.work.list_single_status_summary",
        evidence=evidence,
        action=ActionReference(action_id="operator.modelo.work.status"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="work_unit_id",
                status=ActionArgumentStatus.RESOLVED,
                value=work_unit.work_unit_id,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="work_unit_id",
            ),
        ),
    )


def lifecycle_continuation_for_work_history(
    work_unit: WorkUnit,
) -> ModeloWorkLifecycleContinuation:
    """Return the canonical state-inspection continuation for one history observation."""
    evidence = _continuation_evidence(
        condition_id="modelo.work.history.inspection",
        evidence_id="modelo.work.history.observation",
        values={"work_unit_id": work_unit.work_unit_id},
    )
    return ModeloWorkLifecycleContinuation(
        notice_code="modelo.work.history.next_action",
        summary_locale_key="cli.app.modelo.work.history_next_action_summary",
        evidence=evidence,
        action=ActionReference(action_id="operator.modelo.work.status"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="work_unit_id",
                status=ActionArgumentStatus.RESOLVED,
                value=work_unit.work_unit_id,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="work_unit_id",
            ),
        ),
    )


def lifecycle_continuation_for_work_status(
    work_unit: WorkUnit,
) -> ModeloWorkLifecycleContinuation:
    """Return calculation only when the real calculation guard admits this unit."""
    evidence = _continuation_evidence(
        condition_id="modelo.work.status.calculation",
        evidence_id="modelo.work.status.observation",
        values={"work_unit_id": work_unit.work_unit_id, "work_unit_state": work_unit.state.value},
    )
    if work_unit.state is WorkUnitState.DESCARTADO:
        return ModeloWorkLifecycleContinuation(
            notice_code="modelo.work.status.action_unavailable",
            summary_locale_key="cli.app.modelo.work.status_discarded_summary",
            evidence=evidence,
            no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
        )
    if work_unit.state is not WorkUnitState.BORRADOR:
        raise ValueError(f"unhandled work-unit lifecycle state: {work_unit.state.value}")
    return ModeloWorkLifecycleContinuation(
        notice_code="modelo.work.status.next_action",
        summary_locale_key="cli.app.modelo.work.status_calculate_summary",
        evidence=evidence,
        action=ActionReference(action_id="operator.modelo.work.calculate"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="work_unit_id",
                status=ActionArgumentStatus.RESOLVED,
                value=work_unit.work_unit_id,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="work_unit_id",
            ),
        ),
    )


def _default_name(*, modelo: str, filing_year: int, period: Period) -> str:
    """Return the default display name for a fresh work unit."""
    return f"{modelo}-{filing_year}-{period.registry_token}"


def create_work_unit(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    revision_id: RevisionId,
    name: str | None = None,
    actor: str = "system",
    causante_ccaa: CCAA | None = None,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
    enforce_applicability: bool = True,
) -> WorkUnit:
    """Create or load the :class:`WorkUnit` for an exact filing target key.

    The key is ``bucket_id`` + ``modelo`` + ``filing_year`` + ``period`` +
    ``revision_id``. The revision id must be known to the bundled registry, the
    period must be declared for that revision, and the revision id must be the
    law-determined revision that
    :func:`~cadrumo.application.modelo._work_addressing.resolve_registry_revision_for_work_target`
    would select for ``(modelo, filing_year, period)`` alone -- this door
    re-confirms that pairing itself rather than trusting a caller to have
    resolved it, since a caller holding a stale or hand-picked revision id for
    the right modelo and a declared period would otherwise build a work unit
    under the wrong year's norms with no signal. The active profile must also
    be ready for the requested modelo work before any record is inserted.

    If the derived work-unit id already exists and is still active, the existing
    record is returned without emitting another creation event. Otherwise a
    BORRADOR work unit is inserted and a ``MODELO_WORK_UNIT_CREATED`` bucket
    event is appended.

    A DESCARTADO unit is REFUSED rather than returned. Because the id is
    content-addressed over exactly the coordinates this function is given, a
    retry after a discard re-derives the same id, so returning the record handed
    the caller a unit every downstream verb then reports as absent — stranding
    that filing target. The refusal states the dead end instead of restating the
    command that produced it. Recovery needs a supersede transition, which does
    not exist yet.
    """
    if period.filing_year != filing_year:
        evidence_values = {
            "modelo": modelo,
            "filing_year": filing_year,
            "period_year": period.filing_year,
            "period": period.registry_token,
            "revision_id": revision_id,
            "filing_year_matches_period": False,
        }
        raise WorkUnitMutationRefusedError(
            translated_message="application.modelo.errors.work_unit_filing_year_period_mismatch",
            context=evidence_values,
            precondition_failure=build_modelo_precondition_failure_for_scenario(
                subject_leaf_key="modelo.work.create",
                scenario_id="modelo.work.create.period.filing_year.mismatch",
                evidence_id="modelo.work.create.period.observation",
                evidence_values=evidence_values,
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )
    from ._profile_readiness_gate import (
        require_existing_profile_baseline_ready_for_modelo_work,
        require_profile_ready_for_modelo_work,
    )

    require_existing_profile_baseline_ready_for_modelo_work(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        enforce_applicability=enforce_applicability,
    )
    reject_unknown_revision(modelo=modelo, revision_id=revision_id)
    reject_unknown_period_for_revision(modelo=modelo, revision_id=revision_id, period=period)
    from ._work_addressing import resolve_registry_revision_for_work_target

    resolve_registry_revision_for_work_target(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        registry_revision_id=revision_id,
    )

    require_profile_ready_for_modelo_work(
        bucket_id=bucket_id,
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
        period=period,
        enforce_applicability=enforce_applicability,
    )
    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    # Revisioned: the catalogue is composed into the co-commit below with the
    # creation event, so it cannot use a self-committing mutation, and an
    # unguarded read would rewrite the singleton row over a work unit another
    # caller created in between.
    catalogue, catalogue_revision_id = repo.load_revisioned()
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    existing = catalogue.get(work_unit_id)
    if existing is not None:
        if existing.state is WorkUnitState.DESCARTADO:
            evidence_values = _work_unit_lifecycle_facts(existing)
            raise WorkUnitMutationRefusedError(
                translated_message="application.modelo.errors.work_unit_create_discarded",
                context=evidence_values,
                precondition_failure=build_modelo_precondition_failure_for_scenario(
                    subject_leaf_key="modelo.work.create",
                    scenario_id="modelo.work.create.lifecycle.target_discarded",
                    evidence_id="modelo.work.create.lifecycle.observation",
                    evidence_values=evidence_values,
                    provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                ),
            )
        return existing
    now = clock or _utc_now()
    unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=name.strip() if name else _default_name(modelo=modelo, filing_year=filing_year, period=period),
        created_at=now,
        updated_at=now,
        causante_ccaa=causante_ccaa,
    )
    # One unit of work: the new work unit and MODELO_WORK_UNIT_CREATED. Emitted
    # through a separate write, an event-storage failure left the unit durable
    # while the history had no record that it was ever created.
    created_event = _build_bucket_event(
        bucket_id=unit.bucket_id,
        event_type=BucketEventType.MODELO_WORK_UNIT_CREATED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=unit.work_unit_id,
        payload={
            "modelo": str(unit.modelo),
            "filing_year": str(unit.filing_year),
            "period": unit.period.registry_token,
            "revision_id": unit.revision_id,
            "name": unit.name,
        },
    )
    repo.save_with_secure_object_writes(
        upsert_work_unit(catalogue, unit),
        (_bucket_event_write(bv_repo, (created_event,)),),
        expected_revision_id=catalogue_revision_id,
    )
    return unit


def list_work_units(
    *,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> tuple[WorkUnit, ...]:
    """Return :class:`WorkUnit` records, optionally filtered to one bucket.

    Discarded work units are hidden by default so operator-facing discovery sees
    only active draft roots. Pass ``include_discarded=True`` for audit/history
    views that need the abandoned records.
    """
    repo = repository or WorkUnitCatalogueRepository()
    catalogue = repo.load()
    units = tuple(
        unit
        for unit in catalogue.values()
        if (bucket_id is None or unit.bucket_id == bucket_id)
        and (include_discarded or unit.state is WorkUnitState.BORRADOR)
    )
    return tuple(
        sorted(
            units,
            key=lambda u: (
                u.bucket_id,
                u.filing_year,
                str(u.modelo),
                u.period.registry_token,
            ),
        ),
    )


def _work_unit_in_repository_bucket(
    work_unit_id: str,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol,
) -> WorkUnit:
    """Return the work unit addressed by ``work_unit_id`` within this bucket.

    :class:`WorkUnitCatalogue` may hold rows for more than one bucket -- which is
    why :func:`list_work_units` takes a bucket filter -- but the single-subject
    surfaces looked units up by id alone. A caller bound to bucket A could
    therefore read, rename, or discard a valid bucket-B unit and emit a
    lifecycle event scoped to B, bypassing the bucket authority at the command
    boundary entirely.

    A unit belonging to another bucket is reported as NOT FOUND rather than as a
    refusal: from this repository's scope it genuinely is not addressable, and a
    distinct refusal would confirm the existence of a work unit in a bucket the
    caller has no claim on.

    The check is skipped only when the repository resolved no bucket of its own,
    where there is no scope to compare against.
    """
    catalogue = repository.load()
    unit = catalogue.get(work_unit_id)
    repository_bucket = repository.bucket_id
    if unit is None or (repository_bucket is not None and unit.bucket_id != repository_bucket):
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    return unit


def _work_unit_lifecycle_facts(work_unit: WorkUnit) -> dict[str, str | int]:
    """Return the primitive state coordinates carried by every lifecycle refusal."""
    return {
        "work_unit_id": work_unit.work_unit_id,
        "work_unit_state": work_unit.state.value,
        "modelo": str(work_unit.modelo),
        "filing_year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
        "revision_id": work_unit.revision_id,
    }


def require_active_work_unit(
    work_units: WorkUnitCatalogue,
    *,
    work_unit_id: str,
    repository_bucket_id: str | None,
    use: ActiveWorkUnitUse,
) -> WorkUnit:
    """Resolve one scoped active work unit or raise its declared lifecycle refusal.

    Calculation and external-import operations share this guard so a discarded
    state has one authority for addressability, typed facts, and the declared
    terminal verdict. Callers select only their operation identity; they cannot
    recreate the state predicate or its action/no-recovery outcome.
    """
    work_unit = work_units.get(work_unit_id)
    if work_unit is None or (repository_bucket_id is not None and work_unit.bucket_id != repository_bucket_id):
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    if work_unit.state is WorkUnitState.BORRADOR:
        return work_unit
    if work_unit.state is not WorkUnitState.DESCARTADO:
        raise ValueError(f"unhandled work-unit lifecycle state: {work_unit.state.value}")

    refusal = _ACTIVE_WORK_UNIT_REFUSALS[use]
    evidence_values = _work_unit_lifecycle_facts(work_unit)
    raise WorkUnitMutationRefusedError(
        translated_message=refusal.translated_message,
        context=evidence_values,
        precondition_failure=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key=refusal.subject_leaf_key,
            scenario_id=refusal.scenario_id,
            evidence_id=refusal.evidence_id,
            evidence_values=evidence_values,
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        ),
    )


def require_revision_parent_active(
    *,
    work_unit: WorkUnit,
    calculation_revision_id: CalculationRevisionId,
    operation: RevisionParentOperation,
) -> WorkUnit:
    """Admit a verify/file revision only while its persisted parent work unit is active."""
    if work_unit.state is WorkUnitState.BORRADOR:
        return work_unit
    if work_unit.state is not WorkUnitState.DESCARTADO:
        raise ValueError(f"unhandled work-unit lifecycle state: {work_unit.state.value}")
    refusal = _REVISION_PARENT_DISCARDED_REFUSALS[operation]
    evidence_values = {
        **_work_unit_lifecycle_facts(work_unit),
        "calculation_revision_id": calculation_revision_id,
    }
    raise CalculationRevisionNotFoundError(
        translated_message=refusal.translated_message,
        context=evidence_values,
        precondition_failure=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key=refusal.subject_leaf_key,
            scenario_id=refusal.scenario_id,
            evidence_id=refusal.evidence_id,
            evidence_values=evidence_values,
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        ),
    )


def get_work_unit(
    work_unit_id: str,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> WorkUnit:
    """Return one :class:`WorkUnit` by id or raise :class:`WorkUnitNotFoundError`.

    Scoped to the repository's own bucket: a unit belonging to another bucket is
    not addressable here and reads as not found.
    """
    repo = repository or WorkUnitCatalogueRepository()
    return _work_unit_in_repository_bucket(work_unit_id, repository=repo)


def rename_work_unit(
    work_unit_id: str,
    new_name: str,
    *,
    actor: str,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Update a :class:`WorkUnit` display name and emit a rename event.

    Discarded work units are immutable through this lifecycle surface.
    Successful renames preserve the content-addressed work-unit id and update
    only display metadata plus ``updated_at``.

    Scoped to the repository's own bucket: a unit belonging to another bucket is
    not addressable here, so an A-bound caller cannot rename a B unit and emit a
    B-scoped rename event.
    """
    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    existing = _work_unit_in_repository_bucket(work_unit_id, repository=repo)
    # Revisioned: the catalogue is composed into the co-commit below with the
    # lifecycle event, so it cannot use a self-committing mutation, and an
    # unguarded read rewrites the whole singleton row over a unit another
    # caller created or changed in between.
    catalogue, catalogue_revision_id = repo.load_revisioned()
    if existing.state is WorkUnitState.DESCARTADO:
        evidence_values = _work_unit_lifecycle_facts(existing)
        raise WorkUnitMutationRefusedError(
            translated_message="application.modelo.errors.work_unit_mutation_refused",
            context=evidence_values,
            precondition_failure=build_modelo_precondition_failure_for_scenario(
                subject_leaf_key="modelo.work.rename",
                scenario_id="modelo.work.rename.lifecycle.discarded",
                evidence_id="modelo.work.rename.lifecycle.observation",
                evidence_values=evidence_values,
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            ),
        )
    now = clock or _utc_now()
    cleaned_name = new_name.strip()
    cleaned_actor = actor.strip()
    renamed = existing.model_copy(update={"name": cleaned_name, "updated_at": now})
    # One unit of work: the renamed unit and MODELO_WORK_UNIT_RENAMED.
    renamed_event = _build_bucket_event(
        bucket_id=renamed.bucket_id,
        event_type=BucketEventType.MODELO_WORK_UNIT_RENAMED,
        occurred_at=now,
        actor=cleaned_actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=renamed.work_unit_id,
        payload={
            "modelo": str(renamed.modelo),
            "filing_year": str(renamed.filing_year),
            "period": renamed.period.registry_token,
            "previous_name": existing.name,
            "new_name": cleaned_name,
        },
    )
    repo.save_with_secure_object_writes(
        upsert_work_unit(catalogue, renamed),
        (_bucket_event_write(bv_repo, (renamed_event,)),),
        expected_revision_id=catalogue_revision_id,
    )
    return renamed


def discard_work_unit(
    work_unit_id: str,
    *,
    actor: str,
    reason: str | None = None,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Transition a :class:`WorkUnit` to ``DESCARTADO`` and emit a discard event.

    Discard is a durable state transition, not a physical delete. The work-unit
    record remains available for history/audit reads, repeated discards refuse
    with :class:`WorkUnitAlreadyDiscardedError`, and active-listing callers must
    opt in with ``include_discarded=True`` to see the abandoned root.

    Scoped to the repository's own bucket: a unit belonging to another bucket is
    not addressable here, so an A-bound caller cannot discard a B unit and emit a
    B-scoped discard event.
    """
    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    existing = _work_unit_in_repository_bucket(work_unit_id, repository=repo)
    # Revisioned: the catalogue is composed into the co-commit below with the
    # lifecycle event, so it cannot use a self-committing mutation, and an
    # unguarded read rewrites the whole singleton row over a unit another
    # caller created or changed in between.
    catalogue, catalogue_revision_id = repo.load_revisioned()
    if existing.state is WorkUnitState.DESCARTADO:
        evidence_values = _work_unit_lifecycle_facts(existing)
        raise WorkUnitAlreadyDiscardedError(
            translated_message="application.modelo.errors.work_unit_already_discarded",
            context=evidence_values,
            precondition_failure=build_modelo_precondition_failure_for_scenario(
                subject_leaf_key="modelo.work.discard",
                scenario_id="modelo.work.discard.lifecycle.already_discarded",
                evidence_id="modelo.work.discard.lifecycle.observation",
                evidence_values=evidence_values,
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            ),
        )
    now = clock or _utc_now()
    discarded = existing.model_copy(
        update={
            "state": WorkUnitState.DESCARTADO,
            "discarded_at": now,
            "discarded_by": actor.strip(),
            "discard_reason": reason.strip() if reason else None,
            "updated_at": now,
        },
    )
    # One unit of work: the discarded unit and MODELO_WORK_UNIT_DISCARDED.
    discarded_event = _build_bucket_event(
        bucket_id=discarded.bucket_id,
        event_type=BucketEventType.MODELO_WORK_UNIT_DISCARDED,
        occurred_at=now,
        actor=discarded.discarded_by or actor.strip(),
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=discarded.work_unit_id,
        payload={
            "modelo": str(discarded.modelo),
            "filing_year": str(discarded.filing_year),
            "period": discarded.period.registry_token,
            "reason": discarded.discard_reason or "",
        },
    )
    repo.save_with_secure_object_writes(
        upsert_work_unit(catalogue, discarded),
        (_bucket_event_write(bv_repo, (discarded_event,)),),
        expected_revision_id=catalogue_revision_id,
    )
    return discarded
