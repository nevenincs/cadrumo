"""Version bump executor: the pipeline stage replacing the retired manual bump recipe.

The retired local recipe printed eleven instructions for a human to
transcribe by hand: compute the version, apply it to seven declaration
surfaces, regenerate and verify the lock, stage, commit, tag, and (on a
separate human decision) push. This module is that sequence made executable
and tested, so the release orchestrator's first job can run it without a
human re-typing seven file paths.

The version stays computed, never chosen, from conventional-commit history --
:func:`run_release_please_dry_run` shells out to the same `release-please@16
release-pr --dry-run --debug` invocation `just release` already runs, and
:func:`parse_computed_version` reads the version release-please decided on
rather than accepting one as a parameter. Every mutation is applied through
:func:`apply_version`, which refuses rather than guesses whenever a surface
does not carry exactly the one version literal it expects.

See Also:
    :func:`apply_version`
        The seven-surface mutation, mirroring the retired manual bump
        checklist's steps 1-7.
    :func:`dev.release.readiness.check_version_surfaces_agree`
        The parity check re-run after every bump so a transcription-class
        error cannot survive an automated one either.
    :func:`dev.release.version_identity.assert_version_available`
        The all-destination identity guard invoked before any ref leaves the
        runner.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from cadrumo.core.product_identity import PRODUCT_IDENTITY

from .._paths import REPO_ROOT, UTF_8
from . import readiness, version_identity

_UTF_8: Final[str] = UTF_8

#: The seven declaration surfaces the retired manual bump checklist printed
#: as steps 1-7,
#: relative to the repository root.
MANIFEST_RELATIVE: Final[Path] = Path(".release-please-manifest.json")
#: release-please's own config file, relative to the repository root -- see
#: `run_release_please_dry_run`'s docstring for why this MUST stay relative.
RELEASE_PLEASE_CONFIG_RELATIVE: Final[Path] = Path("release-please-config.json")
ROOT_PYPROJECT_RELATIVE: Final[Path] = Path("pyproject.toml")
DATA_MANUALS_PYPROJECT_RELATIVE: Final[Path] = Path("packaging/cadrumo_data_manuals/pyproject.toml")
DATA_OFFICIAL_PYPROJECT_RELATIVE: Final[Path] = Path("packaging/cadrumo_data_official/pyproject.toml")
INIT_RELATIVE: Final[Path] = Path("src/cadrumo/__init__.py")
CHANGELOG_RELATIVE: Final[Path] = Path("CHANGELOG.md")

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
            f"{surface} must declare exactly one version literal matching {pattern.pattern!r}, found {len(matches)}",
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
    path.write_text(after, encoding=_UTF_8, newline="\n")
    return SurfaceUpdate(MANIFEST_RELATIVE, before, after)


def _bump_pyproject_version(repo_root: Path, relative: Path, version: str) -> SurfaceUpdate:
    path = repo_root / relative
    before = path.read_text(encoding=_UTF_8)
    after = _substitute_single(before, _PYPROJECT_VERSION_RE, version, surface=str(relative))
    path.write_text(after, encoding=_UTF_8, newline="\n")
    return SurfaceUpdate(relative, before, after)


def _bump_init(repo_root: Path, version: str) -> SurfaceUpdate:
    path = repo_root / INIT_RELATIVE
    before = path.read_text(encoding=_UTF_8)
    after = _substitute_single(before, _INIT_VERSION_RE, version, surface=str(INIT_RELATIVE))
    path.write_text(after, encoding=_UTF_8, newline="\n")
    return SurfaceUpdate(INIT_RELATIVE, before, after)


def _bump_dependency_pins(repo_root: Path, version: str) -> SurfaceUpdate:
    """Bump both mandatory exact companion pins in the root `pyproject.toml`.

    Counted as ONE of the seven surfaces (the retired manual bump checklist's
    step 6 named both pins together), so this returns a single
    :class:`SurfaceUpdate` covering both substitutions.
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
    path.write_text(after, encoding=_UTF_8, newline="\n")
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
    path.write_text(after, encoding=_UTF_8, newline="\n")
    return SurfaceUpdate(CHANGELOG_RELATIVE, before, after)


