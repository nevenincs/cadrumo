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

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ._ledger_value_fixtures import repository

__all__ = ["repository"]

# Imported absolutely, not as `from .. import <module>`: the test needs
# the MODULE object, and the package-facade gate reads any `from ..
# import` edge as reaching through the inert namespace.
import cadrumo.application.ledger.establishment_ladder as ladder_module

from ....adapters.inbound.einvoice._parsers import ParsedEInvoice, parse_einvoice_document
from ....adapters.persistence.storage.errors import SecureObjectRowIdentityError
from ....core.classifier_input_source import ClassifierInputSource
from ....domain.iva.classification import InvoiceKind, IvaTerritorialScope
from ....domain.iva.errors import IvaCatalogueError
from ....domain.iva.establishment import (
    country_code_for_printed_tax_identifier,
    territorial_scope_for_country,
    territorial_scope_for_spanish_postal_code,
)
from ....domain.iva.identification import identification_state_for_printed_tax_identifier
from ....domain.iva.schema import EUMemberState
from ....tests.attribute_scope import scoped_attribute
from ..counterparty_establishment import (
    ConfirmedCounterpartyFactsRepository,
    ConfirmedCounterpartyResolution,
    record_confirmed_counterparty_facts,
)
from ..establishment_ladder import (
    CounterpartyEstablishment,
    EstablishmentRung,
    _charged_iva_rates,
    _spanish_iva_was_charged,
    resolve_counterparty_establishment_scope,
    resolve_draft_counterparty_establishment,
)
from ..evidence_draft import counterparty_draft_side
from ..invoice_draft_records import InvoiceDraft, InvoiceDraftLine, InvoiceDraftRateBreakdown
from ..regime_contradiction import draft_prints_a_repercutido_line

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "37373737-3737-4737-8737-373737373737"
runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")
_SPANISH_CIF = "B12345674"
_GERMAN_IVA = "DE811234567"
_GREEK_IVA = "EL123456789"
_ASSERTED_AT = datetime(2026, 5, 12, 9, 30, tzinfo=UTC)

_LAS_PALMAS = "35001"
_MADRID = "28013"
_PARIS = "75001"
_BERLIN = "10115"
_CEUTA = "51001"


def _resolve(
    repository: ConfirmedCounterpartyFactsRepository,
    *,
    tax_identifier: str | None = None,
    country_name: str | None = None,
    country_code: str | None = None,
    postal_code: str | None = None,
) -> CounterpartyEstablishment:
    return resolve_counterparty_establishment_scope(
        bucket_id=_BUCKET_ID,
        tax_identifier=tax_identifier,
        stated_country_name=country_name,
        resolved_country_code=country_code,
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
    ("France", _PARIS, EstablishmentRung.ADDRESS_COUNTRY, IvaTerritorialScope.EU_MEMBER),
    ("Alemania", _BERLIN, EstablishmentRung.ADDRESS_COUNTRY, IvaTerritorialScope.EU_MEMBER),
    (None, _MADRID, None, None),
)


