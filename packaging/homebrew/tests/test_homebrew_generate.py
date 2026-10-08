"""Real-artifact tests for the generated Cadrumo Homebrew tap snapshot."""

from __future__ import annotations

import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from dev.packaging._distribution_names import normalise_distribution_name
from dev.packaging.cohort_attestation import add_test_runtime_wheelhouse, add_test_source_archive
from dev.packaging.command_spec_attestation import attest_command_specs
from dev.packaging.hashing import sha256_path
from dev.packaging.lane_verification_core import (
    build_companion_wheels,
    build_root_snapshot,
    build_sdist,
    build_wheel,
    run_checked,
)
from packaging.markers import Marker, default_environment

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
#: The backends the two isolation-disabled builds load. They are installed to
#: run a build, never as part of the product's runtime closure, so the lock walk
#: the formula derives its resources from does not reach them and they are
#: pinned explicitly instead. A lock row that happens to share one of these
#: names belongs to an unrelated development dependency and says nothing about
#: which backend the formula should build against.
_EXPLICIT_BUILD_BACKENDS = frozenset({"setuptools", "setuptools-scm", "maturin"})
#: The index's immutable per-file path: the digest-derived directories under
#: which an uploaded artifact is served forever. The ``/packages/source/`` form
#: the cohort artifacts use is a redirect to whichever file the project serves
#: now, so it is expressly not this.
_IMMUTABLE_INDEX_FILE = re.compile(
    r"https://files\.pythonhosted\.org/packages/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}/(?P<filename>[^/]+)",
)


def _formula_resources_for_target(formula: str, target: str) -> dict[str, tuple[str, str]]:
    """Observe the resources active within the formula's OS and architecture blocks."""
    platform, architecture = target.split("-", 1)
    predicates = {
        "on_macos do": platform == "macos",
        "on_linux do": platform == "linux",
        "on_arm do": architecture == "arm64",
        "on_intel do": architecture == "x86_64",
    }
    conditions: dict[int, bool] = {}
    observed: dict[str, tuple[str, str]] = {}
    lines = formula.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped in predicates:
            conditions[indent] = predicates[stripped]
        elif stripped == "end":
            conditions.pop(indent, None)
        elif stripped.startswith('resource "') and all(conditions.values()):
            declaration = _RESOURCE.match("\n" + "\n".join(lines[index : index + 4]))
            assert declaration is not None, line
            name, url, digest = declaration.groups()
            assert name not in observed, (target, name)
            observed[name] = (url, digest)
    return observed


@dataclass(frozen=True)
class BuiltCohort:
    """One real sdist-and-companion cohort shared by formula tests."""

    directory: Path
    root: Path
    manuals: Path
    official: Path
    normatives: Path
    version: str


