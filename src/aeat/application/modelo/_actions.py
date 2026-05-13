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

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
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
from ...domain.period import period_end_date
from ...domain.modelos._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingRecord,
    FilingRecordStatus,
    derive_filing_record_id,
)
from ...domain.modelos._filing_repository import (
    FilingRecordCatalogueRepository,
    upsert_filing_record,
)
from ...domain.modelos._repository import (
    WorkUnitCatalogueRepository,
    upsert_work_unit,
)
from ...domain.modelos._verification_report import (
    VerificationCompletenessStatus,
    VerificationFinding,
    VerificationFindingKind,
    VerificationFindingSeverity,
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

_BUCKET_EVENT_PAYLOAD_VERSION = 1


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


class FilingRecordNotFoundError(ModeloError, KeyError):
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


class ExternalFilingImportError(ModeloError):
    """Raised when the external-filing import path cannot persist an
    imported baseline (e.g., empty casilla values, missing evidence
    reference)."""


def _default_name(*, modelo: str, filing_year: int, period: str) -> str:
    """Return the default display name for a fresh work unit.

    Shape: ``<modelo>-<year>-<period>`` (e.g. ``303-2026-Q1``).
    Callers may supply their own name; this helper exists so the
    domain shape stays predictable when the operator does not
    care to name the unit.
    """
    return f"{modelo}-{filing_year}-{period}"


def create_work_unit(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
    name: str | None = None,
    repository: WorkUnitCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Create or load a work unit for the four-axis key.

    Idempotent: when a work unit already exists under the
    deterministic id, the existing record is returned unchanged.
    A subsequent call with a different ``name`` does NOT mutate the
    persisted name; ``rename_work_unit`` is the dedicated mutation
    surface for that.

    Args:
        bucket_id: Stable bucket the work unit belongs to.
        modelo: AEAT modelo code (e.g. ``"303"``).
        filing_year: Tax year for the filing.
        period: Filing period token (e.g. ``"Q1"``).
        revision_id: Stable id of the targeted modelo revision.
        name: Optional display name; defaults to
            ``<modelo>-<year>-<period>``.
        repository: Repository override for testing; defaults to
            the canonical ``WorkUnitCatalogueRepository``.
        clock: ``datetime`` override for testing the created /
            updated timestamps. Defaults to ``datetime.now(UTC)``.

    Returns:
        The persisted :class:`aeat.domain.modelos.WorkUnit`.
    """

    repo = repository or WorkUnitCatalogueRepository()
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
    )
    updated = upsert_work_unit(catalogue, unit)
    repo.save(updated)
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
        and (include_discarded or unit.state is WorkUnitState.DRAFT)
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
        raise WorkUnitNotFoundError(f"no modelo work unit with work_unit_id={work_unit_id!r}")
    return unit


def rename_work_unit(
    work_unit_id: str,
    new_name: str,
    *,
    repository: WorkUnitCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Update a work unit's display name and bump ``updated_at``.

    The ``work_unit_id`` does not change — the identifier is
    content-addressed by the four-axis key, not by display name.
    """

    repo = repository or WorkUnitCatalogueRepository()
    catalogue: WorkUnitCatalogue = repo.load()
    existing = catalogue.get(work_unit_id)
    if existing is None:
        raise WorkUnitNotFoundError(f"no modelo work unit with work_unit_id={work_unit_id!r}")
    if existing.state is WorkUnitState.DISCARDED:
        raise WorkUnitMutationRefusedError(
            f"work unit {work_unit_id!r} is discarded; "
            "create a fresh work unit on the same modelo / year / period to continue"
        )
    now = clock or datetime.now(UTC)
    renamed = existing.model_copy(update={"name": new_name.strip(), "updated_at": now})
    updated_catalogue = upsert_work_unit(catalogue, renamed)
    repo.save(updated_catalogue)
    return renamed


def discard_work_unit(
    work_unit_id: str,
    *,
    actor: str,
    reason: str | None = None,
    repository: WorkUnitCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Transition a work unit to ``DISCARDED`` state.

    Audit metadata (``discarded_at``, ``discarded_by``, optional
    ``discard_reason``) is captured in the same write. Once
    discarded, the work unit cannot be renamed or re-activated;
    the operator must create a fresh work unit on the same modelo
    / year / period.

    Raises:
        WorkUnitNotFoundError: When ``work_unit_id`` is absent.
        WorkUnitAlreadyDiscardedError: When the unit is already
            in ``DISCARDED`` state. Idempotent retries would
            corrupt the audit trail.
    """

    repo = repository or WorkUnitCatalogueRepository()
    catalogue: WorkUnitCatalogue = repo.load()
    existing = catalogue.get(work_unit_id)
    if existing is None:
        raise WorkUnitNotFoundError(f"no modelo work unit with work_unit_id={work_unit_id!r}")
    if existing.state is WorkUnitState.DISCARDED:
        raise WorkUnitAlreadyDiscardedError(
            f"work unit {work_unit_id!r} is already discarded "
            f"(by {existing.discarded_by!r} at {existing.discarded_at!s})"
        )
    now = clock or datetime.now(UTC)
    discarded = existing.model_copy(
        update={
            "state": WorkUnitState.DISCARDED,
            "discarded_at": now,
            "discarded_by": actor.strip(),
            "discard_reason": reason.strip() if reason else None,
            "updated_at": now,
        }
    )
    updated_catalogue = upsert_work_unit(catalogue, discarded)
    repo.save(updated_catalogue)
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


def calculate_modelo_revision(
    work_unit_id: str,
    *,
    actor: str = "system",
    casilla_inputs: Mapping[str, Decimal],
    binding_values: Mapping[str, Decimal] | None = None,
    enum_binding_values: Mapping[str, str] | None = None,
    relation_values: Mapping[str, Decimal] | None = None,
    filing_period_date: date | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
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
       and returns the full ``casilla_values`` map (inputs ∪
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

    from ...domain.calculations.registry import (
        RegistrySnapshotError,
        ValidatedRegistryAuthority,
    )
    from ...domain.calculations.registry._formula_runtime import (
        calculate_registry_snapshot,
    )

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(f"no modelo work unit with work_unit_id={work_unit_id!r}")
    if work_unit.state is WorkUnitState.DISCARDED:
        raise WorkUnitMutationRefusedError(f"work unit {work_unit_id!r} is discarded; cannot calculate")

    try:
        from ...core.config import PROJECT_ROOT

        authority = ValidatedRegistryAuthority.load(_registry_root(), source_root=PROJECT_ROOT)
    except FileNotFoundError as exc:
        raise CalculationRegistryUnavailableError(
            f"registry root {_registry_root()} is missing; cannot calculate"
        ) from exc
    try:
        snapshot = authority.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        )
    except RegistrySnapshotError as exc:
        raise CalculationRegistryUnavailableError(
            f"registry snapshot for modelo={work_unit.modelo!r} "
            f"year={work_unit.filing_year} period={work_unit.period!r} "
            f"could not be resolved: {exc}"
        ) from exc

    period_date = filing_period_date or period_end_date(
        filing_year=work_unit.filing_year,
        registry_period=work_unit.period,
    )
    resolved_bindings = dict(binding_values or {})
    resolved_enum_bindings = dict(enum_binding_values or {})
    resolved_relations = dict(relation_values or {})

    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=dict(casilla_inputs),
        date_context={"filing_period": period_date},
        binding_values=resolved_bindings,
        enum_binding_values=resolved_enum_bindings,
        relation_values=resolved_relations,
    )

    inputs_snapshot: dict[str, str] = dict(
        sorted((k.strip(), _canonical_decimal_str(v)) for k, v in casilla_inputs.items())
    )
    binding_overrides: dict[str, str] = dict(
        sorted(
            [(k.strip(), _canonical_decimal_str(v)) for k, v in resolved_bindings.items()]
            + [(k.strip(), v.strip()) for k, v in resolved_enum_bindings.items()]
        )
    )
    casilla_values: dict[str, Decimal] = dict(engine_result.values)

    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
    )
    revisions = cr_repo.load()
    existing = revisions.get(revision_id)
    if existing is not None:
        # Idempotent: structurally identical re-run.
        return existing
    now = clock or datetime.now(UTC)
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.DRAFT,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
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
            "work_unit_id": work_unit_id,
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "input_casilla_count": str(len(inputs_snapshot)),
            "casilla_count": str(len(casilla_values)),
            "formula_count": str(len(engine_result.entries)),
        },
    )
    return revision


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
        raise CalculationRevisionNotFoundError(f"no calculation revision with id={calculation_revision_id!r}")
    return revision


def mark_revision_verified_complete(
    calculation_revision_id: str,
    *,
    actor: str,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> CalculationRevision:
    """Transition a draft revision to ``VERIFIED_COMPLETE``.

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
        raise CalculationRevisionNotFoundError(f"no calculation revision with id={calculation_revision_id!r}")
    if existing.state is not CalculationRevisionState.DRAFT:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{existing.state.value!r}; only DRAFT revisions can be marked verified-complete"
        )
    now = clock or datetime.now(UTC)
    verified = existing.model_copy(
        update={
            "state": CalculationRevisionState.VERIFIED_COMPLETE,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        }
    )
    cr_repo.save(upsert_calculation_revision(catalogue, verified))
    return verified


def _registry_root() -> Path:
    """Resolve the registry root relative to the project root.

    The previous string default ``"registry/aeat"`` plus
    ``source_root=Path(".")`` was CWD-relative — running the action
    from any directory that wasn't the repo root (production daemon,
    background worker, wheel install, subprocess) raised
    ``FileNotFoundError`` for every modelo. Routing through
    ``aeat.core.config.PROJECT_ROOT`` makes the resolution
    independent of the caller's working directory.
    """

    from ...core.config import PROJECT_ROOT

    return PROJECT_ROOT / "registry" / "aeat"


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

    from pathlib import Path

    from ...domain.calculations.registry import (
        RegistrySnapshotError,
        ValidatedRegistryAuthority,
    )

    from ...core.config import PROJECT_ROOT

    try:
        authority = ValidatedRegistryAuthority.load(_registry_root(), source_root=PROJECT_ROOT)
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


def verify_modelo_revision(
    calculation_revision_id: str,
    *,
    actor: str,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    verification_repository: VerificationReportCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    clock: datetime | None = None,
) -> VerificationReport:
    """Evaluate a draft revision against the verified-complete contract.

    Pipeline:

    1. Load the revision (must be DRAFT).
    2. Resolve the registry snapshot for the parent work unit's
       (modelo, year, period). On failure, emit a BLOCKING finding
       and refuse the transition.
    3. For each required-manual-input casilla in the registry:
       check the revision's ``casilla_values`` contains it. Missing
       entries become MISSING_REQUIRED_CASILLA findings of BLOCKING
       severity.
    4. Build a :class:`VerificationReport`. When zero blocking
       findings are present and the completeness status is
       ``COMPLETE``, ``granted_verified_complete`` is ``True`` and
       the calculation revision transitions DRAFT →
       VERIFIED_COMPLETE.
    5. Persist the report in the verification-report catalogue.
       Failed attempts persist so the audit trail explains why a
       transition was refused.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not in
            DRAFT state. Re-verifying a verified-complete or filed
            revision is rejected because the state is immutable
            from those points; the operator must produce a new
            calculation revision (which lands as a fresh draft) to
            verify again.
    """

    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    revisions = cr_repo.load()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(f"no calculation revision with id={calculation_revision_id!r}")
    if target.state is not CalculationRevisionState.DRAFT:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{target.state.value!r}; only DRAFT revisions can be verified"
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}"
        )

    findings: list[VerificationFinding] = []
    resolved_casillas: list[str] = []
    missing_required: list[str] = []

    registry_lookup = _required_input_casillas_for_revision(
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )
    if registry_lookup is None:
        findings.append(
            VerificationFinding(
                kind=VerificationFindingKind.BLOCKING_RULE,
                severity=VerificationFindingSeverity.BLOCKING,
                message=(
                    f"registry snapshot for modelo={work_unit.modelo!r} "
                    f"year={work_unit.filing_year} period={work_unit.period!r} "
                    f"could not be resolved"
                ),
                next_action="aeat app registry verify",
            )
        )
    else:
        required, _optional = registry_lookup
        # Check operator-supplied inputs, not engine output. With the
        # formula engine wired into calculate, every declared casilla
        # appears in ``casilla_values`` (engine-defaulted to zero for
        # missing inputs). ``inputs_snapshot`` carries only the inputs
        # the operator actually supplied — that is the right basis for
        # the "missing required" gate.
        revision_keys = set(target.inputs_snapshot)
        for casilla_id in required:
            if casilla_id in revision_keys:
                resolved_casillas.append(casilla_id)
            else:
                missing_required.append(casilla_id)
                findings.append(
                    VerificationFinding(
                        kind=VerificationFindingKind.MISSING_REQUIRED_CASILLA,
                        severity=VerificationFindingSeverity.BLOCKING,
                        casilla_id=casilla_id,
                        message=(
                            f"required casilla {casilla_id!r} is not present in "
                            f"the calculation revision's inputs_snapshot"
                        ),
                        next_action=(
                            f"aeat app modelo work calculate {target.work_unit_id} --casilla {casilla_id}=VALUE"
                        ),
                    )
                )

    has_blocking = any(f.severity is VerificationFindingSeverity.BLOCKING for f in findings)
    if has_blocking:
        completeness = (
            VerificationCompletenessStatus.INCOMPLETE
            if missing_required and not any(f.kind is VerificationFindingKind.BLOCKING_RULE for f in findings)
            else VerificationCompletenessStatus.BLOCKED
        )
        granted = False
    else:
        completeness = VerificationCompletenessStatus.COMPLETE
        granted = True

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
        granted_verified_complete=granted,
    )

    # Persist the report regardless of outcome — failed attempts
    # are part of the audit trail.
    vr_repo.save(upsert_verification_report(vr_repo.load(), report))

    if granted:
        verified = target.model_copy(
            update={
                "state": CalculationRevisionState.VERIFIED_COMPLETE,
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
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "completeness_status": completeness.value,
            "finding_count": str(len(findings)),
            "missing_required_count": str(len(missing_required)),
        },
    )

    return report


