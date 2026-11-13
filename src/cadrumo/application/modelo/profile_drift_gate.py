"""Profile-drift gate: has a profile fact a saved calculation read been edited since?

A calculation reads profile facts (a descendant's birth date, the tax-residence
region, a derived selector such as the Art. 58 aggregate) and the revision keeps
which ones with a digest of each, in ``profile_read_fingerprint``. This gate
rebuilds the profile's fact index the same way the calculation did and digests
the same reads. A difference means the casillas rest on facts the profile no
longer holds, so the stored figures are not the operator's figures any more.

Beside the ledger and invoice drift gates and resolved the same way: the
revision is calculated again. Verify compares a draft; export compares a
verified revision, because a grant seals the revision and verify then returns
its report unchanged, while a profile edit is not held at the write the way a
sealed invoice is. A filed revision is not refused here: its bytes are what was
filed. Verify returns a filed revision's sealed report unchanged, so the form
that shows the filed declaration serves :func:`filed_profile_superseded_findings`
instead, a warning whose door is the amendment. This never recomputes casillas;
a check that quietly recalculated would mint values the operator never saw.

A revision calculated before reads were recorded is UNKNOWN, not stale: it is
disclosed as a warning and nothing is refused for it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.profile_read_fingerprint import changed_profile_reads
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .export_contracts import ModeloExportEvidenceMissingError
from .lifecycle_view_refusal_doors import unit_calculate_verdict
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure
from .profile_binding import current_profile_read_fingerprint
from .profile_derived_facts import ProfileBindingResolutionError

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit

#: Figures resting on profile facts since corrected are not the filer's
#: figures, and a filed one is corrected through the LGT art. 120 amendment.
PROFILE_DRIFT_LEGAL_REFS: tuple[str, ...] = ("ley-58-2003:art-120",)

PROFILE_DRIFT_KEY = "application.modelo.findings.profile_read_drift"
PROFILE_READS_UNKNOWN_KEY = "application.modelo.findings.profile_read_fingerprint_absent"
PROFILE_SUPERSEDED_FILED_KEY = "application.modelo.findings.profile_read_superseded_filed"

_VERIFY_CONDITION = "modelo.work.verify.profile_reads.current"
_VERIFY_EVIDENCE = "modelo.work.verify.profile_reads"


class ProfileReadDriftStatus(StrEnum):
    """How the facts a revision read compare with the profile now."""

    CURRENT = "current"
    CHANGED = "changed"
    UNKNOWN = "unknown"
    """The revision predates read recording; nothing is known either way."""


@dataclass(frozen=True, slots=True)
class ProfileReadDrift:
    """The comparison, naming the reads whose value moved."""

    status: ProfileReadDriftStatus
    changed_selectors: tuple[str, ...] = ()


def profile_read_drift(
    target: CalculationRevision,
    work_unit: WorkUnit,
    *,
    profile_record: object | None,
    operation: PinnedAuthorityOperation,
) -> ProfileReadDrift:
    """Compare the reads ``target`` recorded with the profile as it stands.

    ``profile_record`` is the loaded current record; ``None`` loads it from the
    work unit's bucket. A profile that can no longer be derived (a stored fact
    that stopped parsing) is a change, since the calculation read it parsed.
    """
    recorded = target.profile_read_fingerprint
    if recorded is None:
        return ProfileReadDrift(status=ProfileReadDriftStatus.UNKNOWN)
    snapshot = operation.reading_snapshot(
        work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    try:
        current = current_profile_read_fingerprint(
            snapshot,
            recorded,
            bucket_id=work_unit.bucket_id,
            profile_record=profile_record,
            operation=operation,
        )
    except ProfileBindingResolutionError:
        return ProfileReadDrift(
            status=ProfileReadDriftStatus.CHANGED,
            changed_selectors=tuple(entry.selector for entry in recorded.entries),
        )
    changed = changed_profile_reads(recorded, current)
    if not changed:
        return ProfileReadDrift(status=ProfileReadDriftStatus.CURRENT)
    return ProfileReadDrift(status=ProfileReadDriftStatus.CHANGED, changed_selectors=changed)


def require_profile_reads_current_for_export(
    revision: CalculationRevision,
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse to export a verified revision whose read profile facts were edited since.

    A filed revision is exported as filed, and a revision whose reads are unknown
    is disclosed at verify rather than refused here.

    Raises:
        ModeloExportEvidenceMissingError: The revision's profile basis is no
            longer the profile's; calculating again records the current one.
    """
    if revision.state is not CalculationRevisionState.VERIFICADO_COMPLETO:
        return
    drift = profile_read_drift(revision, work_unit, profile_record=None, operation=operation)
    if drift.status is not ProfileReadDriftStatus.CHANGED:
        return
    raise ModeloExportEvidenceMissingError(
        translated_message="application.modelo.errors.export_profile_read_drift",
        context={
            "calculation_revision_id": revision.calculation_revision_id,
            "changed_count": len(drift.changed_selectors),
            "reason": "profile_read_drift",
        },
        precondition_verdict=unit_calculate_verdict("export_profile_reads", work_unit.work_unit_id),
    )


