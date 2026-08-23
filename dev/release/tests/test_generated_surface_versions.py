"""Real-behavior tests for the generated-surface version/digest readiness check.

Builds a minimal cohort carrying the four real generated-surface formats (the
Scoop JSON manifest, the Homebrew Ruby formula, the marketplace plugin JSON
inside its zip, and the stamped manifest inside the ``.mcpb`` bundle) and drives
``check_generated_surface_versions`` end to end - no mocks, real parsing of each
format on disk. Each test mutates one embedded value and asserts the
per-surface failure is named.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from cadrumo.core import iter_directory

from ...packaging.tests._cohort_attestation import make_minimal_test_python_cohort
from ..readiness import check_generated_surface_versions

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WHEEL_CADRUMO = "a" * 64
_WHEEL_MANUALS = "b" * 64
_WHEEL_OFFICIAL = "c" * 64
_SDIST_CADRUMO = "d" * 64


def _cohort(
    root: Path,
    *,
    version: str = "0.2.1",
    scoop_version: str | None = None,
    scoop_hashes: list[str] | None = None,
    homebrew_version: str | None = None,
    homebrew_sha: str | None = None,
    marketplace_version: str | None = None,
    mcpb_version: str | None = None,
) -> Path:
    """Materialise a cohort's version/digest surfaces; any override introduces drift."""
    (root / "python").mkdir(parents=True)
    (root / "scoop").mkdir()
    (root / "homebrew" / "Formula").mkdir(parents=True)
    (root / "claude").mkdir()
    (root / "mcpb").mkdir()

    (root / "release-cohort.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    python_sha = make_minimal_test_python_cohort(root / "python", version=version)
    wheel_cadrumo = python_sha["cadrumo"]
    wheel_manuals = python_sha["cadrumo-data-manuals"]
    wheel_official = python_sha["cadrumo-data-official"]
    sdist_cadrumo = python_sha["cadrumo-sdist"]
    (root / "scoop" / "cadrumo.json").write_text(
        json.dumps(
            {
                "version": scoop_version or version,
                "architecture": {
                    "64bit": {"hash": scoop_hashes or [wheel_cadrumo, wheel_manuals, wheel_official]},
                },
            },
        ),
        encoding="utf-8",
    )
    hv = homebrew_version or version
    hs = homebrew_sha or sdist_cadrumo
    (root / "homebrew" / "Formula" / "cadrumo.rb").write_text(
        "class Cadrumo < Formula\n"
        f'  url "https://github.com/nevenincs/cadrumo/releases/download/v{hv}/cadrumo-{hv}.tar.gz"\n'
        f'  sha256 "{hs}"\n'
        "end\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(root / "claude" / f"cadrumo-marketplace-{version}.zip", "w") as archive:
        archive.writestr(
            "plugins/cadrumo/.claude-plugin/plugin.json",
            json.dumps({"version": marketplace_version or version}),
        )
    with zipfile.ZipFile(root / "mcpb" / f"cadrumo-{version}.mcpb", "w") as archive:
        archive.writestr("manifest.json", json.dumps({"version": mcpb_version or version}))
    return root


def _replace_generated_json_surface(cohort: Path, *, surface: str, payload: object) -> str:
    """Replace one real generated JSON document with an arbitrary parsed JSON shape."""
    encoded = json.dumps(payload)
    if surface == "scoop":
        (cohort / "scoop" / "cadrumo.json").write_text(encoded, encoding="utf-8")
        return "scoop manifest unreadable"
    if surface == "marketplace":
        bundle = next(iter_directory(cohort / "claude", pattern="cadrumo-marketplace-*.zip"))
        with zipfile.ZipFile(bundle, "w") as archive:
            archive.writestr("plugins/cadrumo/.claude-plugin/plugin.json", encoded)
        return "marketplace plugin manifest unreadable"
    if surface == "mcpb":
        bundle = next(iter_directory(cohort / "mcpb", pattern="cadrumo-*.mcpb"))
        with zipfile.ZipFile(bundle, "w") as archive:
            archive.writestr("manifest.json", encoded)
        return "mcpb bundle manifest unreadable"
    raise AssertionError(f"unexpected generated JSON surface: {surface}")


def test_all_surfaces_bind_the_cohort(tmp_path: Path) -> None:
    """A consistent cohort passes: every embedded version + digest equals the cohort."""
    cohort = _cohort(tmp_path / "cohort")
    check = check_generated_surface_versions(tmp_path, cohort_directory=cohort)
    assert check.passed
    assert check.severity == "blocking"


def test_scoop_version_drift_is_named(tmp_path: Path) -> None:
    """A stale Scoop manifest version drifts from the cohort and fails, surface named."""
    cohort = _cohort(tmp_path / "cohort", scoop_version="9.9.9")
    check = check_generated_surface_versions(tmp_path, cohort_directory=cohort)
    assert not check.passed
    assert "scoop version" in check.detail


def test_scoop_digest_drift_is_named(tmp_path: Path) -> None:
    """A Scoop 64bit hash that is not the cohort wheel digest fails, surface named."""
    cohort = _cohort(tmp_path / "cohort", scoop_hashes=["e" * 64, _WHEEL_MANUALS, _WHEEL_OFFICIAL])
    check = check_generated_surface_versions(tmp_path, cohort_directory=cohort)
    assert not check.passed
    assert "scoop 64bit hashes" in check.detail


def test_homebrew_version_and_sha_drift_are_named(tmp_path: Path) -> None:
    """A stale Homebrew formula version and sha256 both drift and are enumerated."""
    cohort = _cohort(tmp_path / "cohort", homebrew_version="8.8.8", homebrew_sha="f" * 64)
    check = check_generated_surface_versions(tmp_path, cohort_directory=cohort)
    assert not check.passed
    assert "homebrew formula stable version" in check.detail
    assert "homebrew formula stable sha256" in check.detail


def test_marketplace_version_drift_is_named(tmp_path: Path) -> None:
    """A stale marketplace plugin.json version drifts from the cohort and fails."""
    cohort = _cohort(tmp_path / "cohort", marketplace_version="7.7.7")
    check = check_generated_surface_versions(tmp_path, cohort_directory=cohort)
    assert not check.passed
    assert "marketplace plugin version" in check.detail


def test_mcpb_stamped_version_drift_is_named(tmp_path: Path) -> None:
    """A ``.mcpb`` bundle whose stamped manifest version drifts from the cohort fails."""
    cohort = _cohort(tmp_path / "cohort", mcpb_version="6.6.6")
    check = check_generated_surface_versions(tmp_path, cohort_directory=cohort)
    assert not check.passed
    assert "mcpb stamped version" in check.detail


@pytest.mark.parametrize("surface", ("scoop", "marketplace", "mcpb"))
@pytest.mark.parametrize("payload", ([], 7))
def test_generated_json_non_object_surface_blocks_readiness(
    tmp_path: Path,
    surface: str,
    payload: object,
) -> None:
    """Real JSON files and bundle members with list/scalar bodies block instead of crashing the gate."""
    cohort = _cohort(tmp_path / "cohort")
    expected_detail = _replace_generated_json_surface(cohort, surface=surface, payload=payload)

    check = check_generated_surface_versions(tmp_path, cohort_directory=cohort)

    assert check.severity == "blocking"
    assert check.passed is False
    assert expected_detail in check.detail


def test_missing_cohort_surfaces_fail_closed(tmp_path: Path) -> None:
    """An absent cohort directory fails closed, never silently passing."""
    check = check_generated_surface_versions(tmp_path, cohort_directory=tmp_path / "absent")
    assert not check.passed
    assert "unreadable" in check.detail
