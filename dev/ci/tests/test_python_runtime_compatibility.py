"""Detector-teeth tests for the source/binary compatibility runner."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...packaging._command import CommandResult
from .. import python_runtime_compatibility as compatibility

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _command_result(*, returncode: int, stderr: str = "", stdout: str = "") -> CommandResult:
    """Build one real-shaped result for the shared subprocess boundary."""
    started = datetime(2026, 9, 2, tzinfo=UTC)
    return CommandResult(
        argv=("uv", "pip", "install"),
        cwd="C:/probe",
        started_at=started,
        completed_at=started,
        duration_seconds=0.001,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _evidence(*, mode: str, status: str = "passed", dependency_status: str = "resolved") -> compatibility.ProbeEvidence:
    """Build a minimal valid evidence row without invoking a package installer."""
    digest = hashlib.sha256(b"fixture").hexdigest()
    return compatibility.ProbeEvidence(
        schema="cadrumo.python-runtime-compatibility.v1",
        runtime={
            "id": "cp314",
            "selector": "3.14",
            "python": "3.14.7",
            "implementation": "CPython",
            "stability": "stable",
            "platform": "win32",
            "machine": "AMD64",
        },
        mode=mode,
        status=status,
        stability="stable",
        lock_sha256=digest,
        artifact_sha256=digest,
        artifact_digests={"cadrumo": digest},
        source_commit="a" * 40,
        cohort_manifest_sha256=digest if mode == "binary" else None,
        builder_python="3.13.11" if mode == "binary" else None,
        dependency={"status": dependency_status, "detail": "fixture"},
        isolation={"checkout_imports_removed": True, "ambient_product_executables_removed": True},
        commands=(),
        failure={"category": "fixture", "detail": "failed"} if status == "failed" else None,
        observed_at="2026-09-02T00:00:00+00:00",
    )


def test_source_and_binary_modes_are_distinct_json_verdicts() -> None:
    """A source pass cannot be confused with a binary-wheel pass."""
    source = _evidence(mode="source")
    binary = _evidence(mode="binary")

    assert source.to_dict()["mode"] == "source"
    assert binary.to_dict()["mode"] == "binary"
    assert source.to_dict() != binary.to_dict()
    assert json.loads(json.dumps(source.to_dict()))["mode"] == "source"


def test_evidence_rejects_skipped_dependency_outcome() -> None:
    """Missing or unexecuted dependency proof cannot be represented as a skip."""
    with pytest.raises(compatibility.CompatibilityProbeError, match="cannot be skipped"):
        _evidence(mode="binary", status="failed", dependency_status="skipped")


def test_binary_missing_wheel_is_a_failed_attributable_outcome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The binary mode reports missing wheels as red evidence, never a successful skip."""
    artifact = tmp_path / "cadrumo-0.2.2-py3-none-any.whl"
    artifact.write_bytes(b"wheel fixture")

    monkeypatch.setattr(
        compatibility,
        "run_command",
        lambda *_args, **_kwargs: _command_result(
            returncode=1,
            stderr="No compatible wheel was found for native dependency",
        ),
    )

    commands, status, detail = compatibility._install(
        "uv",
        repo_root=tmp_path,
        work_dir=tmp_path,
        venv=tmp_path / "venv",
        artifacts=(("cadrumo", artifact),),
        mode=compatibility.ProbeMode.BINARY,
    )

    assert commands[0].exit_status == 1
    assert status is compatibility.DependencyStatus.MISSING_WHEEL
    assert detail and "wheel" in detail.lower()
    assert status.value != "skipped"


def test_binary_mode_requires_a_cohort_and_returns_failed_evidence(tmp_path: Path) -> None:
    """A binary row without a sealed cohort is an explicit failed row."""
    (tmp_path / "uv.lock").write_text("requires-python = '>=3.13'\n", encoding="utf-8")
    evidence = compatibility.run_probe(
        mode=compatibility.ProbeMode.BINARY,
        python="3.13",
        runtime_id="cp313",
        repo_root=tmp_path,
        work_dir=tmp_path / "work",
        cohort_dir=None,
    )

    assert evidence.status == "failed"
    assert evidence.mode == "binary"
    assert evidence.failure == {
        "category": "cohort-missing",
        "detail": "binary mode requires --cohort-dir",
    }
    assert evidence.dependency["status"] != "skipped"


def test_lock_and_artifact_digests_are_required_lowercase_sha256() -> None:
    """Evidence cannot bind to a mutable or non-digest artifact identity."""
    digest = hashlib.sha256(b"fixture").hexdigest()
    payload = _evidence(mode="source").to_dict()
    payload["lock_sha256"] = "not-a-digest"
    with pytest.raises(compatibility.CompatibilityProbeError, match="lock_sha256"):
        compatibility.ProbeEvidence(**payload)
    assert len(digest) == 64
