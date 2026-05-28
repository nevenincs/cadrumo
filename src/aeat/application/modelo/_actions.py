"""Modelo work-unit lifecycle actions.

Each action loads the catalogue, applies a single mutation in
memory (or returns a read view), and writes the catalogue back.
The catalogue is content-addressed by ``work_unit_id`` so
deterministic deriveation lets ``create_work_unit`` be idempotent:
calling it twice with the same four-axis key returns the same
record without producing a duplicate.

The action signatures take an explicit ``bucket_id`` so the
service layer is unit-testable without a workflow-state fixture.
"""

from __future__ import annotations

import asyncio
import hashlib
import re as _re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...application.auth import AuthProviderKind, select_provider
from ...core.config import Settings, load_settings
from ...core.i18n import tr
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.calculations.registry import (
    CasillaDefinition,
    CasillaObservation,
    ConvenioRateRow,
    ModeloRevision,
    RegistryCalculationEntry,
    RegistryCalculationResult,
    RegistrySnapshot,
    VerificationPredicateDefinition,
    calculate_registry_snapshot,
    enum_consumed_binding_ids,
    expression_binding_refs,
    input_casilla_alias_map,
    materialize_relation_binding_values,
)
from ...domain.deadlines import DeadlineEngine, TaxpayerProfile
from ...domain.filing import ModeloDraftStatus
from ...domain.invoices import InvoiceCatalogueRepository
from ...domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos._codes import ModeloCode
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ...domain.modelos._filing_repository import (
    ModeloRecordCatalogueRepository,
    upsert_filing_record,
)
from ...domain.modelos._repository import (
    WorkUnitCatalogueRepository,
    upsert_work_unit,
)
from ...domain.modelos._row_models import ModeloDetailRow
from ...domain.modelos._verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from ...domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
    upsert_verification_report,
)
from ...domain.modelos._work_unit import (
    WorkUnit,
    WorkUnitCatalogue,
    WorkUnitState,
    derive_work_unit_id,
)
from ...domain.period import parse_canonical_period, period_end_date
from ...domain.profile._ccaa import CCAA
from ...domain.submission import SubmissionEngine
from ...domain.transactions import TransactionCatalogue, TransactionCatalogueRepository
from ..filing import (
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    filing_profile_from_taxpayer,
)
from ..live import Borrador100SnapshotRepository
from ..workflow import (
    DeadlineEngineAdapter,
    ModeloInputs,
    RegistryModeloDraftProtocol,
    WorkflowEngine,
    WorkflowPurpose,
    WorkflowResult,
    WorkflowRunRepository,
    WorkflowStage,
)
from ._borrador_binding import (
    Modelo100BorradorBindingResult,
    Modelo100BorradorSourceResolver,
)
from ._profile_binding import ProfileSourcedBindingResult

if TYPE_CHECKING:
    from ...domain.calculations.registry import ValidatedRegistryAuthority
    from ..calculations._iva_wallet_reconciliation import (
        IvaCompensationReconciliationDecision,
    )
    from ..calculations._observations_repository import IvaWalletDecisionRepository

_BUCKET_EVENT_PAYLOAD_VERSION = 2
"""Schema version for the bucket-event payload dict emitted by this module.

v1 -> v2: ``has_provenance`` key added on the
``modelo.calculation.created`` payload signalling whether the linked
revision carries a non-empty typed observations tuple. The same
payload carries the explicit ``calculation_revision_id`` join key and
the borrador participation triple (``borrador_participated``,
``borrador_binding_count``, ``borrador_bindings_trace_sha256``) so that
audit tools reading the event log alone can detect grounding-loss
regressions without joining against the encrypted revision catalogue.
"""


def _emit_bucket_event(
    *,
    repository: BucketEventHistoryRepository,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: Mapping[str, str],
) -> BucketEvent:
    """Append one event to the bucket-event-history catalogue and
    return the persisted record. Content-addressed: re-emitting an
    identical event is a no-op.
    """

    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor.strip(),
        object_type=object_type,
        object_id=object_id,
        payload=payload,
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor.strip(),
        object_type=object_type,
        object_id=object_id,
        payload_version=_BUCKET_EVENT_PAYLOAD_VERSION,
        payload=dict(payload),
    )
    catalogue = repository.load()
    repository.save(append_bucket_event(catalogue, event))
    return event


class WorkUnitNotFoundError(ModeloError, KeyError):
    """Raised when a work-unit lookup or mutation targets a missing id."""


class WorkUnitAlreadyDiscardedError(ModeloError):
    """Raised when discard is invoked on a work unit already discarded."""


class WorkUnitMutationRefusedError(ModeloError):
    """Raised when a mutation targets a discarded work unit."""


class CalculationRevisionNotFoundError(ModeloError, KeyError):
    """Raised when a calculation revision lookup fails."""


class CalculationRevisionStateError(ModeloError):
    """Raised when a state transition is requested from an incompatible source state.

    Examples: marking a non-draft revision as verified-complete;
    filing a revision that is not verified-complete; verifying a
    revision that has already been filed.
    """


class ModeloRecordNotFoundError(ModeloError, KeyError):
    """Raised when a filing record lookup fails."""


class VerificationReportNotFoundError(ModeloError, KeyError):
    """Raised when a verification report lookup fails."""


class AmendmentEvidenceMissingError(ModeloError):
    """Raised when the modelo-amend path is asked to amend a filing
    record that carries no imported official evidence.

    The amend path is gated on ``external_evidence`` being populated
    on the baseline filing record. A locally-computed filing record
    must use the standard re-file supersession path (calculate →
    verify → file) instead of the amend verb.
    """


class AmendmentTargetStateError(ModeloError):
    """Raised when the modelo-amend path is asked to amend a filing
    record that is not in ``CURRENT`` status (e.g., it was already
    superseded by a later filing)."""


class StoredCalculationDriftError(ModeloError):
    """Raised when the verify path detects that a persisted calculation revision
    has drifted from its content-addressed id.

    The ``calculation_revision_id`` is a SHA-256 hash of
    ``(work_unit_id, inputs_snapshot, binding_overrides, casilla_values)``.
    When the stored payload re-hashes to a different value the record has been
    mutated after creation — either by tampering or a storage corruption.  The
    verify path refuses VERIFICADO_COMPLETO and raises this error so the
    operator is forced to produce a fresh calculation revision.
    """


class ExternalModeloImportError(ModeloError):
    """Raised when the external-filing import path cannot persist an
    imported baseline (e.g., empty casilla values, missing evidence
    reference)."""


#: Legal anchors for the modelo workflow gate. The gate enforces
#: that a Modelo declaration only transitions to VERIFICADO_COMPLETO
#: or FILED after the workflow engine ran auth + deadline-window +
#: draft + preflight stages. The grounding spans:
#:
#:   - ``ley-58-2003:art-119`` (declaracion tributaria — what a tax
#:     declaration is, the locked semantics of ModeloRecord
#:     persistence)
#:   - ``ley-58-2003:art-120`` (autoliquidaciones — the
#:     self-assessment regime modelo file_modelo_revision performs,
#:     and the rectificacion procedure that flows through
#:     amend_modelo_revision)
#:   - ``ley-58-2003:art-122`` (complementarias / sustitutivas — the
#:     supersession transition that file_modelo_revision applies when
#:     a prior CURRENT filing exists)
_WORKFLOW_GATE_LEGAL_REFS: tuple[str, ...] = (
    "ley-58-2003:art-119",
    "ley-58-2003:art-120",
    "ley-58-2003:art-122",
)


class ModeloWorkflowGateError(ModeloError):
    """Raised when the workflow gate refuses an internal file transition.

    The gate is grounded in the procedural articles of the Ley General
    Tributaria (Ley 58/2003) named in
    :data:`_WORKFLOW_GATE_LEGAL_REFS`. A refusal here means the
    declaration cannot be considered legally filed under those
    articles' regime.
    """

    def __init__(self, result: WorkflowResult) -> None:
        # The live WorkflowResult is retained on a private attribute so it
        # never reaches the CLI error boundary. `render_error_text` merges
        # every *public* instance attribute into the operator-facing
        # context via `vars(error)`; a public `result` attribute would
        # leak a raw Python object repr (datetime constructors, enum
        # reprs, nested WorkflowStep tuples) straight at a non-technical
        # taxpayer. The context below carries only already-stringified
        # primitives — the clean summary the operator needs.
        self._result = result
        reason = result.aborted_reason.value if result.aborted_reason is not None else "unknown"
        summary = result.summary.strip() or "the workflow gate aborted this transition"
        super().__init__(
            summary,
            context={
                "abort_code": reason,
                "stage": result.final_stage.value,
            },
        )

    @property
    def result(self) -> WorkflowResult:
        """Return the live :class:`WorkflowResult` that triggered the abort.

        Exposed as a property (not a plain instance attribute) so the
        CLI error boundary's ``vars(error)`` context merge never picks
        it up and renders its raw Python repr to the operator.
        """

        return self._result


class AmendmentOverrideCasillaError(ModeloError):
    """Raised when an amendment override targets a casilla id the
    registry does not declare for the baseline's modelo / filing
    year / period. The corrected revision is the legal basis of the
    complementaria filing — fabricated casilla ids cannot be silently
    accepted."""


class AmendmentVerificationRefusedError(ModeloError):
    """Raised when the corrected casilla map fails verification.

    Mirrors the standard ``verify_modelo_revision`` contract: every
    required-manual-input casilla declared by the registry for the
    baseline's modelo / filing year / period must be present in the
    corrected map. Amend refuses rather than persisting an
    incomplete complementaria because the corrected revision is the
    legal basis of the filing."""


def _default_name(*, modelo: str, filing_year: int, period: str) -> str:
    """Return the default display name for a fresh work unit.

    Shape: ``<modelo>-<year>-<period>`` (e.g. ``303-2026-Q1``).
    Callers may supply their own name; this helper exists so the
    domain shape stays predictable when the operator does not
    care to name the unit.
    """
    return f"{modelo}-{filing_year}-{period}"


def workflow_period_for_work_unit(work_unit: WorkUnit) -> str:
    """Return the canonical period token consumed by WorkflowEngine.

    The work unit stores the period as a short registry token (``"1T"``,
    ``"0A"``, ``"03"``, ``"1P"``); the :class:`WorkflowEngine` consumes a
    year-qualified token (``"2026Q1"``, ``"2026"``, ``"2026-03"``,
    ``"2026P1"``).  This is the single producer of that mapping, used by
    the workflow gate and by run-id resolution so they cannot diverge.
    """

    if work_unit.period.endswith("T") and len(work_unit.period) == 2:
        quarter = work_unit.period[0]
        return f"{work_unit.filing_year}Q{quarter}"
    if work_unit.period == "0A":
        return str(work_unit.filing_year)
    if len(work_unit.period) == 2 and work_unit.period.isdigit():
        return f"{work_unit.filing_year}-{work_unit.period}"
    # Pago-fraccionado tokens (``"1P"`` / ``"2P"`` / ``"3P"``) compose to
    # ``"YYYYPn"`` so the workflow engine and registry token resolver share
    # the same year-qualified form.
    if len(work_unit.period) == 2 and work_unit.period.endswith("P") and work_unit.period[0] in "123":
        return f"{work_unit.filing_year}P{work_unit.period[0]}"
    # Fallback: validate via the canonical parser; raise on unrecognised tokens.
    parse_canonical_period(work_unit.period)
    return work_unit.period


class _RevisionInputsProvider:
    """Loads immutable calculation-revision inputs for the workflow gate."""

    def __init__(self, *, revision: CalculationRevision, work_unit: WorkUnit) -> None:
        self._revision = revision
        self._modelo = work_unit.modelo
        self._period = workflow_period_for_work_unit(work_unit)

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: TaxpayerProfile,
    ) -> ModeloInputs:
        del profile
        if modelo != self._modelo or period != self._period:
            raise ValueError("workflow input request does not match calculation revision")
        return {
            **dict(self._revision.inputs_snapshot),
            **dict(self._revision.binding_overrides),
        }


class _RevisionDraftBuilder:
    """Builds and locally approves the draft backed by the target revision."""

    def __init__(self, *, work_unit: WorkUnit, actor: str, clock: datetime) -> None:
        self._work_unit = work_unit
        self._actor = actor
        self._clock = clock
        self._schema_provider = build_runtime_schema_provider(
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            modelos=(work_unit.modelo,),
        )

    def build(
        self,
        *,
        modelo: str,
        period: str,
        profile: TaxpayerProfile,
        inputs: ModeloInputs,
        fail_on_warning: bool = False,
    ) -> RegistryModeloDraftProtocol:
        draft = build_draft(
            modelo=modelo,
            period=period,
            profile=filing_profile_from_taxpayer(profile),
            inputs=inputs,
            schema_provider=self._schema_provider,
            fail_on_warning=fail_on_warning,
        )
        if draft.status is not ModeloDraftStatus.LISTO_PARA_PRESENTAR:
            return draft
        return approve_draft(
            draft,
            bucket_id=self._work_unit.bucket_id,
            approved_by=self._actor,
            schema_provider=self._schema_provider,
            transaction_catalogue=TransactionCatalogue(),
            approved_at=self._clock,
        )


class _RevisionDeadlineWindowChecker:
    """Checks the same deadline schedule the workflow gate already computed."""

    def __init__(self, *, profile: TaxpayerProfile, engine: DeadlineEngine) -> None:
        self._profile = profile
        self._engine = engine

    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        year, _ = parse_canonical_period(period)
        schedule = self._engine.compute(self._profile, year, today=today)
        return any(
            obligation.modelo == modelo
            and obligation.period == period
            and obligation.opens_on <= today <= obligation.closes_on
            for obligation in schedule.obligations
        )


def _build_revision_workflow_engine(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    profile: TaxpayerProfile,
    actor: str,
    clock: datetime,
    settings: Settings | None,
) -> WorkflowEngine:
    cfg = settings or load_settings()
    deadline_engine = DeadlineEngine()
    provider_kind = (
        AuthProviderKind(cfg.aeat_auth_provider.value)
        if cfg.aeat_auth_provider is not None
        else AuthProviderKind.CERTIFICATE
    )
    submission_engine = SubmissionEngine(
        auth_provider=select_provider(provider_kind, settings=cfg),
        deadline_checker=_RevisionDeadlineWindowChecker(profile=profile, engine=deadline_engine),
        settings=cfg,
    )
    return WorkflowEngine(
        deadline_engine=DeadlineEngineAdapter(deadline_engine),
        filing_draft_builder=_RevisionDraftBuilder(work_unit=work_unit, actor=actor, clock=clock),
        submission_engine=submission_engine,
        session=None,
        certificate_bundle=None,
        inputs_provider=_RevisionInputsProvider(
            revision=revision,
            work_unit=work_unit,
        ),
        settings=cfg,
    )


