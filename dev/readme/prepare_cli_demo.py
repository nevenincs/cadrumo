"""Prepare the isolated synthetic data used by the README CLI recording."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

from cadrumo.core import is_link_like

from .._paths import REPO_ROOT, UTF_8

_UTF_8: Final[str] = UTF_8

VAR_ROOT = REPO_ROOT / "var"
DEMO_ROOT = VAR_ROOT / "readme-demo"
DEMO_PASSPHRASE = "readme-demo-only-synthetic-passphrase-2026"  # noqa: S105 - published synthetic value
_CLI_BOOTSTRAP = "from cadrumo.entrypoints.cli import main; main()"


def _reset_demo_root() -> None:
    """Recreate the demo root after proving recursive cleanup cannot escape ``var``."""
    resolved_repo = REPO_ROOT.resolve(strict=True)
    resolved_var = VAR_ROOT.resolve(strict=False)
    resolved_demo = DEMO_ROOT.resolve(strict=False)
    if is_link_like(VAR_ROOT):
        raise RuntimeError(f"refusing to use symlinked var root: {VAR_ROOT}")
    try:
        resolved_var.relative_to(resolved_repo)
    except ValueError as exc:
        raise RuntimeError(f"refusing demo root outside repository: {resolved_var}") from exc
    try:
        relative_demo = resolved_demo.relative_to(resolved_var)
    except ValueError as exc:
        raise RuntimeError(f"refusing cleanup outside {resolved_var}") from exc
    if relative_demo == Path("."):
        raise RuntimeError("refusing to clean the var root itself")
    if is_link_like(DEMO_ROOT):
        raise RuntimeError(f"refusing to clean symlinked demo root: {DEMO_ROOT}")
    if DEMO_ROOT.exists():
        shutil.rmtree(resolved_demo)
    DEMO_ROOT.mkdir(parents=True)


def demo_environment() -> dict[str, str]:
    """Return a clean Cadrumo environment rooted in the disposable demo directory."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    environment.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(DEMO_ROOT),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "CADRUMO_SECRET_PASSPHRASE": DEMO_PASSPHRASE,
            "CADRUMO_SECRET_STORE_BACKEND": "unsecured",
            "CADRUMO_SECRET_STORE_DIR": str(DEMO_ROOT / "secrets"),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
    )
    return environment


def _run_cli(stage: str, *arguments: str, environment: dict[str, str]) -> None:
    """Run one real CLI process and surface its diagnostics if setup fails."""
    result = subprocess.run(  # noqa: S603 - executable and arguments are developer-owned constants
        [sys.executable, "-c", _CLI_BOOTSTRAP, *arguments],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        timeout=180,
        check=False,
    )
    if result.returncode == 0:
        return
    diagnostics = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    raise RuntimeError(f"{stage} failed with exit code {result.returncode}\n{diagnostics}")


def prepare_demo() -> None:
    """Create the proven profile and persisted Modelo 115 observation."""
    _reset_demo_root()
    environment = demo_environment()
    _run_cli(
        "profile setup",
        "config",
        "profile",
        "create",
        "operator",
        "--quiet",
        "--accept-defaults",
        "--entity-type",
        "natural_person",
        "--tax-id",
        "12345678Z",
        "--name",
        "Operator",
        "--surnames",
        "Quickfile",
        "--activity",
        "design",
        environment=environment,
    )
    observation = json.dumps(
        {
            "source_kind": "ledger_transaction",
            "source_object_id": "rent-ledger-row-001",
            "perceptor_nif": "B12345678",
            "perceptor_name": "Arrendador Ejemplo SL",
            "scheme": "arrendamiento_urbano",
            "taxable_base": "2700.00",
            "retencion_amount": "513.00",
            "accrued_on": "2026-03-15",
        },
        separators=(",", ":"),
    )
    _run_cli(
        "retencion observation setup",
        "--format",
        "json",
        "app",
        "modelo",
        "aggregate",
        "--modelo",
        "115",
        "--year",
        "2026",
        "--period",
        "1T",
        "--retencion-observation",
        observation,
        environment=environment,
    )


def main() -> None:
    """Prepare the demo and print the stable renderer handoff marker."""
    prepare_demo()
    print("demo ready")


if __name__ == "__main__":
    main()
