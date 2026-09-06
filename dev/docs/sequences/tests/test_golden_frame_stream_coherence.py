"""A committed golden frame must not claim two stream shapes at once.

:class:`dev.docs.sequences.golden_store.GoldenFrame` covers stdout and stderr
independently: ``envelope`` is the verbatim document, ``envelope_source`` names
the stream that carried it, and ``text`` / ``stderr_text`` hold the normalised
content of whichever stream did NOT carry it. Three coherence rules keep those
fields from describing two different runs -- an envelope without its source, a
source without its envelope, and a stream credited with the envelope while also
storing raw content.

Every rule is a refusal on a PERSISTED record, so a golden that violates one is
committed, replayed, and diffed against forever; the incoherent half simply
never participates in the comparison. The refusals below are asserted through
the real model validator, and the two coherent shapes are asserted alongside
them so the gate cannot pass by refusing everything.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..golden_store import GoldenFrame
from ..schema import FrameKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_PAIRED = "'envelope' and 'envelope_source' are set together or not at all"


def _frame(**overrides: object) -> GoldenFrame:
    """Build a frame whose only variation is the stream fields under test."""
    fields: dict[str, object] = {"kind": FrameKind.COMMAND, "argv": ("aeat", "--help"), "exit_code": 0}
    fields.update(overrides)
    return GoldenFrame(**fields)  # type: ignore[arg-type]


def test_an_envelope_without_its_source_is_refused() -> None:
    """A document with no named stream cannot be replayed against either one."""
    with pytest.raises(ValidationError, match=_PAIRED):
        _frame(envelope={"status": "ok"})


def test_a_source_without_its_envelope_is_refused() -> None:
    """The other direction of the same pairing, which one-sided guards miss."""
    with pytest.raises(ValidationError, match=_PAIRED):
        _frame(envelope_source="stdout")


def test_stdout_cannot_both_carry_the_envelope_and_store_text() -> None:
    """``text`` is the stdout content for frames where stdout held no envelope."""
    with pytest.raises(ValidationError, match="stdout carried the envelope"):
        _frame(envelope={"status": "ok"}, envelope_source="stdout", text="ignored stdout")


def test_stderr_cannot_both_carry_the_envelope_and_store_text() -> None:
    """The stderr mirror of the rule above, on the refusal-envelope path."""
    with pytest.raises(ValidationError, match="stderr carried the envelope"):
        _frame(envelope={"status": "error"}, envelope_source="stderr", stderr_text="ignored stderr")


def test_a_frame_whose_only_output_is_an_exit_code_is_accepted() -> None:
    """Anti-vacuity: an all-absent frame is legitimate and must not be refused."""
    frame = _frame()

    assert frame.envelope is None
    assert frame.text is None
    assert frame.stderr_text is None


def test_an_envelope_on_one_stream_with_content_on_the_other_is_accepted() -> None:
    """Anti-vacuity: the rules bind a stream to itself, not to both streams."""
    frame = _frame(envelope={"status": "ok"}, envelope_source="stdout", stderr_text="a warning")

    assert frame.envelope_source == "stdout"
    assert frame.stderr_text == "a warning"