def _run_revision_workflow_gate(
    *,
    engine: WorkflowEngine,
    profile: TaxpayerProfile,
    work_unit: WorkUnit,
    today: date,
    runs_dir: Path | None,
    run_repository: WorkflowRunRepository,
    resumed_from: str | None = None,
    purpose: WorkflowPurpose = WorkflowPurpose.FILE,
) -> WorkflowResult:
    result = asyncio.run(
        engine.run_for_period(
            profile,
            work_unit.modelo,
            workflow_period_for_work_unit(work_unit),
            today=today,
            resumed_from=resumed_from,
            purpose=purpose,
        )
    )
    run_repository.save(result, runs_dir=runs_dir)
    if result.final_stage is WorkflowStage.ABORTED:
        raise ModeloWorkflowGateError(result)
    return result


def create_work_unit(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
    name: str | None = None,
    actor: str = "system",
    causante_ccaa: CCAA | None = None,
    repository: WorkUnitCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Create or load a work unit for the four-axis key.

    Idempotent: when a work unit already exists under the
    deterministic id, the existing record is returned unchanged.
    A subsequent call with a different ``name`` does NOT mutate the
    persisted name; ``rename_work_unit`` is the dedicated mutation
    surface for that.

    On a genuine creation (not an idempotent re-load) a
    ``modelo.work_unit.created`` bucket event is emitted so the
    work-unit history is complete from its first moment — the audit
    trail records when and by whom the unit was provisioned. An
    idempotent re-load emits nothing: the unit already exists and the
    original creation event already stands.

    Args:
        bucket_id: Stable bucket the work unit belongs to.
        modelo: AEAT modelo code (e.g. ``"303"``).
        filing_year: Tax year for the filing.
        period: Filing period token (e.g. ``"Q1"``).
        revision_id: Stable id of the targeted modelo revision.
        name: Optional display name; defaults to
            ``<modelo>-<year>-<period>``.
        actor: Actor label recorded on the creation bucket event.
        repository: Repository override for testing; defaults to
            the canonical ``WorkUnitCatalogueRepository``.
        bucket_event_repository: Bucket-event repository override for
            testing; defaults to ``BucketEventHistoryRepository``.
        clock: ``datetime`` override for testing the created /
            updated timestamps. Defaults to ``datetime.now(UTC)``.

    Returns:
        The persisted :class:`aeat.domain.modelos.WorkUnit`.
    """

    _reject_unknown_revision(modelo=modelo, revision_id=revision_id)
    _reject_unknown_period_for_revision(modelo=modelo, revision_id=revision_id, period=period)
    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    catalogue = repo.load()
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    existing = catalogue.get(work_unit_id)
    if existing is not None:
        return existing
    now = clock or datetime.now(UTC)
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
    updated = upsert_work_unit(catalogue, unit)
    repo.save(updated)
    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=unit.bucket_id,
        event_type=BucketEventType.MODELO_WORK_UNIT_CREATED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=unit.work_unit_id,
        payload={
            "modelo": str(unit.modelo),
            "filing_year": str(unit.filing_year),
            "period": unit.period,
            "revision_id": unit.revision_id,
            "name": unit.name,
        },
    )
    return unit


def list_work_units(
    *,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    repository: WorkUnitCatalogueRepository | None = None,
) -> tuple[WorkUnit, ...]:
    """Return work units, optionally filtered to one bucket.

    Discarded work units are excluded by default; pass
    ``include_discarded=True`` to see them. The result is sorted
    by ``(bucket_id, filing_year, modelo, period)`` so consumers
    see a stable ordering across calls without re-sorting.
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
                u.period,
            ),
        )
    )


def get_work_unit(
    work_unit_id: str,
    *,
    repository: WorkUnitCatalogueRepository | None = None,
) -> WorkUnit:
    """Return one work unit by id.

    Raises:
        WorkUnitNotFoundError: When no work unit lives under
            ``work_unit_id``. ``KeyError`` is in the base classes
            so callers that prefer the Python idiom can still
            ``except KeyError``.
    """

    repo = repository or WorkUnitCatalogueRepository()
    catalogue = repo.load()
    unit = catalogue.get(work_unit_id)
    if unit is None:
        raise WorkUnitNotFoundError(tr("application.modelo.errors.work_unit_not_found", work_unit_id=work_unit_id))
    return unit


def rename_work_unit(
    work_unit_id: str,
    new_name: str,
    *,
    actor: str,
    repository: WorkUnitCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Update a work unit's display name and bump ``updated_at``.

    The ``work_unit_id`` does not change — the identifier is
    content-addressed by the four-axis key, not by display name.
    A ``modelo.work_unit.renamed`` bucket event records the actor and
    the prior / new name so the audit trail captures who initiated the
    rename.
    """

    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    catalogue: WorkUnitCatalogue = repo.load()
    existing = catalogue.get(work_unit_id)
    if existing is None:
        raise WorkUnitNotFoundError(tr("application.modelo.errors.work_unit_not_found", work_unit_id=work_unit_id))
    if existing.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            f"work unit {work_unit_id!r} is discarded; "
            "create a fresh work unit on the same modelo / year / period to continue"
        )
    now = clock or datetime.now(UTC)
    cleaned_name = new_name.strip()
    cleaned_actor = actor.strip()
    renamed = existing.model_copy(update={"name": cleaned_name, "updated_at": now})
    updated_catalogue = upsert_work_unit(catalogue, renamed)
    repo.save(updated_catalogue)
    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=renamed.bucket_id,
        event_type=BucketEventType.MODELO_WORK_UNIT_RENAMED,
        occurred_at=now,
        actor=cleaned_actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=renamed.work_unit_id,
        payload={
            "modelo": str(renamed.modelo),
            "filing_year": str(renamed.filing_year),
            "period": renamed.period,
            "previous_name": existing.name,
            "new_name": cleaned_name,
        },
    )
    return renamed


def discard_work_unit(
    work_unit_id: str,
    *,
    actor: str,
    reason: str | None = None,
    repository: WorkUnitCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Transition a work unit to ``DISCARDED`` state.

    Audit metadata (``discarded_at``, ``discarded_by``, optional
    ``discard_reason``) is captured in the same write. Once
    discarded, the work unit cannot be renamed or re-activated;
    the operator must create a fresh work unit on the same modelo
    / year / period. A ``modelo.work_unit.discarded`` bucket event
    is emitted alongside the state transition.

    Raises:
        WorkUnitNotFoundError: When ``work_unit_id`` is absent.
        WorkUnitAlreadyDiscardedError: When the unit is already
            in ``DISCARDED`` state. Idempotent retries would
            corrupt the audit trail.
    """

    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    catalogue: WorkUnitCatalogue = repo.load()
    existing = catalogue.get(work_unit_id)
    if existing is None:
        raise WorkUnitNotFoundError(tr("application.modelo.errors.work_unit_not_found", work_unit_id=work_unit_id))
    if existing.state is WorkUnitState.DESCARTADO:
        raise WorkUnitAlreadyDiscardedError(
            f"work unit {work_unit_id!r} is already discarded "
            f"(by {existing.discarded_by!r} at {existing.discarded_at!s})"
        )
    now = clock or datetime.now(UTC)
    discarded = existing.model_copy(
        update={
            "state": WorkUnitState.DESCARTADO,
            "discarded_at": now,
            "discarded_by": actor.strip(),
            "discard_reason": reason.strip() if reason else None,
            "updated_at": now,
        }
    )
    updated_catalogue = upsert_work_unit(catalogue, discarded)
    repo.save(updated_catalogue)
    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=discarded.bucket_id,
        event_type=BucketEventType.MODELO_WORK_UNIT_DISCARDED,
        occurred_at=now,
        actor=discarded.discarded_by or actor.strip(),
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=discarded.work_unit_id,
        payload={
            "modelo": str(discarded.modelo),
            "filing_year": str(discarded.filing_year),
            "period": discarded.period,
            "reason": discarded.discard_reason or "",
        },
    )
    return discarded


# ---------------------------------------------------------------------------
# Calculation revision lifecycle: calculate / verify / mark-verified / file
# ---------------------------------------------------------------------------


def _canonical_decimal_str(value: Decimal) -> str:
    """Stable string form of a Decimal for content-addressing."""

    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")


class CalculationRegistryUnavailableError(ModeloError):
    """Raised when the registry snapshot for a work unit's
    (modelo, year, period) cannot be resolved at calculate time.

    The calculate path runs the registry's formula engine against
    the snapshot; if no snapshot exists for the work unit's axis
    triple the action fails clearly rather than persisting a
    revision with operator-supplied values that bypass formula
    evaluation.
    """


class ModeloAggregationBindingError(ModeloError):
    """Raised when bucket-derived aggregation bindings conflict with caller input."""


class ModeloIvaWalletReconciliationBlocked(ModeloError):  # noqa: N818
    """Raised when Modelo 303 calculation is blocked by IVA wallet reconciliation."""


class CasillaProvenanceMissingError(ModeloError):
    """Raised when an engine-result casilla has no registry definition.

    Every casilla in :attr:`RegistryCalculationResult.values` must be
    a casilla declared on the registry snapshot's revision. A casilla
    present in the engine result but absent from
    ``snapshot.revision.casillas`` is a referential-integrity
    violation: building a :class:`CasillaObservation` for it would
    silently emit empty ``legal_refs`` / ``source_refs`` and erase the
    legal provenance the audit surface depends on. The observation
    build hard-fails instead of persisting a provenance-stripped row.
    """


def calculate_modelo_revision(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[str, Decimal],
    binding_values: Mapping[str, Decimal] | None = None,
    enum_binding_values: Mapping[str, str] | None = None,
    backend_binding_values: Mapping[str, Decimal] | None = None,
    backend_casilla_inputs: Mapping[str, Decimal] | None = None,
    iva_compensation_decision: object | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    ledger_preflight_transaction_repository: TransactionCatalogueRepository | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[str, Decimal] | None = None,
    source_transaction_ids: tuple[str, ...] = (),
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> CalculationRevision:
    """Run the registry formula engine and persist a draft revision.

    Pipeline:

    1. Load the work unit; refuse on DISCARDED.
    2. Resolve the registry snapshot for ``(modelo, filing_year,
       period)``. Failure to resolve raises
       :exc:`CalculationRegistryUnavailableError` — the calculate
       path runs the engine, so a missing snapshot is a hard refusal.
    3. Run :func:`calculate_registry_snapshot` over the snapshot
       with the operator-supplied manual casilla inputs, binding
       values, enum-binding values, and relation values. The
       engine evaluates every declared formula in dependency order
       and returns the full ``casilla_values`` map (inputs plus
       formula outputs).
    4. Build canonical-string ``inputs_snapshot`` and
       ``binding_overrides`` from the engine inputs (so the
       content-addressed revision id is stable across structurally
       identical re-runs).
    5. Persist the revision in ``DRAFT`` state; advance the work
       unit's ``current_calculation_revision_id`` pointer; emit
       ``modelo.calculation.created``.

    The revision starts in DRAFT state; callers must run
    ``verify_modelo_revision`` and ``file_modelo_revision``
    explicitly to advance through the lifecycle.
    """

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    work_units = wu_repo.load()
    work_unit = _load_work_unit_for_calculation(work_units, work_unit_id=work_unit_id)
    snapshot = _resolve_registry_snapshot_for_work_unit(work_unit)
    # Operator-supplied casilla keys may be the registry number or BOE
    # form number shown by `modelo casillas`; normalise both the caller
    # inputs and the backend-merged inputs to canonical casilla ids
    # before the engine consumes them.
    casilla_inputs = _normalize_casilla_input_aliases(snapshot.revision, casilla_inputs)
    if backend_casilla_inputs is not None:
        backend_casilla_inputs = _normalize_casilla_input_aliases(snapshot.revision, backend_casilla_inputs)
    _raise_if_ledger_preflight_blocks_calculation(
        work_unit=work_unit,
        revision=snapshot.revision,
        transaction_repository=ledger_preflight_transaction_repository,
    )
    if iva_compensation_decision is None:
        iva_compensation_decision = _load_persisted_iva_compensation_decision_for_work_unit(
            work_unit,
            repository=iva_compensation_decision_repository,
        )
    else:
        iva_compensation_decision = _require_persisted_iva_compensation_decision_for_work_unit(
            work_unit,
            supplied_decision=iva_compensation_decision,
            repository=iva_compensation_decision_repository,
        )

    period_date = filing_period_date or period_end_date(
        filing_year=work_unit.filing_year,
        registry_period=work_unit.period,
    )
    caller_binding_values = dict(binding_values or {})
    caller_enum_binding_values = dict(enum_binding_values or {})
    lower_precedence_binding_values = dict(backend_binding_values or {})
    _apply_iva_compensation_decision_binding(
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        bucket_id=work_unit.bucket_id,
        revision=snapshot.revision,
        taxpayer_nif=_taxpayer_nif_for_bucket(work_unit.bucket_id),
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        caller_binding_values=caller_binding_values,
        backend_binding_values=lower_precedence_binding_values,
        decision=iva_compensation_decision,
    )
    borrador_result = _resolve_borrador_bindings_for_calculation(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        borrador_snapshot_id=borrador_snapshot_id,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        registry_snapshot=snapshot,
        snapshot_repository=borrador_snapshot_repository,
    )
    profile_result = _resolve_profile_bindings_for_calculation(
        bucket_id=work_unit.bucket_id,
        snapshot=snapshot,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        borrador_result=borrador_result,
        backend_binding_values=lower_precedence_binding_values,
    )
    resolved_bindings = dict(
        sorted(
            {
                **profile_result.binding_values,
                **lower_precedence_binding_values,
                **borrador_result.binding_values,
                **caller_binding_values,
            }.items()
        )
    )
    resolved_enum_bindings = dict(
        sorted(
            {
                **profile_result.enum_binding_values,
                **borrador_result.enum_binding_values,
                **caller_enum_binding_values,
            }.items()
        )
    )
    resolved_date_bindings = dict(sorted(profile_result.date_binding_values.items()))
    _reject_binding_channel_mismatch(snapshot.revision, resolved_bindings, resolved_enum_bindings)
    resolved_relations = dict(relation_values or {})
    relation_binding_values = materialize_relation_binding_values(
        snapshot.revision,
        resolved_relations,
        period=work_unit.period,
    )
    resolved_bindings = dict(sorted({**relation_binding_values, **resolved_bindings}.items()))
    # When the operator supplies --casilla for a previous_filing-bound casilla (e.g.
    # M130 casilla 15 resultados negativos, M131 casilla 11) and no upstream resolver has
    # provided the corresponding binding value, promote the casilla override into the
    # binding_values map.  The engine requires that inputs[casilla_id] and
    # binding_values[binding_id] agree; this promotion makes them agree by construction.
    resolved_bindings = dict(
        sorted(
            _lift_previous_filing_casilla_overrides_to_bindings(
                snapshot.revision, casilla_inputs, resolved_bindings
            ).items()
        )
    )
    declaration_period_inputs = _resolve_declaration_period_inputs(
        snapshot.revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    resolved_inputs = dict(
        sorted(
            {
                **declaration_period_inputs,
                **dict(backend_casilla_inputs or {}),
                **_resolve_bound_casilla_inputs_for_available_bindings(
                    snapshot.revision,
                    resolved_bindings,
                ),
                **casilla_inputs,
            }.items()
        )
    )

    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=resolved_inputs,
        date_context={"filing_period": period_date},
        binding_values=resolved_bindings,
        enum_binding_values=resolved_enum_bindings,
        relation_values=resolved_relations,
        date_binding_values=resolved_date_bindings or None,
    )

    inputs_snapshot: dict[str, str] = dict(
        sorted((k.strip(), _canonical_decimal_str(v)) for k, v in resolved_inputs.items())
    )
    binding_overrides: dict[str, str] = dict(
        sorted(
            [(k.strip(), _canonical_decimal_str(v)) for k, v in resolved_bindings.items()]
            + [(k.strip(), v.strip()) for k, v in resolved_enum_bindings.items()]
        )
    )
    casilla_values = dict(engine_result.values)
    typed_observations = _build_typed_observations(engine_result=engine_result, snapshot=snapshot)

    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        borrador_snapshot_id=borrador_result.borrador_snapshot_id,
        bindings_sourced_from_borrador=borrador_result.bindings_sourced_from_borrador,
        detail_rows=detail_rows,
    )
    revisions = cr_repo.load()
    existing = revisions.get(revision_id)
    if existing is not None:
        return existing
    now = clock or datetime.now(UTC)
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        source_transaction_ids=source_transaction_ids,
        borrador_snapshot_id=borrador_result.borrador_snapshot_id,
        bindings_sourced_from_borrador=borrador_result.bindings_sourced_from_borrador,
        casilla_values=casilla_values,
        observations=typed_observations,
        detail_rows=detail_rows,
        created_at=now,
        updated_at=now,
    )
    cr_repo.save(upsert_calculation_revision(revisions, revision))
    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": revision_id,
                    "updated_at": now,
                }
            ),
        )
    )
    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id=revision_id,
        payload={
            "calculation_revision_id": revision_id,
            "work_unit_id": work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "input_casilla_count": str(len(inputs_snapshot)),
            "casilla_count": str(len(casilla_values)),
            "formula_count": str(len(engine_result.entries)),
            "source_transaction_count": str(len(source_transaction_ids)),
            "borrador_snapshot_id": borrador_result.borrador_snapshot_id or "",
            "borrador_participated": ("true" if borrador_result.bindings_sourced_from_borrador else "false"),
            "borrador_binding_count": str(len(borrador_result.bindings_sourced_from_borrador)),
            "borrador_bindings_trace_sha256": hashlib.sha256(
                "\n".join(borrador_result.bindings_sourced_from_borrador).encode("utf-8")
            ).hexdigest(),
            # Signals whether the linked calculation revision carries a
            # non-empty typed observations tuple. Audit tools reading
            # the event log alone can detect grounding-loss regressions
            # without joining against the encrypted revision catalogue;
            # the ``object_id`` field above is the revision id, used as
            # the join key for full provenance recovery.
            "has_provenance": "true" if typed_observations else "false",
        },
    )
    return revision


