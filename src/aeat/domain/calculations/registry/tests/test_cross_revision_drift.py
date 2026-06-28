"""Tests for the cross-revision drift validator.

Per the AEAT registry design contract, every casilla id has
identical legal responsibilities across overlapping revisions of a
modelo. The public `validate_cross_revision_casilla_consistency` gate
reports drift when two overlapping revisions disagree on any
legally-bound field (label, section, data_type, semantic_role,
legal_refs). Non-overlapping revision windows are separate legal
forms and require an explicit continuity/evolution contract before
year-to-year drift can be treated as a load-time error.
"""

from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import load_modelo_directory, load_registry_tree
from .._errors import RegistryValidationError
from .._schema import (
    CasillaDefinition,
    ModeloDefinition,
    ModeloRevision,
    PeriodSelector,
    RegistryCatalogues,
)
from .._validate import (
    RegistryValidator,
)
from .._validate_cross_revision import (
    summarize_non_overlapping_cross_revision_casilla_drift,
    validate_cross_revision_casilla_consistency,
)
from .._validate_registry_scope import validate_registry_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
    continuidad_validation: dict[str, str] | None = None,
) -> ModeloDefinition:
    revision_payloads: dict[str, ModeloRevision] = {}
    default_selector = PeriodSelector(year_from=2024, periods=("0A",))
    for revision_id, casillas in revs.items():
        revision_year = int(revision_id[:4]) if revision_id[:4].isdigit() else 2024
        revision_payloads[revision_id] = ModeloRevision.model_validate(
            {
                "id": revision_id,
                "valid_from": date(revision_year, 1, 1),
                "period_selector": selectors[revision_id] if selectors is not None else default_selector,
                "legal_refs": ("ley-58-2003:art-29",),
                "source_refs": ("aeat-manual",),
                "casillas": tuple(casillas),
                "continuidad_validation": (
                    "advisory"
                    if continuidad_validation is None
                    else continuidad_validation.get(revision_id, "advisory")
                ),
                "casilla_continuidad_evolutions": () if evolutions is None else evolutions.get(revision_id, ()),
            },
        )
    return ModeloDefinition.model_validate(
        {
            "id": modelo_id,
            "title": f"Modelo {modelo_id}",
            "official_name": f"Modelo {modelo_id}",
            "tax_domain": "iva",
            "cadence": "annual",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": revision_payloads,
        },
    )


def _annual_revision_selectors() -> dict[str, PeriodSelector]:
    return {
        "2024": PeriodSelector(years=(2024,), periods=("0A",)),
        "2025": PeriodSelector(years=(2025,), periods=("0A",)),
    }


def _annual_modelo(
    left: CasillaDefinition,
    right: CasillaDefinition,
    *,
    evolutions: dict[str, tuple[dict[str, object], ...]] | None = None,
    continuidad_validation: dict[str, str] | None = None,
) -> ModeloDefinition:
    return _modelo(
        "100",
        {"2024": [left], "2025": [right]},
        selectors=_annual_revision_selectors(),
        evolutions=evolutions,
        continuidad_validation=continuidad_validation,
    )


def _continuity_evolution(
    *,
    evolution_kind: str = "label_evolved",
    continuidad_id: str = "base",
    evolution_id: str | None = None,
) -> dict[str, object]:
    return {
        "id": evolution_id or f"{continuidad_id}-{evolution_kind}-2025",
        "continuidad_id": continuidad_id,
        "from_revision": "2024",
        "to_revision": "2025",
        "evolution_kind": evolution_kind,
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
    }


def _evolutions(*payloads: dict[str, object]) -> dict[str, tuple[dict[str, object], ...]]:
    return {"2025": payloads}


@pytest.fixture(scope="module")
def committed_registry() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return load_registry_tree(bundled_path("registry", "aeat"))


@pytest.fixture(scope="module")
def committed_m100(committed_registry: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]) -> ModeloDefinition:
    modelos, _catalogues = committed_registry
    return next(modelo for modelo in modelos if modelo.id == "100")


