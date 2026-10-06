"""Project an explicitly selected persisted revision without recalculating it."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    assert_revision_snapshot_evidence_coverage,
)
from ...domain.modelos.work_unit import WorkUnit
from .review_snapshot import (
    CalculationReviewSelection,
    EvidenceDisposition,
    EvidenceInventoryItem,
    ReviewAmount,
    ReviewContribution,
    ReviewFinding,
    ReviewSnapshot,
    ReviewSnapshotContent,
    ReviewSourceKind,
    ReviewStatus,
    seal_review_snapshot,
)


def build_calculation_review_snapshot(
    *, selection: CalculationReviewSelection, revision: CalculationRevision, work_unit: WorkUnit
) -> ReviewSnapshot:
    """Retain saved values and captured evidence, with explicit attribution gaps.

    The caller owns encrypted repository access and the selected authority pin.
    Neither current ledger state nor the work unit's current-revision pointer
    substitutes for the explicitly selected saved revision. A revision-wide
    source trace does not prove any individual amount's contributing rows.
    """
    if (
        work_unit.bucket_id != str(selection.profile_id)
        or work_unit.work_unit_id != selection.work_unit_id
        or revision.work_unit_id != selection.work_unit_id
        or revision.calculation_revision_id != selection.calculation_revision_id
        or str(work_unit.modelo) != selection.modelo
        or work_unit.filing_year != selection.filing_year
        or work_unit.period.registry_token != selection.period
        or work_unit.revision_id != selection.registry_snapshot_ref.revision_id
        or revision.registry_snapshot_ref != selection.registry_snapshot_ref
    ):
        raise ValueError("saved review selection does not match its persisted revision and profile")
    assert_revision_snapshot_evidence_coverage(revision)
    ledger = revision.ledger_filing_evidence
    rows = ledger.rows if ledger is not None else ()
    fingerprint_snapshot = revision.ledger_filing_snapshot
    if ledger is not None and fingerprint_snapshot is not None:
        fingerprints = {row.transaction_id: row.fingerprint for row in fingerprint_snapshot.rows}
        if ledger.snapshot_fingerprint != fingerprint_snapshot.snapshot_fingerprint or any(
            row.fingerprint != fingerprints.get(row.transaction_id) for row in rows
        ):
            raise ValueError("saved ledger evidence does not match its captured fingerprints")
    findings = [
        ReviewFinding(
            code="review.original_authority_generation_unavailable",
            detail=(
                "The saved revision retains registry coordinates but not its original authority generation. "
                "Selection authority identifiers describe the pinned publication authority."
            ),
        ),
        ReviewFinding(
            code="review.saved_display_semantics_unavailable",
            detail="Values retain their saved decimal precision; currency, unit and rounding policy are not inferred.",
        ),
    ]
    if revision.source_transaction_ids and ledger is None:
        findings.append(
            ReviewFinding(
                code="review.captured_ledger_unavailable",
                detail="This revision did not retain its contributing ledger rows; current rows were not substituted.",
                related_ids=revision.source_transaction_ids,
            )
        )
    evidence = tuple(
        EvidenceInventoryItem(
            evidence_id=attachment_id,
            source_revision=revision.calculation_revision_id,
            disposition=EvidenceDisposition.EXCLUDED,
            reason="Original attachment bytes were not selected for this spreadsheet publication.",
        )
        for attachment_id in sorted({attachment_id for row in rows for attachment_id in row.attachment_ids})
    )
    observations = {item.casilla_id: item for item in revision.observations}
    contributions: list[ReviewContribution] = []
    amounts: list[ReviewAmount] = []
    for casilla_id, value in sorted(revision.casilla_values.items()):
        amount_id = f"casilla:{casilla_id}"
        contribution_id = f"source:{amount_id}"
        observation = observations.get(casilla_id)
        operator_layer = revision.operator_layer
        raw_input = operator_layer.decimal_casilla_inputs.get(casilla_id) if operator_layer is not None else None
        manual = observation is not None and observation.formula_id is None and _same_decimal(raw_input, value)
        contributions.append(
            ReviewContribution(
                contribution_id=contribution_id,
                kind=ReviewSourceKind.MANUAL_INPUT if manual else ReviewSourceKind.UNAVAILABLE,
                source_id=amount_id,
                source_revision=revision.calculation_revision_id,
                detail=(
                    "Exact manual input retained in this saved revision."
                    if manual
                    else "Saved output; exact contribution mapping was not captured for review."
                ),
            )
        )
        amounts.append(
            ReviewAmount(
                amount_id=amount_id,
                casilla_id=casilla_id,
                value=value,
                unit="recorded value",
                rounding="saved decimal; no recalculation",
                contribution_ids=(contribution_id,),
                formula_reference=observation.formula_id if observation is not None else None,
                legal_refs=observation.legal_refs if observation is not None else (),
                source_refs=observation.source_refs if observation is not None else (),
            )
        )
    for (casilla_id, row_index), value in sorted(revision.row_casilla_values.items()):
        amount_id = f"casilla:{casilla_id}:row:{row_index}"
        contribution_id = f"source:{amount_id}"
        contributions.append(
            ReviewContribution(
                contribution_id=contribution_id,
                kind=ReviewSourceKind.UNAVAILABLE,
                source_id=amount_id,
                source_revision=revision.calculation_revision_id,
                detail="Saved row output; review attribution has not been resolved from its captured row source.",
            )
        )
        amounts.append(
            ReviewAmount(
                amount_id=amount_id,
                casilla_id=casilla_id,
                row_id=str(row_index),
                value=value,
                unit="recorded value",
                rounding="saved decimal; no recalculation",
                contribution_ids=(contribution_id,),
            )
        )
    if any(item.kind is ReviewSourceKind.UNAVAILABLE for item in contributions):
        findings.append(
            ReviewFinding(
                code="review.amount_attribution_unavailable",
                detail="Unattributed amounts are saved results, not inferred totals from adjacent ledger rows.",
            )
        )
    return seal_review_snapshot(
        ReviewSnapshotContent(
            selection=selection,
            status=ReviewStatus.INCOMPLETE,
            amounts=tuple(amounts),
            ledger_rows=rows,
            contributions=tuple(contributions),
            evidence=evidence,
            findings=tuple(findings),
        )
    )


def _same_decimal(raw_input: str | None, value: Decimal) -> bool:
    if raw_input is None:
        return False
    try:
        return Decimal(raw_input) == value
    except InvalidOperation:
        return False
