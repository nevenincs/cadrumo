"""Own the installed runtime that serves a packaging probe's disposable root."""

from __future__ import annotations

import sys
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .installed_tax_oracle import InstalledTaxEvidence


@contextmanager
def installed_cli_runtime(cli: Path, environment: Mapping[str, str], log: Path) -> Generator[None]:
    """Serve the explicit probe root through the installed caller-owned runtime."""
    from dev.runtime_lifecycle.caller_owned_root import Programs, caller_owned_runtime

    suffix = ".exe" if sys.platform == "win32" else ""
    programs = Programs(
        aeat=cli.resolve(strict=True),
        runtime=cli.with_name(f"cadrumo-runtime{suffix}").resolve(strict=True),
        mcp=cli.with_name(f"cadrumo-mcp{suffix}").resolve(strict=True),
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    with caller_owned_runtime(programs, environment, log) as runtime:
        ready = runtime.ready()
        if ready.get("kind") != "runtime_ready" or not isinstance(ready.get("pid"), int) or ready["pid"] <= 0:
            raise RuntimeError("installed runtime did not attest readiness")
        yield
    if runtime.exit_code != 64:
        raise RuntimeError(f"installed runtime did not settle its caller's stop: {runtime.exit_code}")


def run_installed_tax_oracle_with_runtime(
    cli: Path,
    *,
    storage_root: Path,
    work_dir: Path,
    cohort_source_digest: str,
    cohort_manifest_sha256: str,
    cohort_root_wheel_sha256: str,
    timeout_seconds: float = 180.0,
) -> InstalledTaxEvidence:
    """Run the tax oracle while its actual installed host owns the selected root."""
    from .installed_tax_oracle import isolated_product_environment, run_installed_tax_oracle

    work_dir.mkdir(parents=True, exist_ok=True)
    environment = isolated_product_environment(storage_root)
    with installed_cli_runtime(cli, environment, work_dir / "caller-owned-runtime.log"):
        return run_installed_tax_oracle(
            cli,
            storage_root=storage_root,
            work_dir=work_dir,
            cohort_source_digest=cohort_source_digest,
            cohort_manifest_sha256=cohort_manifest_sha256,
            cohort_root_wheel_sha256=cohort_root_wheel_sha256,
            timeout_seconds=timeout_seconds,
        )
