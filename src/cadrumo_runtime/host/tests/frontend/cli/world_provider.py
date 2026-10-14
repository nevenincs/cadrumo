"""Runtime-owned providers for tax CLI scenario fixture ports."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_sessionless_storage_root
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.entrypoints.cli.tests.cli_fixture_worlds import ApiProbeSession, BackendKind, HumanProbeSession
from cadrumo.tests.cli_fixture_ports import CliInvocation

from ._cli_surface_support import _active_bucket_id, create_cli_surface_profile, isolated_cli_surface_backend
from ._ledger_validation_support import _set_profile_axis, open_bucket_session
from .runtime_profile_backend import (
    copied_runtime_profile_backend,
    runtime_profile_backend,
    seeded_runtime_profile_origin,
)


class RuntimeCliWorldProvider:
    """Supply existing custody-backed worlds without changing their implementation."""

    @contextmanager
    def human_probe(
        self, tmp_path: Path, *, client_native_store: AutomationSecretStore | None = None
    ) -> Generator[HumanProbeSession]:
        from ._command_drive_support import seeded_probe_runtime

        with seeded_probe_runtime(tmp_path, client_native_store=client_native_store) as runtime:
            yield runtime

    @contextmanager
    def api_probe(self, tmp_path: Path) -> Generator[ApiProbeSession]:
        from .portable_api_cli_runtime import portable_api_cli_runtime

        with portable_api_cli_runtime(tmp_path) as runtime:
            yield runtime

    @contextmanager
    def backend(self, kind: BackendKind, tmp_path: Path) -> Generator[None]:
        if kind == "surface":
            with isolated_cli_surface_backend(tmp_path):
                yield
        elif kind == "validation":
            with open_bucket_session(tmp_path):
                yield
        elif kind == "sessionless":
            with isolated_sessionless_storage_root(tmp_path=tmp_path):
                yield
        else:
            settings = {"cadrumo_output_language": "en"} if kind == "recorded_fx" else None
            with runtime_profile_backend(tmp_path, settings_overrides=settings):
                yield

    @contextmanager
    def seeded_origin(
        self,
        *,
        seed: Callable[..., object],
        tmp_path_factory: pytest.TempPathFactory,
        invoke_cli: CliInvocation,
        name: str,
        origin_name: str,
    ) -> Generator[Path]:
        with seeded_runtime_profile_origin(
            seed=seed,
            tmp_path_factory=tmp_path_factory,
            invoke_cli=invoke_cli,
            settings_overrides={"cadrumo_output_language": "en"},
        ) as origin:
            yield origin

    @contextmanager
    def seeded_copy(
        self,
        *,
        seed: Callable[..., object],
        request: pytest.FixtureRequest,
        tmp_path: Path,
        name: str,
        origin_name: str,
    ) -> Generator[None]:
        origin = request.getfixturevalue(origin_name)
        assert isinstance(origin, Path)
        with copied_runtime_profile_backend(origin, tmp_path, settings_overrides={"cadrumo_output_language": "en"}):
            yield

    def create_surface_profile(self, label: str = "operator", *, log_in: bool = True) -> None:
        create_cli_surface_profile(label, log_in=log_in)

    def active_bucket_id(self) -> str:
        return _active_bucket_id()

    def set_profile_axis(self, key: str, value: str) -> None:
        _set_profile_axis(key, value)
