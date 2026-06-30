"""Real-behavior tests for the evidence-driven LLM split application path.

Exercises :func:`suggest_evidence_split` and :func:`apply_evidence_split`
against real SQLite persistence in an isolated profile, with a concrete
in-process split proposer injected by dependency injection (no mocks). Covers
the Stage-3b split contract:

* the model proposes per-child PROPORTIONS and selects each child's expense
  category + IVA category; the system DERIVES each child's euro amount (summing
  exactly to the parent) and the regulated rate / base / amount from the
  registry (never the model);
* applying a reviewed suggestion drives the single-writer
  :func:`split_transaction` (parent -> SPLIT, children ACTIVE) and then stamps
  each child's classification, derived numbers, parent-invoice evidence link,
  and ``llm:<model>`` provenance through the manual write;
* the persisted child state survives a save/load roundtrip.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.categories import SpendingCategory
from ....domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ....domain.iva import InvoiceKind, IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    LLMSplitChild,
    LLMSplitResponse,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    LLMProvider,
    LLMSplitApplyResult,
    LLMSplitSuggestion,
    apply_evidence_classification,
    apply_evidence_split,
    suggest_evidence_split,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_BUCKET = "bucket-split"


class _FixedSplitProposer:
    """Concrete in-process split proposer returning a fixed proposal.

    Implements the :class:`aeat.domain.transactions.LLMSplitProposer` protocol
    (``decided_by`` + ``propose_split``) with no subprocess or network I/O, so
    the application + persistence stack runs end to end offline. Records the
    evidence text it was handed so a test can assert evidence reached the prompt.
    """

    def __init__(self, *, response: LLMSplitResponse, model: str = "test-model") -> None:
        self._response = response
        self._model = model
        self.last_evidence_text: str | None = None

    @property
    def decided_by(self) -> str:
        return f"llm:claude:{self._model}"

    def propose_split(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMSplitResponse:
        self.last_evidence_text = evidence_text
        return self._response


def _two_line_proposal() -> LLMSplitResponse:
    """A 60/40 two-child proposal, both domestic-general 21% business lines."""
    return LLMSplitResponse(
        children=(
            LLMSplitChild(
                proportion=Decimal("0.6"),
                category=SpendingCategory.MATERIAL_OFICINA,
                iva_category=IvaCategory.DOMESTIC_GENERAL_21,
                evidence_citation="material de oficina",
            ),
            LLMSplitChild(
                proportion=Decimal("0.4"),
                category=SpendingCategory.SOFTWARE_SUSCRIPCION,
                iva_category=IvaCategory.DOMESTIC_GENERAL_21,
                evidence_citation="licencia software",
            ),
        ),
        reason="invoice has two distinct line items",
    )


@pytest.fixture
def repositories(
    tmp_path: Path,
) -> Iterator[tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository]]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        objects = profile.repository
        yield (
            TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects),
            BucketEventHistoryRepository(objects=objects),
            objects,
        )


def _seed_received_invoice(objects: SecureObjectRepository, *, invoice_number: str = "P-2026-001") -> str:
    """Persist one RECEIVED purchase invoice in the bucket and return its id."""
    line = InvoiceLine(
        description="Material oficina",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    invoice = Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": _BUCKET,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 5, 2),
            "counterparty_name": "Proveedor Mixto SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        },
    )
    InvoiceCatalogueRepository(objects=objects).save(InvoiceCatalogue.from_invoices((invoice,)))
    return invoice.invoice_id


def _seed_parent(
    repository: TransactionCatalogueRepository,
    *,
    amount: Decimal = Decimal("121.00"),
    evidence_id: str | None = None,
) -> str:
    """Persist one ACTIVE parent transaction and return its id."""
    raw = RawTransaction(
        transaction_id="row-split-parent",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=amount,
        currency="EUR",
        counterparty="Proveedor Mixto SL",
        description="mixed supplier invoice",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_NOW,
            provider_name="csv",
        ),
        raw_fields={"Concepto": "mixed supplier invoice"},
    )
    fields: dict[str, object] = {"raw": raw, "direction": TransactionDirection.OUTGOING, "source_jurisdiction": "ES"}
    if evidence_id is not None:
        fields["purchase_invoice_evidence_id"] = evidence_id
    tx = Transaction.model_validate(fields)
    repository.save(TransactionCatalogue.from_transactions([tx]))
    return tx.transaction_id


# ---------------------------------------------------------------------------
# suggest: model proposes proportions, system derives amounts + substrate
# ---------------------------------------------------------------------------


def test_suggest_derives_child_amounts_summing_to_parent(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    gross = Decimal("121.00")
    tx_id = _seed_parent(repository, amount=gross)

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    assert isinstance(suggestion, LLMSplitSuggestion)
    assert suggestion.parent_amount == gross
    assert len(suggestion.children) == 2
    # The derived amounts sum EXACTLY to the parent gross to the cent.
    assert sum((child.amount for child in suggestion.children), Decimal("0")) == gross
    # 60/40 of 121.00.
    assert suggestion.children[0].amount == Decimal("72.60")
    assert suggestion.children[1].amount == Decimal("48.40")
    assert suggestion.provenance == "llm:claude:test-model"


def test_suggest_derives_each_child_substrate_from_registry(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    for child in suggestion.children:
        assert child.iva_category is IvaCategory.DOMESTIC_GENERAL_21
        assert child.rate_derivable is True
        # The registry rate, not a model-emitted number.
        assert child.iva_rate == Decimal("0.21")
        # base + iva reconstitutes the derived child amount to the cent.
        assert child.taxable_base is not None and child.iva_amount is not None
        assert child.taxable_base + child.iva_amount == child.amount


def test_suggest_injects_evidence_text_when_reading(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    # No linked evidence -> _resolve_evidence_text returns (None, None) and the
    # proposer is handed None; this proves read_evidence does not fabricate text
    # nor require a cloud acknowledgement when there is nothing to read.
    tx_id = _seed_parent(repository)
    proposer = _FixedSplitProposer(response=_two_line_proposal())

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=proposer,
        transaction_repository=repository,
        read_evidence=True,
    )

    assert proposer.last_evidence_text is None
    assert suggestion.evidence_id is None


# ---------------------------------------------------------------------------
# apply: single-writer split + per-child classification, evidence, provenance
# ---------------------------------------------------------------------------


def test_apply_splits_parent_and_classifies_children(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    gross = Decimal("121.00")
    tx_id = _seed_parent(repository, amount=gross)

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert isinstance(result, LLMSplitApplyResult)
    assert result.classified_child_count == 2
    assert len(result.child_transaction_ids) == 2

    # Reload from secure storage: the persisted state is the contract, not the
    # in-memory return value (save/load roundtrip).
    catalogue = repository.load()
    parent = catalogue.get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.SPLIT

    persisted_sum = Decimal("0")
    for child_id in result.child_transaction_ids:
        child = catalogue.get(child_id)
        assert child is not None
        assert child.lifecycle_state is TransactionLifecycleState.ACTIVE
        assert child.business_classification is BusinessClassification.BUSINESS
        assert child.iva_category is IvaCategory.DOMESTIC_GENERAL_21
        assert child.iva_rate == Decimal("0.21")
        assert child.classified_by == "llm:claude:test-model"
        # Each child's regulated numbers reconstitute its own magnitude.
        assert child.taxable_base is not None and child.iva_amount is not None
        assert child.taxable_base + child.iva_amount == child.raw.amount
        persisted_sum += child.raw.amount
    # The children's magnitudes sum back to the parent gross.
    assert persisted_sum == gross


def test_apply_links_parent_invoice_evidence_to_each_child(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, objects = repositories
    # A real RECEIVED invoice the parent references; the per-child write re-verifies
    # the reference exists in the invoice catalogue, so the link must be genuine.
    evidence_id = _seed_received_invoice(objects)
    tx_id = _seed_parent(repository, evidence_id=evidence_id)

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    catalogue = repository.load()
    for child_id in result.child_transaction_ids:
        child = catalogue.get(child_id)
        assert child is not None
        assert child.purchase_invoice_evidence_id == evidence_id


def test_apply_child_numbers_are_registry_derived_not_model(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    # The proposer supplies only proportions + categories; it never emits a euro
    # amount or a rate. The persisted rate must be the registry's 0.21.
    tx_id = _seed_parent(repository, amount=Decimal("242.00"))

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    catalogue = repository.load()
    children = []
    for child_id in result.child_transaction_ids:
        child = catalogue.get(child_id)
        assert child is not None
        children.append(child)
    # 60/40 of 242.00 -> 145.20 / 96.80, each at 21% registry rate.
    assert sorted(child.raw.amount for child in children) == [Decimal("96.80"), Decimal("145.20")]
    for child in children:
        assert child.iva_rate == Decimal("0.21")


# ---------------------------------------------------------------------------
# no-split verdict: one child = "single line", routed to in-place classification
# ---------------------------------------------------------------------------


def _single_line_proposal() -> LLMSplitResponse:
    """A single-child proposal — the model's 'no split warranted' verdict."""
    return LLMSplitResponse(
        children=(
            LLMSplitChild(
                proportion=Decimal("1.0"),
                category=SpendingCategory.MATERIAL_OFICINA,
                iva_category=IvaCategory.DOMESTIC_GENERAL_21,
                evidence_citation="material de oficina",
            ),
        ),
        reason="invoice is a single line at one rate",
    )


