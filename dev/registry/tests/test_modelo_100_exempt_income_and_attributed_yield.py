"""Modelo 100 keeps plain exemptions out of box 0525 and leaves box 1577 to the member.

Box 0525 carries the exempt income that still sets the tax rate (rentas exentas
con progresividad, DA 20.ª LIRPF): the 2025 input dictionary files it under
"Rentas exentas, excepto para determinar el tipo de gravamen" and the 2025
manual, cap. 15, names treaty-exempt income as that class. The maritime
exemptions of art. 7.p) LIRPF and Ley 19/1994 art. 75 are plain exemptions, so
their amount lands on an internal node that files in no box.

Box 1577 is the member's share of an entity's net activity yield (LIRPF art.
89); the 2025 manual's comunidad de bienes example has comunero Y declare
15.000 of the entity's 30.000. Modelo 184 files the entity's type-2 records for
every member and income class, and a relation prefill carries no member or
class filter, so no edition folds Modelo 184 into Modelo 100.
"""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from cadrumo.domain.calculations.registry.runtime_graph import expression_binding_refs
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ._modelo_100_registry_support import _loaded_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RENTAS_EXENTAS_CON_PROGRESIVIDAD = validated_casilla_id("0525", surface="test_modelo_100_exempt_income")
_MEMBER_ATTRIBUTED_YIELD = validated_casilla_id("1577", surface="test_modelo_100_exempt_income")
_MARITIME_PATH_BINDING = "renta-maritime-path-rebeca"


def _editions() -> tuple[ModeloRevision, ...]:
    return tuple(_loaded_registry()[0]["100"].revisions.values())


def _casilla(revision: ModeloRevision, casilla_id: str) -> CasillaDefinition:
    (casilla,) = (casilla for casilla in revision.casillas if casilla.id == casilla_id)
    return casilla


def test_box_0525_stays_a_declared_input_in_every_edition() -> None:
    for revision in _editions():
        casilla = _casilla(revision, _RENTAS_EXENTAS_CON_PROGRESIVIDAD)

        assert casilla.input_kind == InputKind.MANUAL, revision.id
        assert casilla.formula is None, revision.id
        assert all(formula.target_casilla_id != casilla.id for formula in revision.formulas), revision.id


def test_the_maritime_exemption_lands_on_an_internal_node_that_files_nowhere() -> None:
    maritime_editions = 0
    for revision in _editions():
        manifest = revision.completeness_manifest
        manifest_ids = {entry.casilla_id for entry in manifest.casillas} if manifest is not None else set()
        for formula in revision.formulas:
            if _MARITIME_PATH_BINDING not in expression_binding_refs(formula.expression):
                continue
            maritime_editions += 1
            target = _casilla(revision, formula.target_casilla_id)

            assert target.internal_only, (revision.id, target.id)
            assert target.id not in manifest_ids, (revision.id, target.id)
    assert maritime_editions, "no edition computes the maritime exemption, so nothing was checked"


def test_no_edition_folds_modelo_184_into_modelo_100() -> None:
    for revision in _editions():
        folds_from_184 = [
            binding.id
            for binding in revision.bindings
            if isinstance(binding.provider, RelationPrefillProvider) and str(binding.provider.source_modelo) == "184"
        ]
        member_share = _casilla(revision, _MEMBER_ATTRIBUTED_YIELD)

        assert folds_from_184 == [], revision.id
        assert member_share.binding is None, revision.id
        assert member_share.input_kind != InputKind.BOUND, revision.id
        for classification in revision.dependency_classifications:
            if str(classification.source_modelo) == "184":
                assert classification.treatment == "factual_evidence", (revision.id, classification.id)
                assert classification.binding_refs == (), (revision.id, classification.id)
