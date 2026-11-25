"""Shared typed evidence for package environment conformance."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .environment_models import ApplicationEnvironment


@dataclass(frozen=True)
class Finding:
    """One disagreement between the package's declaration and an installed component."""

    check: str
    subject: str
    message: str

    def render(self) -> str:
        """Spell the finding on one line."""
        return f"[{self.check}] {self.subject}: {self.message}"


@dataclass(frozen=True)
class Reference:
    """The package's declaration, resolved for one build target: the side every comparison trusts."""

    declaration: ApplicationEnvironment
    section: Mapping[str, Any]
    layout: Mapping[str, Any]
    agent: Mapping[str, Any]
    family: str

    @property
    def windows(self) -> bool:
        """Whether the target's environment names compare without case."""
        return self.family == "windows"
