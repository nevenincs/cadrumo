"""Modelo 721 finite BOE-package temporal regressions."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from .....core.resources._boundary import bundled_path
from .....tests import REPO_ROOT
from ..corpus_catalogue import verify_source_file
from ..errors import NoRevisionForPeriodError, RegistryValidationError
from ..legal import verify_legal_catalogue
from ..schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M721_BOE_ERAS = (
    (2023, "boe-modelo-721-2023-layout"),
    (2024, "boe-modelo-721-2024-layout"),
)


def _modelo_721() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("721")


def _revision_721(year: int) -> tuple[ModeloDefinition, ModeloRevision, RegistryCatalogues]:
    modelo, catalogues = _modelo_721()
    return modelo, modelo.revisions[str(year)], catalogues


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key)
            yield from _strings(item)
        return
    if isinstance(value, list | tuple | set | frozenset):
        for item in value:
            yield from _strings(item)


def test_modelo_721_articles_are_content_deadline_and_annex_amendment() -> None:
    _, catalogues = _modelo_721()
    art_3 = catalogues.legal["orden-hfp-886-2023:art-3"]
    art_4 = catalogues.legal["orden-hfp-886-2023:art-4"]
    amendment = catalogues.legal["orden-hac-1504-2024:art-9"]
    first_application = catalogues.legal["orden-hac-1504-2024:df-unica"]

    assert art_3.article == "3"
    assert art_3.required_text == (
        "información contenida en el anexo",
        "artículo 42 quater",
        "monedas virtuales situadas en el extranjero",
    )
    assert "1 de enero" not in art_3.required_text
    assert "31 de marzo" not in art_3.required_text
    assert art_4.article == "4"
    assert "1 de enero" in art_4.required_text
    assert "31 de marzo" in art_4.required_text
    assert "Se sustituye el anexo" in amendment.required_text
    assert "ejercicio 2024" in first_application.required_text
    verify_legal_catalogue(
        {
            art_3.id: art_3,
            art_4.id: art_4,
            amendment.id: amendment,
            first_application.id: first_application,
        },
        source_root=bundled_path(),
    )


def test_modelo_721_selects_only_its_two_hash_pinned_boe_form_spec_eras() -> None:
    """Each selected year names and verifies only its official BOE package."""
    modelo, catalogues = _modelo_721()

    assert set(modelo.revisions) == {"2023", "2024"}
    assert set(modelo.source_refs) == {"aeat-modelo-721-procedure"}
    for filing_year, source_ref in _M721_BOE_ERAS:
        revision = modelo.revisions[str(filing_year)]
        source = catalogues.sources[source_ref]

        assert revision.authority_grade is not None
        assert revision.authority_grade.value == "applicability"
        # 2024 is OPEN: HAC/1504/2024 substitutes the anexo of Orden HFP/886/2023 and
        # applies it "por primera vez" to ejercicio 2024, and BOE's consolidated
        # Referencias posteriores for BOE-A-2023-17429 (read 2026-08-30) records that
        # substitution as the ONLY subsequent amendment -- nothing in 2025 or 2026.
        is_open = filing_year == 2024
        era_end = None if is_open else date(filing_year, 12, 31)
        assert revision.valid_from == date(filing_year, 1, 1)
        assert revision.valid_to == era_end
        if is_open:
            # An open era cannot be spelled with an explicit `years` list, so this one
            # is the range form with no upper bound.
            assert revision.period_selector.years == ()
            assert revision.period_selector.year_from == filing_year
            assert revision.period_selector.year_to is None
        else:
            assert revision.period_selector.years == (filing_year,)
            assert revision.period_selector.year_from is None
        assert revision.period_selector.includes_year(filing_year)
        assert {ref for ref in revision.source_refs if ref.startswith("boe-modelo-721-")} == {source_ref}
        assert revision.export_layouts == ()
        assert source.authority == "boe"
        assert source.evidence_tier == "layout_authority"
        assert source.kind == "form_spec"
        assert source.applies_from == date(filing_year, 1, 1)
        assert source.applies_to == era_end
        assert source.corpus_path.endswith(".pdf")
        verify_source_file(REPO_ROOT, source)
        assert select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31)) == revision

        assert {ref.workbook_source for ref in revision.workbook_parity_refs} == {source_ref}
        assert {window.filing_year for window in revision.deadline_windows} == {filing_year}
        assert all(casilla.source_refs == (source_ref,) for casilla in revision.casillas)

    revision_2023 = modelo.revisions["2023"]
    revision_2024 = modelo.revisions["2024"]
    assert "orden-hac-1504-2024:art-9" not in revision_2023.legal_refs
    assert {"orden-hac-1504-2024:art-9", "orden-hac-1504-2024:df-unica"} <= set(revision_2024.legal_refs)
    # Refused BELOW the first declared era only. 2025+ used to be refused here; that was
    # a hole, not conservatism -- BOE's Referencias posteriores for BOE-A-2023-17429
    # records HAC/1504/2024 as the only subsequent amendment, so its substituted anexo
    # still governs 2025 and later.
    for filing_year in (2021, 2022):
        with pytest.raises(NoRevisionForPeriodError):
            select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31))
    for filing_year in (2025, 2026):
        carried = select_revision(modelo, filing_year=filing_year, period="0A", on=date(filing_year, 12, 31))
        assert carried.id == "2024"


def test_modelo_721_refuses_a_mutated_2023_selector_past_its_boe_package_window() -> None:
    """A selector expansion cannot turn the 2023 Annex into 2024 authority.

    Re-aimed from the 2024 era, which is no longer a boundary: HAC/1504/2024 SUBSTITUTES
    the anexo of Orden HFP/886/2023 and BOE's Referencias posteriores for BOE-A-2023-17429
    lists no amendment after it, so the 2024 package legitimately reaches 2025 and there
    is nothing to refuse there. 2023/2024 remains a real closed boundary -- the 2024
    substitution is exactly what closes the 2023 package -- so the over-reach this guard
    exists to catch is still provably refused.
    """
    modelo, revision, catalogues = _revision_721(2023)
    expanded = revision.model_copy(
        update={
            "valid_to": date(2024, 12, 31),
            "period_selector": revision.period_selector.model_copy(update={"years": (2023, 2024)}),
        },
    )
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, "2023": expanded}})

    selected = select_revision(
        mutated_modelo, filing_year=2024, period="0A", on=date(2024, 12, 31), revision_id="2023"
    )
    assert selected.id == "2023"
    (source_ref,) = (ref for ref in selected.source_refs if ref.startswith("boe-modelo-721-"))
    source = catalogues.sources[source_ref]

    assert source.applies_to == date(2023, 12, 31)
    assert not source.applies_across(date(2024, 1, 1), date(2024, 12, 31))


def test_modelo_721_refuses_a_mutated_boe_package_hash() -> None:
    """The selected finite era remains bound to the exact official PDF bytes."""
    _modelo, _revision, catalogues = _revision_721(2024)
    source_ref = "boe-modelo-721-2024-layout"
    source = catalogues.sources[source_ref].model_copy(update={"sha256": "0" * 64})

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        verify_source_file(REPO_ROOT, source)


def test_modelo_721_does_not_claim_pair_complete_aeat_soap_xml_contract_authority() -> None:
    """Finite BOE Annex evidence is not a substitute for historical AEAT bytes."""
    modelo, catalogues = _modelo_721()
    all_modelo_strings = set(_strings(modelo.model_dump(mode="json")))

    assert "aeat-dr-721" not in all_modelo_strings
    assert "boe-modelo-721-2023-form" not in all_modelo_strings
    assert "ley-11-2021:da-10" not in all_modelo_strings
    assert "boe-modelo-721-2023-form" not in catalogues.sources
    assert catalogues.sources["aeat-modelo-721-procedure"].evidence_tier == "official_source_guidance"
    for revision in modelo.revisions.values():
        assert revision.reviewed_by is not None
        assert "AEAT SOAP/XML material is not pair-complete" in revision.reviewed_by
        assert revision.authority_grade is not None
        assert revision.authority_grade.value == "applicability"
        assert revision.export_layouts == ()


def test_modelo_721_threshold_continuity_has_registry_parameters_without_calculation_surface() -> None:
    modelo, revision, _ = _revision_721(2024)

    link_ids_by_surface = {link.surface: link.id for link in revision.application_links}
    expected_link_ids_by_surface = {
        "portal": "modelo-721-portal",
        "filing": "modelo-721-filing",
        "extractor": "modelo-721-extractor",
        "deadline": "modelo-721-deadline",
    }

    assert "calculation" not in link_ids_by_surface
    assert "modelo-721-calculation" not in revision.constructs[0].application_links
    assert expected_link_ids_by_surface.items() <= link_ids_by_surface.items()
    assert {parameter.id for parameter in revision.parameters} >= {
        "modelo-721-asset-declaration-threshold-eur",
        "modelo-721-redeclaration-increment-threshold-eur",
    }
    assert modelo.id == "721"


def test_modelo_721_redeclaration_is_not_authored_as_scalar_previous_filing_binding() -> None:
    """M721 token continuity is row-set advisory evidence, not scalar previous_filing.

    The previous_filing resolver folds a casilla-value mapping to one Decimal per
    binding. Modelo 721 repeats the same token casillas per custodian/token row, so
    a scalar binding would lose the row identity needed for the re-declaration
    baseline. Reintroducing this as registry previous_filing requires a row-set
    selector, not the retired source_output key.
    """
    _, revision, _ = _revision_721(2024)

    previous_filing_bindings = [binding.id for binding in revision.bindings if binding.source == "previous_filing"]
    all_binding_strings = set(_strings(tuple(binding.model_dump(mode="json") for binding in revision.bindings)))

    assert previous_filing_bindings == []
    assert "source_output" not in all_binding_strings
