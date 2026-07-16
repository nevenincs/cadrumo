"""Audit-state readiness gate run before `just release-apply` is trusted.

Checks a small set of deterministic, release-blocking invariants and reports
a single machine-readable verdict. This module performs **no outward
action** — it reads local files and, best-effort, queries the GitHub issue
tracker read-only via `gh`. It never tags, pushes, or publishes anything;
those steps stay entirely human-run per RELEASING.md.

Two severities distinguish a hard release blocker from an advisory note:

* ``blocking`` — the check is a deterministic, always-computable invariant
  (version-surface parity, changelog presence). A failure here is a real
  release defect and the gate exits non-zero.
* ``advisory`` — the check depends on live external state (GitHub API
  reachability, whether a packaging-smoke run happened in this workspace).
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
    :func:`check_latest_packaging_smoke_evidence`
        Advisory packaging-smoke evidence check for the current checkout.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from cadrumo.core import PRODUCT_IDENTITY

_UTF_8: Final = "utf-8"
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
    return Path(__file__).resolve().parents[2]


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
    return match.group(1)


def _read_manifest_version(repo_root: Path) -> str:
    payload = json.loads((repo_root / ".release-please-manifest.json").read_text(encoding=_UTF_8))
    return str(payload.get(".", ""))


_MCPB_MANIFEST_PATH: Final = Path("packaging/mcpb/manifest.json")


def _read_mcpb_manifest(repo_root: Path) -> tuple[str, tuple[str, ...]]:
    """Return the ``.mcpb`` bundle's declared version and its ``uvx`` bootstrap args.

    The Desktop-Extension bundle self-installs ``cadrumo[agent]`` from PyPI via
    ``uvx --from cadrumo[agent]==<version> cadrumo-mcp``; both its declared
    version and that pin move in lockstep with the package release.
    """
    payload = json.loads((repo_root / _MCPB_MANIFEST_PATH).read_text(encoding=_UTF_8))
    version = str(payload.get("version", ""))
    mcp_config = payload.get("server", {}).get("mcp_config", {})
    args = tuple(str(arg) for arg in mcp_config.get("args", []))
    return version, args


def check_version_surfaces_agree(repo_root: Path) -> ReadinessCheck:
    """Confirm every release authority and exact companion pin reports one version."""
    project_versions = tuple(
        (relative, _read_project_version(repo_root / relative)) for relative, _expected_name in _PROJECT_NAME_PATHS
    )
    pyproject_version = project_versions[0][1]
    init_version = _read_init_version(repo_root)
    manifest_version = _read_manifest_version(repo_root)
    mcpb_version, mcpb_args = _read_mcpb_manifest(repo_root)
    root_project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding=_UTF_8))
    observed_pins = tuple(
        str(requirement) for requirement in root_project["project"]["optional-dependencies"]["corpus-sources"]
    )
    expected_pins = tuple(
        f"{distribution}=={pyproject_version}" for distribution in PRODUCT_IDENTITY.companion_distributions
    )
    # The .mcpb bundle's self-install pin must name the exact package release, so
    # a bump can never ship a bundle that installs a stale cadrumo[agent].
    expected_mcpb_pin = f"{PRODUCT_IDENTITY.distribution}[agent]=={pyproject_version}"
    mcpb_pin_ok = expected_mcpb_pin in mcpb_args
    versions = {version for _relative, version in project_versions} | {init_version, manifest_version, mcpb_version}
    passed = len(versions) == 1 and bool(pyproject_version) and observed_pins == expected_pins and mcpb_pin_ok
    surfaces = " ".join(f"{relative}={version!r}" for relative, version in project_versions)
    detail = (
        f"{surfaces} init={init_version!r} manifest={manifest_version!r} "
        f"mcpb={mcpb_version!r} mcpb_pin_ok={mcpb_pin_ok} pins={observed_pins!r}"
    )
    if passed:
        detail = f"all release authorities, the .mcpb bundle, and exact companion pins agree on {pyproject_version!r}"
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
    *, repo_slug: str = "nevenincs/cadrumo", gh_executable: str | None = None
) -> ReadinessCheck:
    """Confirm no open GitHub issue carries the `priority:P0-blocker` label.

    Advisory: degrades gracefully (reported, non-blocking) when `gh` is
    absent, unauthenticated, or the network is unreachable, since this check
    depends on live external state rather than repository content.

    `gh_executable` accepts an explicit resolved path (used by tests to
    exercise a real, non-mocked stub executable without depending on the
    host platform's PATH/PATHEXT executable-resolution rules); production
    callers resolve the real `gh` via `shutil.which`.
    """
    resolved_gh = gh_executable if gh_executable is not None else shutil.which("gh")
    if resolved_gh is None:
        return ReadinessCheck(
            "no-open-release-blockers",
            "advisory",
            False,
            "gh unavailable: not found on PATH",
        )
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
        return ReadinessCheck(
            "no-open-release-blockers",
            "advisory",
            False,
            f"gh unavailable: {exc}",
        )
    if result.returncode != 0:
        return ReadinessCheck(
            "no-open-release-blockers",
            "advisory",
            False,
            f"gh issue list failed (rc={result.returncode}): {result.stderr.strip()[:200]}",
        )
    try:
        issues = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return ReadinessCheck(
            "no-open-release-blockers",
            "advisory",
            False,
            "gh returned non-JSON output",
        )
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
        payload = json.loads(latest.read_text(encoding=_UTF_8))
    except json.JSONDecodeError:
        return ReadinessCheck(
            "packaging-smoke-evidence",
            "advisory",
            False,
            f"{latest} is not valid JSON",
        )
    ok = bool(payload.get("ok"))
    lane = payload.get("lane", "<unknown>")
    run_label = latest.stem if latest.parent == evidence_dir else latest.parent.name
    return ReadinessCheck(
        "packaging-smoke-evidence",
        "advisory",
        ok,
        f"most recent manifest ({run_label}, lane={lane}) ok={ok}",
    )


def build_report(
    repo_root: Path | str | None = None, *, skip_network: bool = False, gh_executable: str | None = None
) -> ReadinessReport:
    """Run every readiness check and return the aggregate report."""
    root = Path(repo_root) if repo_root is not None else _repo_root()
    checks: list[ReadinessCheck] = [
        check_project_names_are_canonical(root),
        check_version_surfaces_agree(root),
        check_changelog_is_ready(root),
        check_latest_packaging_smoke_evidence(root),
    ]
    if not skip_network:
        checks.append(check_no_open_release_blockers(gh_executable=gh_executable))
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
    args = parser.parse_args(argv)

    report = build_report(skip_network=args.skip_network)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0 if report.ok else 1

    for check in report.checks:
        status = "PASS" if check.passed else ("BLOCK" if check.severity == "blocking" else "WARN")
        print(f"[{status}] {check.name}: {check.detail}")
    if report.ok:
        print("\naudit-state gate: OK — release may proceed to `just release-apply`.")
    else:
        print("\naudit-state gate: BLOCKED — resolve the failures above before releasing.")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
