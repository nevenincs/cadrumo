"""One-command modelo filing orchestration: readiness → calculate → verify → export.

``run_modelo_quickfile`` sequences the existing single-stage modelo application
services for one ``(modelo, filing_year, period)`` target and returns a typed
:class:`QuickfileResult` recording every stage's outcome. It resolves readiness,
resumes or creates the work unit
(:func:`application.modelo.ensure_modelo_work_unit_for_active_target`),
calculates a draft revision
(:func:`application.modelo.calculate_modelo_work_revision`), verifies it
(:func:`application.modelo.verify_modelo_revision`), and exports the
verified revision to a local fichero-BOE artefact
(:func:`application.modelo.export_modelo_revision`).

This orchestrator re-implements no stage: every step delegates to the
authoritative application service, preserving each service's guards, lifecycle
events, and provenance. It stops instructively at the first stage that refuses —
a missing calculation binding, an ungranted verification, or an export gate —
marking the remaining stages skipped so the operator sees exactly where the chain
halted and why.

The chain is BUILD + EXPORT only. It never performs a live AEAT submission and
never contacts AEAT: the terminal step is the local fichero-BOE export the human
files themselves through the AEAT sede (see
:func:`application.modelo.export_modelo_revision`, which is local-only, and
the ``sensitive-financial-data-secure-storage-only`` rule). The internal ``file`` record step is
deliberately excluded: export consumes the ``VERIFICADO_COMPLETO`` revision
directly.

See Also:
    :func:`application.modelo.calculate_modelo_work_revision`:
        The calculate stage this orchestrator drives.
    :func:`application.modelo.verify_modelo_revision`:
        The verify stage; a non-granted report halts the chain.
    :func:`application.modelo.export_modelo_revision`:
        The terminal local export stage.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import AeatProductSoftwareIdentity, PaymentElection, Period, PriorDomiciliationElection, RefundElection
from ...core.errors import CadrumoError
from ...core.identity import BucketId
from ...core.logging import get_logger
from ...domain.calculations.registry.ids import RevisionId
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos import (
    CalculationRevision,
    FilingInstanceEvidence,
    VerificationReport,
    WorkUnit,
)
from ._calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from ._export import ModeloExportCommand, ModeloExportResult, export_modelo_revision
from ._verification_actions import verify_modelo_revision
from .work_addressing import (
    ensure_modelo_work_unit_for_active_target,
    resolve_registry_revision_for_work_target,
)

if TYPE_CHECKING:
    from ..state_projection import ProjectionModeloReadiness

_log = get_logger(__name__)


def _empty_text_context() -> dict[str, str]:
    """Create the typed empty error-context map used by a stage outcome."""
    return {}


class QuickfileStage(StrEnum):
    """The ordered stages of the quickfile filing chain."""

    READINESS = "readiness"
    CREATE = "create"
    CALCULATE = "calculate"
    VERIFY = "verify"
    EXPORT = "export"


#: Canonical stage order the orchestrator walks. Every stage after the one that
#: refuses is recorded as :attr:`QuickfileStageStatus.SKIPPED`.
QUICKFILE_STAGE_ORDER: tuple[QuickfileStage, ...] = (
    QuickfileStage.READINESS,
    QuickfileStage.CREATE,
    QuickfileStage.CALCULATE,
    QuickfileStage.VERIFY,
    QuickfileStage.EXPORT,
)


class QuickfileStageStatus(StrEnum):
    """Outcome status for one quickfile stage.

    ``OK`` — the stage completed and the chain may proceed. ``WARNING`` — the
    stage completed but surfaced a non-blocking advisory (e.g. readiness
    reported the profile is not yet source-ready, which a caller-supplied
    ``--binding`` may still satisfy). ``REFUSED`` — the stage refused and the
    chain halted here. ``SKIPPED`` — a downstream stage that never ran because an
    earlier stage refused.
    """

    OK = "ok"
    WARNING = "warning"
    REFUSED = "refused"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class QuickfileStageOutcome:
    """The typed result of one quickfile stage.

    ``translated_message`` and ``context`` carry the originating
    :class:`core.errors.CadrumoError` metadata verbatim so the transport layer
    can localise the refusal without the application layer depending on i18n.
    """

    stage: QuickfileStage
    status: QuickfileStageStatus
    message: str = ""
    translated_message: str | None = None
    context: Mapping[str, str] = field(default_factory=_empty_text_context)


@dataclass(frozen=True, slots=True)
class QuickfileResult:
    """Aggregate outcome of one ``run_modelo_quickfile`` invocation.

    ``completed`` is ``True`` only when the export stage succeeded and a local
    fichero-BOE artefact was written. ``stopped_at_stage`` names the stage that
    refused when the chain halted early. The intermediate domain records
    (``work_unit``, ``calculation_revision`` — a :class:`CalculationRevision`
    when the calculate stage ran —, ``verification_report``,
    ``export_result``) are surfaced so the transport can render each stage's
    detail, and are ``None`` for stages that never ran.
    """

    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: RevisionId
    stages: tuple[QuickfileStageOutcome, ...]
    completed: bool
    stopped_at_stage: QuickfileStage | None
    readiness: ProjectionModeloReadiness | None
    work_unit: WorkUnit | None
    calculation_revision: CalculationRevision | None
    verification_report: VerificationReport | None
    export_result: ModeloExportResult | None


class QuickfileCommand(BaseModel):
    """Strict input contract for :func:`run_modelo_quickfile`.

    Attributes:
        bucket_id: The active profile bucket the chain runs against.
        modelo: AEAT modelo code (e.g. ``111``, ``130``, ``303``).
        filing_year: Filing year of the target period.
        period: Typed :class:`~core.Period` for the filing target.
        registry_revision_id: Optional assertion of the law-determined registry
            revision. When supplied it is validated against
            :func:`resolve_registry_revision_for_work_target`; it never overrides
            the law-determined pick.
        output_path: Destination for the terminal fichero-BOE export.
        actor: Operator label recorded into each stage's lifecycle event.
        refund_election: Per-filing negative-result disposition threaded into the
            export's fichero declaration type.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: RevisionId | None = None
    output_path: Path
    actor: str
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    prior_domiciliation_election: PriorDomiciliationElection | None = None
    product_software_identity: AeatProductSoftwareIdentity | None = None
    filing_instance_evidence: FilingInstanceEvidence | None = None


