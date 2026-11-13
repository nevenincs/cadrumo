"""Figures entered by hand for an income family the application does not calculate clear its finding while the rows stand.

The Modelo 100 raises a blocking finding for each income family the ejercicio's
ledger holds and no calculator covers. Entering the family's casillas clears it,
bound to the ledger rows present at entry: the operator layer keeps the digest
of the family's rows, a recalculation replays it unchanged, and a row added
afterwards raises the finding again, saying the rows changed. A partial clear
keeps the entry; clearing every casilla of the family drops it.

Real behaviour throughout: an isolated encrypted profile with its ledger, the
bundled authority, the production admission, edit executor and recalculation.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.aggregation.income_family_not_computed import income_family_casilla_ids
from ....application.modelo.edit_models import (
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloScalarEditIntentV1,
)
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId
from ....domain.calculations.registry.irpf_income_categories import irpf_income_family_casilla_sections
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence, CalculationSourceIssue
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .test_m100_carry_attestation import _EVERY_CARRY, _FACTS, _attest, _renta_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CAPITAL = "capital_mobiliario"
_REASON = "income_family_not_computed"


def _interest(provider_id: str, year: int) -> Transaction:
    booked = date(year, 6, 15)
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked,
        value_date=booked,
        amount=Decimal("120.00"),
        currency="EUR",
        counterparty="Banco SA",
        description="intereses",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(year, 7, 1, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": _CAPITAL,
            # The ledger readiness check asks every business income row for its base, whatever its family.
            "taxable_base": Decimal("120.00"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(year, 7, 1, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _family_casillas(renta: SeededOperatorWork) -> tuple[CasillaId, CasillaId]:
    """Two writable casillas of the capital family, as the edition's own sections name them."""
    unit = renta.work_unit
    revision = renta.operation.snapshot(
        "100", filing_year=unit.filing_year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    ).revision
    sections = irpf_income_family_casilla_sections(effective_date=unit.period.end_date, authority=renta.operation)
    family = income_family_casilla_ids(revision, {str(token): tokens for token, tokens in sections.items()})[_CAPITAL]
    writable = sorted(
        entry.casilla_id
        for entry in renta.baseline().permitted_surface
        if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1)
        and entry.casilla_id in family
        and entry.data_type in {"money", "decimal"}
        and ModeloEditScalarIntentKind.SET_TYPED_VALUE in entry.allowed_intents
    )
    first, second, *_ = writable
    return first, second


def _set(casilla_id: CasillaId, value: str) -> ModeloScalarEditIntentV1:
    return ModeloScalarEditIntentV1(
        address=ModeloEditScalarAddressV1(casilla_id=casilla_id),
        kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
        value=Decimal(value),
    )


def _restore(casilla_id: CasillaId) -> ModeloScalarEditIntentV1:
    return ModeloScalarEditIntentV1(
        address=ModeloEditScalarAddressV1(casilla_id=casilla_id), kind=ModeloEditScalarIntentKind.RESTORE_SOURCE_VALUE
    )


def _family_issues(head: CalculationRevision) -> list[CalculationSourceIssue]:
    return [
        issue
        for issue in head.source_issues
        if issue.reason == _REASON and issue.source_ref == f"income-family:{_CAPITAL}"
    ]


def _entries(head: CalculationRevision) -> dict[str, str]:
    assert head.operator_layer is not None
    return dict(head.operator_layer.income_family_entry_digests)


def test_an_entry_clears_the_finding_until_the_rows_change_and_a_full_clear_drops_it(tmp_path: Path) -> None:
    year = max(_renta_years())
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        renta.ports.transaction_repository.save(TransactionCatalogue.from_transactions([_interest("interest-1", year)]))
        first, second = _family_casillas(renta)
        carries = tuple(_attest(binding_id) for binding_id in _EVERY_CARRY)

        # Answering the carries alone calculates, and the family stands as a finding: nothing was entered for it.
        assert renta.apply(binding=carries).refusal is None
        unentered = renta.require_head()
        assert _entries(unentered) == {}
        (raised,) = _family_issues(unentered)
        assert raised.fact is None

        # Entering the family's figures clears it, bound to the one row present.
        assert renta.apply(scalar=(_set(first, "100"), _set(second, "20"))).refusal is None
        entered = renta.require_head()
        bound = _entries(entered)
        assert set(bound) == {_CAPITAL}
        assert _family_issues(entered) == []

        # Calculating again replays the entry exactly as made.
        replayed = renta.recalculate()
        assert _entries(replayed) == bound
        assert _family_issues(replayed) == []

        # A row added afterwards raises the finding again, saying the rows changed since the entry.
        renta.ports.transaction_repository.save(
            TransactionCatalogue.from_transactions([_interest("interest-1", year), _interest("interest-2", year)])
        )
        moved = renta.recalculate()
        assert _entries(moved) == bound
        (changed,) = _family_issues(moved)
        assert changed.fact is not None
        assert changed.fact.sentence is CalculationNoteSentence.INCOME_FAMILY_ROWS_CHANGED_SINCE_ENTRY

        # Clearing one of the family's casillas is no new entry: the earlier one stands, and so does the finding.
        assert renta.apply(scalar=(_restore(second),)).refusal is None
        partial = renta.require_head()
        assert _entries(partial) == bound
        assert len(_family_issues(partial)) == 1

        # Entering the figures again binds the entry to the rows present now.
        assert renta.apply(scalar=(_set(first, "240"),)).refusal is None
        reentered = renta.require_head()
        assert set(_entries(reentered)) == {_CAPITAL}
        assert _entries(reentered) != bound
        assert _family_issues(reentered) == []

        # Clearing every casilla of the family drops the entry, and the finding returns as first raised.
        assert renta.apply(scalar=(_restore(first),)).refusal is None
        cleared = renta.require_head()
        assert _entries(cleared) == {}
        (again,) = _family_issues(cleared)
        assert again.fact is None
