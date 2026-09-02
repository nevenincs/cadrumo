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


def _focused_test(name: str = "fixture-test", *, status: str = "passed") -> compatibility.FocusedTestEvidence:
    """Build one valid focused-test evidence entry for schema fixtures."""
    return compatibility.FocusedTestEvidence(
        name=name,
        status=status,
        command=compatibility.CommandEvidence.from_result(_command_result(returncode=0)),
    )


def _evidence(*, mode: str, status: str = "passed", dependency_status: str = "resolved") -> compatibility.ProbeEvidence:
    """Build a minimal valid evidence row without invoking a package installer."""
    digest = hashlib.sha256(b"fixture").hexdigest()
    artifact_digests = {"cadrumo": digest}
    dependency = {"status": dependency_status, "detail": "fixture"}
    if mode == "binary":
        artifact_digests["runtime-wheelhouse"] = digest
        dependency.update({"source": "sealed-runtime-wheelhouse", "wheelhouse_platform": "windows-x86-64"})
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
        artifact_digests=artifact_digests,
        source_commit="a" * 40,
        cohort_manifest_sha256=digest if mode == "binary" else None,
        builder_python="3.13.11" if mode == "binary" else None,
        dependency=dependency,
        isolation={"checkout_imports_removed": True, "ambient_product_executables_removed": True},
        commands=(),
        focused_tests=(_focused_test(),) if status == "passed" else (),
        failure={"category": "fixture", "detail": "failed"} if status == "failed" else None,
        observed_at="2026-09-02T00:00:00+00:00",
    )


def _wheelhouse_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    """Create one manifest-shaped wheelhouse row for installer command tests."""
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    filename = "native_dependency-1.0.0-py3-none-any.whl"
    payload = b"sealed dependency wheel"
    (wheelhouse / filename).write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    return wheelhouse, {
        "platforms": {"windows-x86-64": {"native-dependency": filename}},
        "wheels": {
            filename: {
                "distribution": "native-dependency",
                "sha256": digest,
                "size": len(payload),
                "version": "1.0.0",
            }
        },
    }


def test_source_and_binary_modes_are_distinct_json_verdicts() -> None:
    """A source pass cannot be confused with a binary-wheel pass."""
    source = _evidence(mode="source")
    binary = _evidence(mode="binary")

    assert source.to_dict()["mode"] == "source"
    assert binary.to_dict()["mode"] == "binary"
    assert source.to_dict() != binary.to_dict()
    assert json.loads(json.dumps(source.to_dict()))["mode"] == "source"


def test_passing_evidence_requires_focused_runtime_tests() -> None:
    """A green row cannot omit its selected-interpreter behavior evidence."""
    payload = _evidence(mode="source").to_dict()
    payload["focused_tests"] = ()

    with pytest.raises(compatibility.CompatibilityProbeError, match="must include focused runtime tests"):
        compatibility.ProbeEvidence(**payload)


def test_evidence_rejects_skipped_dependency_outcome() -> None:
    """Missing or unexecuted dependency proof cannot be represented as a skip."""
    with pytest.raises(compatibility.CompatibilityProbeError, match="cannot be skipped"):
        _evidence(mode="binary", status="failed", dependency_status="skipped")


