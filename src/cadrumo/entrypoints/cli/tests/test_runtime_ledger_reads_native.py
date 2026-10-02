"""Human-password status, history, view, and track use the encrypted profile worker."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from ....application.ledger.actions_manual import (
    get_manual_transaction,
    ledger_transaction_payload,
    ledger_transaction_result_payload,
    ledger_transaction_tracking_payload,
    summarize_manual_transactions,
)
from ....application.ledger.history_query import LEDGER_HISTORY_EVENT_TYPES
from ....application.ledger.models import LedgerStatusReport
from ....application.ledger.readiness_query import read_ledger_readiness
from ....application.ledger.stale_filing_query import read_stale_ledger_filings
from ....application.ledger.status_operation import LEDGER_STATUS_OPERATION_DEFINITION_ID
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....application.user_profile.tests.profile_values import complete_profile_facts
from ....core.config import override_settings
from ....core.period import Period
from ....core.redaction.rules import redact_structured_for_cli_output
from ....domain.buckets.event import BucketEventObjectType, BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ...ledger_action_composition import compose_ledger_action_ports
from ._modelo_work_ux_support import operator_profile_facts
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import native_api_cli_session
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _invoke_with_human_password(
    fixture: NativeCliProfileFixture,
    *,
    label: str,
    command: tuple[str, ...],
    output_format: str = "json",
) -> Result:
    """Run one named-profile CLI command through its protected password channel."""
    with override_settings(cadrumo_cli_reveal_identifiers=False):
        result = invoke_cached_cli(
            (
                "--format",
                output_format,
                "--profile",
                label,
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


def _assert_status_matches_canonical_report(payload: dict[str, object], report: LedgerStatusReport) -> None:
    """Compare every summary field to the report built from decrypted rows."""
    expected = cast(
        "dict[str, object]",
        redact_structured_for_cli_output(report.model_dump(mode="json"), reveal_identifiers=False),
    )
    for field, value in expected.items():
        assert payload[field] == value


def test_native_human_cli_reads_encrypted_ledger_status_history_view_and_track(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Read all four ledger surfaces through a real encrypted profile session."""
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(
            label="native-ledger-reader",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Ledger",
                "identity.surnames": "Reader",
                "activities.description": "design",
                "censo.activity_start_date": "2025-01-01",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        assert fixture.label is not None
        label = fixture.label
        close_active_bucket_session()
        seeded = _invoke_with_human_password(
            fixture,
            label=label,
            command=(
                "app",
                "ledger",
                "add",
                "--date",
                "2026-02-10",
                "--amount",
                "242.00",
                "--direction",
                "OUTGOING",
                "--description",
                "Q1 business expense missing tax facts",
                "--classification",
                "BUSINESS",
                "--actor",
                "native-ledger-reader",
                "--idempotency-key",
                "native-ledger-status-history",
            ),
        )
        assert seeded.exit_code == 0, seeded.output
        seeded_payload = unwrap_cli_result(seeded)
        cli_bucket_id = cast(str, seeded_payload["bucket_id"])
        transaction_id = cast(str, seeded_payload["transaction_id"])
        assert len(transaction_id) == 64
        resolved_target = resolve_login_target(label)
        bucket_id = resolved_target.bucket_id
        expected_cli_bucket_id = redact_structured_for_cli_output({"bucket_id": bucket_id}, reveal_identifiers=False)[
            "bucket_id"
        ]
        assert cli_bucket_id == expected_cli_bucket_id
        assert seeded_payload["bucket_id"] == expected_cli_bucket_id

        unfiltered = _invoke_with_human_password(fixture, label=label, command=("app", "ledger", "status"))
        assert unfiltered.exit_code == 0, unfiltered.output
        unfiltered_payload = unwrap_cli_result(unfiltered)

        period = Period.from_year_and_code(2026, "1T")
        filtered = _invoke_with_human_password(
            fixture,
            label=label,
            command=("app", "ledger", "status", "--period", "1T", "--year", "2026"),
        )
        assert filtered.exit_code == 0, filtered.output
        filtered_payload = unwrap_cli_result(filtered)

        prefix = transaction_id[:12]
        history = _invoke_with_human_password(fixture, label=label, command=("app", "ledger", "history", prefix))
        assert history.exit_code == 0, history.output
        history_payload = unwrap_cli_result(history)

        view = _invoke_with_human_password(fixture, label=label, command=("app", "ledger", "view", prefix))
        assert view.exit_code == 0, view.output
        view_payload = unwrap_cli_result(view)

        track = _invoke_with_human_password(fixture, label=label, command=("app", "ledger", "track", prefix))
        assert track.exit_code == 0, track.output
        track_payload = unwrap_cli_result(track)

        view_text = _invoke_with_human_password(
            fixture, label=label, command=("app", "ledger", "view", prefix), output_format="text"
        )
        assert view_text.exit_code == 0, view_text.output
        assert transaction_id in view_text.output
        assert "Q1 business expense missing tax facts" in view_text.output

        track_text = _invoke_with_human_password(
            fixture, label=label, command=("app", "ledger", "track", prefix), output_format="text"
        )
        assert track_text.exit_code == 0, track_text.output
        assert transaction_id in track_text.output
        assert unfiltered_payload["bucket_id"] == expected_cli_bucket_id
        assert filtered_payload["bucket_id"] == expected_cli_bucket_id
        assert history_payload["bucket_id"] == expected_cli_bucket_id

        # The CLI calls have closed their password-authenticated worker sessions.
        # Reauthenticate with the actual fixture password before reading the
        # encrypted catalogue and append-only event history as the oracle.
        close_active_bucket_session()
        login = login_profile(
            name=label,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        active_session = current_active_bucket_session()
        assert login.bucket_id == bucket_id
        assert active_session is not None
        assert active_session.bucket_id == bucket_id, (
            f"encrypted oracle session bound {active_session.bucket_id}, expected requested profile {bucket_id}"
        )
        try:
            ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
            catalogue = TransactionCatalogueRepository(bucket_id=bucket_id).load()
            stored = catalogue.get(transaction_id)
            assert stored is not None
            assert stored.transaction_id == transaction_id
            assert stored.created_event_id is not None
            assert stored.raw.amount == 242

            all_report = summarize_manual_transactions(bucket_id=bucket_id, ports=ports, catalogue=catalogue)
            period_report = summarize_manual_transactions(
                bucket_id=bucket_id, period=period, ports=ports, catalogue=catalogue
            )
            readiness = read_ledger_readiness(
                bucket_id=bucket_id,
                period=period,
                transaction_repository=ports.transaction_repository,
                usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
                operation=authority_operation,
            )
            stale = read_stale_ledger_filings(
                bucket_id=bucket_id,
                revisions=ports.calculation_repository.load(operation=authority_operation).revisions,
                work_units=ports.work_unit_repository.load(),
                transactions=catalogue,
            )
            manual = get_manual_transaction(bucket_id=bucket_id, transaction_id=transaction_id, ports=ports)
            canonical_view = ledger_transaction_result_payload(manual).model_dump(mode="json")
            canonical_track = {
                "bucket_id": bucket_id,
                "transaction": ledger_transaction_payload(manual.transaction).model_dump(mode="json"),
                "tracking": ledger_transaction_tracking_payload(manual.transaction).model_dump(mode="json"),
                "source_filename": None,
                "source_row_index": None,
                "participated_in": None,
            }
            participation = TransactionParticipationIndexRepository(bucket_id=bucket_id).load(transaction_id)
            events = (
                BucketEventHistoryRepository()
                .load()
                .for_object(
                    object_type=BucketEventObjectType.LEDGER_TRANSACTION,
                    object_id=transaction_id,
                )
            )
            history_events = tuple(event for event in events if event.event_type in LEDGER_HISTORY_EVENT_TYPES)
        finally:
            close_active_bucket_session()

        _assert_status_matches_canonical_report(unfiltered_payload, all_report)
        _assert_status_matches_canonical_report(filtered_payload, period_report)
        assert filtered_payload["period"] == {"filing_year": 2026, "code": "1T"}
        assert filtered_payload["checked_transaction_count"] == period_report.checked_transaction_count == 1
        assert filtered_payload["readiness_issue_count"] == len(readiness)
        assert filtered_payload["readiness_issues"] == redact_structured_for_cli_output(
            [issue.model_dump(mode="json") for issue in readiness], reveal_identifiers=False
        )
        expected_stale_filings = redact_structured_for_cli_output(
            [finding.model_dump(mode="json") for finding in stale], reveal_identifiers=False
        )
        assert unfiltered_payload["stale_filings"] == expected_stale_filings
        assert filtered_payload["stale_filings"] == expected_stale_filings

        assert view_payload == redact_structured_for_cli_output(canonical_view, reveal_identifiers=False)
        assert participation.transaction_id == transaction_id
        assert participation.participations == ()
        assert track_payload == redact_structured_for_cli_output(canonical_track, reveal_identifiers=False)
        assert track_payload["participated_in"] is None

        assert history_payload["transaction_id"] == stored.transaction_id
        assert history_payload["event_count"] == len(history_events) == 1
        expected_history_events = redact_structured_for_cli_output(
            [event.model_dump(mode="json") for event in history_events], reveal_identifiers=False
        )
        assert history_payload["events"] == expected_history_events
        assert history_events[0].event_id == stored.created_event_id
        assert history_events[0].event_type is BucketEventType.LEDGER_TRANSACTION_CREATED
        assert history_events[0].actor == "native-ledger-reader"
        assert history_events[0].payload["source_command"] == "aeat app ledger add"


def test_native_api_ledger_status_requires_all_periods_even_when_query_selects_one(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A matching CLI period cannot narrow a grant for whole-profile status."""
    period = Period.from_year_and_code(2026, "1T")

    def prepare_profile(profile_id: UUID, root: Path) -> None:
        facts = complete_profile_facts(
            authority_operation.profile_schema(),
            facts=tuple(
                UserProfileFact(path=path, value=value)
                for path, value in operator_profile_facts(activity_start_date="2025-01-01").items()
            ),
        )
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE
        seeded = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "ledger",
                "add",
                "--date",
                "2026-02-10",
                "--amount",
                "242.00",
                "--direction",
                "OUTGOING",
                "--description",
                "Whole-profile status grant seed",
                "--classification",
                "BUSINESS",
                "--actor",
                "native-api-ledger-status",
                "--idempotency-key",
                "native-api-ledger-status-seed",
            ]
        )
        assert seeded.exit_code == 0, seeded.output

    def scope_for_destination(
        client_id: UUID,
        *,
        periods: frozenset[Period] | None,
    ) -> AccessScope:
        return AccessScope(
            operations=frozenset({LEDGER_STATUS_OPERATION_DEFINITION_ID}),
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                }
            ),
            disclosures=frozenset(
                {
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{LEDGER_STATUS_OPERATION_DEFINITION_ID}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    ),
                }
            ),
            periods=periods,
            allow_period_independent=True,
            allow_delegation=False,
        )

    def finite_period_scope(client_id: UUID) -> AccessScope:
        return scope_for_destination(client_id, periods=frozenset({period}))

    def whole_profile_scope(client_id: UUID) -> AccessScope:
        return scope_for_destination(client_id, periods=None)

    command = ("app", "ledger", "status", "--period", "1T", "--year", "2026")
    with native_api_cli_session(
        tmp_path / "finite-period",
        scope_for_destination=finite_period_scope,
        prepare_profile=prepare_profile,
    ) as finite:
        refused = finite.invoke_credential_reference(*command)
        assert refused.exit_code == 2, refused.output
        error = require_error_document(refused.output)["error"]
        assert error["code"] == "REFUSED_RUNTIME_FRONTEND"
        assert error["context"] == {"reason": "period_denied"}
        assert "business_expense_total" not in refused.output

    with native_api_cli_session(
        tmp_path / "all-periods",
        scope_for_destination=whole_profile_scope,
        prepare_profile=prepare_profile,
    ) as whole_profile:
        accepted = whole_profile.invoke_credential_reference(*command)
        assert accepted.exit_code == 0, accepted.output
        result = unwrap_cli_result(accepted)
        assert result["period"] == {"filing_year": 2026, "code": "1T"}
        assert result["total_count"] == 1
        assert result["business_expense_total"] == "242"
