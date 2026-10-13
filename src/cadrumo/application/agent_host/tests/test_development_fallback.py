"""An unset provider gets an environment credential only in development mode."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from ....core.config import Settings
from ....core.storage_environment import StorageMode
from ...provider_settings.contracts import ProviderCredentialSource
from ..development_fallback import development_fallback

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("storage_mode", [StorageMode.DEVELOPMENT, StorageMode.INSTALLED])
def test_unset_provider_environment_fallback_respects_storage_mode(storage_mode: StorageMode) -> None:
    settings = Settings(cadrumo_llm_claude_api_key=SecretStr("synthetic-development-key"))

    credential = development_fallback("claude_api", settings=settings, storage_mode=storage_mode)

    if storage_mode is StorageMode.INSTALLED:
        assert credential is None
    else:
        assert credential is not None
        assert credential.source is ProviderCredentialSource.ENVIRONMENT
        assert credential.secret.get_secret_value() == "synthetic-development-key"


def test_unset_provider_without_a_development_key_is_unavailable() -> None:
    settings = Settings(cadrumo_llm_claude_api_key=None)

    assert development_fallback("claude_api", settings=settings, storage_mode=StorageMode.DEVELOPMENT) is None
