"""Shared genuine release-cohort and client-environment fixture builders.

This is a shared release-cohort test contract, so it lives under the public
``dev.packaging`` tooling package rather than under a ``tests`` path. The
release tests import production cohort/evidence code across that same package
boundary, and this helper belongs to the same shared fixture surface.

Consolidates four near-identical release-cohort builders (three in
``dev/packaging/tests`` -- test_evidence.py, test_distribution_evidence_emit.py,
test_evidence_scrub.py -- plus ``dev/release/tests/test_distribution_readiness.py``'s
``_cohort``) that all built the same real on-disk cohort: every
:data:`~dev.packaging.cohort_manifest.REQUIRED_ARTIFACT_KINDS` artifact, a real
manifest, a real ``load_release_cohort`` read-back. They differed only in
filler identity values (version, source digest, digest bytes) that no caller
asserts against -- confirmed by grepping each file for a second reference to
its own filler before folding it into one shared default -- plus one
non-deterministic ``datetime.now(UTC)`` timestamp two of the four copies
already pinned, and one genuinely meaningful parameter: the release/readiness
cohort builder accepts a ``payload_suffix`` so a test can construct two
cohorts sharing a source digest but carrying different artifact bytes (and so
different digests), which its
mismatched-evidence gate exercises. That parameter is the strictest variant of
the four and is kept; the shared default keeps the artifact bytes unchanged
for every caller that never varies it.

:func:`client_venv_template` lives here for the same reason: it installs the
wheel :func:`_real_product_wheel` serves from the shared content-keyed cohort, so
keeping it beside that accessor is what stops a second, parallel wheel-building
path from appearing.
"""

from __future__ import annotations

import functools
import hashlib
import os
import platform
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from dev._paths import REPO_ROOT
from dev.cache_root import dev_cache_dir
from dev.packaging.command_execution import run_command

from .acquire_common import venv_bin_dir, venv_executable
from .cohort_manifest import (
    REQUIRED_ARTIFACT_KINDS,
    BuildIdentity,
    LoadedReleaseCohort,
    SourceIdentity,
    create_manifest,
    load_release_cohort,
    write_manifest,
)
from .installed_wheel_binding import installed_distribution_payload_sha256, sealed_wheel_payload_sha256
from .native.action_cache import action_lock
from .shared_cohort import shared_cohort

DEFAULT_COHORT_VERSION = "0.2.1"
DEFAULT_COHORT_SOURCE_DIGEST = "c" * 64
DEFAULT_COHORT_BUILD_CONSTRAINTS_SHA256 = "d" * 64
DEFAULT_COHORT_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _uv_executable() -> str:
    """Resolve the uv executable these fixtures build and install through."""
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv executable not found on PATH"
        raise RuntimeError(msg)
    return uv


def _real_product_wheel() -> Path:
    """Return the genuine product wheel; never counterfeit it from installed files.

    One wheel, because the harness ships inside it. It comes from the shared,
    content-keyed cohort, so every process and every packaging proof reading the
    same source reads the same snapshot-built bytes.
    """
    return shared_cohort().wheel


def _real_companion_wheels() -> tuple[Path, Path, Path]:
    """Return the mandatory data companions built beside the genuine core wheel."""
    return shared_cohort().companions


def _template_is_intact(template: Path, wheel: Path) -> bool:
    """Whether a cached template still holds exactly the sealed wheel's installed payload."""
    try:
        cli = venv_executable(template, "aeat").resolve(strict=True)
        return installed_distribution_payload_sha256(cli, "cadrumo") == sealed_wheel_payload_sha256(wheel)
    except (OSError, RuntimeError):
        return False


@functools.lru_cache(maxsize=1)
def client_venv_template() -> Path:
    """Install the real four-wheel product into a minimal venv, once per cohort content.

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
    and treat it as read-only. It is keyed by the cohort's content key and the
    owning interpreter and kept in the development cache, so every process of a
    run and every later run over the same content shares one install; a reused
    template must still attest to the sealed wheel's payload.
    """
    cohort = shared_cohort()
    cache = dev_cache_dir("packaging-client-venv")
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{cohort.key}\0{sys.executable}".encode()).hexdigest()
    root = cache / key
    template = root / ".venv"
    with action_lock(cache, key):
        if (root / "complete").is_file() and _template_is_intact(template, cohort.wheel):
            os.utime(root / "complete")
            return template
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir()
        # uv reads VIRTUAL_ENV when deciding which environment a command targets;
        # dropping it keeps the explicit --python selection unambiguous under a
        # pytest run that is itself executing inside an activated environment.
        environment = {name: value for name, value in os.environ.items() if name != "VIRTUAL_ENV"}
        uv = _uv_executable()
        interpreter = venv_bin_dir(template) / ("python.exe" if os.name == "nt" else "python")
        for argv in (
            [uv, "venv", "--python", sys.executable, str(template)],
            [
                uv,
                "pip",
                "install",
                "--python",
                str(interpreter),
                str(cohort.wheel),
                *(str(wheel) for wheel in cohort.companions),
            ],
        ):
            completed = run_command(argv, cwd=REPO_ROOT, environment=environment)
            if completed.returncode != 0:
                raise RuntimeError(f"client venv fixture build failed: {argv!r}\n{completed.stderr}")
        (root / "complete").write_text(cohort.key, encoding="utf-8")
        _prune_templates(cache, keep=key)
    return template


def _prune_templates(cache: Path, *, keep: str) -> None:
    """Keep the newest few templates; each one is a full install of several hundred megabytes."""
    entries = [path for path in cache.iterdir() if path.name != keep and (path / "complete").is_file()]
    entries.sort(key=lambda path: (path / "complete").stat().st_mtime_ns, reverse=True)
    for stale in entries[2:]:
        shutil.rmtree(stale, ignore_errors=True)


def release_cohort(
    root: Path,
    *,
    version: str = DEFAULT_COHORT_VERSION,
    source_digest: str = DEFAULT_COHORT_SOURCE_DIGEST,
    build_constraints_sha256: str = DEFAULT_COHORT_BUILD_CONSTRAINTS_SHA256,
    created_at: datetime = DEFAULT_COHORT_CREATED_AT,
    payload_suffix: str = "",
) -> LoadedReleaseCohort:
    """Materialise a genuine release cohort with every required artifact kind.

    ``payload_suffix`` varies each artifact's bytes without touching source or
    version identity, so two cohorts can share one source digest/version yet
    carry different digests -- the shape the digest-mismatch readiness gate
    needs.
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
        source=SourceIdentity(source_digest=source_digest, tag=f"v{version}"),
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
