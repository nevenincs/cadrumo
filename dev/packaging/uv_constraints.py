"""Export the tested runtime dependency closure from uv.lock as pip constraints.

The Scoop manifest and the MCPB bundle install the product wheels at user
install time and let uv resolve their transitive dependencies. Left unpinned,
that resolution floats to whatever the index serves on the install date,
drifting from the closure the release actually tested. Homebrew pins the same
closure resource-by-resource inside the generated formula; this module is the
Scoop and MCPB counterpart, exporting the exact third-party versions recorded in
``uv.lock`` as a pip constraints file so every installer pins to the tested
cohort. Versions are never hardcoded here: the closure is derived from the
lockfile on every generation.

One product distribution carries both console scripts, so its closure is the
whole runtime surface the installers must pin: the MCP SDK and its transport
stack are ``cadrumo``'s own requirements, reached by the same export as the
CLI's. Local, bundle-local-wheel rows (``cadrumo`` and the two data companions)
are excluded via ``--no-emit-package``; only genuine third-party leaves are
pinned.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .._paths import UTF_8

_UTF_8 = UTF_8
#: The runtime install closure is ``cadrumo`` and the two data companions. All
#: three install from bundle-local or index-resolved product wheels, so they are
#: excluded from the pinned third-party constraint set; only their transitive
#: dependency closure needs pinning.
_LOCAL_PRODUCT_PACKAGES = ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official")
#: The distribution whose resolution is exported.
_EXPORTED_PACKAGE = "cadrumo"
_CONSTRAINTS_HEADER = (
    "# Runtime dependency closure pinned from the tested uv.lock.\n"
    "# Generated at packaging time; do not edit by hand.\n"
)


def export_runtime_constraints(*, repo_root: Path) -> tuple[str, ...]:
    """Return the pinned third-party runtime requirement lines from ``uv.lock``.

    Each returned line is a fully version-pinned PEP 508 requirement (``name==
    version`` with any environment marker preserved). Local product rows and the
    project itself are excluded because they install from bundle-local wheels.

    The product is one distribution carrying both console scripts, so its own
    closure is the whole runtime surface the installers need — the agent
    server's requirements are cadrumo's requirements.
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
