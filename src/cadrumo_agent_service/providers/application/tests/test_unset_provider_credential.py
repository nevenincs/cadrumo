"""An unset provider has no credential; no process environment value stands in for a stored key."""

from __future__ import annotations

import pytest

from ...domain.catalog import ProviderConsumer
from ..resolution import (
    ProviderCredentialResolver,
    ProviderCredentialUnavailable,
    ProviderCredentialUnavailableReason,
)
from .memory_store import MemoryProviderSettingsStore
from .synthetic_catalog import (
    BARE_GATEWAY_LANE,
    DEFAULTED_KEY_LANE,
    GATEWAY_LANE,
    KEY_LANE,
    MISSING_LANE,
    OTHER_KEY_LANE,
    StaticCatalogSource,
    UnavailableCatalogSource,
    synthetic_catalog,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LANES_TAKING_A_KEY = [KEY_LANE, GATEWAY_LANE, DEFAULTED_KEY_LANE, OTHER_KEY_LANE, BARE_GATEWAY_LANE]


@pytest.mark.parametrize("lane", _LANES_TAKING_A_KEY)
def test_an_unset_key_lane_is_unavailable_even_when_the_environment_names_a_key(
    lane: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for entry in synthetic_catalog().providers:
        monkeypatch.setenv(f"CADRUMO_LLM_{entry.provider.upper()}_API_KEY", "synthetic-environment-key")

    resolved = ProviderCredentialResolver(
        store=MemoryProviderSettingsStore(), catalog_source=StaticCatalogSource()
    ).resolve(lane, ProviderConsumer.ASSISTANT)

    assert resolved == ProviderCredentialUnavailable(
        provider=lane,
        consumer=ProviderConsumer.ASSISTANT,
        reason=ProviderCredentialUnavailableReason.CREDENTIAL_MISSING,
    )


def test_an_unknown_lane_is_unavailable_as_unknown() -> None:
    resolved = ProviderCredentialResolver(
        store=MemoryProviderSettingsStore(), catalog_source=StaticCatalogSource()
    ).resolve(MISSING_LANE, ProviderConsumer.ASSISTANT)

    assert isinstance(resolved, ProviderCredentialUnavailable)
    assert resolved.reason is ProviderCredentialUnavailableReason.UNKNOWN_PROVIDER


def test_an_agent_that_cannot_report_its_providers_resolves_nothing() -> None:
    resolved = ProviderCredentialResolver(
        store=MemoryProviderSettingsStore(), catalog_source=UnavailableCatalogSource()
    ).resolve(KEY_LANE, ProviderConsumer.ASSISTANT)

    assert isinstance(resolved, ProviderCredentialUnavailable)
    assert resolved.reason is ProviderCredentialUnavailableReason.CATALOG_UNAVAILABLE
