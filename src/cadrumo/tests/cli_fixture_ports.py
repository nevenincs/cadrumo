"""Shared invocation options for repository CLI test runners."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import NotRequired, TypedDict

from click.testing import Result


class ClickInvokeKwargs(TypedDict, total=False):
    """Exact Click invocation options supported by the shared CLI test runners."""

    env: NotRequired[Mapping[str, str | None] | None]
    color: NotRequired[bool]
    catch_exceptions: NotRequired[bool]
    input: NotRequired[str | bytes | None]
    obj: NotRequired[object]


type CliInvocation = Callable[..., Result]