def apply_version(
    repo_root: Path,
    version: str,
    *,
    changelog_block: str,
    release_date: str,
) -> tuple[SurfaceUpdate, ...]:
    """Apply *version* to all seven release declaration surfaces.

    Mirrors the seven numbered instructions the retired manual bump justfile
    recipe printed for a human to transcribe: the release-please
    manifest, the three `pyproject.toml` versions, the package dunder
    version, both mandatory companion dependency pins (one surface), and the
    changelog block. Each surface is read, exactly-one-match substituted (or,
    for the manifest and changelog, structurally updated), and written; a
    surface with zero or more than one match refuses rather than silently
    touching the wrong thing or leaving a stale second occurrence behind.

    Raises:
        VersionBumpError: If any surface does not carry exactly the expected
            single version literal, if the changelog already carries a
            section for *version*.
    """
    updates = (
        _bump_manifest(repo_root, version),
        _bump_pyproject_version(repo_root, ROOT_PYPROJECT_RELATIVE, version),
        _bump_pyproject_version(repo_root, DATA_MANUALS_PYPROJECT_RELATIVE, version),
        _bump_pyproject_version(repo_root, DATA_OFFICIAL_PYPROJECT_RELATIVE, version),
        _bump_init(repo_root, version),
        _bump_dependency_pins(repo_root, version),
        _bump_changelog(repo_root, version, changelog_block, release_date=release_date),
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


def regenerate_and_verify_lock(repo_root: Path, *, uv_executable: str | None = None) -> None:
    """Regenerate `uv.lock`, then verify it via `uv lock --check`.

    Mirrors the retired manual bump checklist's step 8: the pins
    :func:`apply_version` just rewrote must resolve into a lock the fail-closed
    `uv lock --check` gate accepts, catching a resolution failure or a drifted
    lock before anything is staged or committed.
    """
    uv = uv_executable or shutil.which("uv")
    if uv is None:
        raise VersionBumpError("uv is not on PATH; cannot regenerate or verify the lock")
    _run([uv, "lock"], cwd=repo_root)
    _run([uv, "lock", "--check"], cwd=repo_root)


def verify_bump(repo_root: Path) -> None:
    """Re-run the version-surfaces-agree readiness check after a bump.

    The transcription-error class :func:`dev.release.readiness.check_version_surfaces_agree`
    exists to catch cannot survive an automated bump either -- whatever the
    cause (a future :func:`apply_version` defect, an interrupted partial
    write, or a hand edit landing between the bump and this check).
    """
    check = readiness.check_version_surfaces_agree(repo_root)
    if not check.passed:
        raise VersionBumpError(f"post-bump readiness re-check failed: {check.detail}")


def stage_bump(
    repo_root: Path,
    version: str,
    *,
    changelog_block: str,
    release_date: str,
    uv_executable: str | None = None,
) -> tuple[SurfaceUpdate, ...]:
    """Apply *version*, regenerate and verify the lock, then re-verify parity.

    Composes steps 1-8 of the retired manual bump checklist. Nothing
    here touches git: a failure at any stage leaves the working tree mutated
    but never staged or committed, because the commit/tag/push stage only
    runs after this returns successfully.
    """
    updates = apply_version(repo_root, version, changelog_block=changelog_block, release_date=release_date)
    regenerate_and_verify_lock(repo_root, uv_executable=uv_executable)
    verify_bump(repo_root)
    return updates


#: The bumped surfaces plus the regenerated lock, staged for the release
#: commit. Mirrors the retired manual bump checklist's step 9 explicit
#: `git add` file list exactly.
_STAGED_RELATIVE_PATHS: Final[tuple[Path, ...]] = (
    MANIFEST_RELATIVE,
    ROOT_PYPROJECT_RELATIVE,
    DATA_MANUALS_PYPROJECT_RELATIVE,
    DATA_OFFICIAL_PYPROJECT_RELATIVE,
    INIT_RELATIVE,
    CHANGELOG_RELATIVE,
    Path("uv.lock"),
)


#: Known shapes a release-please `release-pr --dry-run --debug` log can
#: announce its computed version in. Deliberately conservative: an
#: unrecognised shape refuses (:func:`parse_computed_version`) rather than
#: guessing. The first two are VERIFIED against a real successful dry-run
#: (2026-08-02, `nevenincs/cadrumo` @ `ac6305809d`, computed `0.2.0` from
#: `v0.1.0`): the collapsible PR-body summary tag and the changelog
#: comparison heading it renders. The PR title itself carries no version in
#: this repo's config (`pullRequestTitlePattern miss the part of
#: '${version}'` -- a `pull-request-title-pattern` gap worth tidying
#: separately, not required for this to work), so the trailing two patterns
#: -- retained as a defensive fallback for a differently-configured
#: release-please run -- are unverified against real output.
_VERSION_ANNOUNCEMENT_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"<summary>(?P<version>[0-9][^<]*)</summary>"),
    re.compile(r"##\s*\[(?P<version>[0-9][^\]]*)\]\(https://[^)]*/compare/[^)]*\)\s*\(\d{4}-\d{2}-\d{2}\)"),
    re.compile(r'"version"\s*:\s*"(?P<version>[0-9][^"]*)"'),
    re.compile(r"chore\(?[\w.-]*\)?!?:\s*release\s+(?P<version>[0-9][^\s\"]*)", re.IGNORECASE),
)


