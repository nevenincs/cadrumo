"""Unit tests for the closed IRNR treaty-surface enums.

The value tokens are asserted against the TRLIRNR / treaty vocabulary the
registry stores (``tipo_renta`` casilla tokens and the override-kind tokens the
``treaties/`` authoring tree will carry); a drift in a stored token would be a
boundary-hydration break, so the tests pin the exact strings.

See Also:
    :mod:`~core.irnr`
        Core closed-axis declarations for IRNR income type and treaty override
        semantics.
    :class:`~core.TipoRentaIrnr`
        Typed income-category axis hydrated from registry ``tipo_renta`` tokens.
    :class:`~core.ConvenioOverrideKind`
        Typed treaty override-kind axis whose ``carries_rate`` partition is
        asserted here.
    :class:`~domain.calculations.registry.ConvenioAuthority`
        Cross-cutting treaty authority that consumes these enum members.
    :func:`~domain.calculations.registry._formula_runtime_irnr.evaluate_irnr_resolve_tipo_gravamen`
        IRNR rate-resolution path that hydrates and branches on the same axes.
"""

from __future__ import annotations

import pytest

from ..irnr import ConvenioOverrideKind, TipoRentaIrnr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TIPO_RENTA_IRNR_CASES = (
    pytest.param("general", TipoRentaIrnr.GENERAL, id="general"),
    pytest.param("ue_residente", TipoRentaIrnr.UE_RESIDENTE, id="ue-residente"),
    pytest.param("pension", TipoRentaIrnr.PENSION, id="pension"),
    pytest.param("dividend", TipoRentaIrnr.DIVIDEND, id="dividend"),
    pytest.param("interest", TipoRentaIrnr.INTEREST, id="interest"),
    pytest.param("ganancia_patrimonial", TipoRentaIrnr.GANANCIA_PATRIMONIAL, id="ganancia-patrimonial"),
    pytest.param("inmobiliaria", TipoRentaIrnr.INMOBILIARIA, id="inmobiliaria"),
    pytest.param("canones", TipoRentaIrnr.CANONES, id="canones"),
)
_TIPO_RENTA_IRNR_TOKENS = frozenset(
    {
        "general",
        "ue_residente",
        "pension",
        "dividend",
        "interest",
        "ganancia_patrimonial",
        "inmobiliaria",
        "canones",
    },
)

_CONVENIO_OVERRIDE_CASES = (
    pytest.param("flat", ConvenioOverrideKind.FLAT, True, id="flat"),
    pytest.param("ceiling", ConvenioOverrideKind.CEILING, True, id="ceiling"),
    pytest.param(
        "allocation_domestic_tariff",
        ConvenioOverrideKind.ALLOCATION_DOMESTIC_TARIFF,
        False,
        id="allocation-domestic-tariff",
    ),
    pytest.param("exempt", ConvenioOverrideKind.EXEMPT, False, id="exempt"),
)
_CONVENIO_OVERRIDE_TOKENS = frozenset(
    {
        "flat",
        "ceiling",
        "allocation_domestic_tariff",
        "exempt",
    },
)


def test_tipo_renta_irnr_tokens_match_registry_vocabulary() -> None:
    """The income-type axis carries exactly the TRLIRNR-declarable tokens."""
    assert {member.value for member in TipoRentaIrnr} == _TIPO_RENTA_IRNR_TOKENS


@pytest.mark.parametrize(("token", "member"), _TIPO_RENTA_IRNR_CASES)
def test_tipo_renta_irnr_token_hydrates_to_member(token: str, member: TipoRentaIrnr) -> None:
    assert TipoRentaIrnr(token) is member
    assert member == token
    assert str(member) == token


def test_convenio_override_kind_tokens_and_rate_bearing_partition() -> None:
    """The override-kind axis carries the four decided treaty precedence kinds."""
    assert {member.value for member in ConvenioOverrideKind} == _CONVENIO_OVERRIDE_TOKENS


@pytest.mark.parametrize(("token", "kind", "carries_rate"), _CONVENIO_OVERRIDE_CASES)
def test_convenio_override_kind_token_hydrates_to_member(
    token: str,
    kind: ConvenioOverrideKind,
    carries_rate: bool,
) -> None:
    assert ConvenioOverrideKind(token) is kind
    assert kind == token
    assert kind.carries_rate is carries_rate


def test_convenio_override_kind_rejects_unknown_token() -> None:
    with pytest.raises(ValueError, match="not a valid ConvenioOverrideKind"):
        ConvenioOverrideKind("stacking")
