"""The rectification facts survive the encrypted invoice boundary, and an older record loads without them.

The four facts a factura rectificativa states are what decide the SIGN and the
PERIOD of a Modelo 303 modification: RD 1619/2012 art. 15.5's two methods read
the same figures as two different modifications, and LIVA art. 89.Cinco and
art. 114.Dos place the modification on the cause and, for the recipient, on the
reception date. A save-drops-field regression on any of them would not merely
lose a field: it would turn a record whose modification is stateable into one
the declaration blocks, or -- if a later reader ever defaulted them -- into a
filed figure nobody stated.

Every fact is populated NON-DEFAULT (each default is ``None``) and the cause is
``art_80_tres``, whose period rule differs from every other cause's, so the
roundtrip cannot pass by re-deriving a value from the class or the dates.

The second proof is the migration one the slice promises: a record stored
before these fields existed carries none of their keys, and must load as a
record that STATES nothing rather than one that refuses or invents a default.
It deletes the persisted keys and asserts the reload is a readable record whose
facts are absent.

Real-behaviour: the real encrypted repository over an isolated runtime profile.
No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

import json as _json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.classification.policies import SensitivityClass
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.invoices.catalogue import InvoiceCatalogue
from .....domain.invoices.enums import InvoiceClass, IvaRate, PaymentStatus
from .....domain.invoices.models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from .....domain.invoices.rectification import missing_rectification_facts, required_rectification_facts
from .....domain.iva.schema import InvoiceKind
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..invoices import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

# Mirrors the persistence contract in ``adapters/persistence/profile/invoices.py``.
_INVOICE_NAMESPACE = "cadrumo.domain.invoices"
_INVOICE_OBJECT_KEY = "catalogue"
_INVOICE_CATALOGUE_VERSION = 1

_YEAR = filing_year_envelope().horizon
_ISSUED_AT = date(_YEAR, 4, 15)
_RECEIVED_ON = date(_YEAR, 4, 22)
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")

_RECTIFICATION_KEYS = (
    "rectification_method",
    "rectification_cause",
    "rectification_direction",
    "document_received_on",
)


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Build and decode invoices under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


def _served_tokens() -> tuple[str, str, str]:
    """A method, cause and direction fact 0141 declares, read rather than spelled."""
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    return (
        str(catalogue.sustitucion_token),
        str(catalogue.art_80_tres_cause_token),
        str(catalogue.minoracion_token),
    )


def _received_rectificativa() -> Invoice:
    """A received rectificativa stating all four facts, each diverging from its default."""
    method, cause, direction = _served_tokens()
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "invoice_class": InvoiceClass.from_registry("RECTIFICATIVA"),
            "series": "R",
            "rectifies_invoice_number": "2026/F-0001",
            "invoice_number": "2026/R-0001",
            "issued_at": _ISSUED_AT,
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": _BASE,
            "iva_total": _CUOTA,
            "grand_total": _BASE + _CUOTA,
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Abono por concurso del destinatario",
                    quantity=Decimal("1"),
                    unit_price=_BASE,
                    subtotal=_BASE,
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=_CUOTA,
                ),
            ),
            "payment_status": PaymentStatus.PENDING,
            "rectification_method": method,
            "rectification_cause": cause,
            "rectification_direction": direction,
            "document_received_on": _RECEIVED_ON,
        },
        context=INVOICE_WRITE_ADMISSION,
    )


def _catalogue() -> InvoiceCatalogue:
    invoice = _received_rectificativa()
    return InvoiceCatalogue(invoices={invoice.invoice_id: invoice})


def test_every_rectification_fact_survives_the_encrypted_roundtrip_intact(tmp_path: Path) -> None:
    """Strict equality across the real encrypted cycle, with all four facts non-default."""
    method, cause, direction = _served_tokens()

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc"):
        original = _catalogue()
        InvoiceCatalogueRepository().save(original)
        loaded = InvoiceCatalogueRepository().load()

    assert loaded == original

    restored = next(iter(loaded.values()))
    assert str(restored.rectification_method) == method
    assert str(restored.rectification_cause) == cause
    assert str(restored.rectification_direction) == direction
    assert restored.document_received_on == _RECEIVED_ON
    # The whole point of persisting them: the declaration has nothing left to ask for.
    assert missing_rectification_facts(restored) == ()


def test_a_record_stored_without_the_fields_loads_with_them_absent(tmp_path: Path) -> None:
    """A record written before these fields existed stays readable and states nothing.

    Deletes all four persisted keys and reloads. The record must still open --
    an operator has to be able to reach it to supply the facts -- and every
    fact must read as ABSENT, which is what the Modelo 303 finding then names.
    A reload that refused would lock the catalogue holding it; one that
    defaulted a value would invent a modification nobody stated.
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
        assert all(invoice_dict.get(key) is not None for key in _RECTIFICATION_KEYS), (
            "fixture must actually persist all four facts for this proof to mean anything"
        )
        for key in _RECTIFICATION_KEYS:
            del invoice_dict[key]
        profile.repository.save(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        reloaded = InvoiceCatalogueRepository().load()

    survivor = next(iter(reloaded.values()))
    assert survivor.rectification_method is None
    assert survivor.rectification_cause is None
    assert survivor.rectification_direction is None
    assert survivor.document_received_on is None
    assert missing_rectification_facts(survivor) == required_rectification_facts(InvoiceKind.RECEIVED)
    # Anti-tautology: the stripped record must NOT compare equal to the one
    # that stated the facts, or this proof would pass on a boundary that
    # silently restored them.
    assert reloaded != original
