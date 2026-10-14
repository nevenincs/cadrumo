"""Application-owned ports for CLI test worlds and admitted invocation."""

from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Literal, Protocol, Unpack
from uuid import UUID

import pytest
from click.testing import Result

from ....application.user_profile.automation_custody_port import AutomationSecretStore
from ....application.user_profile.automation_enrollment import EnrollmentProposal
from ....tests.cli_fixture_ports import ClickInvokeKwargs, CliInvocation

type BackendKind = Literal["active", "recorded_fx", "inventory", "surface", "validation", "sessionless"]


class HumanProbeSession(Protocol):
    """Admitted profile command interface for declaration assertions."""

    @property
    def profile_id(self) -> UUID: ...

    def invoke(self, args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result: ...


class ApiProbeSession(HumanProbeSession, Protocol):
    """Own-grant API inputs, interpreted by the tax assertion owner."""

    @property
    def grant_id(self) -> UUID: ...

    @property
    def key_id(self) -> UUID: ...

    @property
    def proposal(self) -> EnrollmentProposal: ...


class CliWorldProvider(Protocol):
    """Own runtime setup and custody behind fixture lifetime ports."""

    def human_probe(
        self, tmp_path: Path, *, client_native_store: AutomationSecretStore | None = None
    ) -> AbstractContextManager[HumanProbeSession]: ...
    def api_probe(self, tmp_path: Path) -> AbstractContextManager[ApiProbeSession]: ...
    def backend(self, kind: BackendKind, tmp_path: Path) -> AbstractContextManager[None]: ...
    def seeded_origin(
        self,
        *,
        seed: Callable[..., object],
        tmp_path_factory: pytest.TempPathFactory,
        invoke_cli: CliInvocation,
        name: str,
        origin_name: str,
    ) -> AbstractContextManager[Path]: ...
    def seeded_copy(
        self,
        *,
        seed: Callable[..., object],
        request: pytest.FixtureRequest,
        tmp_path: Path,
        name: str,
        origin_name: str,
    ) -> AbstractContextManager[None]: ...
    def create_surface_profile(self, label: str = "operator", *, log_in: bool = True) -> None: ...
    def active_bucket_id(self) -> str: ...
    def set_profile_axis(self, key: str, value: str) -> None: ...


_PROVIDER: ContextVar[CliWorldProvider | None] = ContextVar("cli-fixture-world-provider", default=None)
_INVOKE: ContextVar[CliInvocation | None] = ContextVar("cli-fixture-joined-invocation", default=None)


@contextmanager
def bind_cli_fixture_ports(provider: CliWorldProvider, invoke: CliInvocation) -> Generator[None]:
    """Retain the injected world and invocation ports for one fixture lifetime."""
    provider_token = _PROVIDER.set(provider)
    invoke_token = _INVOKE.set(invoke)
    try:
        yield
    finally:
        _INVOKE.reset(invoke_token)
        _PROVIDER.reset(provider_token)


def cli_world_provider() -> CliWorldProvider:
    """Read the explicit repository-provided world port."""
    provider = _PROVIDER.get()
    if provider is None:
        raise RuntimeError("CLI scenario requires the injected cli_world_provider fixture")
    return provider


def invoke_joined_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the CLI through its injected admitted-operator callback."""
    invoke = _INVOKE.get()
    if invoke is None:
        raise RuntimeError("CLI scenario requires the injected invoke_cli fixture")
    return invoke(args, **kwargs)