def _apply_iva_compensation_decision_binding(
    modelo: str,
    filing_year: int,
    period: str,
    *,
    bucket_id: str,
    revision: ModeloRevision,
    taxpayer_nif: str | None = None,
    casilla_inputs: Mapping[str, Decimal] | None = None,
    backend_casilla_inputs: Mapping[str, Decimal] | None = None,
    caller_binding_values: dict[str, Decimal],
    backend_binding_values: dict[str, Decimal],
    decision: object | None,
) -> None:
    """Apply a non-blocking IVA wallet decision to Modelo 303 binding values."""

    if modelo != "303":
        return
    binding_id = "modelo-303-compensacion-pendiente-anteriores"
    bound_casilla_id = "iva.compensacion-pendiente-periodos-anteriores"
    caller_casilla_value = dict(casilla_inputs or {}).get(bound_casilla_id)
    backend_casilla_value = dict(backend_casilla_inputs or {}).get(bound_casilla_id)
    if decision is None:
        caller_value = caller_binding_values.get(binding_id)
        backend_value = backend_binding_values.get(binding_id)
        if (
            caller_value is not None
            or backend_value is not None
            or caller_casilla_value is not None
            or backend_casilla_value is not None
        ):
            raise ModeloIvaWalletReconciliationBlocked(
                translated_message="application.modelo.errors.iva_wallet_not_seeded",
                suggestion="aeat app modelo iva-wallet seed --filing-year YEAR --period PERIOD --amount 0 --confirm",
            )
        return

    from ..calculations._iva_wallet_reconciliation import IvaCompensationReconciliationDecision

    if not isinstance(decision, IvaCompensationReconciliationDecision):
        raise ModeloIvaWalletReconciliationBlocked("iva_compensation_decision has an unsupported type")
    if decision.target_year != filing_year or decision.target_period != period:
        raise ModeloIvaWalletReconciliationBlocked(
            "IVA wallet reconciliation decision target does not match the Modelo 303 work unit"
        )
    if taxpayer_nif is None:
        raise ModeloIvaWalletReconciliationBlocked(
            "IVA wallet reconciliation decision cannot be applied without a work-unit taxpayer identity"
        )
    if decision.taxpayer_nif.strip().upper() != taxpayer_nif.strip().upper():
        raise ModeloIvaWalletReconciliationBlocked(
            "IVA wallet reconciliation decision taxpayer does not match the Modelo 303 work unit"
        )
    if decision.blocked:
        raise ModeloIvaWalletReconciliationBlocked(
            "IVA wallet reconciliation blocks automatic Modelo 303 calculation: "
            f"{decision.divergence}: {decision.reason}"
        )
    if decision.selected_amount is None:
        raise ModeloIvaWalletReconciliationBlocked("IVA wallet reconciliation decision has no selected amount")
    selected = Decimal(decision.selected_amount)
    caller_value = caller_binding_values.get(binding_id)
    if caller_value is not None and Decimal(caller_value) != selected:
        raise ModeloIvaWalletReconciliationBlocked(
            "caller binding for Modelo 303 prior compensation conflicts with IVA wallet reconciliation decision"
        )
    if caller_casilla_value is not None and Decimal(caller_casilla_value) != selected:
        raise ModeloIvaWalletReconciliationBlocked(
            "caller casilla input for Modelo 303 prior compensation conflicts with IVA wallet reconciliation decision"
        )
    if backend_casilla_value is not None and Decimal(backend_casilla_value) != selected:
        raise ModeloIvaWalletReconciliationBlocked(
            "backend casilla input for Modelo 303 prior compensation conflicts with IVA wallet reconciliation decision"
        )
    from ..aggregation import CalculationSourceContext
    from ..calculations import IvaWalletDecisionSourceResolver

    resolution = IvaWalletDecisionSourceResolver(decision).resolve(
        CalculationSourceContext(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision=revision,
        )
    )
    backend_binding_values.update(resolution.binding_values)


def _require_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    supplied_decision: object,
    repository: IvaWalletDecisionRepository | None = None,
) -> object:
    if work_unit.modelo != "303":
        return supplied_decision
    persisted = _load_persisted_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
    if persisted is None:
        raise ModeloIvaWalletReconciliationBlocked(
            translated_message="application.modelo.errors.iva_wallet_not_seeded",
            suggestion="aeat app modelo iva-wallet seed --filing-year YEAR --period PERIOD --amount 0 --confirm",
        )
    if persisted != supplied_decision:
        raise ModeloIvaWalletReconciliationBlocked(
            "supplied IVA wallet reconciliation decision does not match the persisted decision"
        )
    return persisted


def _load_persisted_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    repository: IvaWalletDecisionRepository | None = None,
) -> IvaCompensationReconciliationDecision | None:
    if work_unit.modelo != "303":
        return None
    taxpayer_nif = _taxpayer_nif_for_bucket(work_unit.bucket_id)
    if taxpayer_nif is None:
        return None
    if repository is None:
        from ..calculations._observations_repository import IvaWalletDecisionRepository

        repository = IvaWalletDecisionRepository()

    return repository.load_decision(
        taxpayer_nif,
        work_unit.filing_year,
        work_unit.period,
    )


def _persisted_blocked_iva_compensation_decision_for_work_unit(
    work_unit: WorkUnit,
    *,
    repository: IvaWalletDecisionRepository | None = None,
) -> IvaCompensationReconciliationDecision | None:
    decision = _load_persisted_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
    if decision is not None and bool(decision.blocked):
        return decision
    return None


def _raise_if_persisted_iva_compensation_decision_blocks_work_unit(
    work_unit: WorkUnit,
    *,
    repository: IvaWalletDecisionRepository | None = None,
) -> None:
    decision = _persisted_blocked_iva_compensation_decision_for_work_unit(work_unit, repository=repository)
    if decision is not None:
        raise ModeloIvaWalletReconciliationBlocked(_iva_wallet_blocked_message(decision))


def _iva_wallet_blocked_message(decision: Any) -> str:
    divergence = str(decision.divergence)
    reason = str(decision.reason)
    return f"IVA wallet reconciliation is blocked for Modelo 303 ({divergence}): {reason}"


def _taxpayer_nif_for_bucket(bucket_id: str) -> str | None:
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile import UserProfileLifecycleRepository
    from ..user_profile._projections import record_to_path_values

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    value = record_to_path_values(record).get("identity.tax_id")
    if value is None or not value.strip():
        return None
    return value.strip()


def _iva_regime_for_bucket(bucket_id: str) -> str | None:
    """Return the profile's ``iva.regime`` value, or ``None`` if unset or profile absent."""
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile import UserProfileLifecycleRepository
    from ..user_profile._projections import record_to_path_values

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None
    value = record_to_path_values(record).get("iva.regime")
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


_LEDGER_PREFLIGHT_BINDING_SOURCES = frozenset(
    {
        "ledger_iva_aggregation",
        "ledger_renta_expense_aggregation",
    }
)
# IVA regimes that do not use ledger aggregation for IVA repercutido; these
# clients supply régimen-simplificado casillas (47-58) directly as manual
# inputs rather than deriving them from the transaction ledger.
_IVA_LEDGER_EXEMPT_REGIMES = frozenset({"SIMPLIFICADO"})
_ANNUAL_REGISTRY_PERIODS = frozenset(("0A",))


def _raise_if_ledger_preflight_blocks_calculation(
    *,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> None:
    if not any(binding.source in _LEDGER_PREFLIGHT_BINDING_SOURCES for binding in revision.bindings):
        return
    # Régimen simplificado clients supply casillas 47-58 as manual inputs;
    # they have no transaction ledger to satisfy the IVA aggregation preflight.
    iva_regime = _iva_regime_for_bucket(work_unit.bucket_id)
    if iva_regime in _IVA_LEDGER_EXEMPT_REGIMES:
        return
    from ..ledger import preflight_ledger_tax_readiness

    report = preflight_ledger_tax_readiness(
        bucket_id=work_unit.bucket_id,
        period=_ledger_preflight_period_for_work_unit(work_unit),
        transaction_repository=transaction_repository,
    )
    if report.ready:
        return
    first_issue = report.issues[0]
    raise ModeloAggregationBindingError(
        "ledger preflight blocks modelo calculation: "
        f"{first_issue.transaction_id} {first_issue.reason.value}: {first_issue.detail}. "
        f"Run `aeat app ledger preflight --period {report.period.raw}` before calculating."
    )


def _ledger_preflight_period_for_work_unit(work_unit: WorkUnit) -> str:
    token = work_unit.period.strip().upper()
    if token in {"1T", "2T", "3T", "4T"}:
        return f"{work_unit.filing_year}Q{token[0]}"
    if token in {"Q1", "Q2", "Q3", "Q4"}:
        return f"{work_unit.filing_year}{token}"
    if token in _ANNUAL_REGISTRY_PERIODS:
        return str(work_unit.filing_year)
    if len(token) == 2 and token.isdigit():
        return f"{work_unit.filing_year}-{token}"
    return token


def calculate_modelo_revision_from_bucket_aggregation(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[str, Decimal] | None = None,
    binding_values: Mapping[str, Decimal] | None = None,
    enum_binding_values: Mapping[str, str] | None = None,
    iva_compensation_decision: object | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[str, Decimal] | None = None,
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    borrador_snapshot_repository: Borrador100SnapshotRepository | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    clock: datetime | None = None,
) -> CalculationRevision:
    """Calculate a modelo revision using bucket-local ledger aggregation."""

    from ...domain.calculations.registry import RegistrySnapshotError
    from ..aggregation import (
        CalculationSourceContext,
        LedgerIvaAggregationSourceResolver,
        LedgerRentaExpenseAggregationSourceResolver,
        merge_source_resolutions,
    )

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(tr("application.modelo.errors.work_unit_not_found", work_unit_id=work_unit_id))
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            tr("application.modelo.errors.work_unit_discarded_cannot_calculate", work_unit_id=work_unit_id)
        )

    try:
        authority = _authority_via_resources()
        snapshot = authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        )
    except FileNotFoundError as exc:
        raise CalculationRegistryUnavailableError(
            f"registry root {_registry_root()} is missing; cannot calculate from bucket aggregation"
        ) from exc
    except RegistrySnapshotError as exc:
        raise CalculationRegistryUnavailableError(
            f"registry snapshot for modelo={work_unit.modelo!r} "
            f"year={work_unit.filing_year} period={work_unit.period!r} "
            f"could not be resolved: {exc}"
        ) from exc

    # Normalise operator-supplied casilla aliases (registry number / BOE
    # form number) to canonical ids before the source-collision and
    # bucket-merge checks compare them against registry casilla ids.
    if casilla_inputs is not None:
        casilla_inputs = _normalize_casilla_input_aliases(snapshot.revision, casilla_inputs)

    source_resolution = merge_source_resolutions(
        (
            LedgerIvaAggregationSourceResolver(transaction_repository=transaction_repository).resolve(
                CalculationSourceContext(
                    bucket_id=work_unit.bucket_id,
                    modelo=work_unit.modelo,
                    filing_year=work_unit.filing_year,
                    period=work_unit.period,
                    revision=snapshot.revision,
                )
            ),
            LedgerRentaExpenseAggregationSourceResolver(
                transaction_repository=transaction_repository,
                invoice_repository=invoice_repository,
            ).resolve(
                CalculationSourceContext(
                    bucket_id=work_unit.bucket_id,
                    modelo=work_unit.modelo,
                    filing_year=work_unit.filing_year,
                    period=work_unit.period,
                    revision=snapshot.revision,
                )
            ),
        )
    )
    _reject_caller_overrides_of_source_bindings(
        revision=snapshot.revision,
        owned_sources=frozenset(source_resolution.owned_sources),
        caller_binding_values=binding_values or {},
        caller_casilla_inputs=casilla_inputs or {},
    )
    backend_inputs = _merge_bucket_bound_inputs(
        revision=snapshot.revision,
        casilla_inputs=casilla_inputs or {},
        bound_inputs=_resolve_bound_casilla_inputs_for_available_bindings(
            snapshot.revision,
            source_resolution.binding_values,
        ),
    )
    return calculate_modelo_revision(
        work_unit_id,
        actor=actor,
        casilla_inputs=casilla_inputs or {},
        binding_values=binding_values or {},
        backend_binding_values=source_resolution.binding_values,
        backend_casilla_inputs=backend_inputs,
        iva_compensation_decision=iva_compensation_decision,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        ledger_preflight_transaction_repository=transaction_repository,
        enum_binding_values=enum_binding_values,
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=relation_values,
        source_transaction_ids=tuple(source_resolution.source_transaction_ids),
        filing_period_date=filing_period_date,
        work_unit_repository=wu_repo,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        borrador_snapshot_repository=borrador_snapshot_repository,
        detail_rows=detail_rows,
        clock=clock,
    )


