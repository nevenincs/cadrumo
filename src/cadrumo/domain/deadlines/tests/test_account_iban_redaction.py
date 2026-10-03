"""A rejected account IBAN never reaches a diagnostic.

The refund and charge accounts are financial identity data. When one is
refused, the error names the account and the broken rule, never the value, so
neither the rendered message, the error context, nor the registered cause
carries it -- whether the account is validated alone or inside the profile
that holds it.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from ..models import ChargeAccount, IVARegime, ModeloIVAProfile, RefundAccount, Schedule, TaxpayerProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Synthetic values: one with the ISO 13616 shape and a broken mod-97 residue,
# one that does not have the shape at all.
_BAD_CHECKSUM = "ES7620770024003102575767"
_BAD_SHAPE = "ES76-ZZ#2077"


def _texts(error: ValidationError) -> tuple[str, ...]:
    """Everything a diagnostic could render from ``error``, cause chain included."""
    texts = [str(error), repr(error)]
    for detail in error.errors(include_input=False):
        texts.append(str(detail))
        for value in (detail.get("ctx") or {}).values():
            texts.append(str(value))
            cause = getattr(value, "__cause__", None)
            while cause is not None:
                texts.extend((str(cause), repr(cause)))
                cause = cause.__cause__
    return tuple(texts)


def _profile_with(refund_iban: str) -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X1234567L",
            "iva_regime": IVARegime("GENERAL"),
            "iva": {"tax_territory": "comun", "refund_account": {"iban": refund_iban}},
        }
    )


_BUILDERS: dict[str, Callable[[str], object]] = {
    "refund account": lambda iban: RefundAccount(iban=iban),
    "charge account": lambda iban: ChargeAccount(iban=iban),
    "refund account inside the iva profile": lambda iban: ModeloIVAProfile.model_validate(
        {"tax_territory": "comun", "refund_account": {"iban": iban}}
    ),
    "refund account inside the taxpayer profile": _profile_with,
}


@pytest.mark.parametrize("iban", [_BAD_CHECKSUM, _BAD_SHAPE], ids=["mod-97", "shape"])
@pytest.mark.parametrize("holder", sorted(_BUILDERS))
def test_a_refused_iban_is_named_by_rule_never_by_value(holder: str, iban: str) -> None:
    with pytest.raises(ValidationError) as caught:
        _BUILDERS[holder](iban)

    iban_errors = [detail for detail in caught.value.errors(include_input=False) if detail["loc"][-1] == "iban"]
    assert len(iban_errors) == 1, f"{holder}: the IBAN itself must be refused"
    assert "iban" in iban_errors[0]["msg"], f"{holder}: the refusal must still name the account field"
    texts = _texts(caught.value)
    compact = iban.replace("-", "")
    for text in texts:
        assert iban not in text, f"{holder}: the raw IBAN leaked into {text!r}"
        assert compact not in text, f"{holder}: the canonical IBAN leaked into {text!r}"


def test_a_valid_iban_is_still_accepted_and_canonicalised() -> None:
    """The redaction does not loosen validation: a well-formed IBAN still passes, canonicalised."""
    valid = "ES91 2100 0418 4502 0005 1332"

    assert RefundAccount(iban=valid).iban == "ES9121000418450200051332"
    assert ChargeAccount(iban=valid).iban == "ES9121000418450200051332"


def test_a_refused_schedule_never_echoes_the_profile_account() -> None:
    """A schedule is refused with its whole input in hand; the profile's account is not echoed."""
    valid = "ES9121000418450200051332"

    with pytest.raises(ValidationError) as caught:
        Schedule.model_validate({"profile": {"iva": {"refund_account": {"iban": valid}}}})

    assert valid in str(caught.value.errors(include_input=True)), "the refusal never reaches the account"
    # Pydantic shortens a long echoed input in the middle, so the tail is what would show.
    assert valid[-12:] not in f"{caught.value} {caught.value!r}"
