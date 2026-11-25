"""Filed capture observation accumulation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ..modelo.filing_chain_reconciliation import FilingReconciliationResult
from .filed_history_discovery import recapture_divergence_notices
from .filed_observation_persistence import (
    enroll_filed_justificante_evidence,
    filed_observation_identity_key,
)
from .filed_observation_ports import FiledObservationPersistencePorts, FiledObservationProtocol

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


FILED_SUBMITTED_FILE_EXTRACTION_NOTICE_CODE = "live.filed.pull.submitted_file_extraction_failed"


_SUBMITTED_FILE_EXTRACTION_ERROR_METADATA_KEY = "submitted_file_extraction_error"


def submitted_file_extraction_notices(observation: FiledObservationProtocol) -> tuple[Notice, ...]:
    """Project a recorded submitted-file layout refusal onto the notice channel.

    The Sede adapter is the authority for both parsing and the persisted error
    text. It records a refusal under ``submitted_file_extraction_error`` and
    preserves its declaration-PDF fallback without trying to reinterpret either
    one here. This projection only makes that already-recorded fact visible to
    the operator, retaining the parser's own reason and the filed record that
    needs follow-up. A clean capture has no metadata key and therefore no
    advisory.
    """
    reason = observation.metadata.get(_SUBMITTED_FILE_EXTRACTION_ERROR_METADATA_KEY, "").strip()
    if not reason:
        return ()
    return (
        Notice(
            severity=NoticeSeverity.WARNING,
            code=FILED_SUBMITTED_FILE_EXTRACTION_NOTICE_CODE,
            message=tr(
                "live.filed.pull.submitted_file_extraction_failed",
                modelo=observation.modelo,
                period=observation.period.registry_token,
                ejercicio=observation.ejercicio,
                expediente_id=observation.expediente_id,
                reason=reason,
            ),
            context={
                "modelo": observation.modelo,
                "filing_year": str(observation.ejercicio),
                "period": observation.period.registry_token,
                "expediente_id": observation.expediente_id,
                "reason": reason,
            },
        ),
    )


class _CaptureReportFields(TypedDict):
    """Deduped report fields shared by every filed-declaration capture report."""

    captured_count: int
    reached_count: int
    observation_paths: tuple[str, ...]
    observation_ids: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    justificante_metadata_count: int
    justificante_csvs: tuple[str, ...]
    filing_evidence_stamped_count: int
    filing_record_ids: tuple[str, ...]
    filing_evidence_conflict_count: int
    filing_evidence_conflict_record_ids: tuple[str, ...]
    evidence_notices: tuple[Notice, ...]
    casilla_count: int
    reconciliation_results: tuple[FilingReconciliationResult, ...]


@dataclass(slots=True)
class FiledCaptureAccumulator:
    """Mutable accumulator for one filed-declaration capture run.

    Holds the persisted-artefact ledgers shared by the single-shot, bulk, and
    source capture paths. :meth:`absorb` folds one captured observation into the
    run (persist manifest, collect artefact refs, enrol justificante evidence,
    reconcile the filing chain); :meth:`capture_report_fields` projects the deduped
    report fields every capture report shares. The ``dict.fromkeys`` dedup
    ordering is preserved verbatim so report values stay byte-identical.
    """

    operation: PinnedAuthorityOperation | None = None
    observation_paths: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    artefact_refs: list[str] = field(default_factory=list)
    justificante_csvs: list[str] = field(default_factory=list)
    filing_record_ids: list[str] = field(default_factory=list)
    conflicting_filing_record_ids: list[str] = field(default_factory=list)
    reconciliation_results: list[FilingReconciliationResult] = field(default_factory=list)
    observations_for_calculation: list[FiledObservationProtocol] = field(default_factory=list)
    evidence_notices: list[Notice] = field(default_factory=list)
    #: Recapture-divergence advisories, one per re-captured filing whose casilla
    #: values this sweep changed. Read before each upsert, never after.
    recapture_notices: list[Notice] = field(default_factory=list)
    justificante_csvs_by_observation: dict[tuple[str, int, str, str], tuple[str, ...]] = field(default_factory=dict)
    casilla_count: int = 0
    #: Observations folded in, counted in every mode. ``observation_paths``
    #: cannot serve as the tally because a preview persists nothing and would
    #: leave it empty, which would silently uncap a limited sweep.
    absorbed_count: int = 0

    @property
    def reached_count(self) -> int:
        """Units this run REACHED, answering :class:`SyncRunCoverageSource`.

        The surface-neutral name the sync-run store asks for, mapped onto this
        sweep's own tally. Both coverage counts are read off this one object so
        they cannot be drawn from different populations.
        """
        return self.absorbed_count

    @property
    def divergences(self) -> Sequence[Notice]:
        """Divergences found among the reached units, one entry each.

        Bounded by :attr:`reached_count` by construction: :meth:`absorb` appends
        at most one advisory per observation and increments the tally on the
        same pass, so the sync-run coverage bound cannot be violated from here.
        """
        return self.recapture_notices

    def absorb(
        self,
        observation: FiledObservationProtocol,
        *,
        ports: FiledObservationPersistencePorts,
        bucket_id: str,
        output_root: Path,
        dry_run: bool = False,
    ) -> None:
        """Persist one captured observation and fold its artefacts into the run.

        With ``dry_run`` the divergence read still happens and every write is
        skipped: no observation is persisted, no justificante evidence is
        enrolled, and nothing is queued for the calculation-observation write
        downstream. The preview therefore runs the real funnel minus its
        writes, rather than a parallel implementation that could drift from it.
        """
        # Read the recapture divergence BEFORE the upsert, because a re-capture
        # is an unconditional upsert and afterwards the prior values are gone.
        # This is the only ordering that can answer "what did this sweep change";
        # the advisory it produces was built and exported but never called from
        # any production path, so a corrected filing silently overwrote the
        # previously observed values and the operator was never told.
        self.recapture_notices.extend(
            recapture_divergence_notices(
                (observation,),
                repository=ports.calculation_repository,
                operation=self.operation,
            )
        )
        # The Sede capture deliberately preserves a submitted-file layout
        # refusal as observation metadata and then keeps the declaration-PDF
        # fallback available. Metadata alone is not an operator surface,
        # though: fold the recorded refusal into the one capture advisory lane
        # before persistence so every capture mode can forward it verbatim.
        self.evidence_notices.extend(submitted_file_extraction_notices(observation))
        self.absorbed_count += 1
        if dry_run:
            # Everything past this point writes. The divergence read above is
            # the preview's whole answer and it has already happened.
            return
        manifest_path = ports.observation_persistence.persist_observation(observation)
        self.observation_paths.append(capture_report_path(manifest_path, output_root=output_root))
        self.observation_ids.append(manifest_path.name)
        self.artefact_refs.extend(
            storage_ref
            for artefact in observation.artefacts
            for storage_ref in (artefact.storage_ref,)
            if storage_ref is not None
        )
        enrollment = enroll_filed_justificante_evidence(observation, ports=ports, bucket_id=bucket_id)
        self.justificante_csvs.extend(enrollment.justificante_csvs)
        self.justificante_csvs_by_observation[filed_observation_identity_key(observation)] = (
            enrollment.justificante_csvs
        )
        self.filing_record_ids.extend(enrollment.filing_record_ids)
        self.conflicting_filing_record_ids.extend(enrollment.conflicting_filing_record_ids)
        self.reconciliation_results.extend(enrollment.reconciliation_results)
        # The enrolment already produced one typed WARNING per artefact that
        # yielded no evidence, each naming its own reason. They were being
        # discarded here, which is what let a capture extract casillas and report
        # zero justificante evidence with no visible cause. Collected verbatim --
        # never merged -- because two distinguishable dead ends folded into one
        # notice recreates the collapse the reasons exist to undo.
        self.evidence_notices.extend(enrollment.notices)
        self.casilla_count += len(observation.casillas)
        self.observations_for_calculation.append(observation)

    def capture_report_fields(self) -> _CaptureReportFields:
        """Return the deduped report fields shared by every filed-capture report."""
        return {
            "captured_count": len(self.observation_paths),
            "reached_count": self.reached_count,
            "observation_paths": tuple(self.observation_paths),
            "observation_ids": tuple(self.observation_ids),
            "artefact_refs": tuple(self.artefact_refs),
            "justificante_metadata_count": len(tuple(dict.fromkeys(self.justificante_csvs))),
            "justificante_csvs": tuple(dict.fromkeys(self.justificante_csvs)),
            "filing_evidence_stamped_count": len(tuple(dict.fromkeys(self.filing_record_ids))),
            "filing_record_ids": tuple(dict.fromkeys(self.filing_record_ids)),
            "filing_evidence_conflict_count": len(tuple(dict.fromkeys(self.conflicting_filing_record_ids))),
            "filing_evidence_conflict_record_ids": tuple(dict.fromkeys(self.conflicting_filing_record_ids)),
            "evidence_notices": tuple(self.evidence_notices),
            "casilla_count": self.casilla_count,
            "reconciliation_results": tuple(self.reconciliation_results),
        }


def capture_report_path(path: Path, *, output_root: Path) -> str:
    """Return a stable report path relative to the configured output root when possible."""
    try:
        return path.relative_to(output_root).as_posix()
    except ValueError:
        return str(path)
