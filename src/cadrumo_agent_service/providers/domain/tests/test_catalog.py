"""The provider catalog document the agent serves, parsed strictly through the real parser."""

from __future__ import annotations

import json
from typing import Any

import pytest

from cadrumo.core.errors.hierarchy import CoreValidationError

from ..catalog import (
    BackgroundInput,
    BackgroundOption,
    ProviderAuthKind,
    ProviderConsumer,
    ProviderTransport,
    parse_provider_catalog,
    validate_https_base_url,
    validate_loopback_http_base_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _document(*lanes: dict[str, Any], schema_version: int = 5) -> str:
    return json.dumps({"schema_version": schema_version, "providers": list(lanes), "icon_attribution": {}})


_HOSTED_BACKGROUND: dict[str, Any] = {"runnable": True, "inputs": ["text", "image", "pdf"], "options": []}
_DIGEST = "sha256:" + "a" * 64


def _model(model_id: str, **overrides: Any) -> dict[str, Any]:
    """Return one declared model with every field the agent prints and no stated fact."""
    model: dict[str, Any] = {
        "id": model_id,
        "display_name": model_id,
        "effort": {"reasoning": "toggle", "control": "none", "levels": [], "default": None},
        "vision": None,
        "size_bytes": None,
        "context_length": None,
        "licence": None,
    }
    model.update(overrides)
    return model


def _local_model(model_id: str, *, vision: bool, **overrides: Any) -> dict[str, Any]:
    """Return one declared model with every fact stated, as the agent prints a local model."""
    stated: dict[str, Any] = {
        "vision": vision,
        "size_bytes": 1_889_519_687,
        "context_length": 262_144,
        "licence": {"spdx": "Apache-2.0", "name": "Synthetic licence", "digest": _DIGEST},
    }
    stated.update(overrides)
    return _model(model_id, **stated)


def _with_licence(licence: dict[str, Any]) -> str:
    return _document(_keyless_lane(models=[_local_model("synthetic-reader:1", vision=False, licence=licence)]))


def _with_model(**overrides: Any) -> str:
    return _document(_keyless_lane(models=[{**_local_model("synthetic-reader:1", vision=False), **overrides}]))


def _with_background(lane: dict[str, Any], background: dict[str, Any]) -> str:
    return _document({**lane, "background": background})


def _without(lane: dict[str, Any], field: str) -> dict[str, Any]:
    return {key: value for key, value in lane.items() if key != field}


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
        "recommended": {},
        "background": _HOSTED_BACKGROUND,
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
        "recommended": {},
        "background": _HOSTED_BACKGROUND,
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
        "models": [
            _local_model("synthetic-reader:1", vision=False),
            _local_model("synthetic-viewer:1", vision=True),
        ],
        "recommended": {"text": "synthetic-reader:1"},
        "background": {
            "runnable": True,
            "inputs": ["text", "image"],
            "options": ["temperature", "context_tokens", "response_schema"],
        },
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


def test_version_five_retains_presentation_metadata_without_affecting_authentication() -> None:
    icon = {"key": "example", "variants": [{"variant": "mono", "media_type": "image/svg+xml", "sha256": "a" * 64}]}
    effort = {"reasoning": "supported", "control": "levels", "levels": ["low", "high"], "default": "low"}
    document = json.loads(_document(_cli_lane(icon=icon, models=[_model("sample", effort=effort)])))
    document["icon_attribution"] = {"title": "Synthetic artwork", "licence": "MIT"}

    catalog = parse_provider_catalog(json.dumps(document))

    assert catalog.providers[0].description == "Synthetic CLI provider"
    assert catalog.providers[0].icon == icon
    assert catalog.providers[0].models[0].effort == effort
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


def test_a_lane_shaped_as_the_agents_local_lane_parses_every_typed_model_fact() -> None:
    """The lane mirrors the agent's printed local lane field for field, with invented model ids and facts."""
    lane = _keyless_lane(
        description="Open models run on this computer by a local server.",
        default_base_url="http://127.0.0.1:11434",
        icon=None,
        platform={"docs_url": None, "models_url": None, "status": {"kind": "none", "page_url": None, "api_url": None}},
        default_model="synthetic-reader:1",
        models=[
            _local_model("synthetic-viewer:1", vision=True),
            _local_model("synthetic-reader:1", vision=False),
            _model("synthetic-unstated:1"),
        ],
        recommended={"vision": "synthetic-viewer:1", "text": "synthetic-reader:1"},
        unread=[],
    )

    keyless = parse_provider_catalog(_document(lane)).entry("local_api")

    assert keyless is not None
    viewer = keyless.model("synthetic-viewer:1")
    assert viewer is not None and viewer.licence is not None
    assert (viewer.vision, viewer.size_bytes, viewer.context_length) == (True, 1_889_519_687, 262_144)
    assert (viewer.licence.spdx, viewer.licence.name, viewer.licence.digest) == (
        "Apache-2.0",
        "Synthetic licence",
        _DIGEST,
    )
    reader = keyless.model("synthetic-reader:1")
    assert reader is not None and reader.vision is False
    unstated = keyless.model("synthetic-unstated:1")
    assert unstated is not None
    assert (unstated.vision, unstated.size_bytes, unstated.context_length, unstated.licence) == (None, None, None, None)
    assert keyless.model("synthetic-absent:1") is None
    assert keyless.background.runnable is True
    assert keyless.background.inputs == (BackgroundInput.TEXT, BackgroundInput.IMAGE)
    assert keyless.background.options == (
        BackgroundOption.TEMPERATURE,
        BackgroundOption.CONTEXT_TOKENS,
        BackgroundOption.RESPONSE_SCHEMA,
    )


def test_a_lane_that_runs_no_background_request_parses_with_no_input() -> None:
    catalog = parse_provider_catalog(_with_background(_cli_lane(), {"runnable": False, "inputs": [], "options": []}))

    background = catalog.providers[0].background
    assert (background.runnable, background.inputs, background.options) == (False, (), ())


def test_a_licence_without_an_spdx_identifier_parses() -> None:
    licence = {"spdx": None, "name": "Synthetic community licence", "digest": _DIGEST}

    keyless = parse_provider_catalog(_with_licence(licence)).entry("local_api")

    assert keyless is not None
    reader = keyless.model("synthetic-reader:1")
    assert reader is not None and reader.licence is not None
    assert (reader.licence.spdx, reader.licence.name) == (None, "Synthetic community licence")


_AGENT_MODEL_ID_LENGTH = 512
"""cadrumo-agent's longest public id, which its catalogues bound a model id by."""
_AGENT_LANES = 128
"""The most lanes cadrumo-agent's catalogues carry."""
_AGENT_DISPLAY_LENGTH = 256
"""cadrumo-agent's longest display text, which its catalogues bound a licence's SPDX identifier by."""


def _lanes(count: int) -> str:
    """Return a document of ``count`` keyless lanes, each its own provider identity."""
    return _document(
        *(
            _keyless_lane(id=f"local{index}_api", provider=f"local{index}", display_name=f"Local {index}")
            for index in range(count)
        )
    )


def test_a_model_the_agent_states_a_zero_size_for_parses_with_that_size() -> None:
    keyless = parse_provider_catalog(_with_model(size_bytes=0)).entry("local_api")

    assert keyless is not None
    reader = keyless.model("synthetic-reader:1")
    assert reader is not None and reader.size_bytes == 0


def test_a_model_id_as_long_as_the_agent_allows_parses_and_one_longer_is_refused() -> None:
    longest = "m" * _AGENT_MODEL_ID_LENGTH
    document = _document(_keyless_lane(models=[_local_model(longest, vision=False)], recommended={"text": longest}))

    keyless = parse_provider_catalog(document).entry("local_api")

    assert keyless is not None and keyless.model(longest) is not None
    assert keyless.recommended == {"text": longest}
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(_with_model(id=longest + "m"))


def test_a_model_id_with_a_control_character_is_refused() -> None:
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(_with_model(id="synthetic\x00reader:1"))


def test_as_many_lanes_as_the_agent_allows_parse_and_one_more_is_refused() -> None:
    assert len(parse_provider_catalog(_lanes(_AGENT_LANES)).providers) == _AGENT_LANES
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(_lanes(_AGENT_LANES + 1))


def test_an_spdx_identifier_as_long_as_the_agent_allows_parses_and_one_longer_is_refused() -> None:
    longest = "S" * _AGENT_DISPLAY_LENGTH
    keyless = parse_provider_catalog(_with_licence({"spdx": longest, "name": "Synthetic", "digest": _DIGEST})).entry(
        "local_api"
    )

    assert keyless is not None
    reader = keyless.model("synthetic-reader:1")
    assert reader is not None and reader.licence is not None and reader.licence.spdx == longest
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(_with_licence({"spdx": longest + "S", "name": "Synthetic", "digest": _DIGEST}))


_AGENT_PROVIDER_ID_LENGTH = 64
"""cadrumo-agent's longest provider metadata key, which bounds a provider id and its credential id."""
_PROGRAM_NAME_LENGTH = 255
"""The longest file name a cli program can have on a common filesystem."""


def _provider_lane(provider: str) -> dict[str, Any]:
    return _key_lane(id=f"{provider}_api", provider=provider, agent_credential_id=provider)


def test_a_provider_id_as_long_as_the_agent_allows_parses_and_one_longer_is_refused() -> None:
    longest = "p" * _AGENT_PROVIDER_ID_LENGTH
    lane_id = f"{longest}_api"

    entry = parse_provider_catalog(_document(_provider_lane(longest))).entry(lane_id)

    assert entry is not None and (entry.id, entry.provider, entry.agent_credential_id) == (lane_id, longest, longest)
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(_document(_provider_lane(longest + "p")))


def test_a_credential_id_as_long_as_the_agent_allows_parses_and_one_longer_is_refused() -> None:
    longest = "c" * _AGENT_PROVIDER_ID_LENGTH

    entry = parse_provider_catalog(_document(_key_lane(agent_credential_id=longest))).entry("example_api")

    assert entry is not None and entry.agent_credential_id == longest
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(_document(_key_lane(agent_credential_id=longest + "c")))


def test_a_lane_id_one_past_the_longest_provider_and_transport_is_neither_parsed_nor_looked_up() -> None:
    catalog = parse_provider_catalog(_document(_key_lane()))

    assert catalog.entry("p" * (_AGENT_PROVIDER_ID_LENGTH + 1) + "_api") is None
    assert catalog.entry("example_api") is not None


def test_a_lane_id_stored_under_the_earlier_forty_character_rule_still_parses() -> None:
    provider = "o" * 36
    entry = parse_provider_catalog(_document(_provider_lane(provider))).entry(f"{provider}_api")

    assert entry is not None and len(entry.id) == 40


def test_a_display_name_as_long_as_the_agent_serves_parses_and_one_longer_is_refused() -> None:
    longest = "D" * _AGENT_DISPLAY_LENGTH

    entry = parse_provider_catalog(_document(_key_lane(display_name=longest))).entry("example_api")

    assert entry is not None and entry.display_name == longest
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(_document(_key_lane(display_name=longest + "D")))


@pytest.mark.parametrize(
    "program",
    [
        pytest.param("x" * _PROGRAM_NAME_LENGTH, id="longest-file-name"),
        pytest.param("agy", id="short"),
        pytest.param("Example-CLI.v2", id="mixed-case-dot-and-hyphen"),
    ],
)
def test_a_cli_program_that_is_one_file_name_parses(program: str) -> None:
    entry = parse_provider_catalog(_document(_cli_lane(cli_programs=[program]))).entry("example_cli")

    assert entry is not None and entry.cli_programs == (program,)


@pytest.mark.parametrize(
    "program",
    [
        pytest.param("x" * (_PROGRAM_NAME_LENGTH + 1), id="one-past-the-longest-file-name"),
        pytest.param("", id="empty"),
        pytest.param("bin/example", id="slash"),
        pytest.param("bin\\example", id="backslash"),
        pytest.param("c:example", id="drive-colon"),
        pytest.param("exam\tple", id="control-character"),
    ],
)
def test_a_cli_program_that_is_not_one_file_name_is_refused(program: str) -> None:
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(_document(_cli_lane(cli_programs=[program])))


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
        pytest.param(_document(_key_lane(), schema_version=6), id="unknown-schema-version"),
        pytest.param(_document(_key_lane(), schema_version=4), id="retired-schema-version-four"),
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
        pytest.param(
            _document(_key_lane(recommended={"text": "synthetic-reader:1"})), id="recommended-on-modelless-lane"
        ),
        pytest.param(_document(_without(_keyless_lane(), "recommended")), id="missing-recommended"),
        pytest.param(_document(_without(_key_lane(), "background")), id="missing-background"),
        pytest.param(
            _with_background(_key_lane(), {"runnable": True, "inputs": ["text", "audio"], "options": []}),
            id="unknown-input-kind",
        ),
        pytest.param(
            _with_background(_key_lane(), {"runnable": True, "inputs": ["text", "text"], "options": []}),
            id="duplicate-input",
        ),
        pytest.param(
            _with_background(_key_lane(), {"runnable": True, "inputs": ["image", "text"], "options": []}),
            id="inputs-out-of-order",
        ),
        pytest.param(
            _with_background(
                _key_lane(), {"runnable": True, "inputs": ["text"], "options": ["temperature", "temperature"]}
            ),
            id="duplicate-option",
        ),
        pytest.param(
            _with_background(_key_lane(), {"runnable": True, "inputs": ["text"], "options": ["seed"]}),
            id="unknown-option",
        ),
        pytest.param(
            _with_background(
                _key_lane(), {"runnable": True, "inputs": ["text"], "options": ["response_schema", "temperature"]}
            ),
            id="options-out-of-order",
        ),
        pytest.param(
            _with_background(_cli_lane(), {"runnable": False, "inputs": ["text"], "options": []}),
            id="unrunnable-lane-with-input",
        ),
        pytest.param(
            _with_background(_key_lane(), {"runnable": "yes", "inputs": [], "options": []}),
            id="runnable-not-a-bool",
        ),
        pytest.param(
            _with_background(_key_lane(), {"runnable": True, "inputs": ["text"], "options": [], "extra": 1}),
            id="background-unknown-field",
        ),
        pytest.param(_with_model(size_bytes=-1), id="size-negative"),
        pytest.param(_with_model(size_bytes="1"), id="size-not-an-integer"),
        pytest.param(_with_model(size_bytes=1.5), id="size-fractional"),
        pytest.param(_with_model(context_length=0), id="context-length-zero"),
        pytest.param(_with_model(vision="yes"), id="vision-not-a-bool"),
        pytest.param(_with_model(installed=True), id="model-unknown-field"),
        pytest.param(
            _document(_keyless_lane(models=[_without(_local_model("synthetic-reader:1", vision=False), "licence")])),
            id="model-missing-licence",
        ),
        pytest.param(
            _document(_keyless_lane(models=[_without(_local_model("synthetic-reader:1", vision=False), "vision")])),
            id="model-missing-vision",
        ),
        pytest.param(
            _document(_keyless_lane(models=[_model("synthetic-reader:1"), _model("synthetic-reader:1")])),
            id="duplicate-model",
        ),
        pytest.param(
            _with_licence({"spdx": "MIT", "name": "Synthetic", "digest": "sha256:" + "A" * 64}),
            id="licence-digest-uppercase",
        ),
        pytest.param(
            _with_licence({"spdx": "MIT", "name": "Synthetic", "digest": "md5:" + "a" * 32}),
            id="licence-digest-wrong-algorithm",
        ),
        pytest.param(
            _with_licence({"spdx": "MIT", "name": "Synthetic", "digest": "sha256:" + "a" * 63}),
            id="licence-digest-short",
        ),
        pytest.param(
            _with_licence({"spdx": "MIT", "name": "Synthetic", "digest": "sha256:" + "g" * 64}),
            id="licence-digest-not-hex",
        ),
        pytest.param(_with_licence({"spdx": "MIT", "name": "", "digest": _DIGEST}), id="licence-name-empty"),
        pytest.param(_with_licence({"spdx": "MIT", "name": "Synthetic"}), id="licence-missing-digest"),
        pytest.param(
            _with_licence({"spdx": "MIT", "name": "Synthetic", "digest": _DIGEST, "url": "x"}),
            id="licence-unknown-field",
        ),
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