def _resolve_profile_bindings_for_calculation(
    *,
    bucket_id: str,
    snapshot: RegistrySnapshot,
    caller_binding_values: Mapping[str, Decimal],
    caller_enum_binding_values: Mapping[str, str],
    borrador_result: Modelo100BorradorBindingResult,
    backend_binding_values: Mapping[str, Decimal],
) -> ProfileSourcedBindingResult:
    """Resolve ``source = "profile"`` bindings from the bucket's user profile.

    Bindings already satisfied by a higher-precedence layer (caller
    ``--binding`` / ``--enum-binding``, a consumed borrador snapshot, or
    backend bucket aggregation) are excluded so the profile only fills
    bindings nothing else provided. The profile is the substrate of
    record for taxpayer facts such as the Modelo 100 tax-residence
    CCAA; without this step the operator would have to re-type a fact
    the profile already holds.
    """

    from ..aggregation import CalculationSourceContext, ProfileSourceResolver

    caller_owned = (
        set(caller_binding_values)
        | set(caller_enum_binding_values)
        | set(borrador_result.binding_values)
        | set(borrador_result.enum_binding_values)
        | set(backend_binding_values)
    )
    resolution = ProfileSourceResolver(
        caller_binding_ids=caller_owned,
        registry_snapshot=snapshot,
    ).resolve(
        CalculationSourceContext(
            bucket_id=bucket_id,
            modelo=snapshot.modelo.id,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
            revision=snapshot.revision,
        )
    )
    return ProfileSourcedBindingResult(
        binding_values=resolution.binding_values,
        enum_binding_values=resolution.enum_binding_values,
        date_binding_values=resolution.date_binding_values,
        bindings_sourced_from_profile=tuple(
            sorted(
                set(resolution.binding_values)
                | set(resolution.enum_binding_values)
                | set(resolution.date_binding_values)
            )
        ),
    )


def _reject_binding_channel_mismatch(
    revision: ModeloRevision,
    binding_values: Mapping[str, Decimal],
    enum_binding_values: Mapping[str, str],
) -> None:
    """Refuse bindings supplied through the wrong engine channel.

    The registry runtime resolves a binding leaf from the Decimal
    ``binding_values`` channel unless a dispatch op consumes it as a
    string enum key, in which case it is read from
    ``enum_binding_values``. A caller that supplies an enum-dispatch
    binding through the Decimal channel (or vice versa) would otherwise
    get the opaque engine error ``binding ... has no supplied value``
    even though a value was provided. The Modelo 100 estimacion-directa
    modality binding is the canonical trap: it carries a ``typed_enum``
    annotation yet is consumed as a Decimal operand, so a value routed
    by ``typed_enum`` alone lands in the wrong channel. This guard
    rejects the mismatch at the binding boundary with a clear message.
    """

    enum_consumed = enum_consumed_binding_ids(revision)
    misrouted_to_decimal = sorted(set(binding_values) & enum_consumed)
    if misrouted_to_decimal:
        raise ModeloError(
            f"bindings {misrouted_to_decimal!r} are consumed by the registry as enum "
            f"dispatch keys and must be supplied through the enum-binding channel, "
            f"not as Decimal binding values"
        )
    misrouted_to_enum = sorted(set(enum_binding_values) & {b.id for b in revision.bindings} - enum_consumed)
    misrouted_to_enum = [
        binding_id for binding_id in misrouted_to_enum if _binding_is_formula_consumed(revision, binding_id)
    ]
    if misrouted_to_enum:
        raise ModeloError(
            f"bindings {misrouted_to_enum!r} are consumed by the registry as Decimal "
            f"operands and must be supplied as Decimal binding values, not through the "
            f"enum-binding channel. `aeat app modelo bindings list` reports each "
            f"binding's input_channel; a binding shown as input_channel=decimal "
            f"takes a numeric --binding KEY=VALUE even when typed_enum is set"
        )


def _binding_is_formula_consumed(revision: ModeloRevision, binding_id: str) -> bool:
    """Return whether any formula expression references ``binding_id``."""

    return any(binding_id in expression_binding_refs(formula.expression) for formula in revision.formulas)


def _resolve_borrador_bindings_for_calculation(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    borrador_snapshot_id: str | None,
    caller_binding_values: Mapping[str, Decimal],
    caller_enum_binding_values: Mapping[str, str],
    registry_snapshot: RegistrySnapshot,
    snapshot_repository: Borrador100SnapshotRepository | None,
) -> Modelo100BorradorBindingResult:
    from ..aggregation import CalculationSourceContext

    resolution = Modelo100BorradorSourceResolver(
        borrador_snapshot_id=borrador_snapshot_id,
        caller_binding_values=caller_binding_values,
        caller_enum_binding_values=caller_enum_binding_values,
        registry_snapshot=registry_snapshot,
        snapshot_repository=snapshot_repository,
    ).resolve(
        CalculationSourceContext(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision=registry_snapshot.revision,
        )
    )
    sourced = tuple(sorted(set(resolution.binding_values) | set(resolution.enum_binding_values)))
    return Modelo100BorradorBindingResult(
        borrador_snapshot_id=borrador_snapshot_id.strip() if borrador_snapshot_id else None,
        binding_values=resolution.binding_values,
        enum_binding_values=resolution.enum_binding_values,
        bindings_sourced_from_borrador=sourced,
    )


