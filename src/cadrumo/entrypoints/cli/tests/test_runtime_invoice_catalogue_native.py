"""Native worker acceptance for canonical encrypted invoice catalogue reads."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.invoices.catalogue_read_operation import (
    INVOICE_LIST_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_REFUSAL_CODE,
)
from ....application.invoices.catalogue_remove_operation import INVOICE_REMOVE_OPERATION_DEFINITION_ID
from ....application.invoices.catalogue_update_operation import INVOICE_UPDATE_OPERATION_DEFINITION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.login_session import authenticate_profile_for_invocation
from ....core.config import override_settings
from ....core.period import Period
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from .native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_FIRST_PERIOD = Period.from_year_and_code(2025, "1T")
_INVOICE_OPERATIONS = frozenset({INVOICE_LIST_OPERATION_DEFINITION_ID, INVOICE_VIEW_OPERATION_DEFINITION_ID})


@dataclass(frozen=True, slots=True)
class _InvoiceFixture:
    """Valid canonical invoices and a deterministic short-prefix collision."""

    catalogue: InvoiceCatalogue
    unique_invoice_id: str
    ambiguous_prefix: str
    ambiguous_invoice_ids: tuple[str, str]


def _invoice(profile_id: UUID, invoice_number: str, authority: PinnedAuthorityOperation) -> Invoice:
    with validating_governed_facts(authority):
        return Invoice.model_validate(
            {
                "kind": InvoiceKind.RECEIVED,
                "bucket_id": str(profile_id),
                "invoice_number": invoice_number,
                "issued_at": "2025-05-01",
                "counterparty_name": "Native catalogue supplier",
                "notes": "Original invoice note kept by a partial update.",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "base_total": Decimal("100.00"),
                "iva_total": Decimal("21.00"),
                "grand_total": Decimal("121.00"),
                "currency": "EUR",
                "payment_status": PaymentStatus.PAID,
                "lines": (
                    InvoiceLine(
                        description="Native catalogue invoice line",
                        quantity=Decimal("1"),
                        unit_price=Decimal("100.00"),
                        subtotal=Decimal("100.00"),
                        iva_rate=IvaRate.from_registry("RATE_21"),
                        iva_amount=Decimal("21.00"),
                    ),
                ),
            }
        )


def _seed_catalogue(profile_id: UUID, authority: PinnedAuthorityOperation) -> _InvoiceFixture:
    seen: dict[str, Invoice] = {}
    collision: tuple[Invoice, Invoice] | None = None
    for index in range(96):
        candidate = _invoice(profile_id, f"NATIVE-AMBIGUOUS-{index:03d}", authority)
        prefix = candidate.invoice_id[:2]
        previous = seen.get(prefix)
        if previous is not None:
            collision = (previous, candidate)
            break
        seen[prefix] = candidate
    assert collision is not None

    ambiguous_ids = tuple(invoice.invoice_id for invoice in collision)
    ambiguous_prefix = collision[0].invoice_id[:2]
    unique = next(
        _invoice(profile_id, f"NATIVE-UNIQUE-{index:03d}", authority)
        for index in range(96)
        if not any(
            _invoice(profile_id, f"NATIVE-UNIQUE-{index:03d}", authority).invoice_id.startswith(invoice.invoice_id[:8])
            for invoice in collision
        )
    )
    rows = (*collision, unique)
    catalogue = InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in rows})
    InvoiceCatalogueRepository(bucket_id=str(profile_id)).save(catalogue)
    return _InvoiceFixture(
        catalogue=catalogue,
        unique_invoice_id=unique.invoice_id,
        ambiguous_prefix=ambiguous_prefix,
        ambiguous_invoice_ids=cast(tuple[str, str], ambiguous_ids),
    )


def _scope(
    client_id: UUID,
    *,
    periods: frozenset[Period] | None,
    result: bool = True,
    commit: bool = False,
    operation_ids: frozenset[str] = _INVOICE_OPERATIONS,
) -> AccessScope:
    actions = {
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.RESUME,
        AccessAction.OBSERVE,
        AccessAction.CANCEL,
        AccessAction.DETACH,
    }
    if result:
        actions.add(AccessAction.RESULT)
    if commit:
        actions.add(AccessAction.COMMIT)
    return AccessScope(
        operations=operation_ids,
        actions=frozenset(actions),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id="operation.observation",
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for definition_id in operation_ids
                ),
            }
        ),
        periods=periods,
        allow_period_independent=periods is None,
        allow_delegation=False,
    )


def _prepare(authority: PinnedAuthorityOperation):
    def prepare(profile_id: UUID, _root: Path) -> _InvoiceFixture:
        return _seed_catalogue(profile_id, authority)

    return prepare


def _catalogue_after_password_login(profile_id: UUID, authority: PinnedAuthorityOperation):
    close_active_bucket_session()
    login = authenticate_profile_for_invocation(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=authority.profile_decode_context(),
    )
    assert login.bucket_id == str(profile_id)
    try:
        return InvoiceCatalogueRepository(bucket_id=str(profile_id)).load()
    finally:
        close_active_bucket_session()


def _events_after_password_login(profile_id: UUID, authority: PinnedAuthorityOperation):
    close_active_bucket_session()
    login = authenticate_profile_for_invocation(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=authority.profile_decode_context(),
    )
    assert login.bucket_id == str(profile_id)
    try:
        return BucketEventHistoryRepository().load()
    finally:
        close_active_bucket_session()


def test_native_cli_lists_and_resolves_exact_and_unique_invoice_prefixes(tmp_path: Path, authority_operation) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(client_id, periods=None),
        prepare_profile=_prepare(authority_operation),
    ) as session:
        fixture = session.prepared
        with override_settings(cadrumo_cli_reveal_identifiers=True):
            listed = session.invoke_password("app", "ledger", "invoice", "list")
            if listed.exit_code != 0:
                error = cast(dict[str, object], require_error_document(listed.output)["error"])
                context_value = error.get("context")
                raw_context = cast(dict[str, object], context_value if isinstance(context_value, dict) else {})
                safe_context = {
                    key: value
                    for key in ("reason", "refusal_code", "effect", "terminal_condition")
                    if isinstance((value := raw_context.get(key)), str)
                    and len(value) <= 80
                    and all(character.isascii() and (character.isalnum() or character in "_.-") for character in value)
                }
                pytest.fail(
                    "native invoice list failed at its CLI boundary: "
                    f"code={error.get('code')!r}, category={error.get('category')!r}, context={safe_context!r}",
                    pytrace=False,
                )
            inventory = unwrap_cli_result(listed)
            assert inventory["count"] == 3
            rows = cast(list[dict[str, object]], inventory["rows"])
            assert {cast(str, row["invoice_id"]) for row in rows} == set(fixture.catalogue.invoices)

            exact = session.invoke_password("app", "ledger", "invoice", "view", fixture.unique_invoice_id)
            assert exact.exit_code == 0
            assert unwrap_cli_result(exact)["invoice_id"] == fixture.unique_invoice_id

            prefix = fixture.unique_invoice_id[:8]
            assert sum(invoice_id.startswith(prefix) for invoice_id in fixture.catalogue.invoices) == 1
            selected = session.invoke_password("app", "ledger", "invoice", "view", prefix)
            assert selected.exit_code == 0
            assert unwrap_cli_result(selected)["invoice_id"] == fixture.unique_invoice_id

            ambiguous = session.invoke_password("app", "ledger", "invoice", "view", fixture.ambiguous_prefix)
            assert ambiguous.exit_code == 2
            error = require_error_document(ambiguous.output)["error"]
            context = cast(dict[str, object], error["context"])
            assert error["code"] == "REFUSED_CLI_BOUNDARY"
            assert context["refusal_code"] == INVOICE_VIEW_REFUSAL_CODE
            assert context["terminal_condition"] == "refused"
            assert context["effect"] == "none"
            assert context["invoice_id"] == fixture.ambiguous_prefix
            assert tuple(cast(str, context["candidates"]).split(", ")) == fixture.ambiguous_invoice_ids

        assert _catalogue_after_password_login(session.profile_id, authority_operation) == fixture.catalogue


def test_native_invoice_reads_refuse_finite_period_grants_before_submission(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(client_id, periods=frozenset({_FIRST_PERIOD})),
        prepare_profile=_prepare(authority_operation),
    ) as session:
        fixture = session.prepared
        for command in (
            ("app", "ledger", "invoice", "list"),
            ("app", "ledger", "invoice", "view", fixture.unique_invoice_id),
        ):
            refused = session.invoke_credential_reference(*command)
            assert refused.exit_code == 2
            error = require_error_document(refused.output)["error"]
            assert error["code"] == "REFUSED_RUNTIME_FRONTEND"
            context = cast(dict[str, object], error["context"])
            assert context == {"reason": "period_denied"}

        assert _catalogue_after_password_login(session.profile_id, authority_operation) == fixture.catalogue


def test_native_invoice_result_denial_preserves_read_receipt_and_catalogue(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(client_id, periods=None, result=False),
        prepare_profile=_prepare(authority_operation),
    ) as session:
        fixture = session.prepared
        refused = session.invoke_credential_reference("app", "ledger", "invoice", "view", fixture.unique_invoice_id)
        assert refused.exit_code == 2
        error = require_error_document(refused.output)["error"]
        assert error["code"] == "REFUSED_CLI_BOUNDARY"
        context = cast(dict[str, object], error["context"])
        assert context["reason"] == "operation_denied"
        assert context["terminal_condition"] == "succeeded"
        assert context["effect"] == "none"
        assert isinstance(context["operation_id"], str)

        assert _catalogue_after_password_login(session.profile_id, authority_operation) == fixture.catalogue


def test_native_invoice_remove_refuses_without_yes_and_preserves_updated_receipt(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The confirmation gate is pre-submit; a committed delete keeps its receipt if RESULT is denied."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(
            client_id,
            periods=None,
            result=False,
            commit=True,
            operation_ids=frozenset({INVOICE_REMOVE_OPERATION_DEFINITION_ID}),
        ),
        prepare_profile=_prepare(authority_operation),
    ) as session:
        fixture = session.prepared
        refused = session.invoke_credential_reference("app", "ledger", "invoice", "remove", fixture.unique_invoice_id)
        assert refused.exit_code == 2
        assert _catalogue_after_password_login(session.profile_id, authority_operation) == fixture.catalogue

        committed = session.invoke_credential_reference(
            "app", "ledger", "invoice", "remove", fixture.unique_invoice_id, "--yes"
        )
        assert committed.exit_code == 2
        error = require_error_document(committed.output)["error"]
        assert error["code"] == "REFUSED_CLI_BOUNDARY"
        context = cast(dict[str, object], error["context"])
        assert context["reason"] == "operation_denied"
        assert context["terminal_condition"] == "succeeded"
        assert context["effect"] == "updated"
        assert isinstance(context["operation_id"], str)

        after = _catalogue_after_password_login(session.profile_id, authority_operation)
        expected = InvoiceCatalogue(
            invoices={
                invoice_id: invoice
                for invoice_id, invoice in fixture.catalogue.invoices.items()
                if invoice_id != fixture.unique_invoice_id
            }
        )
        assert after == expected


def test_native_invoice_update_commits_partial_patch_with_persisted_audit_receipt(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The real worker applies only selected corrections and returns its durable event id."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(
            client_id,
            periods=None,
            result=True,
            commit=True,
            operation_ids=frozenset({INVOICE_UPDATE_OPERATION_DEFINITION_ID}),
        ),
        prepare_profile=_prepare(authority_operation),
    ) as session:
        fixture = session.prepared
        invoice_id = fixture.unique_invoice_id
        original = fixture.catalogue.invoices[invoice_id]
        updated = session.invoke_credential_reference(
            "app",
            "ledger",
            "invoice",
            "update",
            invoice_id,
            "--counterparty-name",
            "Corrected native supplier",
            "--retention-amount",
            "0.00",
        )
        assert updated.exit_code == 0
        receipt = unwrap_cli_result(updated)
        assert receipt["invoice_id"] == invoice_id
        assert receipt["counterparty_name"] == "Corrected native supplier"
        assert Decimal(str(receipt["retention_amount"])) == Decimal("0.00")
        event_ids = cast(list[str], receipt["bucket_event_ids"])
        assert len(event_ids) == 1

        after = _catalogue_after_password_login(session.profile_id, authority_operation)
        assert set(after.invoices) == set(fixture.catalogue.invoices)
        corrected = after.invoices[invoice_id]
        assert corrected.invoice_id == original.invoice_id
        assert corrected.counterparty_name == "Corrected native supplier"
        assert corrected.retention_amount == Decimal("0.00")
        assert corrected.notes == original.notes
        assert corrected.linked_transaction_ids == original.linked_transaction_ids
        assert (
            corrected.model_copy(
                update={
                    "counterparty_name": original.counterparty_name,
                    "retention_amount": original.retention_amount,
                    "updated_at": original.updated_at,
                }
            )
            == original
        )
        for other_id, other_invoice in fixture.catalogue.invoices.items():
            if other_id != invoice_id:
                assert after.invoices[other_id] == other_invoice

        events = _events_after_password_login(session.profile_id, authority_operation)
        assert all(event_id in events.events for event_id in event_ids)
        assert any(
            events.events[event_id].object_id == invoice_id
            and events.events[event_id].event_type is BucketEventType.PAYABLE_INVOICE_UPDATED
            for event_id in event_ids
        )
