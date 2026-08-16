"""The suffered-retención advisories name the payer's certificate, never a capture.

Restores the property a dropped test once pinned directly against the
free-text default (commit ``16d7fc2682`` retired it as "superseded by locale
keys" when the per-predicate-id Python default it tested,
``resolve_advisory_message_default``, was deleted) — but nothing replaced
it, so every ADVISORY predicate fell back to the same generic "a registry
advisory predicate fired for this revision" sentence, naming no remedy at
all. This module pins the property against the CURRENT mechanism instead:
``_advisory_predicate_finding`` selects a predicate-specific literal
``message_locale_key`` for the two suffered-retención families at their own
``ModeloVerificationFinding`` constructor call site — required by
``test_every_production_verification_finding_constructor_is_locale_neutral``,
which asserts every such call site's locale key is a literal, not a
returned value — rendered through the real ``tr()`` catalogue lookup rather
than a hand-written string.

The remedy must name the payer's certificate, never an instruction to pull,
capture or fetch a filing: the taxpayer never filed the Modelo that declares
the retención (Modelo 111 for trabajo, Modelo 123 for capital mobiliario
ahorro) — a third party did — so no local sweep can retrieve it on their
behalf.
"""

from __future__ import annotations

import pytest

from ....core.i18n import tr
from ....core.resources import resources
from ....domain.calculations.registry import VerificationPredicateDefinition
from .._verification_predicates import _advisory_predicate_finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REVISION_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
_FORBIDDEN_WORDS = ("pull", "capture", "fetch")
_LOCALES_NAMING_THE_SPANISH_CERTIFICATE = ("en", "es")
_ALL_LOCALES = ("en", "es", "ca", "hu")


def _trabajo_predicate_id(year: int) -> str:
    return f"modelo-100-{year}-retenciones-trabajo-declaradas-cuando-ingresos-integros-trabajo-positivos"


def _capital_mobiliario_predicate_id(year: int) -> str:
    return f"modelo-100-{year}-retenciones-capital-mobiliario-declaradas-cuando-ingresos-integros-positivos"


def _predicate(year: int, predicate_id: str) -> VerificationPredicateDefinition:
    revision = resources().modelos.authority.snapshot("100", filing_year=year, period="0A").revision
    for predicate in revision.verification_predicates or ():
        if predicate.predicate_id == predicate_id:
            return predicate
    pytest.fail(f"{predicate_id} is not declared on the M100/{year} revision")


def _assert_names_the_certificate_and_no_forbidden_word(locale_key: str) -> None:
    for locale in _LOCALES_NAMING_THE_SPANISH_CERTIFICATE:
        assert "certificado de retenciones" in tr(locale_key, locale=locale)
    for locale in _ALL_LOCALES:
        message = tr(locale_key, locale=locale)
        assert message, (locale_key, locale)
        for forbidden in _FORBIDDEN_WORDS:
            assert forbidden not in message.lower(), f"{locale}: the advisory tells the operator to {forbidden}"


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_the_trabajo_advisory_names_the_certificate_and_never_a_forbidden_word(year: int) -> None:
    finding = _advisory_predicate_finding(_predicate(year, _trabajo_predicate_id(year)))
    assert finding.message_locale_key == "application.modelo.findings.suffered_retencion_trabajo_uncredited"
    _assert_names_the_certificate_and_no_forbidden_word(finding.message_locale_key)


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_the_capital_mobiliario_advisory_names_the_certificate_and_never_a_forbidden_word(year: int) -> None:
    finding = _advisory_predicate_finding(_predicate(year, _capital_mobiliario_predicate_id(year)))
    assert finding.message_locale_key == "application.modelo.findings.suffered_retencion_capital_mobiliario_uncredited"
    _assert_names_the_certificate_and_no_forbidden_word(finding.message_locale_key)


def test_an_unrelated_advisory_predicate_falls_back_to_the_generic_message() -> None:
    """The dispatch is a narrow match, not a blanket override of every advisory."""
    finding = _advisory_predicate_finding(
        _predicate(2025, "modelo-100-2025-cuota-resultante-determinada-cuando-base-liquidable-general-positiva"),
    )
    assert finding.message_locale_key == "application.modelo.findings.registry_advisory_predicate_fired"


def test_the_two_predicate_families_resolve_to_distinct_messages() -> None:
    """The trabajo and capital-mobiliario remedies are not accidentally the same string."""
    trabajo_finding = _advisory_predicate_finding(_predicate(2025, _trabajo_predicate_id(2025)))
    capital_mobiliario_finding = _advisory_predicate_finding(_predicate(2025, _capital_mobiliario_predicate_id(2025)))
    trabajo_message = tr(trabajo_finding.message_locale_key, locale="en")
    capital_mobiliario_message = tr(capital_mobiliario_finding.message_locale_key, locale="en")
    assert trabajo_message != capital_mobiliario_message
    assert "111" in trabajo_message
    assert "123" in capital_mobiliario_message
