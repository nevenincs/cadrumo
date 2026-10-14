"""Runtime-host frontend CLI fixture composition."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Unpack

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.tests.published_authority_support import release_published_authority_operation
from cadrumo.core.config import reset_settings_cache
from cadrumo.core.external_constants import OUTPUT_LANGUAGE_ENV_VAR
from cadrumo.core.i18n.render import clear_output_language_cache
from cadrumo.tests.cli_fixture_ports import ClickInvokeKwargs
from cadrumo.tests.env import temporary_env
from cadrumo_runtime.commands.tests.runtime_profile_cli_fixture import NativeCliProfileFixture

from .cli_runner import bind_public_cli_runner, invoke_cached_cli, operator_runtime_scope


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> object:
    """Own any runtime joined by test fixtures until the test body begins."""
    del item
    with operator_runtime_scope():
        return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> object:
    """Retire joined runtimes before test fixtures unwind."""
    del item
    with operator_runtime_scope():
        return (yield)


@pytest.fixture(autouse=True)
def _bind_public_aeat_runner(run_cadrumo_cli: Callable[..., Result]) -> Iterator[None]:
    """Inject the repository-root public AEAT runner into runtime test support."""
    with bind_public_cli_runner(run_cadrumo_cli):
        yield


@pytest.fixture(scope="session", autouse=True)
def _published_authority_lease() -> Iterator[None]:
    """Release the per-worker published authority lease that seeded CLI fixtures take."""
    yield
    release_published_authority_operation()


@pytest.fixture
def open_bucket_cli_backend(tmp_path: Path) -> Iterator[None]:
    """Open the dedicated ledger UX bucket lifecycle for one requesting test."""
    from .ledger_ux_support import open_ledger_ux_session

    with open_ledger_ux_session(tmp_path):
        yield


@pytest.fixture(autouse=True)
def force_english_output() -> Iterator[None]:
    """Pin CLI output to English and invalidate pointer-keyed settings around the test."""
    with temporary_env(**{OUTPUT_LANGUAGE_ENV_VAR: "en"}):
        reset_settings_cache()
        clear_output_language_cache()
        try:
            yield
        finally:
            reset_settings_cache()
            clear_output_language_cache()


@pytest.fixture(autouse=True)
def isolated_cadrumo_root(tmp_path: Path) -> Iterator[None]:
    """Point Settings.cadrumo_local_storage_root at the test's temporary root."""
    with temporary_env(CADRUMO_LOCAL_STORAGE_ROOT=str(tmp_path)):
        yield


@pytest.fixture
def native_overview_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    """Register a readiness-complete synthetic profile before worker login."""
    from ._overview_native_support import registered_overview_profile

    with registered_overview_profile(tmp_path) as fixture:
        yield fixture


@pytest.fixture(scope="session")
def invoke_cli(run_cadrumo_cli: Callable[..., Result]) -> Callable[..., Result]:
    """Invoke through the exact operator bound by the current test world."""

    def invoke(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
        with bind_public_cli_runner(run_cadrumo_cli):
            return invoke_cached_cli(args, **kwargs)

    return invoke
