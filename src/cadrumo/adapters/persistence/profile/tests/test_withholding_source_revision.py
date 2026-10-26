"""Source catalogue assertions guard the real encrypted withholding batch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.profile.withholding_observation_workflow import WithholdingObservationWorkflowAdapter
from cadrumo.adapters.persistence.storage.secure_object_namespaces import WITHHOLDING_WORKFLOW_NAMESPACE
from cadrumo.adapters.persistence.storage.sql.secure_object_records import (
    SecureObjectDeletion,
    SecureObjectRevisionAssertion,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.invoice_retencion import build_invoice_withholding_capture
from cadrumo.application.aggregation.ledger_payment_withholding import build_ledger_payment_withholding_capture
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import quarterly_filer_cadence
from cadrumo.application.aggregation.withholding_observation_service import (
    WithholdingObservationMutationError,
    WithholdingObservationService,
    WithholdingSourceCatalogueBaseline,
    WithholdingWindowScope,
)
from cadrumo.application.aggregation.withholding_producer import WithholdingEvidenceCaptureCommand, WithholdingProducer
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.transactions.models import TransactionCatalogue

from .test_ledger_payment_withholding import _YEAR, _payroll_payment, _request
from .test_withholding_monthly_filer_capture import _professional_request, _received_professional_invoice

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]
_BUCKET_ID = "11981198-1198-4198-8198-119811981198"
type _SourceKind = Literal[BindingSourceKind.PAYABLE_INVOICE, BindingSourceKind.LEDGER_TRANSACTION]
_SOURCE_KINDS = pytest.mark.parametrize(
    "source_kind", (BindingSourceKind.PAYABLE_INVOICE, BindingSourceKind.LEDGER_TRANSACTION)
)


@dataclass(frozen=True)
class _SourceCapture:
    command: WithholdingEvidenceCaptureCommand
    scope: WithholdingWindowScope
    revision_id: str
    assertions: Callable[[WithholdingSourceCatalogueBaseline], tuple[SecureObjectRevisionAssertion, ...]]
    edit: Callable[[], None]
    current_revision: Callable[[], str | None]


def _source_capture(objects: SecureObjectRepository, source_kind: _SourceKind) -> _SourceCapture:
    if source_kind is BindingSourceKind.PAYABLE_INVOICE:
        invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        invoice = _received_professional_invoice()
        invoices.save(build_invoice_catalogue((invoice,)))
        loaded_invoices, revision_id = invoices.load_revisioned()
        invoice = loaded_invoices.invoices[invoice.invoice_id]
        capture = build_invoice_withholding_capture(
            invoice,
            catalogue_revision_id=revision_id,
            request=_professional_request(invoice),
            applicable_year=_YEAR,
            cadence=quarterly_filer_cadence(_YEAR),
        )

        def edit_invoice() -> None:
            invoices.save(build_invoice_catalogue((invoice.model_copy(update={"invoice_number": "CORRECTED-001"}),)))

        repository = invoices
        edit = edit_invoice
    else:
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        transaction = _payroll_payment()
        transactions.save(TransactionCatalogue.from_transactions((transaction,)))
        loaded_transactions, revision_id = transactions.load_revisioned()
        transaction = loaded_transactions.transactions[transaction.transaction_id]
        capture = build_ledger_payment_withholding_capture(
            transaction,
            catalogue_revision_id=revision_id,
            request=_request(transaction),
            applicable_year=_YEAR,
            cadence=quarterly_filer_cadence(_YEAR),
        )

        def edit_transaction() -> None:
            transactions.save(
                TransactionCatalogue.from_transactions((transaction.model_copy(update={"group_label": "corrected"}),))
            )

        repository = transactions
        edit = edit_transaction

    def assertions(baseline: WithholdingSourceCatalogueBaseline) -> tuple[SecureObjectRevisionAssertion, ...]:
        assert baseline.source_kind is source_kind
        return repository.revision_assertions(expected_revision_id=baseline.revision_id)

    return _SourceCapture(capture.command, capture.scope, revision_id, assertions, edit, repository.load_revision)


def _workflow(
    objects: SecureObjectRepository, source: _SourceCapture
) -> tuple[WithholdingProducer, WithholdingObservationWorkflowAdapter]:
    workflow = WithholdingObservationWorkflowAdapter(
        objects=objects,
        retenciones=RetencionObservationRepositoryAdapter(objects=objects),
        percepciones=PercepcionObservationRepositoryAdapter(objects=objects),
        source_catalogue_assertions=source.assertions,
    )
    return WithholdingProducer(service=WithholdingObservationService(workflow)), workflow


@_SOURCE_KINDS
def test_source_guarded_capture_reopens_both_projections_and_replays_after_source_edit(
    tmp_path: Path, source_kind: _SourceKind
) -> None:
    """Admission control neither advances the source nor changes the command's replay identity."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        source = _source_capture(profile.repository, source_kind)
        producer, _ = _workflow(profile.repository, source)
        result = producer.capture(
            source.command, cadence=quarterly_filer_cadence(_YEAR), source_catalogue_revision_id=source.revision_id
        )
        assert result is not None and not result.mutation.replayed
        assert source.current_revision() == source.revision_id
        reopened, workflow = _workflow(profile.repository, source)
        state = workflow.load_window(source.scope)
        assert len(state.entries) == 2
        assert all(entry.identity.source_kind == source_kind.value for entry in state.entries)
        assert (
            len(
                RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
                    source.scope.modelo, source.scope.period
                )
            )
            == 1
        )
        assert (
            len(
                PercepcionObservationRepositoryAdapter(objects=profile.repository).load_observations(
                    source.scope.modelo, source.scope.period
                )
            )
            == 1
        )
        source.edit()
        fresh_revision = source.current_revision()
        assert fresh_revision is not None and fresh_revision != source.revision_id
        replay = reopened.capture(
            source.command, cadence=quarterly_filer_cadence(_YEAR), source_catalogue_revision_id=fresh_revision
        )
        assert replay is not None and replay.mutation.replayed
        assert replay.mutation.baseline == result.mutation.baseline
        assert workflow.load_window(source.scope) == state