def _message_facts(work_unit: WorkUnit, drift: ProfileReadDrift) -> dict[str, str | int]:
    facts: dict[str, str | int] = {
        "modelo": str(work_unit.modelo),
        "filing_year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
        "changed_count": len(drift.changed_selectors),
    }
    return facts


def _failure(target: CalculationRevision, work_unit: WorkUnit, drift: ProfileReadDrift) -> ModeloPreconditionFailure:
    return build_modelo_precondition_failure(
        subject_leaf_key="modelo.work.verify",
        condition_id=_VERIFY_CONDITION,
        scenario_id="modelo.work.verify.profile_reads.drift_detected",
        evidence_id=_VERIFY_EVIDENCE,
        evidence_values={
            "calculation_revision_id": target.calculation_revision_id,
            "work_unit_id": target.work_unit_id,
            "changed_read_count": len(drift.changed_selectors),
            "changed_reads": "|".join(drift.changed_selectors),
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_id="operator.modelo.work.calculate",
        action_argument_values={"work_unit_id": work_unit.work_unit_id},
    )


def filed_profile_superseded_findings(
    target: CalculationRevision,
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[ModeloVerificationFinding, ...]:
    """Tell the filer a declaration recorded as filed rests on profile facts since edited.

    The filed bytes stay what was filed, so nothing is blocked: the finding is a
    warning, and correcting a filed declaration is an amendment (LGT art. 120.3),
    which the form serves as the finding's door. A filing whose reads were not
    recorded, or that a later filing superseded, says nothing.
    """
    if target.state is not CalculationRevisionState.PRESENTADO:
        return ()
    drift = profile_read_drift(target, work_unit, profile_record=None, operation=operation)
    if drift.status is not ProfileReadDriftStatus.CHANGED:
        return ()
    return (
        ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.WARNING,
            message_locale_key=PROFILE_SUPERSEDED_FILED_KEY,
            message_facts=_message_facts(work_unit, drift),
            legal_refs=PROFILE_DRIFT_LEGAL_REFS,
        ),
    )


def profile_drift_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    profile_record: object | None,
    operation: PinnedAuthorityOperation,
    source_refs: tuple[str, ...] = (),
    failure_observer: Callable[[ModeloVerificationFinding, ModeloPreconditionFailure], None] | None = None,
) -> list[ModeloVerificationFinding]:
    """Report a draft whose read profile facts were edited, or whose reads are unknown.

    A drifted draft is a blocking stale calculation, recovered by calculating
    again. Only a draft is compared, as the ledger and invoice gates compare one.
    """
    if target.state is not CalculationRevisionState.BORRADOR:
        return []
    drift = profile_read_drift(target, work_unit, profile_record=profile_record, operation=operation)
    if drift.status is ProfileReadDriftStatus.CURRENT:
        return []
    if drift.status is ProfileReadDriftStatus.UNKNOWN:
        return [
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message_locale_key=PROFILE_READS_UNKNOWN_KEY,
                message_facts=_message_facts(work_unit, drift),
                legal_refs=PROFILE_DRIFT_LEGAL_REFS,
                source_refs=source_refs,
            )
        ]
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key=PROFILE_DRIFT_KEY,
        message_facts=_message_facts(work_unit, drift),
        legal_refs=PROFILE_DRIFT_LEGAL_REFS,
        source_refs=source_refs,
    )
    if failure_observer is not None:
        failure_observer(finding, _failure(target, work_unit, drift))
    return [finding]


__all__ = [
    "PROFILE_DRIFT_KEY",
    "PROFILE_DRIFT_LEGAL_REFS",
    "PROFILE_READS_UNKNOWN_KEY",
    "PROFILE_SUPERSEDED_FILED_KEY",
    "ProfileReadDrift",
    "ProfileReadDriftStatus",
    "filed_profile_superseded_findings",
    "profile_drift_findings",
    "profile_read_drift",
    "require_profile_reads_current_for_export",
]
