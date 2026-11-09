"""Pure installed-workbench search snapshot assembly.

The installed composition root supplies already-built public projections and
their already-admitted destinations.  This module keeps only the resulting
redacted documents; it neither retains the source projections nor resolves a
repository, token, network client, or business authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Never, SupportsIndex, override

from pydantic import SecretStr

from ...core.period import Period
from ...domain.modelos.ledger_filing_snapshot import FiledRegisterState
from ...domain.modelos.work_unit import WorkUnitState
from ..aeat_sync.workspace import (
    AeatSyncNotificationReadState,
    AeatSyncReconciliationState,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceReconciliationRowV1,
)
from ..ledger.workspace import LedgerWorkspaceProjectionV1
from ..modelo.declarations_list import DeclarationListGroup
from ..modelo.declarations_list_projection import ModeloDeclarationListRowV1
from ..modelo.declarations_workspace_contracts import DeclarationsWorkspaceProjectionV1
from ..modelo.workspace_models import ModeloWorkspaceCapabilityDisposition, ModeloWorkspaceProjectionV1
from ..review.filter import LedgerReviewStatus
from .workbench import (
    WorkbenchDestinationAdmission,
    WorkbenchFilingAddress,
    WorkbenchModeloAddress,
    WorkbenchRevisionAddress,
    WorkbenchSearchDocument,
    WorkbenchSearchKind,
    WorkbenchSearchLabelKey,
    WorkbenchSearchService,
    WorkbenchSearchSource,
    WorkbenchSearchStatus,
)


@dataclass(frozen=True, slots=True)
class InstalledWorkbenchSearchSnapshotV1:
    """One immutable, redacted document snapshot for the installed palette."""

    documents: tuple[WorkbenchSearchDocument, ...]

    def service(self) -> WorkbenchSearchService:
        """Build the pure query service over this exact snapshot."""
        return WorkbenchSearchService(self.documents)

    @override
    def __reduce_ex__(self, protocol: SupportsIndex, /) -> Never:
        """Refuse Python serialization of the ephemeral identity seed set."""
        del protocol
        raise TypeError("installed workbench search snapshots are memory-only")


def assemble_installed_workbench_search_snapshot(
    *,
    ledger: LedgerWorkspaceProjectionV1,
    declarations: DeclarationsWorkspaceProjectionV1,
    aeat_sync: AeatSyncWorkspaceProjectionV1,
    modelo: tuple[ModeloWorkspaceProjectionV1, ...],
    ledger_admission: WorkbenchDestinationAdmission,
    declarations_admission: WorkbenchDestinationAdmission,
    aeat_sync_admission: WorkbenchDestinationAdmission,
) -> InstalledWorkbenchSearchSnapshotV1:
    """Derive redacted documents from preloaded current workspace projections.

    This is intentionally a one-shot assembly operation.  The caller decides
    when fresh projections are authoritative and invokes it again; searching a
    returned service never reads state or rebuilds its documents.
    """
    _require_destination(ledger_admission, "workbench.ledger")
    _require_destination(declarations_admission, "workbench.declarations")
    _require_destination(aeat_sync_admission, "workbench.aeat_sync")

    documents: list[WorkbenchSearchDocument] = []
    documents.extend(_ledger_documents(ledger, ledger_admission))
    documents.extend(_ledger_evidence_documents(ledger, ledger_admission))
    documents.extend(_declarations_documents(declarations, declarations_admission))
    documents.extend(_aeat_sync_documents(aeat_sync, aeat_sync_admission))
    documents.extend(_modelo_documents(modelo, declarations_admission))
    return InstalledWorkbenchSearchSnapshotV1(tuple(documents))


def _require_destination(admission: WorkbenchDestinationAdmission, destination: str) -> None:
    """Refuse a projection whose admission belongs to another workbench area."""
    if admission.destination != destination:
        raise ValueError(f"installed search admission must target {destination!r}")


def _ledger_documents(
    projection: LedgerWorkspaceProjectionV1,
    admission: WorkbenchDestinationAdmission,
) -> tuple[WorkbenchSearchDocument, ...]:
    """Project Ledger entries so the operator can find them by what they recall.

    The counterparty, description, date and amount are what someone actually
    searches for; the transaction id is what the machine addresses the row by,
    and it stays out of the matchable terms because nobody types a 64-character
    hex string into a command palette.
    """
    return tuple(
        WorkbenchSearchDocument(
            kind=WorkbenchSearchKind.LEDGER_ENTRY,
            source=WorkbenchSearchSource.LEDGER_ENTRY,
            status=_ledger_status(row.review_status),
            label_key=WorkbenchSearchLabelKey.LEDGER_ENTRY,
            admission=admission,
            identity_basis=SecretStr(row.transaction_id),
            content_terms=tuple(
                term
                for term in (
                    row.counterparty,
                    row.description,
                    row.date,
                    row.amount,
                    row.currency,
                )
                if term
            ),
        )
        for row in projection.entries
    )


def _ledger_status(value: str) -> WorkbenchSearchStatus:
    """Translate the Ledger's closed review state without inferring content."""
    return {
        LedgerReviewStatus.PENDING: WorkbenchSearchStatus.LEDGER_ENTRY_NEEDS_REVIEW,
        LedgerReviewStatus.REVIEWED: WorkbenchSearchStatus.LEDGER_ENTRY_CLASSIFIED,
        LedgerReviewStatus.SKIPPED: WorkbenchSearchStatus.LEDGER_ENTRY_CLASSIFIED,
        LedgerReviewStatus.EXCLUDED: WorkbenchSearchStatus.LEDGER_ENTRY_CLASSIFIED,
    }[LedgerReviewStatus(value)]


