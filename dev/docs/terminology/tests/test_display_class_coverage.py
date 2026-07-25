"""Coverage gate: every injected search record derives exactly one display class.

The ratified search-record contract makes ``display_class`` a
closed axis derived once at the injection seam and shipped in the Pagefind meta.
This gate walks the SAME unified projection the injection consumes -- the real
approved concept cards, the real casilla projection, and constructed CLI
command/option records -- and proves :func:`derive_display_class` maps every one
to exactly one valid :class:`ResultDisplayClass` member, with no record falling
through to a null/unknown class. A record with no derivable class is a gate
failure: a record that maps to no class is a unit-gate failure.

The concept and casilla records come from the real deterministic projections
(no live CLI subprocess walk); the CLI records are constructed directly, mirroring
``test_unified_record.py``, because their shape -- not the transiently-broken tree
walk -- is the contract under test.
"""

from __future__ import annotations

import pytest

from cadrumo.core.external_constants import OutputLanguage

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _cli_command_record():
    from dev.docs.terminology._cli_projection import CliSurfaceRecord
    from dev.docs.terminology._search_record import SearchRecordKind

    return CliSurfaceRecord(
        kind=SearchRecordKind.CLI,
        descriptions={OutputLanguage.ES: "Anade una transaccion", OutputLanguage.EN: "Add a transaction"},
        command_path="aeat app ledger add",
        registry_key="ledger.add",
        family="app",
        target="cli/app.html#aeat-app-ledger-add",
    )


def _cli_option_record():
    from dev.docs.terminology._cli_projection import CliOptionRecord
    from dev.docs.terminology._search_record import SearchRecordKind

    return CliOptionRecord(
        kind=SearchRecordKind.CLI,
        descriptions={OutputLanguage.ES: "Importe de la transaccion"},
        command_path="aeat app ledger add",
        option_names=("--amount",),
        is_argument=False,
        required=True,
        target="cli/app.html#aeat-app-ledger-add",
    )


def _injected_unified_records():
    """The unified records the injection ships: concepts + casillas + CLI.

    Mirrors ``_materialise_records`` (only approved concept cards are injected;
    a draft card is scaffold-empty and 404s), but drives the real projections
    directly so the gate is deterministic and independent of the fragile live
    CLI subprocess walk.
    """
    from dev.docs.terminology._casilla_projection import project_casilla_search_records
    from dev.docs.terminology._concept_cards import project_concept_cards
    from dev.docs.terminology._unified_record import to_search_record

    concept_cards, _ = project_concept_cards()
    approved = [card for card in concept_cards if card.is_approved]
    casilla_records, _ = project_casilla_search_records()

    records = [to_search_record(card) for card in approved]
    records.extend(to_search_record(rec) for rec in casilla_records)
    records.append(to_search_record(_cli_command_record()))
    records.append(to_search_record(_cli_option_record()))
    return records


def test_every_injected_record_derives_exactly_one_valid_display_class() -> None:
    """Every shipped record maps to exactly one ``ResultDisplayClass`` member."""
    from dev.docs.terminology._search_record import ResultDisplayClass
    from dev.docs.terminology._unified_record import derive_display_class

    records = _injected_unified_records()
    # Guard against a vacuous pass: the real projections must actually produce a
    # substantial corpus (thousands of casillas + the approved concept cards).
    assert len(records) > 1000

    valid_members = set(ResultDisplayClass)
    unmapped: list[str] = []
    for record in records:
        display_class = derive_display_class(record)
        if display_class not in valid_members:
            unmapped.append(record.id)

    assert not unmapped, f"records that derived no valid display class: {unmapped[:20]}"


