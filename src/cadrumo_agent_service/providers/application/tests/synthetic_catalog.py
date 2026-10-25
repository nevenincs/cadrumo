"""A synthetic provider catalog, parsed by the real parser, and the ports that serve it.

No real provider name appears here: the ids are invented, so a test cannot lean
on a list Cadrumo does not keep.
"""

from __future__ import annotations

import json
from typing import Any, Final, override

from ...domain.catalog import ProviderCatalog, parse_provider_catalog
from ..ports import ProviderCatalogSource, ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason

KEY_LANE: Final = "example_api"
"""A plain API-key lane whose credential the agent keys as ``example``."""
SIGN_IN_ONLY_LANE: Final = "example_cli"
"""A CLI lane of the same provider that takes only the provider's own sign-in and declares no credential id."""
OTHER_KEY_LANE: Final = "other_api"
THIRD_LANE: Final = "third_cli"
"""A CLI lane that takes a key."""
DEFAULTED_KEY_LANE: Final = "defaulted_api"
"""A plain API-key lane that declares a default endpoint."""
GATEWAY_LANE: Final = "gateway_cli"
"""An API-key-with-base-url lane that declares a default gateway URL."""
GATEWAY_DEFAULT_URL: Final = "https://gateway.example.invalid/v1"
BARE_GATEWAY_LANE: Final = "bare_cli"
"""An API-key-with-base-url lane with no default, so a key needs a stored URL."""
MISSING_LANE: Final = "no_such_lane"


def _lane(
    provider: str,
    transport: str,
    auth_kind: str,
    *,
    credential_id: str | None,
    default_base_url: str | None = None,
    cli_programs: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": f"{provider}_{transport}",
        "provider": provider,
        "transport": transport,
        "display_name": provider.capitalize(),
        "description": "Synthetic provider lane",
        "auth_kind": auth_kind,
        "default_base_url": default_base_url,
        "agent_credential_id": credential_id,
        "cli_programs": list(cli_programs),
    }


def synthetic_document() -> str:
    """Return the schema-version-3 document the synthetic agent serves."""
    lanes = [
        _lane("bare", "cli", "api_key_with_base_url", credential_id="bare", cli_programs=("example",)),
        _lane(
            "defaulted",
            "api",
            "api_key",
            credential_id="defaulted",
            default_base_url="https://defaulted.example.invalid",
        ),
        _lane("example", "api", "api_key", credential_id="example"),
        _lane("example", "cli", "provider_sign_in_only", credential_id=None, cli_programs=("example",)),
        _lane(
            "gateway",
            "cli",
            "api_key_with_base_url",
            credential_id="gateway",
            default_base_url=GATEWAY_DEFAULT_URL,
            cli_programs=("example", "example-helper"),
        ),
        _lane("other", "api", "api_key", credential_id="other"),
        _lane("third", "cli", "api_key", credential_id="third", cli_programs=("third",)),
    ]
    return json.dumps({"schema_version": 3, "providers": lanes, "icon_attribution": {}})


def synthetic_catalog() -> ProviderCatalog:
    """Return the synthetic catalog through the real strict parser."""
    return parse_provider_catalog(synthetic_document())


class ProvidedProviderCatalogSource(ProviderCatalogSource):
    """Serve a catalog the test already parsed, unchanged."""

    def __init__(self, catalog: ProviderCatalog) -> None:
        """Keep the parsed catalog."""
        self._catalog = catalog

    @override
    def catalog(self) -> ProviderCatalog:
        """Return the parsed catalog."""
        return self._catalog


class StaticCatalogSource(ProvidedProviderCatalogSource):
    """Serve the synthetic catalog, as an agent whose declaration never changes would."""

    def __init__(self) -> None:
        """Serve the synthetic catalog."""
        super().__init__(synthetic_catalog())


class UnavailableCatalogSource(ProviderCatalogSource):
    """An agent that cannot report its providers."""

    @override
    def catalog(self) -> ProviderCatalog:
        raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_NOT_FOUND)
