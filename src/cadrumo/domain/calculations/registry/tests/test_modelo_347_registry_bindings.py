"""Modelo 347 counterpart-source registry binding tests.

See Also:
    :func:`~domain.calculations.registry._invoice_bindings.resolve_invoice_binding_values`
        Scalar invoice-source resolver whose thresholded M347 summary output is asserted.
    :class:`~domain.calculations.registry._invoice_bindings.InvoiceObservation`
        Typed observation carrier used to model collectible and payable counterpart totals.
    :func:`~domain.calculations.registry._binding_selector_utils.selector_as_dict`
        Selector normalizer used to verify the committed summary binding records.
    :class:`~core.BindingSourceKind`
        Canonical source-kind taxonomy proving the route is invoice-owned.
    :data:`~core.external_constants.M347_THRESHOLD_EUR`
        Legal declaration floor applied by the summary binding test.
    :class:`~application.invoices.source_resolver.InvoiceCatalogueSourceResolver`
        Application resolver that projects domestic invoices into the same binding route.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from .....core.external_constants import M347_THRESHOLD_EUR
from ..binding_selector_utils import selector_as_dict
from ..invoice_bindings import InvoiceObservation, resolve_invoice_binding_values
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M347_COUNT_BINDING = "modelo-347-declarante-numero-personas-entidades"
_M347_AMOUNT_BINDING = "modelo-347-declarante-importe-total-anual-operaciones"
_M347_SUMMARY_RECORD = "m347_declarante_summary"
#: Grounding every revision of this modelo carries, whatever era it governs.
_M347_BINDING_LEGAL_REFS = {
    "orden-eha-3012-2008:art-1",
    "rd-1065-2007:art-31",
    "ley-58-2003:art-93",
}
_M347_BINDING_SOURCE_REFS = {
    "aeat-dr-347-2011",
    "aeat-modelo-347-procedure",
    "boe-modelo-347-2008-form",
}

#: Grounding only the later half may carry. Orden HAC/1431/2025 is applicable
#: from ejercicio 2025 and its design is the 2025 edition, so a binding on the
#: 2011-2024 half citing either would ground a filing in a norm published after
#: every year that half governs. This pinned the UNION on the early half, which
#: was the pre-split shape: one revision then answered for every year and
#: legitimately carried both eras' grounding.
_M347_2025_ERA_LEGAL_REFS = {"orden-hac-1431-2025:art-1"}
_M347_2025_ERA_SOURCE_REFS = {"aeat-dr-347-2025"}

_M347_EARLY_REVISION = "2011-2024"
_M347_LATER_REVISION = "2025-y-siguientes"


def _modelo_347_revision(revision_id: str = _M347_EARLY_REVISION):
    modelo, _catalogues = _committed_modelo("347")
    return modelo.revisions[revision_id]


def _counterpart_summary_observation(
    *,
    source_id: str,
    party_tax_id: str,
    source_kind: BindingSourceKind,
    base_amount: Decimal,
    invoice_total_amount: Decimal,
) -> InvoiceObservation:
    return InvoiceObservation(
        invoice_id=source_id,
        source_kind=source_kind,
        party_tax_id=party_tax_id,
        country_code="ES",
        transaction_date=date(2025, 1, 1),
        base_amount=base_amount,
        invoice_total_amount=invoice_total_amount,
    )


def test_committed_modelo_347_declares_counterpart_source_summary_bindings() -> None:
    revision = _modelo_347_revision()
    bindings = {binding.id: binding for binding in revision.bindings}

    count_binding = bindings[_M347_COUNT_BINDING]
    amount_binding = bindings[_M347_AMOUNT_BINDING]

    assert count_binding.source is BindingSourceKind.M347_THIRD_PARTY_OPERATION
    assert amount_binding.source is BindingSourceKind.M347_THIRD_PARTY_OPERATION
    assert {
        count_binding.source,
        amount_binding.source,
    }.isdisjoint({BindingSourceKind.LEDGER_TRANSACTION, BindingSourceKind.PURCHASE_INVOICE_EVIDENCE})
    assert count_binding.aggregation is not None
    assert amount_binding.aggregation is not None
    assert count_binding.aggregation.op is BindingAggregationOp.COUNT_DISTINCT
    assert amount_binding.aggregation.op is BindingAggregationOp.SUM
    assert selector_as_dict(count_binding) == {
        "fact": "operator_count",
        "rectification_scope": "any",
        "record": _M347_SUMMARY_RECORD,
    }
    assert selector_as_dict(amount_binding) == {
        "fact": "invoice_total_sum",
        "rectification_scope": "any",
        "record": _M347_SUMMARY_RECORD,
    }
    for binding in (count_binding, amount_binding):
        assert set(binding.legal_refs) >= _M347_BINDING_LEGAL_REFS
        assert set(binding.source_refs) >= _M347_BINDING_SOURCE_REFS
        # The half this test reads governs 2011-2024, so it must NOT reach
        # forward into the 2025 orden or its design.
        assert not set(binding.legal_refs) & _M347_2025_ERA_LEGAL_REFS
        assert not set(binding.source_refs) & _M347_2025_ERA_SOURCE_REFS

    assert set(revision.constructs[0].bindings) >= {_M347_COUNT_BINDING, _M347_AMOUNT_BINDING}


def test_the_later_half_grounds_the_same_bindings_in_the_2025_orden() -> None:
    """The era-specific grounding is present where it belongs.

    Asserted as its own case rather than folded into the sibling: without it the
    exclusion above would pass just as well on a tree that had lost the 2025
    grounding entirely, which is the opposite defect.
    """
    revision = _modelo_347_revision(_M347_LATER_REVISION)
    bindings = {binding.id: binding for binding in revision.bindings}

    for binding_id in (_M347_COUNT_BINDING, _M347_AMOUNT_BINDING):
        binding = bindings[binding_id]
        assert set(binding.legal_refs) >= _M347_BINDING_LEGAL_REFS | _M347_2025_ERA_LEGAL_REFS
        assert set(binding.source_refs) >= _M347_BINDING_SOURCE_REFS | _M347_2025_ERA_SOURCE_REFS


def test_modelo_347_invoice_summary_bindings_apply_invoice_total_declaration_threshold() -> None:
    revision = _modelo_347_revision()
    observations = (
        _counterpart_summary_observation(
            source_id="above-threshold-delivery",
            party_tax_id="B00000001",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            base_amount=Decimal("1500.00"),
            invoice_total_amount=Decimal("1815.00"),
        ),
        _counterpart_summary_observation(
            source_id="above-threshold-acquisition",
            party_tax_id="B00000001",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            base_amount=Decimal("1000.00"),
            invoice_total_amount=M347_THRESHOLD_EUR - Decimal("1815.00") + Decimal("0.01"),
        ),
        _counterpart_summary_observation(
            source_id="below-threshold-control",
            party_tax_id="B00000002",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            base_amount=Decimal("4000.00"),
            invoice_total_amount=M347_THRESHOLD_EUR,
        ),
    )

    resolved = resolve_invoice_binding_values(revision, observations)

    assert resolved == {
        _M347_COUNT_BINDING: Decimal("1"),
        _M347_AMOUNT_BINDING: M347_THRESHOLD_EUR + Decimal("0.01"),
    }
