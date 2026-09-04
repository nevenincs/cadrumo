"""Shared genuine release-cohort and client-environment fixture builders.

Underscore-prefixed so it is never collected as a test module. Lives under
``dev/packaging/tests/`` because :mod:`dev.packaging.cohort_manifest` is this
concept's owning module; ``dev/release/tests`` already imports production
cohort/evidence code across that same package boundary
(``dev/release/tests/test_distribution_readiness.py``), so a cross-package
test-helper import here follows an established precedent (see also
``src/cadrumo/tests/test_regulatory_cap_term_dominance.py`` importing
``..domain.tests._regulatory_cap_witnesses``).

Consolidates four near-identical release-cohort builders (three in
``dev/packaging/tests`` -- test_evidence.py, test_distribution_evidence_emit.py,
test_evidence_scrub.py -- plus ``dev/release/tests/test_distribution_readiness.py``'s
``_cohort``) that all built the same real on-disk cohort: every
:data:`~dev.packaging.cohort_manifest.REQUIRED_ARTIFACT_KINDS` artifact, a real
manifest, a real ``load_release_cohort`` read-back. They differed only in
filler identity values (version, commit, digest bytes) that no caller asserts
against -- confirmed by grepping each file for a second reference to its own
filler before folding it into one shared default -- plus one non-deterministic
``datetime.now(UTC)`` timestamp two of the four copies already pinned, and one
genuinely meaningful parameter: the release/readiness cohort builder accepts a
``payload_suffix`` so a test can construct two cohorts sharing a commit but
carrying different artifact bytes (and so different digests), which its
mismatched-evidence gate exercises. That parameter is the strictest variant of
the four and is kept; the shared default keeps the artifact bytes unchanged
for every caller that never varies it.

:func:`client_venv_template` lives here for the same reason: it installs the
wheel :func:`_real_product_wheel` already builds, so keeping it beside that
builder is what stops a second, parallel wheel-building path from appearing.
"""

from __future__ import annotations

import atexit
import functools
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ..._paths import REPO_ROOT
from .._acquire_common import venv_bin_dir
from ..cohort_manifest import (
    REQUIRED_ARTIFACT_KINDS,
    BuildIdentity,
    LoadedReleaseCohort,
    SourceIdentity,
    create_manifest,
    load_release_cohort,
    write_manifest,
)

DEFAULT_COHORT_VERSION = "0.2.1"
DEFAULT_COHORT_COMMIT = "c" * 40
DEFAULT_COHORT_BUILD_CONSTRAINTS_SHA256 = "d" * 64
DEFAULT_COHORT_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _uv_executable() -> str:
    """Resolve the uv executable these fixtures build and install through."""
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv executable not found on PATH"
        raise RuntimeError(msg)
    return uv


def _session_scratch_root(prefix: str) -> Path:
    """Create a scratch directory that is removed when this process exits.

    A bare ``mkdtemp`` here leaks the whole directory on every run, and these
    fixtures write venvs and wheels measured in hundreds of megabytes, so the
    finalizer is registered at creation rather than left to the caller.
    """
    root = Path(tempfile.mkdtemp(prefix=prefix))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    return root


@functools.lru_cache(maxsize=1)
def _real_product_wheel() -> Path:
    """Build the product wheel once; never counterfeit it from installed files.

    One wheel, because the harness ships inside it. A second build against a
    separate harness project is what this fixture used to do, and there is no
    such project to build.
    """
    output = _session_scratch_root("cadrumo-real-cohort-wheels-")
    completed = subprocess.run(  # noqa: S603 - fixed uv build argv over repository-owned paths.
        [_uv_executable(), "build", "--wheel", "--out-dir", str(output)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"real wheel fixture build failed: {completed.stderr}")
    candidates = tuple(output.glob("cadrumo-*.whl"))
    if len(candidates) != 1:
        raise RuntimeError(f"real wheel fixture expected one cadrumo-*.whl: {candidates!r}")
    return candidates[0]


@functools.lru_cache(maxsize=1)
def client_venv_template() -> Path:
    """Install the real product wheel into a minimal venv, once per process.

    The launcher-facing tests need the genuine installer-generated ``aeat`` and
    ``cadrumo-mcp`` console scripts, the interpreter that owns them, and an
    environment those scripts can actually import in: the installed-console
    entry-point binding resolves each entry point through the confined
    interpreter and imports its module, so a dependency-less install fails on
    the first runtime import rather than on anything the binding is testing.
    The install therefore carries the wheel's own declared closure -- the shape
    a published lane installs -- and nothing from the ambient development
    environment, whose machine-learning, browser-automation and type-checker
    payload no assertion here reads.

    Callers hard-link this template into their own root rather than reinstalling,
    so the environment is materialised once for the whole process.
    """
    root = _session_scratch_root("cadrumo-client-venv-")
    template = root / ".venv"
    # uv reads VIRTUAL_ENV when deciding which environment a command targets;
    # dropping it keeps the explicit --python selection unambiguous under a
    # pytest run that is itself executing inside an activated environment.
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    uv = _uv_executable()
    interpreter = venv_bin_dir(template) / ("python.exe" if os.name == "nt" else "python")
    for argv in (
        [uv, "venv", "--python", sys.executable, str(template)],
        [uv, "pip", "install", "--python", str(interpreter), str(_real_product_wheel())],
    ):
        completed = subprocess.run(  # noqa: S603 - fixed uv argv over fixture-owned paths.
            argv,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"client venv fixture build failed: {argv!r}\n{completed.stderr}")
    return template


def release_cohort(
    root: Path,
    *,
    version: str = DEFAULT_COHORT_VERSION,
    commit: str = DEFAULT_COHORT_COMMIT,
    build_constraints_sha256: str = DEFAULT_COHORT_BUILD_CONSTRAINTS_SHA256,
    created_at: datetime = DEFAULT_COHORT_CREATED_AT,
    payload_suffix: str = "",
) -> LoadedReleaseCohort:
    """Materialise a genuine release cohort with every required artifact kind.

    ``payload_suffix`` varies each artifact's bytes without touching commit or
    version identity, so two cohorts can share one commit/version yet carry
    different digests -- the shape the digest-mismatch readiness gate needs.
    """
    root.mkdir(parents=True)
    artifacts = []
    for index, (name, kind) in enumerate(sorted(REQUIRED_ARTIFACT_KINDS.items())):
        path = root / "artifacts" / f"{name}.bin"
        path.parent.mkdir(exist_ok=True)
        if name == "cadrumo-wheel":
            shutil.copy2(_real_product_wheel(), path)
            if payload_suffix:
                with zipfile.ZipFile(path, "a") as archive:
                    archive.writestr("cadrumo/_foreign_cohort_plant.py", payload_suffix)
        else:
            path.write_bytes(f"{index}:{name}:{payload_suffix}\n".encode())
        artifacts.append((name, kind, path))
    manifest = create_manifest(
        root=root,
        version=version,
        source=SourceIdentity(commit=commit, tag=f"v{version}"),
        created_at=created_at,
        builder=BuildIdentity(
            implementation="dev.packaging.release_cohort",
            format_version=1,
            python=platform.python_version(),
            uv="0.11.29",
            platform=platform.system(),
            architecture=platform.machine(),
            build_constraints_sha256=build_constraints_sha256,
        ),
        artifacts=artifacts,
    )
    write_manifest(root, manifest)
    return load_release_cohort(root)
