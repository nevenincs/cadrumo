"""Real cohort and archive tests for the secondary Cadrumo MCP Bundle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
from types import ModuleType

import pytest
from dev.packaging.python_cohort import load_python_cohort
from dev.packaging.smoke_core import _build_companion_wheels, _build_wheel, _run
from dev.packaging.smoke_sdist_core import _build_sdist

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_BUILD_PY = Path(__file__).resolve().parents[1] / "build.py"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_build_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_cadrumo_mcpb_build", _BUILD_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BUILD = _load_build_module()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_cohort_manifest(
    cohort_dir: Path,
    *,
    artifacts: dict[str, Path],
    version: str,
) -> None:
    names: dict[str, str] = {}
    digests: dict[str, str] = {}
    for label, artifact in artifacts.items():
        retained = cohort_dir / artifact.name
        if retained.resolve() != artifact.resolve():
            shutil.copy2(artifact, retained)
        names[label] = retained.name
        digests[label] = _sha256(retained)
    git = shutil.which("git")
    assert git is not None
    source_commit = subprocess.run(  # noqa: S603 - resolved Git with fixed repository argv
        [git, "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    (cohort_dir / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": names,
                "sha256": digests,
                "source_commit": source_commit,
                "version": version,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def real_cohort(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the real six-file canonical cohort consumed by the bundle."""
    uv = shutil.which("uv")
    assert uv is not None
    work = tmp_path_factory.mktemp("mcpb-real-cohort")
    cohort_dir = work / "cohort"
    cohort_dir.mkdir()
    root_wheel = _build_wheel(_REPO_ROOT, work, uv)
    manuals_wheel, official_wheel = _build_companion_wheels(_REPO_ROOT, work, uv)
    root_sdist = _build_sdist(_REPO_ROOT, work, uv)
    companion_sdists = work / "companion-sdists"
    _run(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists)],
        cwd=_REPO_ROOT / "packaging" / "cadrumo_data_manuals",
    )
    _run(
        [uv, "build", "--sdist", "--out-dir", str(companion_sdists)],
        cwd=_REPO_ROOT / "packaging" / "cadrumo_data_official",
    )
    manuals_sdist = next(companion_sdists.glob("cadrumo_data_manuals-*.tar.gz"))
    official_sdist = next(companion_sdists.glob("cadrumo_data_official-*.tar.gz"))
    version = tomllib.loads(
        (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
    )["project"]["version"]
    assert isinstance(version, str)
    _write_cohort_manifest(
        cohort_dir,
        artifacts={
            "cadrumo": root_wheel,
            "cadrumo-sdist": root_sdist,
            "cadrumo-data-manuals": manuals_wheel,
            "cadrumo-data-manuals-sdist": manuals_sdist,
            "cadrumo-data-official": official_wheel,
            "cadrumo-data-official-sdist": official_sdist,
        },
        version=version,
    )
    return load_python_cohort(cohort_dir).directory


def _copy_cohort(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    return destination


def _rewrite_digest(cohort_dir: Path, label: str) -> None:
    manifest_path = cohort_dir / "python-cohort.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = cohort_dir / document["artifacts"][label]
    document["sha256"][label] = _sha256(artifact)
    manifest_path.write_text(
        json.dumps(document, sort_keys=True),
        encoding="utf-8",
    )


def test_manifest_declares_only_the_bundle_local_python_runtime() -> None:
    """Unexecuted client/platform rows are not advertised as compatibility."""
    manifest = BUILD.load_manifest()
    assert manifest["manifest_version"] == "0.4"
    server = manifest["server"]
    assert server["type"] == "uv"
    assert server["entry_point"] == "src/server.py"
    assert server["mcp_config"] == {
        "command": "uv",
        "args": ["run", "--directory", "${__dirname}", "src/server.py"],
        "env": {
            "CADRUMO_LOCAL_STORAGE_ROOT": "${user_config.storage_root}",
            "CADRUMO_MCP_PERSONA": "${user_config.persona}",
            "CADRUMO_MCP_SURFACE": "${user_config.surface}",
        },
    }
    assert manifest["user_config"]["storage_root"] == {
        "type": "directory",
        "title": "Cadrumo state directory",
        "description": (
            "Persistent, project-independent local state for the Cadrumo MCP service. "
            "The directory is never adopted from the retired aeat product."
        ),
        "required": True,
    }
    assert manifest["compatibility"] == {
        "runtimes": {"python": ">=3.13,<3.14"},
    }


def test_canonical_cohort_renders_bundle_local_sources(real_cohort: Path) -> None:
    """Every product dependency resolves from its canonical embedded wheel."""
    cohort = BUILD.load_cohort(real_cohort)
    project = tomllib.loads(BUILD.runtime_pyproject(cohort))
    assert project["project"]["dependencies"] == [
        f"cadrumo[agent]=={cohort.version}",
        f"cadrumo-data-manuals=={cohort.version}",
        f"cadrumo-data-official=={cohort.version}",
    ]
    sources = project["tool"]["uv"]["sources"]
    expected = {
        "cadrumo": cohort.root_wheel,
        "cadrumo-data-manuals": cohort.manuals_wheel,
        "cadrumo-data-official": cohort.official_wheel,
    }
    for distribution, wheel in expected.items():
        assert sources[distribution] == {"path": f"artifacts/{wheel.name}"}


def test_build_contains_exact_wheels_and_canonical_digest_binding(
    tmp_path: Path,
    real_cohort: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Archive bytes and launch-time identity come from the canonical manifest."""
    cohort = BUILD.load_cohort(real_cohort)
    bundle = BUILD.build(cohort_dir=real_cohort, dist_dir=tmp_path)
    assert bundle.name == f"cadrumo-{cohort.version}.mcpb"
    expected_wheels = {
        cohort.root_wheel.name: cohort.root_wheel,
        cohort.manuals_wheel.name: cohort.manuals_wheel,
        cohort.official_wheel.name: cohort.official_wheel,
    }
    with zipfile.ZipFile(bundle) as archive:
        assert archive.namelist() == [
            f"artifacts/{cohort.root_wheel.name}",
            f"artifacts/{cohort.manuals_wheel.name}",
            f"artifacts/{cohort.official_wheel.name}",
            "manifest.json",
            "pyproject.toml",
            "src/server.py",
        ]
        for filename, wheel in expected_wheels.items():
            assert archive.read(f"artifacts/{filename}") == wheel.read_bytes()
        manifest = json.loads(archive.read("manifest.json"))
        launcher = archive.read("src/server.py").decode()
    expected_sha256 = {
        name: cohort.sha256[name]
        for name in (
            "cadrumo",
            "cadrumo-data-manuals",
            "cadrumo-data-official",
        )
    }
    env = manifest["server"]["mcp_config"]["env"]
    assert json.loads(env["CADRUMO_MCP_COHORT_SHA256"]) == expected_sha256
    assert env["CADRUMO_MCP_REQUIRED_VERSION"] == cohort.version
    assert env["CADRUMO_LOCAL_STORAGE_ROOT"] == "${user_config.storage_root}"
    assert env["UV_PROJECT_ENVIRONMENT"] == (f"${{__dirname}}/.cadrumo-runtime-{BUILD._runtime_identity(cohort)}")
    assert "distribution(name)" in launcher
    assert 'read_text("direct_url.json")' in launcher
    assert "UNSIGNED; assembly only; client installation unproved" in capsys.readouterr().out


def test_missing_companion_is_rejected_by_the_canonical_validator(
    tmp_path: Path,
    real_cohort: Path,
) -> None:
    """MCPB cannot reinterpret an incomplete retained cohort."""
    candidate = _copy_cohort(real_cohort, tmp_path / "missing")
    cohort = load_python_cohort(candidate)
    cohort.official_wheel.unlink()
    with pytest.raises(BUILD.ManifestError, match="invalid Python cohort"):
        BUILD.load_cohort(candidate)


def test_mixed_companion_identity_is_rejected(
    tmp_path: Path,
    real_cohort: Path,
) -> None:
    """Digest-valid files still fail when a companion declares the wrong product."""
    candidate = _copy_cohort(real_cohort, tmp_path / "mixed")
    document = json.loads(
        (candidate / "python-cohort.json").read_text(encoding="utf-8"),
    )
    manuals = candidate / document["artifacts"]["cadrumo-data-manuals"]
    official = candidate / document["artifacts"]["cadrumo-data-official"]
    shutil.copy2(manuals, official)
    _rewrite_digest(candidate, "cadrumo-data-official")
    with pytest.raises(BUILD.ManifestError, match="identities or versions drifted"):
        BUILD.load_cohort(candidate)


def test_foreign_same_version_bytes_get_a_distinct_runtime_identity(
    tmp_path: Path,
    real_cohort: Path,
) -> None:
    """A second same-version cohort cannot reuse the first cohort's UV runtime."""
    original = BUILD.load_cohort(real_cohort)
    candidate = _copy_cohort(real_cohort, tmp_path / "foreign")
    document = json.loads(
        (candidate / "python-cohort.json").read_text(encoding="utf-8"),
    )
    official = candidate / document["artifacts"]["cadrumo-data-official"]
    with zipfile.ZipFile(official, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("foreign-same-version-byte.txt", "different cohort\n")
    _rewrite_digest(candidate, "cadrumo-data-official")
    foreign = BUILD.load_cohort(candidate)
    assert foreign.version == original.version
    assert foreign.sha256["cadrumo-data-official"] != original.sha256["cadrumo-data-official"]
    assert BUILD._runtime_identity(foreign) != BUILD._runtime_identity(original)
    original_env = BUILD.stamped_manifest(original)["server"]["mcp_config"]["env"]
    foreign_env = BUILD.stamped_manifest(foreign)["server"]["mcp_config"]["env"]
    assert original_env["CADRUMO_MCP_COHORT_SHA256"] != foreign_env["CADRUMO_MCP_COHORT_SHA256"]
    assert original_env["UV_PROJECT_ENVIRONMENT"] != foreign_env["UV_PROJECT_ENVIRONMENT"]


def test_real_check_cli_reports_the_v04_template() -> None:
    """The public check validates the committed secondary-bundle template."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [sys.executable, str(_BUILD_PY), "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "manifest.json valid: cadrumo" in completed.stdout
    assert completed.stderr == ""


def test_mcpb_identity_agrees_with_the_product(real_cohort: Path) -> None:
    """Bundle product names and version agree with installed product authority."""
    from cadrumo import __version__
    from cadrumo.core.product_identity import PRODUCT_IDENTITY

    cohort = BUILD.load_cohort(real_cohort)
    manifest = BUILD.stamped_manifest(cohort)
    assert manifest["version"] == cohort.version == __version__
    assert PRODUCT_IDENTITY.distribution == BUILD._DISTRIBUTIONS[0]
    assert PRODUCT_IDENTITY.companion_distributions == BUILD._DISTRIBUTIONS[1:]
    assert PRODUCT_IDENTITY.mcp_executable == BUILD._CONSOLE_SCRIPT
