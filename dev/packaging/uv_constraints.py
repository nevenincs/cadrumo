"""Export the tested product CLI dependency closure from ``uv.lock``.

The Scoop manifest resolves the Cadrumo distribution's transitive dependencies
against these exact pins. The closure is rooted at ``cadrumo`` and excludes
local product artifacts; unrelated workspace packages cannot influence it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from dev._paths import UTF_8

_UTF_8 = UTF_8
#: Product distributions install from release artifacts; only their third-party
#: dependency closure belongs in the generated constraints.
_LOCAL_PRODUCT_PACKAGES = ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official")
_EXPORTED_PACKAGE = "cadrumo"
_CONSTRAINTS_HEADER = (
    "# Runtime dependency closure pinned from the tested uv.lock.\n"
    "# Generated at packaging time; do not edit by hand.\n"
)


def _normalize(name: str) -> str:
    """Return the PEP 503 normalized form of a distribution name."""
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def _requirement_name(requirement: str) -> str:
    """Return the normalized distribution name of one PEP 508 requirement."""
    head = requirement.strip()
    for separator in (";", "["):
        head = head.split(separator, 1)[0]
    for index, character in enumerate(head):
        if character in "<>=!~ \t(":
            head = head[:index]
            break
    return _normalize(head)


def export_runtime_constraints(*, repo_root: Path) -> tuple[str, ...]:
    """Return the pinned third-party runtime requirement lines from ``uv.lock``.

    Each returned line is a fully version-pinned PEP 508 requirement (``name==
    version`` with any environment marker preserved). Local product rows and the
    project itself are excluded because they install from bundle-local wheels.

    The closure is rooted at ``cadrumo`` so unrelated workspace packages cannot
    add dependencies to the product installer.
    """
    lock = repo_root / "uv.lock"
    if not lock.is_file():
        raise SystemExit(f"uv.lock not found at {lock}")
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required to export the pinned dependency constraints")
    command = [
        uv,
        "export",
        "--frozen",
        "--no-dev",
        "--no-default-groups",
        "--package",
        _EXPORTED_PACKAGE,
        "--no-hashes",
        "--no-annotate",
        "--no-header",
        "--no-emit-project",
    ]
    for package in _LOCAL_PRODUCT_PACKAGES:
        command.extend(("--no-emit-package", package))
    result = subprocess.run(  # noqa: S603 - fixed uv argv against the repository lockfile
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        encoding=_UTF_8,
    )
    if result.returncode != 0:
        raise SystemExit(f"uv export failed: {result.stderr.strip()}")
    lines: list[str] = []
    for raw in result.stdout.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(("./", "../", "-e ", "-r ", "file:")):
            raise SystemExit(f"uv export emitted a non-pinned local row: {stripped!r}")
        if "==" not in stripped:
            raise SystemExit(f"uv export row is not version-pinned: {stripped!r}")
        lines.append(stripped)
    if not lines:
        raise SystemExit("uv export produced an empty runtime constraint closure")
    return tuple(lines)


def render_constraints_file(lines: tuple[str, ...], *, min_uv_version: str | None = None) -> str:
    """Render the pinned requirement lines as a deterministic pip constraints file.

    When ``min_uv_version`` is supplied, the header additionally states the
    minimum uv release whose ``uv sync`` honours the pinned closure, so a reader
    of the staged file knows the floor the bundle enforces at first launch.
    """
    header = _CONSTRAINTS_HEADER
    if min_uv_version is not None:
        header += (
            f"# Requires uv >= {min_uv_version}: uv sync honours [tool.uv] "
            "constraint-dependencies only from that release; an older uv ignores these pins.\n"
        )
    return header + "".join(f"{line}\n" for line in lines)
