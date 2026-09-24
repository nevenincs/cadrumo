"""An amendment anchors to the ledger as it stands when the amendment is filed.

Verify anchors a revision to the ledger it was computed from, and an amendment
stands in for verify without ever calling it. So an amended return carried no
anchor at all -- and ``stale_filed_revisions`` skips a revision whose snapshot
is ``None``, which meant an amended filing could never be reported stale no
matter what its books did afterwards.

The capture has to be FRESH rather than inherited. An amendment is filed now,
against the ledger as it stands now; copying the baseline's anchor would assert
that those older facts were the ones checked, backdating the claim by exactly
the interval the amendment exists to correct.

The capture also explains every operator input the draft carries, so an input
the draft grounds in no observation is refused there; calculate refuses the
row-field scalar inputs that would produce one.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from ....application.aggregation.ledger_filing_snapshot import row_fingerprint
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.casilla_membership import (
    reject_row_field_template_scalar_inputs,
    row_field_template_records_by_casilla,
)
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.errors import ModeloValidationError
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .._calculation_helpers import build_typed_observations
from .._calculation_modelo_adjustments import drop_row_field_template_outputs
from ..amendment_actions import _amendment_ledger_anchor

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_AMENDED_AT = datetime(2026, 6, 11, 9, 0, tzinfo=UTC)
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_IVA_RATE = Decimal("0.21")
_OBSERVATION = SimpleNamespace(
    casilla_id="base_retenciones", legal_refs=("art-75",), source_refs=("test-ledger-anchor",)
)
_WORK_BUCKET = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    revision_id = "test-revision"
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_WORK_BUCKET,
            modelo="303",
            filing_year=period.filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_WORK_BUCKET,
        modelo=ModeloCode("303"),
        filing_year=period.filing_year,
        period=period,
        revision_id=revision_id,
        name="303-2026-1T",
        created_at=_T0,
        updated_at=_T0,
    )


def _raw_transaction(provider_id: str, *, amount: Decimal) -> RawTransaction:
    booked_date = date(2026, 2, 15)
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        description=f"IVA transaction {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
) -> Transaction:
    iva_amount = (taxable_base * _IVA_RATE).quantize(Decimal("0.01"))
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, amount=taxable_base + iva_amount),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "material_oficina",
            "taxable_base": taxable_base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva_amount,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _revision(*source_transaction_ids: str):
    return SimpleNamespace(
        source_transaction_ids=tuple(source_transaction_ids),
        observations=(_OBSERVATION,),
        input_values_by_casilla_id={},
        m210_gross_income_source_mode=None,
    )


class _TransactionRepository:
    """Inward fake for the application transaction-catalogue port."""

    def __init__(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    @property
    def bucket_id(self) -> str:
        return _WORK_BUCKET

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self._catalogue
            if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
        )

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in requested
        )

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue:
            filing_date = transaction.raw.value_date or transaction.raw.booked_date
            if start <= filing_date <= end:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=filing_date,
                    )
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=True,
        )

    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue


def test_a_revision_with_no_contributors_anchors_to_nothing_and_says_so() -> None:
    """``None`` rather than an empty snapshot, which would read as a checked ledger."""
    snapshot, evidence = _amendment_ledger_anchor(
        amendment_draft=_revision(),
        work_unit=_work_unit(),
        transaction_repository=_TransactionRepository(TransactionCatalogue.from_transactions(())),
        now=_AMENDED_AT,
    )

    assert snapshot is None
    assert evidence is None


def test_the_anchor_describes_the_ledger_at_amend_time_not_at_baseline_time() -> None:
    """The freshness claim, asserted against a row that moved after the baseline.

    The contributing purchase is restated after the baseline revision exists.
    If the anchor were inherited or recomputed against the older facts, its
    row fingerprint would match the ORIGINAL row; a fresh capture matches the
    restated one.
    """
    sale = _iva_transaction(
        "irene-sale-no-evidence",
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("1000.00"),
    )
    purchase = _iva_transaction(
        "irene-purchase-no-evidence",
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("200.00"),
    )
    revision = _revision(purchase.transaction_id)
    tx_repo = _TransactionRepository(TransactionCatalogue.from_transactions((sale, purchase)))

    # Base and cuota restated against the SAME gross, because the catalogue
    # enforces the identity and derives the transaction id from `raw`.
    restated = purchase.model_copy(
        update={"taxable_base": Decimal("210.00"), "iva_amount": Decimal("32.00")},
    )
    tx_repo.save(TransactionCatalogue.from_transactions((sale, restated)))

    snapshot, evidence = _amendment_ledger_anchor(
        amendment_draft=revision,
        work_unit=_work_unit(),
        transaction_repository=tx_repo,
        now=_AMENDED_AT,
    )

    assert snapshot is not None
    assert evidence is not None
    assert snapshot.captured_at == _AMENDED_AT
    fingerprints = {row.transaction_id: row.fingerprint for row in snapshot.rows}
    assert fingerprints[purchase.transaction_id] == row_fingerprint(restated)
    assert fingerprints[purchase.transaction_id] != row_fingerprint(purchase)


def test_the_anchor_bundles_evidence_covering_every_fingerprinted_contributor() -> None:
    """Snapshot and evidence must describe the same rows or neither explains the filing."""
    sale = _iva_transaction(
        "irene-sale-no-evidence",
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("1000.00"),
    )
    purchase = _iva_transaction(
        "irene-purchase-no-evidence",
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("200.00"),
    )
    revision = _revision(purchase.transaction_id)
    tx_repo = _TransactionRepository(TransactionCatalogue.from_transactions((sale, purchase)))

    snapshot, evidence = _amendment_ledger_anchor(
        amendment_draft=revision,
        work_unit=_work_unit(),
        transaction_repository=tx_repo,
        now=_AMENDED_AT,
    )

    assert snapshot is not None
    assert evidence is not None
    assert evidence.snapshot_fingerprint == snapshot.snapshot_fingerprint
    assert {row.transaction_id for row in evidence.rows} == {row.transaction_id for row in snapshot.rows}


_M193_DECLARED_EXPENSES: CasillaId = validated_casilla_id("decl.gastos-total", surface="test_amendment_ledger_anchor")
_M193_PERCEPTOR_RETENCIONES: CasillaId = validated_casilla_id(
    "perc.retenciones", surface="test_amendment_ledger_anchor"
)


def _m193_revision(
    *,
    casilla_inputs: dict[CasillaId, Decimal],
    source_transaction_ids: tuple[str, ...],
) -> tuple[WorkUnit, CalculationRevision]:
    """Assemble a Modelo 193 draft through the calculation's own output pipeline.

    The engine runs against the published registry, and its observations pass
    through the same row-field drop the calculation applies before it
    persists, so the draft is what calculate would have stored for these
    inputs had it accepted them.
    """
    snapshot = published_snapshot("193", filing_year=2024, period="0A")
    period = Period.from_year_and_code(2024, "0A")
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_WORK_BUCKET,
            modelo="193",
            filing_year=period.filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_WORK_BUCKET,
        modelo=ModeloCode("193"),
        filing_year=period.filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        name="193-2024-0A",
        created_at=_T0,
        updated_at=_T0,
    )
    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=casilla_inputs,
        date_context={"filing_period": period.end_date},
    )
    casilla_values, observations = drop_row_field_template_outputs(
        revision=snapshot.revision,
        casilla_values=dict(engine_result.values),
        observations=build_typed_observations(engine_result=engine_result, snapshot=snapshot),
    )
    input_values = {casilla_id: str(value) for casilla_id, value in casilla_inputs.items()}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=input_values,
        binding_overrides={},
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return work_unit, CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values,
        binding_overrides={},
        casilla_values=casilla_values,
        observations=observations,
        source_transaction_ids=source_transaction_ids,
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _contributing_purchase() -> tuple[Transaction, _TransactionRepository]:
    purchase = _iva_transaction(
        "irene-purchase-no-evidence",
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("200.00"),
    )
    return purchase, _TransactionRepository(TransactionCatalogue.from_transactions((purchase,)))


def test_an_amendment_of_a_revision_without_row_field_inputs_bundles_every_manual_fact() -> None:
    """A declarant scalar keeps its observation, so the amend-time capture explains it."""
    purchase, tx_repo = _contributing_purchase()
    work_unit, draft = _m193_revision(
        casilla_inputs={_M193_DECLARED_EXPENSES: Decimal("250")},
        source_transaction_ids=(purchase.transaction_id,),
    )

    snapshot, evidence = _amendment_ledger_anchor(
        amendment_draft=draft,
        work_unit=work_unit,
        transaction_repository=tx_repo,
        now=_AMENDED_AT,
    )

    assert snapshot is not None
    assert evidence is not None
    (entry,) = evidence.manual_entries
    observation = next(obs for obs in draft.observations if obs.casilla_id == _M193_DECLARED_EXPENSES)
    assert entry.casilla_id == _M193_DECLARED_EXPENSES
    assert entry.value == "250"
    assert set(entry.legal_refs) == {str(ref) for ref in observation.legal_refs}
    assert set(entry.source_refs) == {str(ref) for ref in observation.source_refs}


def test_a_row_field_scalar_input_is_refused_at_calculate_before_any_amendment_could_carry_it() -> None:
    """The amend-time capture rightly refuses an input with no observation; calculate refuses it first.

    A draft holding a scalar ``perc.retenciones`` input is the shape calculate
    stored before it refused such inputs: the row-field drop removed the
    observation, so the capture can ground the input in nothing and refuses.
    The refusal calculate now applies names that same input, so no draft of
    this shape reaches an amendment.
    """
    purchase, tx_repo = _contributing_purchase()
    inputs = {_M193_DECLARED_EXPENSES: Decimal("250"), _M193_PERCEPTOR_RETENCIONES: Decimal("40")}
    work_unit, draft = _m193_revision(casilla_inputs=inputs, source_transaction_ids=(purchase.transaction_id,))
    assert _M193_PERCEPTOR_RETENCIONES in draft.input_values_by_casilla_id
    assert all(obs.casilla_id != _M193_PERCEPTOR_RETENCIONES for obs in draft.observations)

    with pytest.raises(ModeloValidationError) as capture_refusal:
        _amendment_ledger_anchor(
            amendment_draft=draft,
            work_unit=work_unit,
            transaction_repository=tx_repo,
            now=_AMENDED_AT,
        )
    assert capture_refusal.value.context == {"field_name": "legal_refs", "observation_present": False}

    revision = published_snapshot("193", filing_year=2024, period="0A").revision
    with pytest.raises(RegistryValidationError) as calculate_refusal:
        reject_row_field_template_scalar_inputs(revision, inputs)
    assert calculate_refusal.value.context == {
        "casilla_ids": _M193_PERCEPTOR_RETENCIONES,
        "record_ids": ",".join(row_field_template_records_by_casilla(revision)[_M193_PERCEPTOR_RETENCIONES]),
    }
