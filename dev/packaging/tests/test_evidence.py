"""Real filesystem tests for packaging-smoke evidence checkpointing."""

from __future__ import annotations

import json

import pytest

from dev.packaging.evidence import checkpoint_smoke_evidence
from dev.packaging.smoke_core import _write_smoke_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_checkpoint_copies_manifest_without_traversing_secure_runtime(tmp_path) -> None:
    """The checkpoint reads the known manifest leaf, not protected runtime descendants."""
    smoke_root = tmp_path / "packaging-smoke"
    work_dir = smoke_root / "docker-core-20260715T214242Z"
    secrets_dir = work_dir / "profile-root" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "encrypted.bin").write_bytes(b"ciphertext")
    (secrets_dir / "packaging-smoke-manifest.json").write_text("not-json", encoding="utf-8")
    manifest = _write_smoke_manifest(
        work_dir,
        lane="docker-core",
        artifacts={"wheel": "wheel/cadrumo.whl"},
        checks=("clean Linux container install",),
    )
    evidence_root = tmp_path / "packaging-smoke-evidence"

    checkpointed = checkpoint_smoke_evidence(smoke_root, evidence_root, prune_completed=False)

    assert checkpointed == (evidence_root / "docker-core-20260715T214242Z.json",)
    assert json.loads(checkpointed[0].read_text(encoding="utf-8")) == json.loads(manifest.read_text(encoding="utf-8"))
    assert secrets_dir.is_dir()


def test_checkpoint_prunes_only_completed_work_directories(tmp_path) -> None:
    """Successful runtime trees are released while incomplete diagnostic state remains."""
    smoke_root = tmp_path / "packaging-smoke"
    completed = smoke_root / "browser-20260715T214000Z"
    incomplete = smoke_root / "docker-browser-20260715T214500Z"
    completed.mkdir(parents=True)
    incomplete.mkdir(parents=True)
    (completed / "large-browser-payload.bin").write_bytes(b"browser-cache")
    (incomplete / "failure.log").write_text("ENOSPC\n", encoding="utf-8")
    _write_smoke_manifest(
        completed,
        lane="browser-extra",
        artifacts={"wheel": "wheel/cadrumo.whl"},
        checks=("localhost browser health smoke",),
    )
    evidence_root = tmp_path / "packaging-smoke-evidence"

    checkpointed = checkpoint_smoke_evidence(smoke_root, evidence_root, prune_completed=True)

    assert checkpointed == (evidence_root / "browser-20260715T214000Z.json",)
    assert not completed.exists()
    assert (incomplete / "failure.log").read_text(encoding="utf-8") == "ENOSPC\n"
