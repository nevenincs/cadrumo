"""The authority-artifact currency gate refuses a stale publication and accepts a fresh one.

Every case runs on an isolated temporary registry and source tree: the artifact
is written through the real writer, read back through the real runtime reader,
and judged against the identity the publisher derives for the live inputs.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cadrumo.domain.calculations.registry.authority_artifact import AuthorityArtifact, write_authority_artifact
from cadrumo.domain.calculations.registry.tests._referential_integrity_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)
from dev.registry.conformance.cli import app as conformance_app

from ..pipeline.authority_publication import (
    AuthorityArtifactCurrencyStatus,
    authority_artifact_currency,
    authority_candidate_identity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REVISION_TOML = 'id = "2025"\nvalid_from = 2025-01-01\n'


def _stage_inputs(root: Path) -> tuple[Path, Path]:
    """Lay out a small registry and source-evidence tree with LF line endings."""
    registry_root = root / "registry" / "aeat"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (registry_root / "modelos" / "999" / "manifest.toml").write_bytes(b'[modelo]\nid = "999"\n')
    (revision_dir / "revision.toml").write_bytes(_REVISION_TOML.encode())
    evidence_dir = root / "corpus" / "test"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "ley.html").write_bytes(b"<html>provision text</html>\r\n")
    return registry_root, root


def _publish(artifact_path: Path, identity_digest: str) -> None:
    """Write an artifact recording ``identity_digest`` through the real writer."""
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(minimal_modelo(minimal_revision()),),
            catalogues=minimal_catalogues(),
            identity_digest=identity_digest,
        ),
    )


def _fresh_publication(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Stage inputs and publish an artifact recording their live identity."""
    registry_root, source_root = _stage_inputs(tmp_path / "candidate")
    artifact_path = tmp_path / "published" / "authority.json"
    artifact_path.parent.mkdir()
    _publish(artifact_path, authority_candidate_identity(registry_root=registry_root, source_root=source_root))
    return registry_root, source_root, artifact_path


def _status(artifact_path: Path, registry_root: Path, source_root: Path) -> AuthorityArtifactCurrencyStatus:
    return authority_artifact_currency(artifact_path, registry_root=registry_root, source_root=source_root).status


def test_an_artifact_published_from_the_live_inputs_is_current(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)

    currency = authority_artifact_currency(artifact_path, registry_root=registry_root, source_root=source_root)

    assert currency.is_current
    assert currency.recorded_identity_digest == currency.candidate_identity_digest


