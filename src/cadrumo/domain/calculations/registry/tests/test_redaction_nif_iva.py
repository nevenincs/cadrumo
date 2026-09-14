"""The domain NIF-IVA authority drives redaction of prefixed identities.

This contract belongs beside the dated country-format registry: core owns only
the structural token and normalisation mechanics, while the domain owns the
per-country admission policy.
"""

from __future__ import annotations

import pytest

from .....core.identity.documents import IdentityError, validate_identity
from .....core.redaction.rules import redact_for_cli_output, redact_for_log
from ..nif_iva_catalogue import nif_iva_format_for_country
from ..tax_id_format import runtime_tax_id_format

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REDACTED_MARKER = "sha256:"

_SHIPPED_COUNTRIES = (
    "AT",
    "BE",
    "BG",
    "CY",
    "CZ",
    "DE",
    "DK",
    "EE",
    "FI",
    "FR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SE",
    "SI",
    "SK",
    "XI",
    "GR",
)

_ES_PREFIXED = "ESB12345674"
_ES_BARE = "B12345674"


def _redacts(value: str) -> bool:
    """Return whether both operator-facing funnels remove *value*."""
    line = f"counterparty {value} declared"
    cli = redact_for_cli_output(line)
    log = redact_for_log(line)
    assert (value in cli) == (value in log), f"the two funnels disagree about {value!r}"
    return _REDACTED_MARKER in cli and value not in cli


def test_the_shipped_example_corpus_is_populated() -> None:
    assert len(_SHIPPED_COUNTRIES) >= 20, _SHIPPED_COUNTRIES


@pytest.mark.parametrize("country", _SHIPPED_COUNTRIES)
def test_every_shipped_member_state_number_is_redacted(country: str) -> None:
    spec = nif_iva_format_for_country(country)
    assert spec is not None, f"no NIF-IVA format resolved for {country}"
    assert _redacts(spec.example), f"{country} example {spec.example!r} survived the funnel"


def test_the_spanish_prefixed_spelling_is_redacted_like_its_bare_form() -> None:
    assert _redacts(_ES_BARE)
    assert _redacts(_ES_PREFIXED)


def test_a_prefixed_spanish_identifier_failing_its_check_character_is_not_an_identity() -> None:
    with pytest.raises(IdentityError):
        validate_identity("B99999999", runtime_tax_id_format())

    assert not _redacts("ESB99999999")


@pytest.mark.parametrize(
    "ordinary",
    [
        "INVOICE2026",
        "XX12345678",
        "Factura",
        "DE00",
        "REF20260311",
        "ES",
        "SHA256ABCDEF12",
    ],
)
def test_ordinary_output_survives_the_wide_scan(ordinary: str) -> None:
    assert not _redacts(ordinary), f"{ordinary!r} is not a tax identity and must reach the operator"


def test_a_prefix_naming_no_member_state_admits_nothing() -> None:
    assert nif_iva_format_for_country("XX") is None
    assert not _redacts("XX123456789")
