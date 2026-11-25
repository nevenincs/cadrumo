"""One verdict is recovered from a causal chain only when the chain states one verdict.

Driven through real registered errors, raised and chained as callers raise
them, so the traversal sees the causal links it walks in production.
"""

from __future__ import annotations

import pytest

from ...core.model_roles import ModelRole
from ..cli_exception_preconditions import nested_terminal_precondition_verdict
from ..ledger.import_ports import LedgerImportReaderUnavailableError
from ..operator_actions.models import PreconditionVerdict
from .agent_refusal_support import model_not_installed_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INSTALLED = model_not_installed_verdict(ModelRole.TEXT_EXTRACTION)
_OTHER = model_not_installed_verdict(ModelRole.VISION_TRANSCRIPTION)


def _chained(outer: PreconditionVerdict, inner: PreconditionVerdict) -> LedgerImportReaderUnavailableError:
    try:
        try:
            raise LedgerImportReaderUnavailableError(precondition_verdict=inner)
        except LedgerImportReaderUnavailableError as cause:
            raise LedgerImportReaderUnavailableError(precondition_verdict=outer) from cause
    except LedgerImportReaderUnavailableError as error:
        return error


def test_a_wrapper_carrying_its_causes_verdict_states_that_one_verdict() -> None:
    assert nested_terminal_precondition_verdict(_chained(_INSTALLED, _INSTALLED)) == _INSTALLED


def test_two_different_verdicts_in_one_chain_are_ambiguous() -> None:
    assert nested_terminal_precondition_verdict(_chained(_INSTALLED, _OTHER)) is None
