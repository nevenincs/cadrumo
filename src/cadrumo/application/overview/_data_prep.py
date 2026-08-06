"""Data-prep walkthrough: ordered readiness checklist for one (modelo, period).

:func:`build_data_prep_walkthrough` is the application service backing
``aeat app overview prepare --modelo MODELO --year YEAR --period PERIOD``. It
walks the operator through the data-preparation phase that precedes a modelo
calculation - import transactions, classify them, attach purchase-invoice
evidence, register business invoices, resolve ledger readiness gaps, then start
or resume a modelo work unit - showing each step's current state against the
active profile bucket and the exact next command to run.

The builder is READ-ONLY: it inspects the transaction catalogue, the invoice
catalogue, the purchase-invoice evidence store, the ledger preflight report,
and the modelo work-unit catalogue for the requested ``(modelo, filing_year,
period)`` scope. It persists nothing and never contacts AEAT. Every counter it
reports is already produced by an existing read model
(:func:`~application.ledger.preflight_ledger_tax_readiness`,
:func:`~application.modelo.list_work_units`) or a direct repository read;
this module composes them into one ordered checklist rather than introducing a
new aggregation.

See Also:
    :mod:`~application.overview`
        Sibling read-only overview builders (``status``, ``calendar``,
        ``agenda``, ``backlog``, ``explain``) this module follows the same
        shape as.
    :mod:`~application.ledger`
        Owns :func:`~application.ledger.preflight_ledger_tax_readiness`,
        the classification/category/IVA-fact readiness gate this walkthrough's
        "classify" step reuses rather than re-deriving.
    :class:`~domain.modelos.WorkUnit`
        The modelo work-unit record the final step resolves against.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...domain.transactions import BusinessClassification, TransactionLifecycleState

if TYPE_CHECKING:
    from ...application.ledger import LedgerPreflightReport, PurchaseInvoiceEvidence
    from ...domain.invoices import InvoiceCatalogue
    from ...domain.modelos import WorkUnit
    from ...domain.transactions import Transaction, TransactionCatalogueRepositoryProtocol


class DataPrepStepState(StrEnum):
    """Closed lifecycle state for one data-prep walkthrough step.

    Attributes:
        DONE: The step's readiness condition is fully satisfied for the
            requested scope.
        IN_PROGRESS: Some but not all of the step's underlying facts are
            present (e.g. some transactions classified, others not).
        PENDING: The step has not been started for the requested scope.
        BLOCKED: The step cannot proceed because an upstream capability the
            step depends on is not yet available in this application.
    """

    DONE = "done"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    BLOCKED = "blocked"


class DataPrepStepId(StrEnum):
    """Closed identifier for one ordered data-prep walkthrough step."""

    IMPORT_TRANSACTIONS = "import_transactions"
    CLASSIFY_TRANSACTIONS = "classify_transactions"
    ATTACH_EVIDENCE = "attach_evidence"
    REGISTER_INVOICES = "register_invoices"
    RESOLVE_READINESS = "resolve_readiness"
    START_MODELO_WORK = "start_modelo_work"


class DataPrepStep(BaseModel):
    """One ordered row in the data-prep walkthrough.

    Attributes:
        step_id: Closed :class:`DataPrepStepId` for this row.
        state: Current :class:`DataPrepStepState` against the active
            profile bucket and the requested scope.
        summary: Human-readable progress counter (e.g. "247 transactions
            ingested", "14 unclassified").
        next_command: The exact next ``aeat`` command to run to advance this
            step, or resolve its current gap. Always populated so the
            operator (human or autonomous agent) never has to guess.
    """

    model_config = _STRICT_FROZEN

    step_id: DataPrepStepId
    state: DataPrepStepState
    summary: str
    next_command: str


class DataPrepWalkthrough(BaseModel):
    """Outcome of :func:`build_data_prep_walkthrough`.

    Attributes:
        modelo: Registry-validated AEAT modelo code the walkthrough targets.
        filing_year: Filing year for the requested scope.
        period: Registry period token for the requested scope (e.g. ``1T``).
        steps: Ordered :class:`DataPrepStep` rows; step 1 is always
            ``import_transactions``, the final step is always
            ``start_modelo_work``.
        ready_for_calculation: ``True`` only when every step is
            :attr:`~application.overview.DataPrepStepState.DONE`.
    """

    model_config = _STRICT_FROZEN

    modelo: str
    filing_year: int
    period: str
    steps: tuple[DataPrepStep, ...]
    ready_for_calculation: bool = Field(default=False)


_ACTIVE_LIFECYCLE_STATES = frozenset({TransactionLifecycleState.ACTIVE})
_CLASSIFIED_STATES = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.PERSONAL,
        BusinessClassification.MIXED,
        BusinessClassification.REVIEWED_EXCLUDED,
    },
)


def build_data_prep_walkthrough(
    *,
    bucket_id: str,
    modelo: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    invoice_catalogue: InvoiceCatalogue,
    evidence_records: tuple[PurchaseInvoiceEvidence, ...],
    preflight_report: LedgerPreflightReport,
    work_units: tuple[WorkUnit, ...],
) -> DataPrepWalkthrough:
    """Build the ordered data-prep checklist for one (modelo, period) scope.

    Args:
        bucket_id: Active profile bucket the walkthrough is scoped to.
        modelo: Registry-validated AEAT modelo code (already resolved by the
            caller through the registry describe surface).
        period: Typed filing :class:`~core.Period` for the requested scope.
        transaction_repository: Bound
            :class:`~domain.transactions.TransactionCatalogueRepositoryProtocol`
            for ``bucket_id``.
        invoice_catalogue: Loaded
            :class:`~domain.invoices.InvoiceCatalogue` for ``bucket_id``.
        evidence_records: Loaded purchase-invoice evidence rows
            (``tuple[PurchaseInvoiceEvidence, ...]``) for ``bucket_id``.
        preflight_report: Loaded
            :class:`~application.ledger.LedgerPreflightReport` for
            ``(bucket_id, period)``.
        work_units: Active (non-discarded)
            :class:`~domain.modelos.WorkUnit` rows for ``bucket_id``.

    Returns:
        A :class:`DataPrepWalkthrough` with one ordered step per data-prep
        phase and the exact next command for each.
    """
    catalogue = transaction_repository.load()
    all_transactions = tuple(catalogue.transactions.values())
    active_transactions = tuple(t for t in all_transactions if t.lifecycle_state in _ACTIVE_LIFECYCLE_STATES)
    period_transactions = tuple(
        t for t in active_transactions if period.contains(t.raw.value_date or t.raw.booked_date)
    )

    steps: list[DataPrepStep] = []
    steps.append(_import_step(period, period_transactions))
    steps.append(_classify_step(period_transactions))
    steps.append(_evidence_step(period_transactions, evidence_records))
    steps.append(_invoices_step(period, invoice_catalogue))
    steps.append(_readiness_step(preflight_report))
    steps.append(_work_unit_step(modelo=modelo, filing_year=period.filing_year, period=period, work_units=work_units))

    ready = all(step.state is DataPrepStepState.DONE for step in steps)
    return DataPrepWalkthrough(
        modelo=modelo,
        filing_year=period.filing_year,
        period=period.registry_token,
        steps=tuple(steps),
        ready_for_calculation=ready,
    )


def _import_step(period: Period, period_transactions: tuple[Transaction, ...]) -> DataPrepStep:
    count = len(period_transactions)
    if count == 0:
        return DataPrepStep(
            step_id=DataPrepStepId.IMPORT_TRANSACTIONS,
            state=DataPrepStepState.PENDING,
            summary=f"0 transactions recorded for {period.registry_token} {period.filing_year}.",
            next_command="aeat app ledger import --file <statement.csv>",
        )
    return DataPrepStep(
        step_id=DataPrepStepId.IMPORT_TRANSACTIONS,
        state=DataPrepStepState.DONE,
        summary=f"{count} transaction(s) recorded for {period.registry_token} {period.filing_year}.",
        next_command=f"aeat app ledger list --period {period.registry_token} --year {period.filing_year}",
    )


def _classify_step(period_transactions: tuple[Transaction, ...]) -> DataPrepStep:
    if not period_transactions:
        return DataPrepStep(
            step_id=DataPrepStepId.CLASSIFY_TRANSACTIONS,
            state=DataPrepStepState.PENDING,
            summary="No transactions to classify yet.",
            next_command="aeat app ledger import --file <statement.csv>",
        )
    unclassified = sum(1 for t in period_transactions if t.business_classification not in _CLASSIFIED_STATES)
    if unclassified == 0:
        return DataPrepStep(
            step_id=DataPrepStepId.CLASSIFY_TRANSACTIONS,
            state=DataPrepStepState.DONE,
            summary=f"All {len(period_transactions)} transaction(s) classified.",
            next_command="aeat app ledger allocate --help",
        )
    state = DataPrepStepState.IN_PROGRESS if unclassified < len(period_transactions) else DataPrepStepState.PENDING
    return DataPrepStep(
        step_id=DataPrepStepId.CLASSIFY_TRANSACTIONS,
        state=state,
        summary=f"{unclassified} of {len(period_transactions)} transaction(s) unclassified.",
        next_command="aeat app ledger classify --help",
    )


def _evidence_step(
    period_transactions: tuple[Transaction, ...],
    evidence_records: tuple[PurchaseInvoiceEvidence, ...],
) -> DataPrepStep:
    expense_rows = tuple(
        t
        for t in period_transactions
        if t.business_classification in (BusinessClassification.BUSINESS, BusinessClassification.MIXED)
    )
    if not expense_rows:
        return DataPrepStep(
            step_id=DataPrepStepId.ATTACH_EVIDENCE,
            state=DataPrepStepState.DONE,
            summary=f"{len(evidence_records)} purchase-invoice evidence record(s) registered; "
            "no classified business/mixed expenses require evidence yet.",
            next_command="aeat app ledger evidence add --help",
        )
    missing = sum(1 for t in expense_rows if t.purchase_invoice_evidence_id is None)
    if missing == 0:
        return DataPrepStep(
            step_id=DataPrepStepId.ATTACH_EVIDENCE,
            state=DataPrepStepState.DONE,
            summary=f"All {len(expense_rows)} business/mixed expense(s) have attached evidence "
            f"({len(evidence_records)} evidence record(s) registered).",
            next_command="aeat app ledger evidence list",
        )
    state = DataPrepStepState.IN_PROGRESS if missing < len(expense_rows) else DataPrepStepState.PENDING
    return DataPrepStep(
        step_id=DataPrepStepId.ATTACH_EVIDENCE,
        state=state,
        summary=f"{missing} of {len(expense_rows)} business/mixed expense(s) have no attached evidence.",
        next_command="aeat app ledger evidence add --help",
    )


def _invoices_step(period: Period, invoice_catalogue: InvoiceCatalogue) -> DataPrepStep:
    period_invoices = tuple(inv for inv in invoice_catalogue.values() if period.contains(inv.issued_at))
    count = len(period_invoices)
    if count == 0:
        return DataPrepStep(
            step_id=DataPrepStepId.REGISTER_INVOICES,
            state=DataPrepStepState.PENDING,
            summary=f"0 business invoice(s) registered for {period.registry_token} {period.filing_year}.",
            next_command="aeat app ledger invoice add --help",
        )
    return DataPrepStep(
        step_id=DataPrepStepId.REGISTER_INVOICES,
        state=DataPrepStepState.DONE,
        summary=f"{count} business invoice(s) registered for {period.registry_token} {period.filing_year}.",
        next_command="aeat app ledger invoice list",
    )


def _readiness_step(preflight_report: LedgerPreflightReport) -> DataPrepStep:
    if preflight_report.checked_transaction_count == 0:
        return DataPrepStep(
            step_id=DataPrepStepId.RESOLVE_READINESS,
            state=DataPrepStepState.PENDING,
            summary="No transactions checked yet for calculation readiness.",
            next_command="aeat app ledger import --file <statement.csv>",
        )
    issue_count = len(preflight_report.issues)
    if issue_count == 0:
        return DataPrepStep(
            step_id=DataPrepStepId.RESOLVE_READINESS,
            state=DataPrepStepState.DONE,
            summary=f"{preflight_report.checked_transaction_count} transaction(s) checked; no readiness issues.",
            next_command="aeat app ledger preflight "
            f"--period {preflight_report.period.registry_token} --year {preflight_report.period.filing_year}",
        )
    return DataPrepStep(
        step_id=DataPrepStepId.RESOLVE_READINESS,
        state=DataPrepStepState.IN_PROGRESS,
        summary=f"{issue_count} readiness issue(s) across "
        f"{preflight_report.checked_transaction_count} checked transaction(s).",
        next_command="aeat app ledger preflight "
        f"--period {preflight_report.period.registry_token} --year {preflight_report.period.filing_year}",
    )


def _work_unit_step(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    work_units: tuple[WorkUnit, ...],
) -> DataPrepStep:
    matching = tuple(
        unit
        for unit in work_units
        if unit.modelo == modelo
        and unit.filing_year == filing_year
        and unit.period.registry_token == period.registry_token
    )
    if not matching:
        return DataPrepStep(
            step_id=DataPrepStepId.START_MODELO_WORK,
            state=DataPrepStepState.PENDING,
            summary=f"No Modelo {modelo} work unit exists yet for {period.registry_token} {filing_year}.",
            next_command=f"aeat app modelo work create --modelo {modelo} --year {filing_year} "
            f"--period {period.registry_token}",
        )
    unit = matching[0]
    return DataPrepStep(
        step_id=DataPrepStepId.START_MODELO_WORK,
        state=DataPrepStepState.DONE,
        summary=f"Modelo {modelo} work unit '{unit.name}' is in progress.",
        next_command=f"aeat app modelo work calculate {unit.work_unit_id}",
    )


__all__ = [
    "DataPrepStep",
    "DataPrepStepId",
    "DataPrepStepState",
    "DataPrepWalkthrough",
    "build_data_prep_walkthrough",
]