def _resolve_bound_casilla_inputs_for_available_bindings(
    revision: ModeloRevision,
    binding_values: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    resolved: dict[str, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != "bound" or casilla.binding is None:
            continue
        value = binding_values.get(casilla.binding)
        if value is not None:
            resolved[casilla.id] = value
    return resolved


def _lift_previous_filing_casilla_overrides_to_bindings(
    revision: ModeloRevision,
    casilla_inputs: Mapping[str, Decimal],
    resolved_bindings: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Promote operator ``--casilla`` overrides for ``previous_filing``-bound casillas into bindings.

    When an operator supplies ``--casilla "15=2694"`` for a casilla whose registry
    binding declares ``source = "previous_filing"``, and no upstream resolver (borrador,
    profile, ledger, or caller ``--binding``) has already populated the binding, the
    override becomes the authoritative value for that binding.

    This satisfies the engine's twin invariants enforced by ``_initial_values``:
    - The smuggle-rejection guard requires that any ``previous_filing``-bound casilla in
      ``inputs`` ALSO appears in ``binding_values`` under its binding id.
    - The consistency check requires ``inputs[casilla_id] == binding_values[binding_id]``.

    The returned dict extends ``resolved_bindings`` with the promoted entries.
    Bindings already present in ``resolved_bindings`` (from ``--binding``, borrador, or
    the profile layer) are never overwritten — the operator used the correct channel.
    """
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    promoted: dict[str, Decimal] = {}
    for casilla_id, value in casilla_inputs.items():
        casilla = casillas_by_id.get(casilla_id)
        if casilla is None or casilla.input_kind != "bound" or not casilla.binding:
            continue
        binding = bindings_by_id.get(casilla.binding)
        if binding is None or binding.source != "previous_filing":
            continue
        if casilla.binding in resolved_bindings:
            # The binding was already provided via --binding or a resolver; do not
            # override it.  The consistency check in _initial_values will surface any
            # divergence between inputs[casilla_id] and binding_values[binding_id].
            continue
        promoted[casilla.binding] = value
    return {**resolved_bindings, **promoted}


_FILING_PERIOD_ORDINALS: Mapping[str, int] = {
    "1T": 1,
    "2T": 2,
    "3T": 3,
    "4T": 4,
    "0A": 0,
    "01": 1,
    "02": 2,
    "03": 3,
    "04": 4,
    "05": 5,
    "06": 6,
    "07": 7,
    "08": 8,
    "09": 9,
    "10": 10,
    "11": 11,
    "12": 12,
    "1P": 1,
    "2P": 2,
    "3P": 3,
}
"""Numeric ordinal for every registry-native period token.

The registry formula runtime's value map is Decimal-only; a
``period_code`` casilla cannot carry the literal ``"1T"`` token.
Each work unit carries exactly one period family (a Modelo 303
work unit is quarterly or monthly, never both), so the ordinal
alone is an unambiguous numeric projection of that work unit's
period for the ``decl.periodo`` informational casilla.

The ``nP`` tokens are the Impuesto sobre Sociedades pago-fraccionado
instalment claves (Modelo 202); the ordinal mirrors the digit AEAT
expects in the ``periodo`` clave (``1P`` → ``1``, ``2P`` → ``2``,
``3P`` → ``3``).
"""


def _resolve_declaration_period_inputs(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> dict[str, Decimal]:
    """Return informational-casilla inputs sourced from work-unit metadata.

    ``decl.ejercicio`` / ``decl.periodo`` (and any other casilla
    tagged ``semantic_role`` ``filing_year`` / ``filing_period``)
    are ``informational`` casillas: AEAT requires them on the
    filed declaration, but they are neither operator-entered
    figures nor formula outputs. Their values are determined
    entirely by the work unit's ``(filing_year, period)`` axes.

    Without this resolution the engine's ``_initial_values``
    defaults every informational casilla to ``0`` — a Modelo 303
    filed with ``ejercicio``/``periodo`` of ``0`` is structurally
    invalid. The work unit is the authority for these axes, so the
    calculate path projects them onto the matching semantic-role
    casillas here, before the engine runs.
    """

    resolved: dict[str, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind != "informational":
            continue
        if casilla.semantic_role == "filing_year":
            resolved[casilla.id] = Decimal(filing_year)
        elif casilla.semantic_role == "filing_period":
            ordinal = _FILING_PERIOD_ORDINALS.get(period.strip().upper())
            if ordinal is None:
                raise ModeloError(
                    f"work-unit period {period!r} has no registry period ordinal; "
                    f"cannot resolve informational casilla {casilla.id!r}"
                )
            resolved[casilla.id] = Decimal(ordinal)
    return resolved


def _merge_bucket_bound_inputs(
    *,
    revision: ModeloRevision,
    casilla_inputs: Mapping[str, Decimal],
    bound_inputs: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    computed = sorted(
        casilla_id
        for casilla_id in bound_inputs
        if casilla_id in casillas and casillas[casilla_id].input_kind == "computed"
    )
    if computed:
        raise ModeloAggregationBindingError(
            tr("application.modelo.errors.computed_casilla_binding_conflict", computed=computed)
        )
    return dict(sorted({**bound_inputs, **casilla_inputs}.items()))


def _source_owned_binding_ids(revision: ModeloRevision, owned_sources: frozenset[str]) -> frozenset[str]:
    return frozenset(binding.id for binding in revision.bindings if binding.source in owned_sources)


def _source_owned_bound_casilla_ids(revision: ModeloRevision, owned_sources: frozenset[str]) -> frozenset[str]:
    source_owned_binding_ids = _source_owned_binding_ids(revision, owned_sources)
    return frozenset(
        casilla.id
        for casilla in revision.casillas
        if casilla.input_kind == "bound" and casilla.binding in source_owned_binding_ids
    )


def _reject_caller_overrides_of_source_bindings(
    *,
    revision: ModeloRevision,
    owned_sources: frozenset[str],
    caller_binding_values: Mapping[str, Decimal],
    caller_casilla_inputs: Mapping[str, Decimal],
) -> None:
    """Refuse caller-supplied bindings or casilla inputs that collide with
    values bucket source resolvers own.

    Bucket-aggregation calculation derives source-owned binding values
    (and the casillas bound to them) from bucket substrate. Letting a
    caller override those silently would break calculation grounding:
    the persisted revision would no longer reflect the sources it claims
    to aggregate. Both collisions are rejected before any value reaches
    the engine.
    """

    rejected_bindings = sorted(
        set(caller_binding_values).intersection(_source_owned_binding_ids(revision, owned_sources))
    )
    if rejected_bindings:
        # For the IVA compensation binding the operator should use the seed verb, not
        # a manual override, to set the prior carry-forward balance.
        seed_suggestion = (
            "aeat app modelo iva-wallet seed"
            if any("compensacion-pendiente-anteriores" in b for b in rejected_bindings)
            else None
        )
        raise ModeloAggregationBindingError(
            translated_message="errors.error.error_modelo_aggregation_binding",
            suggestion=seed_suggestion,
        )
    rejected_casillas = sorted(
        set(caller_casilla_inputs).intersection(_source_owned_bound_casilla_ids(revision, owned_sources))
    )
    if rejected_casillas:
        raise ModeloAggregationBindingError(
            f"caller casilla inputs cannot override bucket-derived source bound casillas: {rejected_casillas!r}"
        )


def list_calculation_revisions(
    *,
    work_unit_id: str | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
) -> tuple[CalculationRevision, ...]:
    """List calculation revisions, optionally filtered to one work unit.

    Results are sorted by ``(work_unit_id, created_at)`` so the
    chronological revision chain for one work unit is contiguous
    and stable across calls.
    """

    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    revisions = tuple(
        revision for revision in catalogue.values() if work_unit_id is None or revision.work_unit_id == work_unit_id
    )
    return tuple(sorted(revisions, key=lambda r: (r.work_unit_id, r.created_at)))


def get_calculation_revision(
    calculation_revision_id: str,
    *,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
) -> CalculationRevision:
    """Return one calculation revision by id, or raise."""

    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    revision = catalogue.get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            tr(
                "application.modelo.errors.calculation_revision_not_found",
                calculation_revision_id=calculation_revision_id,
            )
        )
    return revision


def mark_revision_verificado_completo(
    calculation_revision_id: str,
    *,
    actor: str,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> CalculationRevision:
    """Transition a draft revision to ``VERIFICADO_COMPLETO``.

    The revision must currently be in ``DRAFT`` state. After the
    transition the revision is immutable; subsequent calculation
    work on the same work unit must produce a new revision.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not
            currently in ``DRAFT`` state.
    """

    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    existing = catalogue.get(calculation_revision_id)
    if existing is None:
        raise CalculationRevisionNotFoundError(
            tr(
                "application.modelo.errors.calculation_revision_not_found",
                calculation_revision_id=calculation_revision_id,
            )
        )
    if existing.state is not CalculationRevisionState.BORRADOR:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{existing.state.value!r}; only DRAFT revisions can be marked verified-complete"
        )
    now = clock or datetime.now(UTC)
    verified = existing.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        }
    )
    cr_repo.save(upsert_calculation_revision(catalogue, verified))
    return verified


def _registry_root() -> Path:
    """Resolve the registry root from the packaged data tree.

    Calling :func:`aeat.core.resources.bundled_path` makes the
    resolution independent of the caller's working directory and
    keeps the editable-install and built-wheel surfaces in sync.
    """

    from ...core.resources import bundled_path

    return bundled_path("registry", "aeat")


def _authority_via_resources() -> ValidatedRegistryAuthority:
    """Return the registry authority via the central resource registry."""
    from ...core.resources import resources

    return resources().modelos.authority


def _reject_unknown_revision(*, modelo: str, revision_id: str) -> None:
    """Refuse a work-unit create that names a revision the registry does not declare.

    The work-unit id is content-addressed over ``(bucket, modelo, year,
    period, revision_id)``, so a typo or stale revision id quietly
    creates an unreachable unit (subsequent ``work calculate`` raises
    the opaque registry-snapshot miss). Catch the typo at the boundary
    with a clear listing of the valid revision ids for the modelo.
    """

    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        modelo_def = _authority_via_resources().modelo(modelo)
    except RegistrySnapshotError as exc:
        # Bubble unknown-modelo as a domain error consistent with the
        # broader create_work_unit error envelope.
        raise ModeloError(str(exc)) from exc
    if revision_id in modelo_def.revisions:
        return
    available = ", ".join(sorted(modelo_def.revisions))
    raise ModeloError(
        f"revision_id {revision_id!r} is not declared on modelo {modelo!r}. Available revisions: {available}"
    )


def _reject_unknown_period_for_revision(*, modelo: str, revision_id: str, period: str) -> None:
    """Refuse a work-unit create that names a period the revision does not declare.

    Cross-domain-continuity W02.P12.S220 (persona R7-003): M202 currently
    accepts ``--period 1T`` at create then fails calculate with
    no-revision-for-period; period validation must fire at create using
    the revision's declared period catalogue.

    The revision's ``filing_schedules`` carry the declared periods per
    period-kind (monthly / quarterly / annual / ad_hoc). The union of
    every schedule's ``periods`` tuple is the valid period set for that
    revision. An unknown period is refused with the sorted-valid list.

    Caller is expected to have already validated the modelo + revision_id
    via :func:`_reject_unknown_revision`; this helper re-loads the modelo
    definition lazily and is safe to call independently.
    """

    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        modelo_def = _authority_via_resources().modelo(modelo)
    except RegistrySnapshotError as exc:
        raise ModeloError(str(exc)) from exc
    revision = modelo_def.revisions.get(revision_id)
    if revision is None:
        return
    declared: set[str] = set()
    for schedule in revision.filing_schedules:
        declared.update(schedule.periods)
    if not declared:
        # Revisions without filing_schedules (rare; informational-only)
        # cannot validate; accept anything to preserve current behaviour.
        return
    if period in declared:
        return
    available = ", ".join(sorted(declared))
    raise ModeloError(
        f"period {period!r} is not declared on modelo {modelo!r} "
        f"revision {revision_id!r}. Available periods: {available}"
    )


def _reject_incomplete_amendment_casillas(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[str, Decimal],
) -> None:
    """Mirror the verify-modelo-revision required-manual gate on amend.

    Refuses to file a complementaria whose corrected casilla map is
    missing one or more registry-declared required-manual casillas.
    The check is identity-equivalent to the verify path's
    ``MISSING_REQUIRED_CASILLA`` finding: the corrected revision is
    the legal basis of the complementaria filing and must satisfy
    the same required-input contract that a fresh calculate → verify
    → file path satisfies.
    """

    required_optional = _required_input_casillas_for_revision(modelo=modelo, filing_year=filing_year, period=period)
    if required_optional is None:
        raise AmendmentVerificationRefusedError(
            f"registry has no snapshot for modelo={modelo!r} filing_year={filing_year} "
            f"period={period!r}; cannot verify amendment completeness"
        )
    required, _ = required_optional
    missing = sorted(casilla_id for casilla_id in required if casilla_id not in casilla_values)
    if missing:
        raise AmendmentVerificationRefusedError(
            f"amendment is incomplete: required casilla id(s) {missing!r} are not present "
            f"in the corrected map for modelo={modelo!r} filing_year={filing_year} period={period!r}"
        )


def _normalize_casilla_input_aliases(
    revision: ModeloRevision,
    casilla_inputs: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    """Resolve operator-supplied ``--casilla`` keys to canonical casilla ids.

    The ``casillas`` discovery command surfaces a ``number`` column —
    the registry number and BOE form number Spanish taxpayers read off
    the paper form. Those numbers are legitimate operator-facing
    identifiers, so a ``--casilla`` key supplied as an unambiguous
    ``number`` or ``form_number`` is normalised here to the canonical
    casilla ``id`` the calculation engine consumes. A key already equal
    to a canonical ``id`` is unchanged; an unresolvable key passes
    through verbatim so the engine still raises its unknown-casilla
    refusal. A canonical ``id`` always wins over an alias collision.
    """

    if not casilla_inputs:
        return dict(casilla_inputs)
    alias_map = input_casilla_alias_map(revision)
    return {alias_map.get(key, key): value for key, value in casilla_inputs.items()}


def _reject_unknown_override_casillas(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    overrides: Mapping[str, Decimal],
) -> None:
    """Refuse override casilla ids the registry does not declare for the modelo / year / period."""

    if not overrides:
        return

    from ...domain.calculations.registry import (
        RegistrySnapshotError,
    )

    try:
        authority = _authority_via_resources()
    except FileNotFoundError as exc:
        raise AmendmentOverrideCasillaError(
            f"registry root {_registry_root()} is missing; cannot validate amendment overrides"
        ) from exc

    try:
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period)
    except RegistrySnapshotError as exc:
        raise AmendmentOverrideCasillaError(
            f"registry has no snapshot for modelo={modelo!r} filing_year={filing_year} "
            f"period={period!r}; cannot validate amendment overrides"
        ) from exc

    known = {str(casilla.id) for casilla in snapshot.revision.casillas}
    unknown = sorted(casilla_id for casilla_id in overrides if casilla_id not in known)
    if unknown:
        raise AmendmentOverrideCasillaError(
            f"amendment overrides target casilla ids that are not declared in registry "
            f"modelo={modelo!r} filing_year={filing_year} period={period!r}: {unknown!r}"
        )


def _reject_unknown_import_casillas(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[str, Decimal],
) -> RegistrySnapshot:
    """Refuse imported casilla ids the registry does not declare and return the resolved snapshot."""

    from ...domain.calculations.registry import (
        RegistrySnapshotError,
    )

    try:
        authority = _authority_via_resources()
    except FileNotFoundError as exc:
        raise ExternalModeloImportError(
            f"registry root {_registry_root()} is missing; cannot validate imported casilla ids"
        ) from exc

    try:
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period)
    except RegistrySnapshotError as exc:
        raise ExternalModeloImportError(
            f"registry has no snapshot for modelo={modelo!r} filing_year={filing_year} "
            f"period={period!r}; cannot validate imported casilla ids"
        ) from exc

    known = {str(casilla.id) for casilla in snapshot.revision.casillas}
    unknown = sorted(casilla_id for casilla_id in casilla_values if casilla_id not in known)
    if unknown:
        raise ExternalModeloImportError(
            f"external-filing import carries casilla ids that are not declared in registry "
            f"modelo={modelo!r} filing_year={filing_year} period={period!r}: {unknown!r}"
        )
    return snapshot


def _external_filing_observations(
    *,
    casilla_values: Mapping[str, Decimal],
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build registry-grounded observations for externally imported casilla values."""

    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    return tuple(
        _casilla_observation_for(
            casilla_id=casilla_id,
            value=value,
            entry=None,
            registry_casilla=casillas_by_id.get(casilla_id),
        )
        for casilla_id, value in casilla_values.items()
    )


def _required_input_casillas_for_revision(
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """Resolve the registry's required and informational input casillas.

    Returns a tuple of (required_casilla_ids, optional_input_casilla_ids)
    drawn from the registry snapshot for the modelo / year / period.
    Returns ``None`` when no registry snapshot can be resolved (e.g.
    the modelo is not in the registry); the verifier treats this as
    a blocking finding so the operator gets a clear refusal rather
    than a silently-passed verification.

    ``required`` casillas with ``input_kind="manual"`` are the
    minimum the operator must supply. Casillas with
    ``input_kind="bound"`` or ``"computed"`` are resolved by the
    backend (bindings + formula engine); the current verify
    implementation treats them as informational because the
    bindings layer is responsible for them.
    """

    from ...domain.calculations.registry import (
        RegistrySnapshotError,
    )

    try:
        authority = _authority_via_resources()
    except FileNotFoundError:
        return None

    try:
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period)
    except RegistrySnapshotError:
        return None

    required: list[str] = []
    optional: list[str] = []
    for casilla in snapshot.revision.casillas:
        casilla_id = str(casilla.id)
        if casilla.input_kind == "manual" and casilla.required:
            required.append(casilla_id)
        elif casilla.input_kind in ("manual", "bound", "computed"):
            optional.append(casilla_id)
    return tuple(required), tuple(optional)


def _verification_predicates_for_revision(
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> tuple[VerificationPredicateDefinition, ...]:
    """Return Layer 2 predicates for the registry revision, or empty tuple.

    Resolves the same snapshot as
    ``_required_input_casillas_for_revision``; when the registry is
    unavailable the verification pipeline already blocked on Layer 1, so
    returning an empty tuple here is safe — the caller never reaches
    predicate evaluation in that case.
    """

    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = _authority_via_resources()
    except FileNotFoundError:
        return ()

    try:
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period)
    except RegistrySnapshotError:
        return ()

    return snapshot.revision.verification_predicates


def _assert_revision_content_integrity(revision: CalculationRevision) -> None:
    """Raise StoredCalculationDriftError when the revision's stored payload
    does not match its content-addressed id or has internal observation drift.

    Two checks run:

    1. Content-hash check: the ``calculation_revision_id`` is a SHA-256
       hash of ``(work_unit_id, inputs_snapshot, binding_overrides,
       casilla_values)``.  Re-deriving the hash and comparing it to the
       stored id detects tampering or corruption of the primary payload.

    2. Observation provenance cross-check: for each typed
       ``CasillaObservation`` in ``revision.observations``, the
       ``observation.value`` must match ``revision.casilla_values``
       for the same casilla.  A mismatch means the typed provenance
       envelope (which carries ``formula_id``, ``legal_refs``,
       ``source_refs``) and the flat casilla-values mapping are no
       longer consistent — either observations or casilla_values was
       mutated after creation.

    Older revisions where ``observations == ()`` skip check 2 so the
    legacy-payload path remains loadable.
    """
    expected = derive_calculation_revision_id(
        work_unit_id=revision.work_unit_id,
        inputs_snapshot=revision.inputs_snapshot,
        binding_overrides=revision.binding_overrides,
        casilla_values=revision.casilla_values,
        source_transaction_ids=revision.source_transaction_ids,
        borrador_snapshot_id=revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=revision.bindings_sourced_from_borrador,
    )
    if expected != revision.calculation_revision_id:
        raise StoredCalculationDriftError(
            f"calculation revision {revision.calculation_revision_id!r} content-address mismatch: "
            f"stored id does not match re-derived hash of its payload; "
            f"the record may have been tampered with or corrupted"
        )

    # Observation provenance cross-check (S210).
    for obs in revision.observations:
        stored = revision.casilla_values.get(obs.casilla_id)
        if stored is None:
            raise StoredCalculationDriftError(
                f"calculation revision {revision.calculation_revision_id!r} provenance drift: "
                f"observation for casilla {obs.casilla_id!r} is present but casilla_values "
                f"has no entry for it; the provenance envelope may have been tampered with"
            )
        if obs.value != stored:
            raise StoredCalculationDriftError(
                f"calculation revision {revision.calculation_revision_id!r} provenance drift: "
                f"observation value for casilla {obs.casilla_id!r} is {obs.value!r} "
                f"but casilla_values holds {stored!r}; "
                f"the record may have been tampered with or corrupted"
            )


_PREDICATE_ALL_NONZERO = _re.compile(r"^all_nonzero\(\[(?P<ids>[^\]]*)\]\)$")
_PREDICATE_ANY_NONZERO = _re.compile(r"^any_nonzero\(\[(?P<ids>[^\]]*)\]\)$")
_PREDICATE_CAP_LE_WHEN_POSITIVE = _re.compile(
    r"^cap_le_when_positive\(\[(?P<ids>[^\]]*)\]\)$"
)
# implies_nonzero(["antecedent_id", "consequent_id"]) — material implication
# with a strictly-positive antecedent test: predicate holds iff antecedent
# is <= 0 OR consequent is non-zero. Authored for AEAT cuota-mínima
# invariants of the shape "cuando C01 sea positivo, C07 debe ser distinta
# de cero" (M131 EO cuota mínima, M130/M303 régimen simplificado analogues).
_PREDICATE_IMPLIES_NONZERO = _re.compile(
    r"^implies_nonzero\(\[(?P<ids>[^\]]*)\]\)$"
)
# advisory_when_ratio_ge(["numerator_id", "denominator_id", "threshold"]) —
# fires a WARNING-severity ADVISORY finding when numerator/denominator >= threshold
# and denominator > 0. Used for Art. 110.3.b RIRPF M130 high-retention exemption.
_PREDICATE_ADVISORY_WHEN_RATIO_GE = _re.compile(
    r'^advisory_when_ratio_ge\(\["(?P<num>[^"]+)",\s*"(?P<den>[^"]+)",\s*"(?P<thr>[^"]+)"\]\)$'
)


def _parse_predicate_casilla_ids(ids_fragment: str) -> list[str]:
    """Parse the comma-separated quoted-id list from a predicate expression."""
    ids: list[str] = []
    for token in ids_fragment.split(","):
        token = token.strip().strip('"').strip("'")
        if token:
            ids.append(token)
    return ids


def _evaluate_predicate_expression(
    expression: str,
    casilla_values: Mapping[str, Decimal],
) -> bool:
    """Return True when the predicate holds, False when it is violated.

    Supports the DSL operators registered in
    :data:`aeat.domain.calculations.registry._schema.KNOWN_VERIFICATION_PREDICATE_OPERATORS`:

    - ``all_nonzero(["id1", "id2", ...])`` — all ids must have a non-zero value.
    - ``any_nonzero(["id1", "id2", ...])`` — at least one id must have a non-zero value.
    - ``cap_le_when_positive(["limited_id", "ceiling_id"])`` — when the ceiling
      casilla is strictly positive, the limited casilla MUST NOT exceed it.
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — material
      implication with strictly-positive antecedent: predicate holds iff
      antecedent <= 0 OR consequent != 0.

    An expression that does not match any registered pattern is treated as
    holding (i.e. unknown predicates do not block the operator). The
    authoring-time validator in
    :mod:`aeat.domain.calculations.registry._validate_surfaces` is the gate
    against typos reaching this branch.
    """
    expr = expression.strip()

    m = _PREDICATE_ALL_NONZERO.match(expr)
    if m:
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        return all(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in ids)

    m = _PREDICATE_ANY_NONZERO.match(expr)
    if m:
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        return any(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in ids)

    m = _PREDICATE_CAP_LE_WHEN_POSITIVE.match(expr)
    if m:
        # cap_le_when_positive(["limited_id", "ceiling_id"]) — when the
        # ceiling casilla is strictly positive, the limited casilla value
        # MUST NOT exceed the ceiling. P08.S47/S48: enforces AEAT cap rules
        # like Modelo 131 C11 ≤ C10 (and Modelo 130 C15 ≤ C14) "en ningún
        # caso podrá figurar... un importe superior a la cantidad positiva
        # consignada".
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        if len(ids) != 2:
            return True
        limited_id, ceiling_id = ids[0], ids[1]
        ceiling = casilla_values.get(ceiling_id, Decimal(0))
        if ceiling <= Decimal(0):
            return True
        limited = casilla_values.get(limited_id, Decimal(0))
        return limited <= ceiling

    m = _PREDICATE_IMPLIES_NONZERO.match(expr)
    if m:
        # implies_nonzero(["antecedent_id", "consequent_id"]) — material
        # implication "antecedent strictly positive → consequent non-zero".
        # Predicate holds (returns True) when:
        #   - the expression is malformed (defensive — same shape as
        #     cap_le_when_positive),
        #   - the antecedent is <= 0 (implication trivially holds with
        #     non-positive antecedent — mirrors AEAT phrasing "cuando C01
        #     sea positivo"),
        #   - or the consequent is non-zero.
        # The violation case (returns False) is "antecedent strictly
        # positive AND consequent == 0". A missing consequent reads as
        # Decimal(0) via the .get default — same convention as the other
        # operators.
        ids = _parse_predicate_casilla_ids(m.group("ids"))
        if len(ids) != 2:
            return True
        antecedent_id, consequent_id = ids[0], ids[1]
        antecedent = casilla_values.get(antecedent_id, Decimal(0))
        if antecedent <= Decimal(0):
            return True
        consequent = casilla_values.get(consequent_id, Decimal(0))
        return consequent != Decimal(0)

    return True


def _resolve_m210_rate(
    profile: TaxpayerProfile,
    tipo_renta: str,
    year: int,
    snapshot: RegistrySnapshot,
) -> tuple[Decimal | None, list[ModeloVerificationFinding]]:
    """Resolve the M210 rate for (profile, tipo_renta, year).

    Returns a (rate, findings) pair. The rate is the Decimal per TRLIRNR
    Art 25 baseline OR the Convenio override when the profile declares a
    treaty country. Returns ``(None, [finding])`` and emits a BLOCKING
    ``ModeloVerificationFinding`` when the Convenio row is missing or
    carries the ``NOT_YET_AUTHORED`` sentinel per m210-irnr-full-engine
    ADR §D2.4. Returns ``(None, [])`` defensively when the baseline row
    for ``tipo_renta`` is absent — that condition indicates a registry-
    load coherence issue, not an operator-actionable filing gap.

    The treaty-country signal comes from
    ``profile.country_of_fiscal_residence``: a non-None value combined
    with ``profile.fiscal_residency == NON_RESIDENT_IRNR`` is the IRNR
    treaty-overlay activation surface; the ``convenio_aplicable``
    property already derives the BOE treaty reference from that field.
    """
    # Build the (cc, tipo_renta) -> ConvenioRateRow lookup dict from
    # the snapshot's parameter rows at function entry. O(N) per call
    # is acceptable for Phase 1 with three rows; the cache-at-load-time
    # optimization is a Phase 2 deferral.
    baseline_param = None
    convenio_param = None
    for parameter in snapshot.revision.parameters:
        if parameter.id == "m210-tipo-gravamen-2025":
            baseline_param = parameter
        elif parameter.id == "m210-convenio-rates":
            convenio_param = parameter

    if baseline_param is None:
        return None, []

    baseline_rate: Decimal | None = None
    for entry in baseline_param.keyed_brackets:
        if entry.key == tipo_renta and entry.valid_from.year <= year and (
            entry.valid_to is None or entry.valid_to.year >= year
        ):
            try:
                baseline_rate = Decimal(entry.value)
            except (ArithmeticError, ValueError):
                return None, []
            break
    if baseline_rate is None:
        return None, []

    treaty_country = profile.country_of_fiscal_residence
    if treaty_country is None:
        return baseline_rate, []

    cc = treaty_country.upper()

    convenio_lookup: dict[tuple[str, str], ConvenioRateRow] = {}
    if convenio_param is not None:
        for row in convenio_param.convenio_rates:
            if row.valid_from.year <= year and (
                row.valid_to is None or row.valid_to.year >= year
            ):
                convenio_lookup[(row.country_code, row.tipo_renta)] = row

    matched_row = convenio_lookup.get((cc, tipo_renta))
    legal_refs: tuple[str, ...] = (
        tuple(str(r) for r in convenio_param.legal_refs) if convenio_param is not None else ()
    )
    source_refs: tuple[str, ...] = (
        tuple(str(r) for r in convenio_param.source_refs) if convenio_param is not None else ()
    )

    if matched_row is None:
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message=(
                f"M210 Convenio rate row missing for country={cc!r} "
                f"tipo_renta={tipo_renta!r} year={year}; "
                "predicate 'm210-convenio-rate-missing' fires"
            ),
            next_action=tr(
                "application.modelo.findings.m210_convenio_rate_missing.next_action",
                cc=cc,
                tipo_renta=tipo_renta,
            ),
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
        return None, [finding]

    if matched_row.rate == "NOT_YET_AUTHORED":
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message=(
                f"M210 Convenio rate row for country={cc!r} "
                f"tipo_renta={tipo_renta!r} year={year} carries the "
                "NOT_YET_AUTHORED placeholder; predicate "
                "'m210-convenio-rate-not-yet-authored' fires"
            ),
            next_action=tr(
                "application.modelo.findings.m210_convenio_rate_not_yet_authored.next_action",
                cc=cc,
                tipo_renta=tipo_renta,
            ),
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
        return None, [finding]

    return Decimal(matched_row.rate), []


def _evaluate_advisory_predicate_fires(
    expression: str,
    casilla_values: Mapping[str, Decimal],
) -> bool:
    """Return True when an advisory predicate's condition is met (i.e. advisory should fire).

    Supports:

    - ``advisory_when_ratio_ge(["num_id", "den_id", "threshold"])`` — fires when
      num/den >= threshold and den > 0. Art. 110.3.b RIRPF: exempt from M130
      when retenciones_acumuladas / rendimientos_brutos >= 0.70.
    """
    expr = expression.strip()
    m = _PREDICATE_ADVISORY_WHEN_RATIO_GE.match(expr)
    if m:
        num_id = m.group("num")
        den_id = m.group("den")
        thr_str = m.group("thr")
        den = casilla_values.get(den_id, Decimal(0))
        if den <= Decimal(0):
            return False
        num = casilla_values.get(num_id, Decimal(0))
        try:
            threshold = Decimal(thr_str)
        except Exception:
            return False
        return (num / den) >= threshold
    return False


def _evaluate_verification_predicates(
    predicates: tuple[VerificationPredicateDefinition, ...],
    casilla_values: Mapping[str, Decimal],
) -> list[ModeloVerificationFinding]:
    """Evaluate Layer 2 cross-casilla predicates; return findings for violations or advisories."""
    if not predicates:
        return []

    findings: list[ModeloVerificationFinding] = []
    for predicate in predicates:
        if predicate.finding_kind == "ADVISORY":
            # ADVISORY predicates fire a WARNING finding when their condition IS met
            # (affirmative logic — opposite of BLOCKING_RULE predicates).
            if _evaluate_advisory_predicate_fires(predicate.expression, casilla_values):
                advisory_key = f"application.modelo.findings.{predicate.predicate_id.replace('-', '_')}"
                findings.append(
                    ModeloVerificationFinding(
                        kind=ModeloVerificationFindingKind.ADVISORY,
                        severity=ModeloVerificationFindingSeverity.WARNING,
                        message=tr(advisory_key),
                        legal_refs=tuple(str(r) for r in predicate.legal_refs),
                    )
                )
        else:
            if not _evaluate_predicate_expression(predicate.expression, casilla_values):
                findings.append(
                    ModeloVerificationFinding(
                        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                        severity=ModeloVerificationFindingSeverity.BLOCKING,
                        message=(f"cross-casilla invariant {predicate.predicate_id!r} violated: {predicate.expression}"),
                        next_action=(
                            f"Ensure all casillas required by predicate "
                            f"{predicate.predicate_id!r} are non-zero before verifying."
                        ),
                        legal_refs=tuple(str(r) for r in predicate.legal_refs),
                    )
                )
    return findings


def verify_modelo_revision(
    calculation_revision_id: str,
    *,
    actor: str,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    verification_repository: VerificationReportCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
) -> VerificationReport:
    """Evaluate a draft revision against the four-layer verified-complete gate.

    The gate is described fully in the package docstring
    (:mod:`aeat.application.modelo`). This function is the implementation
    entry point.

    Pipeline:

    1. **State machine** -- load the revision; it must be in ``BORRADOR``
       (DRAFT) state. Any other state raises
       :exc:`CalculationRevisionStateError`.
    2. **Registry snapshot** -- resolve the snapshot for the parent work
       unit's ``(modelo, filing_year, period)``. On failure, emit a
       BLOCKING finding and refuse the transition immediately.
    3. **Layer 1 — required-input gate** -- for each casilla declared
       ``required = true`` and ``input_kind = "manual"`` in the registry,
       check that the revision's ``casilla_values`` contains a value.
       Missing entries produce
       :attr:`~aeat.domain.modelos._verification_report.ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA`
       findings and set ``completeness_status`` to ``INCOMPLETE``.
    4. **Layer 2 — cross-casilla predicate gate** -- evaluate each
       :class:`~aeat.domain.calculations.registry.VerificationPredicateDefinition`
       from the snapshot against the stored ``casilla_values``.  A failing
       predicate produces a
       :attr:`~aeat.domain.modelos._verification_report.ModeloVerificationFindingKind.BLOCKING_RULE`
       finding.
    5. **Provenance re-validation** -- call
       :func:`_assert_revision_content_integrity` to re-derive the SHA-256
       content address and check that each ``CasillaObservation.value``
       matches ``casilla_values`` for the same casilla.  Either mismatch
       raises :exc:`StoredCalculationDriftError`.
    6. **Workflow engine gate** -- when layers 1-3 produce zero blocking
       findings, run the WorkflowEngine-owned preflight with
       ``WorkflowPurpose.VERIFY`` before mutating state.  This gate
       validates the draft against the registry but is independent of the
       AEAT filing calendar.
    7. **Persist** -- write the :class:`~aeat.domain.modelos._verification_report.ModeloVerificationReport`
       to the verification-report catalogue.  Failed attempts are persisted
       so the audit trail records why the transition was refused.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is absent.
        CalculationRevisionStateError: When the revision is not in BORRADOR
            state.  Re-verifying a verified-complete or filed revision is
            rejected; the operator must produce a fresh calculation revision
            (which lands as a new draft).
        StoredCalculationDriftError: When the content-address or observation
            provenance check fails, indicating storage corruption or
            tampering.
        ModeloWorkflowGateError: When the workflow preflight gate aborts
            before the verified-complete transition.
    """

    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    run_repo = WorkflowRunRepository(objects=bv_repo.secure_object_repository)

    revisions = cr_repo.load()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(
            tr(
                "application.modelo.errors.calculation_revision_not_found",
                calculation_revision_id=calculation_revision_id,
            )
        )
    if target.state is not CalculationRevisionState.BORRADOR:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{target.state.value!r}; only DRAFT revisions can be verified"
        )

    _assert_revision_content_integrity(target)

    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}"
        )

    findings, resolved_casillas, missing_required = _collect_revision_verification_findings(
        work_unit=work_unit,
        target=target,
    )
    blocked_iva_wallet_decision = _persisted_blocked_iva_compensation_decision_for_work_unit(
        work_unit,
        repository=iva_compensation_decision_repository,
    )
    if blocked_iva_wallet_decision is not None:
        findings.append(_iva_wallet_blocking_verification_finding(blocked_iva_wallet_decision))
    completeness, granted = _classify_verification_outcome(
        findings=findings,
        missing_required=missing_required,
    )

    now = clock or datetime.now(UTC)
    report_id = derive_verification_report_id(
        calculation_revision_id=calculation_revision_id,
        run_at=now,
        verified_by=actor.strip(),
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=calculation_revision_id,
        completeness_status=completeness,
        findings=tuple(findings),
        resolved_casillas=tuple(resolved_casillas),
        missing_required_casillas=tuple(missing_required),
        run_at=now,
        verified_by=actor.strip(),
        granted_verificado_completo=granted,
    )

    if granted:
        gate_engine = workflow_engine or _build_revision_workflow_engine(
            revision=target,
            work_unit=work_unit,
            profile=workflow_profile,
            actor=actor.strip(),
            clock=now,
            settings=settings,
        )
        _run_revision_workflow_gate(
            engine=gate_engine,
            profile=workflow_profile,
            work_unit=work_unit,
            today=now.date(),
            runs_dir=workflow_runs_dir,
            run_repository=run_repo,
            purpose=WorkflowPurpose.VERIFY,
        )

    # Persist the report regardless of outcome — failed attempts
    # are part of the audit trail.
    vr_repo.save(upsert_verification_report(vr_repo.load(), report))

    if granted:
        verified = target.model_copy(
            update={
                "state": CalculationRevisionState.VERIFICADO_COMPLETO,
                "verified_at": now,
                "verified_by": actor.strip(),
                "updated_at": now,
            }
        )
        cr_repo.save(upsert_calculation_revision(revisions, verified))

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=work_unit.bucket_id,
        event_type=(
            BucketEventType.MODELO_VERIFICATION_PASSED if granted else BucketEventType.MODELO_VERIFICATION_REFUSED
        ),
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.VERIFICATION_REPORT,
        object_id=report_id,
        payload={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": target.work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "completeness_status": completeness.value,
            "finding_count": str(len(findings)),
            "missing_required_count": str(len(missing_required)),
        },
    )

    return report


