"""Unit tests for :class:`aeat.models._applicability.ModeloApplicability`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ._applicability import ModeloApplicability
from ._categories import TaxpayerProfile

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_ALL: frozenset[TaxpayerProfile] = frozenset(TaxpayerProfile)


def test_happy_path_partition() -> None:
    """A clean 3-bucket partition constructs cleanly."""
    mandatory = frozenset({TaxpayerProfile.AUTONOMO_ED_SOLO})
    optional = frozenset({TaxpayerProfile.AUTONOMO_ED_CON_EMPLEADOS})
    exempt = _ALL - mandatory - optional
    record = ModeloApplicability(
        mandatory_profiles=mandatory,
        optional_profiles=optional,
        exempt_profiles=exempt,
        trigger_notes_es="happy-path partition",
    )
    assert record.mandatory_profiles == mandatory


def test_rejects_profile_in_two_buckets() -> None:
    """A profile appearing in both mandatory and optional raises."""
    overlap = frozenset({TaxpayerProfile.AUTONOMO_ED_SOLO})
    optional = overlap | frozenset({TaxpayerProfile.AUTONOMO_EO})
    exempt = _ALL - overlap - optional
    with pytest.raises(ValidationError):
        ModeloApplicability(
            mandatory_profiles=overlap,
            optional_profiles=optional,
            exempt_profiles=exempt,
            trigger_notes_es="overlap",
        )


def test_rejects_missing_profile() -> None:
    """A partition missing a profile raises."""
    mandatory = frozenset({TaxpayerProfile.AUTONOMO_ED_SOLO})
    optional = frozenset({TaxpayerProfile.AUTONOMO_EO})
    # Drop one profile from the exempt bucket so the partition is incomplete.
    exempt = (_ALL - mandatory - optional) - frozenset({TaxpayerProfile.SL})
    with pytest.raises(ValidationError):
        ModeloApplicability(
            mandatory_profiles=mandatory,
            optional_profiles=optional,
            exempt_profiles=exempt,
            trigger_notes_es="missing SL",
        )


def test_rejects_blank_trigger_notes() -> None:
    """Empty ``trigger_notes_es`` raises."""
    with pytest.raises(ValidationError):
        ModeloApplicability(
            mandatory_profiles=frozenset(),
            optional_profiles=frozenset(),
            exempt_profiles=_ALL,
            trigger_notes_es="   ",
        )
