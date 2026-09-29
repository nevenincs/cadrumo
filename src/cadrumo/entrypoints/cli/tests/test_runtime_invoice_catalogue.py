"""Invoice CLI bridge correlates worker receipts and preserves output parity."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.exchange_rate_provider import exchange_rate_provider
from ....application.invoices.catalogue_creation import build_catalogue_invoice
from ....application.invoices.catalogue_read_operation import (
    INVOICE_VIEW_REFUSAL_CODE,
    InvoiceListProjection,
    InvoiceViewProjection,
    InvoiceViewRefusal,
    InvoiceViewSuccess,
)
from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ....application.invoices.catalogue_selection import InvoiceLookupRefusalReason
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....domain.invoices.models import Invoice
from ....domain.iva.classification import InvoiceKind
from .. import _ledger_business_invoice_cli as handler
from .. import runtime_invoice_catalogue as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE = UUID("20202020-2020-4202-8202-202020202020")
_OTHER = UUID("30303030-3030-4303-8303-303030303030")
_OPERATION_ID = "a" * 64


def _record() -> tuple[Invoice, CatalogueInvoiceSnapshot]:
    invoice = build_catalogue_invoice(
        bucket_id=str(_PROFILE),
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="2026-0142",
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("137.25"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=exchange_rate_provider(),
    )
    return invoice, CatalogueInvoiceSnapshot.from_invoice(invoice)


def _client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )


def test_snapshot_reconstructs_exact_existing_cli_record_payload() -> None:
    invoice, snapshot = _record()
    existing = handler._catalogue_invoice_payload(invoice)
    reconstructed = handler._snapshot_invoice_payload(snapshot)
    assert reconstructed.model_dump(mode="python") == handler.CatalogueInvoiceViewResult.model_validate(
        existing
    ).model_dump(mode="python")
    assert handler._catalogue_invoice_lines(reconstructed) == handler._catalogue_invoice_lines(invoice)


def test_list_bridge_keeps_order_and_exact_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch)
    _, invoice = _record()
    submitted: list[bridge.InvoiceListRequest] = []

    def submit(_client: object, request: bridge.InvoiceListRequest, **_kwargs: object):
        submitted.append(request)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=InvoiceListProjection(profile_id=_PROFILE, kind=InvoiceKind.RECEIVED, invoices=(invoice,)),
            effect=OperationEffect.NONE,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    result = bridge.read_invoice_catalogue(cast(typer.Context, cast(object, None)), kind=InvoiceKind.RECEIVED)
    assert result.invoices == (invoice,)
    assert result.completion.operation_id == _OPERATION_ID
    assert len(submitted) == 1
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].kind is InvoiceKind.RECEIVED


@pytest.mark.parametrize(
    ("profile", "condition", "effect"),
    [
        (_OTHER, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, OperationTerminalCondition.REFUSED, OperationEffect.NONE),
        (_PROFILE, OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED),
    ],
)
def test_list_bad_result_retains_receipt(
    monkeypatch: pytest.MonkeyPatch, profile: UUID, condition: OperationTerminalCondition, effect: OperationEffect
) -> None:
    _client(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "run_registered_operation",
        lambda *_args, **_kwargs: RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=InvoiceListProjection(profile_id=profile, kind=None, invoices=()),
            effect=effect,
            terminal_condition=condition,
        ),
    )
    with pytest.raises(CliRefusedBoundaryError) as error:
        bridge.read_invoice_catalogue(cast(typer.Context, cast(object, None)), kind=None)
    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["terminal_condition"] == condition.value
    assert error.value.context["effect"] == effect.value


def test_view_refusal_releases_only_registered_bounded_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch)
    prefix = "a"
    candidate_ids = ("a" * 64, "a" * 63 + "b")
    monkeypatch.setattr(
        bridge,
        "run_registered_operation",
        lambda *_args, **_kwargs: RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=InvoiceViewProjection(
                profile_id=_PROFILE,
                invoice_id=prefix,
                outcome=InvoiceViewRefusal(reason=InvoiceLookupRefusalReason.AMBIGUOUS, candidate_ids=candidate_ids),
            ),
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.REFUSED,
            refusal_code=INVOICE_VIEW_REFUSAL_CODE,
        ),
    )
    with pytest.raises(CliRefusedBoundaryError) as error:
        bridge.view_invoice_catalogue(cast(typer.Context, cast(object, None)), invoice_id=prefix)
    assert error.value.context is not None
    assert error.value.translated_message == "application.invoices.lifecycle.errors.ambiguous_invoice_prefix"
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["candidates"] == ", ".join(candidate_ids)


def test_view_success_requires_selected_invoice_and_none_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch)
    _, invoice = _record()
    prefix = invoice.invoice_id[:8]
    projection = InvoiceViewProjection(
        profile_id=_PROFILE, invoice_id=prefix, outcome=InvoiceViewSuccess(invoice=invoice)
    )
    monkeypatch.setattr(
        bridge,
        "run_registered_operation",
        lambda *_args, **_kwargs: RegisteredOperationCompletion(
            operation_id=_OPERATION_ID, projection=projection, effect=OperationEffect.NONE
        ),
    )
    assert bridge.view_invoice_catalogue(cast(typer.Context, cast(object, None)), invoice_id=prefix).invoice == invoice


def test_view_presentation_failure_preserves_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    _, invoice = _record()
    prefix = invoice.invoice_id[:8]
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=InvoiceViewProjection(
            profile_id=_PROFILE, invoice_id=prefix, outcome=InvoiceViewSuccess(invoice=invoice)
        ),
        effect=OperationEffect.NONE,
    )
    monkeypatch.setattr(
        handler,
        "view_invoice_catalogue",
        lambda *_args, **_kwargs: bridge.InvoiceCatalogueViewRead(completion=completion, invoice=invoice),
    )
    monkeypatch.setattr(
        handler, "emit_envelope", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("private"))
    )
    with pytest.raises(CliRefusedBoundaryError) as error:
        handler.invoice_view(cast(typer.Context, cast(object, None)), invoice_id=prefix)
    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["effect"] == OperationEffect.NONE.value
    assert error.value.__cause__ is None
