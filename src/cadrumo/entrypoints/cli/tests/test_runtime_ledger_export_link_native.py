"""Exact-profile native worker coverage for ledger export and invoice link."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.invoices.catalogue_add_operation import INVOICE_ADD_OPERATION_DEFINITION_ID
from ....application.ledger.export_operation import LEDGER_EXPORT_OPERATION_DEFINITION_ID
from ....application.ledger.ledger_add_contracts import LEDGER_ADD_OPERATION_DEFINITION_ID
from ....application.ledger.link_operation import (
    LEDGER_LINK_OPERATION_DEFINITION_ID,
)
from ....core.redaction.rules import redact_structured_for_cli_output
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import NativeApiCliSession
from .test_runtime_invoice_add import native_invoice_runtime_session, password_profile_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_OPERATIONS = frozenset(
    {
        INVOICE_ADD_OPERATION_DEFINITION_ID,
        LEDGER_ADD_OPERATION_DEFINITION_ID,
        LEDGER_EXPORT_OPERATION_DEFINITION_ID,
        LEDGER_LINK_OPERATION_DEFINITION_ID,
    }
)
_PROFILE_VALUE_OPERATIONS = frozenset({LEDGER_EXPORT_OPERATION_DEFINITION_ID, LEDGER_LINK_OPERATION_DEFINITION_ID})
_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Export Link",
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
_SUPPLIER_CIF = "A58818501"


def _invoke(session: NativeApiCliSession[None], *command: str, output_format: str = "json") -> Result:
    """Run a protected-stdin invocation against the fixture's exact profile."""
    profile_label = session.profile_label
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--language",
            "en",
            "--format",
            output_format,
            "--profile",
            profile_label,
            "--profile-secrets-stdin",
            *command,
        ),
        input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
    )
    assert PROFILE_INPUT not in result.output
    return result


def test_native_export_filter_and_invoice_link_use_the_bound_worker(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Export filtered rows and link one invoice through the registered profile worker."""
    with native_invoice_runtime_session(
        tmp_path,
        operation_ids=_PROFILE_OPERATIONS,
        profile_value_operation_ids=_PROFILE_VALUE_OPERATIONS,
        authority_operation=authority_operation,
    ) as session:
        first_add = _invoke(
            session,
            "app",
            "ledger",
            "add",
            "--date",
            "2026-03-10",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Q1 supplier settlement",
            "--idempotency-key",
            "export-link-q1",
        )
        assert first_add.exit_code == 0, first_add.output
        first_transaction_id = cast(str, unwrap_cli_result(first_add)["transaction_id"])

        second_add = _invoke(
            session,
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "85.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Q2 supplier settlement",
            "--idempotency-key",
            "export-link-q2",
        )
        assert second_add.exit_code == 0, second_add.output
        second_transaction_id = cast(str, unwrap_cli_result(second_add)["transaction_id"])

        invoice_add = _invoke(
            session,
            "app",
            "ledger",
            "invoice",
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            _SUPPLIER_CIF,
            "--counterparty-name",
            "Native Supplier SL",
            "--invoice-number",
            "EXPORT-LINK-001",
            "--invoice-date",
            "2026-03-10",
            "--country-code",
            "ES",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "21",
        )
        assert invoice_add.exit_code == 0, invoice_add.output
        invoice_id = cast(str, unwrap_cli_result(invoice_add)["invoice_id"])

        output = (tmp_path / "q1-ledger.csv").resolve()
        exported = _invoke(
            session,
            "app",
            "ledger",
            "export",
            "--output",
            str(output),
            "--export-format",
            "csv",
            "--period",
            "1T",
            "--year",
            "2026",
        )
        assert exported.exit_code == 0, exported.output
        export_payload = unwrap_cli_result(exported)
        exported_bytes = output.read_bytes()
        assert export_payload["output_path"] == str(output)
        assert export_payload["row_count"] == 1
        assert export_payload["byte_size"] == len(exported_bytes)
        assert export_payload["sha256"] == hashlib.sha256(exported_bytes).hexdigest()
        export_rows = cast(list[dict[str, object]], export_payload["rows"])
        assert [row["description"] for row in export_rows] == ["Q1 supplier settlement"]
        csv_rows = list(csv.DictReader(io.StringIO(exported_bytes.decode("utf-8-sig"))))
        assert len(csv_rows) == 1
        assert csv_rows[0]["description"] == "Q1 supplier settlement"
        assert first_transaction_id in exported_bytes.decode("utf-8-sig")
        assert second_transaction_id not in exported_bytes.decode("utf-8-sig")

        linked = _invoke(
            session,
            "app",
            "ledger",
            "link",
            first_transaction_id[:12],
            "--invoice-id",
            invoice_id,
        )
        assert linked.exit_code == 0, linked.output
        expected_link_payload = redact_structured_for_cli_output(
            {
                "operation": "ledger.link",
                "bucket_id": str(session.profile_id),
                "transaction_id": first_transaction_id,
                "invoice_id": invoice_id,
                "actor": "operator",
            },
            reveal_identifiers=False,
        )
        assert unwrap_cli_result(linked) == expected_link_payload

        with password_profile_session(session.profile_id, authority_operation):
            bucket_id = str(session.profile_id)
            transaction = TransactionCatalogueRepository(bucket_id=bucket_id).load().get(first_transaction_id)
            invoice = InvoiceCatalogueRepository(bucket_id=bucket_id).load().get(invoice_id)
            assert transaction is not None and transaction.invoice_id == invoice_id
            assert invoice is not None and invoice.linked_transaction_ids == (first_transaction_id,)
            history_before_refusal = BucketEventHistoryRepository().load().events

        missing_invoice = "f" * 64
        refused = _invoke(
            session,
            "app",
            "ledger",
            "link",
            first_transaction_id[:12],
            "--invoice-id",
            missing_invoice,
        )
        assert refused.exit_code == 2, refused.output
        refusal_error = require_error_document(refused.output)["error"]
        assert "Invoice id not found in the active profile invoice catalogue." in cast(str, refusal_error["message"])

        with password_profile_session(session.profile_id, authority_operation):
            history_after_refusal = BucketEventHistoryRepository().load().events
        assert {
            key: event
            for key, event in history_after_refusal.items()
            if event.event_type is not BucketEventType.PROFILE_ACTIVATED
        } == {
            key: event
            for key, event in history_before_refusal.items()
            if event.event_type is not BucketEventType.PROFILE_ACTIVATED
        }
