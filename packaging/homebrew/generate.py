"""Generate a pinned Homebrew formula and tap snapshot from one Python cohort."""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
import tomllib
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from packaging.markers import Marker
from packaging.requirements import Requirement

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from dev.packaging._distribution_names import normalise_distribution_name  # noqa: E402
from dev.packaging._hashing import sha256_path  # noqa: E402
from dev.packaging.python_cohort import load_python_cohort  # noqa: E402

_COMPANIONS = (
    ("cadrumo-data-manuals", "cadrumo_data_manuals"),
    ("cadrumo-data-official", "cadrumo_data_official"),
)

# argon2-cffi-bindings and cryptography are installed with build isolation
# disabled (see the formula install method), so their build backends must be
# present in the virtual environment. A `python -m venv` (what
# virtualenv_create builds) ships pip but NOT setuptools, and Homebrew installs
# every resource with `--no-deps`, so nothing pulls setuptools in transitively;
# an isolation-disabled build then fails to load `setuptools.build_meta`.
# setuptools is therefore pinned here as an explicit venv resource (both
# backends need it: argon2 uses setuptools.build_meta directly, cryptography's
# build-requires lists it), alongside the two family-specific backends that are
# likewise absent from the locked runtime closure. setuptools-scm (argon2
# backend) is pinned to the self-contained 8.x line because 10.x splits its
# versioning into a separate `vcs_versioning` distribution that an
# isolation-disabled build cannot resolve. maturin (cryptography's build
# backend, cryptography>=48 requires maturin>=1.9.4,<2,!=1.12.0) builds from its
# own Rust source under isolation ON safely — its build overlay never imports
# cffi, so pac-ret there does not fault — and `rust` is already a formula build
# dependency. Declared as (name, url, sha256).
_EXTRA_BUILD_BACKEND = (
    (
        "setuptools",
        "https://files.pythonhosted.org/packages/34/26/f5d29e25ffdb535afef2d35cdb55b325298f96debd670da4c325e08d70f4/setuptools-83.0.0.tar.gz",
        "025bccbbf0fa05b6192bc64ae1e7b16e001fd6d6d4d5de03c97b1c1ade523bef",
    ),
    (
        "setuptools-scm",
        "https://files.pythonhosted.org/packages/4f/a4/00a9ac1b555294710d4a68d2ce8dfdf39d72aa4d769a7395d05218d88a42/setuptools_scm-8.1.0.tar.gz",
        "42dea1b65771cba93b7a515d65a65d8246e560768a66b9106a592c8e7f26c8a7",
    ),
    (
        "maturin",
        "https://files.pythonhosted.org/packages/e7/b3/addd877f871fb1860d46d3a4f206ecb10b946c85846805e6367631926fd3/maturin-1.14.1.tar.gz",
        "9d6577a62cd08e0ceba7a0db06fb098e0c9b1b3429bad747a4f3a18215a1b3df",
    ),
)
_TARGETS: dict[str, dict[str, str]] = {
    "macos-arm64": {
        "implementation_name": "cpython",
        "implementation_version": "3.13.0",
        "os_name": "posix",
        "platform_machine": "arm64",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Darwin",
        "platform_version": "",
        "python_full_version": "3.13.0",
        "python_version": "3.13",
        "sys_platform": "darwin",
    },
    "linux-x86_64": {
        "implementation_name": "cpython",
        "implementation_version": "3.13.0",
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "python_full_version": "3.13.0",
        "python_version": "3.13",
        "sys_platform": "linux",
    },
    "linux-arm64": {
        "implementation_name": "cpython",
        "implementation_version": "3.13.0",
        "os_name": "posix",
        "platform_machine": "aarch64",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "python_full_version": "3.13.0",
        "python_version": "3.13",
        "sys_platform": "linux",
    },
}


@dataclass(frozen=True)
class Resource:
    """One immutable Homebrew Python resource."""

    name: str
    url: str
    sha256: str
    platforms: frozenset[str]


@dataclass(frozen=True)
class SdistArtifact:
    """One readable and identity-verified cohort source distribution."""

    path: Path
    name: str
    version: str
    sha256: str
    requirements: tuple[str, ...]


def _one(cohort_dir: Path, pattern: str) -> Path:
    matches = tuple(sorted(cohort_dir.glob(pattern)))
    if len(matches) != 1:
        raise SystemExit(f"expected one artifact matching {pattern!r}; got {[path.name for path in matches]!r}")
    return matches[0].resolve(strict=True)