def _evolution_pairs(modelo: ModeloDefinition, continuidad_id: str) -> dict[tuple[str, str], str]:
    return {
        (evolution.from_revision, evolution.to_revision): evolution.evolution_kind
        for revision in modelo.revisions.values()
        for evolution in revision.casilla_continuidad_evolutions
        if evolution.continuidad_id == continuidad_id
    }


def _cross_revision_casilla_consistency_failures(modelos: list[ModeloDefinition]) -> tuple[str, ...]:
    try:
        validate_cross_revision_casilla_consistency(modelos)
    except RegistryValidationError as exc:
        message = str(exc)
        prefix = "cross-revision casilla drift detected:\n"
        assert message.startswith(prefix), message
        return tuple(line.removeprefix(" - ") for line in message.removeprefix(prefix).splitlines())
    return ()


def _write_continuity_modelo_directory(
    tmp_path: Path,
    *,
    strict: bool,
    include_evolution: bool,
) -> Path:
    target = tmp_path / "999"
    revisions_dir = target / "revisions"
    revisions_dir.mkdir(parents=True)
    (target / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Continuity test"
official_name = "Continuity test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (revisions_dir / "2024.toml").write_text(
        """
[revisions."2024"]
valid_from = 2024-01-01
period_selector = { years = [2024], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2024".casillas]]
id = "0700"
number = "700"
label = "Old base"
section = ["test"]
data_type = "money"
continuidad_id = "base"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    strict_line = 'continuidad_validation = "strict"\n' if strict else ""
    evolution_block = (
        """

[[revisions."2025".casilla_continuidad_evolutions]]
id = "base-label-2025"
continuidad_id = "base"
from_revision = "2024"
to_revision = "2025"
evolution_kind = "label_evolved"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".rstrip()
        if include_evolution
        else ""
    )
    (revisions_dir / "2025.toml").write_text(
        f"""
[revisions."2025"]
valid_from = 2025-01-01
period_selector = {{ years = [2025], periods = ["0A"] }}
{strict_line}legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "0700"
number = "700"
label = "New base"
section = ["test"]
data_type = "money"
continuidad_id = "base"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
{evolution_block}
""".lstrip(),
        encoding="utf-8",
    )
    return target