def _collect_revision_verification_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
) -> tuple[list[ModeloVerificationFinding], list[str], list[str]]:
    """Build the verification finding list for one calculation revision.

    Returns ``(findings, resolved_casillas, missing_required)``. A
    revision whose ``(modelo, year, period)`` triple does not resolve
    against the registry yields a single BLOCKING_RULE finding and
    empty resolved/missing lists — there is no per-casilla check to
    perform without a registry snapshot.

    With a snapshot present, the operator-supplied
    ``inputs_snapshot`` keys are compared against the registry's
    required-input casilla set. Each missing required casilla
    produces a MISSING_REQUIRED_CASILLA finding plus an entry in the
    missing-required list; each present required casilla lands in
    the resolved-casillas list.
    """
    findings: list[ModeloVerificationFinding] = []
    resolved_casillas: list[str] = []
    missing_required: list[str] = []

    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = _authority_via_resources()
        snapshot = authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        )
    except (FileNotFoundError, RegistrySnapshotError):
        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                message=(
                    f"registry snapshot for modelo={work_unit.modelo!r} "
                    f"year={work_unit.filing_year} period={work_unit.period!r} "
                    f"could not be resolved"
                ),
                next_action="aeat app registry verify",
            )
        )
        return findings, resolved_casillas, missing_required

    revision_keys = set(target.inputs_snapshot)
    for casilla in snapshot.revision.casillas:
        casilla_id = str(casilla.id)
        if casilla.input_kind == "manual" and casilla.required:
            if casilla_id in revision_keys:
                resolved_casillas.append(casilla_id)
            else:
                missing_required.append(casilla_id)
                findings.append(
                    _missing_required_casilla_finding(
                        casilla_id,
                        target.work_unit_id,
                        casilla_def=casilla,
                    )
                )

    # Layer 2: cross-casilla predicate gate.
    findings.extend(
        _evaluate_verification_predicates(
            snapshot.revision.verification_predicates,
            target.casilla_values,
        )
    )

    # Advisory: DT 12ª LIRPF — warn when a large trabajo income (0003 > 20 000)
    # is present but the trabajo reducción slot (0011) is zero / absent.
    # This heuristic surfaces the DT_12A_REDUCCION_POSSIBLE advisory so
    # retirees do not silently lose the 40% reducción for pre-2007 aportaciones.
    dt12_finding = _dt12_reduccion_advisory_finding(snapshot.revision, target.casilla_values)
    if dt12_finding is not None:
        findings.append(dt12_finding)

    return findings, resolved_casillas, missing_required


