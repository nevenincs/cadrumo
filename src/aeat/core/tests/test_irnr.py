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
    cases = (
        ("general", TipoRentaIrnr.GENERAL),
        ("ue_residente", TipoRentaIrnr.UE_RESIDENTE),
        ("pension", TipoRentaIrnr.PENSION),
        ("dividend", TipoRentaIrnr.DIVIDEND),
        ("interest", TipoRentaIrnr.INTEREST),
        ("ganancia_patrimonial", TipoRentaIrnr.GANANCIA_PATRIMONIAL),
        ("inmobiliaria", TipoRentaIrnr.INMOBILIARIA),
    )

    assert {member.value for member in TipoRentaIrnr} == {token for token, _ in cases}
    for token, member in cases:
        assert TipoRentaIrnr(token) is member
        assert member == token
        assert str(member) == token


def test_convenio_override_kind_tokens_and_rate_bearing_partition() -> None:
    """The override-kind axis carries the four decided treaty precedence kinds."""
    cases = (
        ("flat", ConvenioOverrideKind.FLAT, True),
        ("ceiling", ConvenioOverrideKind.CEILING, True),
        ("allocation_domestic_tariff", ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF, False),
        ("exempt", ConvenioOverrideKind.EXEMPT, False),
    )

    assert {member.value for member in ConvenioOverrideKind} == {token for token, _, _ in cases}
    for token, kind, carries_rate in cases:
        assert ConvenioOverrideKind(token) is kind
        assert kind == token
        assert kind.carries_rate is carries_rate

    with pytest.raises(ValueError, match="not a valid ConvenioOverrideKind"):
        ConvenioOverrideKind("stacking")
