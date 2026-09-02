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

import json
import warnings
from datetime import date
from pathlib import Path

import pytest

from .....core.resources.bundled_data import bundled_path
from .._validate import RegistryValidator
from .._validate_cross_revision import (
    declared_cross_revision_continuity_semantic_linkage_failures,
    validate_cross_revision_casilla_consistency,
)
from ..errors import RegistryValidationError
from ..ids import LegalRefId
from ..loader import load_modelo_directory
from ..modelo_localization import ModeloLocalizationFieldKind, casilla_occurrence_locale_key
from ..schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ..schema_references import PeriodSelector
from ..schema_surfaces import CasillaConstraints, CasillaDefinition
from ..validate_registry_scope import validate_registry_scope
from ._registry_schema_support import _committed_registry_tree
from ._synthetic_locale_fixtures import (
    _synthetic_locale_scope,
    _write_test_label,
    synthetic_locale_state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


__all__ = ["_synthetic_locale_scope"]


def _casilla(
    *,
    cid: str = "0001",
    label: str = "Test casilla",
    section: tuple[str, ...] = ("test",),
    data_type: str = "money",
    semantic_role: str | None = None,
    legal_refs: tuple[LegalRefId, ...] = ("ley-58-2003:art-29",),
    continuidad_id: str | None = None,
) -> CasillaDefinition:
    # Continuity is a legal identity assertion. Synthetic fixtures that are not
    # specifically testing a missing semantic role should therefore model the
    # ordinary role-derived spelling as the production corpus does.
    resolved_semantic_role = semantic_role
    if resolved_semantic_role is None and continuidad_id is not None:
        resolved_semantic_role = continuidad_id.replace("-", "_")
    payload = {
        "id": cid,
        "number": cid,
        "localization_keys": (_write_test_label(label),),
        "section": section,
        "data_type": data_type,
        "semantic_role": resolved_semantic_role,
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
                "localization_key": f"test.schema.revision.{revision_id}.label",
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
            "title_localization_key": f"test.schema.modelo.{modelo_id}.title",
            "official_name_localization_key": f"test.schema.modelo.{modelo_id}.official_name",
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


def _three_year_modelo(
    first: list[CasillaDefinition],
    second: list[CasillaDefinition],
    third: list[CasillaDefinition],
    *,
    evolutions: dict[str, tuple[dict[str, object], ...]] | None = None,
    continuidad_validation: dict[str, str] | None = None,
    shared_window: bool = False,
) -> ModeloDefinition:
    """Build a 2023/2024/2025 modelo, the narrowest shape a chain gap needs.

    ``shared_window`` gives every revision the same period selector, modelling
    variant schemas of one period (the M369 shape) rather than a temporal
    sequence.
    """
    selector = PeriodSelector(years=(2023, 2024, 2025), periods=("0A",))
    selectors = (
        {"2023": selector, "2024": selector, "2025": selector}
        if shared_window
        else {year: PeriodSelector(years=(int(year),), periods=("0A",)) for year in ("2023", "2024", "2025")}
    )
    return _modelo(
        "100",
        {"2023": first, "2024": second, "2025": third},
        selectors=selectors,
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
    return _committed_registry_tree()


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
section = ["test"]
data_type = "money"
continuidad_id = "base"
semantic_role = "base"
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
section = ["test"]
data_type = "money"
continuidad_id = "base"
semantic_role = "base"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
{evolution_block}
""".lstrip(),
        encoding="utf-8",
    )
    _write_test_label("Old")
    _write_test_label("New")
    for revision_id, label in (("2024", "Old"), ("2025", "New")):
        key = casilla_occurrence_locale_key("999", revision_id, "0700", ModeloLocalizationFieldKind.LABEL)
        if synthetic_locale_state.root is not None:
            with (synthetic_locale_state.root / "es.yml").open("a", encoding="utf-8") as handle:
                handle.write(f"{json.dumps(key)}: {json.dumps(label)}\n")
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

    def test_advisory_continuity_evolution_requires_a_target_surface(self) -> None:
        source = _casilla(cid="0700", label="Base", continuidad_id="base")
        target = _casilla(cid="0900", label="Unrelated")
        modelo = _annual_modelo(
            source,
            target,
            evolutions=_evolutions(_continuity_evolution(evolution_id="base-label-2025")),
        )

        failures = validate_registry_scope([modelo])

        assert len(failures) == 1
        assert "non-retired evolution has no target" in failures[0]

    def test_continuity_evolution_rejects_duplicate_boundary_declarations(self) -> None:
        source = _casilla(cid="0700", label="Base", continuidad_id="base")
        target = _casilla(cid="0700", label="Base", continuidad_id="base")
        modelo = _annual_modelo(
            source,
            target,
            evolutions=_evolutions(
                _continuity_evolution(evolution_id="base-label-2025"),
                _continuity_evolution(evolution_id="base-label-repeat-2025"),
            ),
        )

        failures = validate_registry_scope([modelo])

        assert len(failures) == 1
        assert "continuity evolution duplicate" in failures[0]

    def test_repurposed_evolution_covers_a_versioned_width_boundary(self) -> None:
        source = _casilla(
            cid="0700",
            semantic_role="historic_cnae",
            continuidad_id="prorrata-cnae",
        ).model_copy(
            update={
                "constraints": CasillaConstraints(
                    min_length=3,
                    max_length=3,
                    legal_refs=("ley-58-2003:art-29",),
                    source_refs=("aeat-manual",),
                ),
            },
        )
        target = _casilla(
            cid="0700",
            semantic_role="cnae_2026_four_digit",
            continuidad_id="prorrata-cnae",
        ).model_copy(
            update={
                "constraints": CasillaConstraints(
                    min_length=4,
                    max_length=4,
                    legal_refs=("ley-58-2003:art-29",),
                    source_refs=("aeat-manual",),
                ),
            },
        )
        modelo = _annual_modelo(
            source,
            target,
            evolutions=_evolutions(
                _continuity_evolution(evolution_kind="repurposed", continuidad_id="prorrata-cnae"),
            ),
            continuidad_validation={"2025": "strict"},
        )

        assert validate_registry_scope([modelo]) == ()

    def test_continuity_semantic_linkage_requires_role_derived_id_when_role_is_unique(self) -> None:
        source = _casilla(
            cid="0700",
            semantic_role="total_tax_due",
            continuidad_id="unrelated-continuity-id",
        )
        target = _casilla(
            cid="0700",
            semantic_role="total_tax_due",
            continuidad_id="unrelated-continuity-id",
        )

        failures = validate_registry_scope([_annual_modelo(source, target)])

        assert len(failures) == 1
        assert "semantic linkage mismatch" in failures[0]
        assert "total-tax-due" in failures[0]

    def test_continuity_semantic_linkage_requires_roles_across_a_revision_boundary(self) -> None:
        source = _casilla(cid="0700", continuidad_id="total-tax-due").model_copy(
            update={"semantic_role": None},
        )
        target = _casilla(
            cid="0700",
            semantic_role="total_tax_due",
            continuidad_id="total-tax-due",
        )

        failures = validate_registry_scope([_annual_modelo(source, target)])

        assert len(failures) == 1
        assert "semantic linkage missing" in failures[0]
        assert "2024" in failures[0]

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

    def test_strict_continuity_validation_rejects_chain_that_resumes_after_a_gap(self) -> None:
        present = _casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")
        absent = _casilla(cid="0900", label="Unrelated")
        m = _three_year_modelo(
            [present],
            [absent],
            [_casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")],
            evolutions={
                "2024": (
                    {
                        "id": "la-rioja-otras-retired-2024",
                        "continuidad_id": "la-rioja-otras",
                        "from_revision": "2023",
                        "to_revision": "2024",
                        "evolution_kind": "retired",
                        "legal_refs": ("ley-58-2003:art-29",),
                        "source_refs": ("aeat-manual",),
                    },
                ),
            },
            continuidad_validation={"2023": "strict", "2024": "strict", "2025": "strict"},
        )

        failures = validate_registry_scope([m])

        assert len(failures) == 1
        assert "strict continuity chain is not contiguous" in failures[0]
        assert "la-rioja-otras" in failures[0]
        assert "2024" in failures[0]
        assert "new grounded continuidad_id" in failures[0]

    def test_strict_continuity_validation_rejects_gapped_chain_without_any_retirement_record(self) -> None:
        """A gap declared only by absence is caught even where no retirement fires.

        The disappearance boundary here is advisory-to-advisory, so the
        retirement gate stays silent; contiguity is what makes the resumption
        visible.
        """
        chained = _casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")
        m = _three_year_modelo(
            [chained],
            [_casilla(cid="0900", label="Unrelated")],
            [_casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")],
            continuidad_validation={"2025": "strict"},
        )

        failures = validate_registry_scope([m])

        assert [failure for failure in failures if "strict continuity retirement missing" in failure] == []
        assert len(failures) == 1
        assert "strict continuity chain is not contiguous" in failures[0]

    def test_strict_continuity_validation_accepts_a_contiguous_chain(self) -> None:
        m = _three_year_modelo(
            [_casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")],
            [_casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")],
            [_casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")],
            continuidad_validation={"2023": "strict", "2024": "strict", "2025": "strict"},
        )

        assert validate_registry_scope([m]) == ()

    def test_strict_continuity_validation_accepts_two_chains_across_the_gap(self) -> None:
        """The declared resolution: the resumed concept takes a new chain id."""
        m = _three_year_modelo(
            [
                _casilla(
                    cid="1082",
                    label="Otras deducciones",
                    semantic_role="la_rioja_otras",
                    continuidad_id="la-rioja-otras-2023",
                ),
            ],
            [_casilla(cid="0900", label="Unrelated")],
            [
                _casilla(
                    cid="1082",
                    label="Otras deducciones",
                    semantic_role="la_rioja_otras",
                    continuidad_id="la-rioja-otras-2025",
                ),
            ],
            evolutions={
                "2024": (
                    {
                        "id": "la-rioja-otras-2023-retired-2024",
                        "continuidad_id": "la-rioja-otras-2023",
                        "from_revision": "2023",
                        "to_revision": "2024",
                        "evolution_kind": "retired",
                        "legal_refs": ("ley-58-2003:art-29",),
                        "source_refs": ("aeat-manual",),
                    },
                ),
            },
            continuidad_validation={"2023": "strict", "2024": "strict", "2025": "strict"},
        )

        assert validate_registry_scope([m]) == ()

    def test_strict_continuity_contiguity_ignores_variant_revisions_sharing_a_window(self) -> None:
        """Variant schemas of one period are alternatives, not a temporal gap."""
        m = _three_year_modelo(
            [_casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")],
            [_casilla(cid="0900", label="Unrelated")],
            [_casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")],
            continuidad_validation={"2023": "strict", "2024": "strict", "2025": "strict"},
            shared_window=True,
        )

        assert [failure for failure in validate_registry_scope([m]) if "not contiguous" in failure] == []

    def test_strict_continuity_contiguity_stays_silent_on_a_fully_advisory_span(self) -> None:
        m = _three_year_modelo(
            [_casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")],
            [_casilla(cid="0900", label="Unrelated")],
            [_casilla(cid="1082", label="Otras deducciones", continuidad_id="la-rioja-otras")],
        )

        assert validate_registry_scope([m]) == ()

    def test_directory_loaded_advisory_continuity_modelo_passes_registry_scope(self, tmp_path: Path) -> None:
        """A directory-loaded advisory-continuity modelo carrying evolution passes scope validation.

        Covers the loader-plus-scope path for the non-strict continuity case,
        the strict counterpart of the sibling test below.
        """
        modelo = load_modelo_directory(
            _write_continuity_modelo_directory(tmp_path, strict=False, include_evolution=True),
        )

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


def test_committed_corpus_continuity_semantic_linkage_is_complete(
    committed_registry: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    modelos, _catalogues = committed_registry

    assert declared_cross_revision_continuity_semantic_linkage_failures(modelos) == ()


def test_committed_m100_continuity_surface_for_0582_is_loaded(committed_m100: ModeloDefinition) -> None:
    for revision_id in ("2022", "2023", "2024", "2025"):
        revision = committed_m100.revisions[revision_id]
        casilla = next(item for item in revision.casillas if item.id == "0582")
        assert revision.continuidad_validation == "strict"
        assert casilla.continuidad_id == "irpf-intereses-demora-regularizacion-estatal"

    assert (
        tuple(
            evolution
            for evolution in committed_m100.revisions["2022"].casilla_continuidad_evolutions
            if evolution.continuidad_id == "irpf-intereses-demora-regularizacion-estatal"
        )
        == ()
    )
    assert tuple(
        evolution.evolution_kind
        for revision_id in ("2023", "2024", "2025")
        for evolution in committed_m100.revisions[revision_id].casilla_continuidad_evolutions
        if evolution.continuidad_id == "irpf-intereses-demora-regularizacion-estatal"
    ) == ("unchanged", "unchanged", "unchanged")


def test_committed_m100_continuity_surface_for_1038_retirement_is_loaded(committed_m100: ModeloDefinition) -> None:
    continuidad_id = "irpf-deduccion-galicia-otras"
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
    continuidad_id = "irpf-inmueble-porcentaje-propiedad"
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
    continuidad_id = "irpf-inmueble-vivienda-habitual-flag"
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
    source_0582 = next(casilla for casilla in revision_2025.casillas if casilla.id == "0582")
    drift_key, drift_label = next(
        (casilla.localization_keys[0], casilla.label)
        for casilla in revision_2025.casillas
        if casilla.id != "0582" and casilla.label != source_0582.label
    )
    assert drift_label != source_0582.label
    mutated_casillas = tuple(
        casilla.model_copy(
            update={"localization_keys": (drift_key,)},
        )
        if casilla.id == "0582"
        else casilla
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
