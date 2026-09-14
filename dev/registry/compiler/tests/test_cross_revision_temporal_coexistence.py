"""Regression tests for temporal coexistence in cross-revision consistency."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..validate_cross_revision import (
    cross_revision_casilla_consistency_failures,
    strict_cross_revision_casilla_continuity_failures,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla(*, data_type: str, continuidad_id: str | None = None) -> CasillaDefinition:
    payload: dict[str, object] = {
        "id": "0001",
        "number": "0001",
        "localization_keys": ("test.registry.casilla.label",),
        "section": ("test",),
        "data_type": data_type,
        "semantic_role": "test_value",
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
    }
    if continuidad_id is not None:
        payload["continuidad_id"] = continuidad_id
    return CasillaDefinition.model_validate(payload)


def _revision(
    revision_id: str,
    *,
    valid_from: date,
    valid_to: date | None,
    casilla: CasillaDefinition,
    strict: bool = False,
) -> ModeloRevision:
    return ModeloRevision.model_validate(
        {
            "id": revision_id,
            "localization_key": f"test.registry.revision.{revision_id}.label",
            "valid_from": valid_from,
            "valid_to": valid_to,
            "period_selector": PeriodSelector(years=(2025,), periods=("alta",)),
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": (casilla,),
            "continuidad_validation": "strict" if strict else "advisory",
        },
    )


def _modelo(left: ModeloRevision, right: ModeloRevision) -> ModeloDefinition:
    return ModeloDefinition.model_validate(
        {
            "id": "036",
            "title_localization_key": "test.registry.modelo.title",
            "official_name_localization_key": "test.registry.modelo.official_name",
            "tax_domain": "censo",
            "cadence": "ad_hoc",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": {left.id: left, right.id: right},
        },
    )


def test_shared_filing_coordinate_across_disjoint_date_windows_is_not_simultaneous_drift() -> None:
    modelo = _modelo(
        _revision(
            "before-cutover",
            valid_from=date(2023, 1, 1),
            valid_to=date(2025, 2, 2),
            casilla=_casilla(data_type="money"),
        ),
        _revision(
            "after-cutover",
            valid_from=date(2025, 2, 3),
            valid_to=None,
            casilla=_casilla(data_type="decimal"),
        ),
    )

    assert cross_revision_casilla_consistency_failures((modelo,)) == ()


def test_shared_filing_coordinate_with_intersecting_date_windows_still_fails() -> None:
    modelo = _modelo(
        _revision(
            "variant-a",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
            casilla=_casilla(data_type="money"),
        ),
        _revision(
            "variant-b",
            valid_from=date(2025, 2, 3),
            valid_to=None,
            casilla=_casilla(data_type="decimal"),
        ),
    )

    failures = cross_revision_casilla_consistency_failures((modelo,))

    assert len(failures) == 1
    assert "data_type" in failures[0]


def test_disjoint_date_windows_remain_subject_to_strict_successive_continuity() -> None:
    modelo = _modelo(
        _revision(
            "before-cutover",
            valid_from=date(2023, 1, 1),
            valid_to=date(2025, 2, 2),
            casilla=_casilla(data_type="money", continuidad_id="test-value"),
        ),
        _revision(
            "after-cutover",
            valid_from=date(2025, 2, 3),
            valid_to=None,
            casilla=_casilla(data_type="decimal", continuidad_id="test-value"),
            strict=True,
        ),
    )

    failures = strict_cross_revision_casilla_continuity_failures((modelo,))

    assert len(failures) == 1
    assert "strict continuity drift" in failures[0]
    assert "data_type" in failures[0]
