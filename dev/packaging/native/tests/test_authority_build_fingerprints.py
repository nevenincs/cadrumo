"""Native builds admit registry publications without becoming authoring commands."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

from .. import authority_build

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _publication(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    payload = b"published authority fixture"
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


@pytest.mark.parametrize("current", [False, True])
def test_authority_admission_never_republishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, current: bool) -> None:
    root = tmp_path / ".authority"
    pair = _publication(root)
    build = tmp_path / "build"
    build.mkdir()
    (build / "build-paths.json").write_text(json.dumps({"paths": {"generated": "generated"}}))
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(root))
    monkeypatch.setattr(authority_build, "REPO_ROOT", tmp_path)
    admitted: list[Path] = []

    def currency(descriptor: Path, **kwargs: Path) -> SimpleNamespace:
        admitted.append(descriptor)
        assert kwargs["registry_root"] == tmp_path / "src/cadrumo/_data/registry/aeat"
        return SimpleNamespace(is_current=current, detail="sources changed")

    monkeypatch.setattr(authority_build, "authority_database_currency", currency)
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    if current:
        authority_build.publish(build)
    else:
        with pytest.raises(SystemExit, match="registry-publish-authority"):
            authority_build.publish(build)
    assert admitted == [pair[0]]
    assert before == {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}


def test_missing_publication_reports_the_explicit_authoring_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build-paths.json").write_text(json.dumps({"paths": {}}))
    missing = tmp_path / "missing"
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(missing))
    with pytest.raises(SystemExit, match="registry-publish-authority"):
        authority_build.publish(tmp_path)
    assert not missing.exists()
