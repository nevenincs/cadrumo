"""Install and exercise one generated Cadrumo Homebrew formula from source."""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, override

from dev._paths import REPO_ROOT

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if not __package__:
    __package__ = "dev.packaging"

from ._command import CommandResult, run_command  # noqa: E402
from ._hashing import sha256_path  # noqa: E402

_UTF_8: Final[str] = "utf-8"
_FORMULA_NAME: Final[str] = "cadrumo"
CLEANUP_STATE_NAME: Final[str] = "homebrew-cleanup-state.json"
_CLEANUP_STATE_SCHEMA: Final[str] = "cadrumo.packaging.homebrew-cleanup-state.v1"
_RELEASE_ARTIFACT = re.compile(
    r'(?P<url_prefix>\s+url ")(?P<base>https://[^"]+/releases/download/v[^/"]+)'
    r'/(?P<filename>[^/"]+\.tar\.gz)"(?P<separator>\r?\n)'
    r'(?P<sha_prefix>\s+sha256 ")(?P<sha256>[0-9a-f]{64})"',
)
_TAP_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*/[a-z0-9][a-z0-9_-]*")


def _require_valid_tap_name(tap_name: str) -> None:
    """Accept one lowercase ``user/repository`` tap pair as Homebrew itself does.

    A Homebrew tap name maps to a ``homebrew-<repository>`` GitHub repository, so
    the repository segment may carry underscores (the ``x86_64`` architecture id)
    as well as hyphens; the matrix passes ``cadrumo-smoke/linux-x86_64``.
    """
    if not _TAP_NAME.fullmatch(tap_name):
        raise SystemExit(f"tap name must be one lowercase user/repository pair: {tap_name!r}")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    @override
    def log_message(self, format: str, *args: object) -> None:
        """Keep HTTP access details in command evidence rather than stderr."""


class _QuietServer(http.server.ThreadingHTTPServer):
    @override
    def handle_error(
        self,
        request: object,
        client_address: tuple[str, int],
    ) -> None:
        """Ignore clients closing a completed or superseded Homebrew download."""


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode(_UTF_8)).hexdigest()


def _run(
    argv: list[str],
    *,
    cwd: Path,
    log_dir: Path,
    label: str,
    env: dict[str, str] | None = None,
) -> CommandResult:
    completed = run_command(argv, cwd=cwd, environment=env)
    log = log_dir / f"{label}.log"
    log.write_text(
        f"argv={json.dumps(argv, ensure_ascii=False)}\n"
        f"cwd={cwd}\n"
        f"exit_code={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}\n",
        encoding=_UTF_8,
        newline="\n",
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"command failed ({completed.returncode}): {argv!r}; retained log: {log}",
        )
    return completed


def _brew_lines(
    brew: Path,
    arguments: list[str],
    *,
    cwd: Path,
    log_dir: Path,
    label: str,
) -> tuple[str, ...]:
    result = _run(
        [str(brew), *arguments],
        cwd=cwd,
        log_dir=log_dir,
        label=label,
    )
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def localize_formula(
    formula: str,
    *,
    cohort_dir: Path,
    server_base_url: str,
) -> tuple[str, dict[str, str]]:
    """Point exactly three cohort sdists at a loopback server without other edits."""
    replacements: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        filename = match.group("filename")
        if Path(filename).name != filename:
            raise SystemExit(f"formula cohort URL contains an unsafe filename: {filename!r}")
        artifact = (cohort_dir / filename).resolve(strict=True)
        if artifact.parent != cohort_dir:
            raise SystemExit(f"formula cohort artifact escapes its directory: {artifact}")
        expected_sha256 = match.group("sha256")
        actual_sha256 = sha256_path(artifact)
        if actual_sha256 != expected_sha256:
            raise SystemExit(
                f"formula cohort artifact digest mismatch: {filename} expected {expected_sha256}, got {actual_sha256}",
            )
        original = f"{match.group('base')}/{filename}"
        localized = f"{server_base_url.rstrip('/')}/{filename}"
        replacements[original] = localized
        return (
            f'{match.group("url_prefix")}{localized}"'
            f'{match.group("separator")}{match.group("sha_prefix")}{expected_sha256}"'
        )

    localized = _RELEASE_ARTIFACT.sub(replace, formula)
    if len(replacements) != 3:
        raise SystemExit(
            f"expected root and two companion release sdists in the generated formula; got {sorted(replacements)!r}",
        )
    if localized == formula:
        raise SystemExit("formula localization made no changes")
    restored = localized
    for original, replacement in replacements.items():
        restored = restored.replace(replacement, original)
    if restored != formula:
        raise SystemExit("formula localization changed material beyond cohort URLs")
    return localized, dict(sorted(replacements.items()))


