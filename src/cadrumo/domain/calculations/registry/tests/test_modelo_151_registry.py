"""Tests for the committed Modelo 151 (IRPF régimen impatriados / Beckham) registry foundation."""

from __future__ import annotations

import pytest

from .....core.resources._boundary import bundled_path
from .._validate import RegistryValidator
from ..legal import verify_legal_catalogue
from ..schema import ModeloDefinition, RegistryCatalogues
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M151_FORM_ORDER_REF = "orden-hap-2783-2015:art-1"


def _load_modelo_151() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("151")


def test_modelo_151_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_151()
    assert modelo.id == "151"
    assert modelo.revisions, "151 must declare at least one revision"
    assert any(rev.formulas for rev in modelo.revisions.values()), "151 must declare formulas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_151_revision_2015_declares_constructs() -> None:
    modelo, _ = _load_modelo_151()
    revision = modelo.revisions["2015-2022"]
    assert revision.constructs, "151 2015-2022 revision must declare constructs"
    construct_ids = {c.id for c in revision.constructs}
    assert "m151-impatriado-calculation" in construct_ids


def test_modelo_151_revision_2015_formula_targets_resolve() -> None:
    modelo, _ = _load_modelo_151()
    revision = modelo.revisions["2015-2022"]
    impatriado = next(c for c in revision.constructs if c.id == "m151-impatriado-calculation")
    formula_ids = {f.id for f in revision.formulas}
    for declared_formula in impatriado.formulas:
        assert declared_formula in formula_ids, (
            f"construct lists formula {declared_formula!r} but the revision does not declare it"
        )


def test_modelo_151_legal_authority_is_ley_35_2006_art_93() -> None:
    """M151 is the Beckham regime (Ley 35/2006 art. 93 LIRPF)."""
    modelo, catalogues = _load_modelo_151()
    revision = modelo.revisions["2015-2022"]
    impatriado = next(c for c in revision.constructs if c.id == "m151-impatriado-calculation")
    assert "ley-35-2006:art-93" in impatriado.legal_refs
    assert "ley-35-2006:art-93" in catalogues.legal


def test_modelo_151_form_order_is_boe_corpus_backed() -> None:
    modelo, catalogues = _load_modelo_151()
    revision = modelo.revisions["2015-2022"]
    legal = {_M151_FORM_ORDER_REF: catalogues.legal[_M151_FORM_ORDER_REF]}

    verify_legal_catalogue(legal, source_root=bundled_path())

    # Asserted on the REVISION, not the modelo. The approving orden is
    # span-scoped -- Orden HAP/2783/2015 governs 2015-2022 and a later
    # instrument governs the 2025 span -- so the modelo level carries only the
    # framework refs both spans share.
    assert _M151_FORM_ORDER_REF not in modelo.legal_refs
    assert _M151_FORM_ORDER_REF in revision.legal_refs
    assert revision.orden_aplicabilidad == (_M151_FORM_ORDER_REF,)
    reference = legal[_M151_FORM_ORDER_REF]
    assert reference.document_id == "BOE-A-2015-14021"
    assert reference.kind == "orden"
    assert reference.article == "1"


def test_modelo_151_2015_workbook_parity_uses_era_matching_record_design() -> None:
    """The 2015-2022 revision cites its own-era design.

    ``boe-modelo-151-layout`` was retiered to ``official_source_guidance`` (a
    915-byte orden excerpt with no annex/layout content). AEAT's historical
    Diseños de Registro index does publish an era-appropriate design for
    2015-2022 (Orden HAP/2783/2015); it had simply never been bundled, so
    this is a genuine acquisition and re-point, not a permanent gap.
    """
    modelo, catalogues = _load_modelo_151()
    revision = modelo.revisions["2015-2022"]
    workbook = revision.workbook_parity_refs[0]

    assert "boe-modelo-151-form" not in catalogues.sources
    assert catalogues.sources["aeat-modelo-151-procedure"].evidence_tier == "official_source_guidance"
    assert workbook.id == "modelo-151-cuota-escala"
    assert workbook.formula_coverage == "static_layout"
    assert workbook.workbook_source == "aeat-dr-151-2015"
    assert workbook.source_refs == ("aeat-dr-151-2015",)

    source = catalogues.sources[workbook.workbook_source]
    assert source.evidence_tier == "layout_authority"
    assert source.kind == "record_design"
    assert source.applies_from is not None and source.applies_from.year == 2015


