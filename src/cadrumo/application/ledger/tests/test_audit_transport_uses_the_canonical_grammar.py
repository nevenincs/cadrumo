"""The audit payload's transport is read by the grammar's owner, not re-parsed.

A provenance stamp is ``llm:<transport>-<reader>:<model>``, so the transport is
not the second colon-delimited segment -- it is the part of that segment before
the hyphen. Two surfaces split on the colon alone and published both halves glued
together: ``local-text`` where the field means ``local``.

**It was invisible while every read was on-host** and one label was as good as
another. With off-host reading re-sanctioned behind a per-invocation consent
gate, the same slice publishes ``openai-text`` as the provider of a document that
left the machine -- **wrong in a way a reader believes rather than questions**,
which is worse than a field that is missing.

**The fix is convergence, not a better split.** Two implementations of one
grammar agree only while somebody maintains both, and this pair had already
stopped agreeing. Both surfaces now delegate to the parser that owns the shape.

Every stamp here is built by :func:`~core.build_provenance_stamp` rather than
written as a literal. A fixture authored to the shape under test proves only that
the parser reads the fixture; driving the real builder means a change to the
grammar reaches these cases instead of leaving them asserting a shape nothing
produces any more.
"""

from __future__ import annotations

import pytest

from ....core.config import LLMProvider
from ....core.provenance_stamp import build_provenance_stamp, provenance_stamp_transport
from ..llm_classification import _transport_from_provenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("provider", list(LLMProvider))
def test_the_audit_transport_matches_the_canonical_parser(provider: LLMProvider) -> None:
    """Agreement over every provider, not a spot check on the one in front of us.

    Parameterised over the whole enum so a transport added later joins on the day
    it is declared rather than on the day somebody remembers this file.
    """
    stamp = build_provenance_stamp(provider=provider, reader="text", model="m1")

    assert _transport_from_provenance(stamp) == provenance_stamp_transport(stamp)


@pytest.mark.parametrize("provider", list(LLMProvider))
def test_the_reader_is_not_glued_onto_the_transport(provider: LLMProvider) -> None:
    """The defect itself, stated as the property rather than as the old output.

    Asserting the value is not ``"<transport>-text"`` would pass the day the
    reader label changes while the bug survives. What must hold is that the
    published value carries no reader at all.
    """
    stamp = build_provenance_stamp(provider=provider, reader="text", model="m1")

    published = _transport_from_provenance(stamp)

    # The enum spells its members upper-case and the stamp grammar lower-cases
    # them, so the comparison folds rather than asserting the enum's spelling --
    # which would test the builder's casing rather than the parser's split.
    assert published == provider.value.lower()
    assert "-" not in published


def test_a_second_reader_does_not_move_the_transport() -> None:
    """The discriminating case: one transport, two readers, one published value.

    A parser that returned the whole segment would report two different providers
    for one transport, which is exactly the mis-branching the audit field exists
    to prevent.
    """
    text = build_provenance_stamp(provider=LLMProvider.LOCAL, reader="text", model="m1")
    vision = build_provenance_stamp(provider=LLMProvider.LOCAL, reader="vision", model="m1")

    assert text != vision
    assert _transport_from_provenance(text) == _transport_from_provenance(vision)


def test_an_unreadable_stamp_surfaces_rather_than_being_blanked() -> None:
    """A shape the grammar does not cover is published whole, never as a transport.

    Falling back to a transport label would answer a question this cannot answer,
    and would drop exactly the artefact a consent withdrawal most needs to see.
    Falling back to empty would hide it just as well.
    """
    assert _transport_from_provenance("not-a-stamp") == "not-a-stamp"
    assert provenance_stamp_transport("not-a-stamp") is None