def _ledger_evidence_documents(
    projection: LedgerWorkspaceProjectionV1,
    admission: WorkbenchDestinationAdmission,
) -> tuple[WorkbenchSearchDocument, ...]:
    """Project authoritative sealed-revision drift as stale Ledger evidence."""
    return tuple(
        WorkbenchSearchDocument(
            kind=WorkbenchSearchKind.LEDGER_EVIDENCE,
            source=WorkbenchSearchSource.LEDGER_EVIDENCE,
            status=WorkbenchSearchStatus.LEDGER_EVIDENCE_STALE,
            label_key=WorkbenchSearchLabelKey.LEDGER_EVIDENCE,
            admission=admission,
            identity_basis=SecretStr(row.calculation_revision_id),
        )
        for row in projection.affected_declarations
        if row.changed_count or row.removed_count or row.register_state is FiledRegisterState.CHANGED
    )


def _declarations_documents(
    projection: DeclarationsWorkspaceProjectionV1,
    admission: WorkbenchDestinationAdmission,
) -> tuple[WorkbenchSearchDocument, ...]:
    """Project declaration, calculation, filing, and lifecycle coordinates."""
    documents: list[WorkbenchSearchDocument] = []
    for row in projection.declarations:
        documents.append(
            WorkbenchSearchDocument(
                kind=WorkbenchSearchKind.DECLARATION,
                source=WorkbenchSearchSource.DECLARATION,
                status=_declaration_status(row.state, row.has_current_calculation, row.has_current_filing),
                label_key=WorkbenchSearchLabelKey.DECLARATION,
                address=WorkbenchModeloAddress(modelo=row.modelo, filing_year=row.filing_year, period=row.period),
                admission=admission,
            )
        )
    for row in projection.calculation_revisions:
        documents.append(
            WorkbenchSearchDocument(
                kind=WorkbenchSearchKind.REVISION,
                source=WorkbenchSearchSource.REVISION,
                status=(
                    WorkbenchSearchStatus.REVISION_CURRENT
                    if row.is_current
                    else WorkbenchSearchStatus.REVISION_SUPERSEDED
                ),
                label_key=WorkbenchSearchLabelKey.REVISION,
                address=WorkbenchRevisionAddress(
                    modelo=row.modelo,
                    filing_year=row.filing_year,
                    period=row.period,
                    calculation_revision_id=row.calculation_revision_id,
                ),
                admission=admission,
            )
        )
    for row in projection.filings:
        documents.append(
            WorkbenchSearchDocument(
                kind=WorkbenchSearchKind.FILING,
                source=WorkbenchSearchSource.FILING,
                status=(
                    WorkbenchSearchStatus.FILING_ACCEPTED
                    if row.aeat_accepted
                    else WorkbenchSearchStatus.FILING_SUBMITTED
                ),
                label_key=WorkbenchSearchLabelKey.FILING,
                address=WorkbenchFilingAddress(
                    modelo=row.modelo,
                    filing_year=row.filing_year,
                    period=row.period,
                    filing_record_id=row.filing_record_id,
                ),
                admission=admission,
            )
        )
    for row in projection.lifecycle:
        documents.append(
            WorkbenchSearchDocument(
                kind=WorkbenchSearchKind.HISTORY,
                source=WorkbenchSearchSource.HISTORY,
                status=WorkbenchSearchStatus.HISTORY_OBSERVED,
                label_key=WorkbenchSearchLabelKey.HISTORY,
                address=WorkbenchModeloAddress(modelo=row.modelo, filing_year=row.filing_year, period=row.period),
                admission=admission,
                identity_basis=SecretStr(row.fact_id),
            )
        )
    return tuple(documents)


