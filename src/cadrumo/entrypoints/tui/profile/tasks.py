"""Presentation contracts for work offered from the profile overview.

The entrypoint supplies each task's callable and owns its effects.  This
module carries only the screen-facing projection of that task and its settled
outcome, so the overview never learns profile, authentication, export, or
operation policy.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ....core import OperatorProgress

if TYPE_CHECKING:
    from ....application.user_profile import ProfileOverview


type ManagerProgressSinkBinder = Callable[[Callable[[OperatorProgress], None]], AbstractContextManager[None]]


class ManagerActionDisposition(StrEnum):
    """How a completed task should be presented to the operator."""

    SUCCESS = "success"
    WARNING = "warning"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class ManagerActionOutcome:
    """What an injected task did, as the overview needs to know it."""

    message: str
    overview: ProfileOverview | None = None
    close_session: bool = False
    disposition: ManagerActionDisposition = ManagerActionDisposition.SUCCESS


@dataclass(frozen=True, slots=True)
class ManagerAction:
    """One injected task offered alongside the profile fields."""

    key: str
    label: str
    run: Callable[[], ManagerActionOutcome]
    label_key: str | None = None
    owns_paths: tuple[str, ...] = ()
    progress_sink: ManagerProgressSinkBinder | None = None


__all__ = [
    "ManagerAction",
    "ManagerActionDisposition",
    "ManagerActionOutcome",
    "ManagerProgressSinkBinder",
]