def _new_run_root(evidence_dir: Path) -> Path:
    evidence = evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_root = evidence / f"run-{run_id}"
    run_root.mkdir()
    return run_root


def _installed_python(prefix: Path) -> Path:
    candidates = (
        prefix / "libexec" / "bin" / "python",
        prefix / "libexec" / "bin" / "python3",
        prefix / "libexec" / "bin" / "python3.13",
    )
    matches = tuple(path.absolute() for path in candidates if path.is_file())
    if not matches:
        raise SystemExit(f"installed Homebrew virtualenv exposes no Python under {prefix / 'libexec'}")
    return matches[0]


def _write_json(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )


def _assert_oracle_evidence(*, tax_document: dict[str, object]) -> None:
    """Refuse a Homebrew keg whose installed CLI does not reproduce the oracle.

    The CLI is the only executable this formula installs. ``cadrumo-mcp`` ships
    in the sibling ``cadrumo-harness`` distribution, which Homebrew does not
    carry — one distribution per formula — so there is no MCP leg to exercise
    here; the harness is reached through pipx, the MCPB bundle, or the Claude
    plugin, each of which runs the MCP oracle on its own acquisition path.
    """
    if tax_document.get("target_value") != "23000.00":
        raise SystemExit(f"installed CLI oracle returned unexpected evidence: {tax_document!r}")


