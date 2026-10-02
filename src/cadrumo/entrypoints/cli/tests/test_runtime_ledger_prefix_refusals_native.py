"""Native CLI refusal contracts for registered ledger prefix reads."""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import product
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from ....application.ledger.actions_manual import create_manual_transaction
from ....application.ledger.models import ManualLedgerTransactionCommand
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....core.config import override_settings
from ....core.hashing import HEX_ALPHABET
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import TransactionDirection
from ....tests.cli_envelope import require_error_document
from ...ledger_action_composition import compose_ledger_action_ports
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PREFIX_REFUSAL_CODE = "REFUSED_FINANCIAL_LEDGER_TRANSACTION_ID_PREFIX"
_READ_VERBS = ("history", "view", "track")
_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Ledger",
    "identity.surnames": "Prefix Reader",
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


def _invoke_with_human_password(
    fixture: NativeCliProfileFixture,
    *,
    label: str,
    command: tuple[str, ...],
) -> Result:
    """Run one installed CLI command with the fixture's real profile password."""
    with override_settings(cadrumo_cli_reveal_identifiers=False):
        result = invoke_cached_cli(
            (
                "--format",
                "json",
                "--profile",
                label,
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


def _member(document: dict[str, object], key: str) -> dict[str, object]:
    value = document[key]
    assert isinstance(value, dict), f"{key!r} must be an object: {value!r}"
    return cast("dict[str, object]", value)


def _assert_prefix_refusal(
    result: Result,
    *,
    verb: str,
    submitted: bool,
    seen_operation_ids: set[str],
) -> None:
    """Check the stable no-recovery condition and the correct pre/post-submit receipt shape."""
    assert result.exit_code == 2, result.output
    document = require_error_document(result.output)
    assert document["status"] == "error"
    assert document["command"] == f"ledger.{verb}"
    error = _member(document, "error")
    assert error["category"] == "REFUSED"
    action = _member(error, "action")
    assert action["failed_condition_id"] == "cli.ledger.transaction_id.resolves"
    assert action["no_recovery_outcome"] == NoRecoveryOutcome.OPERATOR_DECISION.value
    evidence = action["evidence"]
    assert isinstance(evidence, list) and evidence
    first_evidence = cast("dict[str, object]", evidence[0])
    facts = _member(first_evidence, "values")
    assert facts["transaction_id_resolves"] is False

    context = _member(error, "context")
    if not submitted:
        assert error["code"] == _PREFIX_REFUSAL_CODE
        assert "operation_id" not in context
        assert "effect" not in context
        assert "terminal_condition" not in context
        return

    assert error["code"] == "REFUSED_CLI_BOUNDARY"
    assert context["reason"] == _PREFIX_REFUSAL_CODE
    operation_id = context.get("operation_id")
    assert isinstance(operation_id, str) and operation_id
    assert operation_id not in seen_operation_ids
    seen_operation_ids.add(operation_id)
    assert context["effect"] == OperationEffect.NONE.value
    assert context["terminal_condition"] == OperationTerminalCondition.REFUSED.value


def _seed_real_transactions_and_find_prefixes(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> tuple[str, str, tuple[str, ...]]:
    """Persist valid canonical transactions until a real one-nibble collision exists."""
    from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository

    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
    transaction_ids: list[str] = []
    prefix_groups: dict[str, list[str]] = {}
    for index in range(17):
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=bucket_id,
                booked_date=date(2026, 2, 10),
                amount=Decimal(100 + index),
                direction=TransactionDirection.OUTGOING,
                description=f"Native prefix refusal seed {index}",
                idempotency_key=f"native-prefix-refusal-{index}",
            ),
            ports=ports,
            occurred_at=datetime(2026, 2, 10, 12, 0, index, tzinfo=UTC),
        )
        transaction_id = created.transaction.transaction_id
        assert len(transaction_id) == 64
        transaction_ids.append(transaction_id)
        prefix_groups.setdefault(transaction_id[0], []).append(transaction_id)
        if len(prefix_groups[transaction_id[0]]) > 1:
            break

    assert len(transaction_ids) == len(set(transaction_ids))
    ambiguous = next(prefix for prefix, members in prefix_groups.items() if len(members) > 1)
    catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
    persisted_ids = {transaction.transaction_id for transaction in catalogue.values()}
    assert set(transaction_ids) <= persisted_ids
    historical_handles = {
        entry.previous_transaction_id for transaction in catalogue.values() for entry in transaction.edit_lineage
    }
    addressable_ids = persisted_ids | historical_handles
    alphabet = tuple(sorted(HEX_ALPHABET))
    missing = next(
        "".join(candidate)
        for width in (1, 2, 3)
        for candidate in product(alphabet, repeat=width)
        if not any(transaction_id.startswith("".join(candidate)) for transaction_id in addressable_ids)
    )
    return missing, ambiguous, tuple(transaction_ids)


def test_native_registered_ledger_reads_keep_prefix_refusal_policy_and_receipts(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Malformed, missing, and ambiguous handles refuse through all three worker-backed reads."""
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label="native-ledger-prefix-reader", facts=_PROFILE_FACTS)
        assert fixture.label is not None
        label = fixture.label
        bucket_id = resolve_login_target(label).bucket_id

        close_active_bucket_session()
        login = login_profile(
            name=label,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        assert login.bucket_id == bucket_id
        active_session = current_active_bucket_session()
        assert active_session is not None
        assert active_session.bucket_id == bucket_id
        missing, ambiguous, seeded_ids = _seed_real_transactions_and_find_prefixes(
            bucket_id=bucket_id,
            operation=authority_operation,
        )
        close_active_bucket_session()

        seen_operation_ids: set[str] = set()
        for verb in _READ_VERBS:
            malformed = _invoke_with_human_password(
                fixture,
                label=label,
                command=("app", "ledger", verb, "not-hex!"),
            )
            _assert_prefix_refusal(
                malformed,
                verb=verb,
                submitted=False,
                seen_operation_ids=seen_operation_ids,
            )

            absent = _invoke_with_human_password(
                fixture,
                label=label,
                command=("app", "ledger", verb, missing),
            )
            _assert_prefix_refusal(
                absent,
                verb=verb,
                submitted=True,
                seen_operation_ids=seen_operation_ids,
            )

            collision = _invoke_with_human_password(
                fixture,
                label=label,
                command=("app", "ledger", verb, ambiguous),
            )
            _assert_prefix_refusal(
                collision,
                verb=verb,
                submitted=True,
                seen_operation_ids=seen_operation_ids,
            )

        assert len(seen_operation_ids) == 6
        assert len(seeded_ids) >= 2
