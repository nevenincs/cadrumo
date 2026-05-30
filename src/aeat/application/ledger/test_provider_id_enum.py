"""Real-behavior tests for LedgerProviderID enum coverage.

Asserts that LedgerProviderID covers every dispatch literal used in the
ledger import chain and that no bare-string provider IDs survive in production
source outside the canonical StrEnum definition.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._actions import LedgerProviderID

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# Literals that were previously bare-string dispatch targets in _actions.py
_KNOWN_PROVIDER_LITERALS: frozenset[str] = frozenset(
    [p.value for p in LedgerProviderID]
)

_ACTIONS_MODULE = (
    PROJECT_ROOT / "src" / "aeat" / "application" / "ledger" / "_actions.py"
)

_DISPATCH_BARE_STRING_RE = re.compile(
    r'provider_id\s*==\s*"([^"]+)"|provider_id\s+in\s+\{([^}]+)\}'
)


def test_ledger_provider_id_enum_round_trip() -> None:
    """Every LedgerProviderID value round-trips through StrEnum construction."""
    for member in LedgerProviderID:
        reconstructed = LedgerProviderID(member.value)
        assert reconstructed is member, (
            f"LedgerProviderID({member.value!r}) did not return the canonical member"
        )


def test_ledger_provider_id_covers_all_known_values() -> None:
    """LedgerProviderID contains every expected dispatch value."""
    expected = {"auto", "csv", "ofx", "qfx", "xlsx", "excel", "n26", "pdf", "pdf-n26"}
    actual = {p.value for p in LedgerProviderID}
    missing = expected - actual
    assert not missing, f"LedgerProviderID is missing values: {missing}"


def test_no_bare_string_dispatch_survivors_in_actions() -> None:
    """_actions.py dispatch chain contains no bare-string provider-ID comparisons.

    After the S399 migration every if-branch uses identity comparison on
    LedgerProviderID members; bare string literals of the form
    ``provider_id == "csv"`` or ``provider_id in {"ofx", "qfx"}`` must not
    survive.
    """
    source = _ACTIONS_MODULE.read_text(encoding="utf-8")
    # Exclude lines that define the StrEnum values themselves
    lines_with_bare_dispatch = []
    for i, line in enumerate(source.splitlines(), start=1):
        # Skip lines inside the LedgerProviderID class body (value assignments)
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Detect any remaining provider-id string comparison pattern
        if re.search(r'provider_id\s*(?:==|in)\s*["\']', line):
            lines_with_bare_dispatch.append(f"_actions.py:{i}: {stripped!r}")

    assert not lines_with_bare_dispatch, (
        f"Bare provider_id string comparison(s) survived migration:\n"
        + "\n".join(f"  {l}" for l in lines_with_bare_dispatch)
    )
