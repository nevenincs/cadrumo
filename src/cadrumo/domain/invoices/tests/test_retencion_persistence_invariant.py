"""The retencion invariant must still hold on the way back off disk.

The rich :class:`Invoice` gained a consistency validator tying its two retencion
fields to each other and to the base they withhold from. A validator is only
worth what it enforces at the boundaries a record actually crosses, and the one
that matters here is persistence: an invoice reaches the retencion routing after
a save and a load, not straight from construction.

The sibling ``test_secure_storage_roundtrip`` already persists both retencion
fields at non-default values and reads them back, so the plain roundtrip is
covered and is not repeated. What nothing covered is the invariant itself
surviving the round trip. That gap is not cosmetic: if a stored invoice could
load carrying a ``retention_rate`` with no ``retention_amount``, the routing
step would read the missing amount as "this invoice declares no retencion" and
exclude the liability -- a real withholding dropped from Modelo 111, arriving
through a state the validator claims cannot exist.

Two directions are pinned, because the invariant has two halves and they fail
differently:

* a dropped ``retention_amount`` beside a surviving rate must REFUSE the load,
  since a rate alone declares no withheld figure and inferring one would
  manufacture the number the document never stated;
* a retencion mutated ABOVE the base must refuse too -- RIRPF art. 95.1
  withholds "sobre los ingresos integros satisfechos", so a figure exceeding
  the base imponible is not a rounding artefact but a corrupted record.

Each carries a positive control: the same bytes re-persisted unmodified load
back equal, so a refusal caused by the mutation procedure rather than by the
mutation itself could not be mistaken for the property under test.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage import SensitivityClass
from ....tests.secure_sql import isolated_runtime_profile
from ...iva import InvoiceKind, IvaCategory
from .. import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus, iva_rate_percentage

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Mirrors the persistence contract declared in
# ``adapters/persistence/profile/invoices.py``. Restated as literals rather
# than imported, since those names are private to their owning adapter module.
_INVOICE_NAMESPACE = "cadrumo.domain.invoices"
_INVOICE_OBJECT_KEY = "catalogue"
_INVOICE_CATALOGUE_VERSION = 1

_BASE = Decimal("1000.00")
_RETENCION = Decimal("150.00")
_RETENCION_RATE = Decimal("0.15")


def _retention_invoice() -> Invoice:
    """A received professional invoice declaring both retencion fields."""
    rate = iva_rate_percentage(IvaRate.RATE_21)
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_BASE * rate,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "F-PROV-901",
            "issued_at": date(2026, 3, 15),
            "counterparty_name": "Asesoria Profesional Martinez SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "iva_category": IvaCategory.DOMESTIC_GENERAL_21,
            "lines": (line,),
            "base_total": _BASE,
            "iva_total": _BASE * rate,
            "grand_total": _BASE + _BASE * rate,
            "retention_rate": _RETENCION_RATE,
            "retention_amount": _RETENCION,
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
        },
    )


def _persist_and_mutate(tmp_path: Path, mutate) -> None:
    """Persist the fixture, prove the untouched bytes reload, then apply *mutate*.

    The control runs inside the same profile as the mutation, so the two share
    every condition except the edit under test.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        invoice = _retention_invoice()
        InvoiceCatalogueRepository().save(InvoiceCatalogue(invoices={invoice.invoice_id: invoice}))

        record = profile.repository.load(
            _INVOICE_NAMESPACE,
            _INVOICE_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_INVOICE_CATALOGUE_VERSION,
        )
        assert record is not None

        # Positive control: the stored bytes load back to the same record.
        loaded = InvoiceCatalogueRepository().load()
        assert loaded is not None
        assert loaded.invoices[invoice.invoice_id] == invoice

        envelope = json.loads(record.payload.decode("utf-8"))
        stored = envelope["payload"]["invoices"][invoice.invoice_id]
        assert stored["retention_amount"] == str(_RETENCION), (
            "the fixture must serialise retention_amount for these proofs to mean anything"
        )
        assert stored["retention_rate"] == str(_RETENCION_RATE)
        mutate(stored)
        profile.repository.save(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(ValidationError):
            InvoiceCatalogueRepository().load()


def test_a_stored_rate_without_its_amount_refuses_on_load(tmp_path: Path) -> None:
    """A rate alone declares no withheld figure, on disk as in memory.

    Were this to load, the routing step would read the absent amount as "no
    retencion declared" and drop a real liability out of Modelo 111 -- through
    a record shape the validator asserts is impossible.
    """

    def _drop_amount(stored: dict[str, object]) -> None:
        del stored["retention_amount"]

    _persist_and_mutate(tmp_path, _drop_amount)


def test_a_stored_retencion_above_its_base_refuses_on_load(tmp_path: Path) -> None:
    """The base imponible bounds the withholding after persistence too.

    RIRPF art. 95.1 withholds on the ingresos integros, so a stored figure
    exceeding the base is a corrupted record rather than a rounding artefact.
    Raising the amount alone also breaks its agreement with the stored rate, so
    the mutation is refused whichever half is checked first -- which is the
    point: the two halves are one contract.
    """

    def _inflate_amount(stored: dict[str, object]) -> None:
        stored["retention_amount"] = str(_BASE + Decimal("0.01"))

    _persist_and_mutate(tmp_path, _inflate_amount)
