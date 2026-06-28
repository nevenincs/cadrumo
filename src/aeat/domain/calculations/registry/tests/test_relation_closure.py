"""Tests for registry cross-model relation closure."""

from __future__ import annotations

from decimal import Decimal
from functools import cache

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .....tests.registry_observations import registry_grounded_modelo_observation
from .. import CasillaId, RegistryCatalogues, RegistryValidationError, validated_casilla_id
from .._bindings import RegistryModeloObservation
from .._loader import load_registry_tree
from .._relations import relation_source_requirements, resolve_relation_values_from_observations
from .._schema import ModeloDefinition, ModeloRevision
from .._schema_surfaces import RelationDefinition
from .._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_M115_BASE_CASILLA: CasillaId = validated_casilla_id("02", surface="_M115_BASE_CASILLA")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03", surface="_M115_RETENCIONES_CASILLA")
_UNKNOWN_SOURCE_CASILLA: CasillaId = validated_casilla_id("missing-output", surface="_UNKNOWN_SOURCE_CASILLA")


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


def _modelo_115_observations() -> tuple[RegistryModeloObservation, ...]:
    values_by_period = {
        "1T": {
            _M115_BASE_CASILLA: Decimal("250.10"),
            _M115_RETENCIONES_CASILLA: Decimal("47.52"),
        },
        "2T": {
            _M115_BASE_CASILLA: Decimal("749.90"),
            _M115_RETENCIONES_CASILLA: Decimal("142.48"),
        },
        "3T": {
            _M115_BASE_CASILLA: Decimal("1200.00"),
            _M115_RETENCIONES_CASILLA: Decimal("228.00"),
        },
        "4T": {
            _M115_BASE_CASILLA: Decimal("-50.25"),
            _M115_RETENCIONES_CASILLA: Decimal("0.00"),
        },
    }
    return tuple(
        registry_grounded_modelo_observation(
            modelo="115",
            filing_year=2026,
            period=period,
            casilla_values=casilla_values,
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

    assert len(requirements) == 2
    by_output = {requirement.source_casilla_ids[0]: requirement for requirement in requirements}
    assert set(by_output) == {
        _M115_BASE_CASILLA,
        _M115_RETENCIONES_CASILLA,
    }
    for requirement in by_output.values():
        assert requirement.source_modelo == "115"
        assert requirement.filing_year == 2026
        assert requirement.periods == ("1T", "2T", "3T", "4T")
        assert requirement.dependency_role == "periodic_to_annual_summary"
        assert requirement.aggregation_op == "sum"
    assert by_output[_M115_BASE_CASILLA].target_bindings == ("modelo-180-115-base-anual",)
    assert by_output[_M115_RETENCIONES_CASILLA].target_bindings == ("modelo-180-115-retenciones-anual",)


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
    """The resolver produces the two monetary 180 annual bindings from four 115 quarterly filings.

    Asserts structural wiring (both relation binding keys are populated) and
    that each resolved value equals the sum of the corresponding casilla
    observations across the four quarters. ``decl.total-perceptores`` is now a
    retenciones_aggregation binding and is deliberately absent from this relation
    resolver.
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

    # Assert both relation binding keys are present — wiring check.
    expected_keys = {
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
    }
    assert expected_keys == set(values.keys()), "resolver must populate exactly the two monetary 180 annual bindings"

    # Derive expected sums programmatically from the observation fixtures, keyed
    # by the casilla_id each binding sources from (02=base, 03=retenciones).
    casilla_sums: dict[CasillaId, Decimal] = {}
    for obs in observations:
        for casilla_obs in obs.observations:
            casilla_sums[casilla_obs.casilla_id] = (
                casilla_sums.get(casilla_obs.casilla_id, Decimal("0")) + casilla_obs.value
            )

    assert values["modelo-180-rel-115-base-anual"] == casilla_sums[_M115_BASE_CASILLA]
    assert values["modelo-180-rel-115-retenciones-anual"] == casilla_sums[_M115_RETENCIONES_CASILLA]


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
            _replace_modelo(modelos, mutated_modelo),
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
            _replace_modelo(modelos, mutated_modelo),
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
        },
    )
    mutated_target = _with_revision(target_modelo, widened_revision)

    with pytest.raises(RegistryValidationError, match="lacks source revision year coverage for 2014-2022"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry((source_modelo, mutated_target))


def test_registry_validator_rejects_relation_to_unknown_source_casilla_id() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    relation = revision.relations[0].model_copy(update={"source_casilla_id": _UNKNOWN_SOURCE_CASILLA})
    mutated_revision = revision.model_copy(update={"relations": (relation, *revision.relations[1:])})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="has no source casilla id"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo),
        )


def test_registry_validator_rejects_relation_source_casilla_id_that_is_only_a_binding_id() -> None:
    modelos, catalogues = _committed_tree()
    target_modelo = _modelo(modelos, "390")
    source_modelo = _modelo(modelos, "303")
    revision = target_modelo.revisions["2010-y-siguientes"]
    source_revision = source_modelo.revisions["2009-y-siguientes"]
    binding_id = source_revision.bindings[0].id
    assert binding_id not in {casilla.id for casilla in source_revision.casillas}

    relation = revision.relations[0].model_copy(update={"source_casilla_id": binding_id})
    mutated_revision = revision.model_copy(update={"relations": (relation, *revision.relations[1:])})
    mutated_modelo = _with_revision(target_modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="has no source casilla id"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo),
        )


def test_registry_validator_rejects_relation_source_casilla_display_token() -> None:
    modelos, catalogues = _committed_tree()
    target_modelo = _modelo(modelos, "390")
    source_modelo = _modelo(modelos, "303")
    revision = target_modelo.revisions["2010-y-siguientes"]
    source_revision = source_modelo.revisions["2009-y-siguientes"]
    relation = next(
        item
        for item in revision.relations
        if item.id == "modelo-390-rel-303-compensacion-ultimo-periodo"
    )
    source_casilla = next(item for item in source_revision.casillas if item.id == relation.source_casilla_id)
    assert source_casilla.number != source_casilla.id

    noncanonical_source_id = validated_casilla_id(
        source_casilla.number,
        surface="relation display token source casilla id",
    )
    mutated_relation = relation.model_copy(update={"source_casilla_id": noncanonical_source_id})
    mutated_revision = revision.model_copy(
        update={
            "relations": tuple(mutated_relation if item.id == relation.id else item for item in revision.relations),
        },
    )
    mutated_modelo = _with_revision(target_modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match=r"not a canonical casilla\.id") as exc_info:
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo),
        )

    message = str(exc_info.value)
    assert source_casilla.number in message
    assert source_casilla.id in message


def test_registry_validator_rejects_previous_filing_source_casilla_id_missing_from_matching_revision() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "130")
    revision = modelo.revisions["2019-y-siguientes"]
    revision_scoped_only = validated_casilla_id("0059", surface="M100 revision-scoped test casilla")
    binding = next(item for item in revision.bindings if item.id == "irpf.previous_year_economic_activity_net_income")
    mutated_selector = {**binding.selector, "source_casilla_ids": (revision_scoped_only,)}
    mutated_binding = binding.model_copy(update={"selector": mutated_selector})
    mutated_revision = revision.model_copy(
        update={"bindings": tuple(mutated_binding if item.id == binding.id else item for item in revision.bindings)},
    )
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="period-compatible 100 revision"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo),
        )


def test_registry_validator_rejects_previous_filing_source_casilla_display_token() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "303")
    revision = modelo.revisions["2009-y-siguientes"]
    binding = next(item for item in revision.bindings if item.id == "modelo-303-compensacion-pendiente-anteriores")
    source_casilla = next(item for item in revision.casillas if item.id == binding.selector["source_casilla_id"])
    assert source_casilla.number != source_casilla.id

    noncanonical_source_id = validated_casilla_id(
        source_casilla.number,
        surface="previous_filing display token source casilla id",
    )
    mutated_selector = {**binding.selector, "source_casilla_id": noncanonical_source_id}
    mutated_binding = binding.model_copy(update={"selector": mutated_selector})
    mutated_revision = revision.model_copy(
        update={"bindings": tuple(mutated_binding if item.id == binding.id else item for item in revision.bindings)},
    )
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match=r"not a canonical casilla\.id") as exc_info:
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo),
        )

    message = str(exc_info.value)
    assert source_casilla.number in message
    assert source_casilla.id in message


def test_registry_validator_rejects_nondirect_previous_filing_binding() -> None:
    """A previous_filing binding with a non-direct selector is rejected.

    The M100 cross-modelo slot bindings carry a non-direct selector
    ({source_modelo, source_casilla_id}, no period anchor). They are canonically
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
            _replace_modelo(modelos, mutated_modelo),
        )


def test_registry_validator_rejects_relation_targeted_previous_filing_binding() -> None:
    """A binding both relation-targeted and previous_filing is rejected.

    The M180 base slot is relation-targeted and canonically
    ``relation_prefill``. Re-stamping it back to ``previous_filing`` (even with
    its direct selector intact) must trip the relation-vs-previous_filing
    collision gate (aggregation-taxonomy ruling 3) — the two mechanisms must
    have disjoint declared ownership.
    """
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "180")
    revision = modelo.revisions["2023-y-siguientes"]
    target_id = "modelo-180-115-base-anual"
    mutated_bindings = tuple(
        binding.model_copy(update={"source": "previous_filing"}) if binding.id == target_id else binding
        for binding in revision.bindings
    )
    mutated_revision = revision.model_copy(update={"bindings": mutated_bindings})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="both a relation target_binding and a 'previous_filing'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo),
        )


def test_relation_definition_requires_dependency_role() -> None:
    modelos, _ = _committed_tree()
    relation = _modelo(modelos, "180").revisions["2023-y-siguientes"].relations[0]
    raw_relation = relation.model_dump(mode="python")
    raw_relation.pop("dependency_role")

    with pytest.raises(ValidationError, match="dependency_role"):
        RelationDefinition.model_validate(raw_relation)


def test_relation_definition_rejects_annual_summary_relation_without_summary_role() -> None:
    modelos, _ = _committed_tree()
    relation = _modelo(modelos, "180").revisions["2023-y-siguientes"].relations[0]
    raw_relation = relation.model_dump(mode="python")
    raw_relation["dependency_role"] = "direct_calculation"

    with pytest.raises(ValidationError, match="annual summary relation"):
        RelationDefinition.model_validate(raw_relation)
