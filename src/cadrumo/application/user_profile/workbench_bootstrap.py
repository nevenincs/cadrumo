"""Truthful profile-selection and authentication state for the installed workbench."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from ...core.profile_discovery import ProfileSummaryOutcome
from .login_interaction import (
    ProfileLoginChoice,
    preselected_profile_login_id,
    profile_login_choices,
)
from .login_session import ProfileLoginOutcome, bind_resumed_profile_session
from .profile_summary import ProfileSummaryInventory, summary_inventory


class WorkbenchBootstrapInventoryState(StrEnum):
    """Truthful result of the non-authenticating profile inventory read."""

    RECOGNIZED = "recognized"
    CONCURRENT_CHANGE = "concurrent_change"
    DEGRADED = "degraded"
    EMPTY = "empty"


class WorkbenchBootstrapSessionState(StrEnum):
    """Authentication state following a recognized non-empty inventory."""

    RESUMED = "resumed"
    LOGIN_REQUIRED = "login_required"
    CANCELLED = "cancelled"
    AUTHENTICATED = "authenticated"


@dataclass(frozen=True, slots=True)
class WorkbenchRegistrationRequiredV1:
    """Typed zero-profile handoff; registration remains owned by its existing flow."""

    reason_code: str = "workbench.bootstrap.registration_required"


@dataclass(frozen=True, slots=True)
class WorkbenchBootstrapV1:
    """One immutable bootstrap observation without credentials or custody material."""

    inventory_state: WorkbenchBootstrapInventoryState
    session_state: WorkbenchBootstrapSessionState | None = None
    choices: tuple[ProfileLoginChoice, ...] = field(default=(), repr=False)
    preselected_profile_id: str | None = field(default=None, repr=False)
    selected_profile_id: str | None = field(default=None, repr=False)
    selected_profile_label: str | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        """Refuse contradictory inventory, selection, and session combinations."""
        choice_ids = tuple(choice.profile_id for choice in self.choices)
        _validate_bootstrap_choice_ids(choice_ids)
        _validate_bootstrap_inventory_payload(
            inventory_state=self.inventory_state,
            choices=self.choices,
            session_state=self.session_state,
            preselected_profile_id=self.preselected_profile_id,
            reason_code=self.reason_code,
        )
        _validate_bootstrap_reason(self.inventory_state, self.reason_code)
        _validate_bootstrap_preselection(self.preselected_profile_id, choice_ids)
        _validate_bootstrap_selection(
            session_state=self.session_state,
            selected_profile_id=self.selected_profile_id,
            selected_profile_label=self.selected_profile_label,
            choice_ids=choice_ids,
        )

    @property
    def registration_required(self) -> WorkbenchRegistrationRequiredV1 | None:
        """Return the explicit zero-profile handoff, never a fabricated login choice."""
        if self.inventory_state is WorkbenchBootstrapInventoryState.EMPTY:
            return WorkbenchRegistrationRequiredV1()
        return None


type ProfileInventoryReaderV1 = Callable[[], ProfileSummaryInventory]
type ProfileChoiceReaderV1 = Callable[[], tuple[ProfileLoginChoice, ...]]
type ProfilePreselectionReaderV1 = Callable[[str | None], str | None]


class ProfileSessionResumeDoorV1(Protocol):
    """Keyword-only boundary for attempting a persisted-session resume."""

    def __call__(self, *, bucket_id: str) -> object | None:
        """Return ``None`` only when the persisted session resumes."""
        ...


def prepare_workbench_bootstrap(
    *,
    inventory_reader: ProfileInventoryReaderV1 = summary_inventory,
    choice_reader: ProfileChoiceReaderV1 = profile_login_choices,
    preselection_reader: ProfilePreselectionReaderV1 = preselected_profile_login_id,
    resume_session: ProfileSessionResumeDoorV1 = bind_resumed_profile_session,
) -> WorkbenchBootstrapV1:
    """Inspect profile availability and resume only the exact recognized selection."""
    inventory = inventory_reader()
    inventory_state = _unavailable_bootstrap_for_inventory(inventory)
    if inventory_state is not None:
        return inventory_state

    choices = choice_reader()
    if not _choices_match_inventory(inventory, choices):
        return WorkbenchBootstrapV1(
            inventory_state=WorkbenchBootstrapInventoryState.DEGRADED,
            reason_code="workbench.bootstrap.profile_inventory_changed",
        )
    preselected = _valid_preselection(preselection_reader(None), choices)
    if preselected is not None and resume_session(bucket_id=preselected) is None:
        return _resumed_bootstrap(choices, preselected)
    return _login_required_bootstrap(choices, preselected)


def _validate_bootstrap_choice_ids(choice_ids: tuple[str, ...]) -> None:
    """Require each recognized profile choice to identify one profile once."""
    if len(choice_ids) != len(set(choice_ids)):
        raise ValueError("workbench bootstrap profile choices must be unique")


def _validate_bootstrap_inventory_payload(
    *,
    inventory_state: WorkbenchBootstrapInventoryState,
    choices: tuple[ProfileLoginChoice, ...],
    session_state: WorkbenchBootstrapSessionState | None,
    preselected_profile_id: str | None,
    reason_code: str | None,
) -> None:
    """Validate the fields allowed by each inventory state."""
    if inventory_state is WorkbenchBootstrapInventoryState.RECOGNIZED:
        if not choices or session_state is None or reason_code is not None:
            raise ValueError("recognized workbench bootstrap requires choices and a session state")
    elif choices or session_state is not None or preselected_profile_id is not None:
        raise ValueError("empty, concurrent, or degraded workbench bootstrap cannot carry login choices")


def _validate_bootstrap_reason(
    inventory_state: WorkbenchBootstrapInventoryState,
    reason_code: str | None,
) -> None:
    """Validate reason-code requirements for unavailable and empty inventory."""
    if (
        inventory_state
        in {
            WorkbenchBootstrapInventoryState.CONCURRENT_CHANGE,
            WorkbenchBootstrapInventoryState.DEGRADED,
        }
        and reason_code is None
    ):
        raise ValueError("unavailable workbench bootstrap requires a safe reason code")
    if inventory_state is WorkbenchBootstrapInventoryState.EMPTY and reason_code is not None:
        raise ValueError("empty workbench bootstrap is not a degraded inventory")


def _validate_bootstrap_preselection(preselected_profile_id: str | None, choice_ids: tuple[str, ...]) -> None:
    """Require a preselected profile to belong to the recognized choices."""
    if preselected_profile_id is not None and preselected_profile_id not in choice_ids:
        raise ValueError("workbench bootstrap preselection is absent from its profile choices")


def _validate_bootstrap_selection(
    *,
    session_state: WorkbenchBootstrapSessionState | None,
    selected_profile_id: str | None,
    selected_profile_label: str | None,
    choice_ids: tuple[str, ...],
) -> None:
    """Require selected identity fields exactly when the session is authenticated."""
    authenticated = session_state in {
        WorkbenchBootstrapSessionState.RESUMED,
        WorkbenchBootstrapSessionState.AUTHENTICATED,
    }
    if authenticated != (selected_profile_id is not None and selected_profile_label is not None):
        raise ValueError("only an authenticated workbench bootstrap carries a selected profile")
    if selected_profile_id is not None and selected_profile_id not in choice_ids:
        raise ValueError("authenticated workbench profile is absent from its recognized inventory")


def _unavailable_bootstrap_for_inventory(inventory: ProfileSummaryInventory) -> WorkbenchBootstrapV1 | None:
    """Return a terminal bootstrap state for an unrecognized inventory."""
    if inventory.outcome is ProfileSummaryOutcome.CONCURRENT_CHANGE:
        return WorkbenchBootstrapV1(
            inventory_state=WorkbenchBootstrapInventoryState.CONCURRENT_CHANGE,
            reason_code="workbench.bootstrap.profile_inventory_concurrent_change",
        )
    if not inventory.recognized:
        return WorkbenchBootstrapV1(
            inventory_state=WorkbenchBootstrapInventoryState.DEGRADED,
            reason_code="workbench.bootstrap.profile_inventory_unavailable",
        )
    if not inventory.summaries:
        return WorkbenchBootstrapV1(inventory_state=WorkbenchBootstrapInventoryState.EMPTY)
    return None


def _choices_match_inventory(
    inventory: ProfileSummaryInventory,
    choices: tuple[ProfileLoginChoice, ...],
) -> bool:
    """Return whether login choices still describe the same inventory."""
    expected = tuple((str(item.profile_id), str(item.label)) for item in inventory.summaries)
    observed = tuple((choice.profile_id, choice.label) for choice in choices)
    return len(expected) == len(observed) and dict(expected) == dict(observed)


def _valid_preselection(
    preselected_profile_id: str | None,
    choices: tuple[ProfileLoginChoice, ...],
) -> str | None:
    """Keep only preselection values present in the recognized choices."""
    if preselected_profile_id not in {choice.profile_id for choice in choices}:
        return None
    return preselected_profile_id


def _resumed_bootstrap(
    choices: tuple[ProfileLoginChoice, ...],
    preselected_profile_id: str,
) -> WorkbenchBootstrapV1:
    """Build the selected state after a persisted session resumed successfully."""
    selected = next(choice for choice in choices if choice.profile_id == preselected_profile_id)
    return WorkbenchBootstrapV1(
        inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
        session_state=WorkbenchBootstrapSessionState.RESUMED,
        choices=choices,
        preselected_profile_id=preselected_profile_id,
        selected_profile_id=selected.profile_id,
        selected_profile_label=selected.label,
    )


def _login_required_bootstrap(
    choices: tuple[ProfileLoginChoice, ...],
    preselected_profile_id: str | None,
) -> WorkbenchBootstrapV1:
    """Build the recognized state that still needs interactive authentication."""
    return WorkbenchBootstrapV1(
        inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
        session_state=WorkbenchBootstrapSessionState.LOGIN_REQUIRED,
        choices=choices,
        preselected_profile_id=preselected_profile_id,
    )


def complete_workbench_login(
    preparation: WorkbenchBootstrapV1,
    outcome: ProfileLoginOutcome | None,
) -> WorkbenchBootstrapV1:
    """Convert the existing Login screen result into a closed bootstrap state."""
    if preparation.session_state is not WorkbenchBootstrapSessionState.LOGIN_REQUIRED:
        raise ValueError("only a login-required bootstrap can accept a login result")
    if outcome is None:
        return WorkbenchBootstrapV1(
            inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
            session_state=WorkbenchBootstrapSessionState.CANCELLED,
            choices=preparation.choices,
            preselected_profile_id=preparation.preselected_profile_id,
        )
    choice_by_profile_id = {choice.profile_id: choice for choice in preparation.choices}
    choice = choice_by_profile_id.get(outcome.bucket_id)
    if choice is None:
        raise ValueError("authenticated profile is absent from the recognized bootstrap inventory")
    if outcome.label != choice.label:
        raise ValueError("authenticated profile label disagrees with the recognized bootstrap inventory")
    return WorkbenchBootstrapV1(
        inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
        session_state=WorkbenchBootstrapSessionState.AUTHENTICATED,
        choices=preparation.choices,
        preselected_profile_id=preparation.preselected_profile_id,
        selected_profile_id=outcome.bucket_id,
        selected_profile_label=choice.label,
    )


__all__ = [
    "ProfileChoiceReaderV1",
    "ProfileInventoryReaderV1",
    "ProfilePreselectionReaderV1",
    "ProfileSessionResumeDoorV1",
    "WorkbenchBootstrapInventoryState",
    "WorkbenchBootstrapSessionState",
    "WorkbenchBootstrapV1",
    "WorkbenchRegistrationRequiredV1",
    "complete_workbench_login",
    "prepare_workbench_bootstrap",
]
