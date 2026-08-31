"""The counterparty IVA identification survives the encrypted invoice boundary.

``counterparty_identification_state`` is what Ley 37/1992 art. 25 exempts on, so
a save-drops-field / load-re-defaults-field regression on it would not merely
lose a field: it would silently turn every stored intra-community supply into a
row the aggregation gate refuses, or -- if a later reader ever restored the
country fallback this field replaced -- into one it wrongly accepts.

The fixture populates the field NON-DEFAULT (the default is ``None``) and
diverging from the counterparty's country, so the roundtrip cannot pass by
re-deriving the value from the address on load. The anti-tautology proof deletes
the persisted key and asserts the load surfaces the loss rather than quietly
re-defaulting it.
"""

from __future__ import annotations

import json as _json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....core.classification.policies import SensitivityClass
from ....tests.secure_sql import isolated_runtime_profile
from ...iva.classification import InvoiceKind
from ...iva.schema import EUMemberState, IvaCategory
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceCatalogue, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Mirrors the persistence contract in ``adapters/persistence/profile/invoices.py``.
_INVOICE_NAMESPACE = "cadrumo.domain.invoices"
_INVOICE_OBJECT_KEY = "catalogue"
_INVOICE_CATALOGUE_VERSION = 1


def _french_identified_invoice() -> Invoice:
    """An issued supply whose acquirer is established in Spain and identified in France.

    The two facts diverge deliberately. A boundary that re-derived the
    identification from ``counterparty_country`` on load would return ``ES`` (or
    ``None``) here and the strict equality below would fail -- which is the only
    reason this fixture is worth anything.
    """
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "F-2026-0417",
            "issued_at": date(2026, 5, 12),
            "counterparty_name": "Établissement Client",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "counterparty_identification_state": EUMemberState.FR,
            "base_total": Decimal("500.00"),
            "iva_total": Decimal("0.00"),
            "grand_total": Decimal("500.00"),
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Entrega intracomunitaria de bienes",
                    quantity=Decimal("1"),
                    unit_price=Decimal("500.00"),
                    subtotal=Decimal("500.00"),
                    iva_rate=IvaRate.EXEMPT,
                    iva_amount=Decimal("0.00"),
                    spending_category_id="entrega-intracomunitaria",
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory.INTRA_COMMUNITY_SUPPLY,
        },
    )


def _catalogue() -> InvoiceCatalogue:
    invoice = _french_identified_invoice()
    return InvoiceCatalogue(invoices={invoice.invoice_id: invoice})


def test_identification_state_survives_the_encrypted_roundtrip_intact(tmp_path: Path) -> None:
    """Strict equality across the real encrypted cycle, with the fact non-default."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"):
        original = _catalogue()
        InvoiceCatalogueRepository().save(original)
        loaded = InvoiceCatalogueRepository().load()

    assert loaded == original

    restored = next(iter(loaded.values()))
    assert restored.counterparty_identification_state is EUMemberState.FR
    # The proof that nothing re-derived it: the address still says Spain.
    assert restored.counterparty_country == "ES"
    assert restored.counterparty_eu_member_state is EUMemberState.ES


def test_dropping_the_persisted_identification_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: the field cannot vanish on disk and re-default in silence.

    Deletes ``counterparty_identification_state`` from the encrypted envelope
    and reloads. The load must not return a catalogue that compares EQUAL to the
    original -- either it refuses, or the divergence is visible. A silent
    re-default to ``None`` would be the exact save-drops-field regression this
    proof exists to catch, and it would read as a clean roundtrip everywhere
    else.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _catalogue()
        invoice = next(iter(original.values()))
        InvoiceCatalogueRepository().save(original)

        record = profile.repository.load(
            _INVOICE_NAMESPACE,
            _INVOICE_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_INVOICE_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        invoice_dict = envelope["payload"]["invoices"][invoice.invoice_id]
        assert invoice_dict.get("counterparty_identification_state") == "fr", (
            "fixture must actually persist the identification for this proof to mean anything"
        )
        del invoice_dict["counterparty_identification_state"]
        profile.repository.save(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        reloaded = InvoiceCatalogueRepository().load()

    assert reloaded != original, "a dropped identification re-defaulted silently: the boundary is tautological"
    survivor = next(iter(reloaded.values()))
    assert survivor.counterparty_identification_state is not EUMemberState.FR
