"""Tests for the closed taxonomy of AEAT-reported deuda objects.

The member set is the closed axis contract: the stored tokens are what an
adapter hydrates from AEAT's reported objeto tributario label and what a
persisted snapshot carries, so a renamed token silently changes stored data.
The independence assertions pin the separation from
:class:`PostFilingEventKind`, which classifies an event stream rather than a
standing liability.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from ..objeto_tributario import ObjetoTributario
from ..post_filing_event import PostFilingEventKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_member_set_is_closed_and_tokens_are_exact() -> None:
    """The axis carries exactly these five members with these stored tokens."""
    assert {member.name: member.value for member in ObjetoTributario} == {
        "INTERES_DEMORA": "interes_demora",
        "RECARGO_APREMIO": "recargo_apremio",
        "SANCION": "sancion",
        "LIQUIDACION": "liquidacion",
        "OTRO": "otro",
    }


def test_the_axis_is_a_strenum_so_members_serialise_as_their_tokens() -> None:
    """A member is substitutable for its token in str and JSON positions."""
    assert issubclass(ObjetoTributario, StrEnum)
    assert str(ObjetoTributario.SANCION) == "sancion"
    assert ObjetoTributario("recargo_apremio") is ObjetoTributario.RECARGO_APREMIO


def test_an_unreported_label_is_refused_rather_than_coerced() -> None:
    """A label outside the axis raises; it is never silently mapped to OTRO.

    ``OTRO`` is a classification an adapter chooses deliberately for an
    unrecognised label. Making the enum itself coerce would erase the
    difference between "AEAT said otro" and "we did not recognise this".
    """
    with pytest.raises(ValueError, match="is not a valid ObjetoTributario"):
        ObjetoTributario("providencia_de_apremio")


def test_the_axis_is_independent_of_the_post_filing_event_taxonomy() -> None:
    """Neither enum is derived from or substitutable for the other.

    A deuda row is a standing liability carrying an amount and a procedural
    state; a post-filing event is an announcement in a stream. Sharing one
    type would give two entities one identity and lifecycle.
    """
    assert not issubclass(ObjetoTributario, PostFilingEventKind)
    assert not issubclass(PostFilingEventKind, ObjetoTributario)


def test_the_shared_liquidacion_noun_is_two_distinct_members() -> None:
    """``liquidacion`` names a legal noun on both axes without joining them.

    Both taxonomies legitimately carry the Spanish noun: one classifies the
    notified *event* that a liquidación was issued, the other classifies the
    resulting *debt's* object. The tokens coincide because the legal noun
    coincides, which is why identity — not token disjointness — is the
    property that keeps the axes separate.
    """
    assert ObjetoTributario.LIQUIDACION is not PostFilingEventKind.LIQUIDACION
    assert type(ObjetoTributario.LIQUIDACION) is not type(PostFilingEventKind.LIQUIDACION)


def test_the_axis_is_not_a_widening_of_the_post_filing_event_taxonomy() -> None:
    """The deuda-specific objects cannot be expressed by the event taxonomy.

    This is the substantive reason the axis is its own enum rather than added
    members on the existing one: a recargo de apremio and an AEAT-assessed
    interés de demora are debt objects, and the event taxonomy has no member
    for either — its nearest rows classify the *notification* announcing an
    apremio, not the surcharge itself.
    """
    event_tokens = {member.value for member in PostFilingEventKind}
    assert ObjetoTributario.RECARGO_APREMIO.value not in event_tokens
    assert ObjetoTributario.INTERES_DEMORA.value not in event_tokens