def _sdist_artifact(
    cohort_dir: Path,
    pattern: str,
    *,
    expected_name: str,
    expected_version: str,
) -> SdistArtifact:
    path = _one(cohort_dir, pattern)
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            metadata_members = tuple(member for member in archive.getmembers() if member.name.endswith("/PKG-INFO"))
            if len(metadata_members) != 1:
                raise SystemExit(f"expected one PKG-INFO member in {path.name}")
            handle = archive.extractfile(metadata_members[0])
            if handle is None:
                raise SystemExit(f"could not read PKG-INFO from {path.name}")
            metadata = Parser().parsestr(handle.read().decode("utf-8"))
    except (tarfile.TarError, UnicodeDecodeError) as exc:
        raise SystemExit(f"invalid source distribution {path.name}: {exc}") from exc
    name = metadata.get("Name")
    version = metadata.get("Version")
    if (
        not name
        or not version
        or normalise_distribution_name(name) != normalise_distribution_name(expected_name)
        or version != expected_version
    ):
        raise SystemExit(
            f"source distribution identity mismatch for {path.name}: "
            f"{name!r} {version!r}, expected {expected_name!r} {expected_version!r}",
        )
    return SdistArtifact(
        path=path,
        name=name,
        version=version,
        sha256=sha256_path(path),
        requirements=tuple(metadata.get_all("Requires-Dist", [])),
    )


def _validate_companion_pins(root: SdistArtifact, companions: tuple[SdistArtifact, ...]) -> None:
    requirements = [Requirement(value) for value in root.requirements]
    for companion in companions:
        matches = [
            requirement
            for requirement in requirements
            if normalise_distribution_name(requirement.name) == normalise_distribution_name(companion.name)
        ]
        if len(matches) != 1:
            raise SystemExit(f"root sdist must declare exactly one dependency on {companion.name}")
        requirement = matches[0]
        if (
            requirement.extras
            or requirement.marker is not None
            or str(requirement.specifier) != f"=={companion.version}"
        ):
            raise SystemExit(
                f"root sdist must require {companion.name}=={companion.version} "
                f"unconditionally and without extras; found {requirement}",
            )


