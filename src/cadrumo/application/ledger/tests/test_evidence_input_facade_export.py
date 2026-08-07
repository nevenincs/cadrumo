"""``EvidenceInput`` is reachable through the package's public facade.

``transcribe_text_layer`` is exported from :mod:`application.ledger`, and its
argument type is ``EvidenceInput``. While that type was private, no
out-of-package consumer could construct a call to the exported function without
reaching into ``._evidence_input`` -- which ``aeat-architecture-boundaries``
forbids, so the exported function was effectively uncallable from outside.

This gate reddens if the promotion is ever reverted, and identity-checks the
resolved object so a second definition shadowing the canonical one (rather than
a re-export of it) also fails.
"""

from __future__ import annotations

import inspect

import pytest

from ... import ledger
from .._evidence_input import EvidenceInput as _canonical_evidence_input

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_evidence_input_resolves_from_the_public_facade() -> None:
    """The lazy ``__getattr__`` hands back the canonical class, not a copy."""
    from ...ledger import EvidenceInput

    assert EvidenceInput is _canonical_evidence_input


def test_evidence_input_is_declared_in_the_facade_all() -> None:
    """Attribute resolution alone would pass on an undeclared accident."""
    assert "EvidenceInput" in ledger.__all__


def test_the_exported_reading_entry_point_annotates_the_exported_type() -> None:
    """The reason for the export, stated as a check rather than a comment.

    If ``transcribe_text_layer`` stopped taking an ``EvidenceInput``, the
    export would be justified by nothing and this reddens instead of quietly
    leaving a stale public name behind.
    """
    signature = inspect.signature(ledger.transcribe_text_layer)
    annotations = {str(parameter.annotation) for parameter in signature.parameters.values()}

    assert any("EvidenceInput" in annotation for annotation in annotations)
