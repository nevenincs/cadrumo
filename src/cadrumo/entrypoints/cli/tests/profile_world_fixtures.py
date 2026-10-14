"""Tax-owned fixture declarations consuming repository-provided runtime worlds."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ....tests.cli_fixture_ports import CliInvocation
from .cli_fixture_worlds import BackendKind, CliWorldProvider


def profile_backend_fixture(kind: BackendKind):
    """Declare the original per-test world lifetime and automatic use."""

    @pytest.fixture(name="_isolated_backend", autouse=True)
    def backend(tmp_path: Path, cli_world_provider: CliWorldProvider) -> Iterator[None]:
        with cli_world_provider.backend(kind, tmp_path):
            yield

    return backend


active_profile_isolated_backend = profile_backend_fixture("active")
recorded_fx_isolated_backend = profile_backend_fixture("recorded_fx")
inventory_isolated_backend = profile_backend_fixture("inventory")
cli_surface_isolated_backend = profile_backend_fixture("surface")


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path, cli_world_provider: CliWorldProvider) -> Iterator[None]:
    with cli_world_provider.backend("sessionless", tmp_path):
        yield


def recorded_fx_seeded_backend(
    *,
    seed: Callable[..., object],
    autouse: bool = True,
    name: str = "_isolated_backend",
    origin_name: str = "_isolated_backend_origin",
):
    """Declare one module seed and one independently signed-in copy per test."""

    @pytest.fixture(name=origin_name, scope="module")
    def origin(
        tmp_path_factory: pytest.TempPathFactory, invoke_cli: CliInvocation, cli_world_provider: CliWorldProvider
    ) -> Iterator[Path]:
        with cli_world_provider.seeded_origin(
            seed=seed, tmp_path_factory=tmp_path_factory, invoke_cli=invoke_cli, name=name, origin_name=origin_name
        ) as root:
            yield root

    @pytest.fixture(name=name, autouse=autouse)
    def copy(request: pytest.FixtureRequest, tmp_path: Path, cli_world_provider: CliWorldProvider) -> Iterator[None]:
        with cli_world_provider.seeded_copy(
            seed=seed, request=request, tmp_path=tmp_path, name=name, origin_name=origin_name
        ):
            yield

    return origin, copy