def test_single_child_suggestion_does_not_recommend_split(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_single_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    assert suggestion.recommends_split is False
    assert len(suggestion.children) == 1
    # The lone child carries the whole gross and the registry-derived substrate.
    assert suggestion.children[0].amount == Decimal("121.00")
    assert suggestion.children[0].iva_rate == Decimal("0.21")


def test_apply_evidence_split_refuses_a_no_split_verdict(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_single_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    with pytest.raises(TransactionValidationError, match="no-split verdict"):
        apply_evidence_split(
            suggestion,
            bucket_id=_BUCKET,
            transaction_repository=repository,
            bucket_event_repository=events,
            occurred_at=_NOW,
        )


def test_apply_evidence_classification_writes_in_place_from_the_lone_child(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_single_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    result = apply_evidence_classification(
        suggestion,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    # The parent is classified in place — NOT split; no child rows are created.
    catalogue = repository.load()
    parent = catalogue.get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert parent.business_classification is BusinessClassification.BUSINESS
    assert parent.category_id == SpendingCategory.MATERIAL_OFICINA.value
    assert parent.iva_category is IvaCategory.DOMESTIC_GENERAL_21
    # Registry-derived substrate for the whole gross, stamped with llm provenance.
    assert parent.iva_rate == Decimal("0.21")
    assert parent.taxable_base is not None and parent.iva_amount is not None
    assert parent.taxable_base + parent.iva_amount == Decimal("121.00")
    assert result.transaction.classified_by == "llm:claude:test-model"


def test_apply_evidence_classification_refuses_a_multi_child_split(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    with pytest.raises(TransactionValidationError, match="recommends a split"):
        apply_evidence_classification(suggestion, bucket_id=_BUCKET, transaction_repository=repository)
