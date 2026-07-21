"""Real-artifact tests for the generated Cadrumo Homebrew tap snapshot."""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from dev.packaging.smoke_core import _run
from dev.packaging.smoke_sdist_core import _build_sdist

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = Path(__file__).resolve().parents[3]
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
    release_base: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def built_cohort(tmp_path_factory: pytest.TempPathFactory) -> BuiltCohort:
    """Build the real root and companion source distributions."""
    uv = shutil.which("uv")
    assert uv is not None
    root_dir = tmp_path_factory.mktemp("homebrew-cohort")
    build_dir = root_dir / "build"
    root = _build_sdist(_REPO_ROOT, build_dir, uv)
    companion_dir = build_dir / "companions"
    manuals_project = _REPO_ROOT / "packaging" / "cadrumo_data_manuals"
    official_project = _REPO_ROOT / "packaging" / "cadrumo_data_official"
    _run([uv, "build", "--sdist", "--out-dir", str(companion_dir)], cwd=manuals_project)
    _run([uv, "build", "--sdist", "--out-dir", str(companion_dir)], cwd=official_project)
    manuals = next(companion_dir.glob("cadrumo_data_manuals-*.tar.gz"))
    official = next(companion_dir.glob("cadrumo_data_official-*.tar.gz"))
    cohort = root_dir / "cohort"
    cohort.mkdir()
    copied = []
    for artifact in (root, manuals, official):
        target = cohort / artifact.name
        shutil.copy2(artifact, target)
        copied.append(target)
    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    return BuiltCohort(
        directory=cohort,
        root=copied[0],
        manuals=copied[1],
        official=copied[2],
        version=version,
        release_base=f"https://github.com/nevenincs/cadrumo/releases/download/v{version}",
    )


def _generate(cohort: BuiltCohort, output: Path, *, release_base: str | None = None) -> Path:
    _run(
        [
            sys.executable,
            str(_GENERATOR),
            "--cohort-dir",
            str(cohort.directory),
            "--lock",
            str(_REPO_ROOT / "uv.lock"),
            "--version",
            cohort.version,
            "--release-base-url",
            cohort.release_base if release_base is None else release_base,
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
    assert f'url "{built_cohort.release_base}/{built_cohort.root.name}"' in formula
    assert f'sha256 "{_sha256(built_cohort.root)}"' in formula
    assert 'depends_on "python@3.13"' in formula
    assert 'depends_on "cmake" => :build' in formula
    assert 'depends_on "jpeg-turbo"' in formula
    assert 'depends_on "qpdf"' in formula
    assert 'uses_from_macos "libffi"' in formula
    assert 'on_linux do\n    depends_on "zlib-ng-compat"' in formula
    assert 'virtualenv_install_with_resources using: "python3.13"' in formula
    assert 'assert_predicate bin/"aeat", :executable?' in formula
    assert 'assert_predicate bin/"cadrumo-mcp", :executable?' in formula
    assert 'shell_output("#{bin}/aeat --version")' in formula

    resources = {name: (url, digest) for name, url, digest in _RESOURCE.findall(formula)}
    assert resources["cadrumo-data-manuals"] == (
        f"{built_cohort.release_base}/{built_cohort.manuals.name}",
        _sha256(built_cohort.manuals),
    )
    assert resources["cadrumo-data-official"] == (
        f"{built_cohort.release_base}/{built_cohort.official.name}",
        _sha256(built_cohort.official),
    )
    assert "mcp" in resources
    assert "tzdata" not in resources
    assert len(resources) == 69
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


@pytest.mark.parametrize(
    "release_base",
    (
        "http://github.com/nevenincs/cadrumo/releases/download/v0.2.1",
        "https://github.com/nevenincs/cadrumo/releases/latest/download",
        "https://github.com/nevenincs/cadrumo/releases/download/v0.2.1?mutable=1",
    ),
)
def test_generator_rejects_mutable_release_urls(
    tmp_path: Path,
    built_cohort: BuiltCohort,
    release_base: str,
) -> None:
    """The formula cannot be generated against a mutable release endpoint."""
    with pytest.raises(SystemExit):
        _generate(built_cohort, tmp_path / "tap", release_base=release_base)