_DT12_TRABAJO_INGRESO_ROLE = "irpf_rendimiento_trabajo_importe_integro_dinerario"
_DT12_TRABAJO_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion"
#: Heuristic threshold above which DT 12ª advisory fires (large lump-sum pension).
_DT12_LARGE_TRABAJO_THRESHOLD = Decimal("20000")


def _dt12_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[str, Decimal],
) -> ModeloVerificationFinding | None:
    """Return a DT_12A_REDUCCION_POSSIBLE WARNING when a large trabajo income is
    present but no trabajo reducción has been declared.

    The check is advisory only (WARNING severity); it does not block VERIFICADO_COMPLETO.
    Heuristic: casilla with semantic_role ``irpf_rendimiento_trabajo_importe_integro_dinerario``
    value > 20 000 AND casilla with role ``irpf_rendimiento_trabajo_reduccion`` is zero/absent.
    Returns ``None`` when the advisory does not apply or when the snapshot revision
    does not carry the required semantic roles (non-M100 modelos).
    """

    ingreso_id: str | None = None
    reduccion_id: str | None = None
    for casilla in getattr(revision, "casillas", ()):
        role = getattr(casilla, "semantic_role", None)
        if role == _DT12_TRABAJO_INGRESO_ROLE:
            ingreso_id = str(casilla.id)
        elif role == _DT12_TRABAJO_REDUCCION_ROLE:
            reduccion_id = str(casilla.id)

    if ingreso_id is None or reduccion_id is None:
        return None

    ingreso_value = casilla_values.get(ingreso_id, Decimal(0))
    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))

    if ingreso_value > _DT12_LARGE_TRABAJO_THRESHOLD and reduccion_value == Decimal(0):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message=(
                f"DT_12A_REDUCCION_POSSIBLE: casilla {ingreso_id} = {ingreso_value} "
                f"but casilla {reduccion_id} (reducción trabajo) is zero. "
                f"If this income includes a plan-de-pensiones capital rescate with "
                f"pre-31-Dec-2006 aportaciones, a 40%% DT 12ª LIRPF reducción may apply."
            ),
            next_action=(
                "Supply --rescate-plan-pensiones-capital IMPORTE "
                "--rescate-plan-pensiones-aportaciones-pre-2007 IMPORTE "
                "--rescate-plan-pensiones-aportaciones-totales IMPORTE "
                "to aeat app modelo work calculate to auto-inject the DT 12ª reducción "
                "into casilla 0011 (ley-35-2006:dt-12)."
            ),
            legal_refs=("ley-35-2006:dt-12",),
        )
    return None


def _missing_required_casilla_finding(
    casilla_id: str,
    work_unit_id: str,
    *,
    casilla_def: CasillaDefinition | None = None,
) -> ModeloVerificationFinding:
    legal_refs: tuple[str, ...] = tuple(str(r) for r in casilla_def.legal_refs) if casilla_def is not None else ()
    source_refs: tuple[str, ...] = tuple(str(r) for r in casilla_def.source_refs) if casilla_def is not None else ()
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=casilla_id,
        message=(f"required casilla {casilla_id!r} is not present in the calculation revision's inputs_snapshot"),
        next_action=(f"aeat app modelo work calculate {work_unit_id} --casilla {casilla_id}=VALUE"),
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _iva_wallet_blocking_verification_finding(decision: object) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message=_iva_wallet_blocked_message(decision),
        next_action="Review the IVA wallet reconciliation decision before verifying or exporting this Modelo 303.",
    )


def _classify_verification_outcome(
    *,
    findings: list[ModeloVerificationFinding],
    missing_required: list[str],
) -> tuple[VerificationCompletenessStatus, bool]:
    """Compute the completeness status + granted flag from finding shape.

    With no BLOCKING finding, the report is COMPLETE and the
    verified-complete transition is granted. With at least one
    BLOCKING_RULE finding, the report is BLOCKED. With BLOCKING
    findings that are exclusively MISSING_REQUIRED_CASILLA, the
    report is INCOMPLETE so the operator sees that completing the
    inputs unblocks the transition.
    """
    has_blocking = any(f.severity is ModeloVerificationFindingSeverity.BLOCKING for f in findings)
    if not has_blocking:
        return VerificationCompletenessStatus.COMPLETE, True
    has_blocking_rule = any(f.kind is ModeloVerificationFindingKind.BLOCKING_RULE for f in findings)
    if missing_required and not has_blocking_rule:
        return VerificationCompletenessStatus.INCOMPLETE, False
    return VerificationCompletenessStatus.BLOCKED, False


def _load_work_unit_for_calculation(work_units, *, work_unit_id: str):  # type: ignore[no-untyped-def]
    """Load a work unit by id, rejecting missing ids and DISCARDED state.

    Returns the work unit. Raises :class:`WorkUnitNotFoundError`
    when the id is absent and :class:`WorkUnitMutationRefusedError`
    when the work unit is in DISCARDED state — a discarded work
    unit cannot accept a new calculation revision.
    """
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(tr("application.modelo.errors.work_unit_not_found", work_unit_id=work_unit_id))
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            tr("application.modelo.errors.work_unit_discarded_cannot_calculate", work_unit_id=work_unit_id)
        )
    return work_unit


def _resolve_registry_snapshot_for_work_unit(work_unit):  # type: ignore[no-untyped-def]
    """Resolve the registry snapshot for ``(modelo, filing_year, period)``.

    Both failure modes (registry root missing on disk, or the
    authority refusing the (modelo, year, period) triple) re-raise
    as :class:`CalculationRegistryUnavailableError` so the caller
    sees one typed envelope regardless of which boundary refused.
    """
    from ...domain.calculations.registry import RegistrySnapshotError

    try:
        authority = _authority_via_resources()
    except FileNotFoundError as exc:
        raise CalculationRegistryUnavailableError(
            f"registry root {_registry_root()} is missing; cannot calculate"
        ) from exc
    try:
        return authority.snapshot(
            work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        )
    except RegistrySnapshotError as exc:
        raise CalculationRegistryUnavailableError(
            f"registry snapshot for modelo={work_unit.modelo!r} "
            f"year={work_unit.filing_year} period={work_unit.period!r} "
            f"could not be resolved: {exc}"
        ) from exc


def _build_typed_observations(
    *, engine_result: RegistryCalculationResult, snapshot: RegistrySnapshot
) -> tuple[CasillaObservation, ...]:
    """Build a typed CasillaObservation tuple for every casilla in the engine result.

    Computed casillas carry their full formula provenance from the
    engine entry; non-computed (input + bound) casillas pull their
    legal_refs / source_refs from the registry casilla definition.
    Building observations purely from ``engine_result.entries``
    would drop grounding for every input and bound casilla — the
    audit surface depends on the full chain.

    Every casilla in ``engine_result.values`` must be declared on the
    snapshot revision. A casilla absent from
    ``snapshot.revision.casillas`` raises
    :exc:`CasillaProvenanceMissingError` rather than yielding an
    observation with empty legal provenance.
    """
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    entries_by_target = {entry.target: entry for entry in engine_result.entries}
    return tuple(
        _casilla_observation_for(
            casilla_id=casilla_id,
            value=value,
            entry=entries_by_target.get(casilla_id),
            registry_casilla=casillas_by_id.get(casilla_id),
        )
        for casilla_id, value in engine_result.values.items()
    )


def _casilla_observation_for(
    *,
    casilla_id: str,
    value: Decimal,
    entry: RegistryCalculationEntry | None,
    registry_casilla: CasillaDefinition | None,
) -> CasillaObservation:
    """Project one casilla into a :class:`CasillaObservation` with full provenance."""
    if entry is not None:
        return CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            formula_id=entry.formula_id,
            operand_refs=entry.operand_refs,
            operand_values=entry.operand_values,
            legal_refs=entry.legal_refs,
            source_refs=entry.source_refs,
        )
    if registry_casilla is None:
        raise CasillaProvenanceMissingError(
            f"casilla {casilla_id!r} is present in the engine result but absent "
            f"from the registry snapshot revision; it has no legal_refs / "
            f"source_refs definition and cannot be projected to a "
            f"CasillaObservation without erasing legal provenance"
        )
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        formula_id=None,
        operand_refs=(),
        operand_values=(),
        legal_refs=registry_casilla.legal_refs,
        source_refs=registry_casilla.source_refs,
    )


def _amendment_observations(
    *,
    corrected_values: Mapping[str, Decimal],
    overrides: Mapping[str, Decimal],
    baseline_revision: CalculationRevision,
    snapshot: RegistrySnapshot,
) -> tuple[CasillaObservation, ...]:
    """Build typed observations for an amendment revision.

    An amendment is an operator-corrected value set, not an engine
    recomputation: a casilla the operator did not override keeps the
    baseline revision's observation verbatim (value and full formula
    provenance); an overridden casilla gets a fresh observation
    carrying the corrected value and the registry casilla's
    ``legal_refs`` / ``source_refs`` (an operator override means the
    casilla is no longer a formula output, so formula provenance is
    dropped). Building the amendment without observations would discard
    all regulatory grounding from the persisted revision and the CLI
    emit — the audit surface depends on the full chain.

    Every casilla in ``corrected_values`` must be declared on the
    snapshot revision, mirroring :func:`_build_typed_observations`.
    """

    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    baseline_by_id = {obs.casilla_id: obs for obs in baseline_revision.observations}
    observations: list[CasillaObservation] = []
    for casilla_id, value in corrected_values.items():
        if casilla_id not in overrides:
            carried = baseline_by_id.get(casilla_id)
            if carried is not None:
                observations.append(carried)
                continue
        registry_casilla = casillas_by_id.get(casilla_id)
        if registry_casilla is None:
            raise CasillaProvenanceMissingError(
                f"casilla {casilla_id!r} is present in the amendment's corrected "
                f"values but absent from the registry snapshot revision; it has "
                f"no legal_refs / source_refs definition and cannot be projected "
                f"to a CasillaObservation without erasing legal provenance"
            )
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                formula_id=None,
                operand_refs=(),
                operand_values=(),
                legal_refs=registry_casilla.legal_refs,
                source_refs=registry_casilla.source_refs,
            )
        )
    return tuple(observations)


def file_modelo_revision(
    calculation_revision_id: str,
    *,
    actor: str,
    workflow_profile: TaxpayerProfile,
    notes: str | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    filing_repository: ModeloRecordCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    workflow_engine: WorkflowEngine | None = None,
    workflow_runs_dir: Path | None = None,
    settings: Settings | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """File a verified-complete revision as the current filed answer.

    State transitions performed atomically (from the caller's
    perspective — each repository save is sequenced):

    1. Verify the revision is in ``VERIFICADO_COMPLETO`` state.
    2. Run the workflow gate for the revision's modelo and period.
    3. Look up any existing current filing record for the same
       (bucket, modelo, year, period) tuple.
    4. If a prior current filing exists:
        * mark the prior filing record ``SUPERSEDED`` with
          ``superseded_at`` and ``superseded_by_filing_record_id``;
        * transition the prior filed calculation revision from
          ``FILED`` to ``FILED_SUPERSEDED``.
    5. Create the new filing record with status ``CURRENT``.
    6. Transition the target calculation revision from
       ``VERIFICADO_COMPLETO`` to ``FILED``.
    7. Advance the work unit's ``filed_calculation_revision_id``
       and ``current_filing_record_id`` pointers.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not in
            ``VERIFICADO_COMPLETO`` state.
        WorkUnitNotFoundError: When the revision's parent work
            unit cannot be loaded.
        ModeloWorkflowGateError: When the workflow/preflight gate
            aborts before filing-state mutation.
    """

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    run_repo = WorkflowRunRepository(objects=bv_repo.secure_object_repository)

    revisions = cr_repo.load()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(
            tr(
                "application.modelo.errors.calculation_revision_not_found",
                calculation_revision_id=calculation_revision_id,
            )
        )
    if target.state is not CalculationRevisionState.VERIFICADO_COMPLETO:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{target.state.value!r}; only VERIFICADO_COMPLETO revisions can be filed"
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}"
        )
    _raise_if_persisted_iva_compensation_decision_blocks_work_unit(
        work_unit,
        repository=iva_compensation_decision_repository,
    )

    now = clock or datetime.now(UTC)
    gate_engine = workflow_engine or _build_revision_workflow_engine(
        revision=target,
        work_unit=work_unit,
        profile=workflow_profile,
        actor=actor.strip(),
        clock=now,
        settings=settings,
    )
    _run_revision_workflow_gate(
        engine=gate_engine,
        profile=workflow_profile,
        work_unit=work_unit,
        today=now.date(),
        runs_dir=workflow_runs_dir,
        run_repository=run_repo,
    )

    new_filing_id = derive_filing_record_id(
        work_unit_id=target.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    filing_catalogue = fr_repo.load()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    # 1. Build new current filing record.
    new_filing = ModeloRecord(
        filing_record_id=new_filing_id,
        work_unit_id=target.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=notes.strip() if notes else None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
    )

    # 2. Supersede prior filing record if present.
    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        superseded_prior = prior_current.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
            }
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, superseded_prior)

        # Transition prior filed calculation revision to FILED_SUPERSEDED.
        prior_revision = revisions.get(prior_current.calculation_revision_id)
        if prior_revision is not None and prior_revision.state is CalculationRevisionState.PRESENTADO:
            superseded_revision = prior_revision.model_copy(
                update={
                    "state": CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
                    "superseded_at": now,
                    "updated_at": now,
                }
            )
            revisions = upsert_calculation_revision(revisions, superseded_revision)

    # 3. Insert new filing record + transition target revision to FILED.
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)
    filed_target = target.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": now,
            "filed_by": actor.strip(),
            "updated_at": now,
        }
    )
    revisions = upsert_calculation_revision(revisions, filed_target)

    # 4. Persist (catalogue saves are sequenced).
    cr_repo.save(revisions)
    fr_repo.save(updated_filing_catalogue)

    # 5. Advance work-unit pointers.
    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "filed_calculation_revision_id": calculation_revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                }
            ),
        )
    )

    # 6. Emit bucket events: one supersession event per prior filing
    # (if any), then the new modelo.filed event.
    if prior_current is not None:
        _emit_bucket_event(
            repository=bv_repo,
            bucket_id=work_unit.bucket_id,
            event_type=BucketEventType.MODELO_FILED_SUPERSEDED,
            occurred_at=now,
            actor=actor,
            object_type=BucketEventObjectType.FILING_RECORD,
            object_id=prior_current.filing_record_id,
            payload={
                "superseded_by_filing_record_id": new_filing_id,
                "calculation_revision_id": prior_current.calculation_revision_id,
                "modelo": work_unit.modelo,
                "filing_year": str(work_unit.filing_year),
                "period": work_unit.period,
            },
        )

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": target.work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "supersedes_filing_record_id": (prior_current.filing_record_id if prior_current is not None else ""),
        },
    )

    return new_filing


