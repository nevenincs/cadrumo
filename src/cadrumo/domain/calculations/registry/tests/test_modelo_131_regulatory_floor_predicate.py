"""Regression coverage for the Modelo 131 regulatory-floor predicate."""

from __future__ import annotations

from functools import cache

import pytest

from .....core.corpus_text import normalise_corpus_text
from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from ..schema import ModeloDefinition, RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PREDICATE_IDS = {
    "2019-2023": "modelo-131-2019-2023-pago-fraccionado-determinado-cuando-rendimientos-positivos",
    "2024": "modelo-131-2024-pago-fraccionado-determinado-cuando-rendimientos-positivos",
    "2025": "modelo-131-2025-pago-fraccionado-determinado-cuando-rendimientos-positivos",
    "2026": "modelo-131-2026-pago-fraccionado-determinado-cuando-rendimientos-positivos",
}
_EXPECTED_EXPRESSION = 'implies_nonzero(["01", "02"])'
_ROLLED_BACK_EXPRESSION = 'implies_nonzero(["01", "07"])'
_RD_439_ART_110 = "rd-439-2007:art-110"
_ORDEN_EHA_672_ART_3 = "orden-eha-672-2007:art-3"
_M131_INSTRUCTIONS_SOURCE = "aeat-modelo-131-instructions"


@cache
def _committed_modelo_131() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = bundled_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == "131"), catalogues


@pytest.mark.parametrize("revision_id", sorted(_PREDICATE_IDS))
def test_modelo_131_regulatory_floor_predicates_use_data_base_lane(revision_id: str) -> None:
    modelo, _catalogues = _committed_modelo_131()
    revision = modelo.revisions[revision_id]
    predicates = {predicate.predicate_id: predicate for predicate in revision.verification_predicates}

    predicate = predicates[_PREDICATE_IDS[revision_id]]
    assert predicate.expression == _EXPECTED_EXPRESSION
    assert predicate.finding_kind == "ADVISORY"
    assert _RD_439_ART_110 in tuple(str(ref) for ref in predicate.legal_refs)
    assert _ROLLED_BACK_EXPRESSION not in {p.expression for p in revision.verification_predicates}

    c07_formula = next(formula for formula in revision.formulas if formula.target_casilla_id == "07")
    c07_inputs = tuple(str(arg.casilla_id) for arg in c07_formula.expression.args)
    assert c07_formula.expression.op == "add"
    assert c07_inputs == ("02", "04", "06")
    assert "01" not in c07_inputs


@pytest.mark.parametrize("revision_id", sorted(_PREDICATE_IDS))
def test_modelo_131_regulatory_floor_predicates_carry_revision_evidence(revision_id: str) -> None:
    modelo, catalogues = _committed_modelo_131()
    revision = modelo.revisions[revision_id]
    verification_id = f"modelo-131-{revision_id}-calculation-verification"
    verification = next(item for item in revision.verification_expectations if item.id == verification_id)

    assert _ORDEN_EHA_672_ART_3 in tuple(str(ref) for ref in revision.legal_refs)
    assert _M131_INSTRUCTIONS_SOURCE in tuple(str(ref) for ref in revision.source_refs)
    assert _M131_INSTRUCTIONS_SOURCE in tuple(str(ref) for ref in verification.source_refs)

    assert _RD_439_ART_110 in catalogues.legal
    assert _ORDEN_EHA_672_ART_3 in catalogues.legal
    assert _M131_INSTRUCTIONS_SOURCE in catalogues.sources


def test_modelo_131_regulatory_floor_predicate_has_bundled_corpus_evidence() -> None:
    _modelo, catalogues = _committed_modelo_131()

    art_110 = catalogues.legal[_RD_439_ART_110]
    assert art_110.evidence_tier == "legal_authority"
    assert art_110.corpus_ref == "corpus/normatives/html/rd-439-2007-art-110.html#a110"
    art_110_text = normalise_corpus_text((bundled_path() / art_110.corpus_ref.split("#", 1)[0]).read_text("utf-8"))
    for required_text in (
        "el 4 por ciento de los rendimientos netos",
        "el porcentaje anterior sera el 3 por ciento",
        "no disponga de personal asalariado dicho porcentaje sera el 2 por ciento",
        "Los contribuyentes podran aplicar en cada uno de los pagos fraccionados porcentajes superiores",
    ):
        assert normalise_corpus_text(required_text) in art_110_text

    order_art_3 = catalogues.legal[_ORDEN_EHA_672_ART_3]
    order_text = normalise_corpus_text((bundled_path() / order_art_3.corpus_ref.split("#", 1)[0]).read_text("utf-8"))
    for required_text in order_art_3.required_text:
        assert normalise_corpus_text(required_text) in order_text

    instructions = catalogues.sources[_M131_INSTRUCTIONS_SOURCE]
    assert instructions.evidence_tier == "official_source_guidance"
    instructions_text = normalise_corpus_text((bundled_path() / instructions.corpus_path).read_text("utf-8"))
    for required_text in (
        "Casilla 01",
        "suma de los rendimientos netos",
        "Casilla 02",
        "Pago Fraccionado del trimestre",
        "el 2 por 100",
        "el 3 por 100",
        "el 4 por 100",
        "no se permiten porcentajes inferiores",
        "Casilla 07",
        "casillas 02, 04 y 06",
    ):
        assert normalise_corpus_text(required_text) in instructions_text