class TestCrossRevisionConsistency:
    def test_identical_casilla_across_revisions_passes(self) -> None:
        a = _casilla(cid="0700", label="Test", data_type="money")
        b = _casilla(cid="0700", label="Test", data_type="money")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        assert _cross_revision_casilla_consistency_failures([m]) == ()

    def test_label_drift_caught(self) -> None:
        a = _casilla(cid="0700", label="Original")
        b = _casilla(cid="0700", label="Different")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _cross_revision_casilla_consistency_failures([m])
        assert len(failures) == 1
        assert "label" in failures[0]
        assert "0700" in failures[0]

    def test_data_type_drift_caught(self) -> None:
        a = _casilla(cid="0700", data_type="money")
        b = _casilla(cid="0700", data_type="decimal")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _cross_revision_casilla_consistency_failures([m])
        assert any("data_type" in f for f in failures)

    def test_section_drift_caught(self) -> None:
        a = _casilla(cid="0700", section=("a", "b"))
        b = _casilla(cid="0700", section=("a", "c"))
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _cross_revision_casilla_consistency_failures([m])
        assert any("section" in f for f in failures)

    def test_semantic_role_drift_caught(self) -> None:
        a = _casilla(cid="0700", semantic_role="taxpayer_nif")
        b = _casilla(cid="0700", semantic_role="payee_nif")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _cross_revision_casilla_consistency_failures([m])
        assert any("semantic_role" in f for f in failures)

    def test_legal_refs_drift_caught(self) -> None:
        a = _casilla(cid="0700", legal_refs=("ley-58-2003:art-29",))
        b = _casilla(cid="0700", legal_refs=("ley-58-2003:art-30",))
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _cross_revision_casilla_consistency_failures([m])
        assert any("legal_refs" in f for f in failures)

    def test_single_revision_casilla_passes(self) -> None:
        a = _casilla(cid="0700")
        m = _modelo("100", {"2025": [a]})
        assert _cross_revision_casilla_consistency_failures([m]) == ()

    def test_three_revisions_one_diverges(self) -> None:
        a = _casilla(cid="0700", label="Same")
        b = _casilla(cid="0700", label="Same")
        c = _casilla(cid="0700", label="Different")
        m = _modelo("100", {"2023": [a], "2024": [b], "2025": [c]})
        failures = _cross_revision_casilla_consistency_failures([m])
        assert len(failures) == 2
        assert all("2025" in failure for failure in failures)

    def test_two_modelos_independent(self) -> None:
        m100 = _modelo("100", {"2024": [_casilla(cid="0700", label="A")], "2025": [_casilla(cid="0700", label="A")]})
        m180 = _modelo("180", {"2020": [_casilla(cid="0700", label="X")], "2025": [_casilla(cid="0700", label="X")]})
        assert _cross_revision_casilla_consistency_failures([m100, m180]) == ()

    def test_canonical_revision_appears_in_failure_message(self) -> None:
        a = _casilla(cid="0700", label="Old")
        b = _casilla(cid="0700", label="New")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _cross_revision_casilla_consistency_failures([m])
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

        failures = _cross_revision_casilla_consistency_failures([m])

        assert len(failures) == 1
        assert "label" in failures[0]

    def test_non_overlapping_period_selectors_are_not_cross_revision_drift(self) -> None:
        a = _casilla(cid="0700", label="Old")
        b = _casilla(cid="0700", label="New")
        m = _annual_modelo(a, b)

        assert _cross_revision_casilla_consistency_failures([m]) == ()

    def test_non_overlapping_period_selectors_are_reported_as_advisory_inventory(self) -> None:
        a = _casilla(cid="0700", label="Old", legal_refs=("ley-58-2003:art-29",))
        b = _casilla(cid="0700", label="New", legal_refs=("ley-58-2003:art-30",))
        m = _annual_modelo(a, b)

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
        m = _annual_modelo(a, b, evolutions=_evolutions(_continuity_evolution(evolution_id="base-label-2025")))

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
        m = _annual_modelo(a, b, evolutions=_evolutions(_continuity_evolution(evolution_id="base-label-2025")))

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

    def test_advisory_continuity_validation_does_not_fail_non_overlapping_drift(self) -> None:
        a = _casilla(cid="0700", label="Old")
        b = _casilla(cid="0700", label="New")
        m = _annual_modelo(a, b)

        assert validate_registry_scope([m]) == ()

    def test_strict_continuity_validation_fails_uncovered_non_overlapping_drift(self) -> None:
        a = _casilla(cid="0700", label="Old", continuidad_id="base")
        b = _casilla(cid="0700", label="New", continuidad_id="base")
        m = _annual_modelo(a, b, continuidad_validation={"2025": "strict"})

        failures = validate_registry_scope([m])

        assert len(failures) == 1
        assert "strict continuity drift" in failures[0]
        assert "label" in failures[0]
        assert "0700" in failures[0]

    def test_strict_continuity_validation_ignores_unannotated_advisory_surface(self) -> None:
        a = _casilla(cid="0700", label="Old")
        b = _casilla(cid="0700", label="New")
        m = _annual_modelo(a, b, continuidad_validation={"2025": "strict"})

        assert validate_registry_scope([m]) == ()

    def test_strict_continuity_validation_accepts_covered_non_overlapping_drift(self) -> None:
        a = _casilla(cid="0700", label="Old", continuidad_id="base")
        b = _casilla(cid="0700", label="New", continuidad_id="base")
        m = _annual_modelo(
            a,
            b,
            evolutions=_evolutions(_continuity_evolution(evolution_id="base-label-2025")),
            continuidad_validation={"2025": "strict"},
        )

        assert validate_registry_scope([m]) == ()

    def test_strict_continuity_validation_accepts_repurposed_decision(self) -> None:
        a = _casilla(
            cid="0700",
            label="Old base",
            section=("old",),
            data_type="money",
            semantic_role="total_tax_due",
            legal_refs=("ley-58-2003:art-29",),
            continuidad_id="base",
        )
        b = _casilla(
            cid="0700",
            label="New base",
            section=("new",),
            data_type="decimal",
            semantic_role="prior_period_tax_due",
            legal_refs=("ley-58-2003:art-30",),
            continuidad_id="base",
        )
        m = _annual_modelo(
            a,
            b,
            evolutions=_evolutions(
                _continuity_evolution(evolution_kind="repurposed", evolution_id="base-repurposed-2025"),
            ),
            continuidad_validation={"2025": "strict"},
        )

        assert validate_registry_scope([m]) == ()

    def test_strict_continuity_validation_requires_retired_decision_for_missing_surface(self) -> None:
        a = _casilla(cid="0700", label="Old base", continuidad_id="base")
        b = _casilla(cid="0900", label="Unrelated")
        m = _annual_modelo(a, b, continuidad_validation={"2025": "strict"})

        failures = validate_registry_scope([m])

        assert len(failures) == 1
        assert "strict continuity retirement missing" in failures[0]
        assert "base" in failures[0]
        assert "2024" in failures[0]
        assert "2025" in failures[0]

    def test_strict_continuity_validation_accepts_retired_decision_for_missing_surface(self) -> None:
        a = _casilla(cid="0700", label="Old base", continuidad_id="base")
        b = _casilla(cid="0900", label="Unrelated")
        m = _annual_modelo(
            a,
            b,
            evolutions=_evolutions(_continuity_evolution(evolution_kind="retired", evolution_id="base-retired-2025")),
            continuidad_validation={"2025": "strict"},
        )

        assert validate_registry_scope([m]) == ()

    def test_strict_continuity_validation_rejects_unmatched_evolution_continuity_id(self) -> None:
        a = _casilla(cid="0700", label="Base", continuidad_id="base")
        b = _casilla(cid="0700", label="Base", continuidad_id="base")
        m = _annual_modelo(
            a,
            b,
            evolutions=_evolutions(
                _continuity_evolution(continuidad_id="missing", evolution_id="missing-label-2025"),
            ),
            continuidad_validation={"2025": "strict"},
        )

        failures = validate_registry_scope([m])

        assert len(failures) == 1
        assert "strict continuity evolution mismatch" in failures[0]
        assert "missing" in failures[0]
        assert "no matching casilla continuity id" in failures[0]

    def test_strict_continuity_validation_rejects_retired_decision_when_target_surface_remains(
        self,
    ) -> None:
        a = _casilla(cid="0700", label="Base", continuidad_id="base")
        b = _casilla(cid="0700", label="Base", continuidad_id="base")
        m = _annual_modelo(
            a,
            b,
            evolutions=_evolutions(_continuity_evolution(evolution_kind="retired", evolution_id="base-retired-2025")),
            continuidad_validation={"2025": "strict"},
        )

        failures = validate_registry_scope([m])

        assert len(failures) == 1
        assert "strict continuity evolution mismatch" in failures[0]
        assert "target revision still declares" in failures[0]

    def test_directory_loaded_advisory_continuity_inventory_reports_evolution(self, tmp_path: Path) -> None:
        modelo = load_modelo_directory(
            _write_continuity_modelo_directory(tmp_path, strict=False, include_evolution=True),
        )

        summaries = summarize_non_overlapping_cross_revision_casilla_drift([modelo])

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.field == "label"
        assert summary.continuidad_ids == ("base",)
        assert summary.evolution_kinds == ("label_evolved",)
        assert summary.covered_by_evolution_count == 1
        assert validate_registry_scope([modelo]) == ()

    def test_directory_loaded_strict_continuity_hard_fails_uncovered_drift(self, tmp_path: Path) -> None:
        modelo = load_modelo_directory(
            _write_continuity_modelo_directory(tmp_path, strict=True, include_evolution=False),
        )

        failures = validate_registry_scope([modelo])

        assert len(failures) == 1
        assert "strict continuity drift" in failures[0]
        assert "0700" in failures[0]
        assert "label" in failures[0]


