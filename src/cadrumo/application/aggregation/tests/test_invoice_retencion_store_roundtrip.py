"""Strict persistence coverage for the invoice-projected retenedor liability.

Routing a received invoice's retencion into the per-perceptor store made a new
kind of row writable there: one whose ``source_kind`` is ``payable_invoice`` and
whose ``source_object_id`` is an invoice id rather than a ledger transaction id.
Every prior roundtrip on this store wrote ``ledger_transaction`` or
``aggregate_pull``, so nothing had carried an invoice-sourced row across the
encrypted boundary and read it back.

What the routing step's own gate already proves, and is deliberately NOT
repeated here: that a received invoice reaches the real store through the one
shared write helper and comes back with the right amount, base, source kind and
scheme, and that an issued invoice contributes nothing. This module adds the two
properties the roundtrip discipline asks for on top of that, neither of which
that gate makes:

* **strict equality** across the boundary rather than a four-field spot check,
  with the observation's one defaultable field (``perceptor_name``) carrying a
  non-default value -- a save-drops-field regression on it is invisible to a
  fixture that leaves it empty, and invisible to assertions that never read it;
* an **on-disk** anti-tautology proof. The store already has an anti-tautology
  test, but it validates the payload MODEL against a partial dict; it never
  persists mutated bytes and never re-reads them through the production path.
  A model that is strict in isolation says nothing about a read path that might
  re-default around it, which is exactly the regression the roundtrip above
  would then be unable to surface.

The figures are the invoice's own declared base and retencion. No registry
formula is under test.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import RETENCION_OBSERVATIONS_NAMESPACE
from ....core.aggregation import AggregationCaptureKind, BindingSourceKind
from ....core.period import Period
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....tests.secure_sql import isolated_runtime_profile
from .._invoice_retencion import route_invoice_retenciones
from .._retencion_observations_repository import (
    RetencionObservationRepository,
    persist_retencion_observations,
)
from .._retenciones import RetencionScheme

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "1T")
_MODELO = "111"
_SCHEME = RetencionScheme.PROFESSIONAL

# The supplier's invoice, stated once. Retencion sits outside the grand total.
_BASE = Decimal("1000.00")
_RETENCION = Decimal("150.00")
_RETENCION_RATE = Decimal("0.15")
# Non-default deliberately: this is the observation's only defaultable field,
# and it only roundtrips if a fixture actually populates it.
_PERCEPTOR_NAME = "Asesoria Profesional Martinez SL"
_PERCEPTOR_NIF = "B12345674"


def _received_invoice() -> Invoice:
    """A received professional invoice carrying a declared retencion."""
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
            "invoice_number": "F-PROV-778",
            "issued_at": date(2026, 3, 15),
            "counterparty_name": _PERCEPTOR_NAME,
            "counterparty_tax_id": _PERCEPTOR_NIF,
            "counterparty_country": "ES",
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
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


def _routed_observation():
    """The one observation the invoice projects, before any persistence."""
    routing = route_invoice_retenciones(((_received_invoice(), _SCHEME),))
    assert routing.excluded == (), "the fixture invoice must route; a defect here would empty the test"
    assert len(routing.observations) == 1
    return routing.observations[0]


def test_the_projected_observation_carries_its_defaultable_field_non_default() -> None:
    """The fixture is only a roundtrip witness if it populates what may default.

    ``perceptor_name`` is the only field on the observation with a default, so
    it is the only one a save-drops-field regression could hide behind. Pinning
    it here means the equality assertion below is actually testing something a
    default could not satisfy.
    """
    observation = _routed_observation()

    assert observation.perceptor_name == _PERCEPTOR_NAME
    assert observation.perceptor_name != "", "the defaultable field must be populated for the roundtrip to witness it"
    assert observation.source_kind is BindingSourceKind.PAYABLE_INVOICE
    assert observation.source_object_id == _received_invoice().invoice_id


def test_an_invoice_sourced_observation_survives_the_encrypted_boundary_intact(tmp_path: Path) -> None:
    """Strict equality across save and load, not a spot check of four fields.

    The routing gate asserts the amount, base, source kind and scheme come
    back. That leaves every other field -- the perceptor name, the invoice id
    standing in for a transaction id, the accrual date -- free to be dropped or
    re-defaulted on the way through with nothing to notice. Comparing the whole
    record is what closes that.
    """
    original = _routed_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        persist_retencion_observations(
            modelo=_MODELO,
            filing_year=_PERIOD.filing_year,
            period=_PERIOD,
            observations=(original,),
        )
        loaded = RetencionObservationRepository().load_observations(_MODELO, _PERIOD)

    assert loaded == (original,)


def test_a_dropped_field_on_disk_refuses_on_load(tmp_path: Path) -> None:
    """Delete a persisted field, re-encrypt, and the production read must refuse.

    The proof that the equality above is not tautological. The existing
    anti-tautology gate on this store validates the payload MODEL against a
    partial dict, which cannot see a read path that re-defaults around a strict
    model; this one goes through the real bytes.

    The positive control re-persists the SAME bytes unmodified and loads them
    back equal, so a refusal produced by the mutation procedure itself could not
    be mistaken for the property under test.

    The refusal is pinned to the field that was dropped rather than accepted as
    any refusal at all. A read that rejected the mutated bytes for some other
    reason -- an envelope-level check, a key-identity mismatch introduced by the
    re-save -- would otherwise keep this green while the strictness it exists to
    prove had gone. ``loc`` and ``type`` are the structural answer to which
    check ran, so nothing here depends on message wording.
    """
    original = _routed_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = RetencionObservationRepository()
        prepared = repository.to_secure_object_write(
            repository.build_observation_payload(
                modelo=_MODELO,
                filing_year=_PERIOD.filing_year,
                period=_PERIOD,
                observation=original,
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
            ),
        )
        objects = repository.secure_object_repository

        def _persist(envelope_bytes: bytes) -> None:
            objects.save(
                namespace=RETENCION_OBSERVATIONS_NAMESPACE.namespace,
                object_key=prepared.object_key,
                classification=RETENCION_OBSERVATIONS_NAMESPACE.sensitivity,
                schema_version=RETENCION_OBSERVATIONS_NAMESPACE.schema_version,
                written_at=prepared.written_at,
                payload=envelope_bytes,
            )

        _persist(prepared.payload)
        assert repository.load_observations(_MODELO, _PERIOD) == (original,)

        envelope = json.loads(prepared.payload.decode("utf-8"))
        stored = envelope["payload"]["observation"]
        assert stored["retencion_amount"] == str(_RETENCION), (
            "the fixture must serialise retencion_amount for this proof to mean anything"
        )
        del stored["retencion_amount"]
        _persist(json.dumps(envelope).encode("utf-8"))

        with pytest.raises(ValidationError) as exc_info:
            repository.load_observations(_MODELO, _PERIOD)

    errors = exc_info.value.errors()
    assert len(errors) == 1, f"expected one refusal, got {[error['type'] for error in errors]}"
    assert errors[0]["type"] == "missing"
    assert errors[0]["loc"][-1] == "retencion_amount"


def test_a_dropped_perceptor_name_reloads_unequal_rather_than_silently_defaulting(
    tmp_path: Path,
) -> None:
    """The defaultable field's own proof: dropping it must be detectable.

    ``perceptor_name`` has a default, so a strict model cannot refuse its
    absence -- the load succeeds. That is exactly why the roundtrip must assert
    EQUALITY rather than presence: the surfaced signal for this field is the
    reloaded record differing from the original, and if that comparison were
    ever relaxed to a field-by-field spot check the drop would become invisible.
    """
    original = _routed_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = RetencionObservationRepository()
        prepared = repository.to_secure_object_write(
            repository.build_observation_payload(
                modelo=_MODELO,
                filing_year=_PERIOD.filing_year,
                period=_PERIOD,
                observation=original,
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
            ),
        )
        envelope = json.loads(prepared.payload.decode("utf-8"))
        del envelope["payload"]["observation"]["perceptor_name"]
        repository.secure_object_repository.save(
            namespace=RETENCION_OBSERVATIONS_NAMESPACE.namespace,
            object_key=prepared.object_key,
            classification=RETENCION_OBSERVATIONS_NAMESPACE.sensitivity,
            schema_version=RETENCION_OBSERVATIONS_NAMESPACE.schema_version,
            written_at=prepared.written_at,
            payload=json.dumps(envelope).encode("utf-8"),
        )

        loaded = repository.load_observations(_MODELO, _PERIOD)

    assert loaded != (original,), "a dropped defaultable field must surface as inequality, never pass unnoticed"
    assert loaded[0].perceptor_name == ""
    assert loaded[0].retencion_amount == original.retencion_amount