def test_a_registry_edit_after_publication_makes_the_artifact_stale(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    revision = registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    revision.write_bytes(revision.read_bytes().replace(b"2025-01-01", b"2025-01-02"))

    currency = authority_artifact_currency(artifact_path, registry_root=registry_root, source_root=source_root)

    assert currency.status is AuthorityArtifactCurrencyStatus.STALE
    assert currency.recorded_identity_digest != currency.candidate_identity_digest


def test_a_same_size_registry_edit_with_its_timestamp_restored_is_still_stale(tmp_path: Path) -> None:
    """The identity is content-addressed, so a stat-preserving edit cannot hide."""
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    revision = registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    before = revision.stat()
    revision.write_bytes(revision.read_bytes().replace(b'"2025"', b'"2026"'))
    os.utime(revision, ns=(before.st_atime_ns, before.st_mtime_ns))

    assert revision.stat().st_size == before.st_size
    assert _status(artifact_path, registry_root, source_root) is AuthorityArtifactCurrencyStatus.STALE


def test_a_source_evidence_edit_after_publication_makes_the_artifact_stale(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    (source_root / "corpus" / "test" / "ley.html").write_bytes(b"<html>amended provision</html>\r\n")

    assert _status(artifact_path, registry_root, source_root) is AuthorityArtifactCurrencyStatus.STALE


def test_a_planted_artifact_recording_another_candidate_is_stale(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    _publish(artifact_path, "0" * 64)

    assert _status(artifact_path, registry_root, source_root) is AuthorityArtifactCurrencyStatus.STALE


def test_an_identical_checkout_elsewhere_derives_the_recorded_identity(tmp_path: Path) -> None:
    """A clone at another absolute path, with fresh timestamps, agrees with the publisher."""
    _registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    clone = tmp_path / "elsewhere" / "clone"
    shutil.copytree(source_root, clone)

    assert _status(artifact_path, clone / "registry" / "aeat", clone) is AuthorityArtifactCurrencyStatus.CURRENT


def test_registry_line_endings_and_working_tree_byproducts_do_not_change_the_identity(tmp_path: Path) -> None:
    """A CRLF working copy of the LF registry, a lock sidecar and bytecode are not candidate changes."""
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    revision = registry_root / "modelos" / "999" / "revisions" / "2025" / "revision.toml"
    revision.write_bytes(revision.read_bytes().replace(b"\n", b"\r\n"))
    (registry_root / ".generated-export-transaction-999-2025.lock").write_bytes(b"")
    (registry_root / "modelos" / "999" / "__pycache__").mkdir()
    (registry_root / "modelos" / "999" / "__pycache__" / "x.cpython-313.pyc").write_bytes(b"\x00")
    (source_root / "corpus" / "test" / "ley.html.lock").write_bytes(b"")

    assert _status(artifact_path, registry_root, source_root) is AuthorityArtifactCurrencyStatus.CURRENT


def test_source_evidence_line_endings_are_byte_exact(tmp_path: Path) -> None:
    """Legal evidence is digested raw: a line-ending translation is a real evidence change."""
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    evidence = source_root / "corpus" / "test" / "ley.html"
    evidence.write_bytes(evidence.read_bytes().replace(b"\r\n", b"\n"))

    assert _status(artifact_path, registry_root, source_root) is AuthorityArtifactCurrencyStatus.STALE


def test_a_missing_or_superseded_artifact_is_unreadable_rather_than_current(tmp_path: Path) -> None:
    registry_root, source_root, artifact_path = _fresh_publication(tmp_path)
    missing = authority_artifact_currency(
        tmp_path / "absent.json", registry_root=registry_root, source_root=source_root
    )
    frame = json.loads(artifact_path.read_bytes())
    frame["schema_version"] = "cadrumo-authority-artifact-v2"
    artifact_path.write_text(json.dumps(frame), encoding="utf-8")
    superseded = authority_artifact_currency(artifact_path, registry_root=registry_root, source_root=source_root)

    assert missing.status is AuthorityArtifactCurrencyStatus.UNREADABLE
    assert "AuthorityArtifactUnavailableError" in missing.detail
    assert superseded.status is AuthorityArtifactCurrencyStatus.UNREADABLE
    assert "cadrumo-authority-artifact-v2" in superseded.detail
    assert missing.recorded_identity_digest is None


def test_the_integrity_gate_refuses_a_stale_artifact_on_stderr_before_compiling(tmp_path: Path) -> None:
    """The planted stale copy fails the owning gate with exit 1; the registry is never compiled."""
    registry_root, source_root, _artifact_path = _fresh_publication(tmp_path)
    stale = tmp_path / "published" / "stale-authority.json"
    _publish(stale, "0" * 64)

    result = CliRunner().invoke(
        conformance_app,
        [
            "integrity",
            "--json",
            "--registry-root",
            str(registry_root),
            "--source-root",
            str(source_root),
            "--authority-artifact",
            str(stale),
        ],
    )

    assert result.exit_code == 1, result.output
    assert result.stdout == ""
    refusal = json.loads(result.stderr)
    assert refusal["status"] == "refused"
    assert refusal["currency"] == "stale"
    assert refusal["recorded_identity_digest"] == "0" * 64
    assert refusal["candidate_identity_digest"] == authority_candidate_identity(
        registry_root=registry_root, source_root=source_root
    )
    assert refusal["republish_with"] == "python -m dev.registry.pipeline publish-authority"
