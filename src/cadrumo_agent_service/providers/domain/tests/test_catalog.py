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
    development_key_variable,
    parse_provider_catalog,
    validate_https_base_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _document(*lanes: dict[str, Any], schema_version: int = 2) -> str:
    return json.dumps({"schema_version": schema_version, "providers": list(lanes)})


def _key_lane(**overrides: Any) -> dict[str, Any]:
    lane: dict[str, Any] = {
        "id": "example_api",
        "provider": "example",
        "transport": "api",
        "display_name": "Example",
        "auth_kind": "api_key",
        "default_base_url": None,
        "agent_credential_id": "example",
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
        "auth_kind": "provider_sign_in_only",
        "default_base_url": None,
        "agent_credential_id": None,
        "cli_programs": ["example"],
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
    assert catalog.credential_lane_ids == ("example_api", "sample_cli", "plain_api")
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


def test_the_development_variable_is_constructed_from_the_provider_id() -> None:
    catalog = parse_provider_catalog(_document(_key_lane(), _cli_lane()))

    assert {entry.development_variable for entry in catalog.providers} == {"CADRUMO_LLM_EXAMPLE_API_KEY"}
    assert development_key_variable("zz_provider") == "CADRUMO_LLM_ZZ_PROVIDER_API_KEY"


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
        pytest.param(_document(_key_lane(), schema_version=3), id="unknown-schema-version"),
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
