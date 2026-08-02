"""Version bump executor: the pipeline stage replacing `release-apply`.

`just release-apply` printed eleven instructions for a human to transcribe by
hand: compute the version, apply it to seven declaration surfaces, regenerate
and verify the lock, stage, commit, tag, and (on a separate human decision)
push. This module is that sequence made executable and tested, so the release
orchestrator's first job can run it without a human re-typing seven file
paths.

The version stays computed, never chosen, from conventional-commit history --
:func:`run_release_please_dry_run` shells out to the same `release-please@16
release-pr --dry-run --debug` invocation `just release` already runs, and
:func:`parse_computed_version` reads the version release-please decided on
rather than accepting one as a parameter. Every mutation is applied through
:func:`apply_version`, which refuses rather than guesses whenever a surface
does not carry exactly the one version literal it expects, and the
build-stamped `.mcpb` manifest sentinel is asserted untouched on every call --
it is never a version authority; `packaging/mcpb/build.py` stamps the real
cohort version over it at build time.

See Also:
    :func:`apply_version`
        The seven-surface mutation, mirroring the retiring `release-apply`
        checklist's steps 1-7.
    :func:`dev.release.readiness.check_version_surfaces_agree`
        The parity check re-run after every bump so a transcription-class
        error cannot survive an automated one either.
    :func:`dev.release.version_identity.assert_version_available`
        The all-destination identity guard invoked before any ref leaves the
        runner.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core import PRODUCT_IDENTITY

_UTF_8: Final[str] = "utf-8"

#: The seven declaration surfaces `release-apply` printed as steps 1-7,
#: relative to the repository root. NOT included: `packaging/mcpb/manifest.json`
#: -- its tracked "version" is a build-stamped sentinel
#: (`dev.release.readiness.check_version_surfaces_agree` requires it stay put;
#: `packaging/mcpb/build.py` stamps the real version at build time), so
#: touching it here would make the bump fail its own post-bump readiness
#: re-check.
MANIFEST_RELATIVE: Final[Path] = Path(".release-please-manifest.json")
ROOT_PYPROJECT_RELATIVE: Final[Path] = Path("pyproject.toml")
DATA_MANUALS_PYPROJECT_RELATIVE: Final[Path] = Path("packaging/cadrumo_data_manuals/pyproject.toml")
DATA_OFFICIAL_PYPROJECT_RELATIVE: Final[Path] = Path("packaging/cadrumo_data_official/pyproject.toml")
INIT_RELATIVE: Final[Path] = Path("src/cadrumo/__init__.py")
CHANGELOG_RELATIVE: Final[Path] = Path("CHANGELOG.md")
MCPB_MANIFEST_RELATIVE: Final[Path] = Path("packaging/mcpb/manifest.json")

_INIT_VERSION_RE: Final = re.compile(r'^(__version__\s*=\s*)"[^"]*"', re.MULTILINE)
_PYPROJECT_VERSION_RE: Final = re.compile(r'^(version\s*=\s*)"[^"]*"', re.MULTILINE)
_UNRELEASED_HEADING: Final[str] = "## [Unreleased]\n"

#: `uv.lock` regeneration and the version-identity/readiness re-checks all
#: shell out; a generous but bounded timeout so a hung subprocess fails loudly
#: rather than hanging the bump indefinitely.
_SUBPROCESS_TIMEOUT_S: Final[int] = 600


class VersionBumpError(RuntimeError):
    """The bump cannot proceed; nothing beyond this point has been mutated."""


@dataclass(frozen=True, slots=True)
class SurfaceUpdate:
    """One declaration surface's full text before and after a bump."""

    relative_path: Path
    before: str
    after: str


def _substitute_single(text: str, pattern: re.Pattern[str], version: str, *, surface: str) -> str:
    """Replace the sole match of *pattern* in *text*, refusing zero or many."""
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise VersionBumpError(
            f"{surface} must declare exactly one version literal matching {pattern.pattern!r}, "
            f"found {len(matches)}",
        )
    return pattern.sub(lambda m: f'{m.group(1)}"{version}"', text, count=1)


