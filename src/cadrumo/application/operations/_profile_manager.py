"""Frontend-neutral contracts for profile-manager actions."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core import OperatorProgress

if TYPE_CHECKING:
    from ..user_profile import ProfileOverview

type ManagerProgressSinkBinder = Callable[[Callable[[OperatorProgress], None]], AbstractContextManager[None]]


class ManagerActionDisposition(StrEnum):
    """How a completed manager action should be presented."""

    SUCCESS = "success"
    WARNING = "warning"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class ManagerActionOutcome:
    """Result of one frontend-neutral profile-manager action."""

    message: str
    overview: ProfileOverview | None = None
    close_session: bool = False
    disposition: ManagerActionDisposition = ManagerActionDisposition.SUCCESS


@dataclass(frozen=True, slots=True)
class ManagerAction:
    """One profile-manager action supplied to a presentation surface."""

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
