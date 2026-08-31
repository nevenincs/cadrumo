"""Registry coverage tests for taxpayer-typed rate schedules."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.resources import bundled_path
from ..binding_selector_utils import selector_as_dict
from ..ids import ParameterId
from ..schema_formula import FormulaExpression
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_revision(
    modelo_id: str,
    revision_id: str,
    *,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
):
    modelo, catalogues = _committed_modelo(modelo_id)
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
        revision_id=revision_id,
        grade=grade,
    ).revision


def test_natural_person_route_has_irpf_tarifa_bracket_schedules() -> None:
    """Modelo 100 carries the IRPF bracket tables for a natural person."""

    revision = _modelo_revision("100", "2025")
    parameters = {parameter.id: parameter for parameter in revision.parameters}

    expected = {
        "renta-2025-escala-estatal-base-general": {
            "ley-35-2006:art-62",
            "ley-35-2006:art-63",
        },
        "renta-2025-escala-estatal-base-ahorro": {"ley-35-2006:art-66"},
        "renta-2025-escala-autonomica-base-ahorro": {"ley-35-2006:art-76"},
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
        if formula.id == "renta-2025-cuota-escala-autonomica-sobre-base-liquidable-general"
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
    assert dispatch_table, "autonomic IRPF general scale must dispatch by CCAA"
    for ccaa, parameter_id in dispatch_table.items():
        parameter = parameters[parameter_id]
        assert parameter.data_type == "bracket_table", ccaa
        assert "ley-35-2006:art-74" in parameter.legal_refs, ccaa
        assert parameter.source_refs, ccaa


def test_legal_entity_route_has_is_rate_schedule_by_entity_form() -> None:
    """Modelo 200 carries the LIS Art. 29 rate schedule for legal entities."""

    # The helper asks for filing year 2025, which the 2024/2025 split made a
    # coordinate the 2024 revision no longer covers -- and a revision_id narrows
    # the law-determined pick rather than selecting it, so naming the earlier
    # era here refuses instead of quietly answering from the wrong year.
    revision = _modelo_revision(
        "200",
        "2025-y-siguientes",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
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

    binding = next(
        binding for binding in revision.bindings if binding.id == "modelo-200-2024-profile-legal-entity-form"
    )
    selector = selector_as_dict(binding)
    assert binding.source == "profile"
    assert selector["profile_model"] == "taxpayer"
    assert selector["field"] == "legal_entity_form"
    assert binding.typed_enum == "LegalEntityForm"
    assert "ley-27-2014:art-29" in binding.legal_refs

    dispatch_formula = next(
        formula for formula in revision.formulas if formula.id == "modelo-200-tipo-gravamen-por-forma-juridica"
    )
    assert {"ley-27-2014:art-29", "ley-27-2014:art-30"} <= set(dispatch_formula.legal_refs)
    general_form_dispatch = {
        "sl": "is.modelo-200.tipo-gravamen-general",
        "sa": "is.modelo-200.tipo-gravamen-general",
        "sal": "is.modelo-200.tipo-gravamen-general",
        "sll": "is.modelo-200.tipo-gravamen-general",
        "sociedad_civil_mercantil": "is.modelo-200.tipo-gravamen-general",
        "other": "is.modelo-200.tipo-gravamen-general",
        "cooperativa": "is.modelo-200.tipo-gravamen-cooperative-protected",
        "sin_fines_lucrativos": "is.modelo-200.tipo-gravamen-non-profit-special-regime",
    }
    micro_form_dispatch = {
        **general_form_dispatch,
        "sl": "is.modelo-200.tipo-gravamen-pyme-display",
        "sa": "is.modelo-200.tipo-gravamen-pyme-display",
        "sal": "is.modelo-200.tipo-gravamen-pyme-display",
        "sll": "is.modelo-200.tipo-gravamen-pyme-display",
        "sociedad_civil_mercantil": "is.modelo-200.tipo-gravamen-pyme-display",
        "other": "is.modelo-200.tipo-gravamen-pyme-display",
    }
    erd_form_dispatch = {
        **general_form_dispatch,
        "sl": "is.modelo-200.tipo-gravamen-erd-art101",
        "sa": "is.modelo-200.tipo-gravamen-erd-art101",
        "sal": "is.modelo-200.tipo-gravamen-erd-art101",
        "sll": "is.modelo-200.tipo-gravamen-erd-art101",
        "sociedad_civil_mercantil": "is.modelo-200.tipo-gravamen-erd-art101",
        "other": "is.modelo-200.tipo-gravamen-erd-art101",
    }

    # The formula is a four-lane nested if_then_else:
    # new-entity override -> micro-empresa -> ERD art.101 -> general sub-form.
    # Each lane keeps sal/sll on the legal-entity axis.
    new_entity_dispatch = dispatch_formula.expression.args[1].args[2].dispatch_table
    micro_dispatch = dispatch_formula.expression.args[2].args[1].args[2].dispatch_table
    erd_dispatch = dispatch_formula.expression.args[2].args[2].args[1].args[2].dispatch_table
    general_dispatch = dispatch_formula.expression.args[2].args[2].args[2].args[2].dispatch_table

    assert new_entity_dispatch == {
        key: "is.modelo-200.tipo-gravamen-new-entity-first-2-years" for key in general_form_dispatch
    }
    assert micro_dispatch == micro_form_dispatch
    assert erd_dispatch == erd_form_dispatch
    assert general_dispatch == general_form_dispatch
