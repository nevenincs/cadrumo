"""A text-layer document classifies on-host, with no cloud transport.

This is the gate that must be green **before** any cloud read path is
deleted. The sequencing is a constraint rather than a preference: delete the
cloud path first and there is a window in which text-layer PDFs cannot be
classified at all, which is a capability regression shipped to operators for
however long the window lasts.

The proof is deliberately run against the real wiring rather than against a
hand-built classifier. A test that constructed ``LocalTextLLMClassifier``
itself would prove the class works and say nothing about whether the classify
path reaches it -- three deliverables once shipped correct, tested, and
unreferenced, because a unit test passes whether or not anything calls the
code.
"""

from __future__ import annotations

import inspect

import pytest

from ....application.ledger.llm_classification import classify_with_evidence
from .. import ledger_llm_composition

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_classify_path_reaches_the_local_text_reader() -> None:
    """The classify path is composed with the local reader when no cloud provider is given.

    Enrolment gate, not a unit test. Reads the classify seam's own source, so
    it fails if the wiring is removed even while ``LocalTextLLMClassifier``
    itself stays perfectly functional.

    Before this wiring the same branch raised ``_TEXT_PATH_NEEDS_PROVIDER``,
    making a cloud provider mandatory for any text-layer document. The
    application seam receives its text reader as a port, so the local reader is
    wired where the CLI composes that port.
    """
    assert "LocalTextLLMClassifier(" in inspect.getsource(ledger_llm_composition), (
        "the classify path must reach the local text reader; without it a text-layer "
        "document has no on-host route and requires a cloud transport"
    )
    assert "_TEXT_PATH_NEEDS_PROVIDER" not in inspect.getsource(classify_with_evidence), (
        "the text path must no longer refuse for want of a cloud provider"
    )
