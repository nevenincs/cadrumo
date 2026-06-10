"""Tests for registry cross-model relation closure."""

from __future__ import annotations

import shutil
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import RegistryCatalogues, RegistryLoadError, RegistryValidationError
from .._bindings import CasillaObservation, RegistryModeloObservation
from .._loader import load_modelo_directory, load_registry_tree
from .._relations import relation_source_requirements, resolve_relation_values_from_observations
from .._schema import ModeloDefinition, ModeloRevision
from .._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_MODELO_180_DIR = _REGISTRY_ROOT / "modelos" / "180"
_MODELO_180_FIRST_RELATION_FRAGMENT = (
    Path("revisions") / "2023-y-siguientes" / "relations" / "0001-modelo-180-rel-115-perceptores-anual.toml"
)


@cache
def _committed_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return load_registry_tree(_REGISTRY_ROOT)


def _modelo(modelos: tuple[ModeloDefinition, ...], modelo_id: str) -> ModeloDefinition:
    return next(modelo for modelo in modelos if modelo.id == modelo_id)


def _with_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revision}})


def _replace_modelo(
    modelos: tuple[ModeloDefinition, ...],
    updated: ModeloDefinition,
) -> tuple[ModeloDefinition, ...]:
    return tuple(updated if modelo.id == updated.id else modelo for modelo in modelos)


def _copy_committed_modelo_180(target: Path) -> Path:
    shutil.copytree(_MODELO_180_DIR, target)
    return target


def _modelo_115_observations() -> tuple[RegistryModeloObservation, ...]:
    values_by_period = {
        "1T": {"01": Decimal("1"), "02": Decimal("250.10"), "03": Decimal("47.52")},
        "2T": {"01": Decimal("1"), "02": Decimal("749.90"), "03": Decimal("142.48")},
        "3T": {"01": Decimal("2"), "02": Decimal("1200.00"), "03": Decimal("228.00")},
        "4T": {"01": Decimal("1"), "02": Decimal("-50.25"), "03": Decimal("0.00")},
    }
    return tuple(
        RegistryModeloObservation(
            modelo="115",
            filing_year=2026,
            period=period,
            observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in casilla_values.items()),
        )
        for period, casilla_values in values_by_period.items()
    )


def test_registry_validator_checks_cross_model_relation_closure() -> None:
    modelos, catalogues = _committed_tree()

    assert len(modelos) >= 5, "committed registry must carry several modelos"
    assert any(any(rev.relations for rev in modelo.revisions.values()) for modelo in modelos), (
        "at least one modelo must declare cross-model relations for closure validation to be meaningful"
    )

    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)


def test_modelo_180_relation_source_requirements_identify_source_filings() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]

    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)
    requirements = relation_source_requirements(revision, filing_year=2026, period="0A")

    assert len(requirements) == 3
    by_output = {requirement.source_output: requirement for requirement in requirements}
    assert set(by_output) == {"01", "02", "03"}
    for requirement in by_output.values():
        assert requirement.source_modelo == "115"
        assert requirement.filing_year == 2026
        assert requirement.periods == ("1T", "2T", "3T", "4T")
        assert requirement.dependency_role == "periodic_to_annual_summary"
        assert requirement.aggregation_op == "sum"
    assert by_output["01"].target_bindings == ("modelo-180-115-perceptores-anual",)
    assert by_output["02"].target_bindings == ("modelo-180-115-base-anual",)
    assert by_output["03"].target_bindings == ("modelo-180-115-retenciones-anual",)


def test_relation_source_requirements_obey_target_periods() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]

    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)

    assert relation_source_requirements(revision, filing_year=2026, period="1T") == ()


def test_relation_observation_resolution_obeys_target_periods() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]

    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)

    assert resolve_relation_values_from_observations(revision, (), filing_year=2026, period="1T") == {}


def test_modelo_180_relations_resolve_from_observed_source_filings() -> None:
    """The resolver produces the three 180 annual bindings from four 115 quarterly filings.

    Asserts structural wiring (all three binding keys are populated) and
    that each resolved value equals the sum of the corresponding casilla
    observations across the four quarters — derived programmatically from
    the same observations supplied to the resolver, not hand-computed.
    """
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    observations = _modelo_115_observations()

    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)
    values = resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=2026,
        period="0A",
    )

    # Assert all three binding keys are present — wiring check.
    expected_keys = {
        "modelo-180-rel-115-perceptores-anual",
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
    }
    assert expected_keys == set(values.keys()), "resolver must populate exactly the three 180 annual bindings"

    # Derive expected sums programmatically from the observation fixtures, keyed
    # by the casilla_id each binding sources from (01=perceptores, 02=base, 03=retenciones).
    casilla_sums: dict[str, Decimal] = {}
    for obs in observations:
        for casilla_obs in obs.observations:
            casilla_sums[casilla_obs.casilla_id] = (
                casilla_sums.get(casilla_obs.casilla_id, Decimal("0")) + casilla_obs.value
            )

    assert values["modelo-180-rel-115-perceptores-anual"] == casilla_sums["01"]
    assert values["modelo-180-rel-115-base-anual"] == casilla_sums["02"]
    assert values["modelo-180-rel-115-retenciones-anual"] == casilla_sums["03"]