def test_cross_revision_validator_accepts_committed_corpus(
    committed_registry: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    modelos, _catalogues = committed_registry
    validate_cross_revision_casilla_consistency(modelos)


def test_committed_corpus_non_overlapping_inventory_keeps_annual_m100_drift_visible(
    committed_registry: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    modelos, _catalogues = committed_registry
    summaries = summarize_non_overlapping_cross_revision_casilla_drift(modelos)

    m100_summaries = [summary for summary in summaries if summary.modelo_id == "100"]
    assert m100_summaries
    assert {summary.field for summary in m100_summaries}.issuperset({"label", "legal_refs"})
    assert all(summary.example_casilla_ids for summary in m100_summaries)


def test_committed_m100_continuity_surface_for_0582_is_loaded(committed_m100: ModeloDefinition) -> None:
    for revision_id in ("2022", "2023", "2024", "2025"):
        revision = committed_m100.revisions[revision_id]
        casilla = next(item for item in revision.casillas if item.id == "0582")
        assert revision.continuidad_validation == "strict"
        assert casilla.continuidad_id == "irpf.intereses-demora-regularizacion.estatal"

    assert (
        tuple(
            evolution
            for evolution in committed_m100.revisions["2022"].casilla_continuidad_evolutions
            if evolution.continuidad_id == "irpf.intereses-demora-regularizacion.estatal"
        )
        == ()
    )
    assert tuple(
        evolution.evolution_kind
        for revision_id in ("2023", "2024", "2025")
        for evolution in committed_m100.revisions[revision_id].casilla_continuidad_evolutions
        if evolution.continuidad_id == "irpf.intereses-demora-regularizacion.estatal"
    ) == ("unchanged", "unchanged", "unchanged")


def test_committed_m100_continuity_surface_for_1038_retirement_is_loaded(committed_m100: ModeloDefinition) -> None:
    continuidad_id = "irpf.deduccion-autonomica.galicia.otras"
    for revision_id in ("2023", "2024"):
        revision = committed_m100.revisions[revision_id]
        casilla = next(item for item in revision.casillas if item.id == "1038")
        assert revision.continuidad_validation == "strict"
        assert casilla.label == "Otras deducciones"
        assert casilla.continuidad_id == continuidad_id

    assert not any(item.id == "1038" for item in committed_m100.revisions["2025"].casillas)

    assert _evolution_pairs(committed_m100, continuidad_id) == {
        ("2023", "2024"): "unchanged",
        ("2024", "2025"): "retired",
    }


def test_committed_m100_continuity_surface_for_0063_legal_refs_is_loaded(committed_m100: ModeloDefinition) -> None:
    continuidad_id = "irpf.inmueble.porcentaje-propiedad"
    for revision_id in ("2020", "2021", "2022", "2023", "2024", "2025"):
        revision = committed_m100.revisions[revision_id]
        casilla = next(item for item in revision.casillas if item.id == "0063")
        assert casilla.continuidad_id == continuidad_id

    assert {
        revision_id: committed_m100.revisions[revision_id].continuidad_validation
        for revision_id in ("2020", "2021", "2022", "2023", "2024", "2025")
    } == {
        "2020": "advisory",
        "2021": "advisory",
        "2022": "strict",
        "2023": "strict",
        "2024": "strict",
        "2025": "strict",
    }

    assert _evolution_pairs(committed_m100, continuidad_id) == {
        ("2020", "2021"): "legal_refs_evolved",
        ("2020", "2022"): "legal_refs_evolved",
        ("2020", "2023"): "legal_refs_evolved",
        ("2020", "2024"): "legal_refs_evolved",
        ("2020", "2025"): "legal_refs_evolved",
        ("2021", "2022"): "unchanged",
        ("2021", "2025"): "legal_refs_evolved",
        ("2022", "2023"): "unchanged",
        ("2022", "2025"): "legal_refs_evolved",
        ("2023", "2024"): "unchanged",
        ("2023", "2025"): "legal_refs_evolved",
        ("2024", "2025"): "legal_refs_evolved",
    }


def test_committed_m100_continuity_surface_for_0070_label_and_legal_refs_is_loaded(
    committed_m100: ModeloDefinition,
) -> None:
    continuidad_id = "irpf.inmueble.vivienda-habitual-flag"
    for revision_id in ("2020", "2021", "2022", "2023", "2024", "2025"):
        revision = committed_m100.revisions[revision_id]
        casilla = next(item for item in revision.casillas if item.id == "0070")
        assert casilla.continuidad_id == continuidad_id

    assert {
        revision_id: committed_m100.revisions[revision_id].continuidad_validation
        for revision_id in ("2020", "2021", "2022", "2023", "2024", "2025")
    } == {
        "2020": "advisory",
        "2021": "advisory",
        "2022": "strict",
        "2023": "strict",
        "2024": "strict",
        "2025": "strict",
    }

    assert _evolution_pairs(committed_m100, continuidad_id) == {
        ("2020", "2021"): "label_and_legal_refs_evolved",
        ("2020", "2022"): "label_and_legal_refs_evolved",
        ("2020", "2023"): "label_and_legal_refs_evolved",
        ("2020", "2024"): "label_and_legal_refs_evolved",
        ("2020", "2025"): "label_and_legal_refs_evolved",
        ("2021", "2022"): "label_evolved",
        ("2021", "2023"): "label_evolved",
        ("2021", "2024"): "label_evolved",
        ("2021", "2025"): "label_and_legal_refs_evolved",
        ("2022", "2023"): "label_evolved",
        ("2022", "2024"): "label_evolved",
        ("2022", "2025"): "label_and_legal_refs_evolved",
        ("2023", "2024"): "label_evolved",
        ("2023", "2025"): "label_and_legal_refs_evolved",
        ("2024", "2025"): "label_and_legal_refs_evolved",
    }


def test_committed_m100_strict_continuity_surface_rejects_covered_label_drift(
    committed_registry: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
    committed_m100: ModeloDefinition,
) -> None:
    modelos, _catalogues = committed_registry
    revision_2025 = committed_m100.revisions["2025"]
    mutated_casillas = tuple(
        casilla.model_copy(update={"label": f"{casilla.label} drift"}) if casilla.id == "0582" else casilla
        for casilla in revision_2025.casillas
    )
    mutated_revision = revision_2025.model_copy(update={"casillas": mutated_casillas})
    mutated_revisions = dict(committed_m100.revisions)
    mutated_revisions["2025"] = mutated_revision
    mutated_m100 = committed_m100.model_copy(update={"revisions": mutated_revisions})
    mutated_modelos = tuple(mutated_m100 if modelo.id == "100" else modelo for modelo in modelos)

    failures = validate_registry_scope(mutated_modelos)

    assert len(failures) == 3
    assert all("strict continuity drift" in failure for failure in failures)
    assert all("0582" in failure for failure in failures)
    assert all("label" in failure for failure in failures)
    source_revisions = {
        revision_id for failure in failures for revision_id in ("2022", "2023", "2024") if revision_id in failure
    }
    assert source_revisions == {
        "2022",
        "2023",
        "2024",
    }


def test_backend_registry_validation_accepts_committed_corpus_drift_gate(
    committed_registry: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    modelos, catalogues = committed_registry
    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)


def test_singleton_semantic_role_warning_count_does_not_regress(
    committed_registry: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    modelos, catalogues = committed_registry
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)

    singleton_warnings = [
        str(item.message)
        for item in captured
        if "semantic_role" in str(item.message) and "appears on exactly one casilla" in str(item.message)
    ]

    # Re-baselined after the 2026-05-20 indexed typo scan and
    # semantic-axis sibling filters. Any new singleton typo warning is
    # now a regression or a missing explicit singleton policy.
    assert len(singleton_warnings) == 0, singleton_warnings[:10]