def _release_base_url(value: str, *, version: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise SystemExit(f"release base URL must be immutable HTTPS without query or fragment: {value!r}")
    normalized = value.rstrip("/")
    if not normalized.endswith(f"/releases/download/v{version}"):
        raise SystemExit(f"release base URL must end with '/releases/download/v{version}': {value!r}")
    return normalized


def _applies(marker: str | None, target: dict[str, str]) -> bool:
    if marker is None:
        return True
    environment = dict(target)
    return Marker(marker).evaluate(environment)


def _select_package(
    dependency: dict[str, Any],
    packages_by_name: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    candidates = packages_by_name.get(str(dependency["name"]), [])
    version = dependency.get("version")
    if version is not None:
        candidates = [candidate for candidate in candidates if candidate.get("version") == version]
    registry = dependency.get("source", {}).get("registry")
    if registry is not None:
        candidates = [candidate for candidate in candidates if candidate.get("source", {}).get("registry") == registry]
    registry_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("source", {}).get("registry") == "https://pypi.org/simple"
    ]
    if len(registry_candidates) != 1:
        raise SystemExit(
            f"expected one PyPI lock package for {dependency['name']!r}; got "
            f"{[(item.get('version'), item.get('source')) for item in candidates]!r}",
        )
    return registry_candidates[0]


def _locked_resources(lock_path: Path) -> tuple[Resource, ...]:
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages = list(lock["package"])
    packages_by_name: dict[str, list[dict[str, Any]]] = {}
    for package in packages:
        packages_by_name.setdefault(str(package["name"]), []).append(package)
    roots = packages_by_name.get("cadrumo", [])
    if len(roots) != 1:
        raise SystemExit("uv.lock must contain exactly one cadrumo package")
    root = roots[0]
    resolved: dict[str, Resource] = {}
    for platform, target in _TARGETS.items():
        # The formula installs the ``cadrumo`` distribution and its mandatory
        # closure only. The agent harness (personas, skills, and the
        # ``cadrumo-mcp`` server) is the separate ``cadrumo-harness``
        # distribution, which depends on ``cadrumo`` rather than the reverse and
        # publishes no cohort artifact a formula resource could pin. Homebrew
        # installs one distribution per formula, so the harness is out of this
        # formula's scope: it is obtained with ``pipx install cadrumo-harness``,
        # through the MCP bundle, or through the Claude plugin.
        queue = list(root.get("dependencies", []))
        seen = {"cadrumo-data-manuals", "cadrumo-data-official", "cadrumo-harness"}
        while queue:
            dependency = queue.pop(0)
            name = str(dependency["name"])
            if name in seen or not _applies(dependency.get("marker"), target):
                continue
            package = _select_package(dependency, packages_by_name)
            seen.add(name)
            sdist = package.get("sdist")
            if not isinstance(sdist, dict):
                raise SystemExit(f"locked Homebrew resource lacks an sdist: {name}")
            url = str(sdist["url"])
            digest = str(sdist["hash"])
            if (
                not url.startswith("https://files.pythonhosted.org/")
                or not digest.startswith("sha256:")
                or not re.fullmatch(r"[0-9a-f]{64}", digest.removeprefix("sha256:"))
            ):
                raise SystemExit(f"locked Homebrew resource is not immutable PyPI material: {name}")
            material = Resource(
                name=name,
                url=url,
                sha256=digest.removeprefix("sha256:"),
                platforms=frozenset({platform}),
            )
            previous = resolved.get(name)
            if previous is not None:
                if (previous.url, previous.sha256) != (material.url, material.sha256):
                    raise SystemExit(f"platform lock material differs for Homebrew resource: {name}")
                material = Resource(
                    name=name,
                    url=material.url,
                    sha256=material.sha256,
                    platforms=previous.platforms | material.platforms,
                )
            resolved[name] = material
            queue.extend(package.get("dependencies", []))
    return tuple(sorted(resolved.values(), key=lambda resource: resource.name))


def _resource_declaration(resource: Resource, *, indent: int) -> str:
    prefix = "  " * indent
    return (
        f'{prefix}resource "{resource.name}" do\n'
        f'{prefix}  url "{resource.url}"\n'
        f'{prefix}  sha256 "{resource.sha256}"\n'
        f"{prefix}end\n"
    )


def _platform_resource_body(
    resources: tuple[Resource, ...],
    *,
    platform: str,
) -> str:
    platform_targets = frozenset(target for target in _TARGETS if target.startswith(f"{platform}-"))
    blocks: list[str] = []
    for resource in resources:
        selected = resource.platforms & platform_targets
        if selected == platform_targets:
            blocks.append(_resource_declaration(resource, indent=2))
        elif selected and len(selected) != 1:
            raise SystemExit(
                f"Homebrew resource closure has an unsupported target subset for "
                f"{resource.name}: {sorted(resource.platforms)!r}",
            )
    if len(platform_targets) < 2:
        # A single-architecture platform (macOS is ARM-only) has no split to
        # emit: every applicable resource already went out above, and running
        # the loop below would emit each of them a second time.
        return "".join(blocks)
    for architecture, suffix in (("arm", "arm64"), ("intel", "x86_64")):
        target = f"{platform}-{suffix}"
        selected_resources = tuple(
            resource for resource in resources if resource.platforms & platform_targets == frozenset({target})
        )
        if selected_resources:
            declarations = "".join(_resource_declaration(resource, indent=3) for resource in selected_resources)
            blocks.append(
                f"    on_{architecture} do\n{declarations}    end\n",
            )
    return "".join(blocks)


def _resource_blocks(resources: tuple[Resource, ...]) -> str:
    all_targets = frozenset(_TARGETS)
    common = tuple(resource for resource in resources if resource.platforms == all_targets)
    conditional = tuple(resource for resource in resources if resource.platforms != all_targets)
    for resource in conditional:
        if not resource.platforms <= all_targets:
            raise SystemExit(
                f"Homebrew resource closure names an unsupported target for "
                f"{resource.name}: {sorted(resource.platforms)!r}",
            )

    blocks: list[str] = []
    macos = _platform_resource_body(conditional, platform="macos").rstrip()
    if macos:
        blocks.append(f"  on_macos do\n{macos}\n  end")
    linux = _platform_resource_body(conditional, platform="linux").rstrip()
    linux_body = '    depends_on "zlib-ng-compat"'
    if linux:
        linux_body = f"{linux_body}\n\n{linux}"
    blocks.append(f"  on_linux do\n{linux_body}\n  end")
    blocks.extend(_resource_declaration(resource, indent=1).rstrip() for resource in common)
    return "\n\n".join(blocks)


def generate_formula(
    *,
    cohort_dir: Path,
    lock_path: Path,
    version: str,
    release_base_url: str,
) -> str:
    """Return one deterministic formula for the exact supplied cohort."""
    load_python_cohort(cohort_dir)
    base_url = _release_base_url(release_base_url, version=version)
    root = _sdist_artifact(
        cohort_dir,
        f"cadrumo-{version}.tar.gz",
        expected_name="cadrumo",
        expected_version=version,
    )
    companions = tuple(
        _sdist_artifact(
            cohort_dir,
            f"{filename}-{version}.tar.gz",
            expected_name=name,
            expected_version=version,
        )
        for name, filename in _COMPANIONS
    )
    _validate_companion_pins(root, companions)
    companion_resources = tuple(
        Resource(
            name=artifact.name,
            url=f"{base_url}/{artifact.path.name}",
            sha256=artifact.sha256,
            platforms=frozenset(_TARGETS),
        )
        for artifact in companions
    )
    build_backend_resources = tuple(
        Resource(name=name, url=url, sha256=sha256, platforms=frozenset(_TARGETS))
        for name, url, sha256 in _EXTRA_BUILD_BACKEND
    )
    resources = (
        *companion_resources,
        *build_backend_resources,
        *_locked_resources(lock_path.resolve(strict=True)),
    )
    resource_text = _resource_blocks(resources)
    return f'''class Cadrumo < Formula
  include Language::Python::Virtualenv

  desc "Deterministic Spanish tax calculation CLI"
  homepage "https://github.com/nevenincs/cadrumo"
  url "{base_url}/{root.path.name}"
  sha256 "{root.sha256}"
  license "Apache-2.0"

  depends_on "cmake" => :build
  depends_on "pkgconf" => :build
  depends_on "rust" => :build
  depends_on "jpeg-turbo"
  depends_on "libyaml"
  depends_on "openssl@3"
  depends_on "python@3.13"
  depends_on "qpdf"
  uses_from_macos "libffi"
  uses_from_macos "libxml2"
  uses_from_macos "libxslt"

{resource_text}

  def install
    # Apple's Virtualization.framework guests (colima and Docker Desktop VMs on
    # Apple silicon -- the dominant Linux-arm64 environment) fault on the
    # pac-ret pointer-authentication return instruction (retaa) that Homebrew's
    # cc shim injects via HOMEBREW_CCCFG "b". Drop it on Linux arm64 only, so
    # no compiled C extension carries retaa there; native macOS arm64 executes
    # pointer authentication fine and keeps the hardening.
    # Written as a modifier `if`: `brew audit --strict` rejects a block `if`
    # whose body is a single line (Style/IfUnlessModifier), and that audit is a
    # hard gate on the macOS acquisition leg.
    ENV["HOMEBREW_CCCFG"] = ENV["HOMEBREW_CCCFG"].to_s.delete("b") if OS.linux? && Hardware::CPU.arm?
    venv = virtualenv_create(libexec, "python3.13")
    # argon2-cffi-bindings and cryptography each run cffi at build time: an
    # isolated PEP 517 build installs a fresh cffi into a pip build-isolation
    # overlay that re-inherits the shim's flags (on Linux arm64: pac-ret,
    # which crashes cffi on load under Apple virtualization -- for cryptography
    # it faults in cryptography-cffi's build.rs running build_openssl.py).
    # Build both with isolation off against the already-installed venv cffi
    # instead; their build backends (setuptools, setuptools-scm, maturin) are
    # present from the resources installed above.
    venv.pip_install resources.reject {{ |r| ["argon2-cffi-bindings", "cryptography"].include?(r.name) }}
    venv.pip_install resource("argon2-cffi-bindings"), build_isolation: false
    # cryptography's maturin build backend shells out to the `maturin`
    # executable by bare name. The sdist install places that binary at
    # libexec/bin, bundles no copy inside the Python package, and adds no PATH
    # entry, so the isolation-off build dies `FileNotFoundError: 'maturin'`.
    # Put the venv bin on PATH so the backend resolves it.
    ENV.prepend_path "PATH", libexec/"bin"
    venv.pip_install resource("cryptography"), build_isolation: false
    venv.pip_install_and_link buildpath
  end

  test do
    assert_predicate bin/"aeat", :executable?
    assert_match "CADRUMO #{{version}}", shell_output("#{{bin}}/aeat --version")
  end
end
'''


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--lock", default=Path("uv.lock"), type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--release-base-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> int:
    """Write one deterministic tap snapshot containing ``Formula/cadrumo.rb``."""
    args = _parser().parse_args()
    formula = generate_formula(
        cohort_dir=args.cohort_dir.resolve(strict=True),
        lock_path=args.lock,
        version=args.version,
        release_base_url=args.release_base_url,
    )
    output = args.output_dir.resolve() / "Formula" / "cadrumo.rb"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(formula, encoding="utf-8", newline="\n")
    sys.stdout.write(f"{output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