def _refusal_outcome(stage: QuickfileStage, exc: CadrumoError) -> QuickfileStageOutcome:
    """Build a REFUSED outcome carrying the error's localisation metadata."""
    context = {str(key): str(value) for key, value in (exc.context or {}).items()}
    return QuickfileStageOutcome(
        stage=stage,
        status=QuickfileStageStatus.REFUSED,
        message=str(exc),
        translated_message=exc.translated_message,
        context=context,
    )


def _skipped_after(stopped_at: QuickfileStage) -> tuple[QuickfileStageOutcome, ...]:
    """Return SKIPPED outcomes for every stage after ``stopped_at``."""
    stop_index = QUICKFILE_STAGE_ORDER.index(stopped_at)
    return tuple(
        QuickfileStageOutcome(stage=stage, status=QuickfileStageStatus.SKIPPED)
        for stage in QUICKFILE_STAGE_ORDER[stop_index + 1 :]
    )


def run_modelo_quickfile(
    command: QuickfileCommand,
    *,
    workflow_profile: TaxpayerProfile,
    build_calculation_inputs: Callable[[str], WorkCalculateInputBundle],
) -> QuickfileResult:
    """Run readiness → create → calculate → verify → export for one modelo target.

    Each stage delegates to its authoritative application service. The chain
    halts at the first stage that refuses (a raised
    :class:`core.errors.CadrumoError`, or an ungranted verification), records
    the refusal, and marks the remaining stages skipped.

    ``build_calculation_inputs`` is the transport-supplied factory that turns the
    resolved work-unit id into a validated
    :class:`~application.modelo.WorkCalculateInputBundle`; the input bundle
    can only be validated once the work unit (and therefore its registry
    revision) is known, so the factory is invoked after the create stage.

    Args:
        command: The resolved quickfile target.
        workflow_profile: The active :class:`TaxpayerProfile` the readiness and
            calculate stages are evaluated against.
        build_calculation_inputs: Factory producing the calculate-stage inputs.

    Returns:
        A :class:`QuickfileResult` whose ``completed`` flag is ``True`` only when
        the terminal export wrote a local fichero-BOE artefact.
    """
    stages: list[QuickfileStageOutcome] = []

    # ── Stage 1: readiness ────────────────────────────────────────────────
    # Resolving the law-determined registry revision is the hard precondition
    # for the whole chain; a failure here refuses at readiness. The readiness
    # projection itself is advisory: a not-ready verdict is a WARNING because a
    # caller-supplied --binding may still satisfy a source the projection reads
    # as missing.
    try:
        registry_revision_id = resolve_registry_revision_for_work_target(
            modelo=command.modelo,
            filing_year=command.filing_year,
            period=command.period,
            registry_revision_id=command.registry_revision_id,
        )
    except CadrumoError as exc:
        stages.append(_refusal_outcome(QuickfileStage.READINESS, exc))
        stages.extend(_skipped_after(QuickfileStage.READINESS))
        return QuickfileResult(
            modelo=command.modelo,
            filing_year=command.filing_year,
            period=command.period,
            registry_revision_id="",
            stages=tuple(stages),
            completed=False,
            stopped_at_stage=QuickfileStage.READINESS,
            readiness=None,
            work_unit=None,
            calculation_revision=None,
            verification_report=None,
            export_result=None,
        )

    readiness = _resolve_readiness(command, registry_revision_id=registry_revision_id)
    stages.append(_readiness_outcome(readiness))

    # ── Stage 2: create / resume the work unit ────────────────────────────
    try:
        ensure_result = ensure_modelo_work_unit_for_active_target(
            bucket_id=command.bucket_id,
            modelo=command.modelo,
            filing_year=command.filing_year,
            period=command.period,
            registry_revision_id=command.registry_revision_id,
            actor=command.actor,
            catalogue=WorkUnitCatalogueRepository(bucket_id=command.bucket_id).load(),
        )
    except CadrumoError as exc:
        return _halted(
            command,
            registry_revision_id=registry_revision_id,
            stages=stages,
            refusal=_refusal_outcome(QuickfileStage.CREATE, exc),
            readiness=readiness,
        )
    work_unit = ensure_result.work_unit
    stages.append(
        QuickfileStageOutcome(
            stage=QuickfileStage.CREATE,
            status=QuickfileStageStatus.OK,
            message=("resumed" if ensure_result.reused else "created"),
            context={"work_unit_id": work_unit.work_unit_id},
        ),
    )

    # ── Stage 3: calculate ────────────────────────────────────────────────
    try:
        calculation_inputs = replace(
            build_calculation_inputs(work_unit.work_unit_id),
            filing_instance_evidence=command.filing_instance_evidence,
        )
        calculation = calculate_modelo_work_revision(
            work_unit_id=work_unit.work_unit_id,
            actor=command.actor,
            inputs=calculation_inputs,
        )
    except CadrumoError as exc:
        return _halted(
            command,
            registry_revision_id=registry_revision_id,
            stages=stages,
            refusal=_refusal_outcome(QuickfileStage.CALCULATE, exc),
            readiness=readiness,
            work_unit=work_unit,
        )
    calculation_revision = calculation.revision
    stages.append(
        QuickfileStageOutcome(
            stage=QuickfileStage.CALCULATE,
            status=QuickfileStageStatus.OK,
            context={"calculation_revision_id": calculation_revision.calculation_revision_id},
        ),
    )

    # ── Stage 4: verify ───────────────────────────────────────────────────
    try:
        report = verify_modelo_revision(
            calculation_revision.calculation_revision_id,
            actor=command.actor,
            workflow_profile=workflow_profile,
        )
    except CadrumoError as exc:
        return _halted(
            command,
            registry_revision_id=registry_revision_id,
            stages=stages,
            refusal=_refusal_outcome(QuickfileStage.VERIFY, exc),
            readiness=readiness,
            work_unit=work_unit,
            calculation_revision=calculation_revision,
        )
    if not report.granted_verificado_completo:
        blocking = tuple(f for f in report.findings if _is_blocking(f))
        refusal = QuickfileStageOutcome(
            stage=QuickfileStage.VERIFY,
            status=QuickfileStageStatus.REFUSED,
            message="verification did not grant verificado-completo",
            context={
                "granted_verificado_completo": "false",
                "blocking_finding_count": str(len(blocking)),
                "verification_report_id": report.verification_report_id,
            },
        )
        return _halted(
            command,
            registry_revision_id=registry_revision_id,
            stages=stages,
            refusal=refusal,
            readiness=readiness,
            work_unit=work_unit,
            calculation_revision=calculation_revision,
            verification_report=report,
        )
    stages.append(
        QuickfileStageOutcome(
            stage=QuickfileStage.VERIFY,
            status=QuickfileStageStatus.OK,
            context={
                "granted_verificado_completo": "true",
                "verification_report_id": report.verification_report_id,
            },
        ),
    )

    # ── Stage 5: export (local fichero-BOE; never contacts AEAT) ───────────
    try:
        export_result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calculation_revision.calculation_revision_id,
                output_path=command.output_path,
                actor=command.actor,
                refund_election=command.refund_election,
                payment_election=command.payment_election,
                prior_domiciliation_election=command.prior_domiciliation_election,
                product_software_identity=command.product_software_identity,
            ),
            workflow_profile=workflow_profile,
        )
    except CadrumoError as exc:
        return _halted(
            command,
            registry_revision_id=registry_revision_id,
            stages=stages,
            refusal=_refusal_outcome(QuickfileStage.EXPORT, exc),
            readiness=readiness,
            work_unit=work_unit,
            calculation_revision=calculation_revision,
            verification_report=report,
        )
    stages.append(
        QuickfileStageOutcome(
            stage=QuickfileStage.EXPORT,
            status=QuickfileStageStatus.OK,
            context={
                "output_path": str(export_result.output_path),
                "file_sha256": export_result.file_sha256,
            },
        ),
    )

    return QuickfileResult(
        modelo=command.modelo,
        filing_year=command.filing_year,
        period=command.period,
        registry_revision_id=registry_revision_id,
        stages=tuple(stages),
        completed=True,
        stopped_at_stage=None,
        readiness=readiness,
        work_unit=work_unit,
        calculation_revision=calculation_revision,
        verification_report=report,
        export_result=export_result,
    )


