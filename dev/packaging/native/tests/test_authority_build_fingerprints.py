"""Every build republishes a missing or stale authority; a rebuild republishes it unconditionally."""

from __future__ import annotations

import hashlib
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


@pytest.mark.parametrize(
    ("rebuild", "arguments"), [(False, ["publish-authority", "--if-stale"]), (True, ["publish-authority"])]
)
def test_a_build_asks_the_publisher_to_publish_a_missing_or_stale_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rebuild: bool, arguments: list[str]
) -> None:
    root = tmp_path / ".authority"
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(root))
    monkeypatch.setattr(authority_build, "REPO_ROOT", tmp_path)
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        commands.append(command)
        _publication(root)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(authority_build, "run_command", run)
    authority_build.publish(tmp_path, rebuild=rebuild)
    # The publisher decides staleness from the registry sources and compiler;
    # an existing publication never short-circuits a normal build.
    authority_build.publish(tmp_path, rebuild=rebuild)
    assert len(commands) == 2
    assert all(command[-len(arguments) :] == arguments for command in commands)


@pytest.mark.parametrize("rebuild", [False, True])
def test_failed_publication_preserves_existing_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rebuild: bool
) -> None:
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
        authority_build.publish(tmp_path, rebuild=rebuild)
    assert error.value.code == 7
    assert [path.read_bytes() for path in pair] == before
