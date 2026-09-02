"""Encoded document payloads must never reach the plaintext diagnostic log.

Sensitive financial documents live only in encrypted secure storage, and their
decrypted bytes may exist only transiently in process memory. The diagnostic
log is an unencrypted file on the operator's disk, so an invoice or bank
statement written into it has left its only sanctioned home -- and stays there
after the process that read it exits.

The route is not hypothetical. The root logger runs at DEBUG so Cadrumo's own
diagnostics are complete, every third-party library in the process inherits
that level, and a model client at DEBUG logs its entire request object. For a
vision request that object carries the base64 document. Crucially the payload
is never a ``str`` argument the record scrubber walks into: it is a field of an
opaque object that becomes text only when the handler formats the record,
downstream of every filter.

These tests drive the real configured logging stack against a temp log
directory and read the bytes back off disk, then restore the healthy default
configuration so sibling tests see an intact logger. Each containment
assertion is paired with a positive control proving the record was emitted and
that first-party diagnostics still land -- a fix that blinded our own logging
would satisfy the containment half alone.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import TYPE_CHECKING, override

import pytest

from .. import logging as _logging_mod
from ..config import override_settings
from ..logging import configure_logging

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

if TYPE_CHECKING:
    from collections.abc import Iterator

_PNG_PAYLOAD = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"CONFIDENTIAL-INVOICE-PIXELS" * 40).decode()
_JPEG_PAYLOAD = base64.b64encode(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"CONFIDENTIAL-STATEMENT" * 40).decode()


class _RequestOptions:
    """Stand-in for a model client's request-options object.

    Mirrors the shape that leaks: the payload is reachable only through the
    object's ``__str__``, so a scrubber that walks strings, mappings and
    sequences of the record's arguments never sees it.
    """

    def __init__(self, payload: str) -> None:
        self.json_data = {"messages": [{"content": [{"type": "image", "source": {"data": payload}}]}]}

    @override
    def __str__(self) -> str:
        return f"RequestOptions(json_data={self.json_data!r})"


@pytest.fixture
def log_file(tmp_path: Path) -> Iterator[Path]:
    """Configure the real logging stack against a temp log directory."""
    log_dir = tmp_path / "containment-logs"
    original_configured = _logging_mod._configured
    try:
        _logging_mod._configured = False
        with override_settings(
            cadrumo_log_dir=log_dir,
            cadrumo_log_root_level="DEBUG",
            cadrumo_log_file_level="DEBUG",
        ):
            configure_logging()
            yield log_dir / "cadrumo.log"
    finally:
        _logging_mod._configured = False
        configure_logging()
        _logging_mod._configured = original_configured or True


def _written_log_text(log_file: Path) -> str:
    """Flush every handler and return what actually reached the disk."""
    for handler in logging.getLogger().handlers:
        handler.flush()
    if not log_file.exists():
        return ""
    return log_file.read_text(encoding="utf-8", errors="replace")


def test_third_party_request_object_payload_never_reaches_the_log_file(log_file: Path) -> None:
    """The measured defect: an SDK request object dumped at DEBUG."""
    logging.getLogger("anthropic._base_client").debug("Request options: %s", _RequestOptions(_PNG_PAYLOAD))

    written = _written_log_text(log_file)
    assert _PNG_PAYLOAD not in written, "the document payload reached the plaintext diagnostic log"
    assert "iVBORw0KGg" not in written, "a PNG magic reached the plaintext diagnostic log"


def test_third_party_debug_records_do_not_reach_the_log_file(log_file: Path) -> None:
    """The ceiling seam, gated on its own behaviour rather than on a payload.

    Redaction can only remove what it recognises. Holding third-party loggers
    below DEBUG at the sink is the half that needs no such recognition, so it
    is asserted directly: the record never arrives, whatever it contained.
    """
    logging.getLogger("anthropic._base_client").debug("sending request to the messages endpoint")

    assert "sending request to the messages endpoint" not in _written_log_text(log_file)


def test_third_party_warnings_still_reach_the_log_file(log_file: Path) -> None:
    """Positive control: third-party logging is held below DEBUG, not silenced."""
    logging.getLogger("anthropic._base_client").warning("retrying after connection reset")

    assert "retrying after connection reset" in _written_log_text(log_file)


def test_first_party_image_payload_is_redacted_but_the_record_survives(log_file: Path) -> None:
    """The local on-host route: our own module logs a request carrying images."""
    logging.getLogger("cadrumo.llm.local").debug(
        "ollama vision request %s",
        {"model": "probe-vision", "images": [_JPEG_PAYLOAD]},
    )

    written = _written_log_text(log_file)
    assert _JPEG_PAYLOAD not in written, "the document payload reached the plaintext diagnostic log"
    assert "ollama vision request" in written, "the first-party diagnostic record must survive redaction"
    assert "probe-vision" in written, "non-payload diagnostic context must survive redaction"
    assert "<redacted:payload>" in written, "the payload's removal must be visible, not silent"


def test_first_party_data_uri_and_raw_bytes_payloads_are_contained(log_file: Path) -> None:
    """A ``data:`` URI and a raw ``bytes`` argument are payloads too."""
    logger = logging.getLogger("cadrumo.adapters.probe")
    logger.debug("inline attachment %s", f"data:image/png;base64,{_PNG_PAYLOAD}")
    logger.debug("decrypted evidence %s", b"\x89PNG\r\n\x1a\n" + b"RAW-DOCUMENT-BYTES" * 40)

    written = _written_log_text(log_file)
    assert _PNG_PAYLOAD not in written, "a data-URI payload reached the plaintext diagnostic log"
    assert "RAW-DOCUMENT-BYTES" not in written, "raw decrypted bytes reached the plaintext diagnostic log"


def test_ordinary_first_party_debug_diagnostics_are_untouched(log_file: Path) -> None:
    """Positive control: containment must not cost us our own DEBUG channel."""
    logging.getLogger("cadrumo.application.probe").debug(
        "resolved revision %s for period %s across %d casillas",
        "2026-303-v2",
        "1T",
        47,
    )

    written = _written_log_text(log_file)
    assert "resolved revision 2026-303-v2 for period 1T across 47 casillas" in written
    assert "<redacted:payload>" not in written, "ordinary diagnostics must not be redacted"
