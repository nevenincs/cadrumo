"""Development-only checks for authored verification vocabulary declarations."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_verification import VerificationRoundingCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_vocabulary_matches_what_the_registry_actually_declares() -> None:
    """The runtime vocabulary includes every value used by authored declarations."""
    declared = {
        match.group(1)
        for path in Path("src/cadrumo/_data/registry").rglob("verification_expectations/*.toml")
        for match in re.finditer(r'rounding = "([^"]+)"', path.read_text(encoding="utf-8"))
    }

    assert declared, "no verification rounding declarations found; the scan is not measuring anything"
    assert declared <= {code.value for code in VerificationRoundingCode}
