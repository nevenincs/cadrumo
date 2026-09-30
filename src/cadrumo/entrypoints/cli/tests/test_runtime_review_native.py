"""Native profile proof for authenticated application review queue and item reads."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import pytest
from click.testing import Result
from pydantic import BaseModel

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.review.read_operation import (
    REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ReviewQueueReadRequest,
    ReviewViewReadRequest,
)
from ....application.user_profile.login_session import login_profile
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ...tests.review_read_operation_test_support import (
    ReviewReadConformanceCase,
    prepare_review_read_conformance_case,
)
from ._runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    RuntimeFailureObservation,
    native_cli_profile_scope,
)
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.tax_id": "00000000T",
    "identity.name": "Native",
    "identity.surnames": "Review",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "contact.postcode": "28013",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _invoke(
    profile: NativeCliProfileFixture,
    *command: str,
    env: Mapping[str, str | None] | None = None,
) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        ("--language", "en", "--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
        env=env,
    )
    assert profile.passphrase not in result.output
    return result


def _seed_case(
    profile: NativeCliProfileFixture,
    *,
    operation: PinnedAuthorityOperation,
    definition_id: str,
) -> ReviewReadConformanceCase:
    assert profile.label is not None
    login = login_profile(
        name=profile.label,
        passphrase_callback=lambda: profile.passphrase,
        profile_decode_context=operation.profile_decode_context(),
    )
    try:
        return prepare_review_read_conformance_case(
            definition_id,
            profile_id=UUID(login.bucket_id),
            operation=operation,
        )
    finally:
        close_active_bucket_session()


def _expected_row(case: ReviewReadConformanceCase) -> dict[str, object]:
    expected = case.expected_read
    row = getattr(expected, "row", None)
    if row is None:
        rows = getattr(expected, "rows", None)
        if not rows or len(rows) != 1:
            raise AssertionError("review queue fixture did not produce one expected row")
        row = rows[0]
    if not isinstance(row, BaseModel):
        raise AssertionError("review fixture expected row is not a Pydantic projection")
    return row.model_dump(mode="json")


def test_native_review_queue_and_item_view_match_encrypted_canonical_projection(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Both public routes disclose the complete row derived from encrypted storage."""
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-app-review", facts=_PROFILE_FACTS)

        queue_case = _seed_case(
            profile,
            operation=authority_operation,
            definition_id=REVIEW_QUEUE_OPERATION_DEFINITION_ID,
        )
        if not isinstance(queue_case.request, ReviewQueueReadRequest):
            raise AssertionError("review queue fixture returned another request type")
        row_id = _expected_row(queue_case)["item_id"]
        assert isinstance(row_id, str)
        queue = _invoke(
            profile,
            "app",
            "review",
            "queue",
            "--state",
            "pending",
            "--kind",
            "ledger_transaction",
            "--source-kind",
            "ledger_transaction",
            "--output-language",
            "en",
            "--explain",
        )
        assert queue.exit_code == 0, (queue.output, failures)
        queue_payload = unwrap_cli_result(queue)
        assert queue_payload == {"operation": "review.queue", "rows": [_expected_row(queue_case)]}

        view_case = _seed_case(
            profile,
            operation=authority_operation,
            definition_id=REVIEW_VIEW_OPERATION_DEFINITION_ID,
        )
        if not isinstance(view_case.request, ReviewViewReadRequest):
            raise AssertionError("review view fixture returned another request type")
        assert queue_case.request.profile_id == view_case.request.profile_id
        view = _invoke(profile, "app", "review", "view", row_id, "--output-language", "en")
        assert view.exit_code == 0, (view.output, failures)
        view_payload = unwrap_cli_result(view)
        assert view_payload == {"operation": "review.view", "row": _expected_row(view_case)}

        private_selector = "private-tax-id-12345678Z-review-kind"
        refused = _invoke(
            profile,
            "app",
            "review",
            "queue",
            "--kind",
            private_selector,
            "--output-language",
            "en",
        )
        assert refused.exit_code != 0, refused.output
        assert private_selector not in refused.output
        error = require_error_document(refused.output)["error"]
        assert error["category"] == "REFUSED"
        context = error["context"]
        assert context["refusal_code"] == "REFUSED_REVIEW_UNKNOWN_KIND"
        assert context["reason"] == "REFUSED_REVIEW_UNKNOWN_KIND"
        assert context["terminal_condition"] == "refused"
        assert context["effect"] == "none"
        assert isinstance(context["operation_id"], str) and len(context["operation_id"]) == 64
        assert failures == []