def test_binary_missing_wheel_is_a_failed_attributable_outcome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The binary mode reports missing wheels as red evidence, never a successful skip."""
    artifact = tmp_path / "cadrumo-0.2.2-py3-none-any.whl"
    artifact.write_bytes(b"wheel fixture")
    wheelhouse, manifest = _wheelhouse_fixture(tmp_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        compatibility,
        "run_command",
        lambda *args, **kwargs: (
            captured.update(argv=args[0], environment=kwargs["environment"])
            or _command_result(
                returncode=1,
                stderr="No compatible wheel was found for native dependency",
            )
        ),
    )
    monkeypatch.setenv("UV_INDEX_URL", "https://attacker.invalid/simple")
    monkeypatch.setenv("PIP_FIND_LINKS", "https://attacker.invalid/wheels")

    commands, status, detail = compatibility._install(
        "uv",
        repo_root=tmp_path,
        work_dir=tmp_path,
        venv=tmp_path / "venv",
        artifacts=(("cadrumo", artifact),),
        mode=compatibility.ProbeMode.BINARY,
        wheelhouse_dir=wheelhouse,
        wheelhouse_manifest=manifest,
        wheelhouse_platform="windows-x86-64",
    )

    assert commands[0].exit_status == 1
    assert status is compatibility.DependencyStatus.MISSING_WHEEL
    assert detail and "wheel" in detail.lower()
    assert status.value != "skipped"
    argv = captured["argv"]
    assert isinstance(argv, tuple)
    assert "--offline" in argv
    assert "--no-index" in argv
    assert "--require-hashes" in argv
    assert argv[argv.index("--find-links") + 1] == str(wheelhouse.resolve())
    assert any("native-dependency @ file:" in item and "#sha256=" in item for item in argv)
    environment = captured["environment"]
    assert isinstance(environment, dict)
    assert "UV_INDEX_URL" not in environment
    assert "PIP_FIND_LINKS" not in environment


def test_binary_install_refuses_to_run_without_a_sealed_wheelhouse(tmp_path: Path) -> None:
    """Binary mode cannot silently fall back to the package index."""
    artifact = tmp_path / "cadrumo-0.2.2-py3-none-any.whl"
    artifact.write_bytes(b"wheel fixture")

    with pytest.raises(compatibility.CompatibilityProbeError, match="extracted sealed runtime wheelhouse"):
        compatibility._install(
            "uv",
            repo_root=tmp_path,
            work_dir=tmp_path,
            venv=tmp_path / "venv",
            artifacts=(("cadrumo", artifact),),
            mode=compatibility.ProbeMode.BINARY,
        )


def test_binary_install_refuses_drifted_wheelhouse_bytes(tmp_path: Path) -> None:
    """A substituted dependency wheel is rejected before the installer runs."""
    wheelhouse, manifest = _wheelhouse_fixture(tmp_path)
    (wheelhouse / "native_dependency-1.0.0-py3-none-any.whl").write_bytes(b"substituted")

    with pytest.raises(compatibility.CompatibilityProbeError, match="wheel bytes drifted"):
        compatibility._binary_wheel_targets(
            wheelhouse,
            manifest,
            platform_target="windows-x86-64",
        )


@pytest.mark.parametrize(
    ("stderr", "expected"),
    (
        ("No compatible wheel was found for native dependency", compatibility.DependencyStatus.MISSING_WHEEL),
        ("wheel metadata verification failed after download", compatibility.DependencyStatus.FAILED),
        ("the local wheel was installed but its hash did not verify", compatibility.DependencyStatus.FAILED),
    ),
)
def test_binary_install_failure_taxonomy_is_not_triggered_by_the_word_wheel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
    expected: compatibility.DependencyStatus,
) -> None:
    """Only resolver diagnostics, not arbitrary wheel prose, mean missing-wheel."""
    artifact = tmp_path / "cadrumo-0.2.2-py3-none-any.whl"
    artifact.write_bytes(b"wheel fixture")
    monkeypatch.setattr(
        compatibility,
        "run_command",
        lambda *_args, **_kwargs: _command_result(returncode=1, stderr=stderr),
    )
    monkeypatch.setattr(compatibility, "_binary_wheel_targets", lambda *_args, **_kwargs: ())

    _commands, status, _detail = compatibility._install(
        "uv",
        repo_root=tmp_path,
        work_dir=tmp_path,
        venv=tmp_path / "venv",
        artifacts=(("cadrumo", artifact),),
        mode=compatibility.ProbeMode.BINARY,
        wheelhouse_dir=tmp_path,
        wheelhouse_manifest={},
        wheelhouse_platform="linux-x86-64",
    )

    assert status is expected


def test_focused_runtime_tests_are_target_interpreter_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner records both installed-package behavior and MCP help probes."""
    calls: list[tuple[str, ...]] = []

    def fake_run(argv: tuple[str, ...], **_kwargs: object) -> CommandResult:
        calls.append(argv)
        return _command_result(returncode=0, stdout='{"runtime_behavior_ok": true}\nusage: cadrumo-mcp\n')

    monkeypatch.setattr(compatibility, "run_command", fake_run)
    tests, commands, failure = compatibility._focused_runtime_tests(tmp_path / "venv", work_dir=tmp_path)

    assert failure is None
    assert [test.name for test in tests] == ["installed-package-behavior", "installed-cadrumo-mcp-help"]
    assert all(test.status == "passed" for test in tests)
    assert len(commands) == 2
    assert calls[0][0].endswith("python") or calls[0][0].endswith("python.exe")
    assert calls[1][-1] == "--help"


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
