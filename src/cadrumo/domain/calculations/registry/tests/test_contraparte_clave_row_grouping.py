"""``contraparte_clave`` groups invoice observations into modelo 347 rows (S294 piece 2).

No modelo 347 revision declares a row-producer binding on this grouping yet
(the registry-authoring piece, S294 piece 3, is deferred pending corpus
grounding -- see the tui-architecture modelo 347 contraparte binding
inventory reference). Bindings here are synthetic-but-valid
:class:`DataBindingDefinition` instances, the same technique
``test_is_m347_declarante_summary_invoice_binding.py`` uses for a case the
committed registry does not itself cover -- this proves the shared resolver
core handles the new grouping correctly ahead of the registry TOML that will
eventually declare it for real.

The other half of this Step's proof lives in ``test_invoice_bindings.py``:
its ``test_resolve_invoice_binding_row_values_groups_by_operator_and_clave_
summing_bases`` test (M349's own grouping, unmodified by this change) still
asserts its exact expected dict byte-for-byte, proving the new
``contraparte_clave`` branch added alongside M349's two existing groupings
left them untouched.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingAggregation, BindingSourceKind
from ..invoice_bindings import InvoiceObservation, resolve_invoice_binding_row_values
from ..schema import DataBindingDefinition, ModeloRevision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _synthetic_contraparte_binding(binding_id: str, row_field: str) -> DataBindingDefinition:
    return DataBindingDefinition.model_validate(
        {
            "id": binding_id,
            "source": "collectible_invoice",
            "selector": {
                "fact": "row_field",
                "row_field": row_field,
                "grouping": "contraparte_clave",
                "claves": ("A", "B"),
                "rectification_scope": "any",
            },
            "aggregation": BindingAggregation(op="rows"),
            "legal_refs": ("rd-1065-2007:art-33",),
            "source_refs": ("aeat-dr-347-2025",),
        },
    )


def _synthetic_revision() -> ModeloRevision:
    """A real modelo 347 revision with its bindings swapped for synthetic ones.

    Borrows a genuinely committed 347 revision for every OTHER attribute
    (casillas, legal metadata, export layouts); only the bindings tuple is
    replaced, so this is not a wholly fabricated snapshot.
    """
    modelo, _catalogues = _committed_modelo("347")
    revision = modelo.revisions["2025-y-siguientes"]
    return revision.model_copy(
        update={
            "bindings": (
                _synthetic_contraparte_binding("m347-contraparte-row-nif", "party_tax_id"),
                _synthetic_contraparte_binding("m347-contraparte-row-clave", "clave"),
                _synthetic_contraparte_binding("m347-contraparte-row-importe", "importe_total"),
            ),
        },
    )


def _observation(*, party: str, country: str, invoice_total: str, clave: str) -> InvoiceObservation:
    return InvoiceObservation(
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        invoice_id=f"inv-{party}-{invoice_total}",
        party_tax_id=party,
        country_code=country,
        transaction_date=date(2026, 3, 15),
        base_amount=Decimal(invoice_total),
        invoice_total_amount=Decimal(invoice_total),
        operation_clave=clave,
    )


def test_contraparte_clave_groups_by_country_party_and_clave_summing_invoice_totals() -> None:
    """Amounts are above the RD 1065/2007 art. 31 declaration floor on purpose.

    A total at or below :data:`~core.M347_THRESHOLD_EUR` now correctly
    produces no row (see ``test_declaration_floor_...`` in this module and
    the real-resolver proof in
    ``test_modelo_347_contraparte_export_parity.py``); this test's own
    subject is the GROUPING behaviour, so its fixtures must clear the floor
    or they would assert nothing about grouping at all.
    """
    revision = _synthetic_revision()
    observations = (
        _observation(party="B12345674", country="ES", invoice_total="4000.00", clave="B"),
        _observation(party="B12345674", country="ES", invoice_total="500.00", clave="B"),  # same group, summed
        _observation(party="A87654321", country="ES", invoice_total="3200.00", clave="A"),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    # Groups sorted by (country_code, party_tax_id, clave): (ES, A87654321, A), (ES, B12345674, B)
    assert resolved == {
        ("m347-contraparte-row-nif", 1): "A87654321",
        ("m347-contraparte-row-clave", 1): "A",
        ("m347-contraparte-row-importe", 1): Decimal("3200.00"),
        ("m347-contraparte-row-nif", 2): "B12345674",
        ("m347-contraparte-row-clave", 2): "B",
        ("m347-contraparte-row-importe", 2): Decimal("4500.00"),
    }


def test_contraparte_clave_ignores_observations_without_an_operation_clave() -> None:
    """An observation carrying no M347 clave (e.g. one M349 built) contributes no row."""
    revision = _synthetic_revision()
    observations = (
        InvoiceObservation(
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            invoice_id="inv-intracom",
            party_tax_id="DE123456789",
            country_code="DE",
            transaction_date=date(2026, 3, 15),
            base_amount=Decimal("300.00"),
            invoice_total_amount=Decimal("300.00"),
            intracommunity_clave="E",
        ),
        _observation(party="B12345674", country="ES", invoice_total="4200.00", clave="B"),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    assert resolved == {
        ("m347-contraparte-row-nif", 1): "B12345674",
        ("m347-contraparte-row-clave", 1): "B",
        ("m347-contraparte-row-importe", 1): Decimal("4200.00"),
    }
