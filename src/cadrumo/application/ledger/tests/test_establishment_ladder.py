"""The establishment ladder answers in order, and the order is the safety property.

Every rung of this ladder is honest on its own. What this module gates is the
COMPOSITION, because the damage available here is not a rung answering wrongly
but the right rungs consulted in the wrong sequence.

**The load-bearing case is a French party.** Spain, France, Germany and Italy all
print five-digit postal codes, so ``75001`` handed to the Spanish province lookup
returns the peninsula and ``51001`` returns Ceuta y Melilla -- placing a French
party inside a Spanish territory, or outside LIVA entirely. Neither is caught
downstream: both are well-formed answers to a question nobody should have asked.
Ordering prevents it, so the ordering tests below assert not only what the ladder
returned but that the SKIPPED rung would have returned something different --
without that second half, "first decisive wins" is asserted against cases where
every rung agrees, which proves nothing about the order.

**Exhaustion never becomes a territory.** The peninsula is the majority
population, so a default there would pass every fixture written by an author with
mainland examples while silently placing Canarian and Ceutan parties inside a
territory their operations are not subject to. The sweep ranges over the whole
scope enum rather than spot-checking the mainland.

**A corrupt registry and an unestablished party stay different outcomes.** The
bundled vocabulary refuses a fold-colliding table rather than degrading, and the
ladder must not convert that refusal into a quiet "not established": an operator
sent to confirm a counterparty's territory in answer to a broken data file has
been given a question that is not theirs and a remedy that cannot work.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import ClassifierInputSource
from ....domain.iva import (
    IvaCatalogueError,
    IvaTerritorialScope,
    country_code_for_printed_tax_identifier,
    territorial_scope_for_country,
    territorial_scope_for_printed_tax_identifier,
    territorial_scope_for_spanish_postal_code,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import _establishment_ladder as ladder_module
from .._counterparty_establishment import (
    CounterpartyEstablishmentRepository,
    record_counterparty_establishment,
)
from .._establishment_ladder import (
    CounterpartyEstablishment,
    EstablishmentRung,
    resolve_counterparty_establishment_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "37373737-3737-4737-8737-373737373737"
_SPANISH_CIF = "B12345674"
_GERMAN_VAT = "DE811234567"
_GREEK_VAT = "EL123456789"
_ASSERTED_AT = datetime(2026, 5, 12, 9, 30, tzinfo=UTC)

_LAS_PALMAS = "35001"
_MADRID = "28013"
_PARIS = "75001"
_BERLIN = "10115"
_CEUTA = "51001"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def repository(runtime_profile: TestRuntimeProfile) -> CounterpartyEstablishmentRepository:
    return CounterpartyEstablishmentRepository(objects=runtime_profile.repository)


def _resolve(
    repository: CounterpartyEstablishmentRepository,
    *,
    tax_identifier: str | None = None,
    country_name: str | None = None,
    country_code: str | None = None,
    postal_code: str | None = None,
) -> CounterpartyEstablishment:
    return resolve_counterparty_establishment_scope(
        bucket_id=_BUCKET_ID,
        tax_identifier=tax_identifier,
        printed_country_name=country_name,
        printed_country_code=country_code,
        postal_code=postal_code,
        repository=repository,
    )


# The composition measured against the landed rungs, in the form the ladder is
# actually reached in: a printed country name and a printed postal code, which is
# what an address block carries. The last two rows are the ones a default would
# quietly fill in.
_MEASURED_CASES: tuple[tuple[str | None, str | None, EstablishmentRung | None, IvaTerritorialScope | None], ...] = (
    ("España", _LAS_PALMAS, EstablishmentRung.SPANISH_POSTAL_CODE, IvaTerritorialScope.ES_CANARIAS),
    ("España", _MADRID, EstablishmentRung.SPANISH_POSTAL_CODE, IvaTerritorialScope.ES_MAINLAND),
    ("España", None, None, None),
    ("France", _PARIS, EstablishmentRung.PRINTED_COUNTRY, IvaTerritorialScope.EU_MEMBER),
    ("Alemania", _BERLIN, EstablishmentRung.PRINTED_COUNTRY, IvaTerritorialScope.EU_MEMBER),
    (None, _MADRID, None, None),
)


@pytest.mark.parametrize(("country_name", "postal_code", "expected_rung", "expected_scope"), _MEASURED_CASES)
def test_ladder_composes_the_measured_cases(
    repository: CounterpartyEstablishmentRepository,
    country_name: str | None,
    postal_code: str | None,
    expected_rung: EstablishmentRung | None,
    expected_scope: IvaTerritorialScope | None,
) -> None:
    """Each measured case resolves through the rung that owns it, or through none."""
    resolved = _resolve(repository, country_name=country_name, postal_code=postal_code)

    assert resolved.scope is expected_scope
    assert resolved.rung is expected_rung
    assert resolved.established is (expected_scope is not None)


def test_spain_named_is_the_postal_trigger_not_an_exhausted_rung(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """A positively named Spain opens the postal rung rather than ending the ladder.

    The country rung returns no SCOPE for Spain by design, and reading that
    ``None`` as "no evidence" would skip the one rung that can answer -- for the
    majority population, and invisibly, since the skipped result is a plausible
    unknown rather than a wrong value. Asserted against the rung's own refusal so
    the trigger is proven to survive it.
    """
    assert territorial_scope_for_country("ES") is None

    resolved = _resolve(repository, country_name="España", postal_code=_MADRID)

    assert resolved.rung is EstablishmentRung.SPANISH_POSTAL_CODE
    assert resolved.scope is IvaTerritorialScope.ES_MAINLAND


def test_the_country_rung_stops_the_ladder_before_a_foreign_postal_code(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """A French party is not read as Spanish, and the skipped rung would have said so.

    ``75001`` is a real Paris code and a real Madrid-shaped one. The second
    assertion is what makes this a test of ORDER: it establishes that the postal
    rung, had it been consulted, would have returned a different territory.
    """
    resolved = _resolve(repository, country_name="France", postal_code=_PARIS)

    assert resolved.scope is IvaTerritorialScope.EU_MEMBER
    assert resolved.rung is EstablishmentRung.PRINTED_COUNTRY

    skipped_rung_answer = territorial_scope_for_spanish_postal_code(_PARIS)
    assert skipped_rung_answer is IvaTerritorialScope.ES_MAINLAND
    assert skipped_rung_answer is not resolved.scope


def test_the_country_rung_stops_the_ladder_before_a_territory_outside_liva(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """The sharper form: an ungated postal rung would put a French party outside LIVA.

    ``51001`` is a Ceuta prefix, and Ceuta is outside the territorio de aplicación
    del impuesto entirely. A French party landing there is not merely the wrong
    Spanish province, it is a party the classifier would treat as not subject to
    the tax at all.
    """
    resolved = _resolve(repository, country_name="France", postal_code=_CEUTA)

    assert resolved.scope is IvaTerritorialScope.EU_MEMBER
    assert territorial_scope_for_spanish_postal_code(_CEUTA) is IvaTerritorialScope.ES_CEUTA_MELILLA


def test_the_identifier_rung_outranks_the_country_and_postal_rungs(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """A printed German VAT number wins over an address block naming Las Palmas.

    Discriminating rather than agreeing: the lower rungs would resolve this page
    to Canarias, so the assertion cannot pass by accident of every rung agreeing.
    """
    resolved = _resolve(
        repository,
        tax_identifier=_GERMAN_VAT,
        country_name="España",
        postal_code=_LAS_PALMAS,
    )

    assert resolved.rung is EstablishmentRung.TAX_IDENTIFIER_PREFIX
    assert resolved.scope is IvaTerritorialScope.EU_MEMBER

    lower_rung_answer = territorial_scope_for_spanish_postal_code(_LAS_PALMAS)
    assert lower_rung_answer is IvaTerritorialScope.ES_CANARIAS
    assert lower_rung_answer is not resolved.scope


def test_a_greek_vat_prefix_resolves_through_its_iso_code(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """``EL`` is Greece's VAT prefix while ``GR`` is its ISO code, and the catalogues are ISO-keyed.

    Left untranslated, a Greek party matches no Member State and is placed in a
    third country -- an intra-community acquisition reclassified as an import.
    """
    assert country_code_for_printed_tax_identifier(_GREEK_VAT) == "GR"

    resolved = _resolve(repository, tax_identifier=_GREEK_VAT)

    assert resolved.scope is IvaTerritorialScope.EU_MEMBER
    assert resolved.rung is EstablishmentRung.TAX_IDENTIFIER_PREFIX


def test_a_spanish_identifier_contributes_nothing_to_the_identifier_rung(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """Registration is not establishment, so neither Spanish spelling opens a rung.

    The bare CIF and the ``ES``-prefixed form are both checksum-valid Spanish
    identifiers and both establish where the party is REGISTERED. Establishment
    for IVA is the sede de actividad económica, and the validator's own
    non-resident leaders are the counter-population.
    """
    assert territorial_scope_for_printed_tax_identifier(_SPANISH_CIF) is None
    assert territorial_scope_for_printed_tax_identifier(f"ES{_SPANISH_CIF}") is None

    resolved = _resolve(repository, tax_identifier=_SPANISH_CIF)

    assert resolved.scope is None
    assert resolved.rung is None


def test_a_prefix_on_arbitrary_text_is_not_a_country(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """Two leading letters are not a VAT number, so the body must match its own State's shape."""
    resolved = _resolve(repository, tax_identifier="FRANCISCO")

    assert resolved.scope is None
    assert resolved.rung is None


