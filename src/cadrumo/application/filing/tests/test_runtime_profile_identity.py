"""Runtime filing profiles validate Spanish tax identity at construction."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..runtime import ModeloOperatorProfile, filing_profile_from_taxpayer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_modelo_operator_profile_uses_subject_tax_id_validation() -> None:
    """Runtime filing profiles reject invalid NIF/NIE/CIF checksums."""
    profile = ModeloOperatorProfile(tax_id="12345678Z", display_name="Runtime identity")

    assert profile.tax_id == "12345678Z"

    with pytest.raises(ValidationError):
        ModeloOperatorProfile(tax_id="12345678A", display_name="Invalid identity")


def test_filing_profile_projection_keeps_validated_subject_tax_id() -> None:
    """The taxpayer-profile projector preserves the checked identity boundary."""
    source = ModeloOperatorProfile(tax_id="12345678Z", display_name="Source identity")

    projected = filing_profile_from_taxpayer(source, display_name=source.display_name)

    assert projected.tax_id == source.tax_id
    assert projected.display_name == source.display_name


def test_modelo_test_profile_uses_subject_tax_id_validation() -> None:
    """The public filing test helper cannot smuggle malformed tax IDs."""
    with pytest.raises(ValidationError):
        ModeloOperatorProfile(tax_id="12345678A", display_name="Invalid fixture identity")
