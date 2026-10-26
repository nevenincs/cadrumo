"""A synthetic provider catalog, parsed by the real parser, and the ports that serve it.

No real provider name appears here: the ids are invented, so a test cannot lean
on a list Cadrumo does not keep.
"""

from __future__ import annotations

import json
from typing import Any, Final, override

from ...domain.catalog import LiveCatalogModel, ProviderCatalog, parse_provider_catalog
from ..ports import (
    LiveCatalogModels,
    LiveLaneBackground,
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    ProviderCatalogUnavailableReason,
)

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
KEYLESS_LANE: Final = "local_api"
"""A keyless lane on this computer: no credential, no sign-in, a loopback endpoint."""
KEYLESS_DEFAULT_URL: Final = "http://127.0.0.1:41000"
MISSING_LANE: Final = "no_such_lane"


def _lane(
    provider: str,
    transport: str,
    auth_kind: str,
    *,
    credential_id: str | None,
    default_base_url: str | None = None,
    cli_programs: tuple[str, ...] = (),
    reads_off_host: bool = True,
    models: tuple[dict[str, Any], ...] | None = None,
    recommended: dict[str, str] | None = None,
    background: dict[str, Any] | None = None,
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
        "reads_off_host": reads_off_host,
        "cli_programs": list(cli_programs),
        "models": list(_hosted_models() if models is None else models),
        "recommended": {} if recommended is None else recommended,
        "background": _HOSTED_BACKGROUND if background is None else background,
    }


_HOSTED_BACKGROUND: Final = {"runnable": True, "inputs": ["text", "image", "pdf"], "options": []}
"""What a hosted lane's background run takes: every input family and no run option."""
HOSTED_TEXT_MODELS: Final = ("synthetic-text-1", "synthetic-text-2", "synthetic-text-3")
"""Models every hosted lane declares with no stated fact, as the agent declares a hosted model."""
HOSTED_VISION_MODELS: Final = ("synthetic-vision-1", "synthetic-vision-2")
"""Models every hosted lane declares as vision, and nothing else."""
KEYLESS_TEXT_MODEL: Final = "synthetic-text:1"
KEYLESS_VISION_MODEL: Final = "synthetic-vision:1"


def _hosted_model(model_id: str, *, vision: bool | None) -> dict[str, Any]:
    """Return one declared hosted model: only its vision may be stated, as the agent declares a hosted model."""
    return synthetic_model(model_id, vision=vision) | {"size_bytes": None, "context_length": None, "licence": None}


def _hosted_models() -> tuple[dict[str, Any], ...]:
    text = tuple(_hosted_model(model_id, vision=None) for model_id in HOSTED_TEXT_MODELS)
    return text + tuple(_hosted_model(model_id, vision=True) for model_id in HOSTED_VISION_MODELS)


def synthetic_model(model_id: str, *, vision: bool | None) -> dict[str, Any]:
    """Return one declared model shaped as the agent prints a local model, with invented facts."""
    return {
        "id": model_id,
        "display_name": model_id,
        "effort": {"reasoning": "toggle", "control": "none", "levels": [], "default": None},
        "vision": vision,
        "size_bytes": 1_000_000,
        "context_length": 4096,
        "licence": {"spdx": "MIT", "name": "Synthetic licence", "digest": "sha256:" + "0" * 64},
    }


def synthetic_document() -> str:
    """Return the schema-version-5 document the synthetic agent serves."""
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
        _lane(
            "local",
            "api",
            "none",
            credential_id=None,
            default_base_url=KEYLESS_DEFAULT_URL,
            reads_off_host=False,
            models=(
                synthetic_model(KEYLESS_TEXT_MODEL, vision=False),
                synthetic_model(KEYLESS_VISION_MODEL, vision=True),
            ),
            recommended={"text": KEYLESS_TEXT_MODEL, "vision": KEYLESS_VISION_MODEL},
            background={
                "runnable": True,
                "inputs": ["text", "image"],
                "options": ["temperature", "context_tokens", "response_schema"],
            },
        ),
        _lane("other", "api", "api_key", credential_id="other"),
        _lane("third", "cli", "api_key", credential_id="third", cli_programs=("third",)),
    ]
    return json.dumps({"schema_version": 5, "providers": lanes, "icon_attribution": {}})


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


class StaticLiveModels(LiveCatalogModels):
    """A running agent's live entries and background support per lane; ``None`` for either is no live answer.

    ``snapshots`` counts the snapshots taken, each standing for one read of the
    agent's served document; the snapshot is this same unchanging double.
    """

    def __init__(
        self,
        lanes: dict[tuple[str, str], tuple[LiveCatalogModel, ...]] | None = None,
        *,
        backgrounds: dict[tuple[str, str], LiveLaneBackground] | None = None,
    ) -> None:
        """Keep the live entries and background support each lane states; an absent lane states none."""
        self._lanes = lanes
        self._backgrounds = backgrounds
        self.reads = 0
        self.snapshots = 0

    @override
    def snapshot(self) -> StaticLiveModels:
        self.snapshots += 1
        return self

    @override
    def lane_background(self, provider: str, transport: str) -> LiveLaneBackground | None:
        return None if self._backgrounds is None else self._backgrounds.get((provider, transport))

    @override
    def lane_models(self, provider: str, transport: str) -> tuple[LiveCatalogModel, ...] | None:
        self.reads += 1
        if self._lanes is None:
            return None
        return self._lanes.get((provider, transport), ())


def live_model(model_id: str, **facts: Any) -> LiveCatalogModel:
    """Return one live entry through the real model, every fact unstated unless named."""
    stated: dict[str, Any] = {
        "vision": None,
        "size_bytes": None,
        "context_length": None,
        "licence": None,
        "installed": None,
    }
    stated.update(facts)
    return LiveCatalogModel.model_validate({"id": model_id, **stated})
