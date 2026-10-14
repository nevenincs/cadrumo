"""An unset provider gets an environment credential only in development mode."""

from __future__ import annotations

import pytest

from ....core.storage_environment import StorageMode
from ...provider_settings.contracts import ProviderCredentialSource
from ...provider_settings.tests.synthetic_catalog import (
    BARE_GATEWAY_LANE,
    DEFAULTED_KEY_LANE,
    GATEWAY_DEFAULT_URL,
    GATEWAY_LANE,
    KEY_LANE,
    MISSING_LANE,
    OTHER_KEY_LANE,
    SIGN_IN_ONLY_LANE,
    StaticCatalogSource,
    UnavailableCatalogSource,
    development_variable,
)
from ..development_fallback import development_fallback

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("storage_mode", [StorageMode.DEVELOPMENT, StorageMode.INSTALLED])
def test_unset_provider_environment_fallback_respects_storage_mode(storage_mode: StorageMode) -> None:
    environment = {development_variable(KEY_LANE): "synthetic-development-key"}

    credential = development_fallback(
        KEY_LANE, catalog_source=StaticCatalogSource(), environment=environment, storage_mode=storage_mode
    )

    if storage_mode is StorageMode.INSTALLED:
        assert credential is None
    else:
        assert credential is not None
        assert credential.source is ProviderCredentialSource.ENVIRONMENT
        assert credential.secret.get_secret_value() == "synthetic-development-key"


def test_the_variable_name_is_constructed_from_the_provider_id() -> None:
    environment = {development_variable(GATEWAY_LANE): "synthetic-gateway-key"}

    credential = development_fallback(
        GATEWAY_LANE,
        catalog_source=StaticCatalogSource(),
        environment=environment,
        storage_mode=StorageMode.DEVELOPMENT,
    )

    assert development_variable(GATEWAY_LANE) == "CADRUMO_LLM_GATEWAY_API_KEY"
    assert credential is not None
    assert credential.secret.get_secret_value() == "synthetic-gateway-key"
    assert credential.base_url == GATEWAY_DEFAULT_URL


def test_an_api_key_lane_takes_the_agents_declared_default_endpoint() -> None:
    environment = {development_variable(DEFAULTED_KEY_LANE): "synthetic-key"}

    credential = development_fallback(
        DEFAULTED_KEY_LANE,
        catalog_source=StaticCatalogSource(),
        environment=environment,
        storage_mode=StorageMode.DEVELOPMENT,
    )

    assert credential is not None
    assert credential.base_url == "https://defaulted.example.invalid"


@pytest.mark.parametrize("lane", [OTHER_KEY_LANE, SIGN_IN_ONLY_LANE, BARE_GATEWAY_LANE, MISSING_LANE])
def test_unset_provider_without_a_usable_development_key_is_unavailable(lane: str) -> None:
    # The sign-in-only lane shares its provider's variable with the key lane; the lane that takes no credential
    # still resolves nothing, and a gateway with no default endpoint has nowhere to send the key.
    environment = {
        development_variable(SIGN_IN_ONLY_LANE): "synthetic-key",
        development_variable(BARE_GATEWAY_LANE): "synthetic-key",
    }

    assert (
        development_fallback(
            lane, catalog_source=StaticCatalogSource(), environment=environment, storage_mode=StorageMode.DEVELOPMENT
        )
        is None
    )


def test_an_agent_that_cannot_report_its_providers_supplies_no_fallback() -> None:
    environment = {development_variable(KEY_LANE): "synthetic-development-key"}

    assert (
        development_fallback(
            KEY_LANE,
            catalog_source=UnavailableCatalogSource(),
            environment=environment,
            storage_mode=StorageMode.DEVELOPMENT,
        )
        is None
    )