def _bump_manifest(repo_root: Path, version: str) -> SurfaceUpdate:
    path = repo_root / MANIFEST_RELATIVE
    before = path.read_text(encoding=_UTF_8)
    try:
        payload = json.loads(before)
    except json.JSONDecodeError as exc:
        raise VersionBumpError(f"{MANIFEST_RELATIVE} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or "." not in payload:
        raise VersionBumpError(f"{MANIFEST_RELATIVE} does not carry a root '.' entry")
    payload["."] = version
    after = json.dumps(payload, indent=2) + "\n"
    path.write_text(after, encoding=_UTF_8)
    return SurfaceUpdate(MANIFEST_RELATIVE, before, after)


def _bump_pyproject_version(repo_root: Path, relative: Path, version: str) -> SurfaceUpdate:
    path = repo_root / relative
    before = path.read_text(encoding=_UTF_8)
    after = _substitute_single(before, _PYPROJECT_VERSION_RE, version, surface=str(relative))
    path.write_text(after, encoding=_UTF_8)
    return SurfaceUpdate(relative, before, after)


def _bump_init(repo_root: Path, version: str) -> SurfaceUpdate:
    path = repo_root / INIT_RELATIVE
    before = path.read_text(encoding=_UTF_8)
    after = _substitute_single(before, _INIT_VERSION_RE, version, surface=str(INIT_RELATIVE))
    path.write_text(after, encoding=_UTF_8)
    return SurfaceUpdate(INIT_RELATIVE, before, after)


def _bump_dependency_pins(repo_root: Path, version: str) -> SurfaceUpdate:
    """Bump both mandatory exact companion pins in the root `pyproject.toml`.

    Counted as ONE of the seven surfaces (`release-apply` step 6 named both
    pins together), so this returns a single :class:`SurfaceUpdate` covering
    both substitutions.
    """
    path = repo_root / ROOT_PYPROJECT_RELATIVE
    before = path.read_text(encoding=_UTF_8)
    after = before
    for distribution in PRODUCT_IDENTITY.companion_distributions:
        pattern = re.compile(rf'"{re.escape(distribution)}==[^"]*"')
        matches = list(pattern.finditer(after))
        if len(matches) != 1:
            raise VersionBumpError(
                f"{ROOT_PYPROJECT_RELATIVE} must pin {distribution} exactly once, found {len(matches)}",
            )
        after = pattern.sub(f'"{distribution}=={version}"', after, count=1)
    path.write_text(after, encoding=_UTF_8)
    return SurfaceUpdate(ROOT_PYPROJECT_RELATIVE, before, after)


def _bump_changelog(repo_root: Path, version: str, block: str, *, release_date: str) -> SurfaceUpdate:
    """Prepend the release block directly after the `## [Unreleased]` anchor."""
    path = repo_root / CHANGELOG_RELATIVE
    before = path.read_text(encoding=_UTF_8)
    if _UNRELEASED_HEADING not in before:
        raise VersionBumpError(f"{CHANGELOG_RELATIVE} is missing the '## [Unreleased]' anchor to prepend after")
    heading = f"## [{version}] - {release_date}\n"
    if f"## [{version}]" in before:
        raise VersionBumpError(f"{CHANGELOG_RELATIVE} already carries a section for {version}")
    normalized_block = block if block.endswith("\n") else f"{block}\n"
    insertion = f"\n{heading}\n{normalized_block}"
    after = before.replace(_UNRELEASED_HEADING, _UNRELEASED_HEADING + insertion, 1)
    path.write_text(after, encoding=_UTF_8)
    return SurfaceUpdate(CHANGELOG_RELATIVE, before, after)


def apply_version(
    repo_root: Path,
    version: str,
    *,
    changelog_block: str,
    release_date: str,
) -> tuple[SurfaceUpdate, ...]:
    """Apply *version* to all seven release declaration surfaces.

    Mirrors the seven numbered instructions the retiring `release-apply`
    justfile recipe printed for a human to transcribe: the release-please
    manifest, the three `pyproject.toml` versions, the package dunder
    version, both mandatory companion dependency pins (one surface), and the
    changelog block. Each surface is read, exactly-one-match substituted (or,
    for the manifest and changelog, structurally updated), and written; a
    surface with zero or more than one match refuses rather than silently
    touching the wrong thing or leaving a stale second occurrence behind.

    Raises:
        VersionBumpError: If any surface does not carry exactly the expected
            single version literal, if the changelog already carries a
            section for *version*, or if the build-stamped `.mcpb` manifest
            sentinel changed during the call.
    """
    mcpb_path = repo_root / MCPB_MANIFEST_RELATIVE
    mcpb_before = mcpb_path.read_text(encoding=_UTF_8)
    updates = (
        _bump_manifest(repo_root, version),
        _bump_pyproject_version(repo_root, ROOT_PYPROJECT_RELATIVE, version),
        _bump_pyproject_version(repo_root, DATA_MANUALS_PYPROJECT_RELATIVE, version),
        _bump_pyproject_version(repo_root, DATA_OFFICIAL_PYPROJECT_RELATIVE, version),
        _bump_init(repo_root, version),
        _bump_dependency_pins(repo_root, version),
        _bump_changelog(repo_root, version, changelog_block, release_date=release_date),
    )
    mcpb_after = mcpb_path.read_text(encoding=_UTF_8)
    if mcpb_after != mcpb_before:
        raise VersionBumpError(
            f"{MCPB_MANIFEST_RELATIVE} changed during the bump; it must stay the build-stamped sentinel "
            "that packaging/mcpb/build.py stamps over at build time",
        )
    return updates


def _run(argv: list[str], *, cwd: Path, timeout: int = _SUBPROCESS_TIMEOUT_S) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, refusing with its captured output on a non-zero exit."""
    try:
        completed = subprocess.run(  # noqa: S603 - argv is caller-controlled, fixed shape.
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise VersionBumpError(f"{argv[0]} is not on PATH: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VersionBumpError(f"{' '.join(argv)} timed out after {timeout}s") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "")[-4000:]
        raise VersionBumpError(f"{' '.join(argv)} failed (rc={completed.returncode}):\n{tail}")
    return completed
