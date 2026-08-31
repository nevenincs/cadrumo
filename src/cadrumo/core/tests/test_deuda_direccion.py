"""Tests for the owed-versus-refundable direction axis on an AEAT deuda.

Direction is carried as a field so it can never disagree with an amount's
sign. These tests pin the closed member set and the separation from
:class:`AmendmentLiabilityDirection`, a different concept with a similar name.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from ..amendment_kind_regime import AmendmentLiabilityDirection
from ..deuda_direccion import DeudaDireccion

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_member_set_is_closed_and_tokens_are_exact() -> None:
    """The axis carries exactly the two flow directions AEAT reports."""
    assert {member.name: member.value for member in DeudaDireccion} == {
        "DEUDOR": "deudor",
        "ACREEDOR": "acreedor",
    }


def test_the_axis_is_a_strenum_so_members_serialise_as_their_tokens() -> None:
    assert issubclass(DeudaDireccion, StrEnum)
    assert str(DeudaDireccion.DEUDOR) == "deudor"
    assert DeudaDireccion("acreedor") is DeudaDireccion.ACREEDOR


def test_direction_carries_no_sign_vocabulary() -> None:
    """No member encodes flow as an arithmetic sign.

    The axis exists so an amount can stay a non-negative magnitude. A member
    named or valued after a sign would invite a caller to reconstruct
    direction from the number instead of reading the field.
    """
    tokens = {member.value for member in DeudaDireccion} | {member.name for member in DeudaDireccion}
    assert not any(sign in token for token in tokens for sign in ("+", "-", "negative", "positive"))


def test_the_axis_is_independent_of_the_amendment_liability_direction() -> None:
    """Neither enum is derived from or substitutable for the other.

    ``AmendmentLiabilityDirection`` classifies whether correcting a
    declaration raises or lowers the declared liability, selecting between the
    complementaria and rectificación procedures. This axis classifies which
    way an already-assessed amount flows.
    """
    assert not issubclass(DeudaDireccion, AmendmentLiabilityDirection)
    assert not issubclass(AmendmentLiabilityDirection, DeudaDireccion)
    assert {member.value for member in DeudaDireccion}.isdisjoint({m.value for m in AmendmentLiabilityDirection})
