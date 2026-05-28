"""Tests for the cross-revision drift validator.

Per the AEAT registry design contract, every casilla id has
identical legal responsibilities across overlapping revisions of a
modelo. The `_validate_cross_revision_casilla_consistency` gate
reports drift when two overlapping revisions disagree on any
legally-bound field (label, section, data_type, semantic_role,
legal_refs). Non-overlapping revision windows are separate legal
forms and require an explicit continuity/evolution contract before
year-to-year drift can be treated as a load-time error.
"""

from __future__ import annotations

import warnings
from datetime import date

import pytest

from aeat.core.resources import bundled_path

from . import load_registry_tree
from ._schema import CasillaDefinition, ModeloDefinition, ModeloRevision, PeriodSelector
from ._validate import (
    RegistryValidator,
)
from ._validate_cross_revision import (
    _validate_cross_revision_casilla_consistency,
    summarize_non_overlapping_cross_revision_casilla_drift,
    validate_cross_revision_casilla_consistency,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _casilla(
    *,
    cid: str = "0001",
    label: str = "Test casilla",
    section: tuple[str, ...] = ("test",),
    data_type: str = "money",
    semantic_role: str | None = None,
    legal_refs: tuple[str, ...] = ("ley-58-2003:art-29",),
    continuidad_id: str | None = None,
) -> CasillaDefinition:
    payload = {
        "id": cid,
        "number": cid,
        "label": label,
        "section": section,
        "data_type": data_type,
        "semantic_role": semantic_role,
        "legal_refs": legal_refs,
        "source_refs": ("aeat-manual",),
    }
    if continuidad_id is not None:
        payload["continuidad_id"] = continuidad_id
    return CasillaDefinition.model_validate(payload)


def _modelo(
    modelo_id: str,
    revs: dict[str, list[CasillaDefinition]],
    selectors: dict[str, PeriodSelector] | None = None,
    evolutions: dict[str, tuple[dict[str, object], ...]] | None = None,
) -> ModeloDefinition:
    revision_payloads: dict[str, ModeloRevision] = {}
    default_selector = PeriodSelector(year_from=2024, periods=("0A",))
    for revision_id, casillas in revs.items():
        revision_year = int(revision_id[:4]) if revision_id[:4].isdigit() else 2024
        revision_payloads[revision_id] = ModeloRevision.model_validate({
            "id": revision_id,
            "valid_from": date(revision_year, 1, 1),
            "period_selector": selectors[revision_id] if selectors is not None else default_selector,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": tuple(casillas),
            "casilla_continuidad_evolutions": () if evolutions is None else evolutions.get(revision_id, ()),
        })
    return ModeloDefinition.model_validate({
        "id": modelo_id,
        "title": f"Modelo {modelo_id}",
        "official_name": f"Modelo {modelo_id}",
        "tax_domain": "test",
        "cadence": "annual",
        "jurisdiction": "ES-AEAT",
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
        "revisions": revision_payloads,
    })


class TestCrossRevisionConsistency:
    def test_identical_casilla_across_revisions_passes(self) -> None:
        a = _casilla(cid="0700", label="Test", data_type="money")
        b = _casilla(cid="0700", label="Test", data_type="money")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        assert _validate_cross_revision_casilla_consistency([m]) == ()

    def test_label_drift_caught(self) -> None:
        a = _casilla(cid="0700", label="Original")
        b = _casilla(cid="0700", label="Different")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert len(failures) == 1
        assert "label" in failures[0]
        assert "0700" in failures[0]

    def test_data_type_drift_caught(self) -> None:
        a = _casilla(cid="0700", data_type="money")
        b = _casilla(cid="0700", data_type="decimal")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert any("data_type" in f for f in failures)

    def test_section_drift_caught(self) -> None:
        a = _casilla(cid="0700", section=("a", "b"))
        b = _casilla(cid="0700", section=("a", "c"))
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert any("section" in f for f in failures)

    def test_semantic_role_drift_caught(self) -> None:
        a = _casilla(cid="0700", semantic_role="taxpayer_nif")
        b = _casilla(cid="0700", semantic_role="payee_nif")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert any("semantic_role" in f for f in failures)

    def test_legal_refs_drift_caught(self) -> None:
        a = _casilla(cid="0700", legal_refs=("ley-58-2003:art-29",))
        b = _casilla(cid="0700", legal_refs=("ley-58-2003:art-30",))
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert any("legal_refs" in f for f in failures)

    def test_single_revision_casilla_passes(self) -> None:
        a = _casilla(cid="0700")
        m = _modelo("100", {"2025": [a]})
        assert _validate_cross_revision_casilla_consistency([m]) == ()

    def test_three_revisions_one_diverges(self) -> None:
        a = _casilla(cid="0700", label="Same")
        b = _casilla(cid="0700", label="Same")
        c = _casilla(cid="0700", label="Different")
        m = _modelo("100", {"2023": [a], "2024": [b], "2025": [c]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert len(failures) == 2
        assert all("2025" in failure for failure in failures)

    def test_two_modelos_independent(self) -> None:
        m100 = _modelo("100", {"2024": [_casilla(cid="0700", label="A")],
                                "2025": [_casilla(cid="0700", label="A")]})
        m180 = _modelo("180", {"2020": [_casilla(cid="0700", label="X")],
                                "2025": [_casilla(cid="0700", label="X")]})
        assert _validate_cross_revision_casilla_consistency([m100, m180]) == ()

    def test_canonical_revision_appears_in_failure_message(self) -> None:
        a = _casilla(cid="0700", label="Old")
        b = _casilla(cid="0700", label="New")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert len(failures) == 1
        assert "2024" in failures[0]
        assert "2025" in failures[0]

    def test_overlapping_period_selectors_still_catch_drift(self) -> None:
        a = _casilla(cid="0700", label="Old")
        b = _casilla(cid="0700", label="New")
        selector = PeriodSelector(year_from=2024, periods=("0A",))
        m = _modelo(
            "100",
            {"2024-a": [a], "2024-b": [b]},
            selectors={"2024-a": selector, "2024-b": selector},
        )

        failures = _validate_cross_revision_casilla_consistency([m])

        assert len(failures) == 1
        assert "label" in failures[0]

    def test_non_overlapping_period_selectors_are_not_cross_revision_drift(self) -> None:
        a = _casilla(cid="0700", label="Old")
        b = _casilla(cid="0700", label="New")
        m = _modelo(
            "100",
            {"2024": [a], "2025": [b]},
            selectors={
                "2024": PeriodSelector(years=(2024,), periods=("0A",)),
                "2025": PeriodSelector(years=(2025,), periods=("0A",)),
            },
        )

        assert _validate_cross_revision_casilla_consistency([m]) == ()

    def test_non_overlapping_period_selectors_are_reported_as_advisory_inventory(self) -> None:
        a = _casilla(cid="0700", label="Old", legal_refs=("ley-58-2003:art-29",))
        b = _casilla(cid="0700", label="New", legal_refs=("ley-58-2003:art-30",))
        m = _modelo(
            "100",
            {"2024": [a], "2025": [b]},
            selectors={
                "2024": PeriodSelector(years=(2024,), periods=("0A",)),
                "2025": PeriodSelector(years=(2025,), periods=("0A",)),
            },
        )

        summaries = summarize_non_overlapping_cross_revision_casilla_drift([m])

        assert {
            (summary.modelo_id, summary.left_revision_id, summary.right_revision_id, summary.field)
            for summary in summaries
        } == {
            ("100", "2024", "2025", "label"),
            ("100", "2024", "2025", "legal_refs"),
        }
        assert all(summary.drift_count == 1 for summary in summaries)
        assert all(summary.example_casilla_ids == ("0700",) for summary in summaries)

    def test_non_overlapping_inventory_reports_covering_continuity_evolution(self) -> None:
        a = _casilla(cid="0700", label="Old", continuidad_id="base")
        b = _casilla(cid="0700", label="New", continuidad_id="base")
        m = _modelo(
            "100",
            {"2024": [a], "2025": [b]},
            selectors={
                "2024": PeriodSelector(years=(2024,), periods=("0A",)),
                "2025": PeriodSelector(years=(2025,), periods=("0A",)),
            },
            evolutions={
                "2025": (
                    {
                        "id": "base-label-2025",
                        "continuidad_id": "base",
                        "from_revision": "2024",
                        "to_revision": "2025",
                        "evolution_kind": "label_evolved",
                        "legal_refs": ("ley-58-2003:art-29",),
                        "source_refs": ("aeat-manual",),
                    },
                )
            },
        )

        summaries = summarize_non_overlapping_cross_revision_casilla_drift([m])

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.field == "label"
        assert summary.continuidad_ids == ("base",)
        assert summary.evolution_kinds == ("label_evolved",)
        assert summary.covered_by_evolution_count == 1
        assert summary.uncovered_count == 0

    def test_non_overlapping_inventory_reports_uncovered_continuity_drift(self) -> None:
        a = _casilla(cid="0700", legal_refs=("ley-58-2003:art-29",), continuidad_id="base")
        b = _casilla(cid="0700", legal_refs=("ley-58-2003:art-30",), continuidad_id="base")
        m = _modelo(
            "100",
            {"2024": [a], "2025": [b]},
            selectors={
                "2024": PeriodSelector(years=(2024,), periods=("0A",)),
                "2025": PeriodSelector(years=(2025,), periods=("0A",)),
            },
            evolutions={
                "2025": (
                    {
                        "id": "base-label-2025",
                        "continuidad_id": "base",
                        "from_revision": "2024",
                        "to_revision": "2025",
                        "evolution_kind": "label_evolved",
                        "legal_refs": ("ley-58-2003:art-29",),
                        "source_refs": ("aeat-manual",),
                    },
                )
            },
        )

        summaries = summarize_non_overlapping_cross_revision_casilla_drift([m])

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.field == "legal_refs"
        assert summary.continuidad_ids == ("base",)
        assert summary.evolution_kinds == ("label_evolved",)
        assert summary.covered_by_evolution_count == 0
        assert summary.uncovered_count == 1

    def test_non_overlapping_inventory_does_not_duplicate_hard_validator_scope(self) -> None:
        selector = PeriodSelector(year_from=2024, periods=("0A",))
        m = _modelo(
            "100",
            {"2024-a": [_casilla(cid="0700", label="Old")], "2024-b": [_casilla(cid="0700", label="New")]},
            selectors={"2024-a": selector, "2024-b": selector},
        )

        assert summarize_non_overlapping_cross_revision_casilla_drift([m]) == ()

    def test_non_overlapping_inventory_requires_positive_example_limit(self) -> None:
        with pytest.raises(ValueError, match="example_limit"):
            summarize_non_overlapping_cross_revision_casilla_drift([], example_limit=0)


def test_cross_revision_validator_accepts_committed_corpus() -> None:
    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))

    validate_cross_revision_casilla_consistency(modelos)


def test_committed_corpus_non_overlapping_inventory_keeps_annual_m100_drift_visible() -> None:
    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))

    summaries = summarize_non_overlapping_cross_revision_casilla_drift(modelos)

    m100_summaries = [summary for summary in summaries if summary.modelo_id == "100"]
    assert m100_summaries
    assert {summary.field for summary in m100_summaries}.issuperset({"label", "legal_refs"})
    assert all(summary.example_casilla_ids for summary in m100_summaries)


def test_backend_registry_validation_accepts_committed_corpus_drift_gate() -> None:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)


def test_singleton_semantic_role_warning_count_does_not_regress() -> None:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)

    singleton_warnings = [
        str(item.message)
        for item in captured
        if "semantic_role" in str(item.message)
        and "appears on exactly one casilla" in str(item.message)
    ]

    # Re-baselined after the 2026-05-20 indexed typo scan and
    # semantic-axis sibling filters. Any new singleton typo warning is
    # now a regression or a missing explicit singleton policy.
    assert len(singleton_warnings) == 0, singleton_warnings[:10]