def test_every_display_class_is_exercised_by_the_injected_corpus() -> None:
    """The injected corpus + a technical page cover every navigable display class.

    Concept cards split into ``DOC`` (general-fact) and ``MODELO`` (modelo-domain)
    cards, casillas are ``CASILLA``, CLI records are ``CLI``. ``TECHNICAL`` is only
    reachable from a full-text ``api/`` page hit (not an injected custom record),
    so it is exercised through a constructed PAGE record to prove the derivation
    authority produces it.
    """
    from dev.docs.terminology._search_record import ResultDisplayClass, SearchRecordKind
    from dev.docs.terminology._unified_record import (
        RankingTier,
        SearchRecord,
        SearchRecordMetadata,
        derive_display_class,
    )

    derived = {derive_display_class(record) for record in _injected_unified_records()}
    # The injected surfaces cover DOC + MODELO (concepts), CASILLA, and CLI.
    assert {
        ResultDisplayClass.DOC,
        ResultDisplayClass.MODELO,
        ResultDisplayClass.CASILLA,
        ResultDisplayClass.CLI,
    } <= derived

    api_page = SearchRecord(
        id="page:api/cadrumo.core.html",
        kind=SearchRecordKind.PAGE,
        tier=RankingTier.FULLTEXT,
        title="cadrumo.core",
        descriptions={OutputLanguage.EN: "Core module reference."},
        target="api/cadrumo.core.html#module-cadrumo.core",
        ranking_weight=0.5,
        metadata=SearchRecordMetadata(),
    )
    assert derive_display_class(api_page) is ResultDisplayClass.TECHNICAL


def test_concept_domain_splits_modelo_from_general_fact() -> None:
    """A modelo-domain concept is ``MODELO``; every other domain is ``DOC``."""
    from dev.docs.terminology._search_record import ResultDisplayClass, SearchRecordKind
    from dev.docs.terminology._unified_record import (
        RankingTier,
        SearchRecord,
        SearchRecordMetadata,
        derive_display_class,
    )
    from dev.docs.terminology_handbook import ConceptDomain

    def concept(domain: ConceptDomain) -> SearchRecord:
        return SearchRecord(
            id=f"concept:{domain.value}",
            kind=SearchRecordKind.CONCEPT,
            tier=RankingTier.TERM,
            title="term",
            descriptions={OutputLanguage.EN: "gloss"},
            target="_generated/glossary.html#term-x",
            ranking_weight=0.5,
            metadata=SearchRecordMetadata(domain=domain.value),
        )

    assert derive_display_class(concept(ConceptDomain.MODELO)) is ResultDisplayClass.MODELO
    for domain in (
        ConceptDomain.CONCEPTO,
        ConceptDomain.REGIMEN,
        ConceptDomain.PERIODO,
        ConceptDomain.LEGAL,
        ConceptDomain.CASILLA_NAMESPACE,
        ConceptDomain.CLI_VERB,
    ):
        assert derive_display_class(concept(domain)) is ResultDisplayClass.DOC


def test_full_text_page_splits_by_path_prefix() -> None:
    """A full-text hit splits ``cli/`` -> CLI, ``api/`` -> TECHNICAL, else DOC."""
    from dev.docs.terminology._search_record import ResultDisplayClass, SearchRecordKind
    from dev.docs.terminology._unified_record import (
        RankingTier,
        SearchRecord,
        SearchRecordMetadata,
        derive_display_class,
    )

    def page(target: str) -> SearchRecord:
        return SearchRecord(
            id=f"page:{target}",
            kind=SearchRecordKind.PAGE,
            tier=RankingTier.FULLTEXT,
            title="page",
            descriptions={OutputLanguage.EN: "body"},
            target=target,
            ranking_weight=0.5,
            metadata=SearchRecordMetadata(),
        )

    assert derive_display_class(page("cli/app.html#x")) is ResultDisplayClass.CLI
    assert derive_display_class(page("api/cadrumo.core.html#x")) is ResultDisplayClass.TECHNICAL
    assert derive_display_class(page("how-to/import-ledger.html#x")) is ResultDisplayClass.DOC
    assert derive_display_class(page("index.html")) is ResultDisplayClass.DOC
