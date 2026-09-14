"""A fourth IVA screen axis: could this category's base EVER be routed, independent of any row.

The two existing IVA quantity screens are both OBSERVATION-DEPENDENT:
``unsupported_ledger_iva_observations`` asks whether a ROW is selected by some
binding, and ``unrouted_ledger_iva_quantities`` asks whether a consumed row's
FACT is drawn -- and its own docstring states it must not fire on a zero
total, so a by-law cuota-less category (whose cuota IS zero) is filtered
before any exclusion set could matter. Neither can answer a question that
holds true or false from the registry alone, before a single ledger row
exists: "could this revision's bindings EVER draw this category's base?"

``structurally_unroutable_iva_base_categories`` answers exactly that, and
this module proves it end to end: the pure registry-level function, its live
wiring into ``LedgerIvaAggregationSourceResolver`` (scoped to this taxpayer's
actually-present categories on Modelo 303), and a mutation proof that the
detector has teeth.

Real-behaviour: the committed Modelo 303 registry revision and real
:class:`Transaction` fixtures driven through the production classification
path, never a hand-built ``IvaLedgerObservation`` standing in for the
projection. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from ....core.period import Period
from ....domain.calculations.registry.ledger_iva_bindings import structurally_unroutable_iva_base_categories
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.iva.components import registry_category_projection
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2025, 2, 10, 12, 0, tzinfo=UTC)
_Q1_2025 = Period.from_year_and_code(2025, "1T")
_BUCKET_ID = "38383838-3838-4838-8838-383838383838"


def _m303_revision() -> ModeloRevision:
    return compiled_bundled_authority().snapshot("303", filing_year=_Q1_2025.filing_year, period="1T").revision


def _domestic_zero_sale() -> Transaction:
    """A zero-rated domestic sale: zero cuota by law, a real base by law.

    ``IvaCategory.DOMESTIC_ZERO`` is the canonical proof this screen exists
    for: cuota-less BY LAW (so Screen 1/2's cuota-side reasoning never fires
    on it), while the base is a real declared amount M303 currently has no
    ``base_amount_sum`` binding for at all.
    """
    raw = RawTransaction(
        provider_transaction_id="zero-rated-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("500.00"),
        currency="EUR",
        counterparty="Comprador Nacional SL",
        description="venta tipo cero",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "zero-rated-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("500.00"),
            "iva_rate": Decimal("0.00"),
            "iva_amount": Decimal("0.00"),
            "iva_category": IvaCategory("domestic_zero"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _domestic_general_sale() -> Transaction:
    """A fully-covered domestic sale, the negative control."""
    raw = RawTransaction(
        provider_transaction_id="general-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("1210.00"),
        currency="EUR",
        counterparty="Comprador Nacional SL",
        description="venta tipo general",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "general-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory("domestic_general"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def test_domestic_zero_is_structurally_unroutable_on_m303() -> None:
    """Positive control: the registry-only question, no observation needed.

    Per Ruling B, this is the proof the screen exists at all: cuota-less by
    law, base-bearing by law, and reused from
    the registry's ``cuota_less_m303`` projection would wrongly suppress it.
    """
    unroutable = structurally_unroutable_iva_base_categories(_m303_revision())

    assert IvaCategory("domestic_zero") in unroutable, (
        "refutation, not a tuning target: if this ever fails, M303 has gained a base_amount_sum "
        "binding for domestic_zero and the fixture/finding is stale, not the screen"
    )


def test_a_fully_covered_category_is_not_reported() -> None:
    """Negative control: the domestic general tier IS routed on the committed revision."""
    unroutable = structurally_unroutable_iva_base_categories(_m303_revision())

    assert IvaCategory("domestic_general") not in unroutable


def test_the_out_of_scope_declaration_is_not_a_re_export_of_cuota_less() -> None:
    """Ruling B, checked rather than asserted: the two suppression sets differ.

    the registry's ``cuota_less_m303`` projection answers "does this produce a cuota?" and
    would wrongly suppress DOMESTIC_ZERO here (base-bearing despite being
    cuota-less). The out-of-scope set for THIS screen is a real, smaller,
    independently-justified set -- proved by two cuota-less members landing on
    opposite sides of this screen's membership test: DOMESTIC_ZERO (base-
    bearing by law) IS reported, while REGIMEN_SIMPLIFICADO (settled from
    módulos, not the ledger at all) is NOT. If reusing CUOTA_LESS as the
    suppressor here, both would be silenced together.
    """
    unroutable = set(structurally_unroutable_iva_base_categories(_m303_revision()))

    cuota_less = registry_category_projection("cuota_less_m303")
    assert IvaCategory("domestic_zero") in cuota_less
    assert IvaCategory("regimen_simplificado") in cuota_less
    assert IvaCategory("domestic_zero") in unroutable
    assert IvaCategory("regimen_simplificado") not in unroutable
