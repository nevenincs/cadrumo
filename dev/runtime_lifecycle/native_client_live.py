"""Prove the native runtime client against a real runtime on a disposable root.

The native client (``native/application/src/runtime_client.rs``) is what the
desktop window uses to reach the runtime without starting a Python child. Its
live test needs a served root with a profile whose sign-in is stored, so this
driver arranges exactly that and runs the test:

1. creates a synthetic profile on a fresh root below the checkout's temporary
   storage and marks that root as a development root, which admits a
   desktop-frontend password sign-in from any same-account process;
2. starts ``cadrumo-runtime --configured-root`` from the current environment
   and waits for its readiness line;
3. signs the profile in through ``aeat config login``, which stores the
   sign-in the native client then resumes, and creates a Modelo 303 work unit
   through ``aeat app modelo work create``;
4. runs ``cargo test`` for the application crate's ignored live test with the
   root, version, profile, password and work unit handed over in the
   environment; the test resumes the stored sign-in, signs a window in with the
   password (not stored: only the installed desktop image may store it), reads
   the profile's language through a registered operation, submits edits of the
   work unit and a large plain request through the runtime's streamed upload,
   and prints how long the resume and the native sign-in took;
5. stops the runtime by closing its standard input and removes the root.

The password exists only in this process, the CLI's standard input and one
file under the disposable root. Run it with
``uv run --no-sync python -m dev.runtime_lifecycle.native_client_live``.
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

from dev.temporary_output import prepare_temp_root

from .caller_owned_root import AcceptanceError, Programs, caller_owned_runtime, require, run_cli

_PROFILE_NAME = "native-client-live"
_APPLICATION_MANIFEST = Path(__file__).resolve().parents[2] / "native" / "application" / "Cargo.toml"
_DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / "build" / "windows-x64" / "generated" / "contract.rs"


def _programs() -> Programs:
    scripts = Path(sysconfig.get_path("scripts"))
    suffix = ".exe" if sys.platform == "win32" else ""
    programs = Programs(
        aeat=scripts / f"aeat{suffix}",
        runtime=scripts / f"cadrumo-runtime{suffix}",
        mcp=scripts / f"cadrumo-mcp{suffix}",
    )
    require(programs.aeat.is_file() and programs.runtime.is_file(), "install the project entrypoints first")
    return programs


def _environment(root: Path) -> dict[str, str]:
    # The published authority the CLI and the runtime both read stays; every other product setting goes.
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith("CADRUMO_") or name.upper() == "CADRUMO_AUTHORITY_ROOT"
    }
    environment["CADRUMO_STORAGE_ROOT"] = str(root)
    # Native IPC acceptance is independent of the test runner's desktop session.
    environment["CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE"] = "1"
    return environment


def _profile_id(root: Path) -> str:
    """The one profile the root holds, by its bucket directory."""
    from uuid import UUID

    for directory in ("keystore", "buckets"):
        candidates = [entry.name for entry in (root / directory).glob("*") if entry.is_dir()]
        for name in candidates:
            try:
                return str(UUID(name))
            except ValueError:
                continue
    raise AcceptanceError("the created profile's bucket directory was not found")


def run(contract: Path, keep: bool) -> int:
    """Run the live test once; return cargo's exit status."""
    from cadrumo_runtime.application.development_root import mark_development_root

    programs = _programs()
    scratch = Path(tempfile.mkdtemp(prefix="native-client-live-", dir=prepare_temp_root()))
    try:
        root = scratch / "storage"
        environment = _environment(root)
        password = secrets.token_urlsafe(24)
        code, envelope = run_cli(
            programs,
            environment,
            "config",
            "profile",
            "create",
            _PROFILE_NAME,
            "--quiet",
            # Synthetic facts a Modelo 303 work unit needs, so the test can create one.
            "--entity-type",
            "natural_person",
            "--tax-id",
            "12345678Z",
            "--activity",
            "software services",
            "--tax-residence-jurisdiction-scope",
            "common_regime",
            "--iva-regime",
            "GENERAL",
            "--iva-m303-regime-composition",
            "general",
            "--no-iva-redeme-enrolled",
            "--no-iva-cash-accounting-regime-enrolled",
            "--no-iva-voluntary-sii-enrolled",
            "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
            "--secrets-stdin",
            secret={"passphrase": password, "passphrase_confirmation": password},
        )
        require(code == 0 and envelope.get("status") in {"success", "warning"}, f"profile create: {code} {envelope}")
        mark_development_root(root)
        profile_id = _profile_id(root)
        with caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log") as runtime:
            announcement = runtime.ready()
            require(announcement.get("kind") == "runtime_ready", f"readiness: {announcement}")
            code, envelope = run_cli(
                programs,
                environment,
                "config",
                "login",
                _PROFILE_NAME,
                "--secrets-stdin",
                secret={"passphrase": password},
            )
            require(code == 0, f"stored sign-in through the command line: {code} {envelope}")
            # A Modelo 303 work unit for the live test's edits to name; the
            # runtime admits an edit operand only for a work unit the profile holds.
            code, envelope = run_cli(programs, environment, "config", "profile", "complete-setup")
            require(code == 0, f"profile setup: {code} {envelope}")
            code, envelope = run_cli(
                programs,
                environment,
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "303",
                "--year",
                "2026",
                "--period",
                "1T",
                "--allow-not-applicable",
                "--quiet",
            )
            created = envelope.get("result")
            work_unit_id = created.get("work_unit_id") if isinstance(created, dict) else None
            if code != 0 or not isinstance(work_unit_id, str):
                raise AcceptanceError(f"work unit create: {code} {envelope}")
            password_file = scratch / "password"
            password_file.write_bytes(password.encode("utf-8"))
            cargo_environment = {
                **os.environ,
                "CADRUMO_CONTRACT_RS": str(contract),
                "CADRUMO_RUNTIME_LIVE_ROOT": str(root),
                "CADRUMO_RUNTIME_LIVE_VERSION": str(announcement["product_version"]),
                "CADRUMO_RUNTIME_LIVE_PROFILE_ID": profile_id,
                "CADRUMO_RUNTIME_LIVE_PASSWORD_FILE": str(password_file),
                "CADRUMO_RUNTIME_LIVE_WORK_UNIT": work_unit_id,
            }
            cargo = shutil.which("cargo")
            require(cargo is not None, "cargo is not on PATH")
            completed = subprocess.run(  # noqa: S603 -- the resolved cargo; no shell.
                [
                    str(cargo),
                    "test",
                    "--manifest-path",
                    str(_APPLICATION_MANIFEST),
                    "--features",
                    "platform",
                    "--offline",
                    "--lib",
                    "runtime_client::live_tests",
                    "--",
                    "--ignored",
                    "--nocapture",
                ],
                env=cargo_environment,
                check=False,
            )
            stopped = runtime.stop()
            print(f"runtime exit {stopped}; cargo exit {completed.returncode}")
            return completed.returncode
    finally:
        if keep:
            print(f"kept {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)


def main(arguments: list[str] | None = None) -> int:
    """Parse the options and run."""
    parser = argparse.ArgumentParser(prog="native_client_live", allow_abbrev=False)
    parser.add_argument("--contract", type=Path, default=_DEFAULT_CONTRACT, help="the generated contract.rs")
    parser.add_argument("--keep", action="store_true", help="keep the disposable root for inspection")
    options = parser.parse_args(arguments)
    try:
        return run(options.contract.resolve(strict=True), options.keep)
    except AcceptanceError as error:
        print(f"contradicted: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
