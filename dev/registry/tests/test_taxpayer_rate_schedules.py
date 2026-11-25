"""Registry coverage tests for taxpayer-typed rate schedules."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from cadrumo.domain.calculations.registry.ids import ParameterId
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ..conformance.registry_schema_support import committed_modelo
from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _newest_revision(
    modelo_id: str,
    *,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
):
    newest = authored_revisions(modelo_id)[-1]
    modelo, catalogues = committed_modelo(modelo_id)
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=newest.valid_from.year,
        period="0A",
        revision_id=str(newest.id),
        grade=grade,
    ).revision


def test_natural_person_route_has_irpf_tarifa_bracket_schedules() -> None:
    """Modelo 100 carries the IRPF bracket tables for a natural person."""

    revision = _newest_revision("100")
    parameters = {parameter.id: parameter for parameter in revision.parameters}

    expected = {
        "renta-escala-estatal-base-general": {
            "ley-35-2006:art-62",
            "ley-35-2006:art-63",
        },
        "renta-escala-estatal-base-ahorro": {"ley-35-2006:art-66"},
        "renta-escala-autonomica-base-ahorro": {"ley-35-2006:art-76"},
    }
    for parameter_id, legal_refs in expected.items():
        parameter = parameters[parameter_id]
        assert parameter.data_type == "bracket_table", parameter_id
        assert parameter.bracket_axis == "filing_period", parameter_id
        assert legal_refs <= set(parameter.legal_refs), parameter_id
        assert parameter.source_refs, parameter_id
        assert parameter.brackets, parameter_id

    autonomic_formula = next(
        formula
        for formula in revision.formulas
        if formula.id == "renta-cuota-escala-autonomica-sobre-base-liquidable-general"
    )

    # From 2024/2025 the autonomic escala formula wraps its lookup_bracket_by_ccaa
    # operators in the LIRPF art. 64/75 anualidades separate-escala if_then_else
    # predicate, so the dispatch table is no longer at the top level.
    def _first_ccaa_dispatch_table(expression: FormulaExpression) -> Mapping[str, ParameterId] | None:
        if expression.op == "lookup_bracket_by_ccaa":
            return expression.args[2].dispatch_table
        for arg in expression.args:
            found = _first_ccaa_dispatch_table(arg)
            if found is not None:
                return found
        return None

    dispatch_table = _first_ccaa_dispatch_table(autonomic_formula.expression)
    assert dispatch_table is not None and dispatch_table, "autonomic IRPF general scale must dispatch by CCAA"
    # A scale a comunidad approved is grounded in LIRPF art. 74. A residence whose
    # autonomic scale the law fixes instead -- the two ciudades autónomas, sent by
    # disposición adicional trigésima segunda to the art. 65 table -- is grounded in
    # that pair. Every dispatched parameter must carry one of the two groundings, so
    # a scale with neither is still reported.
    approved_by_a_comunidad = {"ley-35-2006:art-74"}
    fixed_by_the_law = {"ley-35-2006:da-32", "ley-35-2006:art-65"}
    for ccaa, parameter_id in dispatch_table.items():
        parameter = parameters[parameter_id]
        declared = set(parameter.legal_refs)
        assert parameter.data_type == "bracket_table", ccaa
        assert approved_by_a_comunidad <= declared or fixed_by_the_law <= declared, ccaa
        assert parameter.source_refs, ccaa


def test_legal_entity_route_has_is_rate_schedule_by_entity_form() -> None:
    """Modelo 200 carries the LIS Art. 29 rate schedule for legal entities."""

    # A revision_id narrows the law-determined pick rather than selecting it, so
    # the filing year must be one the named revision covers: the helper asks for
    # the newest edition's own first exercise, never an earlier era's.
    revision = _newest_revision("200", grade=RegistryAuthorityGrade.CALCULATION)
    parameters = {parameter.id: parameter for parameter in revision.parameters}

    scalar_rates = {
        "is.modelo-200.tipo-gravamen-general",
        "is.modelo-200.tipo-gravamen-pyme-display",
        "is.modelo-200.tipo-gravamen-erd-art101",
        "is.modelo-200.tipo-gravamen-new-entity-first-2-years",
        "is.modelo-200.tipo-gravamen-cooperative-protected",
        "is.modelo-200.tipo-gravamen-non-profit-special-regime",
    }
    for parameter_id in scalar_rates:
        parameter = parameters[parameter_id]
        assert parameter.data_type == "ratio", parameter_id
        assert parameter.values, parameter_id
        assert "ley-27-2014:art-29" in parameter.legal_refs, parameter_id
        assert parameter.source_refs, parameter_id

    micro_empresa = parameters["is.modelo-200.tipo-gravamen-pyme"]
    assert micro_empresa.data_type == "bracket_table"
    assert micro_empresa.brackets
    assert "ley-27-2014:art-29" in micro_empresa.legal_refs
    assert micro_empresa.source_refs

    binding = next(binding for binding in revision.bindings if binding.id == "modelo-200-profile-legal-entity-form")
    selector = selector_as_dict(binding)
    assert binding.source == "profile"
    assert selector["profile_model"] == "taxpayer"
    assert selector["field"] == "legal_entity_form"
    assert binding.value.typed_enum == "LegalEntityForm"
    assert "ley-27-2014:art-29" in binding.legal_refs

    dispatch_formula = next(
        formula for formula in revision.formulas if formula.id == "modelo-200-tipo-gravamen-por-forma-juridica"
    )
    assert {"ley-27-2014:art-29", "ley-27-2014:art-30"} <= set(dispatch_formula.legal_refs)
    # The rate is chosen by the legal entity form, the new-entity flag and the
    # INCN of the preceding período impositivo (LIS art. 29.1 and art. 101), in
    # whatever lane order the edition's design
    # sets; the per-lane rates are proved by evaluation in the cuota-integra lane
    # tests. Here the formula must reach every LIS art. 29 rate and both INCN
    # thresholds, read each axis, and keep sal and sll on the legal-entity axis.
    nodes = tuple(_expression_nodes(dispatch_formula.expression))
    reached = {str(node.parameter) for node in nodes if node.parameter is not None}
    reached |= {
        str(parameter)
        for node in nodes
        if node.dispatch_table is not None
        for parameter in node.dispatch_table.values()
    }
    assert scalar_rates | {"is.modelo-200.incn-umbral-microempresa", "is.modelo-200.incn-umbral-erd-art101"} <= reached
    read = {str(node.binding) for node in nodes if node.binding is not None}
    assert {
        "modelo-200-profile-legal-entity-form",
        "modelo-200-profile-new-entity-flag",
        "modelo-200-incn-periodo-impositivo-anterior",
    } <= read
    form_binding = "modelo-200-profile-legal-entity-form"
    compared = (node.args for node in nodes if any(str(argument.binding) == form_binding for argument in node.args))
    forms = {str(argument.text_literal) for args in compared for argument in args if argument.text_literal is not None}
    forms |= {key for node in nodes if node.dispatch_table is not None for key in node.dispatch_table}
    assert {"sl", "sa", "sal", "sll", "cooperativa", "sociedad_civil_mercantil", "other"} <= forms


def _expression_nodes(expression: FormulaExpression) -> Iterator[FormulaExpression]:
    """Every node of one formula expression, depth first."""
    yield expression
    for argument in expression.args:
        yield from _expression_nodes(argument)