def run_release_please_dry_run(
    repo_root: Path,
    *,
    token: str,
    repository: str,
    npx_executable: str | None = None,
    target_branch: str = "main",
    config_file: Path | None = None,
    manifest_file: Path | None = None,
    timeout: int = _SUBPROCESS_TIMEOUT_S,
) -> str:
    """Run release-please in dry-run/debug mode and return its raw output log.

    Shells out to the same `release-please@16 release-pr --dry-run --debug`
    invocation `just release` already runs.

    Refuses instructively, before ever attempting `npx`, when `node` is
    absent from the runner -- release-please shells out through `npx`, and
    whether the self-hosted fleet carries a Node.js toolchain is unverified.

    `config_file` / `manifest_file`, when supplied, MUST be paths relative to
    the repository root, never absolute local filesystem paths: `--repo-url`
    puts release-please into its GitHub-API remote-fetch mode, where these
    flags are repo-relative strings used to fetch the named files from
    `target_branch`, not local paths on this machine. Confirmed live: an
    absolute path here makes release-please refuse with "Missing required
    manifest config: <path>" because that string never matches anything in
    the fetched tree.

    Grounding note, VERIFIED LIVE (2026-08-02, `nevenincs/cadrumo` @
    `ac6305809d`): this repository has no prior release-please-generated
    release (this is its first automated bump), so release-please finds no
    GitHub Release matching the manifest's recorded version and falls back
    to walking commit history one commit at a time. Early grounding runs
    against a shorter (~700-commit) history died on genuine GitHub API
    504/503s before completing; against this repo's current, longer history
    a live run completed cleanly (`rc=0`) in under five minutes, computing
    `0.2.0` from `v0.1.0`. The walk is bounded by release-please's own
    `commit-search-depth` (default 500, confirmed by the live log: exactly
    500 commits backfilled, well short of the top-level `bootstrap-sha`
    config key's target commit) -- so on the run that actually succeeded,
    the earlier `bootstrap-sha` addition was not what bounded the walk;
    `commit-search-depth`'s own default was. `bootstrap-sha` stays set
    (release-please's own documented answer to a first run with no prior
    release, and self-retiring once a release PR it generated merges) since
    it can only help, not hurt, and the one live run available is not
    sufficient evidence to rule out the earlier failures having been
    ordinary transient GitHub API instability rather than something
    `bootstrap-sha` specifically fixed. The function itself still runs and
    refuses correctly on every locally observable failure (missing node,
    missing npx, a non-zero exit, or a timeout) regardless of the cause.
    """
    if shutil.which("node") is None:
        raise VersionBumpError(
            "node is not on PATH; release-please shells out through npx and needs a Node.js "
            "runtime -- provision node on this runner (OP-11) before retrying",
        )
    npx = npx_executable or shutil.which("npx")
    if npx is None:
        raise VersionBumpError("npx is not on PATH; cannot invoke release-please")
    # RELATIVE, never joined onto repo_root: `--repo-url` puts release-please
    # into its GitHub-API remote-fetch manifest mode, where `--config-file` /
    # `--manifest-file` are repo-relative path STRINGS used to fetch the
    # files from `target_branch` via the API, not local filesystem paths (see
    # the grounding note above). An absolute local path never matches
    # anything in the fetched tree and release-please refuses with
    # "Missing required manifest config: <path>" -- confirmed live.
    config = config_file if config_file is not None else RELEASE_PLEASE_CONFIG_RELATIVE
    manifest = manifest_file if manifest_file is not None else MANIFEST_RELATIVE
    completed = _run(
        [
            npx,
            "--yes",
            "release-please@16",
            "release-pr",
            "--token",
            token,
            "--repo-url",
            repository,
            "--target-branch",
            target_branch,
            "--config-file",
            str(config),
            "--manifest-file",
            str(manifest),
            "--dry-run",
            "--debug",
        ],
        cwd=repo_root,
        timeout=timeout,
    )
    return f"{completed.stdout}\n{completed.stderr}"


