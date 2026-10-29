"""Typed run state and concurrent actor outcomes for session lifecycle probes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from .caller_owned_root import Programs
from .proof_support import Profile
from .session_holder import AsyncRuntimeSessionHolder


@dataclass(slots=True)
class Run:
    """The recorded checks of one run, printed as they happen."""

    checks: list[dict[str, Any]] = field(default_factory=list)

    def check(self, name: str, ok: bool, **facts: Any) -> bool:
        """Record one expectation and its observed facts."""
        entry = {"check": name, "ok": ok, **facts}
        self.checks.append(entry)
        print(json.dumps(entry, sort_keys=True, default=str), flush=True)
        return ok

    @property
    def failed(self) -> list[str]:
        """Name every check that did not hold."""
        return [entry["check"] for entry in self.checks if not entry["ok"]]


@dataclass(slots=True)
class Context:
    """The programs, environment and profiles one run drives."""

    programs: Programs
    environment: dict[str, str]
    python: list[str]
    scratch: Path
    profiles: dict[str, Profile] = field(default_factory=dict)


@dataclass(slots=True)
class Held:
    """One running session holder and the profile it signed in to."""

    name: str
    profile: str
    holder: AsyncRuntimeSessionHolder


def describe(error: BaseException) -> str:
    """Render nested failures without their operands."""
    if isinstance(error, BaseExceptionGroup):
        group = cast(BaseExceptionGroup[BaseException], error)
        return "; ".join(describe(inner) for inner in group.exceptions)
    return f"{type(error).__name__}: {error}"


async def gather_actor_outcomes(actors: Mapping[str, Awaitable[Any]]) -> dict[str, Any]:
    """Start every actor at once and return each one's result or failure."""
    results = await asyncio.gather(*actors.values(), return_exceptions=True)
    return dict(zip(actors, results, strict=True))
