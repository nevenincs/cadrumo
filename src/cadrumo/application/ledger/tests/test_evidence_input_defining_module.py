"""Ownership checks for the ``EvidenceInput`` defining module."""

from __future__ import annotations

import inspect

import pytest

from ..evidence_input import EvidenceInput
from ..evidence_textlayer import transcribe_text_layer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_evidence_input_has_one_public_defining_module() -> None:
    """The transient decrypted-byte carrier is defined at its direct import path."""
    assert EvidenceInput.__module__ == "cadrumo.application.ledger.evidence_input"


def test_text_layer_transcriber_accepts_the_defining_evidence_input_type() -> None:
    """The public reader's input type remains directly constructible by callers."""
    signature = inspect.signature(transcribe_text_layer)
    annotations = {str(parameter.annotation) for parameter in signature.parameters.values()}

    assert any("EvidenceInput" in annotation for annotation in annotations)