def _halted(
    command: QuickfileCommand,
    *,
    registry_revision_id: RevisionId,
    stages: list[QuickfileStageOutcome],
    refusal: QuickfileStageOutcome,
    readiness: ProjectionModeloReadiness | None,
    work_unit: WorkUnit | None = None,
    calculation_revision: CalculationRevision | None = None,
    verification_report: VerificationReport | None = None,
) -> QuickfileResult:
    """Assemble a halted result: append the refusal, skip every later stage."""
    stages.append(refusal)
    stages.extend(_skipped_after(refusal.stage))
    return QuickfileResult(
        modelo=command.modelo,
        filing_year=command.filing_year,
        period=command.period,
        registry_revision_id=registry_revision_id,
        stages=tuple(stages),
        completed=False,
        stopped_at_stage=refusal.stage,
        readiness=readiness,
        work_unit=work_unit,
        calculation_revision=calculation_revision,
        verification_report=verification_report,
        export_result=None,
    )


def _resolve_readiness(
    command: QuickfileCommand,
    *,
    registry_revision_id: RevisionId,
) -> ProjectionModeloReadiness | None:
    """Run the readiness projection for the target, tolerating advisory failure.

    Readiness is imported lazily so the ``application.modelo`` package facade
    does not import ``application.state_projection`` at load time. A raised
    :class:`core.errors.CadrumoError` degrades to ``None`` (advisory only):
    readiness never blocks the chain, so a projection failure must not abort it.
    """
    from ..state_projection import ModeloReadinessRequest, build_operator_state_projection

    try:
        projection = build_operator_state_projection(
            modelo_readiness_requests=(
                ModeloReadinessRequest(
                    modelo=command.modelo,
                    revision_id=registry_revision_id,
                    filing_year=command.filing_year,
                    period=command.period,
                ),
            ),
        )
    except CadrumoError:
        _log.debug("quickfile readiness projection failed; continuing", exc_info=True)
        return None
    if not projection.modelo_readiness:
        return None
    return projection.modelo_readiness[0]