def test_the_bare_domestic_invoice_exhausts_to_nothing(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """The ruling's own fixture: a bare CIF, no country, no gated postal evidence.

    This is the commonest ingested document there is, and the mainland is its
    commonest true answer -- which is exactly why a default here would be
    invisible.
    """
    resolved = _resolve(repository, tax_identifier=_SPANISH_CIF, postal_code=_MADRID)

    assert resolved.scope is None
    assert resolved.rung is None
    assert resolved.source is None
    assert resolved.declared_fact is None


@pytest.mark.parametrize("scope", list(IvaTerritorialScope))
def test_no_scope_is_reachable_from_absent_evidence(
    repository: CounterpartyEstablishmentRepository,
    scope: IvaTerritorialScope,
) -> None:
    """Sweep the whole closed set: absence produces no member of it, not merely not the mainland."""
    resolved = _resolve(repository)

    assert resolved.scope is not scope
    assert resolved.scope is None


def test_an_unrecognised_country_name_never_degrades_to_a_country(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """A name outside the vocabulary establishes nothing, and does not fall through to the postal rung."""
    resolved = _resolve(repository, country_name="Wakanda", postal_code=_MADRID)

    assert resolved.scope is None
    assert resolved.rung is None


def test_the_printed_evidence_rungs_are_backed_by_the_document(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """An evidence rung records a page as its backing, so an auditor is sent to one."""
    resolved = _resolve(repository, country_name="España", postal_code=_LAS_PALMAS)

    assert resolved.source is ClassifierInputSource.DOCUMENT_EVIDENCE
    declared = resolved.declared_fact
    assert declared is not None
    assert declared.value is IvaTerritorialScope.ES_CANARIAS
    assert declared.source is ClassifierInputSource.DOCUMENT_EVIDENCE


def test_a_confirmed_fact_answers_only_once_the_paper_has_settled_nothing(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """The last rung carries an operator's backing, not a document's.

    The same page that exhausted the evidence rungs above now resolves, which is
    the whole ergonomic argument: one question per counterparty rather than one
    per invoice.
    """
    record_counterparty_establishment(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SPANISH_CIF,
        territorial_scope=IvaTerritorialScope.ES_CANARIAS,
        asserted_by="operator",
        asserted_at=_ASSERTED_AT,
        repository=repository,
    )

    resolved = _resolve(repository, tax_identifier=_SPANISH_CIF)

    assert resolved.scope is IvaTerritorialScope.ES_CANARIAS
    assert resolved.rung is EstablishmentRung.CONFIRMED_COUNTERPARTY_FACT
    assert resolved.source is ClassifierInputSource.OPERATOR_ASSERTION


def test_decisive_paper_disagreeing_with_a_confirmed_fact_settles_nothing(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """Disagreement is carried with NO scope, so neither side is preferred by accident.

    Consulting the store even on a decisive page is what keeps this channel
    alive: a first-decisive-rung walk that stopped at the paper would never
    notice, for exactly the population the contradiction protects.
    """
    record_counterparty_establishment(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SPANISH_CIF,
        territorial_scope=IvaTerritorialScope.ES_CANARIAS,
        asserted_by="operator",
        asserted_at=_ASSERTED_AT,
        repository=repository,
    )

    resolved = _resolve(repository, tax_identifier=_SPANISH_CIF, country_name="España", postal_code=_MADRID)

    assert resolved.contradicted
    assert resolved.scope is None
    assert resolved.rung is None
    assert resolved.declared_fact is None
    contradiction = resolved.contradiction
    assert contradiction is not None
    assert contradiction.confirmed_scope is IvaTerritorialScope.ES_CANARIAS
    assert contradiction.evidenced_scope is IvaTerritorialScope.ES_MAINLAND


def test_agreeing_paper_leaves_the_evidence_rung_as_the_answer(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """A stored fact that agrees does not demote the page that proved it."""
    record_counterparty_establishment(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SPANISH_CIF,
        territorial_scope=IvaTerritorialScope.ES_CANARIAS,
        asserted_by="operator",
        asserted_at=_ASSERTED_AT,
        repository=repository,
    )

    resolved = _resolve(repository, tax_identifier=_SPANISH_CIF, country_name="España", postal_code=_LAS_PALMAS)

    assert resolved.scope is IvaTerritorialScope.ES_CANARIAS
    assert resolved.rung is EstablishmentRung.SPANISH_POSTAL_CODE
    assert not resolved.contradicted


def _refusing_rung(*_args: object, **_kwargs: object) -> str | None:
    """Stand in for a rung whose bundled table is corrupt.

    Fault injection, not a stand-in for behaviour under test. What the bundled
    vocabulary DOES on a fold-colliding or malformed table is gated for real in
    the domain lane, against real files; the untestable-by-data half is what the
    LADDER does with that refusal, and no legitimate input reaches it, because a
    correct registry never raises. Raising the real error type through the real
    call path is the only way to ask the question, and the property it asks about
    -- that no rung is wrapped in a bare ``except`` -- is exactly the one a bare
    ``except`` would silently take away.
    """
    raise IvaCatalogueError("the bundled country-name vocabulary is unusable")


def test_a_corrupt_vocabulary_refuses_rather_than_reporting_an_unestablished_party(
    repository: CounterpartyEstablishmentRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken data file raises out of the ladder, and is not a counterparty question.

    The distinguishability is the point. An operator told "this counterparty's
    territory is unestablished" is handed a question they can answer; an operator
    told nothing while the registry is broken is handed a wrong answer with no
    remedy, since confirming the counterparty would paper over a defect.
    """
    monkeypatch.setattr(ladder_module, "country_code_for_printed_country_name", _refusing_rung)

    with pytest.raises(IvaCatalogueError):
        _resolve(repository, country_name="España", postal_code=_MADRID)


def test_a_corrupt_territory_registry_refuses_from_inside_the_rung_walk(
    repository: CounterpartyEstablishmentRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The postal rung's refusal survives the walk too, not only the lookup before it.

    Asked separately because the two rungs raise at different depths: the country
    vocabulary is consulted before the ordered walk begins, while the territory
    registry is read from inside it. A single ``except`` placed around the walk
    would leave the first test green and swallow this one, which is precisely the
    shape that turns a broken data file into a counterparty question.
    """
    monkeypatch.setattr(ladder_module, "territorial_scope_for_spanish_postal_code", _refusing_rung)

    with pytest.raises(IvaCatalogueError):
        _resolve(repository, country_name="España", postal_code=_MADRID)


def test_a_corrupt_identifier_rung_refuses_from_the_top_of_the_walk(
    repository: CounterpartyEstablishmentRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first rung of the walk is covered on the same terms as the last."""
    monkeypatch.setattr(ladder_module, "territorial_scope_for_printed_tax_identifier", _refusing_rung)

    with pytest.raises(IvaCatalogueError):
        _resolve(repository, tax_identifier=_GERMAN_VAT)


def test_the_same_call_reports_an_unestablished_party_against_the_real_registry(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    """The control for the refusal above: not-established is a returned value, never an exception.

    Without this pair the refusal test proves only that something raised, not
    that the two outcomes travel on different channels.
    """
    resolved = _resolve(repository, country_name="Wakanda", postal_code=_MADRID)

    assert resolved.scope is None
    assert resolved.contradiction is None
