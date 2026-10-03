"""Exact-profile runtime coverage for canonical invoice creation."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from ....application.invoices.catalogue_add_contracts import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    INVOICE_ADD_VALIDATION_REFUSAL_CODE,
)
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.login_session import login_profile
from ....application.user_profile.tests.profile_values import complete_profile_facts
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_INVOICE_ADD_OPERATIONS = frozenset({INVOICE_ADD_OPERATION_DEFINITION_ID})


def _scope(
    client_id: UUID,
    operation_ids: frozenset[str] = _INVOICE_ADD_OPERATIONS,
    *,
    profile_value_operation_ids: frozenset[str] = frozenset(),
) -> AccessScope:
    return AccessScope(
        operations=operation_ids,
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
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
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.PROFILE_VALUES,
                    )
                    for definition_id in profile_value_operation_ids
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


_LEDGER_ADD_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Add",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _prepare_profile(
    profile_id: UUID,
    root: Path,
    *,
    authority_operation: PinnedAuthorityOperation | None = None,
) -> None:
    """Optionally complete taxpayer facts for native ledger transaction setup."""
    if authority_operation is None:
        return
    facts = complete_profile_facts(
        authority_operation.profile_schema(),
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in _LEDGER_ADD_PROFILE_FACTS.items()),
    )
    populated = upsert_test_profile_facts(profile_id, facts, root=root)
    with bound_test_profile_record(profile_id, root=root) as repository:
        ready = repository.complete_setup(
            profile_id,
            expected_revision=populated.record_revision,
            expected_content_digest=populated.content_digest,
        )
    assert ready.setup_state is ProfileSetupState.COMPLETE


def native_invoice_runtime_session(
    tmp_path: Path,
    *,
    operation_ids: frozenset[str] = _INVOICE_ADD_OPERATIONS,
    profile_value_operation_ids: frozenset[str] = frozenset(),
    authority_operation: PinnedAuthorityOperation | None = None,
) -> AbstractContextManager[NativeApiCliSession[None]]:
    """Open the native worker with an exact grant for the supplied operation set."""
    return native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(
            client_id,
            operation_ids,
            profile_value_operation_ids=profile_value_operation_ids,
        ),
        prepare_profile=lambda profile_id, root: _prepare_profile(
            profile_id,
            root,
            authority_operation=authority_operation,
        ),
    )


def catalogue_after_password_login(profile_id: UUID, authority_operation: PinnedAuthorityOperation) -> InvoiceCatalogue:
    close_active_bucket_session()
    login = login_profile(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=authority_operation.profile_decode_context(),
    )
    assert login.bucket_id == str(profile_id)
    try:
        return InvoiceCatalogueRepository(bucket_id=str(profile_id)).load()
    finally:
        close_active_bucket_session()


@contextmanager
def password_profile_session(profile_id: UUID, authority_operation: PinnedAuthorityOperation) -> Iterator[None]:
    """Open the enrolled profile for a direct repository assertion."""
    close_active_bucket_session()
    login = login_profile(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=authority_operation.profile_decode_context(),
    )
    assert login.bucket_id == str(profile_id)
    try:
        yield
    finally:
        close_active_bucket_session()


def _add_arguments(*, number: str) -> tuple[str, ...]:
    return (
        "app",
        "ledger",
        "invoice",
        "add",
        "--kind",
        "received",
        "--counterparty-nif",
        "A58818501",
        "--counterparty-name",
        "Runtime supplier SL",
        "--invoice-number",
        number,
        "--invoice-date",
        "2026-03-10",
        "--country-code",
        "ES",
        "--taxable-base",
        "100.00",
        "--iva-rate",
        "21",
    )


def test_native_invoice_add_commits_to_its_exact_profile_and_reads_back(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """The registered add worker commits a linkable invoice to the enrolled profile."""
    with native_invoice_runtime_session(tmp_path) as session:
        added = session.invoke_password(*_add_arguments(number="RUNTIME-ADD-001"))
        assert added.exit_code == 0, added.output
        result = unwrap_cli_result(added)
        invoice_id = cast(str, result["invoice_id"])
        assert len(invoice_id) == 64

        catalogue = catalogue_after_password_login(session.profile_id, authority_operation)
        assert set(catalogue.invoices) == {invoice_id}
        stored = catalogue.invoices[invoice_id]
        assert stored.bucket_id == str(session.profile_id)
        assert stored.invoice_number == "RUNTIME-ADD-001"
        assert stored.grand_total == stored.base_total + stored.iva_total


def test_native_invoice_add_refusal_leaves_the_catalogue_unchanged(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """A domain-invalid request reaches the exact-profile worker and publishes no invoice."""
    with native_invoice_runtime_session(tmp_path) as session:
        before = catalogue_after_password_login(session.profile_id, authority_operation)
        refused = session.invoke_password(
            *_add_arguments(number="RUNTIME-ADD-INVALID-001"),
            "--retention-rate",
            "0.15",
        )
        assert refused.exit_code == 2, refused.output
        error = require_error_document(refused.output)["error"]
        context = cast(dict[str, object], error["context"])
        assert error["code"] == "REFUSED_CLI_BOUNDARY"
        assert context["refusal_code"] == INVOICE_ADD_VALIDATION_REFUSAL_CODE
        assert context["terminal_condition"] == "refused"
        assert context["effect"] == "none"
        assert isinstance(context["operation_id"], str) and len(context["operation_id"]) == 64
        assert "0.15" not in refused.output

        after = catalogue_after_password_login(session.profile_id, authority_operation)
        assert after == before


def test_native_duplicate_invoice_add_is_refused_without_a_second_record(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """The exact-profile worker preserves duplicate identity refusal semantics."""
    with native_invoice_runtime_session(tmp_path) as session:
        first = session.invoke_password(*_add_arguments(number="RUNTIME-DUPLICATE-001"))
        assert first.exit_code == 0, first.output
        first_result = unwrap_cli_result(first)
        invoice_id = cast(str, first_result["invoice_id"])
        before = catalogue_after_password_login(session.profile_id, authority_operation)
        assert set(before.invoices) == {invoice_id}

        duplicate = session.invoke_password(*_add_arguments(number="RUNTIME-DUPLICATE-001"))
        assert duplicate.exit_code == 2, duplicate.output
        error = require_error_document(duplicate.output)["error"]
        context = cast(dict[str, object], error["context"])
        assert error["code"] == "REFUSED_CLI_BOUNDARY"
        assert context["refusal_code"] == INVOICE_ADD_VALIDATION_REFUSAL_CODE
        assert context["terminal_condition"] == "refused"
        assert context["effect"] == "none"
        assert isinstance(context["operation_id"], str) and len(context["operation_id"]) == 64
        message = str(error["message"])
        assert invoice_id in message, error

        after = catalogue_after_password_login(session.profile_id, authority_operation)
        assert after == before
        assert set(after.invoices) == {invoice_id}
