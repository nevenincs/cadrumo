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


@pytest.mark.parametrize(
    ("token", "member"),
    (
        pytest.param("pension", TipoRentaIrnr.PENSION, id="pension"),
        pytest.param("interest", TipoRentaIrnr.INTEREST, id="interest"),
    ),
)
def test_tipo_renta_irnr_is_str_and_hydrates_from_token(token: str, member: TipoRentaIrnr) -> None:
    """A StrEnum member equals its token and hydrates from the stored string."""
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


@pytest.mark.parametrize(
    ("kind", "carries_rate"),
    (
        pytest.param(ConvenioOverrideKind.FLAT, True, id="flat"),
        pytest.param(ConvenioOverrideKind.CEILING, True, id="ceiling"),
        pytest.param(ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF, False, id="allocation-domestic-tariff"),
        pytest.param(ConvenioOverrideKind.EXEMPT, False, id="exempt"),
    ),
)
def test_convenio_override_kind_rate_bearing_partition(kind: ConvenioOverrideKind, carries_rate: bool) -> None:
    """flat/ceiling carry a rate; allocation/exempt do not."""
    assert kind.carries_rate is carries_rate


def test_convenio_override_kind_rejects_unknown_token() -> None:
    """An unknown override kind is refused at hydration."""
    with pytest.raises(ValueError, match="not a valid ConvenioOverrideKind"):
        ConvenioOverrideKind("stacking")