def test_modelo_151_2025_workbook_parity_uses_era_matching_record_design() -> None:
    modelo, catalogues = _load_modelo_151()
    revision = modelo.revisions["2025-y-siguientes"]
    workbook = revision.workbook_parity_refs[0]

    assert workbook.id == "modelo-151-cuota-escala"
    assert workbook.formula_coverage == "static_layout"
    assert workbook.workbook_source == "aeat-dr-151-2023"
    assert workbook.source_refs == ("aeat-dr-151-2023",)

    source = catalogues.sources[workbook.workbook_source]
    assert source.evidence_tier == "layout_authority"
    assert source.kind == "record_design"
    assert source.applies_from is not None and source.applies_from.year == 2023


def test_modelo_151_carries_base_liquidable_under_declaration_advisory() -> None:
    """M151 guards the base-liquidable -> cuota-integra handoff (no-silent-under-declaration).

    ``impatriado.cuota-integra-general`` is formula-derived from
    ``impatriado.base-liquidable-general`` via ``lookup_bracket`` against the
    art. 93.2.e.1º escala, so a positive base resolving to a zero cuota would
    only be reachable through a registry regression -- but the verify gate
    must still surface it as an operator-facing ADVISORY rather than silently
    granting VERIFICADO_COMPLETO, mirroring the M131 01->02 and M200
    00501->DP200014:00552 worked-pattern guards.
    """
    modelo, _ = _load_modelo_151()
    revision = modelo.revisions["2015-2022"]

    predicates = {p.predicate_id: p for p in revision.verification_predicates}
    predicate_id = "modelo-151-base-liquidable-implica-cuota-integra"
    assert predicate_id in predicates, "M151 2015-2022 must declare the base-liquidable advisory"

    guard = predicates[predicate_id]
    assert guard.expression == (
        'implies_nonzero(["impatriado.base-liquidable-general", "impatriado.cuota-integra-general"])'
    )
    assert guard.finding_kind == "ADVISORY", (
        "the guard must stay non-blocking: a legitimately zero cuota must not refuse the draft"
    )
    assert "ley-35-2006:art-93" in tuple(str(r) for r in guard.legal_refs)


def test_modelo_151_2015_2022_cites_no_design_from_a_later_era() -> None:
    """The 2023-and-later design belongs to no surface of the 2015-2022 revision.

    Orden HFP/1338/2023 Disposicion Final Segunda(a) states the successor model
    applies first for ejercicio 2023, which is outside this span, and AEAT names
    the bundled file "01-151-ejercicio-2023-y-siguientes". The revision briefly
    cited that edition alongside its own; the citation was dropped and this pins
    the ruling across every surface it could return through -- a stray re-add
    would otherwise reappear silently in one of them.
    """
    modelo, catalogues = _load_modelo_151()
    revision = modelo.revisions["2015-2022"]

    designs = {
        ref
        for ref in revision.source_refs
        if (source := catalogues.sources.get(ref)) is not None and source.kind == "record_design"
    }
    assert designs == {"aeat-dr-151-2015"}, designs

    later = {
        source.id
        for source in catalogues.sources.values()
        if source.kind == "record_design"
        and source.id.startswith("aeat-dr-151-")
        and source.applies_from is not None
        and source.applies_from.year > 2022
    }
    assert later, "a later-era 151 design must exist for this test to discriminate"

    for casilla in revision.casillas:
        assert not (set(getattr(casilla, "source_refs", ()) or ()) & later), casilla.id
    for workbook in revision.workbook_parity_refs:
        assert workbook.workbook_source not in later
        assert not (set(workbook.source_refs) & later)

    for layout in revision.export_layouts:
        assert not (set(layout.source_refs) & later)
        assert layout.dictionary_source_ref not in later
        for record in layout.records:
            assert not (set(getattr(record, "source_refs", ()) or ()) & later), record