def parse_computed_version(log: str) -> str:
    """Extract the version release-please decided on from its dry-run log.

    The first two entries in `_VERSION_ANNOUNCEMENT_PATTERNS` are VERIFIED
    against a real successful run (see :func:`run_release_please_dry_run`'s
    grounding note); this function correctly extracts `0.2.0` from that run's
    real log. It is deliberately conservative regardless: it tries a small
    set of known release-please output shapes and refuses outright rather
    than guessing when none match, so a log shape this parser does not
    recognise fails LOUDLY (a refusal) instead of silently returning a wrong
    version.

    Raises:
        VersionBumpError: If no recognised version announcement is found.
    """
    for pattern in _VERSION_ANNOUNCEMENT_PATTERNS:
        match = pattern.search(log)
        if match:
            return match.group("version")
    raise VersionBumpError(
        "could not determine the computed version from the release-please dry-run output; "
        "no recognised version announcement was found in the log",
    )


def _manifest_floor_at_head(repo_root: Path, *, git_executable: str) -> str:
    """Return the manifest floor as committed at HEAD, before this bump.

    Deliberately reads HEAD's blob rather than the working-tree file: by the
    time this is called, `apply_version` has already rewritten the
    working-tree manifest to the candidate version.
    """
    completed = _run([git_executable, "show", f"HEAD:{MANIFEST_RELATIVE.as_posix()}"], cwd=repo_root)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VersionBumpError(f"HEAD's {MANIFEST_RELATIVE} is not valid JSON: {exc}") from exc
    recorded = payload.get(".") if isinstance(payload, dict) else None
    if not isinstance(recorded, str) or not recorded.strip():
        raise VersionBumpError(f"HEAD's {MANIFEST_RELATIVE} records no root version")
    return recorded


def commit_tag_and_push(
    repo_root: Path,
    version: str,
    *,
    repository: str,
    git_executable: str | None = None,
    push: bool = False,
    skip_network: bool = False,
    own_source_commit: str | None = None,
) -> str:
    """Guard, then commit, tag, and (only when `push` is True) push the bump.

    The all-destination identity guard (`dev.release.version_identity`) runs
    BEFORE any ref leaves the runner -- before even the local commit -- so a
    version an index, the tag/release namespace, the burned ledger, or the
    manifest floor already owns refuses before a tag exists rather than
    after. This mirrors the retired manual bump checklist's steps 9-11.

    `push` defaults to False: local commit and tag only, matching the
    non-local/CI-only push leg (a real `git push` needs a real remote and
    real credentials, which a unit test does not have); the orchestrator
    passes `push=True` only inside CI, where a push is meaningful and safe
    to attempt because the guard above already ran.

    `skip_network` mirrors `dev.release.version_identity.main`'s own
    `--skip-network` flag exactly: when set, only the burned ledger and the
    manifest floor are checked (no live PyPI/forge queries), which is what
    lets the burned-version and below-floor refusal cases run offline and
    deterministically in tests.

    Returns:
        The SHA of the commit created.

    Raises:
        VersionBumpError: If `git` is unresolvable or any git subprocess
            fails.
        version_identity.VersionIdentityError: If the version collides with
            any destination the identity guard checks.
    """
    git = git_executable or shutil.which("git")
    if git is None:
        raise VersionBumpError("git is not on PATH; cannot commit, tag, or push the bump")

    # `apply_version` already rewrote the working-tree manifest to *version*
    # by the time this stage runs (stage_bump precedes commit_tag_and_push in
    # the orchestration), so reading the floor from the working tree would
    # tautologically compare the candidate against itself. HEAD's committed
    # manifest -- the state before this bump's working-tree changes -- is the
    # floor the guard must check against.
    floor = _manifest_floor_at_head(repo_root, git_executable=git)

    owning: tuple[str, ...] = ()
    existing_tags: tuple[str, ...] = ()
    existing_releases: tuple[str, ...] = ()
    if not skip_network:
        owning = version_identity.pypi_projects_owning(version)
        existing_tags = version_identity.forge_tags_owning(version, repository=repository)
        existing_releases = version_identity.forge_releases_owning(
            version,
            repository=repository,
            own_source_commit=own_source_commit,
        )
    refusals = version_identity.version_conflicts(
        version,
        owning_projects=owning,
        existing_tags=existing_tags,
        existing_releases=existing_releases,
        floor=floor,
    )
    if refusals:
        joined = "\n  - ".join(refusals)
        raise version_identity.VersionIdentityError(f"version {version} is not available to publish:\n  - {joined}")

    tag_name = f"v{version}"
    # `-c` rather than a persisted `git config` call: this repo is the real
    # checkout (or, under a rehearsal, the disposable copy that already seeded
    # its own persisted identity), and a runner image carries no default git
    # identity, so both a bare `git commit` and the annotated `git tag -a`
    # fail when this stage first runs. The same bot identity the account's
    # other automated commits (the Scoop/Homebrew tap pushes) already use.
    identity = ["-c", "user.name=cadrumo-release", "-c", "user.email=release@cadrumo.invalid"]
    _run([git, "add", "--", *(str(relative) for relative in _STAGED_RELATIVE_PATHS)], cwd=repo_root)
    _run([git, *identity, "commit", "-m", f"chore(release): v{version}"], cwd=repo_root)
    commit_sha = _run([git, "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
    _run([git, *identity, "tag", "-a", tag_name, "-m", f"Cadrumo {tag_name}"], cwd=repo_root)
    if push:
        _run([git, "push", "origin", "main"], cwd=repo_root)
        _run([git, "push", "origin", f"refs/tags/{tag_name}"], cwd=repo_root)
    return commit_sha


#: Directories excluded from the rehearsal's repository copy: none of them
#: are read by `apply_version`, `regenerate_and_verify_lock`, or the identity
#: guard, and skipping them keeps the discarded copy cheap.
_REHEARSAL_COPY_EXCLUDED_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".venv",
        "var",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
        "htmlcov",
    },
)


