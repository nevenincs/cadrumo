"""The frame grammar's documented sigils are joined to the dispatch table.

``@static`` was dispatched, named in the refusal an author sees when they
mistype a sigil, and referenced by the ``@blocked`` entry as the thing
``@blocked`` explains -- while the grammar list itself never introduced it.
An author who typed it correctly got a frame; an author reading the grammar
to find out how could not learn it existed.
"""

from __future__ import annotations

import re

import pytest

from .. import parser

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

#: A frame line in the module docstring's grammar list: a sigil before ``aeat``.
_FRAME_BULLET = re.compile(r"^- ``(@[a-z]+) aeat", re.MULTILINE)


def _documented_frame_sigils() -> frozenset[str]:
    """Sigils the grammar list introduces as declaring a frame."""
    assert parser.__doc__ is not None, "the module docstring is the grammar under test"
    return frozenset(_FRAME_BULLET.findall(parser.__doc__))


def test_the_grammar_introduces_every_sigil_that_declares_a_frame() -> None:
    """A sigil the parser accepts that the grammar never teaches.

    This is the direction that failed. The parser dispatched ``@static`` and
    told authors it was accepted, and the only description of the grammar
    did not carry a line for it.
    """
    untaught = sorted(frozenset(parser._FRAME_SIGILS) - _documented_frame_sigils())

    assert not untaught, (
        f"the parser declares a frame for {untaught}, which the grammar list never introduces; "
        "an author cannot write a frame the only description of the grammar omits"
    )


def test_the_grammar_introduces_no_frame_sigil_the_parser_rejects() -> None:
    """The inverse: a documented frame line the parser would refuse.

    A sigil withdrawn from the dispatch table leaves its grammar bullet
    standing, and the bullet reads exactly like the ones still accepted.
    """
    phantom = sorted(_documented_frame_sigils() - frozenset(parser._FRAME_SIGILS))

    assert not phantom, (
        f"the grammar list introduces {phantom} as frame lines, which the parser does not dispatch; "
        "an author following the grammar gets a refusal"
    )