def file_modelo_revision(
    calculation_revision_id: str,
    *,
    actor: str,
    notes: str | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    filing_repository: FilingRecordCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    clock: datetime | None = None,
) -> FilingRecord:
    """File a verified-complete revision as the current filed answer.

    State transitions performed atomically (from the caller's
    perspective — each repository save is sequenced):

    1. Verify the revision is in ``VERIFIED_COMPLETE`` state.
    2. Look up any existing current filing record for the same
       (bucket, modelo, year, period) tuple.
    3. If a prior current filing exists:
        * mark the prior filing record ``SUPERSEDED`` with
          ``superseded_at`` and ``superseded_by_filing_record_id``;
        * transition the prior filed calculation revision from
          ``FILED`` to ``FILED_SUPERSEDED``.
    4. Create the new filing record with status ``CURRENT``.
    5. Transition the target calculation revision from
       ``VERIFIED_COMPLETE`` to ``FILED``.
    6. Advance the work unit's ``filed_calculation_revision_id``
       and ``current_filing_record_id`` pointers.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not in
            ``VERIFIED_COMPLETE`` state.
        WorkUnitNotFoundError: When the revision's parent work
            unit cannot be loaded.
    """

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or FilingRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    revisions = cr_repo.load()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(f"no calculation revision with id={calculation_revision_id!r}")
    if target.state is not CalculationRevisionState.VERIFIED_COMPLETE:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{target.state.value!r}; only VERIFIED_COMPLETE revisions can be filed"
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing work_unit_id={target.work_unit_id!r}"
        )

    now = clock or datetime.now(UTC)

    new_filing_id = derive_filing_record_id(
        work_unit_id=target.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    filing_catalogue = fr_repo.load()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    # 1. Build new current filing record.
    new_filing = FilingRecord(
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
        status=FilingRecordStatus.CURRENT,
    )

    # 2. Supersede prior filing record if present.
    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        superseded_prior = prior_current.model_copy(
            update={
                "status": FilingRecordStatus.SUPERSEDED,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
            }
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, superseded_prior)

        # Transition prior filed calculation revision to FILED_SUPERSEDED.
        prior_revision = revisions.get(prior_current.calculation_revision_id)
        if prior_revision is not None and prior_revision.state is CalculationRevisionState.FILED:
            superseded_revision = prior_revision.model_copy(
                update={
                    "state": CalculationRevisionState.FILED_SUPERSEDED,
                    "superseded_at": now,
                    "updated_at": now,
                }
            )
            revisions = upsert_calculation_revision(revisions, superseded_revision)

    # 3. Insert new filing record + transition target revision to FILED.
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)
    filed_target = target.model_copy(
        update={
            "state": CalculationRevisionState.FILED,
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
                "modelo": str(work_unit.modelo),
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
            "modelo": str(work_unit.modelo),
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
    filing_repository: FilingRecordCatalogueRepository | None = None,
) -> tuple[FilingRecord, ...]:
    """List filing records, optionally filtered to a bucket.

    Superseded records are excluded unless ``include_superseded``
    is true. Results are sorted by ``(bucket_id, filing_year,
    modelo, period, filed_at)``.
    """

    fr_repo = filing_repository or FilingRecordCatalogueRepository()
    catalogue = fr_repo.load()
    records = tuple(
        record
        for record in catalogue.values()
        if (bucket_id is None or record.bucket_id == bucket_id)
        and (include_superseded or record.status is FilingRecordStatus.CURRENT)
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
    filing_repository: FilingRecordCatalogueRepository | None = None,
) -> FilingRecord:
    """Return one filing record by id, or raise."""

    fr_repo = filing_repository or FilingRecordCatalogueRepository()
    catalogue = fr_repo.load()
    record = catalogue.get(filing_record_id)
    if record is None:
        raise FilingRecordNotFoundError(f"no filing record with id={filing_record_id!r}")
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
        raise VerificationReportNotFoundError(f"no verification report with id={verification_report_id!r}")
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
    filing_repository: FilingRecordCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    clock: datetime | None = None,
) -> FilingRecord:
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
    4. Transition it through ``VERIFIED_COMPLETE`` (the verification
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
        FilingRecordNotFoundError: When ``from_filing_record_id`` is
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
    fr_repo = filing_repository or FilingRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    filing_catalogue = fr_repo.load()
    baseline = filing_catalogue.get(from_filing_record_id)
    if baseline is None:
        raise FilingRecordNotFoundError(f"no filing record with id={from_filing_record_id!r}")
    if baseline.external_evidence is None:
        raise AmendmentEvidenceMissingError(
            f"filing record {from_filing_record_id!r} has no external_evidence; the "
            f"modelo amend path requires an imported AEAT-attested baseline. Use the "
            f"standard re-file path (calculate → verify → file) for locally-filed returns."
        )
    if baseline.status is not FilingRecordStatus.CURRENT:
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

    now = clock or datetime.now(UTC)
    corrected_values: dict[str, Decimal] = dict(baseline_revision.casilla_values)
    corrected_values.update(overrides)

    new_revision_id = derive_calculation_revision_id(
        work_unit_id=baseline.work_unit_id,
        inputs_snapshot=baseline_revision.inputs_snapshot,
        binding_overrides=baseline_revision.binding_overrides,
        casilla_values=corrected_values,
    )
    if new_revision_id in revisions:
        raise CalculationRevisionStateError(
            f"amendment overrides produce calculation_revision_id {new_revision_id!r} "
            f"that already exists in the catalogue; no-op overrides cannot be filed as amendments"
        )

    amendment_draft = CalculationRevision(
        calculation_revision_id=new_revision_id,
        work_unit_id=baseline.work_unit_id,
        state=CalculationRevisionState.DRAFT,
        inputs_snapshot=baseline_revision.inputs_snapshot,
        binding_overrides=baseline_revision.binding_overrides,
        casilla_values=corrected_values,
        created_at=now,
        updated_at=now,
        amendment_kind=amendment_kind,
        amends_filing_record_id=baseline.filing_record_id,
        amendment_reason=reason.strip(),
    )
    revisions = upsert_calculation_revision(revisions, amendment_draft)

    # Transition draft → verified-complete (operator opts in by calling amend).
    verified_amendment = amendment_draft.model_copy(
        update={
            "state": CalculationRevisionState.VERIFIED_COMPLETE,
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

    new_filing = FilingRecord(
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
        status=FilingRecordStatus.CURRENT,
        external_evidence=None,
        amends_filing_record_id=baseline.filing_record_id,
    )

    superseded_baseline = baseline.model_copy(
        update={
            "status": FilingRecordStatus.SUPERSEDED,
            "superseded_at": now,
            "superseded_by_filing_record_id": new_filing_id,
        }
    )
    updated_filing_catalogue = upsert_filing_record(filing_catalogue, superseded_baseline)
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)

    filed_amendment = verified_amendment.model_copy(
        update={
            "state": CalculationRevisionState.FILED,
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
    filing_repository: FilingRecordCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    clock: datetime | None = None,
) -> FilingRecord:
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
        ExternalFilingImportError: when ``casilla_values`` is empty or
            ``evidence_reference_id`` is empty.
    """

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or FilingRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    if not casilla_values:
        raise ExternalFilingImportError(
            "external-filing import requires at least one casilla value; "
            "got an empty mapping"
        )
    cleaned_reference = evidence_reference_id.strip()
    if not cleaned_reference:
        raise ExternalFilingImportError(
            "external-filing import requires a non-empty evidence_reference_id"
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(f"no modelo work unit with work_unit_id={work_unit_id!r}")
    if work_unit.state is WorkUnitState.DISCARDED:
        raise WorkUnitMutationRefusedError(f"work unit {work_unit_id!r} is discarded; cannot import")

    inputs_snapshot: dict[str, str] = {}
    binding_overrides: dict[str, str] = {}
    outputs = dict(casilla_values)

    now = clock or datetime.now(UTC)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
    )
    revisions = cr_repo.load()
    if revision_id in revisions:
        raise ExternalFilingImportError(
            f"calculation revision id={revision_id!r} already exists in the catalogue; "
            f"an identical import was already recorded"
        )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.FILED,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by=actor.strip(),
        filed_at=now,
        filed_by=actor.strip(),
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
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    new_filing = FilingRecord(
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
        status=FilingRecordStatus.CURRENT,
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
                "status": FilingRecordStatus.SUPERSEDED,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
            }
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, superseded_prior)
        prior_revision = revisions.get(prior_current.calculation_revision_id)
        if prior_revision is not None and prior_revision.state is CalculationRevisionState.FILED:
            superseded_revision = prior_revision.model_copy(
                update={
                    "state": CalculationRevisionState.FILED_SUPERSEDED,
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
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "evidence_kind": evidence_kind.value,
            "evidence_reference_id": cleaned_reference,
            "supersedes_filing_record_id": (
                prior_current.filing_record_id if prior_current is not None else ""
            ),
            "casilla_count": str(len(outputs)),
        },
    )

    return new_filing


__all__ = [
    "AmendmentEvidenceMissingError",
    "AmendmentTargetStateError",
    "CalculationRegistryUnavailableError",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "ExternalFilingImportError",
    "FilingRecordNotFoundError",
    "VerificationReportNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "amend_modelo_revision",
    "calculate_modelo_revision",
    "import_external_filing_evidence",
    "create_work_unit",
    "discard_work_unit",
    "file_modelo_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_verification_report",
    "get_work_unit",
    "list_calculation_revisions",
    "list_filing_records",
    "list_verification_reports",
    "list_work_units",
    "mark_revision_verified_complete",
    "rename_work_unit",
    "verify_modelo_revision",
]
