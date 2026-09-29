"""Record and golden frames must each describe one coherent run.

:class:`dev.docs.sequences.record_store.RecordFrame` covers stdout and stderr
independently: ``envelope`` is the verbatim document, ``envelope_source`` names
the stream that carried it, and ``text`` / ``stderr_text`` hold the normalised
content of whichever stream did NOT carry it. Three coherence rules keep those
fields from describing two different runs -- an envelope without its source, a
source without its envelope, and a stream credited with the envelope while also
storing raw content. A fourth rule keeps setup frames output-free: they are
build scaffolding the page never shows, so their record keeps only argv, exit
code and captures.

:class:`dev.docs.sequences.golden_store.GoldenFrame` is the committed
fingerprint of a record frame. A setup frame carries no output fingerprint, and
every other executed frame carries both its digest and its size, so a golden
can never silently skip comparing a reader-facing output.

Every rule is a refusal on a PERSISTED model: a record is rendered from and
diffed against, a golden is committed and compared forever, and in both the
incoherent half would simply never participate. The refusals below are asserted
through the real model validators, and the coherent shapes are asserted
alongside them so the gate cannot pass by refusing everything.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..golden_store import GoldenFrame
from ..record_store import RecordFrame
from ..runner import CapturedValue
from ..schema import FrameKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_PAIRED = "'envelope' and 'envelope_source' are set together or not at all"


def _frame(**overrides: object) -> RecordFrame:
    """Build a record frame whose only variation is the stream fields under test."""
    fields: dict[str, object] = {"kind": FrameKind.COMMAND, "argv": ("aeat", "--help"), "exit_code": 0}
    fields.update(overrides)
    return RecordFrame.model_validate(fields)


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


@pytest.mark.parametrize(
    "streams",
    [
        {"envelope": {"status": "ok"}, "envelope_source": "stdout"},
        {"envelope": {"status": "error"}, "envelope_source": "stderr"},
        {"text": "Imported 3 transactions."},
        {"stderr_text": "a warning"},
        {"text": ""},
    ],
    ids=["stdout-envelope", "stderr-envelope", "text", "stderr-text", "empty-text"],
)
def test_a_setup_frame_that_stores_output_is_refused(streams: dict[str, object]) -> None:
    """Setup output is never rendered or compared, so storing any of it is refused.

    The empty string is included on purpose: an empty stream is stored as
    ``None``, so even an empty stored value is a layout the writer never emits.
    """
    with pytest.raises(ValidationError, match="a setup frame records only its argv, exit code and captures"):
        _frame(kind=FrameKind.SETUP, **streams)


def test_a_setup_frame_with_argv_exit_code_and_captures_is_accepted() -> None:
    """Anti-vacuity: the setup rule refuses output, not the frame."""
    frame = _frame(
        kind=FrameKind.SETUP,
        exit_code=0,
        captures=(CapturedValue(name="run_status", json_path="status", value="success"),),
    )

    assert frame.kind is FrameKind.SETUP
    assert [capture.value for capture in frame.captures] == ["success"]
    assert (frame.envelope, frame.envelope_source, frame.text, frame.stderr_text) == (None, None, None, None)


_DIGEST = "0" * 64


def _golden_frame(**overrides: object) -> GoldenFrame:
    """Build a golden frame whose only variation is the fingerprint fields under test."""
    fields: dict[str, object] = {"kind": FrameKind.COMMAND, "argv": ("aeat", "--help"), "exit_code": 0}
    fields.update(overrides)
    return GoldenFrame.model_validate(fields)


@pytest.mark.parametrize(
    "fingerprint",
    [{"output_sha256": _DIGEST, "output_bytes": 4}, {"envelope_source": "stdout"}, {"output_bytes": 0}],
    ids=["digest", "envelope-source", "size"],
)
def test_a_setup_golden_frame_with_an_output_fingerprint_is_refused(fingerprint: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="a setup frame records only its argv, exit code and captures"):
        _golden_frame(kind=FrameKind.SETUP, **fingerprint)


@pytest.mark.parametrize(
    "fingerprint",
    [{}, {"output_sha256": _DIGEST}, {"output_bytes": 4}],
    ids=["neither", "digest-only", "size-only"],
)
def test_a_reader_facing_golden_frame_without_its_full_fingerprint_is_refused(fingerprint: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="records its output digest and size"):
        _golden_frame(**fingerprint)


def test_a_golden_frame_digest_must_be_lowercase_sha256_hex() -> None:
    with pytest.raises(ValidationError):
        _golden_frame(output_sha256=_DIGEST.upper().replace("0", "A"), output_bytes=4)


def test_coherent_golden_frames_are_accepted() -> None:
    """Anti-vacuity: the fingerprint rules refuse incoherent frames, not frames."""
    setup = _golden_frame(kind=FrameKind.SETUP)
    text_only = _golden_frame(output_sha256=_DIGEST, output_bytes=0)
    enveloped = _golden_frame(output_sha256=_DIGEST, output_bytes=12, envelope_source="stderr")

    assert (setup.output_sha256, setup.output_bytes) == (None, None)
    assert text_only.envelope_source is None
    assert enveloped.envelope_source == "stderr"
