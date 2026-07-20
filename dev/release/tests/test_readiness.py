"""Real-behavior tests for the release audit-state readiness gate.

Every check is exercised against real files on a real ``tmp_path`` tree; the
network-dependent check (`check_no_open_release_blockers`) is exercised via
a real `subprocess.run` call against a real, explicit-path probe `gh` script
(no PATH/PATHEXT resolution games), so the process-boundary behavior under
test is genuine.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var

from .. import readiness

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_project(project_file: Path, *, name: str, version: str) -> None:
    project_file.parent.mkdir(parents=True, exist_ok=True)
    project_file.write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n', encoding="utf-8")


def _write_pyprojects(root: Path, version: str) -> None:
    root_project = root / "pyproject.toml"
    _write_project(root_project, name="cadrumo", version=version)
    root_project.write_text(
        root_project.read_text(encoding="utf-8")
        + f'dependencies = ["cadrumo-data-manuals=={version}", "cadrumo-data-official=={version}"]\n',
        encoding="utf-8",
    )
    _write_project(
        root / "packaging" / "cadrumo_data_manuals" / "pyproject.toml",
        name="cadrumo-data-manuals",
        version=version,
    )
    _write_project(
        root / "packaging" / "cadrumo_data_official" / "pyproject.toml",
        name="cadrumo-data-official",
        version=version,
    )


def _write_init(root: Path, version: str) -> None:
    init_dir = root / "src" / "cadrumo"
    init_dir.mkdir(parents=True, exist_ok=True)
    (init_dir / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")


def _write_manifest(root: Path, version: str) -> None:
    (root / ".release-please-manifest.json").write_text(json.dumps({".": version}), encoding="utf-8")


def _write_mcpb_manifest(root: Path, version: str) -> None:
    manifest_dir = root / "packaging" / "mcpb"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": version,
                "server": {
                    "mcp_config": {
                        "command": "uvx",
                        "args": ["--from", f"cadrumo[agent]=={version}", "cadrumo-mcp"],
                    },
                },
            },
        ),
        encoding="utf-8",
    )


def _make_repo_root(tmp_path: Path, *, version: str = "1.2.3") -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _write_pyprojects(root, version)
    _write_init(root, version)
    _write_manifest(root, version)
    _write_mcpb_manifest(root, version)
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.2.3] - 2026-07-04\n\n### Features\n- thing\n", encoding="utf-8"
    )
    return root


def test_version_surfaces_agree_passes_when_all_release_authorities_match(tmp_path: Path) -> None:
    """A repo where every version authority and companion pin agrees passes."""
    root = _make_repo_root(tmp_path, version="2.0.0")

    check = readiness.check_version_surfaces_agree(root)

    assert check.severity == "blocking"
    assert check.passed is True
    assert "2.0.0" in check.detail


def test_version_surfaces_agree_fails_when_the_mcpb_bundle_pin_is_stale(tmp_path: Path) -> None:
    """A stale ``.mcpb`` version or uvx self-install pin reds the release parity gate.

    Enrolling the Desktop-Extension bundle in this gate means a release bump that
    updates every other surface but leaves the bundle pinned to the prior release
    (so the bundle would self-install a stale ``cadrumo[agent]``) fails loudly.
    """
    root = _make_repo_root(tmp_path, version="2.0.0")
    # Bump every other release surface to 2.1.0, leaving the mcpb bundle at 2.0.0.
    _write_pyprojects(root, "2.1.0")
    _write_init(root, "2.1.0")
    _write_manifest(root, "2.1.0")

    check = readiness.check_version_surfaces_agree(root)

    assert check.passed is False
    assert "mcpb='2.0.0'" in check.detail


def test_project_names_are_canonical_for_root_and_both_companions(tmp_path: Path) -> None:
    """The real project files expose the complete accepted Cadrumo distribution tuple."""
    root = _make_repo_root(tmp_path)

    check = readiness.check_project_names_are_canonical(root)

    assert check.passed is True
    assert check.severity == "blocking"
    assert "cadrumo, cadrumo-data-manuals, cadrumo-data-official" in check.detail


@pytest.mark.parametrize(
    ("relative", "former_name"),
    (
        ("pyproject.toml", "aeat-cli"),
        ("packaging/cadrumo_data_manuals/pyproject.toml", "aeat-data-manuals"),
        ("packaging/cadrumo_data_official/pyproject.toml", "aeat-data-official"),
    ),
)
def test_project_names_reject_each_former_product_distribution(
    tmp_path: Path,
    relative: str,
    former_name: str,
) -> None:
    """Any former root or companion distribution name is a blocking release defect."""
    root = _make_repo_root(tmp_path)
    _write_project(root / relative, name=former_name, version="1.2.3")

    check = readiness.check_project_names_are_canonical(root)

    assert check.passed is False
    assert check.severity == "blocking"
    assert former_name in check.detail
    assert "expected 'cadrumo" in check.detail


def test_version_surfaces_agree_fails_on_drift(tmp_path: Path) -> None:
    """A manifest that drifts from pyproject/init is a real, reproducible failure."""
    root = _make_repo_root(tmp_path, version="2.0.0")
    _write_manifest(root, "1.9.9")

    check = readiness.check_version_surfaces_agree(root)

    assert check.passed is False
    assert "1.9.9" in check.detail
    assert "2.0.0" in check.detail


def test_version_surfaces_agree_fails_on_companion_project_drift(tmp_path: Path) -> None:
    """A companion project version that drifts from the release cohort blocks release."""
    root = _make_repo_root(tmp_path, version="2.0.0")
    _write_project(
        root / "packaging" / "cadrumo_data_manuals" / "pyproject.toml",
        name="cadrumo-data-manuals",
        version="1.9.9",
    )

    check = readiness.check_version_surfaces_agree(root)

    assert check.passed is False
    assert "cadrumo_data_manuals" in check.detail
    assert "1.9.9" in check.detail


def test_version_surfaces_agree_fails_on_nonmatching_mandatory_exact_pin(tmp_path: Path) -> None:
    """A mandatory companion pin that does not name the cohort version blocks release."""
    root = _make_repo_root(tmp_path, version="2.0.0")
    project = root / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8").replace(
            "cadrumo-data-official==2.0.0",
            "cadrumo-data-official==1.9.9",
        ),
        encoding="utf-8",
    )

    check = readiness.check_version_surfaces_agree(root)

    assert check.passed is False
    assert "cadrumo-data-official==1.9.9" in check.detail


def test_version_surfaces_agree_fails_when_a_mandatory_companion_is_missing(tmp_path: Path) -> None:
    """Removing a base dependency cannot recreate the retired slim-only install."""
    root = _make_repo_root(tmp_path, version="2.0.0")
    project = root / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8").replace(
            ', "cadrumo-data-official==2.0.0"',
            "",
        ),
        encoding="utf-8",
    )

    check = readiness.check_version_surfaces_agree(root)

    assert check.passed is False
    assert "cadrumo-data-manuals==2.0.0" in check.detail


def test_changelog_ready_fails_when_missing(tmp_path: Path) -> None:
    """A repo with no CHANGELOG.md fails the blocking check with an actionable message."""
    root = _make_repo_root(tmp_path)
    (root / "CHANGELOG.md").unlink()

    check = readiness.check_changelog_is_ready(root)

    assert check.severity == "blocking"
    assert check.passed is False
    assert "missing" in check.detail


def test_changelog_ready_fails_on_empty_file(tmp_path: Path) -> None:
    """An empty CHANGELOG.md is a real failure distinct from a missing file."""
    root = _make_repo_root(tmp_path)
    (root / "CHANGELOG.md").write_text("", encoding="utf-8")

    check = readiness.check_changelog_is_ready(root)

    assert check.passed is False
    assert "empty" in check.detail


def test_changelog_ready_fails_on_unresolved_merge_markers(tmp_path: Path) -> None:
    """A changelog with a leftover merge-conflict marker is refused, never silently released."""
    root = _make_repo_root(tmp_path)
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n<<<<<<< HEAD\nfoo\n=======\nbar\n>>>>>>> branch\n", encoding="utf-8"
    )

    check = readiness.check_changelog_is_ready(root)

    assert check.passed is False
    assert "merge markers" in check.detail


def test_changelog_ready_passes_on_real_populated_file(tmp_path: Path) -> None:
    """A normally-populated changelog passes cleanly."""
    root = _make_repo_root(tmp_path)

    check = readiness.check_changelog_is_ready(root)

    assert check.passed is True


def test_packaging_smoke_evidence_is_advisory_when_absent(tmp_path: Path) -> None:
    """A fresh checkout with no packaging-smoke run reports advisory, not blocking."""
    root = _make_repo_root(tmp_path)

    check = readiness.check_latest_packaging_smoke_evidence(root)

    assert check.severity == "advisory"
    assert check.passed is False
    assert "no packaging-smoke manifest" in check.detail


def test_packaging_smoke_evidence_reads_the_most_recent_real_manifest(tmp_path: Path) -> None:
    """The gate reads the newest manifest on disk and reports its real ok flag."""
    root = _make_repo_root(tmp_path)
    smoke_dir = root / "var" / "packaging-smoke"

    older = smoke_dir / "core-20260101T000000Z"
    older.mkdir(parents=True)
    (older / "packaging-smoke-manifest.json").write_text(
        json.dumps({"ok": False, "lane": "core-wheel"}), encoding="utf-8"
    )

    newer = smoke_dir / "core-20260702T000000Z"
    newer.mkdir(parents=True)
    (newer / "packaging-smoke-manifest.json").write_text(
        json.dumps({"ok": True, "lane": "core-wheel"}), encoding="utf-8"
    )
    # Ensure a real, distinguishable mtime ordering regardless of filesystem
    # timestamp resolution.
    os.utime(older / "packaging-smoke-manifest.json", (1000, 1000))
    os.utime(newer / "packaging-smoke-manifest.json", (2000, 2000))

    check = readiness.check_latest_packaging_smoke_evidence(root)

    assert check.passed is True
    assert "core-20260702T000000Z" in check.detail


def test_packaging_smoke_evidence_reads_a_pruned_checkpoint(tmp_path: Path) -> None:
    """Release readiness retains the evidence signal after ephemeral runtime pruning."""
    root = _make_repo_root(tmp_path)
    evidence_dir = root / "var" / "packaging-smoke-evidence"
    evidence_dir.mkdir(parents=True)
    checkpoint = evidence_dir / "docker-core-20260715T214242Z.json"
    checkpoint.write_text(json.dumps({"ok": True, "lane": "docker-core"}), encoding="utf-8")

    check = readiness.check_latest_packaging_smoke_evidence(root)

    assert check.passed is True
    assert "docker-core-20260715T214242Z" in check.detail
    assert "lane=docker-core" in check.detail


def _write_probe_gh(bin_dir: Path, *, issues_json: str, exit_code: int = 0) -> Path:
    """Write a real executable `gh` script that emits fixed real process output."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        script = bin_dir / "gh.bat"
        script.write_text(f"@echo off\r\necho {issues_json}\r\nexit /b {exit_code}\r\n", encoding="utf-8")
    else:
        script = bin_dir / "gh"
        script.write_text(f"#!/usr/bin/env bash\necho '{issues_json}'\nexit {exit_code}\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_no_open_release_blockers_passes_with_empty_issue_list(tmp_path: Path) -> None:
    """A real subprocess call to a probe `gh` returning `[]` passes as advisory-clean."""
    bin_dir = tmp_path / "bin"
    script = _write_probe_gh(bin_dir, issues_json="[]")

    check = readiness.check_no_open_release_blockers(gh_executable=str(script))

    assert check.passed is True
    assert check.severity == "advisory"


def test_no_open_release_blockers_blocks_on_real_open_blocker(tmp_path: Path) -> None:
    """A real subprocess call to a probe `gh` returning an open blocker issue is a hard release blocker."""
    bin_dir = tmp_path / "bin"
    payload = json.dumps([{"number": 999, "title": "data loss on export"}])
    script = _write_probe_gh(bin_dir, issues_json=payload)

    check = readiness.check_no_open_release_blockers(gh_executable=str(script))

    assert check.passed is False
    assert check.severity == "blocking"
    assert "#999" in check.detail


def test_no_open_release_blockers_is_advisory_when_gh_unresolvable(tmp_path: Path) -> None:
    """A real environment with no resolvable `gh` binary degrades to a non-blocking advisory."""
    missing = tmp_path / "definitely-not-gh"

    check = readiness.check_no_open_release_blockers(gh_executable=str(missing))

    assert check.passed is False
    assert check.severity == "advisory"
    assert "gh unavailable" in check.detail


def test_no_open_release_blockers_is_advisory_when_gh_not_installed(tmp_path: Path) -> None:
    """When `shutil.which("gh")` genuinely returns None, the check reports a non-blocking advisory."""
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()

    with scoped_env_var("PATH", str(empty_path)):
        check = readiness.check_no_open_release_blockers()

    assert check.passed is False
    assert check.severity == "advisory"
    assert "not found on PATH" in check.detail


def test_build_report_blocks_without_complete_distribution_evidence(tmp_path: Path) -> None:
    """Version parity alone cannot authorize a release with no installed evidence."""
    root = _make_repo_root(tmp_path)

    report = readiness.build_report(root, skip_network=True)

    assert report.ok is False
    # A repo with no built cohort blocks on BOTH cohort-dependent gates: the
    # installed-evidence set and the generated-surface version/digest check.
    assert {check.name for check in report.blocking_failures} == {
        "distribution-evidence-complete",
        "generated-surface-versions",
    }


def test_build_report_blocks_on_a_real_version_drift(tmp_path: Path) -> None:
    """A real version-surface drift propagates to the aggregate report as a blocking failure."""
    root = _make_repo_root(tmp_path)
    _write_manifest(root, "9.9.9")

    report = readiness.build_report(root, skip_network=True)

    assert report.ok is False
    names = {c.name for c in report.blocking_failures}
    assert "version-surfaces-agree" in names


def test_report_to_dict_roundtrips_through_json(tmp_path: Path) -> None:
    """The report's dict form is real JSON-serializable output, not a partial shape."""
    root = _make_repo_root(tmp_path)

    report = readiness.build_report(root, skip_network=True)
    payload = json.loads(json.dumps(report.to_dict()))

    assert payload["ok"] is False
    assert isinstance(payload["checks"], list)
    assert all({"name", "severity", "passed", "detail"} <= set(entry) for entry in payload["checks"])


def test_main_cli_json_contract_blocks_without_distribution_evidence(tmp_path: Path) -> None:
    """The JSON contract exits nonzero when required installed evidence is absent."""
    root = _make_repo_root(tmp_path)
    driver = tmp_path / "drive_readiness.py"
    driver.write_text(
        "import json, sys\n"
        f"sys.path.insert(0, {str(Path(readiness.__file__).parents[2])!r})\n"
        "from dev.release import readiness as r\n"
        f"report = r.build_report({str(root)!r}, skip_network=True)\n"
        "print(json.dumps(report.to_dict()))\n"
        "sys.exit(0 if report.ok else 1)\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(driver)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False


def test_real_repo_root_resolves_and_version_surfaces_currently_agree() -> None:
    """Sanity check against the ACTUAL repository: version surfaces agree today."""
    root = readiness._repo_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / ".release-please-manifest.json").is_file()

    check = readiness.check_version_surfaces_agree(root)

    assert check.passed is True, check.detail
    project_names = readiness.check_project_names_are_canonical(root)
    assert project_names.passed is True, project_names.detail
