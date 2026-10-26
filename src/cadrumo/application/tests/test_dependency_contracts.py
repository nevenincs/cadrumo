"""Boundary proofs for the setup item vocabulary the surfaces decode: identities and status rows."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemKind,
    DependencyNote,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
    dependency_item_kind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_item_identities_are_the_two_kinds_and_nothing_else() -> None:
    assert dependency_item_kind("browser") is DependencyItemKind.BROWSER
    assert dependency_item_kind("local_ai") is DependencyItemKind.LOCAL_AI
    # The local AI's program and models are parts of one item, and the Google
    # account is the profile's own sign-in: none of them is an item.
    for refused in ("model_runtime", "local_model", "local_model.text_extraction", "google", "chromium"):
        with pytest.raises(ValueError):
            dependency_item_kind(refused)


def test_status_rows_carry_exactly_the_reason_their_state_needs() -> None:
    stale = DependencyStatusRow(
        item_id="browser",
        kind=DependencyItemKind.BROWSER,
        mode=DependencyCheckMode.QUICK,
        state=DependencyState.STALE,
        stale_reason=DependencyStaleReason.OLDER_REVISION,
    )
    assert stale.stale_reason is DependencyStaleReason.OLDER_REVISION
    refused = (
        {"state": DependencyState.STALE},
        {"state": DependencyState.BLOCKED},
        {"state": DependencyState.FAILED},
        {"state": DependencyState.READY, "failure_category": DependencyFailureCategory.UNEXPECTED},
        {"state": DependencyState.ABSENT, "blocked_reason": DependencyBlockedReason.OFFLINE},
        {"state": DependencyState.ABSENT, "note": DependencyNote.DOWNLOADED_NOT_LOADED},
    )
    for fields in refused:
        with pytest.raises(ValidationError):
            DependencyStatusRow.model_validate(
                {"item_id": "browser", "kind": DependencyItemKind.BROWSER, "mode": DependencyCheckMode.QUICK, **fields}
            )


def test_status_rows_pair_a_recovery_button_with_its_operator_action() -> None:
    with pytest.raises(ValidationError, match="offered together"):
        DependencyStatusRow(
            item_id="browser",
            kind=DependencyItemKind.BROWSER,
            mode=DependencyCheckMode.QUICK,
            state=DependencyState.ABSENT,
            recovery_action_id="operator.provision.browser",
        )
    with pytest.raises(ValidationError, match="kind"):
        DependencyStatusRow(
            item_id="local_ai",
            kind=DependencyItemKind.BROWSER,
            mode=DependencyCheckMode.QUICK,
            state=DependencyState.ABSENT,
        )