@_SOURCE_KINDS
def test_source_edit_after_assertion_preparation_refuses_every_withholding_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_kind: _SourceKind
) -> None:
    """A late real source edit aborts projections, head, history, replay key and liability guard together."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        source = _source_capture(profile.repository, source_kind)
        producer, workflow = _workflow(profile.repository, source)
        before = workflow.load_window(source.scope)
        original_apply_batch = profile.repository.apply_batch
        raced = False

        def apply_batch(
            writes: tuple[SecureObjectWrite, ...],
            deletions: tuple[SecureObjectDeletion, ...] = (),
            *,
            assertions: tuple[SecureObjectRevisionAssertion, ...] = (),
        ) -> None:
            nonlocal raced
            if assertions and not raced:
                raced = True
                assert assertions == source.assertions(
                    WithholdingSourceCatalogueBaseline(source_kind=source_kind, revision_id=source.revision_id)
                )
                source.edit()
            original_apply_batch(writes, deletions, assertions=assertions)

        monkeypatch.setattr(profile.repository, "apply_batch", apply_batch)
        with pytest.raises(WithholdingObservationMutationError) as raised:
            producer.capture(
                source.command, cadence=quarterly_filer_cadence(_YEAR), source_catalogue_revision_id=source.revision_id
            )
        assert raced
        assert raised.value.refusal_code == "source_revision_changed"
        fresh_revision = source.current_revision()
        assert fresh_revision is not None and fresh_revision != source.revision_id
        _, reopened = _workflow(profile.repository, source)
        assert reopened.load_window(source.scope) == before
        assert reopened.idempotency_replay(source.scope, source.command.idempotency_key) is None
        assert profile.repository.list_keys(WITHHOLDING_WORKFLOW_NAMESPACE.namespace) == ()
        assert (
            RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
                source.scope.modelo, source.scope.period
            )
            == ()
        )
        assert (
            PercepcionObservationRepositoryAdapter(objects=profile.repository).load_observations(
                source.scope.modelo, source.scope.period
            )
            == ()
        )
        fresh_result = producer.capture(
            source.command, cadence=quarterly_filer_cadence(_YEAR), source_catalogue_revision_id=fresh_revision
        )
        assert fresh_result is not None and not fresh_result.mutation.replayed
        assert len(reopened.load_window(source.scope).entries) == 2
