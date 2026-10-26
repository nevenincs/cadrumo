"""Native builds admit registry publications without becoming authoring commands."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor
from dev.registry.pipeline import authority_publication

from .. import authority_build
from ..build_stamp import read_record, settle_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _publication(root: Path, payload: bytes = b"published authority fixture") -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    database = root / f"authority-{digest}.sqlite3"
    database.write_bytes(payload)
    descriptor = root / "authority.current.json"
    descriptor.write_bytes(
        AuthorityDescriptor(
            database=database.name, database_size=len(payload), database_sha256=digest, logical_generation="c" * 64
        ).to_bytes()
    )
    return descriptor, database


def _build(tmp_path: Path) -> Path:
    build = tmp_path / "build"
    (build / "generated").mkdir(parents=True)
    (build / "build-paths.json").write_text(json.dumps({"paths": {"generated": "generated"}}))
    (build / "generated/identity.json").write_text(json.dumps({"version": "0.6.0"}))
    (build / "generated/build-freeze.json").write_text(json.dumps({"number": "", "id": "", "date": ""}))
    return build


def _checkout_files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.is_relative_to(root / "build")
    }


@pytest.mark.parametrize("current", [False, True])
def test_authority_admission_never_republishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, current: bool) -> None:
    root = tmp_path / ".authority"
    pair = _publication(root)
    build = _build(tmp_path)
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(root))
    monkeypatch.setattr(authority_build, "REPO_ROOT", tmp_path)
    admitted: list[Path] = []

    def currency(descriptor: Path, **kwargs: Path) -> SimpleNamespace:
        admitted.append(descriptor)
        assert kwargs["registry_root"] == tmp_path / "src/cadrumo/_data/registry/aeat"
        return SimpleNamespace(is_current=current, detail="sources changed")

    monkeypatch.setattr(authority_publication, "authority_database_currency", currency)
    before = _checkout_files(tmp_path)
    if current:
        authority_build.publish(build)
    else:
        with pytest.raises(SystemExit, match="registry-publish-authority"):
            authority_build.publish(build)
    assert admitted == [pair[0]]
    assert before == _checkout_files(tmp_path)
    # Only a passing check is recorded; a stale authority is checked again next time.
    record = read_record(build, authority_build.COMPONENT)
    assert (record is not None and record["state"] == "settled") is current


@pytest.mark.parametrize("change", ["none", "registry", "new-source", "database", "unsettled"])
def test_an_unchanged_authority_is_not_validated_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    root = tmp_path / ".authority"
    _publication(root)
    data = tmp_path / "src/cadrumo/_data"
    registry = data / "registry/aeat/modelos/303/revision.toml"
    registry.parent.mkdir(parents=True)
    registry.write_text("[revision]\nid = 1\n", encoding="utf-8")
    build = _build(tmp_path)
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(root))
    monkeypatch.setattr(authority_build, "REPO_ROOT", tmp_path)
    admitted: list[Path] = []

    def currency(descriptor: Path, **kwargs: Path) -> SimpleNamespace:
        # Stands in for the registry identity computation; the skip decision under test is real.
        admitted.append(descriptor)
        return SimpleNamespace(is_current=True, detail="")

    monkeypatch.setattr(authority_publication, "authority_database_currency", currency)
    authority_build.publish(build)
    assert len(admitted) == 1
    if change == "registry":
        registry.write_text("[revision]\nid = 2\n", encoding="utf-8")
    elif change == "new-source":
        (data / "corpus").mkdir()
        (data / "corpus/new.txt").write_text("evidence\n", encoding="utf-8")
    elif change == "database":
        _publication(root, b"republished authority fixture")
    elif change == "unsettled":
        settle_record(build, authority_build.COMPONENT, settled=False)
    authority_build.publish(build)
    assert len(admitted) == (1 if change == "none" else 2)
