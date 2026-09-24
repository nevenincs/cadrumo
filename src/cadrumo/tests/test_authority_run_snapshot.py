"""A test run keeps reading the authority generation that was current when it started."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from .authority_run_snapshot import freeze_authority_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _publish(root: Path, database: str, payload: bytes) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / database).write_bytes(payload)
    (root / "authority.current.json").write_text(json.dumps({"database": database}), encoding="utf-8")


def test_a_publish_after_the_freeze_does_not_reach_the_frozen_root(tmp_path: Path) -> None:
    live = tmp_path / "checkout" / ".authority"
    _publish(live, "authority-first.sqlite3", b"first generation")

    frozen = freeze_authority_root(live, tmp_path / "run")
    _publish(live, "authority-second.sqlite3", b"second generation")
    (live / "authority-first.sqlite3").unlink()

    assert frozen == tmp_path / "run" / ".authority"
    assert json.loads((frozen / "authority.current.json").read_text(encoding="utf-8")) == {
        "database": "authority-first.sqlite3"
    }
    assert (frozen / "authority-first.sqlite3").read_bytes() == b"first generation"
    assert not (frozen / "authority-second.sqlite3").exists()


def test_a_root_that_selects_no_generation_is_not_frozen(tmp_path: Path) -> None:
    live = tmp_path / ".authority"
    live.mkdir()

    assert freeze_authority_root(live, tmp_path / "run") is None
    assert not (tmp_path / "run").exists()


def test_a_descriptor_whose_database_is_gone_refuses_rather_than_freezing_it(tmp_path: Path) -> None:
    live = tmp_path / ".authority"
    _publish(live, "authority-retired.sqlite3", b"retired")
    (live / "authority-retired.sqlite3").unlink()

    with pytest.raises(RuntimeError, match="kept changing"):
        freeze_authority_root(live, tmp_path / "run")

    assert not (tmp_path / "run" / ".authority" / "authority.current.json").exists()


def test_the_run_under_test_reads_a_frozen_copy_of_the_checkout_authority() -> None:
    configured = Path(os.environ["CADRUMO_AUTHORITY_ROOT"])
    checkout_root = Path(__file__).resolve().parents[3] / ".authority"
    if not (checkout_root / "authority.current.json").is_file():
        pytest.skip("this checkout has no published authority to freeze")

    assert configured.name == ".authority"
    assert configured.resolve() != checkout_root
    assert (configured / "authority.current.json").is_file()
