"""The installation's Google client is read from one place and nowhere else."""

from __future__ import annotations

import ast
import inspect
import json
import tomllib
from pathlib import Path

import pytest

from .....core.config import Settings
from .....core.resources.bundled_data import packaged_data
from .. import installation_client
from ..errors import GoogleAuthClientMetadataUnavailableError, GoogleAuthPreconditionCondition
from ..installation_client import INSTALLATION_CLIENT_DATA_PARTS, load_installation_client
from .installation_client_support import (
    SYNTHETIC_CLIENT_CREDENTIAL,
    SYNTHETIC_CLIENT_ID,
    synthetic_installation_client,
    use_absent_installation_client,
    use_installation_client,
    use_installation_client_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[6]


def _envelope() -> dict[str, dict[str, object]]:
    """Return the synthetic client as the JSON document Google issues."""
    client = synthetic_installation_client()
    fields: dict[str, object] = dict(client.model_dump(mode="json"))
    fields["redirect_uris"] = list(client.redirect_uris)
    return {"installed": fields}


def _write(directory: Path, content: bytes) -> Path:
    path = directory / "oauth_client.json"
    path.write_bytes(content)
    return path


def test_a_desktop_client_download_is_read_into_the_validated_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    installed = use_installation_client(monkeypatch, tmp_path)

    assert load_installation_client() == installed
    assert load_installation_client().redirect_uris == ("http://localhost",)


def test_an_installation_without_the_file_refuses_with_the_one_typed_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_absent_installation_client(monkeypatch, tmp_path)

    with pytest.raises(GoogleAuthClientMetadataUnavailableError) as refused:
        load_installation_client()

    error = refused.value
    assert error.code.code == "REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE"
    assert error.translated_message is None
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == GoogleAuthPreconditionCondition.CLIENT_METADATA_AVAILABLE.value
    assert dict(verdict.evidence[0].values) == {"client_metadata_present": False}


def test_a_directory_at_the_location_is_an_absent_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    location = tmp_path / "oauth_client.json"
    location.mkdir()
    use_installation_client_file(monkeypatch, location)

    with pytest.raises(GoogleAuthClientMetadataUnavailableError) as refused:
        load_installation_client()

    assert refused.value.translated_message is None


def _without(field: str):
    def mutate(document: dict[str, dict[str, object]]) -> object:
        del document["installed"][field]
        return document

    return mutate


def _with(field: str, value: object):
    def mutate(document: dict[str, dict[str, object]]) -> object:
        document["installed"][field] = value
        return document

    return mutate


@pytest.mark.parametrize(
    "mutate",
    (
        pytest.param(lambda document: {"web": document["installed"]}, id="web-client-envelope"),
        pytest.param(lambda document: document["installed"], id="no-envelope"),
        pytest.param(lambda document: [document], id="not-an-object"),
        pytest.param(_without("client_id"), id="no-client-id"),
        pytest.param(_without("client_secret"), id="no-client-secret"),
        pytest.param(_with("client_id", ""), id="blank-client-id"),
        pytest.param(_with("token_uri", "https://oauth2.example.invalid/token"), id="foreign-token-endpoint"),
        pytest.param(_with("auth_uri", "http://accounts.google.com/o/oauth2/auth"), id="plain-http-auth-endpoint"),
        pytest.param(_with("unexpected", "value"), id="unknown-field"),
    ),
)
def test_a_file_that_is_not_a_google_desktop_client_is_refused_as_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mutate
) -> None:
    document = mutate(_envelope())
    use_installation_client_file(monkeypatch, _write(tmp_path, json.dumps(document).encode("utf-8")))

    with pytest.raises(GoogleAuthClientMetadataUnavailableError) as refused:
        load_installation_client()

    error = refused.value
    assert error.code.code == "REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE"
    assert error.translated_message == "adapters.google.installation_client.errors.client_metadata_invalid"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert dict(verdict.evidence[0].values) == {"client_metadata_present": True, "client_metadata_valid": False}


@pytest.mark.parametrize(
    "content",
    (
        pytest.param(b"", id="empty"),
        pytest.param(b"{not json", id="malformed-json"),
        pytest.param(b"\xff\xfe\x00{", id="not-utf-8"),
        pytest.param(b" " * 65_537, id="over-the-size-bound"),
    ),
)
def test_unreadable_content_is_refused_as_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, content: bytes
) -> None:
    use_installation_client_file(monkeypatch, _write(tmp_path, content))

    with pytest.raises(GoogleAuthClientMetadataUnavailableError) as refused:
        load_installation_client()

    assert refused.value.translated_message == "adapters.google.installation_client.errors.client_metadata_invalid"


def test_an_invalid_file_never_surfaces_its_contents(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The file holds the client secret, so no part of it may reach an error."""
    document = _envelope()
    document["installed"]["token_uri"] = "https://oauth2.example.invalid/token"
    use_installation_client_file(monkeypatch, _write(tmp_path, json.dumps(document).encode("utf-8")))

    with pytest.raises(GoogleAuthClientMetadataUnavailableError) as refused:
        load_installation_client()

    error = refused.value
    rendered = "\n".join((str(error), repr(error), repr(error.context), repr(error.__cause__), repr(error.__context__)))
    assert SYNTHETIC_CLIENT_CREDENTIAL not in rendered
    assert "example.invalid" not in rendered


def test_the_location_is_the_bundled_data_root_and_is_not_configurable() -> None:
    """One location, read through the canonical bundled-data reader, with no operator override.

    The suite redirects the location away from a developer's real file, so the
    production resolver is checked in source rather than by calling it.
    """
    assert INSTALLATION_CLIENT_DATA_PARTS == ("google", "oauth_client.json")
    resolver = next(
        node
        for node in ast.parse(inspect.getsource(installation_client)).body
        if isinstance(node, ast.FunctionDef) and node.name == "installation_client_source"
    )
    assert [argument.arg for argument in resolver.args.args] == []
    statements = [node for node in resolver.body if not isinstance(node, ast.Expr)]
    assert [ast.unparse(node) for node in statements] == ["return packaged_data(*INSTALLATION_CLIENT_DATA_PARTS)"]
    assert installation_client.packaged_data is packaged_data
    assert sorted(name for name in Settings.model_fields if "google" in name and "client" in name) == []


def test_the_shipped_client_file_is_a_valid_desktop_client_carried_by_every_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The publisher client is part of the application: present, readable, and excluded from no build."""
    shipped = packaged_data(*INSTALLATION_CLIENT_DATA_PARTS)
    assert shipped.is_file()
    monkeypatch.setattr(installation_client, "installation_client_source", lambda: shipped)

    client = load_installation_client()

    # Shape only: the values themselves are never asserted on or printed.
    assert client.client_id.endswith(".apps.googleusercontent.com")
    assert client.client_id != SYNTHETIC_CLIENT_ID

    directory = f"src/cadrumo/_data/{INSTALLATION_CLIENT_DATA_PARTS[0]}"
    ignore_rules = (_REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert not [rule for rule in ignore_rules if rule.strip().strip("/") == directory]
    targets = tomllib.loads((_REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"][
        "build"
    ]["targets"]
    for target in ("sdist", "wheel"):
        assert not [entry for entry in targets[target]["exclude"] if entry.startswith(directory)], target