def test_relation_observation_resolution_fails_when_required_source_period_is_missing() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    observations = tuple(item for item in _modelo_115_observations() if item.period != "4T")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)

    with pytest.raises(RegistryValidationError, match="expected one observed filing"):
        resolve_relation_values_from_observations(revision, observations, filing_year=2026, period="0A")


def test_registry_validator_rejects_relation_to_unknown_source_modelo() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    relation = revision.relations[0].model_copy(update={"source_modelo": "999"})
    mutated_revision = revision.model_copy(update={"relations": (relation, *revision.relations[1:])})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="unknown source modelo"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo)
        )


def test_registry_validator_rejects_relation_source_period_outside_source_revision() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    relation = revision.relations[0].model_copy(update={"source_periods": ("1T", "99")})
    mutated_revision = revision.model_copy(update={"relations": (relation, *revision.relations[1:])})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="does not support source periods"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo)
        )


def test_registry_validator_rejects_cross_model_relation_years_without_source_revision_coverage() -> None:
    modelos, catalogues = _committed_tree()
    source_modelo = _modelo(modelos, "115")
    target_modelo = _modelo(modelos, "180")
    revision = target_modelo.revisions["2019-2022"]
    widened_selector = revision.period_selector.model_copy(update={"year_from": 2014})
    widened_revision = revision.model_copy(
        update={
            "valid_from": revision.valid_from.replace(year=2014),
            "period_selector": widened_selector,
        }
    )
    mutated_target = _with_revision(target_modelo, widened_revision)

    with pytest.raises(RegistryValidationError, match="lacks source revision year coverage for 2014-2022"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry((source_modelo, mutated_target))


def test_registry_validator_rejects_relation_to_unknown_source_output() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    relation = revision.relations[0].model_copy(update={"source_output": "missing-output"})
    mutated_revision = revision.model_copy(update={"relations": (relation, *revision.relations[1:])})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="has no source output"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo)
        )


def test_registry_validator_rejects_nondirect_previous_filing_binding() -> None:
    """A previous_filing binding with a non-direct selector is rejected.

    The M100 cross-modelo slot bindings carry a non-direct selector
    ({source_modelo, source_output}, no period anchor). They are canonically
    ``relation_prefill``; re-stamping one back to ``previous_filing`` must trip
    the slot-source hygiene gate (aggregation-taxonomy ruling 3).
    """
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "100")
    revision = modelo.revisions["2025"]
    target_id = "renta-2025-modelo-130-pagos-fraccionados"
    mutated_bindings = tuple(
        binding.model_copy(update={"source": "previous_filing"}) if binding.id == target_id else binding
        for binding in revision.bindings
    )
    mutated_revision = revision.model_copy(update={"bindings": mutated_bindings})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="non-direct selector"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo)
        )


def test_registry_validator_rejects_relation_targeted_previous_filing_binding() -> None:
    """A binding both relation-targeted and previous_filing is rejected.

    The M180 perceptores slot is relation-targeted and canonically
    ``relation_prefill``. Re-stamping it back to ``previous_filing`` (even with
    its direct selector intact) must trip the relation-vs-previous_filing
    collision gate (aggregation-taxonomy ruling 3) — the two mechanisms must
    have disjoint declared ownership.
    """
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    target_id = "modelo-180-115-perceptores-anual"
    mutated_bindings = tuple(
        binding.model_copy(update={"source": "previous_filing"}) if binding.id == target_id else binding
        for binding in revision.bindings
    )
    mutated_revision = revision.model_copy(update={"bindings": mutated_bindings})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="both a relation target_binding and a 'previous_filing'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo)
        )


def test_fragmented_modelo_requires_relation_dependency_role(tmp_path: Path) -> None:
    directory = _copy_committed_modelo_180(tmp_path / "180")
    fragment = directory / _MODELO_180_FIRST_RELATION_FRAGMENT
    text = fragment.read_text(encoding="utf-8").replace(
        'dependency_role = "periodic_to_annual_summary"\n',
        "",
        1,
    )
    fragment.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="dependency_role"):
        load_modelo_directory(directory)


def test_fragmented_modelo_rejects_annual_summary_relation_without_summary_role(tmp_path: Path) -> None:
    directory = _copy_committed_modelo_180(tmp_path / "180")
    fragment = directory / _MODELO_180_FIRST_RELATION_FRAGMENT
    text = fragment.read_text(encoding="utf-8").replace(
        'dependency_role = "periodic_to_annual_summary"',
        'dependency_role = "direct_calculation"',
        1,
    )
    fragment.write_text(text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="annual summary relation"):
        load_modelo_directory(directory)
