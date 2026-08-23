"""Audit-state readiness gate run before a release bump is trusted.

Checks a small set of deterministic, release-blocking invariants and reports
a single machine-readable verdict. This module performs **no outward
action** — it reads local files and, best-effort, queries the GitHub issue
tracker read-only via `gh`. It never tags, pushes, or publishes anything;
those steps stay entirely human-run per RELEASING.md.

Two severities distinguish a hard release blocker from an advisory note:

* ``blocking`` — the check is a deterministic release invariant (version-surface
  parity, changelog presence, complete cohort-bound distribution evidence). A failure here is a real
  release defect and the gate exits non-zero.
* ``advisory`` — the check depends on live external state (GitHub API
  reachability).
  A failure here is reported but does not fail the gate, because the signal
  is legitimately absent in a fresh checkout or offline environment.

See `docs/_release_checklist.yaml` (the `audit_state_gate` section) for the
checklist item this gate implements, and `RELEASING.md` for where it sits in
the per-release sequence.

See Also:
    :class:`ReadinessReport`
        Aggregate verdict returned by :func:`build_report` and serialized by
        the CLI.
    :func:`check_version_surfaces_agree`
        Blocking local version-surface parity check.
    :func:`check_changelog_is_ready`
        Blocking changelog presence and merge-marker check.
    :func:`check_distribution_evidence_set`
        Blocking exact-cohort evidence check for every required release row.
    :func:`check_no_open_release_blockers`
        GitHub-backed audit-state blocker check that degrades when live state
        cannot be read.
    :func:`main`
        CLI entrypoint used by the release readiness recipe.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

from pydantic import ValidationError

from cadrumo.core import PRODUCT_IDENTITY, scan_directory
from dev._paths import REPO_ROOT, UTF_8

from ..docs.download_matrix import load_descriptor, required_evidence_rows
from ..packaging.cohort_manifest import load_release_cohort
from ..packaging.evidence import (
    DistributionEvidence,
    EvidenceStatus,
    PackagingSmokeManifest,
    load_distribution_evidence,
)
from ..packaging.python_cohort import load_python_cohort

_UTF_8: Final = UTF_8
_VERSION_RE: Final = re.compile(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
_BLOCKER_LABEL: Final = "priority:P0-blocker"
_GH_TIMEOUT_SECONDS: Final = 15
_PROJECT_NAME_PATHS: Final = (
    (Path("pyproject.toml"), PRODUCT_IDENTITY.distribution),
    (Path("packaging/cadrumo_data_manuals/pyproject.toml"), PRODUCT_IDENTITY.companion_distributions[0]),
    (Path("packaging/cadrumo_data_official/pyproject.toml"), PRODUCT_IDENTITY.companion_distributions[1]),
)


def _repo_root() -> Path:
    """Return the repository root two levels above this module."""
    return REPO_ROOT


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    """One evaluated readiness-gate check."""

    name: str
    severity: str  # "blocking" | "advisory"
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    """The full audit-state gate verdict."""

    checks: tuple[ReadinessCheck, ...] = field(default_factory=tuple)

    @property
    def blocking_failures(self) -> tuple[ReadinessCheck, ...]:
        """Return every failed check whose severity is blocking."""
        return tuple(c for c in self.checks if c.severity == "blocking" and not c.passed)

    @property
    def advisory_failures(self) -> tuple[ReadinessCheck, ...]:
        """Return every failed check whose severity is advisory."""
        return tuple(c for c in self.checks if c.severity == "advisory" and not c.passed)

    @property
    def ok(self) -> bool:
        """Return whether the release may proceed (no blocking failure)."""
        return not self.blocking_failures

    def to_dict(self) -> dict[str, object]:
        """Return a machine-readable summary of the report."""
        return {
            "ok": self.ok,
            "checks": [
                {
                    "name": c.name,
                    "severity": c.severity,
                    "passed": c.passed,
                    "detail": c.detail,
                }
                for c in self.checks
            ],
        }


def _read_project_version(project_file: Path) -> str:
    data = tomllib.loads(project_file.read_text(encoding=_UTF_8))
    return str(data["project"]["version"])


def _read_project_name(project_file: Path) -> str:
    data = tomllib.loads(project_file.read_text(encoding=_UTF_8))
    return str(data["project"]["name"])


def check_project_names_are_canonical(repo_root: Path) -> ReadinessCheck:
    """Require the root and both companion distributions to use the Cadrumo tuple."""
    observed = tuple(
        (relative, _read_project_name(repo_root / relative), expected) for relative, expected in _PROJECT_NAME_PATHS
    )
    mismatches = tuple((relative, actual, expected) for relative, actual, expected in observed if actual != expected)
    if mismatches:
        detail = "; ".join(
            f"{relative}: found {actual!r}, expected {expected!r}" for relative, actual, expected in mismatches
        )
        return ReadinessCheck("project-names-canonical", "blocking", False, detail)
    names = ", ".join(actual for _relative, actual, _expected in observed)
    return ReadinessCheck("project-names-canonical", "blocking", True, f"canonical distributions: {names}")


def _read_init_version(repo_root: Path) -> str:
    text = (repo_root / "src" / "cadrumo" / "__init__.py").read_text(encoding=_UTF_8)
    match = _VERSION_RE.search(text)
    if not match:
        return ""
    return str(match.group(1))


def _read_manifest_version(repo_root: Path) -> str:
    payload = json.loads((repo_root / ".release-please-manifest.json").read_text(encoding=_UTF_8))
    return str(payload.get(".", ""))


#: Every row any channel can produce, whether or not this release claims it.
#: Derived from the channel descriptor so a channel's proof obligation is
#: declared in exactly one place.
ALL_DISTRIBUTION_ROWS: Final[tuple[str, ...]] = tuple(
    sorted({row for channel in load_descriptor().channel for row in channel.evidence_rows}),
)

#: The rows THIS release must prove: the union over the channels it actually
#: claims, floored at the language-native registry. Evidence is proportional to
#: claims — an unclaimed channel no longer blocks a claimed one — but no gate is
#: weakened and no row is removed: a channel still cannot be claimed without its
#: passing row, and flipping a channel to `available` in the descriptor
#: immediately re-arms every row it owns.
REQUIRED_DISTRIBUTION_ROWS: Final[tuple[str, ...]] = required_evidence_rows(load_descriptor())

def _require_json_object(payload: object, *, surface: str) -> dict[str, object]:
    """Return a decoded JSON object or refuse the named release surface."""
    if not isinstance(payload, dict):
        raise ValueError(f"{surface} must be a JSON object")
    return cast(dict[str, object], payload)


def check_version_surfaces_agree(repo_root: Path) -> ReadinessCheck:
    """Confirm every release authority and mandatory companion pin reports one version."""
    project_versions = tuple(
        (relative, _read_project_version(repo_root / relative)) for relative, _expected_name in _PROJECT_NAME_PATHS
    )
    pyproject_version = project_versions[0][1]
    init_version = _read_init_version(repo_root)
    manifest_version = _read_manifest_version(repo_root)
    root_project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding=_UTF_8))
    observed_pins = tuple(
        str(requirement)
        for requirement in root_project["project"]["dependencies"]
        if any(str(requirement).startswith(distribution) for distribution in PRODUCT_IDENTITY.companion_distributions)
    )
    expected_pins = tuple(
        f"{distribution}=={pyproject_version}" for distribution in PRODUCT_IDENTITY.companion_distributions
    )
    versions = {version for _relative, version in project_versions} | {init_version, manifest_version}
    passed = len(versions) == 1 and bool(pyproject_version) and observed_pins == expected_pins
    surfaces = " ".join(f"{relative}={version!r}" for relative, version in project_versions)
    detail = (
        f"{surfaces} init={init_version!r} manifest={manifest_version!r} pins={observed_pins!r}"
    )
    if passed:
        detail = (
            "all release authorities and mandatory exact companion dependencies agree on "
            f"{pyproject_version!r}"
        )
    return ReadinessCheck("version-surfaces-agree", "blocking", passed, detail)


def check_changelog_is_ready(repo_root: Path) -> ReadinessCheck:
    """Confirm CHANGELOG.md exists, is non-empty, and carries no merge-conflict markers."""
    changelog = repo_root / "CHANGELOG.md"
    if not changelog.is_file():
        return ReadinessCheck("changelog-ready", "blocking", False, f"{changelog} is missing")
    text = changelog.read_text(encoding=_UTF_8)
    if not text.strip():
        return ReadinessCheck("changelog-ready", "blocking", False, "CHANGELOG.md is empty")
    conflict_markers = ("<<<<<<<", "=======", ">>>>>>>")
    found = [marker for marker in conflict_markers if marker in text]
    if found:
        return ReadinessCheck(
            "changelog-ready",
            "blocking",
            False,
            f"CHANGELOG.md carries unresolved merge markers: {found}",
        )
    return ReadinessCheck("changelog-ready", "blocking", True, "CHANGELOG.md present, non-empty, no merge markers")


def check_no_open_release_blockers(
    *, repo_slug: str = "nevenincs/cadrumo", gh_executable: str | None = None, strict: bool = False
) -> ReadinessCheck:
    """Confirm no open GitHub issue carries the `priority:P0-blocker` label.

    When `strict` is False (a local/advisory run) this degrades gracefully
    (reported, non-blocking) when `gh` is absent, unauthenticated, the network
    is unreachable, or the output is not JSON, since it depends on live external
    state rather than repository content.

    When `strict` is True (the Gate-2 publish path, which HAS network and must
    not promote past a blocker it could not see) an inability to DETERMINE the
    blocker state is itself blocking: a fail-open advisory there would let the
    gate pass while blind. The escalation is only for *cannot-determine*; a
    successful query that finds open blockers is blocking in both modes.

    `gh_executable` accepts an explicit resolved path (used by tests to
    exercise a real, non-mocked stub executable without depending on the
    host platform's PATH/PATHEXT executable-resolution rules); production
    callers resolve the real `gh` via `shutil.which`.
    """
    undetermined_severity = "blocking" if strict else "advisory"

    def _undetermined(detail: str) -> ReadinessCheck:
        prefix = "cannot determine blocker state: " if strict else ""
        return ReadinessCheck("no-open-release-blockers", undetermined_severity, False, f"{prefix}{detail}")

    resolved_gh = gh_executable if gh_executable is not None else shutil.which("gh")
    if resolved_gh is None:
        return _undetermined("gh unavailable: not found on PATH")
    try:
        result = subprocess.run(
            [
                resolved_gh,
                "issue",
                "list",
                "--repo",
                repo_slug,
                "--label",
                _BLOCKER_LABEL,
                "--state",
                "open",
                "--json",
                "number,title",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _undetermined(f"gh unavailable: {exc}")
    if result.returncode != 0:
        return _undetermined(f"gh issue list failed (rc={result.returncode}): {result.stderr.strip()[:200]}")
    try:
        issues = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return _undetermined("gh returned non-JSON output")
    if issues:
        titles = ", ".join(f"#{i['number']} {i['title']}" for i in issues[:5])
        return ReadinessCheck(
            "no-open-release-blockers",
            "blocking",
            False,
            f"{len(issues)} open {_BLOCKER_LABEL} issue(s): {titles}",
        )
    return ReadinessCheck("no-open-release-blockers", "advisory", True, f"no open {_BLOCKER_LABEL} issues")


def check_latest_packaging_smoke_evidence(repo_root: Path) -> ReadinessCheck:
    """Confirm the most recent packaging-smoke manifest, if any, reports success.

    Advisory: a fresh checkout has never run `just packaging-smoke*`, so
    absence of evidence is reported but does not block the gate.
    """
    smoke_dir = repo_root / "var" / "packaging-smoke"
    evidence_dir = repo_root / "var" / "packaging-smoke-evidence"
    manifests = sorted(
        (*smoke_dir.glob("*/packaging-smoke-manifest.json"), *evidence_dir.glob("*.json")),
        key=lambda path: path.stat().st_mtime,
    )
    if not manifests:
        return ReadinessCheck(
            "packaging-smoke-evidence",
            "advisory",
            False,
            "no packaging-smoke manifest found under var/packaging-smoke or its evidence checkpoint — "
            "run `just packaging-smoke` first",
        )
    latest = manifests[-1]
    try:
        manifest = PackagingSmokeManifest.model_validate_json(latest.read_text(encoding=_UTF_8))
    except (json.JSONDecodeError, ValidationError, UnicodeDecodeError) as exc:
        return ReadinessCheck(
            "packaging-smoke-evidence",
            "advisory",
            False,
            f"{latest} is not a valid packaging-smoke manifest: {exc}",
        )
    run_label = latest.stem if latest.parent == evidence_dir else latest.parent.name
    return ReadinessCheck(
        "packaging-smoke-evidence",
        "advisory",
        manifest.ok,
        f"most recent manifest ({run_label}, lane={manifest.lane}) ok={manifest.ok}",
    )


def _checked_out_commit(repo_root: Path) -> str:
    """Return the exact Git commit whose release readiness is being evaluated."""
    git = shutil.which("git")
    if git is None:
        raise ValueError("cannot resolve checked-out Git commit: git is not installed")
    completed = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=_GH_TIMEOUT_SECONDS,
    )
    commit = completed.stdout.strip().lower()
    if completed.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        detail = completed.stderr.strip()[:200] or completed.stdout.strip()[:200]
        raise ValueError(f"cannot resolve checked-out Git commit: {detail}")
    return commit


def _passing_identity(record: DistributionEvidence) -> tuple[object, ...]:
    """The subset of a passing record's identity that must agree across re-runs.

    Excludes fields expected to legitimately vary across independent re-runs
    of the identical row (``evidence_id``, ``observed_at``, ``commands``, the
    ephemeral ``destination.locator``) so a routine re-run is never mistaken
    for a conflict; keeps the fields that would signal a genuinely different
    row occupant -- which platform ran it, which client claims it, what kind
    of destination it targets.
    """
    client = record.client
    return (
        record.runtime.operating_system,
        record.runtime.architecture,
        client.name if client is not None else None,
        client.version if client is not None else None,
        client.executable if client is not None else None,
        record.destination.kind,
    )


def _select_canonical_passing_evidence(
    records: Sequence[DistributionEvidence],
) -> tuple[dict[str, DistributionEvidence], tuple[str, ...]]:
    """Pick one canonical passing record per row_id, or report conflicts.

    The evidence writer intentionally permits distinct immutable files for
    the same row (a re-run never overwrites a prior capture), so more than
    one passing record per ``row_id`` is an expected, legitimate shape as
    long as every record agrees on :func:`_passing_identity`; the most
    recently observed one is then canonical. Two passing records
    disagreeing on that identity are a genuine ambiguity -- which platform,
    which client -- and must block rather than silently collapse into a
    bare ``row_id`` set.
    """
    by_row: dict[str, list[DistributionEvidence]] = {}
    for record in records:
        if record.result.status is EvidenceStatus.PASSED:
            by_row.setdefault(record.row_id, []).append(record)

    canonical: dict[str, DistributionEvidence] = {}
    conflicts: list[str] = []
    for row_id, group in sorted(by_row.items()):
        identities = {_passing_identity(record) for record in group}
        if len(identities) > 1:
            conflicting_ids = sorted(record.evidence_id for record in group)
            conflicts.append(
                f"{row_id} ({len(group)} passing records, {len(identities)} distinct identities): {conflicting_ids!r}",
            )
            continue
        canonical[row_id] = max(group, key=lambda record: record.observed_at)
    return canonical, tuple(conflicts)


def check_distribution_evidence_set(
    repo_root: Path,
    *,
    cohort_directory: Path | None = None,
    evidence_directory: Path | None = None,
    required_rows: tuple[str, ...] = REQUIRED_DISTRIBUTION_ROWS,
) -> ReadinessCheck:
    """Require passing, exact-cohort evidence for every declared release row."""
    cohort_root = cohort_directory or repo_root / "var" / "release-cohort"
    evidence_root = evidence_directory or repo_root / "var" / "distribution-install-readiness"
    try:
        cohort = load_release_cohort(cohort_root)
        checked_out_commit = _checked_out_commit(repo_root)
    except (OSError, SystemExit, ValueError) as exc:
        return ReadinessCheck("distribution-evidence-complete", "blocking", False, str(exc))

    manifest = cohort.manifest
    expected_tag = f"v{manifest.version}"
    if manifest.source.commit != checked_out_commit:
        return ReadinessCheck(
            "distribution-evidence-complete",
            "blocking",
            False,
            f"cohort commit {manifest.source.commit} does not match checked-out commit {checked_out_commit}",
        )
    if manifest.source.tag != expected_tag:
        return ReadinessCheck(
            "distribution-evidence-complete",
            "blocking",
            False,
            f"cohort tag {manifest.source.tag!r} does not match version tag {expected_tag!r}",
        )
    if not evidence_root.is_dir():
        return ReadinessCheck(
            "distribution-evidence-complete",
            "blocking",
            False,
            f"distribution evidence directory is missing: {evidence_root}",
        )

    paths = scan_directory(evidence_root, pattern="*.json")
    if not paths:
        return ReadinessCheck(
            "distribution-evidence-complete",
            "blocking",
            False,
            f"distribution evidence directory is empty: {evidence_root}",
        )

    records = []
    for path in paths:
        try:
            records.append(load_distribution_evidence(path, cohort_directory=cohort.directory))
        except (OSError, SystemExit, ValueError) as exc:
            return ReadinessCheck(
                "distribution-evidence-complete",
                "blocking",
                False,
                f"invalid or mismatched evidence {path.name}: {exc}",
            )

    failed = sorted({record.row_id for record in records if record.result.status is EvidenceStatus.FAILED})
    if failed:
        return ReadinessCheck(
            "distribution-evidence-complete",
            "blocking",
            False,
            f"cohort has failed distribution rows: {failed!r}",
        )

    canonical_passing, conflicts = _select_canonical_passing_evidence(records)
    if conflicts:
        return ReadinessCheck(
            "distribution-evidence-complete",
            "blocking",
            False,
            "conflicting passing evidence for the same row (runtime/client/destination "
            f"disagree): {'; '.join(conflicts)}",
        )

    passed_rows = set(canonical_passing)
    missing = sorted(set(required_rows) - passed_rows)
    if missing:
        return ReadinessCheck(
            "distribution-evidence-complete",
            "blocking",
            False,
            f"missing passing distribution evidence rows: {missing!r}",
        )

    return ReadinessCheck(
        "distribution-evidence-complete",
        "blocking",
        True,
        f"{len(required_rows)} required rows pass for cohort {manifest.cohort_id}",
    )


def check_generated_surface_versions(
    repo_root: Path,
    *,
    cohort_directory: Path | None = None,
) -> ReadinessCheck:
    """Require the generated Scoop and Homebrew surfaces to bind the cohort.

    Each channel generator embeds the version (and, for Scoop/Homebrew, the exact
    artifact SHA-256s) at build time. A stale embedded value would ship an
    install surface pointing at the wrong release under the right tag, so this
    parses the Scoop JSON manifest and Homebrew Ruby formula and refuses with a
    per-surface enumeration when any embedded value drifts from the cohort.
    """
    name = "generated-surface-versions"
    cohort_root = (cohort_directory or repo_root / "var" / "release-cohort").resolve()
    manifest_path = cohort_root / "release-cohort.json"
    try:
        cohort_manifest = _require_json_object(
            json.loads(manifest_path.read_text(encoding=_UTF_8)),
            surface="release cohort manifest",
        )
        version = str(cohort_manifest["version"])
        python_cohort = load_python_cohort(cohort_root / "python")
        python_sha = python_cohort.sha256
    except (OSError, json.JSONDecodeError, KeyError, ValueError, SystemExit) as exc:
        return ReadinessCheck(
            name, "blocking", False, f"cohort version/digest surfaces unreadable under {cohort_root}: {exc}"
        )

    failures: list[str] = []

    try:
        scoop = _require_json_object(
            json.loads((cohort_root / "scoop" / "cadrumo.json").read_text(encoding=_UTF_8)),
            surface="scoop manifest",
        )
        if str(scoop.get("version")) != version:
            failures.append(f"scoop version {scoop.get('version')!r} != cohort {version!r}")
        expected_hashes = [
            python_sha["cadrumo"],
            python_sha["cadrumo-data-manuals"],
            python_sha["cadrumo-data-official"],
        ]
        scoop_architecture = _require_json_object(scoop.get("architecture"), surface="scoop architecture")
        scoop_64bit = _require_json_object(scoop_architecture.get("64bit"), surface="scoop 64bit architecture")
        actual_hashes = scoop_64bit.get("hash")
        if not isinstance(actual_hashes, list):
            raise ValueError("scoop 64bit hashes must be a JSON array")
        if actual_hashes != expected_hashes:
            failures.append("scoop 64bit hashes do not equal the cohort python-wheel digests")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        failures.append(f"scoop manifest unreadable: {exc}")

    try:
        formula = (cohort_root / "homebrew" / "Formula" / "cadrumo.rb").read_text(encoding=_UTF_8)
        url_match = re.search(r'url "[^"]*/cadrumo-([0-9][^"/]*)\.tar\.gz"', formula)
        sha_match = re.search(r'sha256 "([0-9a-f]{64})"', formula)
        embedded_version = url_match.group(1) if url_match is not None else None
        if embedded_version != version:
            failures.append(f"homebrew formula stable version {embedded_version!r} != cohort {version!r}")
        if sha_match is None or sha_match.group(1) != python_sha["cadrumo-sdist"]:
            failures.append("homebrew formula stable sha256 != cohort cadrumo sdist digest")
    except (OSError, KeyError) as exc:
        failures.append(f"homebrew formula unreadable: {exc}")

    if failures:
        return ReadinessCheck(name, "blocking", False, "; ".join(failures))
    return ReadinessCheck(
        name,
        "blocking",
        True,
        f"scoop and homebrew bind cohort version {version} and digests",
    )


def build_report(
    repo_root: Path | str | None = None,
    *,
    skip_network: bool = False,
    gh_executable: str | None = None,
    cohort_directory: Path | None = None,
    evidence_directory: Path | None = None,
) -> ReadinessReport:
    """Run every readiness check and return the aggregate report.

    ``cohort_directory`` / ``evidence_directory`` relocate the distribution-
    evidence check off its ``var/release-cohort`` / ``var/distribution-install-
    readiness`` defaults - the publish workflow downloads the promoted cohort
    and the aggregated rows into ``var/promotion/*`` and must point the gate at
    them rather than at a working-tree default that does not exist in CI.
    """
    root = Path(repo_root) if repo_root is not None else _repo_root()
    checks: list[ReadinessCheck] = [
        check_project_names_are_canonical(root),
        check_version_surfaces_agree(root),
        check_changelog_is_ready(root),
        check_distribution_evidence_set(
            root,
            cohort_directory=cohort_directory,
            evidence_directory=evidence_directory,
        ),
        check_generated_surface_versions(root, cohort_directory=cohort_directory),
        check_latest_packaging_smoke_evidence(root),
    ]
    if not skip_network:
        # The Gate-2 publish path runs against a promoted cohort directory and has
        # network: there, an inability to determine the blocker state is blocking,
        # not advisory, so the gate cannot promote past a P0 blocker it could not see.
        checks.append(
            check_no_open_release_blockers(gh_executable=gh_executable, strict=cohort_directory is not None),
        )
    return ReadinessReport(checks=tuple(checks))


def main(argv: list[str] | None = None) -> int:
    """Run the release audit-state gate and print the verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable summary.")
    parser.add_argument(
        "--skip-network",
        action="store_true",
        help="Skip the gh-backed open-blocker check (offline/no-gh environments).",
    )
    parser.add_argument(
        "--cohort-dir",
        type=Path,
        default=None,
        help="Release-cohort directory to gate (default: var/release-cohort).",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=None,
        help="Distribution-evidence directory to gate (default: var/distribution-install-readiness).",
    )
    args = parser.parse_args(argv)

    report = build_report(
        skip_network=args.skip_network,
        cohort_directory=args.cohort_dir,
        evidence_directory=args.evidence_dir,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0 if report.ok else 1

    for check in report.checks:
        status = "PASS" if check.passed else ("BLOCK" if check.severity == "blocking" else "WARN")
        print(f"[{status}] {check.name}: {check.detail}")
    if report.ok:
        print("\naudit-state gate: OK — release may proceed to the automated bump.")
    else:
        print("\naudit-state gate: BLOCKED — resolve the failures above before releasing.")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