def _readiness_outcome(readiness: ProjectionModeloReadiness | None) -> QuickfileStageOutcome:
    """Project the readiness verdict onto an OK / WARNING stage outcome."""
    if readiness is None:
        return QuickfileStageOutcome(
            stage=QuickfileStage.READINESS,
            status=QuickfileStageStatus.WARNING,
            message="readiness could not be resolved; proceeding to calculate",
        )
    if readiness.ready:
        return QuickfileStageOutcome(stage=QuickfileStage.READINESS, status=QuickfileStageStatus.OK)
    return QuickfileStageOutcome(
        stage=QuickfileStage.READINESS,
        status=QuickfileStageStatus.WARNING,
        message="profile is not yet source-ready; caller-supplied inputs may still satisfy calculate",
        context={
            "ready": "false",
            "profile_ready": str(readiness.profile_ready).lower(),
            "binding_ready": str(readiness.binding_ready).lower(),
            "missing_bindings": str(len(readiness.missing_bindings)),
        },
    )


def _is_blocking(finding: object) -> bool:
    """Return True when a verification finding carries BLOCKING severity."""
    severity = getattr(finding, "severity", None)
    return bool(getattr(severity, "value", None) == "blocking")


__all__ = [
    "QUICKFILE_STAGE_ORDER",
    "QuickfileCommand",
    "QuickfileResult",
    "QuickfileStage",
    "QuickfileStageOutcome",
    "QuickfileStageStatus",
    "run_modelo_quickfile",
]
