"""Shim-verification subroutine for the restructure semver-bump gate.

Per the restructure ADR (`.vault/adr/2026-04-30-aeat-restructure-adr.md`,
"Shim-verification gate"), the executing agent imports each declared
shim path in a clean Python subprocess and asserts the re-exported
symbols are reachable. Any shim that fails the import gate makes the
semver rule see the break and fire `major` instead of `minor`. This
script is the deterministic mechanism that makes the no-override
semver rule safe.

Pre-Step-7 the OLD module paths (e.g. ``aeat.errors``) are the
canonical homes — the imports succeed because the symbols still live
there. Post-Step-7 the same paths become re-export shims, and the
imports succeed because the shims forward to the canonical
``aeat.core.errors`` / ``aeat.adapters.outbound.aeat.export`` etc.
locations. Either way, the script asserts a stable contract: every
listed import works.

Failure mode = the symbol is missing from the shim's __init__.py
(broken shim). The script returns a non-zero exit code and writes a
machine-readable JSON report to stdout so the calling agent can
classify each failure.

Usage:

    uv run --no-sync python scripts/verify_shims.py

Exit codes:
    0 — every listed import succeeds.
    1 — at least one import failed; details in the stdout JSON.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import NamedTuple


class ShimSpec(NamedTuple):
    """One shim contract entry: import path + exported symbols."""

    module: str
    symbols: tuple[str, ...]
    rationale: str


# The shim contract per ADR Public surface and semver section. Every
# entry is a public-surface import that MUST keep working across the
# restructure. Pre-Step-7 these are direct imports; post-Step-7 they
# are shim re-exports. The script doesn't care which — it asserts the
# import resolves the listed symbols.
SHIM_CONTRACT: tuple[ShimSpec, ...] = (
    ShimSpec(
        module="aeat.errors",
        symbols=(
            "AeatError",
            "ErrorCode",
            "ErrorCategory",
            "ErrorEnvelope",
            "ERROR_REGISTRY",
            "register",
            "build_error_envelope",
            "render_error_text",
            "render_error_json",
            "get_error_exit_code",
            "get_registered_error_code",
            "resolve_error_message",
            "scrub_error_context",
            "FormulasError",
            "RulesetValidationError",
            "FormulaCycleError",
            "CasillaNotDefinedError",
            "AmbiguousPeriodError",
            "MissingRulesetError",
            "EvaluationError",
            "AuditDiscrepancyError",
            "McpLaunchError",
            "FilingFixtureError",
            "FixtureProvisioningError",
            "SiteHealthError",
            "AeatObservabilityError",
            "DeprecatedAliasError",
            "MovedAliasError",
        ),
        rationale=(
            "Documented public surface — error registry + rendering pipeline + 11 "
            "domain-specific exceptions. Per ADR, all preserved via re-export shim "
            "from aeat.core.errors / aeat.domain.formulas / aeat.entrypoints.mcp / "
            "aeat.domain.testing."
        ),
    ),
    ShimSpec(
        module="aeat.auth",
        symbols=(
            "AeatAuthenticator",
            "AeatSession",
            "AeatLoginAssertion",
            "AuthProvider",
            "AuthProviderKind",
            "ClaveMovilAuthProvider",
            "select_provider",
            "AeatAccessGate",
            "AeatGateEnvSnapshot",
            "AeatLiveReadNotEnabledError",
            "restrict_file_permissions",
        ),
        rationale=(
            "Documented public surface — AEAT auth + access-gate + restrict_file_permissions. "
            "Per ADR, preserved via shim from aeat.adapters.outbound.aeat.auth + "
            "aeat.application.auth + aeat.core.access_gate + aeat.core.file_permissions."
        ),
    ),
    ShimSpec(
        module="aeat.submission",
        symbols=("LiveSubmitForbiddenError",),
        rationale=(
            "LiveSubmitForbiddenError is preserved via shim post-Step-7 "
            "(canonical home moves to aeat.core.access_gate._errors)."
        ),
    ),
    ShimSpec(
        module="aeat.formulas",
        symbols=(
            "Engine",
            "FiscalPeriod",
            "Quarter",
            "Ruleset",
            "Discrepancy",
            "ComputationLedger",
            "RulesetRegistry",
            "get_registry",
        ),
        rationale=(
            "Public surface for the per-modelo formula engine. Stable across the "
            "restructure (moves to aeat.domain.formulas; shim re-export from old path)."
        ),
    ),
)


def _verify_one(shim: ShimSpec) -> dict[str, object]:
    """Run one shim's symbols through `import` in a clean subprocess.

    Args:
        shim: The shim spec to verify.

    Returns:
        A dict with keys ``module``, ``status``, ``error`` (only when
        status != "ok"), and ``rationale``.
    """
    symbol_list = ", ".join(shim.symbols)
    program = f"from {shim.module} import {symbol_list}\n"
    try:
        # SHIM_CONTRACT is a static, audit-controlled list — no untrusted input
        # reaches subprocess.run().
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", program],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {
            "module": shim.module,
            "status": "timeout",
            "error": "subprocess timeout after 30s",
            "rationale": shim.rationale,
        }
    if result.returncode == 0:
        return {
            "module": shim.module,
            "status": "ok",
            "symbols_verified": len(shim.symbols),
            "rationale": shim.rationale,
        }
    return {
        "module": shim.module,
        "status": "broken",
        "error": (result.stderr or result.stdout).strip(),
        "rationale": shim.rationale,
    }


def main() -> int:
    """Verify every shim in :data:`SHIM_CONTRACT`.

    Returns:
        0 if every shim passed, 1 otherwise.
    """
    results = [_verify_one(shim) for shim in SHIM_CONTRACT]
    print(json.dumps({"results": results}, indent=2))  # noqa: T201
    return 0 if all(r["status"] == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
