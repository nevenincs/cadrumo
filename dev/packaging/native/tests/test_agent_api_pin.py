from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from ..agent_api_pin import PIN_DIRECTORY, AgentApiPinError, require_pinned_agent_api

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DOCUMENT = b'{"openapi":"3.1.0","info":{"title":"cadrumo-agent","version":"1"}}\n'
_COMMIT = "0" * 39 + "1"


def _pin(directory: Path, document: bytes = _DOCUMENT, overrides: Mapping[str, str] | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "openapi.json").write_bytes(document)
    record = {
        "source": "cadrumo-agent",
        "path": "openapi.json",
        "commit": _COMMIT,
        "sha256": hashlib.sha256(document).hexdigest(),
    } | dict(overrides or {})
    (directory / "pin.json").write_text(json.dumps(record), encoding="utf-8")
    return directory


def _checkout(root: Path, document: bytes = _DOCUMENT) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "openapi.json").write_bytes(document)
    return root


def test_a_checkout_serving_the_pinned_api_is_admitted(tmp_path: Path) -> None:
    require_pinned_agent_api(_checkout(tmp_path / "agent"), _pin(tmp_path / "pin"))


def test_a_checkout_differing_by_one_byte_is_refused_with_both_digests(tmp_path: Path) -> None:
    changed = _DOCUMENT.replace(b'"1"', b'"2"')
    with pytest.raises(AgentApiPinError, match=hashlib.sha256(changed).hexdigest()) as refused:
        require_pinned_agent_api(_checkout(tmp_path / "agent", changed), _pin(tmp_path / "pin"))
    assert _COMMIT in str(refused.value)


def test_line_ending_drift_is_refused(tmp_path: Path) -> None:
    with pytest.raises(AgentApiPinError, match="serves another API"):
        require_pinned_agent_api(
            _checkout(tmp_path / "agent", _DOCUMENT.replace(b"\n", b"\r\n")), _pin(tmp_path / "pin")
        )


def test_a_checkout_without_the_document_is_refused(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    with pytest.raises(AgentApiPinError, match=re.escape("has no readable openapi.json")):
        require_pinned_agent_api(tmp_path / "agent", _pin(tmp_path / "pin"))


def test_a_pinned_file_that_does_not_match_its_record_is_refused(tmp_path: Path) -> None:
    pin = _pin(tmp_path / "pin", overrides={"sha256": "f" * 64})
    with pytest.raises(AgentApiPinError, match="does not hash to the sha256"):
        require_pinned_agent_api(_checkout(tmp_path / "agent"), pin)


@pytest.mark.parametrize(
    ("override", "words"),
    [
        ({"source": "other"}, "not 'cadrumo-agent'"),
        ({"path": "../openapi.json"}, "not one inside the checkout"),
        ({"commit": "0003ac4"}, "full 40-hex commit"),
    ],
)
def test_a_malformed_pin_record_is_refused(tmp_path: Path, override: dict[str, str], words: str) -> None:
    with pytest.raises(AgentApiPinError, match=words):
        require_pinned_agent_api(_checkout(tmp_path / "agent"), _pin(tmp_path / "pin", overrides=override))


def test_a_pin_record_with_extra_keys_is_refused(tmp_path: Path) -> None:
    pin = _pin(tmp_path / "pin")
    record = json.loads((pin / "pin.json").read_text(encoding="utf-8")) | {"note": "x"}
    (pin / "pin.json").write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(AgentApiPinError, match="exactly the text keys"):
        require_pinned_agent_api(_checkout(tmp_path / "agent"), pin)


def test_the_repository_pin_admits_its_own_document() -> None:
    record = json.loads((PIN_DIRECTORY / "pin.json").read_text(encoding="utf-8"))
    mirror = PIN_DIRECTORY / record["path"]
    require_pinned_agent_api(mirror.parent, PIN_DIRECTORY)
