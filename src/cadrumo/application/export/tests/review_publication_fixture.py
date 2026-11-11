"""Independent synthetic baseline for saved-review integration acceptance."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.ledger_filing_snapshot import LedgerEvidenceRow
from ..managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ..publication_receipt import (
    PublicationReceipt,
    PublicationState,
    ReadableExportAuthorization,
    ReadablePayloadCategory,
)
from ..review_snapshot import (
    CalculationReviewSelection,
    EvidenceDisposition,
    EvidenceInventoryItem,
    LedgerReviewSelection,
    ReviewAmount,
    ReviewContribution,
    ReviewFinding,
    ReviewSnapshot,
    ReviewSnapshotContent,
    ReviewSourceKind,
    ReviewStatus,
    seal_review_snapshot,
)

PROFILE_ID = UUID(int=101)
PUBLICATION_ID = UUID(int=102)
EXPORTED_AT = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
EXPECTED_SELECTED_AMOUNTS = {"recorded-iva": "99.75", "proven-zero": "0.00", "adjustment": "-3.50"}
LITERAL_COUNTERPARTY = '=IMPORTXML("https://example.invalid", "//amount")'


def acceptance_label(key: str) -> str:
    """Keep semantic labels readable without pretending locale enrollment is complete."""
    notices = {
        "baseline_notice": "Saved baseline; provisional review is not a filing.",
        "ledger_scope_notice": "Explicit ledger snapshot; no Modelo contribution is implied.",
        "external_notes_notice": "Editable findings remain external to canonical facts.",
        "index_only_notice": "Index only; missing original payloads remain missing.",
        "unattributed": "No captured calculation attribution",
    }
    return notices.get(key, key)


def acceptance_snapshot(*, ledger_only: bool = False, newer_revision: bool = False) -> ReviewSnapshot:
    """Capture recorded results intentionally different from the ledger's 25.20 IVA.

    This fixture is a sealed review baseline, not a substitute implementation of
    the canonical revision loader. A second row belongs to the ledger selection
    but has no captured connection to a calculation amount.
    """
    selection = (
        LedgerReviewSelection(profile_id=PROFILE_ID, ledger_snapshot_id="a" * 64)
        if ledger_only
        else CalculationReviewSelection(
            profile_id=PROFILE_ID,
            work_unit_id="b" * 64,
            calculation_revision_id=("d" if newer_revision else "c") * 64,
            modelo="303",
            filing_year=2026,
            period="1T",
            registry_snapshot_ref=RegistrySnapshotRef(modelo="303", revision_id="2026", modelo_year=2026, period="1T"),
            authority_generation="e" * 64,
            registry_digest="f" * 64,
        )
    )
    rows = (
        LedgerEvidenceRow(
            transaction_id="1" * 64,
            fingerprint="2" * 64,
            booked_date="2026-01-12",
            amount=Decimal("145.20"),
            currency="EUR",
            direction="outflow",
            business_classification="business",
            taxable_base=Decimal("120.00"),
            iva_amount=Decimal("25.20"),
            lifecycle_state="confirmed",
            counterparty=LITERAL_COUNTERPARTY,
            invoice_id="invoice-captured",
            attachment_ids=("=invoice-literal",),
            legal_refs=("official-law",),
            source_refs=("official-source",),
        ),
        LedgerEvidenceRow(
            transaction_id="3" * 64,
            fingerprint="4" * 64,
            booked_date="2026-02-18",
            amount=Decimal("18.15"),
            currency="EUR",
            direction="inflow",
            business_classification="personal",
            lifecycle_state="confirmed",
            counterparty="+unattributed-literal",
            legal_refs=("official-law",),
            source_refs=("official-source",),
        ),
    )
    contributions = (
        ()
        if ledger_only
        else (
            ReviewContribution(
                contribution_id="purchase",
                kind=ReviewSourceKind.LEDGER_ROW,
                source_id="1" * 64,
                source_revision="captured-source-v1",
                evidence_ids=("=invoice-literal",),
                detail="Captured contributor only",
            ),
            ReviewContribution(
                contribution_id="operator",
                kind=ReviewSourceKind.MANUAL_INPUT,
                source_id="+manual-literal",
                source_revision="operator-v1",
                detail="@manual-note-literal",
            ),
            ReviewContribution(
                contribution_id="correction",
                kind=ReviewSourceKind.ADJUSTMENT,
                source_id="-adjustment-literal",
                source_revision="adjustment-v1",
                detail="=adjustment-note-literal",
            ),
        )
    )
    amounts = (
        ()
        if ledger_only
        else (
            ReviewAmount(
                amount_id="recorded-iva",
                casilla_id="29",
                value=Decimal("888.88" if newer_revision else "99.75"),
                unit="money",
                currency="EUR",
                rounding="0.01 HALF_UP",
                contribution_ids=("purchase", "correction"),
                formula_reference="=literal-recorded-reference",
            ),
            ReviewAmount(
                amount_id="proven-zero",
                casilla_id="30",
                value=Decimal("0.00"),
                unit="money",
                currency="EUR",
                rounding="0.01 HALF_UP",
                contribution_ids=("operator",),
            ),
            ReviewAmount(
                amount_id="adjustment",
                casilla_id="31",
                value=Decimal("-3.50"),
                unit="money",
                currency="EUR",
                rounding="0.01 HALF_UP",
                contribution_ids=("correction",),
            ),
        )
    )
    return seal_review_snapshot(
        ReviewSnapshotContent(
            selection=selection,
            status=ReviewStatus.PROVISIONAL,
            amounts=amounts,
            ledger_rows=rows,
            contributions=contributions,
            evidence=(
                EvidenceInventoryItem(
                    evidence_id="=invoice-literal",
                    source_revision="captured-source-v1",
                    disposition=EvidenceDisposition.MISSING,
                    reason="Historical payload was not captured",
                ),
            ),
            findings=(
                ReviewFinding(
                    code="historical_payload_missing",
                    detail="Historical payload was not captured; do not substitute current evidence.",
                    related_ids=("=invoice-literal",),
                ),
            ),
        )
    )


def save_acceptance_snapshot(directory: Path, *, ledger_only: bool = False, newer_revision: bool = False) -> Path:
    """Write synthetic sealed bytes for the real strict JSON rehydration boundary."""
    snapshot = acceptance_snapshot(ledger_only=ledger_only, newer_revision=newer_revision)
    path = directory / ("ledger.json" if ledger_only else "newer.json" if newer_revision else "selected.json")
    path.write_text(snapshot.model_dump_json(), encoding="utf-8")
    return path


def acceptance_publication(
    snapshot: ReviewSnapshot,
    *,
    publication_id: UUID = PUBLICATION_ID,
    predecessor: UUID | None = None,
) -> PublicationReceipt:
    """Create local prepared identity; this record does not admit a remote artifact."""
    return PublicationReceipt(
        publication_id=publication_id,
        profile_id=PROFILE_ID,
        root=ArtifactCreationReceipt(
            profile_id=PROFILE_ID,
            root_folder_id="synthetic-managed-root",
            artifact_id="synthetic-managed-root",
            creation_id=UUID(int=103),
            kind=ManagedArtifactKind.ROOT,
        ),
        snapshot_digest=snapshot.snapshot_digest,
        predecessor_publication_id=predecessor,
    )


def acceptance_authorization(
    publication: PublicationReceipt, *, ledger_only: bool = False
) -> ReadableExportAuthorization:
    """Express a local disclosure fixture independently from backup authorization."""
    return ReadableExportAuthorization(
        profile_id=publication.profile_id,
        publication_id=publication.publication_id,
        root_folder_id=publication.root.artifact_id,
        snapshot_digest=publication.snapshot_digest,
        payload_categories=(ReadablePayloadCategory.LEDGER,)
        if ledger_only
        else (ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.LEDGER),
        disclosure_digest="5" * 64,
    )


def completed_acceptance_receipt(publication: PublicationReceipt) -> PublicationReceipt:
    """Exercise ordered receipt transitions; no provider completion is asserted."""
    child = ArtifactCreationReceipt(
        profile_id=publication.profile_id,
        root_folder_id=publication.root.artifact_id,
        artifact_id=f"synthetic-sheet-{publication.publication_id}",
        parent_id=publication.root.artifact_id,
        creation_id=UUID(int=104),
        kind=ManagedArtifactKind.REVIEW_SHEET,
        publication_id=publication.publication_id,
    )
    current = publication.advance(PublicationState.REMOTE_CREATED, artifacts=(child,))
    for state in (PublicationState.POPULATED, PublicationState.VERIFIED, PublicationState.PUBLISHED):
        current = current.advance(state)
    return current
