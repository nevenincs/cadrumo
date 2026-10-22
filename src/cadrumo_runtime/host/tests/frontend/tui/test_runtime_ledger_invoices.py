"""Host-side review, exact-session dispatch and receipt correlation for the invoice import and wizard doors."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.application.invoices.catalogue_intake_contracts import (
    INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    INVOICE_WIZARD_OPERATION_DEFINITION_ID,
    InvoiceImportProjection,
    InvoiceImportRequest,
    InvoiceWizardOutcome,
    InvoiceWizardProjection,
    InvoiceWizardRequest,
)
from cadrumo.application.invoices.catalogue_intake_refusal import (
    INVOICE_WIZARD_VALIDATION_REFUSAL_CODE,
    InvoiceWizardFieldFailure,
    InvoiceWizardValidationRefusalProjection,
)
from cadrumo.application.ledger.workspace import LedgerWorkspaceArea
from cadrumo.application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.invoices.errors import InvoiceValidationError
from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.invoices_import import LedgerInvoiceImportScreen
from cadrumo.entrypoints.tui.ledger.invoices_wizard import LedgerInvoiceWizardScreen
from cadrumo.entrypoints.tui.ledger.tests.invoices_fixtures import import_outcome, invoice_snapshot
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import ledger_controller, ledger_projection
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....frontend.tui import runtime_ledger_invoices
from ....frontend.tui.runtime_ledger_invoices import (
    RuntimeLedgerInvoiceImportTuiDoorV1,
    RuntimeLedgerInvoiceWizardTuiDoorV1,
    compose_invoices_tools,
)
from .ledger_invoices_runtime_harness import (
    LAPSED_SESSION_ID,
    OTHER_PROFILE_ID,
    PROFILE_ID,
    PROFILE_LABEL,
    Boundary,
    Settled,
    client_of,
    install,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BOOK = b"numero;fecha;base\nF-1;2026-03-01;100.00\n"
_REFUSAL_CODE = "ERROR_INVOICE_VALIDATION"
_DETAIL = OperationErrorDetailV1(
    kind=OperationErrorDetailKind.REGISTERED_ERROR,
    error_code=_REFUSAL_CODE,
    message_key="errors.error.error_invoice_validation",
    context=(),
)


def _import_door(boundary: Boundary) -> RuntimeLedgerInvoiceImportTuiDoorV1:
    return RuntimeLedgerInvoiceImportTuiDoorV1(client_of(boundary), profile_label=PROFILE_LABEL)


def _wizard_door(boundary: Boundary) -> RuntimeLedgerInvoiceWizardTuiDoorV1:
    return RuntimeLedgerInvoiceWizardTuiDoorV1(client_of(boundary), profile_label=PROFILE_LABEL)


def _book(tmp_path: Path) -> Path:
    path = tmp_path / "facturas.csv"
    path.write_bytes(_BOOK)
    return path


def _import_request(path: Path, digest: str | None = None) -> InvoiceImportRequest:
    return InvoiceImportRequest(
        profile_id=PROFILE_ID,
        kind=InvoiceKind.RECEIVED,
        source_path=str(path),
        source_sha256=hashlib.sha256(_BOOK).hexdigest() if digest is None else digest,
        country="ES",
    )


def _outcome(
    *, created: int = 2, refused: int = 1, profile: UUID = PROFILE_ID, digest: str | None = None
) -> InvoiceImportProjection:
    base = import_outcome(created=created, skipped=1, refused=refused)
    return base.model_copy(update={"profile_id": profile, "source_sha256": digest or hashlib.sha256(_BOOK).hexdigest()})


# --- review: read on the host, off the event loop ------------------------------------------------


def test_preview_digests_the_file_off_the_event_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boundary = install(monkeypatch)
    entries: list[bool] = []
    real = runtime_ledger_invoices.sha256_file

    def recording(path: Path) -> str:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            entries.append(False)
        else:
            entries.append(True)
        return real(path)

    monkeypatch.setattr(runtime_ledger_invoices, "sha256_file", recording)
    path = _book(tmp_path)
    source = asyncio.run(_import_door(boundary).preview(str(path)))

    assert source.sha256 == hashlib.sha256(_BOOK).hexdigest()
    assert source.size_bytes == len(_BOOK)
    assert source.file_name == "facturas.csv"
    assert source.source_path == str(path.resolve())
    assert entries == [False]
    assert boundary.submissions == []


@pytest.mark.parametrize("name", ["missing.csv", ""], ids=["missing", "folder"])
def test_preview_refuses_a_missing_file_or_a_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str) -> None:
    boundary = install(monkeypatch)
    with pytest.raises(InvoiceValidationError) as raised:
        asyncio.run(_import_door(boundary).preview(str(tmp_path / name)))
    assert raised.value.translated_message == "application.invoices.bulk_import.errors.file_read_failed"
    assert boundary.submissions == []


def test_preview_reads_nothing_once_the_session_lapsed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boundary = install(monkeypatch)
    door = _import_door(boundary)
    read: list[Path] = []
    monkeypatch.setattr(runtime_ledger_invoices, "sha256_file", read.append)
    boundary.client.session_id = LAPSED_SESSION_ID
    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door.preview(str(_book(tmp_path))))
    assert read == []


# --- apply: exactly the reviewed digest ----------------------------------------------------------


def test_apply_submits_the_reviewed_digest_that_the_preview_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    boundary = install(
        monkeypatch, Settled(INVOICE_IMPORT_OPERATION_DEFINITION_ID, _outcome(), effect=OperationEffect.PARTIAL)
    )
    door = _import_door(boundary)
    source = asyncio.run(door.preview(str(_book(tmp_path))))
    request = InvoiceImportRequest(
        profile_id=door.profile_id,
        kind=InvoiceKind.RECEIVED,
        source_path=source.source_path,
        source_sha256=source.sha256,
    )
    assert asyncio.run(door.apply(request)) == _outcome()
    assert boundary.payloads == [request]
    assert boundary.reads == [(InvoiceImportProjection, False)]


@pytest.mark.parametrize(
    ("outcome", "effect"),
    [
        (_outcome(refused=0), OperationEffect.UPDATED),
        (_outcome(created=0, refused=0), OperationEffect.NONE),
        (_outcome(created=0, refused=2), OperationEffect.NONE),
    ],
)
def test_apply_accepts_each_effect_its_outcome_implies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome: InvoiceImportProjection, effect: OperationEffect
) -> None:
    boundary = install(monkeypatch, Settled(INVOICE_IMPORT_OPERATION_DEFINITION_ID, outcome, effect=effect))
    assert asyncio.run(_import_door(boundary).apply(_import_request(_book(tmp_path)))) == outcome


def test_apply_never_sends_a_request_without_the_reviewed_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    boundary = install(monkeypatch)
    unbound = _import_request(_book(tmp_path)).model_copy(update={"source_sha256": None})
    with pytest.raises(RefusalError) as raised:
        asyncio.run(_import_door(boundary).apply(unbound))
    assert raised.value.reason is RefusalCode.INVALID_FRAME
    assert boundary.submissions == []


@pytest.mark.parametrize(
    "settled",
    [
        Settled(
            INVOICE_IMPORT_OPERATION_DEFINITION_ID, _outcome(profile=OTHER_PROFILE_ID), effect=OperationEffect.PARTIAL
        ),
        Settled(INVOICE_IMPORT_OPERATION_DEFINITION_ID, _outcome(), effect=OperationEffect.UPDATED),
        Settled(INVOICE_IMPORT_OPERATION_DEFINITION_ID, _outcome(refused=0), effect=OperationEffect.NONE),
        Settled(INVOICE_IMPORT_OPERATION_DEFINITION_ID, _outcome(digest="9" * 64), effect=OperationEffect.PARTIAL),
    ],
    ids=["another-profile", "partial-called-updated", "created-called-none", "another-digest"],
)
def test_apply_refuses_a_result_its_receipt_does_not_support(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, settled: Settled
) -> None:
    boundary = install(monkeypatch, settled)
    with pytest.raises(RefusalError) as raised:
        asyncio.run(_import_door(boundary).apply(_import_request(_book(tmp_path))))
    assert raised.value.reason is RefusalCode.INVALID_FRAME


def test_a_refused_import_raises_its_recorded_error_or_bare_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    refused = Settled(
        INVOICE_IMPORT_OPERATION_DEFINITION_ID,
        None,
        condition=OperationTerminalCondition.REFUSED,
        refusal_ref=_REFUSAL_CODE,
    )
    boundary = install(monkeypatch, replace(refused, detail=_DETAIL))
    with pytest.raises(RecordedRegisteredError):
        asyncio.run(_import_door(boundary).apply(_import_request(_book(tmp_path))))
    boundary = install(monkeypatch, refused)
    with pytest.raises(FrontendRefusedError) as bare:
        asyncio.run(_import_door(boundary).apply(_import_request(_book(tmp_path))))
    assert bare.value.reason == _REFUSAL_CODE
    assert boundary.reads == []


def test_apply_submits_nothing_once_the_session_lapsed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boundary = install(monkeypatch)
    door = _import_door(boundary)
    boundary.client.session_id = LAPSED_SESSION_ID
    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door.apply(_import_request(_book(tmp_path))))
    assert boundary.submissions == []


# --- wizard ----------------------------------------------------------------------------------------


def _wizard_request(kind: InvoiceKind = InvoiceKind.ISSUED) -> InvoiceWizardRequest:
    return InvoiceWizardRequest(
        profile_id=PROFILE_ID,
        kind=kind,
        counterparty_nif="B00000000",
        counterparty_name="Synthetic customer",
        invoice_number="F-00001",
        invoice_date="2026-03-01",
        taxable_base="100.00",
        iva_rate="21",
        currency="EUR",
        country_code="ES",
    )


def _recorded(
    *, already_existed: bool = False, kind: InvoiceKind = InvoiceKind.ISSUED, profile: UUID = PROFILE_ID
) -> InvoiceWizardOutcome:
    invoice = invoice_snapshot(kind=kind).model_copy(update={"bucket_id": str(profile)})
    return InvoiceWizardOutcome(
        profile_id=profile,
        outcome="succeeded",
        result=InvoiceWizardProjection(
            profile_id=profile, invoice=invoice, already_existed=already_existed, euro_value_pending=False
        ),
    )


def _field_refusal() -> InvoiceWizardOutcome:
    return InvoiceWizardOutcome(
        profile_id=PROFILE_ID,
        outcome="refused",
        refusal=InvoiceWizardValidationRefusalProjection(
            profile_id=PROFILE_ID,
            field_errors=(InvoiceWizardFieldFailure(field="invoice_date", reason="must be a date"),),
        ),
    )


@pytest.mark.parametrize(
    "settled",
    [
        Settled(INVOICE_WIZARD_OPERATION_DEFINITION_ID, _recorded(), effect=OperationEffect.UPDATED),
        Settled(INVOICE_WIZARD_OPERATION_DEFINITION_ID, _recorded(already_existed=True)),
        Settled(
            INVOICE_WIZARD_OPERATION_DEFINITION_ID,
            _field_refusal(),
            condition=OperationTerminalCondition.REFUSED,
            refusal_ref=INVOICE_WIZARD_VALIDATION_REFUSAL_CODE,
        ),
    ],
    ids=["recorded", "already-recorded", "field-refusal"],
)
def test_the_wizard_returns_the_settled_outcome_for_the_exact_request(
    monkeypatch: pytest.MonkeyPatch, settled: Settled
) -> None:
    boundary = install(monkeypatch, settled)
    assert asyncio.run(_wizard_door(boundary)(_wizard_request())) == settled.result
    assert boundary.payloads == [_wizard_request()]
    assert boundary.reads == [(InvoiceWizardOutcome, True)]


@pytest.mark.parametrize(
    "settled",
    [
        Settled(
            INVOICE_WIZARD_OPERATION_DEFINITION_ID,
            _recorded(profile=OTHER_PROFILE_ID),
            effect=OperationEffect.UPDATED,
        ),
        Settled(INVOICE_WIZARD_OPERATION_DEFINITION_ID, _recorded(), effect=OperationEffect.NONE),
        Settled(
            INVOICE_WIZARD_OPERATION_DEFINITION_ID, _recorded(already_existed=True), effect=OperationEffect.UPDATED
        ),
        Settled(
            INVOICE_WIZARD_OPERATION_DEFINITION_ID,
            _recorded(kind=InvoiceKind.RECEIVED),
            effect=OperationEffect.UPDATED,
        ),
    ],
    ids=["another-profile", "recorded-called-none", "existing-called-updated", "another-kind"],
)
def test_the_wizard_refuses_a_result_its_receipt_does_not_support(
    monkeypatch: pytest.MonkeyPatch, settled: Settled
) -> None:
    boundary = install(monkeypatch, settled)
    with pytest.raises(RefusalError) as raised:
        asyncio.run(_wizard_door(boundary)(_wizard_request()))
    assert raised.value.reason is RefusalCode.INVALID_FRAME


def test_a_refused_wizard_entry_raises_its_recorded_error_and_a_lapsed_session_submits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = install(
        monkeypatch,
        Settled(
            INVOICE_WIZARD_OPERATION_DEFINITION_ID,
            None,
            condition=OperationTerminalCondition.REFUSED,
            refusal_ref=_REFUSAL_CODE,
            detail=_DETAIL,
        ),
    )
    with pytest.raises(RecordedRegisteredError):
        asyncio.run(_wizard_door(boundary)(_wizard_request()))

    boundary = install(monkeypatch)
    door = _wizard_door(boundary)
    boundary.client.session_id = LAPSED_SESSION_ID
    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door(_wizard_request()))
    assert boundary.submissions == []


# --- the overview tools -----------------------------------------------------------------------------


def test_the_overview_offers_the_import_and_wizard_tools_over_the_pinned_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = install(monkeypatch)
    tools = compose_invoices_tools(client_of(boundary), PROFILE_LABEL)

    assert [(tool.key, tool.label_key, tool.area) for tool in tools] == [
        ("ledger.tool.invoices.import", "tui.ledger.invoices.import.tool", LedgerWorkspaceArea.OVERVIEW),
        ("ledger.tool.invoices.wizard", "tui.ledger.invoices.wizard.tool", LedgerWorkspaceArea.OVERVIEW),
    ]
    controller = ledger_controller(ledger_projection())
    importer, wizard = (tool.build(controller) for tool in tools)
    assert isinstance(importer, LedgerInvoiceImportScreen)
    assert isinstance(wizard, LedgerInvoiceWizardScreen)
    assert importer.door.profile_id == PROFILE_ID
    assert wizard.door.profile_id == PROFILE_ID
    assert boundary.submissions == []
