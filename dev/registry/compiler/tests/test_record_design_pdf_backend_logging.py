"""The PDF text backends' own DEBUG stream is held down for the duration of a read."""

from __future__ import annotations

import logging

import pytest

from ..record_design_pdf_visual import quiet_pdf_text_backend_logging

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_debug_inherited_from_an_unconfigured_root_is_held_at_warning() -> None:
    """A process that never configured logging must not pay pdfminer's per-token records.

    The unconfigured state is STAGED here rather than observed, because this
    session is not in it: the root conftest runs ``configure_logging`` at its
    host boundary, which declares these libraries at WARNING. That is precisely
    why the cost went unreported -- it is paid by analysis scripts and bare
    compiler entries, never by the suite that would have measured it.
    """
    pdfminer = logging.getLogger("pdfminer")
    root = logging.getLogger()
    previous_backend, previous_root = pdfminer.level, root.level
    pdfminer.setLevel(logging.NOTSET)
    root.setLevel(logging.DEBUG)
    try:
        with quiet_pdf_text_backend_logging():
            assert pdfminer.getEffectiveLevel() == logging.WARNING
            assert not pdfminer.isEnabledFor(logging.DEBUG)
        assert pdfminer.getEffectiveLevel() == logging.DEBUG
    finally:
        root.setLevel(previous_root)
        pdfminer.setLevel(previous_backend)


def test_a_level_set_on_the_backend_itself_survives() -> None:
    """A developer debugging a parse still gets the stream they asked for."""
    pdfminer = logging.getLogger("pdfminer")
    previous = pdfminer.level
    pdfminer.setLevel(logging.DEBUG)
    try:
        with quiet_pdf_text_backend_logging():
            assert pdfminer.getEffectiveLevel() == logging.DEBUG
    finally:
        pdfminer.setLevel(previous)


def test_a_backend_already_quiet_is_left_alone() -> None:
    """Nothing is raised or restored when the root is already at WARNING or above."""
    pdfminer = logging.getLogger("pdfminer")
    root = logging.getLogger()
    previous_backend, previous_root = pdfminer.level, root.level
    pdfminer.setLevel(logging.NOTSET)
    root.setLevel(logging.WARNING)
    try:
        with quiet_pdf_text_backend_logging():
            assert pdfminer.level == logging.NOTSET
    finally:
        root.setLevel(previous_root)
        pdfminer.setLevel(previous_backend)
