"""The provider catalog document the agent serves, parsed strictly through the real parser."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cadrumo.core.errors.hierarchy import CoreValidationError

from ..catalog import (
    ProviderAuthKind,
    ProviderConsumer,
    ProviderTransport,
    parse_provider_catalog,
    validate_https_base_url,
    validate_loopback_http_base_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _document(*lanes: dict[str, Any], schema_version: int = 4) -> str:
    return json.dumps({"schema_version": schema_version, "providers": list(lanes), "icon_attribution": {}})


def _key_lane(**overrides: Any) -> dict[str, Any]:
    lane: dict[str, Any] = {
        "id": "example_api",
        "provider": "example",
        "transport": "api",
        "display_name": "Example",
        "description": "Synthetic API provider",
        "auth_kind": "api_key",
        "default_base_url": None,
        "agent_credential_id": "example",
        "reads_off_host": True,
        "cli_programs": [],
    }
    lane.update(overrides)
    return lane


def _cli_lane(**overrides: Any) -> dict[str, Any]:
    lane: dict[str, Any] = {
        "id": "example_cli",
        "provider": "example",
        "transport": "cli",
        "display_name": "Example",
        "description": "Synthetic CLI provider",
        "auth_kind": "provider_sign_in_only",
        "default_base_url": None,
        "agent_credential_id": None,
        "reads_off_host": True,
        "cli_programs": ["example"],
    }
    lane.update(overrides)
    return lane


def _keyless_lane(**overrides: Any) -> dict[str, Any]:
    lane: dict[str, Any] = {
        "id": "local_api",
        "provider": "local",
        "transport": "api",
        "display_name": "Local",
        "description": "Synthetic keyless lane on this computer",
        "auth_kind": "none",
        "default_base_url": "http://127.0.0.1:41000",
        "agent_credential_id": None,
        "reads_off_host": False,
        "cli_programs": [],
        "models": [{"id": "synthetic-reader:1"}, {"id": "synthetic-viewer:1"}],
    }
    lane.update(overrides)
    return lane


def test_a_valid_document_parses_into_typed_lanes() -> None:
    gateway = _cli_lane(
        id="sample_cli",
        provider="sample",
        display_name="Sample",
        auth_kind="api_key_with_base_url",
        default_base_url="https://gateway.example.invalid/v1",
        agent_credential_id="sample",
        cli_programs=["example", "example-helper"],
    )
    defaulted = _key_lane(
        id="plain_api",
        provider="plain",
        display_name="Plain",
        agent_credential_id="plain",
        default_base_url="https://plain.example.invalid",
    )
    catalog = parse_provider_catalog(_document(_key_lane(), _cli_lane(), gateway, defaulted))

    assert catalog.provider_ids == ("example_api", "example_cli", "sample_cli", "plain_api")
    assert [entry.agent_credential_id for entry in catalog.providers] == ["example", None, "sample", "plain"]
    api = catalog.providers[0]
    assert (api.transport, api.auth_kind, api.agent_credential_id, api.cli_programs) == (
        ProviderTransport.API,
        ProviderAuthKind.API_KEY,
        "example",
        (),
    )
    assert catalog.providers[1].auth_kind.accepts_provider_sign_in
    assert catalog.providers[2].default_base_url == "https://gateway.example.invalid/v1"
    assert catalog.providers[2].cli_programs == ("example", "example-helper")
    assert catalog.providers[3].default_base_url == "https://plain.example.invalid"
    assert api.consumers == (ProviderConsumer.ASSISTANT,)


def test_version_four_retains_presentation_metadata_without_affecting_authentication() -> None:
    icon = {"key": "example", "variants": [{"variant": "mono", "media_type": "image/svg+xml", "sha256": "a" * 64}]}
    effort = {"reasoning": "supported", "control": "levels", "levels": ["low", "high"], "default": "low"}
    document = json.loads(_document(_cli_lane(icon=icon, models=[{"id": "sample", "effort": effort}])))
    document["icon_attribution"] = {"title": "Synthetic artwork", "licence": "MIT"}

    catalog = parse_provider_catalog(json.dumps(document))

    assert catalog.providers[0].description == "Synthetic CLI provider"
    assert catalog.providers[0].icon == icon
    assert catalog.providers[0].models[0]["effort"] == effort
    assert catalog.icon_attribution == document["icon_attribution"]
    assert catalog.providers[0].agent_credential_id is None
    assert catalog.providers[0].auth_kind is ProviderAuthKind.PROVIDER_SIGN_IN_ONLY


def test_a_keyless_lane_parses_with_its_loopback_url_and_on_host_flag() -> None:
    catalog = parse_provider_catalog(
        _document(_key_lane(), _keyless_lane(recommended={"vision": "synthetic-viewer:1"}))
    )

    keyless = catalog.entry("local_api")
    assert keyless is not None
    assert keyless.auth_kind is ProviderAuthKind.NONE
    assert (keyless.agent_credential_id, keyless.default_base_url) == (None, "http://127.0.0.1:41000")
    assert keyless.reads_off_host is False
    assert keyless.recommended == {"vision": "synthetic-viewer:1"}
    assert catalog.providers[0].reads_off_host is True
    assert catalog.providers[0].recommended == {}


def test_the_keyless_kind_takes_no_credential_no_sign_in_and_no_url_override() -> None:
    kind = ProviderAuthKind.NONE

    assert (kind.accepts_direct_credential, kind.accepts_provider_sign_in, kind.accepts_base_url) == (
        False,
        False,
        False,
    )


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:11434", "http://localhost:1", "http://[::1]:65535", "http://127.0.0.1/", "http://localhost"],
)
def test_loopback_http_origins_pass(url: str) -> None:
    assert validate_loopback_http_base_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:11434",
        "http://192.0.2.1:11434",
        "http://gateway.example.invalid:11434",
        "http://127.0.0.2:11434",
        "http://[::2]:11434",
        "http://[::1:11434",
        "http://127.0.0.1:11434/*",
        "http://127.0.0.1:11434/api",
        "http://user:pw@127.0.0.1:11434",
        "http://127.0.0.1:11434?q=1",
        "http://127.0.0.1:11434#frag",
        "http://127.0.0.1:0",
        "http://127.0.0.1:65536",
        "http://127.0.0.1:",
        " http://127.0.0.1:11434",
        "",
    ],
)
def test_non_loopback_or_decorated_urls_are_refused(url: str) -> None:
    with pytest.raises(ValueError):
        validate_loopback_http_base_url(url)


def test_entry_lookup_refuses_ids_outside_the_lane_grammar() -> None:
    catalog = parse_provider_catalog(_document(_key_lane()))

    assert catalog.entry("example_api") is not None
    assert catalog.entry("missing_lane") is None
    assert catalog.entry("../example_api") is None
    assert catalog.entry("Example_Api") is None


@pytest.mark.parametrize(
    "url",
    [
        "http://gateway.example.invalid",
        "https://",
        "https://user:pw@gateway.example.invalid",
        "https://gateway.example.invalid/?q=1",
        "https://gateway.example.invalid/a*b",
        "https://gateway.example.invalid/a[b",
        "https://gateway.example.invalid/%41",
        "https://gateway.example.invalid/$HOME",
        "https://gatewäy.example.invalid",
        "https://gateway.example.invalid/" + chr(7),
        "-https://gateway.example.invalid",
        "https://gateway.example.invalid/" + "a" * 2048,
    ],
)
def test_base_url_rejections_match_the_desktop_host(url: str) -> None:
    with pytest.raises(ValueError):
        validate_https_base_url(url)


def test_acceptable_base_url_passes() -> None:
    url = "https://gateway.example.invalid/v1"

    assert validate_https_base_url(url) == url


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(_document(_key_lane(), schema_version=5), id="unknown-schema-version"),
        pytest.param(_document(_key_lane(), schema_version=3), id="retired-schema-version-three"),
        pytest.param(
            _document({key: value for key, value in _key_lane().items() if key != "reads_off_host"}),
            id="missing-reads-off-host",
        ),
        pytest.param(
            _document({key: value for key, value in _keyless_lane().items() if key != "reads_off_host"}),
            id="keyless-lane-missing-reads-off-host",
        ),
        pytest.param(_document(_key_lane(reads_off_host="false")), id="reads-off-host-not-a-bool"),
        pytest.param(_document(_keyless_lane(default_base_url="https://127.0.0.1:41000")), id="https-on-keyless"),
        pytest.param(_document(_keyless_lane(default_base_url="http://192.0.2.1:41000")), id="non-loopback-http"),
        pytest.param(_document(_keyless_lane(default_base_url="http://127.0.0.1:41000/api")), id="loopback-path"),
        pytest.param(
            _document(_keyless_lane(default_base_url="http://user:pw@127.0.0.1:41000")), id="loopback-credential"
        ),
        pytest.param(_document(_keyless_lane(default_base_url="http://127.0.0.1:41000?q=1")), id="loopback-query"),
        pytest.param(_document(_keyless_lane(default_base_url=None)), id="keyless-without-url"),
        pytest.param(_document(_key_lane(default_base_url="http://127.0.0.1:41000")), id="http-on-key-lane"),
        pytest.param(
            _document(
                _cli_lane(
                    auth_kind="api_key_with_base_url",
                    agent_credential_id="example",
                    default_base_url="http://localhost:41000",
                )
            ),
            id="http-on-gateway-lane",
        ),
        pytest.param(_document(_keyless_lane(agent_credential_id="local")), id="credential-id-on-keyless"),
        pytest.param(_document(_keyless_lane(recommended={"vision": "not-listed:1"})), id="recommended-not-listed"),
        pytest.param(_document(_keyless_lane(recommended={"": "synthetic-reader:1"})), id="recommended-empty-key"),
        pytest.param(_document(_keyless_lane(recommended={"vision": 1})), id="recommended-not-a-string"),
        pytest.param(_document(_key_lane(), schema_version=2), id="retired-schema-version"),
        pytest.param(_document(_key_lane(), schema_version=0), id="schema-version-zero"),
        pytest.param(_document(), id="no-lanes"),
        pytest.param(_document(_key_lane(), _key_lane()), id="duplicate-lane"),
        pytest.param(
            _document(_key_lane(), _key_lane(id="second_api", provider="second", display_name="Second")),
            id="duplicate-credential-id",
        ),
        pytest.param(_document(_key_lane(cli_programs=["example"])), id="api-lane-with-program"),
        pytest.param(_document(_key_lane(id="example_cli", transport="cli")), id="cli-lane-without-program"),
        pytest.param(_document(_cli_lane(cli_programs=["example", "example"])), id="repeated-program"),
        pytest.param(_document(_key_lane(id="other_api")), id="id-is-not-provider-and-transport"),
        pytest.param(_document(_key_lane(agent_credential_id=None)), id="key-lane-without-credential-id"),
        pytest.param(_document(_cli_lane(agent_credential_id="example")), id="sign-in-only-lane-with-credential-id"),
        pytest.param(_document(_key_lane(), _cli_lane(display_name="Other")), id="identity-names-disagree"),
        pytest.param(_document(_key_lane(id="Example-Api", provider="Example-Api")), id="lane-id-outside-grammar"),
        pytest.param(_document(_key_lane(unexpected="x")), id="unknown-field"),
        pytest.param(_document(_key_lane(auth_kind="oauth_token_or_provider_sign_in")), id="retired-auth-kind"),
        pytest.param(_document(_key_lane(auth_kind="magic")), id="unknown-auth-kind"),
        pytest.param(_document(_key_lane(id="example_web", transport="web")), id="unknown-transport"),
        pytest.param(
            _document({key: value for key, value in _key_lane().items() if key != "cli_programs"}),
            id="missing-field",
        ),
        pytest.param('{"schema_version": 1, "providers": [', id="not-json"),
        pytest.param("[]", id="not-an-object"),
    ],
)
def test_malformed_catalog_is_refused(document: str) -> None:
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(document)