def _ignore_rehearsal_copy_dirs(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _REHEARSAL_COPY_EXCLUDED_DIRS}


def rehearse_bump(
    repo_root: Path,
    version: str,
    *,
    changelog_block: str,
    release_date: str,
    repository: str,
    uv_executable: str | None = None,
    git_executable: str | None = None,
    skip_network: bool = False,
    own_source_commit: str | None = None,
) -> None:
    """Exercise the real bump mechanics against a discarded temporary tree.

    A rehearsal must prove what its own prose and the decision record both
    claim it proves -- that the computed version would survive the
    seven-surface mutation, the lock regeneration, the parity re-check, and
    the all-destination identity guard -- not merely that a version could be
    computed. Returning immediately after :func:`parse_computed_version`
    proves nothing about any of those; in particular it cannot surface an
    owned, burned, or below-floor version before a real dispatch, which is
    the class of refusal an operator would most want to see in a rehearsal.

    Copies `repo_root` (excluding `.git`, `.venv`, build/cache directories,
    and `var/`) into a fresh temporary directory, seeds a throwaway git
    history there (so the identity guard's HEAD-anchored floor lookup has
    something to read), runs the real `stage_bump` +
    `commit_tag_and_push(push=False)` sequence against that COPY, then
    unconditionally discards the directory. The real `repo_root` is never
    written to and no real ref is ever created; `commit_tag_and_push`'s
    network identity checks (unless `skip_network`) still query the REAL
    `repository` remote, because that is the destination a real dispatch
    would check against -- only the git mutations (commit, tag) land on the
    disposable copy.

    Raises:
        VersionBumpError: If any surface refuses, the lock fails to
            regenerate or verify, or the post-bump parity re-check fails.
        version_identity.VersionIdentityError: If the version collides with
            any destination the identity guard checks.
    """
    with tempfile.TemporaryDirectory(prefix="cadrumo-release-rehearsal-") as tmp:
        rehearsal_root = Path(tmp) / "repo"
        shutil.copytree(repo_root, rehearsal_root, ignore=_ignore_rehearsal_copy_dirs)

        git = git_executable or shutil.which("git")
        if git is None:
            raise VersionBumpError("git is not on PATH; cannot rehearse the bump")
        _run([git, "init", "-q", "-b", "main"], cwd=rehearsal_root)
        # Persisted into the rehearsal repo's OWN local config (not `-c`, which
        # only scopes one invocation) so every later commit in this disposable
        # tree -- including the one `commit_tag_and_push` makes below, which
        # runs no differently here than it would against the real repo -- has
        # a valid identity. Runner images ship no default git identity, so a
        # bare `git commit` with no persisted config fails "Author identity
        # unknown" the first time a rehearsal reaches its own bump commit.
        _run([git, "config", "user.email", "rehearsal@cadrumo.invalid"], cwd=rehearsal_root)
        _run([git, "config", "user.name", "rehearsal"], cwd=rehearsal_root)
        _run([git, "add", "-A"], cwd=rehearsal_root)
        _run([git, "commit", "-q", "-m", "rehearsal seed"], cwd=rehearsal_root)

        stage_bump(
            rehearsal_root,
            version,
            changelog_block=changelog_block,
            release_date=release_date,
            uv_executable=uv_executable,
        )
        commit_tag_and_push(
            rehearsal_root,
            version,
            repository=repository,
            git_executable=git,
            push=False,
            skip_network=skip_network,
            own_source_commit=own_source_commit,
        )
        # Falling off the `with` block deletes `tmp` (and everything under
        # `rehearsal_root`) unconditionally, success or refusal alike.


