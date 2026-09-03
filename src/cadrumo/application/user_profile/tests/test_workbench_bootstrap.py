"""Truthful installed-workbench profile bootstrap contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ....core.profile_discovery import ProfileSummaryOutcome
from ....core.profile_publication import ProfilePublicationKind
from ..login_interaction import ProfileLoginChoice
from ..login_session import ProfileLoginOutcome
from ..profile_summary import ProfileSummary, ProfileSummaryInventory
from ..workbench_bootstrap import (
    WorkbenchBootstrapInventoryState,
    WorkbenchBootstrapSessionState,
    complete_workbench_login,
    prepare_workbench_bootstrap,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)
_PROFILE = "11111111-1111-4111-8111-111111111111"


def _inventory(*, label: str = "Operator") -> ProfileSummaryInventory:
    return ProfileSummaryInventory(
        summaries=(
            ProfileSummary(
                profile_id=_PROFILE,
                label=label,
                label_revision=1,
                published_at=_NOW,
                publication_kind=ProfilePublicationKind.ENROLL,
            ),
        )
    )


def _choice(*, label: str = "Operator") -> tuple[ProfileLoginChoice, ...]:
    return (ProfileLoginChoice(profile_id=_PROFILE, label=label),)


def test_degraded_inventory_never_reads_choices_or_attempts_resume() -> None:
    calls: list[str] = []
    result = prepare_workbench_bootstrap(
        inventory_reader=lambda: ProfileSummaryInventory(outcome=ProfileSummaryOutcome.DEGRADED),
        choice_reader=lambda: calls.append("choices") or (),
        preselection_reader=lambda _name: calls.append("preselection") or None,
        resume_session=lambda *, bucket_id: calls.append(bucket_id),
    )

    assert result.inventory_state is WorkbenchBootstrapInventoryState.DEGRADED
    assert result.session_state is None
    assert result.reason_code == "workbench.bootstrap.profile_inventory_unavailable"
    assert calls == []


def test_concurrent_inventory_is_a_distinct_refusal_without_choices_or_resume() -> None:
    calls: list[str] = []
    result = prepare_workbench_bootstrap(
        inventory_reader=lambda: ProfileSummaryInventory(outcome=ProfileSummaryOutcome.CONCURRENT_CHANGE),
        choice_reader=lambda: calls.append("choices") or (),
        preselection_reader=lambda _name: calls.append("preselection") or None,
        resume_session=lambda *, bucket_id: calls.append(bucket_id),
    )

    assert result.inventory_state is WorkbenchBootstrapInventoryState.CONCURRENT_CHANGE
    assert result.session_state is None
    assert result.reason_code == "workbench.bootstrap.profile_inventory_concurrent_change"
    assert calls == []


def test_empty_inventory_is_explicit_registration_requirement_not_login() -> None:
    result = prepare_workbench_bootstrap(
        inventory_reader=ProfileSummaryInventory,
        choice_reader=lambda: pytest.fail("empty inventory must not fabricate login choices"),
    )

    assert result.inventory_state is WorkbenchBootstrapInventoryState.EMPTY
    assert result.session_state is None
    assert result.registration_required is not None
    assert result.registration_required.reason_code == "workbench.bootstrap.registration_required"


def test_selected_profile_resumes_once_and_returns_safe_selected_identity() -> None:
    resumed: list[str] = []
    result = prepare_workbench_bootstrap(
        inventory_reader=_inventory,
        choice_reader=_choice,
        preselection_reader=lambda _name: _PROFILE,
        resume_session=lambda *, bucket_id: resumed.append(bucket_id),
    )

    assert result.inventory_state is WorkbenchBootstrapInventoryState.RECOGNIZED
    assert result.session_state is WorkbenchBootstrapSessionState.RESUMED
    assert result.selected_profile_id == _PROFILE
    assert result.selected_profile_label == "Operator"
    assert resumed == [_PROFILE]
    assert "11111111" not in repr(result)


def test_refused_resume_requires_login_and_login_completion_is_closed() -> None:
    prepared = prepare_workbench_bootstrap(
        inventory_reader=_inventory,
        choice_reader=_choice,
        preselection_reader=lambda _name: _PROFILE,
        resume_session=lambda *, bucket_id: "expired",
    )
    authenticated = complete_workbench_login(
        prepared,
        ProfileLoginOutcome(
            bucket_id=_PROFILE,
            label="Operator",
            authenticated_at=_NOW,
            idle_deadline=_NOW + timedelta(minutes=30),
            absolute_deadline=_NOW + timedelta(hours=8),
            session_persisted=False,
            already_authenticated=False,
        ),
    )
    cancelled = complete_workbench_login(prepared, None)

    assert prepared.session_state is WorkbenchBootstrapSessionState.LOGIN_REQUIRED
    assert authenticated.session_state is WorkbenchBootstrapSessionState.AUTHENTICATED
    assert authenticated.selected_profile_id == _PROFILE
    assert cancelled.session_state is WorkbenchBootstrapSessionState.CANCELLED
    assert cancelled.selected_profile_id is None


def test_changed_inventory_fails_closed_before_preselection_or_resume() -> None:
    calls: list[str] = []
    result = prepare_workbench_bootstrap(
        inventory_reader=_inventory,
        choice_reader=lambda: _choice(label="Changed concurrently"),
        preselection_reader=lambda _name: calls.append("preselection") or _PROFILE,
        resume_session=lambda *, bucket_id: calls.append(bucket_id),
    )

    assert result.inventory_state is WorkbenchBootstrapInventoryState.DEGRADED
    assert result.reason_code == "workbench.bootstrap.profile_inventory_changed"
    assert calls == []


def test_login_outcome_cannot_select_profile_absent_from_recognized_inventory() -> None:
    prepared = prepare_workbench_bootstrap(
        inventory_reader=_inventory,
        choice_reader=_choice,
        preselection_reader=lambda _name: None,
    )
    with pytest.raises(ValueError, match="absent from the recognized bootstrap inventory"):
        complete_workbench_login(
            prepared,
            ProfileLoginOutcome(
                bucket_id="22222222-2222-4222-8222-222222222222",
                label="Foreign",
                authenticated_at=_NOW,
                idle_deadline=_NOW + timedelta(minutes=30),
                absolute_deadline=_NOW + timedelta(hours=8),
                session_persisted=False,
                already_authenticated=False,
            ),
        )


def test_login_outcome_label_must_match_the_admitted_profile_choice() -> None:
    prepared = prepare_workbench_bootstrap(
        inventory_reader=_inventory,
        choice_reader=_choice,
        preselection_reader=lambda _name: None,
    )
    with pytest.raises(ValueError, match="label disagrees with the recognized bootstrap inventory"):
        complete_workbench_login(
            prepared,
            ProfileLoginOutcome(
                bucket_id=_PROFILE,
                label="Injected mismatch",
                authenticated_at=_NOW,
                idle_deadline=_NOW + timedelta(minutes=30),
                absolute_deadline=_NOW + timedelta(hours=8),
                session_persisted=False,
                already_authenticated=False,
            ),
        )
