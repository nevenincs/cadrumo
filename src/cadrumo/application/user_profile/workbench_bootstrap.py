"""Truthful profile-selection and authentication state for the installed workbench."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

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
        if len(choice_ids) != len(set(choice_ids)):
            raise ValueError("workbench bootstrap profile choices must be unique")
        if self.inventory_state is WorkbenchBootstrapInventoryState.RECOGNIZED:
            if not self.choices or self.session_state is None or self.reason_code is not None:
                raise ValueError("recognized workbench bootstrap requires choices and a session state")
        elif self.choices or self.session_state is not None or self.preselected_profile_id is not None:
            raise ValueError("empty or degraded workbench bootstrap cannot carry login choices")
        if self.inventory_state is WorkbenchBootstrapInventoryState.DEGRADED and self.reason_code is None:
            raise ValueError("degraded workbench bootstrap requires a safe reason code")
        if self.inventory_state is WorkbenchBootstrapInventoryState.EMPTY and self.reason_code is not None:
            raise ValueError("empty workbench bootstrap is not a degraded inventory")
        if self.preselected_profile_id is not None and self.preselected_profile_id not in choice_ids:
            raise ValueError("workbench bootstrap preselection is absent from its profile choices")
        selected = self.selected_profile_id
        authenticated = self.session_state in {
            WorkbenchBootstrapSessionState.RESUMED,
            WorkbenchBootstrapSessionState.AUTHENTICATED,
        }
        if authenticated != (selected is not None and self.selected_profile_label is not None):
            raise ValueError("only an authenticated workbench bootstrap carries a selected profile")
        if selected is not None and selected not in choice_ids:
            raise ValueError("authenticated workbench profile is absent from its recognized inventory")

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
    if not inventory.recognized:
        return WorkbenchBootstrapV1(
            inventory_state=WorkbenchBootstrapInventoryState.DEGRADED,
            reason_code="workbench.bootstrap.profile_inventory_unavailable",
        )
    if not inventory.summaries:
        return WorkbenchBootstrapV1(inventory_state=WorkbenchBootstrapInventoryState.EMPTY)

    choices = choice_reader()
    expected = tuple((str(item.profile_id), str(item.label)) for item in inventory.summaries)
    observed = tuple((choice.profile_id, choice.label) for choice in choices)
    if len(expected) != len(observed) or dict(expected) != dict(observed):
        return WorkbenchBootstrapV1(
            inventory_state=WorkbenchBootstrapInventoryState.DEGRADED,
            reason_code="workbench.bootstrap.profile_inventory_changed",
        )
    preselected = preselection_reader(None)
    if preselected not in {choice.profile_id for choice in choices}:
        preselected = None
    if preselected is not None and resume_session(bucket_id=preselected) is None:
        selected = next(choice for choice in choices if choice.profile_id == preselected)
        return WorkbenchBootstrapV1(
            inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
            session_state=WorkbenchBootstrapSessionState.RESUMED,
            choices=choices,
            preselected_profile_id=preselected,
            selected_profile_id=selected.profile_id,
            selected_profile_label=selected.label,
        )
    return WorkbenchBootstrapV1(
        inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
        session_state=WorkbenchBootstrapSessionState.LOGIN_REQUIRED,
        choices=choices,
        preselected_profile_id=preselected,
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
    if outcome.bucket_id not in {choice.profile_id for choice in preparation.choices}:
        raise ValueError("authenticated profile is absent from the recognized bootstrap inventory")
    return WorkbenchBootstrapV1(
        inventory_state=WorkbenchBootstrapInventoryState.RECOGNIZED,
        session_state=WorkbenchBootstrapSessionState.AUTHENTICATED,
        choices=preparation.choices,
        preselected_profile_id=preparation.preselected_profile_id,
        selected_profile_id=outcome.bucket_id,
        selected_profile_label=outcome.label,
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