@pytest.mark.parametrize(("country_name", "postal_code", "expected_rung", "expected_scope"), _MEASURED_CASES)
def test_ladder_composes_the_measured_cases(
    repository: ConfirmedCounterpartyFactsRepository,
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
    repository: ConfirmedCounterpartyFactsRepository,
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
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A French party is not read as Spanish, and the skipped rung would have said so.

    ``75001`` is a real Paris code and a real Madrid-shaped one. The second
    assertion is what makes this a test of ORDER: it establishes that the postal
    rung, had it been consulted, would have returned a different territory.
    """
    resolved = _resolve(repository, country_name="France", postal_code=_PARIS)

    assert resolved.scope is IvaTerritorialScope.EU_MEMBER
    assert resolved.rung is EstablishmentRung.ADDRESS_COUNTRY

    skipped_rung_answer = territorial_scope_for_spanish_postal_code(_PARIS)
    assert skipped_rung_answer is IvaTerritorialScope.ES_MAINLAND
    assert skipped_rung_answer is not resolved.scope


def test_the_country_rung_stops_the_ladder_before_a_territory_outside_liva(
    repository: ConfirmedCounterpartyFactsRepository,
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


def test_a_registration_disagreeing_with_the_address_settles_neither(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A German IVA number on a page addressed to Las Palmas settles NOTHING.

    The same page this file once used to prove the identifier rung outranked the
    others. That ordering is retired, and the retirement inverts the verdict
    rather than merely restating it: a foreign registration beside Spanish
    address evidence is the characteristic face of an entity registered abroad
    and operating through an establecimiento permanente here, so it surfaces to
    the operator instead of being resolved by whichever rung was consulted first.

    Still discriminating, and now in BOTH directions. The lower rungs would
    resolve this page to Canarias and the old top rung to EU_MEMBER, so the
    assertion cannot pass by every rung agreeing — it fails if either side wins.
    """
    resolved = _resolve(
        repository,
        tax_identifier=_GERMAN_IVA,
        country_name="España",
        postal_code=_LAS_PALMAS,
    )

    assert resolved.conflicted
    assert resolved.scope is None
    assert resolved.rung is None

    lower_rung_answer = territorial_scope_for_spanish_postal_code(_LAS_PALMAS)
    assert lower_rung_answer is IvaTerritorialScope.ES_CANARIAS
    assert resolved.scope is not lower_rung_answer
    assert resolved.scope is not IvaTerritorialScope.EU_MEMBER


def test_a_greek_iva_prefix_resolves_through_its_iso_code(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """``EL`` is Greece's IVA prefix while ``GR`` is its ISO code, and the catalogues are ISO-keyed.

    Left untranslated, a Greek party matches no Member State and is placed in a
    third country -- an intra-community acquisition reclassified as an import.
    """
    assert country_code_for_printed_tax_identifier(_GREEK_IVA) == "GR"

    resolved = _resolve(repository, tax_identifier=_GREEK_IVA)

    # The divergence now bites on the fact a registration actually settles. Left
    # untranslated the number names no Member State at all, so the party's
    # identification would read as unestablished rather than as Greek.
    assert resolved.identification_state is EUMemberState.GR

    # And it carries through to the territory once something corroborates it,
    # which is where a mistranslation would have reclassified an intra-community
    # acquisition as an import.
    corroborated = _resolve(repository, tax_identifier=_GREEK_IVA, country_name="Grecia")
    assert corroborated.scope is IvaTerritorialScope.EU_MEMBER


def test_a_spanish_identifier_contributes_nothing_to_the_identifier_rung(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Registration is not establishment, so neither Spanish spelling opens a rung.

    The bare CIF and the ``ES``-prefixed form are both checksum-valid Spanish
    identifiers and both establish where the party is REGISTERED. Establishment
    for IVA is the sede de actividad económica, and the validator's own
    non-resident leaders are the counter-population.

    The IDENTIFICATION axis now answers for the prefixed spelling, and that is
    the separation rather than a contradiction of it. RGAT art. 25 makes the
    ``ES`` prefix the regulated printed form of a NIF-IVA, so a document
    carrying it states where the party is REGISTERED -- while establishment
    stays unanswered, because registration is not establishment. The bare CIF
    prints no prefix and so states no identification at all: reading that
    absence as Spanish would manufacture the fact from silence.
    """
    assert identification_state_for_printed_tax_identifier(_SPANISH_CIF) is None
    assert identification_state_for_printed_tax_identifier(f"ES{_SPANISH_CIF}") is EUMemberState.ES
    # The rung this test is named for is the ESTABLISHMENT one, and neither
    # spelling opens it.
    assert country_code_for_printed_tax_identifier(f"ES{_SPANISH_CIF}") is None

    resolved = _resolve(repository, tax_identifier=_SPANISH_CIF)

    assert resolved.scope is None
    assert resolved.rung is None


def test_a_prefix_on_arbitrary_text_is_not_a_country(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Two leading letters are not an IVA number, so the body must match its own State's shape."""
    resolved = _resolve(repository, tax_identifier="FRANCISCO")

    assert resolved.scope is None
    assert resolved.rung is None


@pytest.mark.parametrize("printed_identifier", [_SPANISH_CIF, f"ES{_SPANISH_CIF}"])
def test_the_bare_domestic_invoice_exhausts_to_nothing(
    repository: ConfirmedCounterpartyFactsRepository,
    printed_identifier: str,
) -> None:
    """The ruling's own fixture: a Spanish identifier, no country, a Spanish postal code.

    This is the commonest ingested document there is, and the mainland is its
    commonest true answer -- which is exactly why a default here would be
    invisible.

    **Both spellings are driven, and the prefixed one is the composed claim the
    ruling actually makes.** A Spanish IVA prefix beside a Spanish postal code is
    the shape a fiscal representative's address takes for an entidad no
    residente: registration in Spain, establishment elsewhere. Each half is
    refused at its own rung, but "refused at the rung" and "refused by the
    assembled ladder" are different statements, and it is the second one the
    ruling makes. Driving only the bare CIF gated the easier half.
    """
    resolved = _resolve(repository, tax_identifier=printed_identifier, postal_code=_MADRID)

    assert resolved.scope is None
    assert resolved.rung is None
    assert resolved.source is None
    assert resolved.declared_fact is None


@pytest.mark.parametrize("scope", list(IvaTerritorialScope))
def test_no_scope_is_reachable_from_absent_evidence(
    repository: ConfirmedCounterpartyFactsRepository,
    scope: IvaTerritorialScope,
) -> None:
    """Sweep the whole closed set: absence produces no member of it, not merely not the mainland."""
    resolved = _resolve(repository)

    assert resolved.scope is not scope
    assert resolved.scope is None


def test_an_unrecognised_country_name_never_degrades_to_a_country(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A name outside the vocabulary establishes nothing, and does not fall through to the postal rung."""
    resolved = _resolve(repository, country_name="Wakanda", postal_code=_MADRID)

    assert resolved.scope is None
    assert resolved.rung is None


def test_the_printed_evidence_rungs_are_backed_by_the_document(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """An evidence rung records a page as its backing, so an auditor is sent to one."""
    resolved = _resolve(repository, country_name="España", postal_code=_LAS_PALMAS)

    assert resolved.source is ClassifierInputSource.DOCUMENT_EVIDENCE
    declared = resolved.declared_fact
    assert declared is not None
    assert declared.value is IvaTerritorialScope.ES_CANARIAS
    assert declared.source is ClassifierInputSource.DOCUMENT_EVIDENCE


def test_a_confirmed_fact_answers_only_once_the_paper_has_settled_nothing(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """The last rung carries an operator's backing, not a document's.

    The same page that exhausted the evidence rungs above now resolves, which is
    the whole ergonomic argument: one question per counterparty rather than one
    per invoice.
    """
    record_confirmed_counterparty_facts(
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
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Disagreement is carried with NO scope, so neither side is preferred by accident.

    Consulting the store even on a decisive page is what keeps this channel
    alive: a first-decisive-rung walk that stopped at the paper would never
    notice, for exactly the population the contradiction protects.
    """
    record_confirmed_counterparty_facts(
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
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A stored fact that agrees does not demote the page that proved it."""
    record_confirmed_counterparty_facts(
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
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A broken data file raises out of the ladder, and is not a counterparty question.

    The distinguishability is the point. An operator told "this counterparty's
    territory is unestablished" is handed a question they can answer; an operator
    told nothing while the registry is broken is handed a wrong answer with no
    remedy, since confirming the counterparty would paper over a defect.
    """
    with (
        scoped_attribute(ladder_module, "country_code_for_printed_country_name", _refusing_rung),
        pytest.raises(IvaCatalogueError),
    ):
        _resolve(repository, country_name="España", postal_code=_MADRID)


def test_a_corrupt_territory_registry_refuses_from_inside_the_rung_walk(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """The postal rung's refusal survives the walk too, not only the lookup before it.

    Asked separately because the two rungs raise at different depths: the country
    vocabulary is consulted before the ordered walk begins, while the territory
    registry is read from inside it. A single ``except`` placed around the walk
    would leave the first test green and swallow this one, which is precisely the
    shape that turns a broken data file into a counterparty question.
    """
    with (
        scoped_attribute(ladder_module, "territorial_scope_for_spanish_postal_code", _refusing_rung),
        pytest.raises(IvaCatalogueError),
    ):
        _resolve(repository, country_name="España", postal_code=_MADRID)


def test_a_corrupt_identifier_rung_refuses_from_the_top_of_the_walk(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """The first lookup of the walk is covered on the same terms as the last.

    The symbol changed with the re-runging and the property did not. The walk no
    longer asks what territory a prefix establishes; it asks which State the
    number identifies, and that call is now what runs first. Patching the retired
    symbol would leave this case passing against a lookup the walk never makes —
    a gate green because it patched nothing.
    """
    with (
        scoped_attribute(ladder_module, "identification_state_for_printed_tax_identifier", _refusing_rung),
        pytest.raises(IvaCatalogueError),
    ):
        _resolve(repository, tax_identifier=_GERMAN_IVA)


def test_a_corrupt_country_rung_refuses_from_between_the_covered_depths(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """The rung BETWEEN the other three, which bracketing them left uncovered.

    The three cases above sit before the walk, at its first rung and at its last,
    and that arrangement reads as complete without being so: an ``except`` around
    the country rung alone falls in the space between two correct depths. It was
    measured rather than reasoned about -- swallowing this rung and no other left
    the entire suite green, so the coverage this file claimed was one rung wider
    than the coverage it had.

    Depth-by-depth rather than one case standing for the walk, because "no rung is
    wrapped" is a claim about every rung individually and a gate that proves it
    for three of four proves the wrong statement.
    """
    with (
        scoped_attribute(ladder_module, "territorial_scope_for_country", _refusing_rung),
        pytest.raises(IvaCatalogueError),
    ):
        _resolve(repository, country_name="France")


def test_a_store_that_cannot_be_read_refuses_rather_than_reporting_no_confirmed_fact(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """The confirmed-fact rung propagates on the same terms as the document rungs.

    Decided rather than merely covered, because this rung sits differently from
    the other three: a corrupt bundled registry is unambiguously a defect, while
    "the store did not answer" could defensibly have been folded into "nothing is
    confirmed". It is not, and the reason is sharper than for the others -- the
    operator may have confirmed this very counterparty already, so swallowing the
    failure would retract their own earlier answer and ask them for it again,
    against a store that would refuse to record it.

    The tier below takes the same position: the secure repository raises rather
    than returning ``None`` when a row exists but its identity is inconsistent,
    so that an inconsistency cannot hide behind an ordinary miss. Folding the
    store's refusal into an empty resolution here would undo that one layer up.
    """

    def _unreadable_store(**_kwargs: object) -> ConfirmedCounterpartyResolution:
        raise SecureObjectRowIdentityError(
            ConfirmedCounterpartyFactsRepository.namespace,
            expected_identifier="0" * 64,
            payload_identifier="1" * 64,
        )

    with (
        scoped_attribute(ladder_module, "resolve_confirmed_counterparty_facts", _unreadable_store),
        pytest.raises(SecureObjectRowIdentityError),
    ):
        _resolve(repository, tax_identifier=_SPANISH_CIF)


def test_the_same_call_reports_an_unestablished_party_against_the_real_registry(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """The control for the refusal above: not-established is a returned value, never an exception.

    Without this pair the refusal test proves only that something raised, not
    that the two outcomes travel on different channels.
    """
    resolved = _resolve(repository, country_name="Wakanda", postal_code=_MADRID)

    assert resolved.scope is None
    assert resolved.contradiction is None


class TestDraftRouting:
    """The counterparty side is chosen by direction, through the one authority.

    A draft is pre-direction data, so this is where the operator's ``--kind``
    reaches the establishment question. The selection is shared with the confirm
    path rather than restated, because a document read as having one counterparty
    when its identity is resolved and another when its territory is would produce
    two coherent, disagreeing records of the same invoice.
    """

    def test_an_issued_document_takes_the_billed_party(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """On an invoice the filer issued, the counterparty is the customer.

        Discriminating rather than agreeing: the supplier side of this draft
        carries a German number, so a selection that fell through to it would
        name a Member State instead of exhausting. The identification axis is
        what the assertion below reads, because it names the FACT the printed
        number states rather than an inference drawn from it, and a resolution
        that took the wrong party could not leave it empty.
        """
        draft = InvoiceDraft(
            supplier_tax_id=_GERMAN_IVA,
            customer_tax_id=_SPANISH_CIF,
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=draft,
            kind=InvoiceKind.ISSUED,
            repository=repository,
        )

        assert resolved.scope is None
        assert resolved.identification_state is None
        assert identification_state_for_printed_tax_identifier(draft.supplier_tax_id) is EUMemberState.DE

    def test_a_received_document_takes_the_issuing_party(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """On an invoice the filer received, the counterparty is the supplier."""
        draft = InvoiceDraft(
            supplier_tax_id=_GERMAN_IVA,
            customer_tax_id=_SPANISH_CIF,
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=draft,
            kind=InvoiceKind.RECEIVED,
            repository=repository,
        )

        # Proven on the identification rather than the territory, and it is the
        # sharper probe: the prefix settles that fact terminally, so a DE reading
        # can only have come from the supplier's number. The territory is
        # deliberately unsettled on this page — neither party printed an address —
        # which is now the honest answer rather than a routing failure.
        assert resolved.identification_state is EUMemberState.DE
        assert resolved.scope is None

    def test_the_selection_never_falls_back_to_the_other_side(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """An unread counterparty stays unread rather than becoming the filer.

        The fall-back this refuses is not hypothetical. The text and vision
        readers cannot populate a customer at all, so a selection reading "the
        customer if set, otherwise the supplier" resolved every issued document
        to the supplier -- who, on a document the filer issued, IS the filer.
        """
        draft = InvoiceDraft(supplier_tax_id=_SPANISH_CIF)

        side = counterparty_draft_side(draft, kind=InvoiceKind.ISSUED)

        assert side.tax_id is None
        assert side.tax_id_field == "customer_tax_id"

    def test_both_directions_carry_their_own_postal_code(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """Establishment is asked of each party independently, so the codes do not share.

        An issuer in Las Palmas invoicing a customer in Madrid crosses a
        territorial boundary one shared code could not express.
        """
        draft = InvoiceDraft(
            supplier_postal_code=_LAS_PALMAS,
            customer_postal_code=_MADRID,
        )

        assert counterparty_draft_side(draft, kind=InvoiceKind.ISSUED).postal_code == _MADRID
        assert counterparty_draft_side(draft, kind=InvoiceKind.RECEIVED).postal_code == _LAS_PALMAS


class TestRungReachabilityFromADraft:
    """Which rungs a draft can reach, asserted so neither the gap nor its closing goes quiet.

    This class began as a record of a gap: no reader recovered a party's printed
    country, so the country rung had no source and the postal rung -- gated on
    country evidence naming Spain -- could not be triggered. **The assertion that
    the draft carried no country field failed the day the reading contract grew
    one, which is what it was for.** A wired ladder returning correct answers
    reads as a reachable ladder whether or not it is one, so the reachability
    question is kept in gates rather than in anyone's memory.

    The gap did not close everywhere. **The read path reaches every rung; the
    structured path still reaches only two**, because the e-invoice parsers read
    a postal element and no country element. Both halves are asserted below.

    **Replace these when reachability changes, never relax them.** A failure here
    means a path gained or lost a rung, and the right response is a gate saying
    which.
    """

    def test_a_printed_country_name_reaches_the_country_rung(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The rung the read path's country field exists to feed now fires from a draft."""
        draft = InvoiceDraft(supplier_country="Alemania", supplier_postal_code=_BERLIN)

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=draft,
            kind=InvoiceKind.RECEIVED,
            repository=repository,
        )

        assert resolved.scope is IvaTerritorialScope.EU_MEMBER
        assert resolved.rung is EstablishmentRung.ADDRESS_COUNTRY

    def test_a_printed_spanish_country_name_reaches_the_postal_rung(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """The postal rung is reachable end to end, which is what the territory table is for.

        The whole chain runs from draft fields: the country name opens the rung
        that the country resolver deliberately refuses to answer, and the postal
        code separates the three Spanish territories behind it.
        """
        draft = InvoiceDraft(
            supplier_tax_id=_SPANISH_CIF,
            supplier_country="España",
            supplier_postal_code=_LAS_PALMAS,
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=draft,
            kind=InvoiceKind.RECEIVED,
            repository=repository,
        )

        assert resolved.scope is IvaTerritorialScope.ES_CANARIAS
        assert resolved.rung is EstablishmentRung.SPANISH_POSTAL_CODE

    def test_the_side_selector_carries_each_party_country_to_its_own_rung(self) -> None:
        """The country follows the direction selection, or the rung reads the wrong party's."""
        draft = InvoiceDraft(supplier_country="España", customer_country="France")

        assert counterparty_draft_side(draft, kind=InvoiceKind.ISSUED).country == "France"
        assert counterparty_draft_side(draft, kind=InvoiceKind.RECEIVED).country == "España"

    def test_a_draft_stating_no_country_still_exhausts(
        self,
        repository: ConfirmedCounterpartyFactsRepository,
    ) -> None:
        """A readable postal code is still not on its own evidence of Spain.

        The rung would answer this code -- the last assertion proves it -- so this
        is a statement about the absent country evidence, not about the code.
        Unchanged by the reading contract gaining a country field: a document that
        prints no country still states none.
        """
        draft = InvoiceDraft(supplier_tax_id=_SPANISH_CIF, supplier_postal_code=_LAS_PALMAS)

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=draft,
            kind=InvoiceKind.RECEIVED,
            repository=repository,
        )

        assert resolved.scope is None
        assert resolved.rung is None
        assert territorial_scope_for_spanish_postal_code(_LAS_PALMAS) is IvaTerritorialScope.ES_CANARIAS

    def test_the_structured_parsers_supply_a_party_country(self) -> None:
        """The structured path has a country source now, which is what opens its postal rung.

        Asserted against the parser's own fields rather than against a parsed
        document, so it holds for every format the reader accepts rather than for
        whichever specimen happens to be in the corpus. This replaces the
        assertion that no such field existed: that one failed the day the source
        landed, which is what it was for.

        What each format actually STATES is a separate question this cannot see,
        and it is covered end to end against real documents in
        ``test_structured_path_country_codes.py``.
        """
        parsed_fields = set(ParsedEInvoice.__slots__)

        assert {"supplier_country_code", "customer_country_code"} <= parsed_fields
        assert {"supplier_postal_code", "customer_postal_code"} <= parsed_fields

    def test_the_cross_industry_invoice_branch_now_states_a_country_too(self) -> None:
        """The last unread structured country, and the rung it was holding shut.

        Replaces ``test_asserted_gap_the_cross_industry_invoice_branch_states_no_country``,
        which asserted this document's ``supplier_country_code`` was ``None``
        and went red the day the CII read landed -- the notification it existed
        to give. Replaced with the positive contract rather than relaxed, per
        that test's own instruction: a gap test that gets adjusted to match the
        code cancels the gate at the moment it fires.

        The document is kept byte for byte from the gap assertion so this is a
        statement about the SAME bytes. It always stated ``ram:CountryID``; what
        changed is that the reader now takes it, which is why the postal code
        alone was never the question. ``38001`` is Santa Cruz de Tenerife, so
        the answer the chain produces is Canarias -- an answer no default could
        return, and one the postal rung cannot even be asked for until the
        country evidence names Spain.
        """
        specimen = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
  <rsm:ExchangedDocument><ram:ID>CII-2026-0001</ram:ID></rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Vendedor Insular SL</ram:Name>
        <ram:PostalTradeAddress>
          <ram:PostcodeCode>38001</ram:PostcodeCode>
          <ram:CountryID>ES</ram:CountryID>
        </ram:PostalTradeAddress>
      </ram:SellerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""
        parsed = parse_einvoice_document(specimen)

        assert parsed.supplier_postal_code == "38001"
        assert parsed.supplier_country_code == "ES"
        # The pairing is the point: a country that names Spain is what admits
        # the postal code as territory evidence at all.
        assert territorial_scope_for_spanish_postal_code("38001") is IvaTerritorialScope.ES_CANARIAS


# -- the rate walk must see every carrier a reader can fill -----------------
#
# ``spanish_iva_charged`` is derived from this walk alone, and it decides
# whether the establecimiento-permanente contradiction gets its rate signal and
# whether rung 3 gets a corroborator. The three carriers are populated by
# DIFFERENT readers -- lines and subtotals only by the structured one, the flat
# rate only by the model-read one -- so a walk of a subset silently turns the
# signal off for whole lanes rather than for odd documents.
#
# Driven from a DRAFT rather than by injecting the rate list. Every other rate
# case in this package passes ``charged_iva_rates`` straight in, which is why a
# collector blind to an entire lane sat unnoticed: injecting the answer cannot
# test the question.

_FLAT_RATE_DRAFT = InvoiceDraft(
    taxable_base=Decimal("1000.00"),
    iva_rate=Decimal("21"),
    iva_amount=Decimal("210.00"),
    grand_total=Decimal("1210.00"),
)


def test_the_model_read_lanes_only_rate_carrier_is_collected() -> None:
    """The measured gap: a text- or vision-read document carries only this one.

    Those readers recover printed totals rather than a line decomposition, so
    neither structured carrier is ever populated for them.
    """
    assert _charged_iva_rates(_FLAT_RATE_DRAFT) == (Decimal("21"),)


@pytest.mark.parametrize(
    "draft",
    [
        _FLAT_RATE_DRAFT,
        InvoiceDraft(lines=(InvoiceDraftLine(iva_rate=Decimal("21")),)),
        InvoiceDraft(iva_breakdown=(InvoiceDraftRateBreakdown(iva_rate=Decimal("21")),)),
    ],
    ids=["flat-model-read", "lines-structured", "subtotals-structured"],
)
def test_each_carrier_alone_is_enough_to_report_the_charge(draft: InvoiceDraft) -> None:
    """A document uses whichever carrier its reader could fill, and no more."""
    assert _charged_iva_rates(draft) == (Decimal("21"),)


def test_the_two_authorities_on_charged_tax_agree_about_the_flat_carrier() -> None:
    """One package must not hold two answers to whether a document charged tax.

    The regime-contradiction check already read the flat rate, so before this
    the pair disagreed on exactly the model-read lane: that check fired while
    the ladder saw no charge at all.
    """
    assert draft_prints_a_repercutido_line(_FLAT_RATE_DRAFT)
    assert _charged_iva_rates(_FLAT_RATE_DRAFT) != ()


def test_the_collected_flat_rate_reaches_the_spanish_registry_lookup() -> None:
    """Collecting it is worthless unless it survives to the question it feeds."""
    rates = _charged_iva_rates(_FLAT_RATE_DRAFT)

    assert _spanish_iva_was_charged(rates, on_date=date(2026, 5, 12))


def test_a_draft_charging_nothing_still_reports_no_rate() -> None:
    """The precision half: an exempt or reverse-charge draft states no rate."""
    assert _charged_iva_rates(InvoiceDraft(taxable_base=Decimal("1000.00"))) == ()


def test_reading_the_flat_carrier_is_what_makes_the_lane_visible() -> None:
    """Mutation proof: without it the model-read lane collects nothing at all.

    Re-runs the pre-change walk, over the two structured carriers only. It
    returns empty for a draft that plainly charges 21%, and every signal derived
    from it goes quiet -- which is the silent lane blindness this closes.
    """

    def _structured_carriers_only(draft: InvoiceDraft) -> tuple[Decimal, ...]:
        rates = [line.iva_rate for line in draft.lines if line.iva_rate is not None]
        rates.extend(sub.iva_rate for sub in draft.iva_breakdown if sub.iva_rate is not None)
        return tuple(rates)

    assert _structured_carriers_only(_FLAT_RATE_DRAFT) == ()
    assert not _spanish_iva_was_charged(
        _structured_carriers_only(_FLAT_RATE_DRAFT),
        on_date=date(2026, 5, 12),
    )
    assert _charged_iva_rates(_FLAT_RATE_DRAFT) != ()