def list_filing_records(
    *,
    bucket_id: str | None = None,
    include_superseded: bool = False,
    filing_repository: ModeloRecordCatalogueRepository | None = None,
) -> tuple[ModeloRecord, ...]:
    """List filing records, optionally filtered to a bucket.

    Superseded records are excluded unless ``include_superseded``
    is true. Results are sorted by ``(bucket_id, filing_year,
    modelo, period, filed_at)``.
    """

    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    catalogue = fr_repo.load()
    records = tuple(
        record
        for record in catalogue.values()
        if (bucket_id is None or record.bucket_id == bucket_id)
        and (include_superseded or record.status is ModeloRecordStatus.VIGENTE)
    )
    return tuple(
        sorted(
            records,
            key=lambda r: (r.bucket_id, r.filing_year, str(r.modelo), r.period, r.filed_at),
        )
    )


def get_filing_record(
    filing_record_id: str,
    *,
    filing_repository: ModeloRecordCatalogueRepository | None = None,
) -> ModeloRecord:
    """Return one filing record by id, or raise."""

    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    catalogue = fr_repo.load()
    record = catalogue.get(filing_record_id)
    if record is None:
        raise ModeloRecordNotFoundError(
            tr("application.modelo.errors.filing_record_not_found", filing_record_id=filing_record_id)
        )
    return record


def list_verification_reports(
    *,
    calculation_revision_id: str | None = None,
    verification_repository: VerificationReportCatalogueRepository | None = None,
) -> tuple[VerificationReport, ...]:
    """List verification reports, optionally filtered to one calculation revision.

    Results are sorted by ``(calculation_revision_id, run_at)``.
    """

    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    catalogue = vr_repo.load()
    reports = tuple(
        r
        for r in catalogue.values()
        if calculation_revision_id is None or r.calculation_revision_id == calculation_revision_id
    )
    return tuple(sorted(reports, key=lambda r: (r.calculation_revision_id, r.run_at)))


def get_verification_report(
    verification_report_id: str,
    *,
    verification_repository: VerificationReportCatalogueRepository | None = None,
) -> VerificationReport:
    """Return one verification report by id, or raise."""

    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    catalogue = vr_repo.load()
    report = catalogue.get(verification_report_id)
    if report is None:
        raise VerificationReportNotFoundError(
            tr("application.modelo.errors.verification_report_not_found", verification_report_id=verification_report_id)
        )
    return report


def amend_modelo_revision(
    *,
    from_filing_record_id: str,
    overrides: Mapping[str, Decimal],
    amendment_kind: CalculationRevisionAmendmentKind,
    reason: str,
    actor: str,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    filing_repository: ModeloRecordCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Build and file an amendment over an externally-filed return.

    Pipeline:

    1. Load the baseline filing record (must exist, must be CURRENT,
       must carry ``external_evidence``). The evidence gate ensures
       the amendment runs against AEAT-attested imported data, not a
       fabricated local original.
    2. Load the baseline calculation revision; merge its
       ``casilla_values`` with the operator-supplied ``overrides``
       to produce the corrected casilla map.
    3. Persist a new ``DRAFT`` calculation revision carrying
       ``amendment_kind``, ``amends_filing_record_id``, and the
       operator-supplied ``reason``.
    4. Transition it through ``VERIFICADO_COMPLETO`` (the verification
       contract for amendments is identity-equivalent to the
       calculate path because the registry-snapshot resolver still
       applies; here we mark it verified-complete directly because
       the operator opts in by invoking the amend verb).
    5. Build a new filing record with
       ``amends_filing_record_id = baseline.filing_record_id`` and
       status CURRENT; supersede the baseline record.
    6. Emit a ``modelo.amended`` bucket event linking the new
       filing record to the baseline.

    Raises:
        ModeloRecordNotFoundError: When ``from_filing_record_id`` is
            absent from the catalogue.
        AmendmentEvidenceMissingError: When the baseline record does
            not carry ``external_evidence``.
        AmendmentTargetStateError: When the baseline record is not
            in ``CURRENT`` status.
        WorkUnitNotFoundError: When the work unit referenced by the
            baseline record cannot be loaded.
    """

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    filing_catalogue = fr_repo.load()
    baseline = filing_catalogue.get(from_filing_record_id)
    if baseline is None:
        raise ModeloRecordNotFoundError(
            tr("application.modelo.errors.filing_record_not_found", filing_record_id=from_filing_record_id)
        )
    if baseline.external_evidence is None:
        raise AmendmentEvidenceMissingError(
            f"filing record {from_filing_record_id!r} has no external_evidence; the "
            f"modelo amend path requires an imported AEAT-attested baseline. Use the "
            f"standard re-file path (calculate → verify → file) for locally-filed returns."
        )
    if baseline.status is not ModeloRecordStatus.VIGENTE:
        raise AmendmentTargetStateError(
            f"filing record {from_filing_record_id!r} is in status {baseline.status.value!r}; "
            f"only CURRENT filings can be amended"
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(baseline.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"filing record {from_filing_record_id!r} references missing work_unit_id={baseline.work_unit_id!r}"
        )

    revisions = cr_repo.load()
    baseline_revision = revisions.get(baseline.calculation_revision_id)
    if baseline_revision is None:
        raise CalculationRevisionNotFoundError(
            f"baseline calculation revision {baseline.calculation_revision_id!r} is missing from the catalogue"
        )

    _reject_unknown_override_casillas(
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        overrides=overrides,
    )

    now = clock or datetime.now(UTC)
    corrected_values: dict[str, Decimal] = dict(baseline_revision.casilla_values)
    corrected_values.update(overrides)

    new_revision_id = derive_calculation_revision_id(
        work_unit_id=baseline.work_unit_id,
        inputs_snapshot=baseline_revision.inputs_snapshot,
        binding_overrides=baseline_revision.binding_overrides,
        casilla_values=corrected_values,
        source_transaction_ids=baseline_revision.source_transaction_ids,
        borrador_snapshot_id=baseline_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=baseline_revision.bindings_sourced_from_borrador,
    )
    if new_revision_id in revisions:
        raise CalculationRevisionStateError(
            f"amendment overrides produce calculation_revision_id {new_revision_id!r} "
            f"that already exists in the catalogue; no-op overrides cannot be filed as amendments"
        )

    # Carry regulatory grounding onto the amendment: build typed
    # CasillaObservation rows for the corrected casilla map so the
    # persisted amendment revision and its CLI emit preserve
    # legal_refs / source_refs (and baseline formula provenance for
    # non-overridden casillas) instead of an empty observations tuple.
    amendment_observations = _amendment_observations(
        corrected_values=corrected_values,
        overrides=overrides,
        baseline_revision=baseline_revision,
        snapshot=_resolve_registry_snapshot_for_work_unit(work_unit),
    )

    amendment_draft = CalculationRevision(
        calculation_revision_id=new_revision_id,
        work_unit_id=baseline.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        inputs_snapshot=baseline_revision.inputs_snapshot,
        binding_overrides=baseline_revision.binding_overrides,
        source_transaction_ids=baseline_revision.source_transaction_ids,
        borrador_snapshot_id=baseline_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=baseline_revision.bindings_sourced_from_borrador,
        casilla_values=corrected_values,
        observations=amendment_observations,
        created_at=now,
        updated_at=now,
        amendment_kind=amendment_kind,
        amends_filing_record_id=baseline.filing_record_id,
        amendment_reason=reason.strip(),
    )
    revisions = upsert_calculation_revision(revisions, amendment_draft)

    # Verify the corrected casilla map against the registry's
    # required-manual-input contract before transitioning. The amend
    # path mirrors the standard verify gate so a complementaria
    # cannot be filed with a missing required casilla.
    _reject_incomplete_amendment_casillas(
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        casilla_values=corrected_values,
    )

    # Transition draft → verified-complete (operator opts in by calling amend).
    verified_amendment = amendment_draft.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        }
    )
    revisions = upsert_calculation_revision(revisions, verified_amendment)

    new_filing_id = derive_filing_record_id(
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=new_revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    new_filing = ModeloRecord(
        filing_record_id=new_filing_id,
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=new_revision_id,
        bucket_id=baseline.bucket_id,
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=None,
        amends_filing_record_id=baseline.filing_record_id,
    )

    superseded_baseline = baseline.model_copy(
        update={
            "status": ModeloRecordStatus.SUPERSEDIDO,
            "superseded_at": now,
            "superseded_by_filing_record_id": new_filing_id,
        }
    )
    updated_filing_catalogue = upsert_filing_record(filing_catalogue, superseded_baseline)
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)

    filed_amendment = verified_amendment.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": now,
            "filed_by": actor.strip(),
            "updated_at": now,
        }
    )
    revisions = upsert_calculation_revision(revisions, filed_amendment)

    cr_repo.save(revisions)
    fr_repo.save(updated_filing_catalogue)

    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": new_revision_id,
                    "filed_calculation_revision_id": new_revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                }
            ),
        )
    )

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=baseline.bucket_id,
        event_type=BucketEventType.MODELO_AMENDED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "amends_filing_record_id": baseline.filing_record_id,
            "calculation_revision_id": new_revision_id,
            "work_unit_id": baseline.work_unit_id,
            "modelo": str(baseline.modelo),
            "filing_year": str(baseline.filing_year),
            "period": baseline.period,
            "amendment_kind": amendment_kind.value,
            "override_count": str(len(overrides)),
        },
    )

    return new_filing


def import_external_filing_evidence(
    *,
    work_unit_id: str,
    casilla_values: Mapping[str, Decimal],
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    actor: str = "aeat-import",
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    filing_repository: ModeloRecordCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Persist an externally-filed return as a baseline filing record.

    This is the canonical entry point the import path (justificante
    PDF reader, AEAT CSV register importer, AEAT live capture) uses
    to land an externally-filed return as the bucket's baseline:

    1. Verify the work unit exists and is not discarded.
    2. Persist a fresh ``FILED`` calculation revision carrying the
       imported casilla values (no inputs / overrides — the operator
       did not compute this locally; AEAT's records are the source
       of truth).
    3. Build a ``CURRENT`` filing record with ``external_evidence``
       populated and ``aeat_accepted=True``.
    4. If a prior current filing exists for the (bucket, modelo,
       year, period) tuple, supersede it (same supersession chain
       the file path uses).
    5. Advance the work-unit pointers to the imported baseline.
    6. Emit a ``modelo.filing.imported`` bucket event linking the
       new filing record id to the evidence reference.

    The amend path consumes records produced here as its baseline.

    Raises:
        WorkUnitNotFoundError: when ``work_unit_id`` is absent.
        WorkUnitMutationRefusedError: when the work unit is discarded.
        ExternalModeloImportError: when ``casilla_values`` is empty or
            ``evidence_reference_id`` is empty.
    """

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    if not casilla_values:
        raise ExternalModeloImportError(tr("application.modelo.errors.external_filing_no_casilla_values"))
    cleaned_reference = evidence_reference_id.strip()
    if not cleaned_reference:
        raise ExternalModeloImportError(tr("application.modelo.errors.external_filing_evidence_reference_blank"))

    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(tr("application.modelo.errors.work_unit_not_found", work_unit_id=work_unit_id))
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            tr("application.modelo.errors.work_unit_discarded_cannot_import", work_unit_id=work_unit_id)
        )

    snapshot = _reject_unknown_import_casillas(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        casilla_values=casilla_values,
    )

    inputs_snapshot: dict[str, str] = {}
    binding_overrides: dict[str, str] = {}
    outputs = dict(casilla_values)
    observations = _external_filing_observations(casilla_values=outputs, snapshot=snapshot)

    now = clock or datetime.now(UTC)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
    )
    revisions = cr_repo.load()
    if revision_id in revisions:
        raise ExternalModeloImportError(
            f"calculation revision id={revision_id!r} already exists in the catalogue; "
            f"an identical import was already recorded"
        )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by=actor.strip(),
        filed_at=now,
        filed_by=actor.strip(),
        observations=observations,
    )
    revisions = upsert_calculation_revision(revisions, revision)

    new_filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    filing_catalogue = fr_repo.load()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    new_filing = ModeloRecord(
        filing_record_id=new_filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=None,
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=evidence_kind,
            reference_id=cleaned_reference,
            imported_at=now,
        ),
    )

    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        superseded_prior = prior_current.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
            }
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, superseded_prior)
        prior_revision = revisions.get(prior_current.calculation_revision_id)
        if prior_revision is not None and prior_revision.state is CalculationRevisionState.PRESENTADO:
            superseded_revision = prior_revision.model_copy(
                update={
                    "state": CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
                    "superseded_at": now,
                    "updated_at": now,
                }
            )
            revisions = upsert_calculation_revision(revisions, superseded_revision)
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)

    cr_repo.save(revisions)
    fr_repo.save(updated_filing_catalogue)

    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": revision_id,
                    "filed_calculation_revision_id": revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                }
            ),
        )
    )

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_FILING_IMPORTED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "work_unit_id": work_unit_id,
            "calculation_revision_id": revision_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "evidence_kind": evidence_kind.value,
            "evidence_reference_id": cleaned_reference,
            "supersedes_filing_record_id": (prior_current.filing_record_id if prior_current is not None else ""),
            "casilla_count": str(len(outputs)),
        },
    )

    return new_filing


__all__ = [
    "AmendmentEvidenceMissingError",
    "AmendmentOverrideCasillaError",
    "AmendmentTargetStateError",
    "AmendmentVerificationRefusedError",
    "CalculationRegistryUnavailableError",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "CasillaProvenanceMissingError",
    "ExternalModeloImportError",
    "ModeloAggregationBindingError",
    "ModeloIvaWalletReconciliationBlocked",
    "ModeloRecordNotFoundError",
    "ModeloWorkflowGateError",
    "VerificationReportNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "amend_modelo_revision",
    "calculate_modelo_revision",
    "calculate_modelo_revision_from_bucket_aggregation",
    "create_work_unit",
    "discard_work_unit",
    "file_modelo_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_verification_report",
    "get_work_unit",
    "import_external_filing_evidence",
    "list_calculation_revisions",
    "list_filing_records",
    "list_verification_reports",
    "list_work_units",
    "mark_revision_verificado_completo",
    "rename_work_unit",
    "verify_modelo_revision",
    "workflow_period_for_work_unit",
]
