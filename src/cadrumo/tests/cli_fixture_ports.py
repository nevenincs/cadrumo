"""Shared invocation options for repository CLI test runners."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, Protocol, TypedDict

from click.testing import Result


class ClickInvokeKwargs(TypedDict, total=False):
    """Exact Click invocation options supported by the shared CLI test runners."""

    env: NotRequired[Mapping[str, str | None] | None]
    color: NotRequired[bool]
    catch_exceptions: NotRequired[bool]
    input: NotRequired[str | bytes | None]
    obj: NotRequired[object]


type CliInvocation = Callable[..., Result]


@dataclass(frozen=True)
class FreshCliResult:
    """Captured command output and independently persisted import observations."""

    completed: subprocess.CompletedProcess[str]
    loaded_modules: tuple[str, ...]


class FreshCliInvocation(Protocol):
    """Run the composed console entry point in a fresh interpreter."""

    def __call__(
        self,
        args: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        env_strip_prefixes: Sequence[str] = ("AEAT_", "PYTEST_"),
        extra_env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        program_name: str | None = None,
        watched_modules: Sequence[str] = (),
        import_report: Path | None = None,
        site_dir: Path | None = None,
    ) -> FreshCliResult:
        """Use exact env when supplied, otherwise filter the inherited environment."""
        ...
