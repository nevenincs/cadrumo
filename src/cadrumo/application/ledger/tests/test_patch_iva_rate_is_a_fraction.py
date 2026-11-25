"""A ledger patch refuses an IVA rate written as a percentage, with the words the backend serves."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ....core.external_constants import OutputLanguage
from ....domain.transactions.errors import TransactionIvaRateNotFractionError
from ..models import ManualLedgerTransactionPatch

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _registered_cause(error: ValidationError) -> BaseException | None:
    raised = error.errors()[0].get("ctx", {}).get("error")
    cause = getattr(raised, "__cause__", None)
    return cause if isinstance(cause, BaseException) else None


@pytest.mark.parametrize("rate", ["21", "1.01", "100", "2"])
def test_a_percentage_like_rate_is_refused_with_the_served_words(rate: str) -> None:
    with pytest.raises(ValidationError) as caught:
        ManualLedgerTransactionPatch.model_validate({"iva_rate": Decimal(rate)})

    cause = _registered_cause(caught.value)
    assert isinstance(cause, TransactionIvaRateNotFractionError)
    assert get_registered_error_code(cause).code == "REFUSED_TRANSACTION_IVA_RATE_NOT_FRACTION"
    sentences = {language: resolve_error_message(cause, locale=language.value) for language in OutputLanguage}
    assert all(rate in sentence for sentence in sentences.values())
    assert len(set(sentences.values())) == len(sentences)
    assert "0.21" in sentences[OutputLanguage.EN]


@pytest.mark.parametrize("rate", ["0", "0.21", "0.052", "1", "1.00"])
def test_a_fraction_up_to_one_is_accepted(rate: str) -> None:
    patch = ManualLedgerTransactionPatch.model_validate({"iva_rate": Decimal(rate)})

    assert patch.iva_rate == Decimal(rate)


def test_an_unset_rate_stays_unset() -> None:
    patch = ManualLedgerTransactionPatch.model_validate({"iva_rate": None, "notes": "kept"})

    assert patch.iva_rate is None
    assert patch.model_fields_set == {"iva_rate", "notes"}
