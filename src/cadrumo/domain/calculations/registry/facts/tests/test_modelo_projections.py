"""Focused tests for non-duplicating modelo parameter projections."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ......core.revision_review import RevisionReviewStatus
from ...schema import ModeloDefinition
from ...schema_base import DateAxis
from ...schema_formula import ParameterDefinition
from ..modelo_projections import (
    MODELO_PARAMETER_PROJECTION_PROVIDER_ID,
    ModeloParameterFact,
    compile_modelo_parameter_projection_facts,
)
from ..providers import FACT_PROVIDER_REGISTRATIONS
from ..resolution import ScalarFactQuery
from ..schema import FactSelector, ScalarFactPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _parameter(parameter_id: str, value: str, *, valid_from: date, valid_to: date | None = None) -> ParameterDefinition:
    return ParameterDefinition.model_validate(
        {
            "id": parameter_id,
            "data_type": "money",
            "unit": "EUR",
            "legal_refs": ("ley-35-2006:art-81",),
            "source_refs": ("aeat-renta-2025-manual-parte1",),
            "source_citations": (
                {"source_ref": "aeat-renta-2025-manual-parte1", "required_text": ("deducción por maternidad",)},
            ),
            "values": (
                {
                    "value": value,
                    "date_axis": "filing_period",
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                },
            ),
        },
    )


def test_query_contract_names_exact_modelo_parameter_coordinates() -> None:
    query = ScalarFactQuery(
        fact_id=ModeloParameterFact.MATERNITY_ANNUAL_CAP,
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=date(2025, 12, 31),
        selectors=(
            FactSelector(name="modelo", value="100"),
            FactSelector(name="parameter_id", value="renta-2025-maternidad-cap-anual"),
        ),
    )

    assert query.fact_id == "renta.maternity.annual-cap"
    assert {(selector.name, selector.value) for selector in query.selectors} == {
        ("modelo", "100"),
        ("parameter_id", "renta-2025-maternidad-cap-anual"),
    }


def test_projection_provider_is_registered_without_claiming_modelo_file_ownership() -> None:
    registration = next(
        item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == MODELO_PARAMETER_PROJECTION_PROVIDER_ID
    )

    assert registration.owned_directories == ()
    assert registration.project_modelos is compile_modelo_parameter_projection_facts


def test_projection_preserves_scalar_temporal_and_provenance_contracts() -> None:
    modelos = (_modelo_100(), _modelo_347())
    facts = {fact.fact_id: fact for fact in compile_modelo_parameter_projection_facts(modelos)}
    variant = facts[ModeloParameterFact.MATERNITY_ANNUAL_CAP].variants[0]

    assert isinstance(variant.payload, ScalarFactPayload)
    assert variant.payload.value == Decimal("1200")
    assert variant.payload.unit == "EUR"
    assert variant.valid_from == date(2025, 1, 1)
    assert variant.valid_to == date(2025, 12, 31)
    assert variant.legal_refs == ("ley-35-2006:art-81",)
    assert variant.source_refs == ("aeat-renta-2025-manual-parte1",)
    assert variant.source_citations
    assert variant.ownership.value == "generated"


def test_identical_parameter_copies_across_revisions_project_once() -> None:
    facts = compile_modelo_parameter_projection_facts((_modelo_100(), _modelo_347()))
    threshold = next(fact for fact in facts if fact.fact_id == ModeloParameterFact.M347_COUNTERPARTY_ANNUAL_THRESHOLD)

    assert len(threshold.variants) == 1
    assert isinstance(threshold.variants[0].payload, ScalarFactPayload)
    assert threshold.variants[0].payload.value == Decimal("3005.06")


def _modelo_100() -> ModeloDefinition:
    parameters = (
        _parameter("renta-2025-maternidad-mensual", "100", valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31)),
        _parameter("renta-2025-maternidad-cap-anual", "1200", valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31)),
        _parameter(
            "renta-2025-maternidad-alta-posterior-incremento",
            "150",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
        ),
    )
    return _modelo("100", {"2025": _revision("2025", parameters)})


def _modelo_347() -> ModeloDefinition:
    parameter = _parameter("modelo-347-tercero-anual-threshold-eur", "3005.06", valid_from=date(2008, 1, 1))
    return _modelo(
        "347",
        {
            "2011-2024": _revision("2011-2024", (parameter,)),
            "2025-y-siguientes": _revision("2025-y-siguientes", (parameter,)),
        },
    )


def _revision(revision_id: str, parameters: tuple[ParameterDefinition, ...]) -> object:
    from types import SimpleNamespace

    return SimpleNamespace(id=revision_id, parameters=parameters, review_status=RevisionReviewStatus.AGENT_REVIEWED)


def _modelo(modelo_id: str, revisions: dict[str, object]) -> ModeloDefinition:
    from types import SimpleNamespace
    from typing import cast

    return cast("ModeloDefinition", SimpleNamespace(id=modelo_id, revisions=revisions))