def _declaration_status(
    state: WorkUnitState,
    has_current_calculation: bool,
    has_current_filing: bool,
) -> WorkbenchSearchStatus:
    """Preserve the declaration owner state in the search status vocabulary."""
    if has_current_filing:
        return WorkbenchSearchStatus.DECLARATION_FILED
    if has_current_calculation:
        return WorkbenchSearchStatus.DECLARATION_READY
    return {
        WorkUnitState.BORRADOR: WorkbenchSearchStatus.DECLARATION_DRAFT,
        WorkUnitState.DESCARTADO: WorkbenchSearchStatus.DECLARATION_NEEDS_ATTENTION,
    }[state]


def _reconciliation_identity_basis(row: AeatSyncWorkspaceReconciliationRowV1) -> SecretStr:
    return SecretStr(
        "|".join(
            (
                str(row.modelo),
                str(row.filing_year),
                row.period.registry_token,
                row.work_unit_id or "",
                row.evidence_kind.value if row.evidence_kind is not None else "",
                row.evidence_id or "",
                row.calculation_revision_id or row.comparison_id or "",
            )
        )
    )


def _aeat_sync_documents(
    projection: AeatSyncWorkspaceProjectionV1,
    admission: WorkbenchDestinationAdmission,
) -> tuple[WorkbenchSearchDocument, ...]:
    """Project reconciliation and notification state without protected payloads."""
    documents: list[WorkbenchSearchDocument] = []
    for row in projection.reconciliation:
        documents.append(
            WorkbenchSearchDocument(
                kind=WorkbenchSearchKind.RECONCILIATION,
                source=WorkbenchSearchSource.RECONCILIATION,
                status=(
                    WorkbenchSearchStatus.RECONCILIATION_OPEN
                    if row.reconciliation_state is AeatSyncReconciliationState.UNRESOLVED
                    else WorkbenchSearchStatus.RECONCILIATION_RESOLVED
                ),
                label_key=WorkbenchSearchLabelKey.RECONCILIATION,
                admission=admission,
                identity_basis=_reconciliation_identity_basis(row),
            )
        )
    for row in projection.notifications:
        selection_key = row.selection_key
        if selection_key is None:  # pragma: no cover - projection construction rejects this
            raise ValueError("installed search requires notification selection identities")
        documents.append(
            WorkbenchSearchDocument(
                kind=WorkbenchSearchKind.NOTIFICATION,
                source=WorkbenchSearchSource.NOTIFICATION,
                status=(
                    WorkbenchSearchStatus.NOTIFICATION_UNREAD
                    if row.read_state is AeatSyncNotificationReadState.UNREAD
                    else WorkbenchSearchStatus.NOTIFICATION_READ
                ),
                label_key=WorkbenchSearchLabelKey.NOTIFICATION,
                admission=admission,
                identity_basis=SecretStr(selection_key),
            )
        )
    return tuple(documents)


