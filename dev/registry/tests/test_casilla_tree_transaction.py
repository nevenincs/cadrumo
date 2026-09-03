"""Detector tests for the reusable whole-casilla transaction boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..pipeline import casilla_tree_transaction as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _tree(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.glob("*.toml")}


def _verify(expected: dict[str, bytes]):
    def verify(root: Path) -> None:
        assert _tree(root) == expected

    return verify


def test_cutover_changes_only_the_predeclared_member(tmp_path: Path) -> None:
    root = tmp_path / "revision" / "casillas"
    root.mkdir(parents=True)
    (root / "c00001.toml").write_bytes(b"old\n")
    (root / "c00002.toml").write_bytes(b"unchanged\n")
    expected = {"c00001.toml": b"new\n", "c00002.toml": b"unchanged\n"}

    subject.publish_verified_casilla_tree(
        casillas_root=root,
        rendered={root / "c00001.toml": "new\n"},
        verifier=_verify(expected),
        journal_name=".journal.json",
        stage_prefix=".stage-",
        backup_prefix=".backup-",
    )

    assert _tree(root) == expected
    assert not (root.parent / ".journal.json").exists()
    assert not tuple(root.parent.glob(".stage-*"))
    assert not tuple(root.parent.glob(".backup-*"))


def test_base_exception_rolls_back_the_whole_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "revision" / "casillas"
    root.mkdir(parents=True)
    (root / "c00001.toml").write_bytes(b"old\n")
    before = _tree(root)
    calls = 0
    real_replace = subject._replace_tree

    class Interrupt(BaseException):
        pass

    def interrupt(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise Interrupt()
        real_replace(source, destination)

    with pytest.raises(Interrupt):
        subject.publish_verified_casilla_tree(
            casillas_root=root,
            rendered={root / "c00001.toml": "new\n"},
            verifier=_verify({"c00001.toml": b"new\n"}),
            journal_name=".journal.json",
            stage_prefix=".stage-",
            backup_prefix=".backup-",
            replace_tree=interrupt,
        )
    assert _tree(root) == before


def test_recovery_restores_an_incomplete_candidate(tmp_path: Path) -> None:
    root = tmp_path / "revision" / "casillas"
    root.mkdir(parents=True)
    (root / "c00001.toml").write_bytes(b"candidate\n")
    backup = root.parent / ".backup-token"
    backup.mkdir()
    (backup / "c00001.toml").write_bytes(b"original\n")
    journal = root.parent / ".journal.json"
    journal.write_text(
        json.dumps({"schema_version": 1, "state": "candidate_live", "stage": ".stage-token", "backup": backup.name}),
        encoding="utf-8",
    )

    def refuse(_root: Path) -> None:
        raise RegistryValidationError("candidate invalid")

    assert subject.recover_verified_casilla_tree(
        casillas_root=root,
        verifier=refuse,
        journal_name=".journal.json",
        stage_prefix=".stage-",
        backup_prefix=".backup-",
    )
    assert _tree(root) == {"c00001.toml": b"original\n"}
    assert not backup.exists()
    assert not journal.exists()


def test_recovery_refuses_a_file_disguised_as_a_backup_without_touching_the_tree(tmp_path: Path) -> None:
    root = tmp_path / "revision" / "casillas"
    root.mkdir(parents=True)
    (root / "c00001.toml").write_bytes(b"original\n")
    backup = root.parent / ".backup-token"
    backup.write_bytes(b"not-a-tree\n")
    journal = root.parent / ".journal.json"
    journal.write_text(
        json.dumps({"schema_version": 1, "state": "backup_staged", "stage": ".stage-token", "backup": backup.name}),
        encoding="utf-8",
    )
    before = _tree(root)

    with pytest.raises(RegistryValidationError, match="recovery backup tree must be a non-linked directory"):
        subject.recover_verified_casilla_tree(
            casillas_root=root,
            verifier=lambda _root: None,
            journal_name=".journal.json",
            stage_prefix=".stage-",
            backup_prefix=".backup-",
        )
    assert _tree(root) == before
    assert backup.read_bytes() == b"not-a-tree\n"
    assert journal.exists()


def test_recovery_refuses_an_invalid_live_candidate_without_backup(tmp_path: Path) -> None:
    root = tmp_path / "revision" / "casillas"
    root.mkdir(parents=True)
    (root / "c00001.toml").write_bytes(b"candidate\n")
    journal = root.parent / ".journal.json"
    journal.write_text(
        json.dumps(
            {"schema_version": 1, "state": "candidate_live", "stage": ".stage-token", "backup": ".backup-token"}
        ),
        encoding="utf-8",
    )
    before = _tree(root)

    def refuse(_root: Path) -> None:
        raise RegistryValidationError("candidate invalid")

    with pytest.raises(RegistryValidationError, match="invalid candidate without backup"):
        subject.recover_verified_casilla_tree(
            casillas_root=root,
            verifier=refuse,
            journal_name=".journal.json",
            stage_prefix=".stage-",
            backup_prefix=".backup-",
        )
    assert _tree(root) == before
    assert journal.exists()


def test_external_workspace_keeps_all_transaction_artifacts_out_of_the_revision(tmp_path: Path) -> None:
    root = tmp_path / "revision" / "casillas"
    workspace = tmp_path / "publisher-workspace"
    root.mkdir(parents=True)
    workspace.mkdir()
    (root / "c00001.toml").write_bytes(b"old\n")

    subject.publish_verified_casilla_tree(
        casillas_root=root,
        rendered={root / "c00001.toml": "new\n"},
        verifier=_verify({"c00001.toml": b"new\n"}),
        journal_name=".journal.json",
        stage_prefix=".stage-",
        backup_prefix=".backup-",
        transaction_root=workspace,
    )

    assert not tuple(root.parent.glob(".stage-*"))
    assert not tuple(root.parent.glob(".backup-*"))
    assert not tuple(root.parent.glob(".journal.json"))
    assert not tuple(workspace.iterdir())


@pytest.mark.parametrize(
    ("keyword", "value"),
    (("journal_name", "../escaped.json"), ("stage_prefix", "../stage-"), ("backup_prefix", "dir\\backup-")),
)
def test_transaction_artifact_components_cannot_escape_the_workspace(
    tmp_path: Path, keyword: str, value: str
) -> None:
    root = tmp_path / "revision" / "casillas"
    workspace = tmp_path / "workspace"
    root.mkdir(parents=True)
    workspace.mkdir()
    (root / "c00001.toml").write_bytes(b"old\n")
    arguments: dict[str, object] = {
        "casillas_root": root,
        "rendered": {root / "c00001.toml": "new\n"},
        "verifier": _verify({"c00001.toml": b"new\n"}),
        "journal_name": ".journal.json",
        "stage_prefix": ".stage-",
        "backup_prefix": ".backup-",
        "transaction_root": workspace,
    }
    arguments[keyword] = value

    with pytest.raises(RegistryValidationError, match="single path component"):
        subject.publish_verified_casilla_tree(**arguments)  # type: ignore[arg-type]
    assert _tree(root) == {"c00001.toml": b"old\n"}
    assert not tuple(workspace.iterdir())