@pytest.fixture(scope="module")
def built_cohort(tmp_path_factory: pytest.TempPathFactory) -> BuiltCohort:
    """Build the real root and companion source distributions."""
    uv = shutil.which("uv")
    assert uv is not None
    root_dir = tmp_path_factory.mktemp("homebrew-cohort")
    build_dir = root_dir / "build"
    # Build from a snapshot of the enumerated tree, not the live working tree:
    # a peer's in-flight edit mid-build would otherwise ride into the sdist
    # partway through, and the formula this test asserts on would describe
    # bytes that no single state of the tree ever held.
    build_root = build_root_snapshot(_REPO_ROOT, build_dir)
    root = build_sdist(build_dir, uv, build_root=build_root)
    companion_dir = build_dir / "companions"
    manuals_project = build_root / "packaging" / "cadrumo_data_manuals"
    official_project = build_root / "packaging" / "cadrumo_data_official"
    normatives_project = build_root / "packaging" / "cadrumo_data_normatives"
    run_checked([uv, "build", "--sdist", "--out-dir", str(companion_dir)], cwd=manuals_project)
    run_checked([uv, "build", "--sdist", "--out-dir", str(companion_dir)], cwd=official_project)
    run_checked([uv, "build", "--sdist", "--out-dir", str(companion_dir)], cwd=normatives_project)
    manuals = next(companion_dir.glob("cadrumo_data_manuals-*.tar.gz"))
    official = next(companion_dir.glob("cadrumo_data_official-*.tar.gz"))
    normatives = next(companion_dir.glob("cadrumo_data_normatives-*.tar.gz"))
    cohort = root_dir / "cohort"
    cohort.mkdir()
    copied = []
    for artifact in (root, manuals, official, normatives):
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
        "cadrumo-data-normatives": copied_wheels[3].name,
        "cadrumo-data-normatives-sdist": copied[3].name,
    }
    digests = {name: sha256_path(cohort / filename) for name, filename in artifacts.items()}
    source_archive = add_test_source_archive(cohort, artifacts, digests)
    add_test_runtime_wheelhouse(cohort, artifacts, digests)
    (cohort / "python-cohort.json").write_text(
        json.dumps(
            {
                "artifacts": artifacts,
                "sha256": digests,
                "source_digest": "a" * 64,
                "version": version,
                "command_spec_attestation": attest_command_specs(
                    site_root=build_root / "src",
                    root_wheel=copied_wheels[0],
                    root_sdist=copied[0],
                    source_archive=source_archive,
                    source_digest="a" * 64,
                    work_root=root_dir,
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
        normatives=copied[3],
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
    # Homebrew installs with pip --no-compile; post_install is the one hook that
    # runs after both a source build and a bottle pour.
    post_install = formula[formula.index("  def post_install\n") : formula.index("  test do\n")]
    assert "compileall.compile_dir(" in post_install
    assert 'libexec/"bin/python"' in post_install
    assert 'libexec/"lib"' in post_install
    assert 'assert_predicate bin/"aeat", :executable?' in formula
    assert 'shell_output("#{bin}/aeat --version")' in formula
    # `pip_install_and_link` links every declared console script, so the test
    # block checks each one arrived rather than only the product CLI.
    assert 'assert_predicate bin/"cadrumo-mcp", :executable?' in formula

    resources = _formula_resources_for_target(formula, "macos-arm64")
    assert resources["cadrumo-data-manuals"] == (
        f"{_INDEX_SOURCE}/cadrumo-data-manuals/{built_cohort.manuals.name}",
        sha256_path(built_cohort.manuals),
    )
    assert resources["cadrumo-data-official"] == (
        f"{_INDEX_SOURCE}/cadrumo-data-official/{built_cohort.official.name}",
        sha256_path(built_cohort.official),
    )
    assert resources["cadrumo-data-normatives"] == (
        f"{_INDEX_SOURCE}/cadrumo-data-normatives/{built_cohort.normatives.name}",
        sha256_path(built_cohort.normatives),
    )
    # The MCP SDK is a mandatory runtime requirement of the distribution this
    # formula installs, and Homebrew installs every resource with --no-deps, so
    # nothing pulls it in transitively: absent from the closure, the installed
    # virtualenv is missing an import the product makes.
    assert "mcp" in resources
    # The root declares tzdata as a mandatory runtime dependency. Homebrew's
    # no-deps resource install must carry that dependency explicitly as well.
    assert "tzdata" in resources
    # The three isolation-disabled build backends: setuptools -- the venv from
    # `python -m venv` ships none and Homebrew installs resources --no-deps;
    # setuptools-scm for argon2; maturin for cryptography.
    assert "setuptools" in resources
    assert "setuptools-scm" in resources
    assert "maturin" in resources
    # Gate on the property, not a pinned tally: the closure is exactly the
    # mandatory `cadrumo` lock walk plus the three data companions plus those
    # three backends, and every member resolves to immutable material. An
    # exact count encodes one moment and trains everyone to bump the constant.
    for target in ("macos-arm64", "linux-arm64", "linux-x86_64"):
        assert _formula_resources_for_target(formula, target)
    assert all(digest and len(digest) == 64 for _url, digest in resources.values())
    assert all(url.startswith("https://") for url, _digest in resources.values())
    # macOS is ARM-only. The lock deliberately selects a different pikepdf
    # version for Darwin, so its material lives in the OS-specific block.
    assert formula.count("  on_macos do\n") == 1
    assert formula.count("  on_linux do\n") == 1
    assert '    resource "secretstorage" do' in formula
    assert '    resource "jeepney" do' in formula
    # The locked SQLAlchemy core no longer requires the asyncio-only greenlet
    # extra. Development or optional-extra material must not enter this recipe.
    for target in ("macos-arm64", "linux-arm64", "linux-x86_64"):
        assert "greenlet" not in _formula_resources_for_target(formula, target)
    assert "on_intel do" not in formula
    assert "on_arm do" not in formula


def test_formula_resources_match_the_locked_pypi_sdists(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """Every runtime resource is one exact sdist from ``uv.lock``."""
    formula = _generate(built_cohort, tmp_path / "tap").read_text(encoding="utf-8")
    lock = tomllib.loads((_REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    for target in ("macos-arm64", "linux-arm64", "linux-x86_64"):
        _assert_target_resources_match_lock(formula, target, lock)


def _assert_target_resources_match_lock(formula: str, target: str, lock: dict[str, Any]) -> None:
    environment = {key: str(value) for key, value in default_environment().items()}
    environment.update({"python_full_version": "3.13.0", "python_version": "3.13"})
    environment["sys_platform"] = "darwin" if target.startswith("macos-") else "linux"
    environment["platform_system"] = "Darwin" if target.startswith("macos-") else "Linux"
    environment["os_name"] = "posix"
    environment["platform_machine"] = "arm64" if target.endswith("arm64") else "x86_64"
    locked_sdists: dict[str, set[tuple[str, str]]] = {}
    for package in lock["package"]:
        if package.get("source", {}).get("registry") != "https://pypi.org/simple" or "sdist" not in package:
            continue
        markers = package.get("resolution-markers", ())
        if markers and not any(Marker(marker).evaluate(environment) for marker in markers):
            continue
        locked_sdists.setdefault(package["name"], set()).add(
            (package["sdist"]["url"], package["sdist"]["hash"].removeprefix("sha256:"))
        )
    resources = _formula_resources_for_target(formula, target)
    backends: set[str] = set()
    for name, material in resources.items():
        if name.startswith("cadrumo-data-"):
            continue
        if name in _EXPLICIT_BUILD_BACKENDS:
            # A build backend is outside the runtime closure by construction, so
            # the lock cannot say which artifact it should be. What the formula
            # must still guarantee is that the pin addresses immutable index
            # material for that exact distribution, so the bytes a user builds
            # against are the reviewed ones and cannot be swapped underneath.
            backends.add(name)
            url, _digest = material
            served = _IMMUTABLE_INDEX_FILE.fullmatch(url)
            assert served is not None, url
            filename = served.group("filename")
            assert filename.endswith(".tar.gz")
            distribution = filename.removesuffix(".tar.gz").rsplit("-", 1)[0]
            assert normalise_distribution_name(distribution) == name
            continue
        assert material in locked_sdists[name], (target, name, material)
    # Every declared backend reached the formula, and no other resource escaped
    # the lock: an unlisted name falls through to the lock comparison above.
    assert backends == set(_EXPLICIT_BUILD_BACKENDS)


def test_generator_rejects_renamed_foreign_companion(
    tmp_path: Path,
    built_cohort: BuiltCohort,
) -> None:
    """A filename-compatible archive with foreign metadata cannot enter the tap."""
    foreign = tmp_path / "foreign"
    shutil.copytree(built_cohort.directory, foreign)
    shutil.copy2(built_cohort.official, foreign / built_cohort.manuals.name)
    manifest = foreign / "python-cohort.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["sha256"]["cadrumo-data-manuals-sdist"] = sha256_path(built_cohort.official)
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SystemExit):
        _generate(
            replace(built_cohort, directory=foreign),
            tmp_path / "tap",
        )
