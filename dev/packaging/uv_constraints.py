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

The closure spans TWO product distributions, not one. ``cadrumo`` carries the
CLI; the sibling ``cadrumo-harness`` carries the agent operating data and the
``cadrumo-mcp`` server, and both installers ship it — the MCPB launches the
harness console script, and the Scoop manifest wraps it. The harness therefore
contributes its own runtime requirements (the MCP SDK and its transport stack)
to the closure these installers must pin, and a constraints file carrying only
``cadrumo``'s closure would let the MCP server's dependencies float.

There is no ``agent`` extra to reach them through any more: it was removed from
``cadrumo`` when the harness became its own distribution. The harness is a plain
``[tool.uv.sources]`` path dependency rather than a ``[tool.uv.workspace]``
member, so ``uv export --package cadrumo-harness`` refuses it ("the workspace
does not have a member cadrumo-harness") and the harness tree carries no
lockfile of its own for a second export to run against. Both closures therefore
reach this export only through the root lockfile's record of the harness inside
``cadrumo``'s own resolution.

TODO: that record is not durable. ``cadrumo-harness`` sits in the ``dev``
dependency group, not in ``[project.dependencies]``, so the next ``uv lock``
moves it out of ``cadrumo``'s runtime resolution and the MCP server's
dependencies leave this export with it. There is no flag that recovers them:
promoting ``cadrumo-harness`` to a ``[tool.uv.workspace]`` member, so
``uv export --package cadrumo-harness`` can address it directly, is the
lockfile-shape decision that resolves this and it is deliberately not taken
here. Until it is, :func:`export_runtime_constraints` refuses rather than
emitting a constraints file the MCP server's dependencies fell out of.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

from dev._paths import UTF_8

_UTF_8 = UTF_8
#: The runtime install closure is ``cadrumo`` plus the ``cadrumo-harness``
#: agent/MCP distribution and the two data companions. The project itself, the
#: harness and both companions install from bundle-local or index-resolved
#: product wheels, so they are excluded from the pinned third-party constraint
#: set; only their transitive dependency closure needs pinning.
_LOCAL_PRODUCT_PACKAGES = ("cadrumo-data-manuals", "cadrumo-data-official", "cadrumo-harness")
#: Path (relative to the repository root) of the sibling harness distribution
#: whose runtime requirements must be covered by the exported closure.
_HARNESS_PYPROJECT = Path("src") / "cadrumo-harness" / "pyproject.toml"
#: The harness depends on ``cadrumo`` itself; that row is a product row, not a
#: third-party requirement the constraints file pins.
_HARNESS_SELF_REFERENCES = frozenset({"cadrumo", *_LOCAL_PRODUCT_PACKAGES})
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


def _harness_runtime_requirements(repo_root: Path) -> tuple[str, ...]:
    """Return the harness's third-party runtime requirement names.

    Read from the harness distribution's own ``pyproject.toml`` so the covered
    set follows the harness's declaration rather than a copy that can rot.
    """
    manifest = repo_root / _HARNESS_PYPROJECT
    if not manifest.is_file():
        raise SystemExit(f"cadrumo-harness pyproject.toml not found at {manifest}")
    document = tomllib.loads(manifest.read_text(encoding=_UTF_8))
    declared = document.get("project", {}).get("dependencies", [])
    names = {_requirement_name(str(row)) for row in declared}
    return tuple(sorted(names - _HARNESS_SELF_REFERENCES))


def export_runtime_constraints(*, repo_root: Path) -> tuple[str, ...]:
    """Return the pinned third-party runtime requirement lines from ``uv.lock``.

    Each returned line is a fully version-pinned PEP 508 requirement (``name==
    version`` with any environment marker preserved). Local product rows and the
    project itself are excluded because they install from bundle-local wheels.

    The exported closure must cover the ``cadrumo-harness`` distribution's own
    runtime requirements as well as ``cadrumo``'s, because both installers ship
    the harness and its ``cadrumo-mcp`` server. Coverage is asserted rather than
    assumed: see :func:`_assert_harness_closure_present`.
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
    _assert_harness_closure_present(lines, repo_root=repo_root)
    return tuple(lines)


def _assert_harness_closure_present(lines: list[str], *, repo_root: Path) -> None:
    """Refuse a closure the ``cadrumo-harness`` runtime requirements fell out of.

    ``uv export`` reaches the harness only through the root lockfile's record of
    ``cadrumo``'s resolution. It cannot be asked for directly: the harness is a
    ``[tool.uv.sources]`` path dependency, not a ``[tool.uv.workspace]`` member,
    so ``uv export --package cadrumo-harness`` refuses it, and the harness tree
    carries no lockfile of its own for a second export to run against.

    When the requirement names are absent, the Scoop manifest and the MCPB
    bundle would install ``cadrumo-harness`` and let the MCP SDK and its
    transport stack float free of the tested cohort — the exact drift this
    module exists to prevent. That is a refusal, never a warning: resolving it
    means promoting ``cadrumo-harness`` to a formal uv workspace member so
    ``uv export --package`` can address it, which is a lockfile-shape decision.
    """
    exported = {_normalize(line.split("==", 1)[0]) for line in lines}
    required = _harness_runtime_requirements(repo_root)
    missing = tuple(name for name in required if name not in exported)
    if missing:
        raise SystemExit(
            "uv export omitted the cadrumo-harness runtime closure: "
            f"{', '.join(missing)}. The harness ships in the Scoop manifest and the "
            "MCPB bundle, so its dependencies must be pinned with cadrumo's. "
            "uv cannot export a path-sourced non-workspace dependency on its own "
            "(`uv export --package cadrumo-harness` refuses: the workspace has no "
            "such member), and src/cadrumo-harness carries no lockfile of its own. "
            "Promote cadrumo-harness to a [tool.uv.workspace] member and export its "
            "closure with --package.",
        )


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
