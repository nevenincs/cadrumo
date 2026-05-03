"""Import contract for retired legacy ruleset citation audits."""

from __future__ import annotations

import pytest

from aeat.entrypoints.cli.audit._helpers import validate_citation_coverage

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_legacy_ruleset_citation_audit_is_disabled() -> None:
    """Ruleset citation coverage must move through the registry validator."""
    with pytest.raises(ValueError, match="legacy ruleset citation audits are disabled"):
        validate_citation_coverage(object())
