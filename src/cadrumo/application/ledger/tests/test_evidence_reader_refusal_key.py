"""A reader refusal says to set the local AI up only when the reader probe names that setup.

The verdicts come from the real reader probe asking a closed runtime port, and
from the probe's own refusal for a role this computer cannot run.
"""

from __future__ import annotations

import pytest

from ....core.config import Settings
from ....core.errors.error_codes import resolve_error_message
from ....core.model_roles import ModelRole
from ...local_reader import probe_local_ai_program
from ...operator_actions.models import PreconditionVerdict
from ...provisioning_contracts import ProvisioningPreconditionCondition, provisioning_no_recovery_verdict
from ..evidence_errors import (
    EVIDENCE_LOCAL_AI_NOT_READY_LOCALE_KEY,
    EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY,
    PurchaseInvoiceEvidenceReaderError,
    evidence_reader_refusal_key,
)
from ..preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"


def test_an_unanswering_local_ai_is_named_with_its_setup() -> None:
    status = probe_local_ai_program(Settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT))
    assert status.available is False

    key = evidence_reader_refusal_key(status.precondition_verdict)

    assert key == EVIDENCE_LOCAL_AI_NOT_READY_LOCALE_KEY
    error = PurchaseInvoiceEvidenceReaderError(translated_message=key, precondition_verdict=status.precondition_verdict)
    assert (
        resolve_error_message(error, locale="en")
        == "Local AI is not ready, so nothing was read. Set it up in the Cadrumo desktop app, then try again."
    )


@pytest.mark.parametrize(
    "verdict",
    [
        None,
        provisioning_no_recovery_verdict(
            ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE,
            facts={"role": ModelRole.TEXT_EXTRACTION.value, "runtime_reachable": True, "role_model_selected": False},
        ),
        ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE,
            facts={"semantic_reader_available": False, "reader_error_type": "ConnectionError"},
        ),
    ],
    ids=["no-verdict", "role-this-computer-cannot-run", "reader-failure"],
)
def test_a_refusal_setup_cannot_repair_offers_no_setup(verdict: PreconditionVerdict | None) -> None:
    key = evidence_reader_refusal_key(verdict)

    assert key == EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY
    sentence = resolve_error_message(PurchaseInvoiceEvidenceReaderError(translated_message=key), locale="en")
    assert "set it up" not in sentence.lower()
    assert "ConnectionError" not in sentence