def run_homebrew_smoke(
    *,
    formula_path: Path,
    cohort_dir: Path,
    evidence_dir: Path,
    tap_name: str,
    brew_path: Path,
    repo_root: Path,
    retain_install: bool = False,
) -> Path:
    """Run audit, source install, formula test, installed oracles, and cleanup.

    With ``retain_install`` the uninstall/untap cleanup is DEFERRED: the keg
    stays installed so a later step can mint the distribution-evidence row
    against the real installed executables, and the recorded cleanup state
    (``homebrew-cleanup-state.json`` in the run root) drives
    ``--cleanup-state`` afterwards.
    """
    formula_source = formula_path.resolve(strict=True)
    cohort = cohort_dir.resolve(strict=True)
    brew = brew_path.expanduser().absolute()
    if not brew.is_file():
        raise SystemExit(f"Homebrew executable is not a file: {brew}")
    repo = repo_root.resolve(strict=True)
    _require_valid_tap_name(tap_name)
    if platform.system() not in {"Darwin", "Linux"}:
        raise SystemExit(f"Homebrew smoke requires macOS or Linux; got {platform.system()}")
    if platform.machine().casefold() not in {"x86_64", "amd64", "arm64", "aarch64"}:
        raise SystemExit(f"unsupported Homebrew smoke architecture: {platform.machine()}")
    os.environ["HOMEBREW_NO_AUTO_UPDATE"] = "1"
    brew_prefix = brew.parent.parent
    os.environ["PATH"] = os.pathsep.join(
        (str(brew_prefix / "bin"), str(brew_prefix / "sbin"), os.environ["PATH"]),
    )

    run_root = _new_run_root(evidence_dir)
    logs = run_root / "logs"
    logs.mkdir()
    tap_repo = run_root / "tap"
    formula_dir = tap_repo / "Formula"
    formula_dir.mkdir(parents=True)
    staged_formula = formula_dir / "cadrumo.rb"
    original_formula = formula_source.read_text(encoding=_UTF_8)
    staged_formula.write_text(original_formula, encoding=_UTF_8, newline="\n")

    preexisting_formulae = set(
        _brew_lines(brew, ["list", "--formula"], cwd=run_root, log_dir=logs, label="brew-list-before"),
    )
    preexisting_taps = set(
        _brew_lines(brew, ["tap"], cwd=run_root, log_dir=logs, label="brew-taps-before"),
    )
    if _FORMULA_NAME in preexisting_formulae:
        raise SystemExit("refusing to replace pre-existing Homebrew formula cadrumo")
    if tap_name in preexisting_taps:
        raise SystemExit(f"refusing to replace pre-existing Homebrew tap {tap_name}")

    server = _QuietServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: _QuietHandler(*args, directory=str(cohort), **kwargs),
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    server_base = f"http://127.0.0.1:{server.server_port}"
    localized_formula, replacements = localize_formula(
        original_formula,
        cohort_dir=cohort,
        server_base_url=server_base,
    )
    cohort_artifacts = [
        {
            "filename": Path(original).name,
            "sha256": sha256_path(cohort / Path(original).name),
            "size": (cohort / Path(original).name).stat().st_size,
        }
        for original in replacements
    ]

    qualified = f"{tap_name}/{_FORMULA_NAME}"
    installed_prefix: Path | None = None
    installed_formulae: tuple[str, ...] = ()
    cleanup_errors: list[str] = []
    tap_registered = False
    started_at = datetime.now(UTC)
    evidence: dict[str, object] = {}
    try:
        _run(["git", "init", "--quiet"], cwd=tap_repo, log_dir=logs, label="tap-git-init")
        _run(
            ["git", "add", "Formula/cadrumo.rb"],
            cwd=tap_repo,
            log_dir=logs,
            label="tap-git-add-original",
        )
        _run(
            [
                "git",
                "-c",
                "user.name=Cadrumo packaging smoke",
                "-c",
                "user.email=packaging-smoke@invalid.example",
                "commit",
                "--quiet",
                "-m",
                "stage immutable Cadrumo formula",
            ],
            cwd=tap_repo,
            log_dir=logs,
            label="tap-git-commit-original",
        )
        _run(
            [str(brew), "tap", tap_name, tap_repo.as_uri()],
            cwd=run_root,
            log_dir=logs,
            label="brew-tap",
        )
        tap_registered = True
        _run(
            [str(brew), "audit", "--strict", "--formula", qualified],
            cwd=run_root,
            log_dir=logs,
            label="brew-audit",
        )

        staged_formula.write_text(localized_formula, encoding=_UTF_8, newline="\n")
        _run(
            ["git", "add", "Formula/cadrumo.rb"],
            cwd=tap_repo,
            log_dir=logs,
            label="tap-git-add-localized",
        )
        _run(
            [
                "git",
                "-c",
                "user.name=Cadrumo packaging smoke",
                "-c",
                "user.email=packaging-smoke@invalid.example",
                "commit",
                "--quiet",
                "-m",
                "localize cohort acquisition for smoke",
            ],
            cwd=tap_repo,
            log_dir=logs,
            label="tap-git-commit-localized",
        )
        tapped_repo = Path(
            _run(
                [str(brew), "--repo", tap_name],
                cwd=run_root,
                log_dir=logs,
                label="brew-tap-repo",
            ).stdout.strip(),
        ).resolve(strict=True)
        _run(
            ["git", "pull", "--ff-only"],
            cwd=tapped_repo,
            log_dir=logs,
            label="brew-tap-pull-localized",
        )
        _run(
            [str(brew), "install", "--build-from-source", qualified],
            cwd=run_root,
            log_dir=logs,
            label="brew-install",
        )
        installed_formulae = _brew_lines(
            brew,
            ["list", "--formula"],
            cwd=run_root,
            log_dir=logs,
            label="brew-list-installed",
        )
        prefix_text = _run(
            [str(brew), "--prefix", qualified],
            cwd=run_root,
            log_dir=logs,
            label="brew-prefix",
        ).stdout.strip()
        installed_prefix = Path(prefix_text).resolve(strict=True)
        # The formula installs the `cadrumo` distribution alone, so `aeat` is the
        # only executable it lands. `cadrumo-mcp` belongs to the sibling
        # `cadrumo-harness` distribution, which Homebrew does not carry.
        aeat = (installed_prefix / "bin" / "aeat").resolve(strict=True)
        if not aeat.is_file() or not os.access(aeat, os.X_OK):
            raise SystemExit(f"installed Homebrew command is not executable: {aeat}")

        _run(
            [str(brew), "test", qualified],
            cwd=run_root,
            log_dir=logs,
            label="brew-test",
        )
        version = _run(
            [str(aeat), "--version"],
            cwd=run_root,
            log_dir=logs,
            label="aeat-version",
        ).stdout.strip()

        installed_python = _installed_python(installed_prefix)
        oracle_env = os.environ.copy()
        oracle_env["PYTHONPATH"] = str(repo)
        tax_evidence = run_root / "tax-evidence.json"
        _run(
            [
                str(installed_python),
                "-m",
                "dev.packaging.installed_tax_oracle",
                "--cli",
                str(aeat),
                "--storage-root",
                str(run_root / "tax-state"),
                "--work-dir",
                str(run_root / "tax-work"),
                "--output",
                str(tax_evidence),
            ],
            cwd=repo,
            log_dir=logs,
            label="installed-tax-oracle",
            env=oracle_env,
        )
        tax_document = json.loads(tax_evidence.read_text(encoding=_UTF_8))
        aeat_sha256 = sha256_path(aeat)
        aeat_path_sha256 = _text_sha256(str(aeat))
        _assert_oracle_evidence(tax_document=tax_document)

        evidence = {
            "schema": "cadrumo.packaging.homebrew-smoke.v1",
            "started_at": started_at.isoformat(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "brew": str(brew),
            "brew_version": _run(
                [str(brew), "--version"],
                cwd=run_root,
                log_dir=logs,
                label="brew-version",
            ).stdout.strip(),
            "tap_name": tap_name,
            "formula_name": qualified,
            "source_formula": str(formula_source),
            "source_formula_sha256": sha256_path(formula_source),
            "localized_formula": str(staged_formula),
            "localized_formula_sha256": sha256_path(staged_formula),
            "cohort_url_replacements": replacements,
            "cohort_artifacts": cohort_artifacts,
            "installed_prefix": str(installed_prefix),
            "installed_formulae": list(installed_formulae),
            "aeat_command": str(aeat),
            "aeat_sha256": aeat_sha256,
            "aeat_path_sha256": aeat_path_sha256,
            "version_output": version,
            "tax_evidence": str(tax_evidence),
            "preexisting_formulae": sorted(preexisting_formulae),
            "preexisting_taps": sorted(preexisting_taps),
        }
    except BaseException as exc:
        _write_json(
            run_root / "homebrew-failure.json",
            {
                "schema": "cadrumo.packaging.homebrew-smoke-failure.v1",
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "started_at": started_at.isoformat(),
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )
        raise
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

        if retain_install:
            # The workflow's later emit step hashes the INSTALLED executables
            # (the mint-time isolation proof), so the keg must survive this
            # process. Record everything the deferred cleanup needs; the
            # workflow runs `--cleanup-state` after the row is minted.
            state_path = run_root / CLEANUP_STATE_NAME
            _write_json(
                state_path,
                cleanup_state_document(
                    brew=brew,
                    tap_name=tap_name,
                    tap_registered=tap_registered,
                    installed_prefix=installed_prefix,
                    preexisting_formulae=preexisting_formulae,
                    preexisting_taps=preexisting_taps,
                ),
            )
            cleanup = {
                "deferred_for_emit": True,
                "cleanup_state": str(state_path),
                "errors": cleanup_errors,
            }
        else:
            deferred_errors, cleanup = _run_brew_cleanup(
                brew=brew,
                run_root=run_root,
                logs=logs,
                tap_name=tap_name,
                preexisting_formulae=preexisting_formulae,
                preexisting_taps=preexisting_taps,
                tap_registered=tap_registered,
                installed_prefix=installed_prefix,
            )
            cleanup_errors.extend(deferred_errors)
            cleanup["errors"] = cleanup_errors
        if evidence and not cleanup_errors:
            evidence["status"] = "passed"
            evidence["completed_at"] = datetime.now(UTC).isoformat()
            evidence["cleanup"] = cleanup
            _write_json(run_root / "homebrew-evidence.json", evidence)
        if cleanup_errors:
            failure_path = run_root / "homebrew-failure.json"
            failure: dict[str, object]
            if failure_path.is_file():
                loaded_failure = json.loads(failure_path.read_text(encoding=_UTF_8))
                failure = dict(loaded_failure) if isinstance(loaded_failure, dict) else {}
            else:
                failure = {
                    "schema": "cadrumo.packaging.homebrew-smoke-failure.v1",
                    "status": "failed",
                    "started_at": started_at.isoformat(),
                    "failed_at": datetime.now(UTC).isoformat(),
                }
            failure["cleanup"] = cleanup
            _write_json(failure_path, failure)
            raise SystemExit("; ".join(cleanup_errors))

    return run_root / "homebrew-evidence.json"


def cleanup_state_document(
    *,
    brew: Path,
    tap_name: str,
    tap_registered: bool,
    installed_prefix: Path | None,
    preexisting_formulae: set[str],
    preexisting_taps: set[str],
) -> dict[str, object]:
    """Return the deferred-cleanup state a ``--retain-install`` run records."""
    return {
        "schema": _CLEANUP_STATE_SCHEMA,
        "brew": str(brew),
        "tap_name": tap_name,
        "tap_registered": tap_registered,
        "installed_prefix": None if installed_prefix is None else str(installed_prefix),
        "preexisting_formulae": sorted(preexisting_formulae),
        "preexisting_taps": sorted(preexisting_taps),
    }


def _run_brew_cleanup(
    *,
    brew: Path,
    run_root: Path,
    logs: Path,
    tap_name: str,
    preexisting_formulae: set[str],
    preexisting_taps: set[str],
    tap_registered: bool,
    installed_prefix: Path | None,
) -> tuple[list[str], dict[str, object]]:
    """Uninstall everything the smoke added and report what survived.

    Removes the staged formula, every newly-appeared dependency formula, and
    the staged tap, comparing against the recorded pre-smoke sets; returns the
    accumulated cleanup errors plus the honest retained-state summary.
    """
    cleanup_errors: list[str] = []

    def cleanup_lines(arguments: list[str], *, label: str) -> set[str]:
        completed = subprocess.run(  # noqa: S603
            [str(brew), *arguments],
            cwd=run_root,
            check=False,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="strict",
        )
        (logs / f"{label}.log").write_text(
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n",
            encoding=_UTF_8,
            newline="\n",
        )
        if completed.returncode != 0:
            cleanup_errors.append(
                f"cleanup command failed ({completed.returncode}): {[str(brew), *arguments]!r}",
            )
            return set()
        return {line.strip() for line in completed.stdout.splitlines() if line.strip()}

    current_formulae = cleanup_lines(
        ["list", "--formula"],
        label="brew-list-before-cleanup",
    )
    new_formulae = current_formulae - preexisting_formulae
    if installed_prefix is not None or _FORMULA_NAME in new_formulae:
        completed = subprocess.run(  # noqa: S603
            [str(brew), "uninstall", "--force", _FORMULA_NAME],
            cwd=run_root,
            check=False,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="strict",
        )
        (logs / "brew-uninstall-cadrumo.log").write_text(
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n",
            encoding=_UTF_8,
            newline="\n",
        )
        if completed.returncode != 0:
            cleanup_errors.append("failed to uninstall staged cadrumo formula")
    remaining_new = (
        cleanup_lines(
            ["list", "--formula"],
            label="brew-list-dependencies",
        )
        - preexisting_formulae
    )
    for formula in sorted(remaining_new, reverse=True):
        completed = subprocess.run(  # noqa: S603
            [str(brew), "uninstall", "--force", "--ignore-dependencies", formula],
            cwd=run_root,
            check=False,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="strict",
        )
        (logs / f"brew-uninstall-{formula.replace('@', '_')}.log").write_text(
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n",
            encoding=_UTF_8,
            newline="\n",
        )
        if completed.returncode != 0:
            cleanup_errors.append(f"failed to uninstall smoke dependency {formula}")

    current_taps = cleanup_lines(
        ["tap"],
        label="brew-taps-before-cleanup",
    )
    if tap_registered or tap_name in current_taps - preexisting_taps:
        completed = subprocess.run(  # noqa: S603
            [str(brew), "untap", tap_name],
            cwd=run_root,
            check=False,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="strict",
        )
        (logs / "brew-untap.log").write_text(
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n",
            encoding=_UTF_8,
            newline="\n",
        )
        if completed.returncode != 0:
            cleanup_errors.append(f"failed to remove staged tap {tap_name}")

    retained_formulae = (
        cleanup_lines(
            ["list", "--formula"],
            label="brew-list-after",
        )
        - preexisting_formulae
    )
    retained_taps = (
        cleanup_lines(
            ["tap"],
            label="brew-taps-after",
        )
        - preexisting_taps
    )
    if retained_formulae:
        cleanup_errors.append(f"cleanup retained formulae: {sorted(retained_formulae)!r}")
    if retained_taps:
        cleanup_errors.append(f"cleanup retained taps: {sorted(retained_taps)!r}")
    if installed_prefix is not None and installed_prefix.exists():
        cleanup_errors.append(f"cleanup retained installed prefix: {installed_prefix}")
    cleanup: dict[str, object] = {
        "retained_formulae": sorted(retained_formulae),
        "retained_taps": sorted(retained_taps),
        "installed_prefix_absent": installed_prefix is None or not installed_prefix.exists(),
    }
    return cleanup_errors, cleanup


def run_deferred_cleanup(state_path: Path) -> int:
    """Run the deferred uninstall/untap recorded by a ``--retain-install`` smoke.

    Loads the recorded pre-smoke formula/tap sets and performs the exact same
    cleanup the smoke would have run inline, writing a
    ``homebrew-cleanup-result.json`` next to the state file; a cleanup error
    exits non-zero so the workflow step surfaces it.
    """
    resolved_state = state_path.resolve(strict=True)
    state = json.loads(resolved_state.read_text(encoding=_UTF_8))
    if state.get("schema") != _CLEANUP_STATE_SCHEMA:
        raise SystemExit(f"unrecognised cleanup state schema in {resolved_state}: {state.get('schema')!r}")
    run_root = resolved_state.parent
    logs = run_root / "logs"
    logs.mkdir(exist_ok=True)
    installed_prefix_text = state.get("installed_prefix")
    cleanup_errors, cleanup = _run_brew_cleanup(
        brew=Path(str(state["brew"])),
        run_root=run_root,
        logs=logs,
        tap_name=str(state["tap_name"]),
        preexisting_formulae={str(name) for name in state["preexisting_formulae"]},
        preexisting_taps={str(name) for name in state["preexisting_taps"]},
        tap_registered=bool(state["tap_registered"]),
        installed_prefix=None if installed_prefix_text is None else Path(str(installed_prefix_text)),
    )
    cleanup["errors"] = cleanup_errors
    _write_json(run_root / "homebrew-cleanup-result.json", cleanup)
    for error in cleanup_errors:
        print(f"cleanup error: {error}")
    return 1 if cleanup_errors else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formula", required=True, type=Path)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--tap-name", default="cadrumo-smoke/acquisition")
    parser.add_argument("--brew", type=Path, default=Path(shutil.which("brew") or "brew"))
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
    )
    parser.add_argument(
        "--retain-install",
        action="store_true",
        help=(
            "Defer the uninstall/untap cleanup so a later step can mint the "
            "distribution-evidence row against the real installed executables; "
            "run --cleanup-state on the recorded state afterwards."
        ),
    )
    return parser


def _cleanup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the deferred Homebrew smoke cleanup.")
    parser.add_argument(
        "--cleanup-state",
        required=True,
        type=Path,
        help="homebrew-cleanup-state.json written by a --retain-install smoke run.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute the real Homebrew smoke lifecycle (or its deferred cleanup)."""
    arguments = sys.argv[1:] if argv is None else argv
    if "--cleanup-state" in arguments:
        cleanup_args = _cleanup_parser().parse_args(arguments)
        return run_deferred_cleanup(cleanup_args.cleanup_state)
    args = _parser().parse_args(arguments)
    evidence = run_homebrew_smoke(
        formula_path=args.formula,
        cohort_dir=args.cohort_dir,
        evidence_dir=args.evidence_dir,
        tap_name=args.tap_name,
        brew_path=args.brew,
        repo_root=args.repo_root,
        retain_install=args.retain_install,
    )
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
