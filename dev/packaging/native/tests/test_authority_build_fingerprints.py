"""Normal builds select existing authority; republication is explicit."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor, AuthorityStoreError

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


@pytest.mark.parametrize("missing", ["descriptor", "database"])
def test_missing_publication_compiles_once_and_explicit_rebuild_always_compiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    root = tmp_path / ".authority"
    descriptor, database = _publication(root)
    (descriptor if missing == "descriptor" else database).unlink()
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(root))
    monkeypatch.setattr(authority_build, "REPO_ROOT", tmp_path)
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        commands.append(command)
        _publication(root)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(authority_build, "run_command", run)
    authority_build.publish(tmp_path)
    assert len(commands) == 1
    stamp = descriptor.stat().st_mtime_ns
    # These inputs no longer participate in the build's publication decision.
    (tmp_path / "compiler.py").write_text("changed compiler", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("changed dependencies", encoding="utf-8")
    authority_build.publish(tmp_path)
    assert len(commands) == 1
    assert descriptor.stat().st_mtime_ns == stamp
    authority_build.publish(tmp_path, rebuild=True)
    assert len(commands) == 2
    assert all(command[-1] == "publish-authority" for command in commands)


def test_malformed_existing_descriptor_is_not_silently_republished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / ".authority"
    descriptor, _ = _publication(root)
    descriptor.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(root))
    with pytest.raises(AuthorityStoreError, match="unexpected or missing members"):
        authority_build.publish(tmp_path)
    assert descriptor.read_text(encoding="utf-8") == "{}"


def test_failed_explicit_publication_preserves_existing_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / ".authority"
    pair = _publication(root)
    before = [path.read_bytes() for path in pair]
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(root))
    monkeypatch.setattr(
        authority_build,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(returncode=7, stdout="", stderr="refused"),
    )
    with pytest.raises(SystemExit) as error:
        authority_build.publish(tmp_path, rebuild=True)
    assert error.value.code == 7
    assert [path.read_bytes() for path in pair] == before
