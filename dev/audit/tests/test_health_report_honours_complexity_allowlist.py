"""The health report consults the reviewed complexity allowlist, not just the CLI.

The allowlist was first wired into ``dev.audit.complexity``'s own CLI path only.
Both surfaces call the same ``_classify_*`` helpers, but they build the ceiling
mapping independently, so the report kept classifying against the bare baseline
and its dimension stayed at its old count while the tool reported the reduced
one. An acceptance that moves the tool but not the reported signal is worse than
no acceptance: it reads as applied while the number anyone watches is unchanged.

Marked integration because it drives the real radon and complexipy scans over
the whole production tree, which is the only way to assert the REPORT's own
verdict rather than a re-implementation of it.
"""

from __future__ import annotations

import re

import pytest

from ..complexity_allowlist import ALLOWLIST_PATH, load_allowlist
from ..report import audit_complexity

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_no_reviewed_acceptance_is_reported_as_a_failing_hotspot() -> None:
    """Every allowlisted key is absent from the health report's failing set.

    Anti-vacuity: the committed allowlist must be non-empty, or a report with
    any failing rows at all would satisfy this trivially.
    """
    allowlist = load_allowlist(is_test_run=False, path=ALLOWLIST_PATH)
    accepted = {
        **allowlist.cyclomatic,
        **allowlist.maintainability,
        **allowlist.cognitive,
    }
    assert accepted, "the committed allowlist is empty, so this gate would pass vacuously"

    dimension = audit_complexity()

    # The key is EXTRACTED from each rendered line and compared exactly, never
    # matched as a substring. A substring test reports a false leak the moment
    # one accepted key is a prefix of another failing one -- `...::f` inside
    # `...::f_extended`, or a bare function inside a method of the same name --
    # which is precisely how this assertion first failed against a report that
    # was in fact correct.
    matches = (re.match(r"\s*\S+\s*\([\d.\s]+\)\s+(\S+)", line) for line in dimension.details)
    reported_keys = {match.group(1) for match in matches if match}
    assert reported_keys, "no key parsed from the report's findings; the line shape changed and this gate is blind"
    leaked = sorted(accepted.keys() & reported_keys)
    assert leaked == [], (
        f"{len(leaked)} reviewed acceptance(s) still reported as failing by the health report, "
        f"so the report is not consulting the allowlist: {leaked[:5]}"
    )
