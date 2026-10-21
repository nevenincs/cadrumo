"""Tax CLI fixture declarations with repository-provided typed ports."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....core.config import reset_settings_cache
from ....core.external_constants import OUTPUT_LANGUAGE_ENV_VAR
from ....core.i18n.render import clear_output_language_cache
from ....tests.cli_fixture_ports import CliInvocation
from ....tests.env import temporary_env
from .cli_fixture_worlds import CliWorldProvider, bind_cli_fixture_ports


@pytest.fixture(autouse=True)
def _injected_cli_ports(
    cli_runtime_lifetime: None, cli_world_provider: CliWorldProvider, invoke_cli: CliInvocation
) -> Iterator[None]:
    """Bind injected ports without importing a runtime provider."""
    with bind_cli_fixture_ports(cli_world_provider, invoke_cli):
        yield


@pytest.fixture(autouse=True)
def force_english_output() -> Iterator[None]:
    """Retain original CLI language and pointer-cache isolation."""
    with temporary_env(**{OUTPUT_LANGUAGE_ENV_VAR: "en"}):
        reset_settings_cache()
        clear_output_language_cache()
        try:
            yield
        finally:
            reset_settings_cache()
            clear_output_language_cache()
