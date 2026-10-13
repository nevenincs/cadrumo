"""Exercise the private wheel's source identity and checksum admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ..agent import agent_wheel

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def wheel_tree(root: Path) -> Path:
    """Create an independently hashed build receipt for an inert wheel payload."""
    wheels = root / "wheels"
    wheels.mkdir()
    wheel = wheels / "cadrumo_agent-0.1.0-py3-none-any.whl"
    payload = b"agent wheel admission fixture"
    wheel.write_bytes(payload)
    record = dict(
        source="configured-folder", version="0.1.0", wheel=wheel.name, wheel_sha256=hashlib.sha256(payload).hexdigest()
    )
    (root / "agent-wheel.json").write_text(json.dumps(record), encoding="utf-8")
    return wheel


def test_built_agent_wheel_is_admitted(tmp_path: Path) -> None:
    """A matching source identity and wheel checksum resolves the built artifact."""
    wheel = wheel_tree(tmp_path)
    assert agent_wheel(tmp_path) == wheel


def test_changed_wheel_is_refused(tmp_path: Path) -> None:
    """Changing bytes after construction cannot reuse the wheel receipt."""
    wheel = wheel_tree(tmp_path)
    wheel.write_bytes(b"changed after build")
    with pytest.raises(ValueError, match="checksum mismatch"):
        agent_wheel(tmp_path)


@pytest.mark.parametrize("name", ["../outside.whl", "wheels/other.whl", "payload.txt"])
def test_wheel_receipt_cannot_select_another_path(tmp_path: Path, name: str) -> None:
    """An altered receipt cannot escape its declared wheel directory."""
    wheel_tree(tmp_path)
    receipt = tmp_path / "agent-wheel.json"
    record = json.loads(receipt.read_text(encoding="utf-8"))
    record["wheel"] = name
    receipt.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid agent wheel path"):
        agent_wheel(tmp_path)
