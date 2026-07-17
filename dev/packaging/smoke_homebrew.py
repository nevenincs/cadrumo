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
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, override

_UTF_8: Final[str] = "utf-8"
_FORMULA_NAME: Final[str] = "cadrumo"
_RELEASE_ARTIFACT = re.compile(
    r'(?P<url_prefix>\s+url ")(?P<base>https://[^"]+/releases/download/v[^/"]+)'
    r'/(?P<filename>[^/"]+\.tar\.gz)"(?P<separator>\r?\n)'
    r'(?P<sha_prefix>\s+sha256 ")(?P<sha256>[0-9a-f]{64})"',
)


@dataclass(frozen=True)
class CommandEvidence:
    """Captured result of one successful external command."""

    argv: tuple[str, ...]
    log: str
    stdout: str


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode(_UTF_8)).hexdigest()


def _run(
    argv: list[str],
    *,
    cwd: Path,
    log_dir: Path,
    label: str,
    env: dict[str, str] | None = None,
) -> CommandEvidence:
    completed = subprocess.run(  # noqa: S603 - fixed internal commands and explicit paths.
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="strict",
    )
    log = log_dir / f"{label}.log"
    rendered = (
        f"argv={json.dumps(argv, ensure_ascii=False)}\n"
        f"cwd={cwd}\n"
        f"exit_code={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}\n"
    )
    log.write_text(rendered, encoding=_UTF_8)
    if completed.returncode != 0:
        raise SystemExit(
            f"command failed ({completed.returncode}): {argv!r}; retained log: {log}",
        )
    return CommandEvidence(tuple(argv), str(log), completed.stdout)


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
        actual_sha256 = _sha256(artifact)
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
    )


def _assert_oracle_evidence(
    *,
    tax_document: dict[str, object],
    mcp_document: dict[str, object],
    aeat_path_sha256: str,
) -> None:
    if tax_document.get("target_value") != "23000.00":
        raise SystemExit(f"installed CLI oracle returned unexpected evidence: {tax_document!r}")
    if mcp_document.get("target_value") != "23000.00":
        raise SystemExit(f"installed MCP oracle returned unexpected evidence: {mcp_document!r}")
    invoked_cli_sha256 = mcp_document.get("invoked_cli_sha256")
    if invoked_cli_sha256 != aeat_path_sha256:
        raise SystemExit(
            "installed MCP server invoked a different CLI identity: "
            f"expected {aeat_path_sha256}, got {invoked_cli_sha256!r}",
        )


def run_homebrew_smoke(
    *,
    formula_path: Path,
    cohort_dir: Path,
    evidence_dir: Path,
    tap_name: str,
    brew_path: Path,
    repo_root: Path,
) -> Path:
    """Run audit, source install, formula test, installed oracles, and cleanup."""
    formula_source = formula_path.resolve(strict=True)
    cohort = cohort_dir.resolve(strict=True)
    brew = brew_path.expanduser().absolute()
    if not brew.is_file():
        raise SystemExit(f"Homebrew executable is not a file: {brew}")
    repo = repo_root.resolve(strict=True)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*", tap_name):
        raise SystemExit(f"tap name must be one lowercase user/repository pair: {tap_name!r}")
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
    staged_formula.write_text(original_formula, encoding=_UTF_8)

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
            "sha256": _sha256(cohort / Path(original).name),
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

        staged_formula.write_text(localized_formula, encoding=_UTF_8)
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
        aeat = (installed_prefix / "bin" / "aeat").resolve(strict=True)
        mcp = (installed_prefix / "bin" / "cadrumo-mcp").resolve(strict=True)
        for command in (aeat, mcp):
            if not command.is_file() or not os.access(command, os.X_OK):
                raise SystemExit(f"installed Homebrew command is not executable: {command}")

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
        mcp_evidence = run_root / "mcp-evidence.json"
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
        _run(
            [
                str(installed_python),
                "-m",
                "dev.packaging.installed_mcp_oracle",
                "--server",
                str(mcp),
                "--storage-root",
                str(run_root / "mcp-state"),
                "--work-dir",
                str(run_root / "mcp-work"),
                "--output",
                str(mcp_evidence),
            ],
            cwd=repo,
            log_dir=logs,
            label="installed-mcp-oracle",
            env=oracle_env,
        )
        tax_document = json.loads(tax_evidence.read_text(encoding=_UTF_8))
        mcp_document = json.loads(mcp_evidence.read_text(encoding=_UTF_8))
        aeat_sha256 = _sha256(aeat)
        aeat_path_sha256 = _text_sha256(str(aeat))
        _assert_oracle_evidence(
            tax_document=tax_document,
            mcp_document=mcp_document,
            aeat_path_sha256=aeat_path_sha256,
        )

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
            "source_formula_sha256": _sha256(formula_source),
            "localized_formula": str(staged_formula),
            "localized_formula_sha256": _sha256(staged_formula),
            "cohort_url_replacements": replacements,
            "cohort_artifacts": cohort_artifacts,
            "installed_prefix": str(installed_prefix),
            "installed_formulae": list(installed_formulae),
            "aeat_command": str(aeat),
            "aeat_sha256": aeat_sha256,
            "aeat_path_sha256": aeat_path_sha256,
            "mcp_command": str(mcp),
            "mcp_sha256": _sha256(mcp),
            "mcp_invoked_cli_sha256": mcp_document["invoked_cli_sha256"],
            "version_output": version,
            "tax_evidence": str(tax_evidence),
            "mcp_evidence": str(mcp_evidence),
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
                [str(brew), "uninstall", "--force", formula],
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
        cleanup = {
            "retained_formulae": sorted(retained_formulae),
            "retained_taps": sorted(retained_taps),
            "installed_prefix_absent": installed_prefix is None or not installed_prefix.exists(),
            "errors": cleanup_errors,
        }
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
        default=Path(__file__).resolve().parents[2],
    )
    return parser


def main() -> int:
    """Execute the real Homebrew smoke lifecycle."""
    args = _parser().parse_args()
    evidence = run_homebrew_smoke(
        formula_path=args.formula,
        cohort_dir=args.cohort_dir,
        evidence_dir=args.evidence_dir,
        tap_name=args.tap_name,
        brew_path=args.brew,
        repo_root=args.repo_root,
    )
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
