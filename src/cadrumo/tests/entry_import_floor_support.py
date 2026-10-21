"""Generic fresh-process helpers for entrypoint import-floor tests."""

from __future__ import annotations

import json
import sys

from cadrumo.tests.audited_process import run_audited_process

DENIED_IMPORT_SUBTREES: tuple[str, ...] = (
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "typer",
    "click",
    "rich",
    "textual",
    "yaml",
    "i18n",
    "rtoml",
    "asyncio",
    "importlib.metadata",
    "logging.config",
    "logging.handlers",
)

LOGGING_IMPORT_CLOSURE: frozenset[str] = frozenset(
    {
        "cadrumo",
        "cadrumo.core",
        "cadrumo.core.cli_metadata",
        "cadrumo.core.diagnostic_log",
        "cadrumo.core.hashing",
        "cadrumo.core.iban",
        "cadrumo.core.logging",
        "cadrumo.core.process_binding",
        "cadrumo.core.redaction",
        "cadrumo.core.redaction.rules",
        "cadrumo.core.redaction.tax_identity_admission",
        "cadrumo.core.type_guards",
    }
)

_PROBE = """
import json, sys
__import__(sys.argv[1])
print(json.dumps(sorted(sys.modules)))
"""


def imported_modules(module: str) -> frozenset[str]:
    """Return every module held after importing ``module`` in a fresh process."""
    completed = run_audited_process(
        [sys.executable, "-I", "-c", _PROBE, module],
        capture_output=True,
        text=True,
        check=False,
        timeout=None,
    )
    assert completed.returncode == 0, completed.stderr
    loaded: object = json.loads(str(completed.stdout).strip().splitlines()[-1])
    assert isinstance(loaded, list)
    names = frozenset(str(name) for name in loaded)
    assert module in names, f"the probe never imported {module}"
    return names


def denied_imports(names: frozenset[str]) -> list[str]:
    """List loaded modules under a declared denied subtree."""
    return sorted(
        name for name in names if any(name == root or name.startswith(f"{root}.") for root in DENIED_IMPORT_SUBTREES)
    )


def unlisted_modules(
    names: frozenset[str],
    allowed: frozenset[str],
) -> list[str]:
    """List loaded ``cadrumo`` modules outside ``allowed``."""
    return sorted(name for name in names if (name == "cadrumo" or name.startswith("cadrumo.")) and name not in allowed)
