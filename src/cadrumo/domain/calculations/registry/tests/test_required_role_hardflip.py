"""Tests for semantic-role validator hard-flip and semantic cross-reference accessor.

`required_role_declaration_failures` enforces that casillas
matching any registered label pattern declare the canonical role.
The pattern set covers only corpus-complete label families.

`collect_casillas_by_semantic_role` returns the cross-reference
mapping role -> tuple of (modelo, revision, casilla) for downstream
consumers.
"""

from __future__ import annotations

from datetime import date

import pytest

from .._validate_semantic_role_required import (
    REQUIRED_ROLE_LABEL_PATTERNS,
    collect_casillas_by_semantic_role,
    required_role_declaration_failures,
)
from ..schema import ModeloDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from ..schema_surfaces import CasillaDefinition
from ._synthetic_locale_fixtures import _synthetic_locale_scope, _write_test_label

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

__all__ = ["_synthetic_locale_scope"]


def _casilla(
    *,
    cid: str = "test",
    label: str = "Test",
    data_type: str = "money",
    semantic_role: str | None = None,
) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": cid,
            "number": "01",
            "localization_keys": (_write_test_label(label),),
            "section": ("test",),
            "data_type": data_type,
            "semantic_role": semantic_role,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
        },
    )


def _registry_modelo(modelo_id: str, revision_id: str, casillas: list[CasillaDefinition]) -> ModeloDefinition:
    revision = ModeloRevision.model_validate(
        {
            "id": revision_id,
            "localization_key": f"test.schema.revision.{revision_id}.label",
            "valid_from": date(2025, 1, 1),
            "period_selector": PeriodSelector(years=(2025,), periods=("0A",)),
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": tuple(casillas),
        },
    )
    return ModeloDefinition.model_validate(
        {
            "id": modelo_id,
            "title_localization_key": f"test.schema.modelo.{modelo_id}.title",
            "official_name_localization_key": f"test.schema.modelo.{modelo_id}.official_name",
            "tax_domain": "iva",
            "cadence": "annual",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": {revision_id: revision},
        },
    )


class TestRequiredRoleLabelPatterns:
    def test_pattern_set_is_non_empty(self) -> None:
        assert len(REQUIRED_ROLE_LABEL_PATTERNS) >= 1


class TestRequiredRoleHardflip:
    def test_label_match_with_correct_role_passes(self) -> None:
        c = _casilla(
            label="Ejercicio al que se refiere la declaracion",
            data_type="year",
            semantic_role="filing_year",
        )
        m = _registry_modelo("180", "2023", [c])
        assert required_role_declaration_failures([m]) == ()

    @pytest.mark.parametrize(
        ("label", "semantic_role"),
        (
            ("Base imponible general", "irpf_base_imponible_general"),
            (
                "Base imponible imputada",
                "irpf_re_agrup_interes_economico_base_imponible_imputada",
            ),
        ),
    )
    def test_base_imponible_labels_require_split_roles(self, label: str, semantic_role: str) -> None:
        c = _casilla(label=label, data_type="decimal", semantic_role=semantic_role)
        m = _registry_modelo("100", "2025", [c])
        assert required_role_declaration_failures([m]) == ()

    def test_label_match_without_role_fails(self) -> None:
        c = _casilla(
            label="Ejercicio al que se refiere la declaracion",
            data_type="year",
            semantic_role=None,
        )
        m = _registry_modelo("180", "2023", [c])
        failures = required_role_declaration_failures([m])
        assert len(failures) == 1
        assert "filing_year" in failures[0]
        assert "no semantic_role" in failures[0]

    def test_label_match_with_wrong_role_fails(self) -> None:
        c = _casilla(
            label="Ejercicio al que se refiere la declaracion",
            data_type="year",
            semantic_role="devengo_year",  # close-but-wrong
        )
        m = _registry_modelo("180", "2023", [c])
        failures = required_role_declaration_failures([m])
        assert len(failures) == 1
        assert "devengo_year" in failures[0]
        assert "filing_year" in failures[0]

    def test_unmatched_label_ignored(self) -> None:
        c = _casilla(label="Some other label")
        m = _registry_modelo("180", "2023", [c])
        assert required_role_declaration_failures([m]) == ()


class TestCrossReferenceAccessor:
    def test_role_groups_returned(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        c = _casilla(cid="c", semantic_role="filing_year", data_type="year")
        m1 = _registry_modelo("180", "2023", [a, c])
        m2 = _registry_modelo("184", "2023", [b])
        grouped = collect_casillas_by_semantic_role([m1, m2])
        assert set(grouped.keys()) == {"taxpayer_nif", "filing_year"}
        assert grouped["taxpayer_nif"] == (
            ("180", "2023", "a"),
            ("184", "2023", "b"),
        )
        assert grouped["filing_year"] == (("180", "2023", "c"),)

    def test_unroled_casillas_excluded(self) -> None:
        c = _casilla(cid="c", semantic_role=None)
        m = _registry_modelo("180", "2023", [c])
        assert collect_casillas_by_semantic_role([m]) == {}

    def test_empty_input_returns_empty(self) -> None:
        assert collect_casillas_by_semantic_role([]) == {}
