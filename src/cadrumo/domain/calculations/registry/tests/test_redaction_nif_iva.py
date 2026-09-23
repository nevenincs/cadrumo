"""The domain NIF-IVA authority drives redaction of prefixed identities.

This contract belongs beside the dated country-format registry: core owns only
the structural token and normalisation mechanics, while the domain owns the
per-country admission policy.
"""

from __future__ import annotations

import pytest

from .....core.identity.documents import IdentityError, validate_identity
from .....core.redaction.rules import redact_for_cli_output, redact_for_log
from .....core.redaction.tax_identity_admission import bind_tax_identity_admission
from ..nif_iva_catalogue import nif_iva_format_for_country
from ..tax_id_format import runtime_tax_id_format

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

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


@pytest.mark.parametrize(
    "document_reference",
    [
        "FAC-2024-0007",
        "INV-2024-0007",
        "EXP-2024-000123",
        "F-2026/0142",
        "FA-24-0007",
        # A real Member State prefix whose digits do not follow Sweden's format.
        "SE-2026-000412",
    ],
)
def test_a_separator_bearing_document_reference_survives_the_prefixed_arm(document_reference: str) -> None:
    """Invoice, expediente and batch numbers are document references, not identities.

    The scan joins letters and digits across separators, so each of these reaches
    the prefixed arm; only the per-State format may admit it, and none matches.
    """
    assert not _redacts(document_reference), f"{document_reference!r} is a document reference"


@pytest.mark.parametrize(
    "printed_identity",
    ["SE 556677889901", "SE556677889901", "FR12345678901", "DE123456789", "ESB12345674"],
)
def test_a_member_state_number_is_still_redacted_beside_those_references(printed_identity: str) -> None:
    assert _redacts(printed_identity), f"{printed_identity!r} is a tax identity and must not reach the operator"


@pytest.mark.parametrize("printed_identity", ["SE556677889901", "SE 556677889901", "ESB12345674"])
def test_without_an_answering_authority_a_member_state_number_is_still_redacted(printed_identity: str) -> None:
    """The fail-safe half of the contract: an unanswered gate hashes rather than leaks.

    With no admission bound the prefixed arm falls back to lexical shape, which
    over-redacts document references by design. That fallback must never be
    narrowed to fix over-redaction, because a real number would then leak
    wherever the authority is unavailable.
    """
    with bind_tax_identity_admission(None):
        assert _redacts(printed_identity), f"{printed_identity!r} leaked with the admission gate suspended"
