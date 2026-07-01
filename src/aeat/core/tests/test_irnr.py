"""Unit tests for the closed IRNR treaty-surface enums.

The value tokens are asserted against the TRLIRNR / treaty vocabulary the
registry stores (``tipo_renta`` casilla tokens and the override-kind tokens the
``treaties/`` authoring tree will carry); a drift in a stored token would be a
boundary-hydration break, so the tests pin the exact strings.
"""

from __future__ import annotations

import pytest

from ...core import ConvenioOverrideKind, TipoRentaIrnr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_tipo_renta_irnr_tokens_match_registry_vocabulary() -> None:
    """The income-type axis carries exactly the TRLIRNR-declarable tokens."""
    assert {member.value for member in TipoRentaIrnr} == {
        "general",
        "ue_residente",
        "pension",
        "interest",
        "ganancia_patrimonial",
        "inmobiliaria",
    }


def test_tipo_renta_irnr_is_str_and_hydrates_from_token() -> None:
    """A StrEnum member equals its token and hydrates from the stored string."""
    for token, member in (
        ("pension", TipoRentaIrnr.PENSION),
        ("interest", TipoRentaIrnr.INTEREST),
    ):
        assert TipoRentaIrnr(token) is member
        assert member == token
        assert str(member) == token


def test_convenio_override_kind_tokens() -> None:
    """The override-kind axis carries the four decided treaty precedence kinds."""
    assert {member.value for member in ConvenioOverrideKind} == {
        "flat",
        "ceiling",
        "allocation_domestic_tariff",
        "exempt",
    }


def test_convenio_override_kind_rate_bearing_partition() -> None:
    """flat/ceiling carry a rate; allocation/exempt do not."""
    for kind, carries_rate in (
        (ConvenioOverrideKind.FLAT, True),
        (ConvenioOverrideKind.CEILING, True),
        (ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF, False),
        (ConvenioOverrideKind.EXEMPT, False),
    ):
        assert kind.carries_rate is carries_rate


def test_convenio_override_kind_rejects_unknown_token() -> None:
    """An unknown override kind is refused at hydration."""
    with pytest.raises(ValueError, match="not a valid ConvenioOverrideKind"):
        ConvenioOverrideKind("stacking")
