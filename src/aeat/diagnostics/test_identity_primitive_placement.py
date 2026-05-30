"""Structural enforcement tests for typed-id alias placement.

Each test parses every Python module under :mod:`aeat` with the
standard-library :mod:`ast` module and asserts the absence of one
structural failure mode for the typed-id alias placement rule. The
tests are real-behavior: no mocks, no fakes, no skipped variants. A
violation surfaces as a precise ``path:line`` location in the
assertion message so the failure points the operator at the source.
"""

from __future__ import annotations

import pytest

from aeat.diagnostics._identity_placement import (
    Finding,
    find_sibling_domain_id_imports,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _render(findings: list[Finding]) -> str:
    return "\n".join(finding.render() for finding in findings)


def test_no_sibling_domain_id_imports() -> None:
    """No ``domain.<a>`` module imports from ``domain.<b>._ids`` for ``a != b``.

    The registry-aliases module (``aeat.domain.calculations.registry._ids``)
    is the one explicit exception declared by the placement rule and is
    accepted from any domain.
    """

    findings = find_sibling_domain_id_imports()
    assert findings == [], "sibling-domain _ids imports detected:\n" + _render(findings)