def _modelo_documents(
    projections: tuple[ModeloWorkspaceProjectionV1, ...],
    admission: WorkbenchDestinationAdmission,
) -> tuple[WorkbenchSearchDocument, ...]:
    """Project each already-admitted Modelo workspace by its natural address."""
    return tuple(
        WorkbenchSearchDocument(
            kind=WorkbenchSearchKind.MODELO,
            source=WorkbenchSearchSource.MODELO,
            status=(
                WorkbenchSearchStatus.MODELO_AVAILABLE
                if any(
                    capability.disposition is ModeloWorkspaceCapabilityDisposition.AVAILABLE
                    for capability in projection.capabilities
                )
                else WorkbenchSearchStatus.MODELO_UNAVAILABLE
            ),
            label_key=WorkbenchSearchLabelKey.MODELO,
            address=WorkbenchModeloAddress(
                modelo=projection.target.modelo,
                filing_year=projection.target.filing_year,
                period=projection.target.period,
            ),
            admission=admission,
        )
        for projection in projections
    )


DeclarationSearchAddress = tuple[str, int, str]
"""One declaration's modelo, filing year and period code: how a hit finds the row it came from."""


def declaration_search_address(row: ModeloDeclarationListRowV1) -> DeclarationSearchAddress | None:
    """Address a worded list row, or ``None`` when it names no period to open."""
    if row.filing_year is None or row.period_code is None:
        return None
    return row.modelo, row.filing_year, row.period_code


def searchable_declaration_rows(
    rows: tuple[ModeloDeclarationListRowV1, ...],
) -> dict[DeclarationSearchAddress, ModeloDeclarationListRowV1]:
    """Keep one row for each address, local work before a row that is only due or held by the AEAT."""
    kept: dict[DeclarationSearchAddress, ModeloDeclarationListRowV1] = {}
    for row in rows:
        address = declaration_search_address(row)
        if address is None:
            continue
        held = kept.get(address)
        if held is None or (held.work_unit_id is None and row.work_unit_id is not None):
            kept[address] = row
    return kept


def declaration_list_documents(
    rows: dict[DeclarationSearchAddress, ModeloDeclarationListRowV1],
    admission: WorkbenchDestinationAdmission,
) -> tuple[WorkbenchSearchDocument, ...]:
    """Project worded list rows so the filer finds a declaration by the words the list shows for it.

    The modelo's number and title, the period in the filer's language and the
    state words are what someone types into a palette; the enums alone could
    only answer to the vocabulary of the code.
    """
    _require_destination(admission, "workbench.declarations")
    return tuple(
        WorkbenchSearchDocument(
            kind=WorkbenchSearchKind.DECLARATION,
            source=WorkbenchSearchSource.DECLARATION,
            status=_list_row_status(row.group),
            label_key=WorkbenchSearchLabelKey.DECLARATION,
            address=WorkbenchModeloAddress(
                modelo=row.modelo, filing_year=year, period=Period.from_year_and_code(year, period_code)
            ),
            admission=admission,
            content_terms=tuple(
                term
                for term in (row.modelo_number, row.modelo_title, row.period_words, row.state_words, row.group_words)
                if term is not None and term != ""
            ),
            precedence=0 if row.work_unit_id is not None else 1,
        )
        for (_, year, period_code), row in rows.items()
    )


def _list_row_status(group: DeclarationListGroup) -> WorkbenchSearchStatus:
    """Translate the list's closed group into the search status vocabulary."""
    return {
        DeclarationListGroup.ATTENTION: WorkbenchSearchStatus.DECLARATION_NEEDS_ATTENTION,
        DeclarationListGroup.IN_PROGRESS: WorkbenchSearchStatus.DECLARATION_IN_PROGRESS,
        DeclarationListGroup.READY: WorkbenchSearchStatus.DECLARATION_READY,
        DeclarationListGroup.NOT_STARTED: WorkbenchSearchStatus.DECLARATION_DRAFT,
        DeclarationListGroup.MAYBE: WorkbenchSearchStatus.DECLARATION_DRAFT,
        DeclarationListGroup.RECORDED: WorkbenchSearchStatus.DECLARATION_FILED,
        DeclarationListGroup.AEAT_UNLINKED: WorkbenchSearchStatus.DECLARATION_FILED,
    }[group]


__all__ = [
    "DeclarationSearchAddress",
    "InstalledWorkbenchSearchSnapshotV1",
    "assemble_installed_workbench_search_snapshot",
    "declaration_list_documents",
    "declaration_search_address",
    "searchable_declaration_rows",
]