def _changelog_block_for(version: str, log: str) -> str:
    """Return the changelog body release-please computed, or a minimal stand-in.

    release-please's dry-run log is the authority for the release notes. When
    the log carries no recognisable body the block degrades to the version
    heading alone rather than fabricating entries: an invented changelog is a
    claim about what shipped, and inventing one is worse than a thin one.
    """
    match = re.search(rf"###?\s*\[?{re.escape(version)}\]?.*?(?=\n#{{2,3}}\s|\Z)", log, re.DOTALL)
    return match.group(0).strip() if match else f"## {version}"


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the version bump as one pipeline stage.

    This is the entry point the release orchestrator invokes. It composes the
    library functions above in the order the retired manual bump checklist
    printed for a human: compute the version from conventional-commit history,
    apply it to all seven declaration surfaces, regenerate and verify the lock,
    re-check parity, then guard, commit, tag, and push.

    The version stays COMPUTED, never chosen: there is deliberately no
    `--version` flag, because a hand-supplied version is the transcription
    error class the whole bump stage exists to remove.

    `--dry-run` runs the real mutation and identity-guard logic against a
    discarded temporary copy of the repository (:func:`rehearse_bump`) rather
    than skipping straight to a printed version, so the rehearsal proves this
    stage rather than merely computing a number: it can surface an owned,
    burned, or below-floor version, a surface refusal, or a lock-regeneration
    failure before a real dispatch, while touching no surface and leaving no
    ref in the real repository.
    """
    parser = argparse.ArgumentParser(description="Bump every release declaration surface and land the release commit.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT", ""))
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT
    if not args.token:
        raise VersionBumpError("a forge token is required to compute the next version; pass --token or set GH_TOKEN")

    log = run_release_please_dry_run(repo_root, token=args.token, repository=args.repository)
    version = parse_computed_version(log)

    if args.dry_run:
        rehearse_bump(
            repo_root,
            version,
            changelog_block=_changelog_block_for(version, log),
            release_date=datetime.now(UTC).date().isoformat(),
            repository=args.repository,
        )
        print(
            f"dry-run: {version} passed the seven-surface mutation, lock regeneration, parity re-check, "
            "and identity guard; no surface written, no ref created",
        )
        _emit_bump_outputs(args.github_output, version=version, commit="")
        return 0

    stage_bump(
        repo_root,
        version,
        changelog_block=_changelog_block_for(version, log),
        release_date=datetime.now(UTC).date().isoformat(),
    )
    commit_sha = commit_tag_and_push(repo_root, version, repository=args.repository, push=args.push)
    print(f"bumped to {version} at {commit_sha}")
    _emit_bump_outputs(args.github_output, version=version, commit=commit_sha)
    return 0


def _emit_bump_outputs(github_output: str, *, version: str, commit: str) -> None:
    """Publish the bumped version and commit as workflow outputs.

    Downstream stages READ these rather than re-deriving them. Re-deriving is
    how a campaign ends up building a different commit than the one the bump
    landed.
    """
    if not github_output:
        return
    with Path(github_output).open("a", encoding=_UTF_8, newline="\n") as handle:
        handle.write(f"version={version}\n")
        handle.write(f"commit={commit}\n")


if __name__ == "__main__":
    raise SystemExit(main())
