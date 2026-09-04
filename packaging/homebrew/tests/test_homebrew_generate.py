"""Real-artifact tests for the generated Cadrumo Homebrew tap snapshot."""

from __future__ import annotations

import json
import re
import shutil
import sys
import tomllib
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from dev.packaging._hashing import sha256_path
from dev.packaging._smoke_common import (
    build_companion_wheels,
    build_sdist,
    build_wheel,
    commit_defined_build_root,
    run_checked,
)
from dev.packaging.python_cohort import _attest_installed_command_specs

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_INDEX_SOURCE = "https://files.pythonhosted.org/packages/source/c"
_GENERATOR = _REPO_ROOT / "packaging" / "homebrew" / "generate.py"
_RESOURCE = re.compile(
    r'\s+resource "([^"]+)" do\n'
    r'\s+url "([^"]+)"\n'
    r'\s+sha256 "([0-9a-f]{64})"\n'
    r"\s+end",
)


@dataclass(frozen=True)
class BuiltCohort:
    """One real sdist-and-companion cohort shared by formula tests."""

    directory: Path
    root: Path
    manuals: Path
    official: Path
    version: str


@pytest.fixture(scope="module")
def built_cohort(tmp_path_factory: pytest.TempPathFactory) -> BuiltCohort:
    """Build the real root and companion source distributions."""
    uv = shutil.which("uv")
    assert uv is not None
    root_dir = tmp_path_factory.mktemp("homebrew-cohort")
    build_dir = root_dir / "build"
    # Build from a commit-defined root, not the working tree: in the shared
    # worktree a peer's uncommitted edit would otherwise ride into the sdist,
    # and the formula this test asserts on would describe bytes matching no
    # commit. On a clean checkout this IS the tree, so CI pays nothing.
    build_root = commit_defined_build_root(_REPO_ROOT, build_dir)
    root = build_sdist(build_dir, uv, build_root=build_root)
    companion_dir = build_dir / "companions"
    manuals_project = build_root / "packaging" / "cadrumo_data_manuals"
    official_project = build_root / "packaging" / "cadrumo_data_official"
    run_checked([uv, "build", "--sdist", "--out-dir", str(companion_dir)], cwd=manuals_project)
    run_checked([uv, "build", "--sdist", "--out-dir", str(companion_dir)], cwd=official_project)
    manuals = next(companion_dir.glob("cadrumo_data_manuals-*.tar.gz"))
    official = next(companion_dir.glob("cadrumo_data_official-*.tar.gz"))
    cohort = root_dir / "cohort"
    cohort.mkdir()
    copied = []
    for artifact in (root, manuals, official):
        target = cohort / artifact.name
        shutil.copy2(artifact, target)
        copied.append(target)
    root_wheel = build_wheel(_REPO_ROOT, build_dir / "wheels", uv, build_root=build_root)
    companion_wheels = build_companion_wheels(build_dir / "wheels", uv, build_root=build_root)
    copied_wheels = []
    for artifact in (root_wheel, *companion_wheels):
        target = cohort / artifact.name
        shutil.copy2(artifact, target)
        copied_wheels.append(target)
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    artifacts = {
        "cadrumo": copied_wheels[0].name,
        "cadrumo-sdist": copied[0].name,
        "cadrumo-data-manuals": copied_wheels[1].name,
        "cadrumo-data-manuals-sdist": copied[1].name,
        "cadrumo-data-official": copied_wheels[2].name,
        "cadrumo-data-official-sdist": copied[2].name,
    }
    source_archive = cohort / f"cadrumo-source-{'a' * 40}.zip"
    with zipfile.ZipFile(source_archive, "w") as archive:
        archive.writestr("pyproject.toml", "[project]\nname='cadrumo'\n")
    artifacts["source-archive"] = source_archive.name
    (cohort / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": artifacts,
                "sha256": {name: sha256_path(cohort / filename) for name, filename in artifacts.items()},
                "source_commit": "a" * 40,
                "version": version,
                "command_spec_attestation": _attest_installed_command_specs(
                    copied_wheels[0],
                    copied[0],
                    "a" * 40,
                    source_archive,
                    work_root=root_dir,
                    uv=uv,
                ),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return BuiltCohort(
        directory=cohort,
        root=copied[0],
        manuals=copied[1],
        official=copied[2],
        version=version,
    )


def _generate(cohort: BuiltCohort, output: Path) -> Path:
    run_checked(
        [
            sys.executable,
            str(_GENERATOR),
            "--cohort-dir",
            str(cohort.directory),
            "--lock",
            str(_REPO_ROOT / "uv.lock"),
            "--version",
            cohort.version,
            "--output-dir",
            str(output),
        ],
        cwd=_REPO_ROOT,
    )
    return output / "Formula" / "cadrumo.rb"


def test_formula_is_deterministic_and_binds_the_real_cohort(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """The tap snapshot pins the exact sdist, companions, Python, and commands."""
    first = _generate(built_cohort, tmp_path / "first")
    second = _generate(built_cohort, tmp_path / "second")
    assert first.read_bytes() == second.read_bytes()
    formula = first.read_text(encoding="utf-8")

    assert formula.startswith("class Cadrumo < Formula\n")
    assert "include Language::Python::Virtualenv" in formula
    # The formula addresses the index that serves the product. A release asset
    # would send every install to a surface no workflow populates.
    assert f'url "{_INDEX_SOURCE}/cadrumo/{built_cohort.root.name}"' in formula
    assert "releases/download" not in formula
    assert f'sha256 "{sha256_path(built_cohort.root)}"' in formula
    assert 'depends_on "python@3.13"' in formula
    assert 'depends_on "cmake" => :build' in formula
    assert 'depends_on "jpeg-turbo"' in formula
    assert 'depends_on "qpdf"' in formula
    assert 'uses_from_macos "libffi"' in formula
    assert 'on_linux do\n    depends_on "zlib-ng-compat"' in formula
    # The install method drops Homebrew's pac-ret branch protection on Linux
    # arm64 only (Apple-Virtualization guests fault on the retaa instruction;
    # native macOS arm64 keeps the hardening) and builds argon2-cffi-bindings
    # with isolation off against the venv cffi, so it no longer uses the bare
    # virtualenv_install_with_resources.
    # Pinned as a MODIFIER `if`, not a block: `brew audit --strict` fails a
    # block `if` with a single-line body (Style/IfUnlessModifier), and that
    # audit is a hard gate on the macOS acquisition leg, so the block form
    # made the formula unshippable.
    assert (
        'ENV["HOMEBREW_CCCFG"] = ENV["HOMEBREW_CCCFG"].to_s.delete("b") if OS.linux? && Hardware::CPU.arm?'
    ) in formula
    # The block form opens the guard on its own line; the modifier form never
    # does. Anchoring on that whole line keeps this a real check -- the bare
    # condition string also appears in the modifier line, so asserting on it
    # alone would be satisfied by the very form this pins.
    assert "\n    if OS.linux? && Hardware::CPU.arm?\n" not in formula
    assert (
        'venv.pip_install resources.reject { |r| ["argon2-cffi-bindings", "cryptography"].include?(r.name) }'
    ) in formula
    assert 'venv.pip_install resource("argon2-cffi-bindings"), build_isolation: false' in formula
    # cryptography's maturin backend shells out to the `maturin` executable, so
    # the venv bin must be on PATH before its isolation-off install.
    assert 'ENV.prepend_path "PATH", libexec/"bin"' in formula
    assert 'venv.pip_install resource("cryptography"), build_isolation: false' in formula
    assert "venv.pip_install_and_link buildpath" in formula
    assert 'assert_predicate bin/"aeat", :executable?' in formula
    # The formula exposes only the product CLI.
    assert 'shell_output("#{bin}/aeat --version")' in formula

    resources = {name: (url, digest) for name, url, digest in _RESOURCE.findall(formula)}
    assert resources["cadrumo-data-manuals"] == (
        f"{_INDEX_SOURCE}/cadrumo-data-manuals/{built_cohort.manuals.name}",
        sha256_path(built_cohort.manuals),
    )
    assert resources["cadrumo-data-official"] == (
        f"{_INDEX_SOURCE}/cadrumo-data-official/{built_cohort.official.name}",
        sha256_path(built_cohort.official),
    )
    # No unrelated workspace dependency may leak into the formula closure.
    assert "mcp" not in resources
    assert "tzdata" not in resources
    # The three isolation-disabled build backends: setuptools -- the venv from
    # `python -m venv` ships none and Homebrew installs resources --no-deps;
    # setuptools-scm for argon2; maturin for cryptography.
    assert "setuptools" in resources
    assert "setuptools-scm" in resources
    assert "maturin" in resources
    # Gate on the property, not a pinned tally: the closure is exactly the
    # mandatory `cadrumo` lock walk plus the two data companions plus those
    # three backends, and every member resolves to immutable material. An
    # exact count encodes one moment and trains everyone to bump the constant.
    assert len(resources) == len(_RESOURCE.findall(formula))
    assert all(digest and len(digest) == 64 for _url, digest in resources.values())
    assert all(url.startswith("https://") for url, _digest in resources.values())
    # macOS is ARM-only (Intel dropped 2026-07-21), so no resource is macOS
    # conditional any more and the on_macos block disappears entirely; Linux
    # still spans two architectures and keeps its block.
    assert formula.count("  on_macos do\n") == 0
    assert formula.count("  on_linux do\n") == 1
    assert '    resource "secretstorage" do' in formula
    assert '    resource "jeepney" do' in formula
    # greenlet's marker excludes macOS arm64, so it is now Linux-common:
    # emitted once inside on_linux, with no architecture split on either side.
    assert formula.count('resource "greenlet" do') == 1
    assert '    resource "greenlet" do' in formula
    assert "on_intel do" not in formula
    assert "on_arm do" not in formula


def test_formula_resources_match_the_locked_pypi_sdists(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """Every non-cohort resource is one exact sdist from ``uv.lock``."""
    formula = _generate(built_cohort, tmp_path / "tap").read_text(encoding="utf-8")
    resources = {name: (url, digest) for name, url, digest in _RESOURCE.findall(formula)}
    lock = tomllib.loads((_REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked_sdists = {
        package["name"]: (
            package["sdist"]["url"],
            package["sdist"]["hash"].removeprefix("sha256:"),
        )
        for package in lock["package"]
        if package.get("source", {}).get("registry") == "https://pypi.org/simple" and "sdist" in package
    }
    for name, material in resources.items():
        if name.startswith("cadrumo-data-"):
            continue
        if name == "setuptools-scm":
            # Added as the argon2 build backend for the isolation-disabled build;
            # it is not a runtime dependency so it is absent from the lock. Pin it
            # to its declared PyPI sdist instead.
            assert material == (
                "https://files.pythonhosted.org/packages/4f/a4/00a9ac1b555294710d4a68d2ce8dfdf39d72aa4d769a7395d05218d88a42/setuptools_scm-8.1.0.tar.gz",
                "42dea1b65771cba93b7a515d65a65d8246e560768a66b9106a592c8e7f26c8a7",
            )
            continue
        if name == "maturin":
            # Added as the cryptography build backend for the isolation-disabled
            # build; not a runtime dependency, so absent from the lock. Pin it to
            # its declared PyPI sdist instead.
            assert material == (
                "https://files.pythonhosted.org/packages/e7/b3/addd877f871fb1860d46d3a4f206ecb10b946c85846805e6367631926fd3/maturin-1.14.1.tar.gz",
                "9d6577a62cd08e0ceba7a0db06fb098e0c9b1b3429bad747a4f3a18215a1b3df",
            )
            continue
        assert material == locked_sdists[name]


def test_generator_rejects_renamed_foreign_companion(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """A filename-compatible archive with foreign metadata cannot enter the tap."""
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    shutil.copy2(built_cohort.root, foreign / built_cohort.root.name)
    shutil.copy2(built_cohort.official, foreign / built_cohort.manuals.name)
    shutil.copy2(built_cohort.official, foreign / built_cohort.official.name)
    with pytest.raises(SystemExit):
        _generate(
            replace(built_cohort, directory=foreign),
            tmp_path / "tap",
        )
