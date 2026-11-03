"""Every reason a read draft cannot be confirmed serves a sentence a frontend can show verbatim."""

from __future__ import annotations

import re

import pytest

from ....core.config import override_settings
from ....core.confirmation_gate import ConfirmationBlockReason
from ....core.external_constants import OutputLanguage
from ..confirmation_block_words import served_block_reason_words
from ..confirmation_gate import ConfirmationBlocker
from ..invoice_evidence_operation_dtos import ConfirmationBlockerProjectionV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_each_reason_serves_its_own_finished_sentence_in_the_workers_language(language: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=language.value):
        served = {reason: served_block_reason_words(reason) for reason in ConfirmationBlockReason}

    assert len({words for words, _language in served.values()}) == len(ConfirmationBlockReason)
    for words, served_language in served.values():
        assert served_language is language
        assert len(words) > 10
        assert not re.search(r"\bapplication\.|\{|\}|%\(", words)


def test_the_blocker_projection_carries_the_sentence_served_for_its_reason() -> None:
    blocker = ConfirmationBlocker(
        blocker_id="0123456789abcdef", reason=ConfirmationBlockReason.CLOSURE_DISCREPANCY, field="grand_total"
    )
    with override_settings(cadrumo_output_language="ca"):
        projection = ConfirmationBlockerProjectionV1.from_blocker(blocker)
        expected = served_block_reason_words(ConfirmationBlockReason.CLOSURE_DISCREPANCY)

    assert (projection.reason_words, projection.reason_words_language) == expected
    assert projection.reason_words_language is OutputLanguage.CA
