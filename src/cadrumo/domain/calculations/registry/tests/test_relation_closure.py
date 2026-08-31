"""Tests for registry cross-model relation closure."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingSourceKind
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources._boundary import bundled_path
from .....tests.registry_observations import registry_grounded_modelo_observation
from .._validate import RegistryValidator
from .._validate_relation_sources import (
    RelationSourceYearCoverageAllowance,
    validate_relation_closure,
    validate_slot_source_hygiene,
)
from ..binding_selector_utils import selector_as_dict
from ..bindings import RegistryModeloObservation
from ..errors import RegistryValidationError
from ..relations import (
    RegistryFoldRequirement,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from ..schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ..schema_surfaces import RelationDefinition, RelationPeriodAlignment, RelationRevisionSelector
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M115_BASE_CASILLA: CasillaId = validated_casilla_id("02", surface="_M115_BASE_CASILLA")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03", surface="_M115_RETENCIONES_CASILLA")
_UNKNOWN_SOURCE_CASILLA: CasillaId = validated_casilla_id("missing-output", surface="_UNKNOWN_SOURCE_CASILLA")


def _committed_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return _committed_registry_tree()


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


def test_registry_fold_requirement_rejects_non_modelo_id_source_modelo() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RegistryFoldRequirement.model_validate(
            {
                "source_modelo": "modelo-115",
                "filing_year": 2026,
                "periods": ("1T",),
                "source_casilla_ids": (_M115_BASE_CASILLA,),
            },
        )

    message = str(exc_info.value)
    assert "source_modelo" in message
    assert r"^\d{3}$" in message


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
            value = casilla_obs.value
            assert isinstance(value, Decimal)
            casilla_sums[casilla_obs.casilla_id] = casilla_sums.get(casilla_obs.casilla_id, Decimal("0")) + value

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


def test_registry_validator_rejects_dependency_classification_to_unknown_source_modelo() -> None:
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "100")
    revision = modelo.revisions["2025"]
    classification = next(
        item for item in revision.dependency_classifications if item.source_modelo == "303" and not item.relation_refs
    )
    mutated_classification = classification.model_copy(update={"source_modelo": "999"})
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                mutated_classification if item.id == classification.id else item
                for item in revision.dependency_classifications
            ),
        },
    )
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match=r"dependency classification .* unknown source modelo"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo),
        )


def test_registry_validator_rejects_relation_source_period_outside_source_revision() -> None:
    """A derived source period no source revision supports must refuse.

    This mutated modelo 180, whose relations source modelo 115 -- and 115 has
    exactly ONE revision. `_resolve_coordinate_owners` abstains when the source
    modelo contributes at most one candidate, because generated-export-tree
    validation runs against a candidate registry pruned to exactly one revision
    and refusing there would report the pruning rather than the registry. With a
    single-revision source that abstention swallows every period-support
    question, so the case asserted a refusal that could not reach it.

    Modelo 390 sources modelo 303, which has six revisions, so the check is
    reachable. The token is `0A`: the period GRAMMAR accepts it, and no 303
    revision declares it, which is exactly the shape this refusal is for. The
    old token `99` is not a valid period at all and is refused at the typed
    model boundary -- reachable here only because `model_copy` skips validation.
    """
    modelos, catalogues = _committed_tree()
    modelo = _modelo(modelos, "390")
    revision = modelo.revisions["2025"]
    relation = revision.relations[0].model_copy(update={"source_periods": ("1T", "0A")})
    mutated_revision = revision.model_copy(update={"relations": (relation, *revision.relations[1:])})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="is not supported by any selected source revision"):
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

    with pytest.raises(RegistryValidationError, match="lacks exact source revision coverage"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry((source_modelo, mutated_target))


def test_m303_2024_relation_coverage_unions_the_early_and_late_revisions() -> None:
    """The 2024 split is period-wise, never a spanning-revision fallback.

    The committed registry validates because 1T/2T and 3T/4T have distinct
    revision owners. Removing early 2T leaves the derived source coordinate
    for late 3T without an owner, which must be red rather than silently
    consulting a legacy 2023+ revision.
    """
    modelos, catalogues = _committed_tree()
    modelo_303 = _modelo(modelos, "303")
    early = modelo_303.revisions["2024-hasta-08-y-2t"]
    period_selector = early.period_selector.model_copy(
        update={"periods": tuple(period for period in early.period_selector.periods if period != "2T")},
    )
    mutated_early = early.model_copy(update={"period_selector": period_selector})
    mutated_303 = _with_revision(modelo_303, mutated_early)

    with pytest.raises(
        RegistryValidationError,
        match=r"lacks exact source revision coverage for derived period '2T' in source years 2024",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_303),
        )


def test_m303_first_quarter_history_requires_an_observation_backed_target() -> None:
    """2009/1T may read filed 2008/4T, but only as historical observation data."""
    modelos, catalogues = _committed_tree()
    modelo_303 = _modelo(modelos, "303")
    revision = modelo_303.revisions["2022"]
    binding_id = "modelo-303-compensacion-pendiente-anteriores"
    bindings = tuple(
        binding.model_copy(update={"source": BindingSourceKind.MANUAL_INPUT}) if binding.id == binding_id else binding
        for binding in revision.bindings
    )
    mutated_revision = revision.model_copy(update={"bindings": bindings})
    mutated_303 = _with_revision(modelo_303, mutated_revision)

    with pytest.raises(
        RegistryValidationError,
        # Source year 2021, not 2008. The refusal itself is unchanged -- what
        # moved is the year it names: the `2022` revision's look-back is the
        # preceding year, where the retired 2009-2022 span's earliest was 2008.
        match=r"lacks exact source revision coverage for derived period '4T' in source years 2021",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_303),
        )


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
    # Modelo 390's open-ended revision was split into exact-year revisions;
    # `2010-y-siguientes` no longer exists, so this died on the lookup.
    revision = target_modelo.revisions["2025"]
    source_revision = source_modelo.revisions["2022"]
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
    # Modelo 390's open-ended revision was split into exact-year revisions;
    # `2010-y-siguientes` no longer exists, so this died on the lookup.
    revision = target_modelo.revisions["2025"]
    source_revision = source_modelo.revisions["2022"]
    relation = next(item for item in revision.relations if item.id == "modelo-390-rel-303-cuota-devengada-total")
    source_casilla = next(item for item in source_revision.casillas if item.number != item.id)
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
    mutated_selector = {**selector_as_dict(binding), "source_casilla_ids": (revision_scoped_only,)}
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
    revision = modelo.revisions["2022"]
    binding = next(item for item in revision.bindings if item.id == "modelo-303-compensacion-pendiente-anteriores")
    selector = selector_as_dict(binding)
    source_casilla = next(item for item in revision.casillas if item.id == selector["source_casilla_id"])
    assert source_casilla.number != source_casilla.id

    noncanonical_source_id = validated_casilla_id(
        source_casilla.number,
        surface="previous_filing display token source casilla id",
    )
    mutated_selector = {**selector, "source_casilla_id": noncanonical_source_id}
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
        binding.model_copy(update={"source": BindingSourceKind.PREVIOUS_FILING}) if binding.id == target_id else binding
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
        binding.model_copy(update={"source": BindingSourceKind.PREVIOUS_FILING}) if binding.id == target_id else binding
        for binding in revision.bindings
    )
    mutated_revision = revision.model_copy(update={"bindings": mutated_bindings})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    with pytest.raises(RegistryValidationError, match="both a relation target_binding and a 'previous_filing'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(
            _replace_modelo(modelos, mutated_modelo),
        )


def test_slot_hygiene_rejects_non_wallet_relation_reusing_wallet_binding() -> None:
    """A wallet binding cannot exempt a second relation from the collision gate."""
    modelos, _catalogues = _committed_tree()
    modelo = _modelo(modelos, "303")
    revision = modelo.revisions["2022"]
    wallet_relation = next(
        relation for relation in revision.relations if relation.id == "modelo-303-rel-self-compensacion-anteriores"
    )
    reused_relation = wallet_relation.model_copy(update={"id": "modelo-303-rel-reused-wallet-binding"})
    mutated_revision = revision.model_copy(update={"relations": (*revision.relations, reused_relation)})
    mutated_modelo = _with_revision(modelo, mutated_revision)

    failures = validate_slot_source_hygiene(
        (mutated_modelo,),
        {mutated_modelo.id: mutated_modelo},
    )

    assert any("non-wallet relation target_binding" in failure for failure in failures)


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


# --------------------------------------------------------------------------
# Relation source-year coverage: structural future exclusion and allowlist.
#
# Modelo 100 is period-versioned per-year (each revision covers exactly one
# closed year, 2020-2025 today), unlike every EXISTING relation's source
# modelo, all of which are open-ended. No relation in the committed corpus
# yet pairs an open-ended consumer with a per-year-versioned source, so these
# tests attach a synthetic one to a REAL open-ended revision (Modelo 130's
# 2019-y-siguientes) reading a REAL per-year-closed one (Modelo 100), rather
# than mutating an existing relation's shape past what it can validly become.
# --------------------------------------------------------------------------

_TEST_RELATION_ID = "test-relation-m130-reads-m100-annual"
_M100_SOURCE_CASILLA: CasillaId = validated_casilla_id("0604", surface="_M100_SOURCE_CASILLA")


def _m130_relation_reading_m100(
    modelos: tuple[ModeloDefinition, ...],
    *,
    target_binding: str,
) -> tuple[tuple[ModeloDefinition, ...], RelationDefinition]:
    """Attach a relation reading Modelo 100 at filing_year_delta=-1 onto Modelo 130's open-ended revision.

    Modelo 130's own revision starts at 2019, so this relation requires
    Modelo 100 source years [2018, infinity): 2018-2019 predates Modelo
    100's own corpus floor (2020), and every year from 2026 onward is beyond
    Modelo 100's latest authored revision (2025) -- the structural "not yet
    published" case under test.

    ``target_binding`` is deliberately a parameter rather than fixed: it
    controls ``source_is_observation_history``
    (``_relation_is_prior_year_filing_carry``), which gates the EXISTING
    pre-modelled-history exception this module's own tests must not
    conflate with the NEW future-year one. Modelo 130's own
    ``irpf.previous_year_economic_activity_net_income`` binding is
    ``previous_filing``-sourced (observation-backed), so targeting it makes
    2018-2019 ALSO structurally excluded -- a real, first-hand finding of
    its own: once this concept's target binding becomes
    ``relation_prefill``-sourced (itself observation-backed) under the real
    migration, its 2018-2019 gap needs no allowlist entry at all. Targeting
    a ledger-sourced binding instead forces ``source_is_observation_history
    = False``, isolating a genuine, allowlist-eligible gap for the other
    tests below.
    """
    modelo_130 = _modelo(modelos, "130")
    revision = modelo_130.revisions["2019-y-siguientes"]
    relation = RelationDefinition(
        id=_TEST_RELATION_ID,
        kind="cross_model_output",
        dependency_role="direct_calculation",
        source_modelo="100",
        source_revision_selector=RelationRevisionSelector(filing_year_delta=-1),
        source_casilla_id=_M100_SOURCE_CASILLA,
        target_binding=target_binding,
        period_alignment=RelationPeriodAlignment(source_period="0A", target_period="0A", filing_year_delta=-1),
        source_periods=("0A",),
        target_periods=("1T", "2T", "3T", "4T"),
        legal_refs=("rd-439-2007:art-110", "orden-eha-672-2007:art-1", "ley-35-2006:art-99", "rd-439-2007:art-95"),
        source_refs=("aeat-dr-130-2019-v12", "aeat-modelo-130-instructions"),
    )
    mutated_revision = revision.model_copy(update={"relations": (*revision.relations, relation)})
    mutated_modelo = _with_revision(modelo_130, mutated_revision)
    return _replace_modelo(modelos, mutated_modelo), relation


def test_an_observation_backed_carry_is_silent_on_both_sides_needing_no_allowance() -> None:
    """A real, first-hand finding: an observation-backed carry needs no allowlist entry at all.

    Targeting Modelo 130's own ``previous_filing``-sourced binding makes
    this relation an observation-backed carry, so BOTH structural
    exclusions apply at once: the EXISTING pre-modelled-history one covers
    2018-2019 and the NEW future-year one covers 2026 onward. Zero failures
    proves the real migration's own eventual relation (whose target binding
    becomes ``relation_prefill`` -- itself observation-backed) needs no
    allowlist entry for the 2018-2019 range the old ``previous_filing``
    mechanism's own allowance was written for.
    """
    modelos, _catalogues = _committed_tree()
    mutated_modelos, _relation = _m130_relation_reading_m100(
        modelos,
        target_binding="irpf.previous_year_economic_activity_net_income",
    )
    modelos_by_id = {modelo.id: modelo for modelo in mutated_modelos}

    failures = validate_relation_closure(mutated_modelos, modelos_by_id)

    assert failures == []


def test_a_non_observation_backed_relation_is_silent_beyond_its_latest_year_but_not_before_it() -> None:
    """The NEW future-year exclusion is unconditional; the pre-modelled-history one stays scoped.

    Targeting a ledger-sourced binding forces ``source_is_observation_history
    = False``, so the EXISTING pre-modelled-history exception does not apply
    and the genuine 2018-2019 gap surfaces as an ordinary failure. Without
    the NEW future-year exclusion, an open-ended consumer (Modelo 130)
    reading a per-year-closed source (Modelo 100) would ALSO fail
    perpetually for every year beyond Modelo 100's latest authored revision
    -- a standing, undischargeable failure no allowlist entry could ever
    satisfy -- so nothing beyond 2025 may be reported either.
    """
    modelos, _catalogues = _committed_tree()
    mutated_modelos, relation = _m130_relation_reading_m100(
        modelos,
        target_binding="modelo-130-actividad-economica-ingresos-cumulative",
    )
    modelos_by_id = {modelo.id: modelo for modelo in mutated_modelos}

    failures = validate_relation_closure(mutated_modelos, modelos_by_id)

    assert any(
        "lacks exact source revision coverage" in failure and "2018-2019" in failure and relation.id in failure
        for failure in failures
    ), failures
    # Nothing beyond Modelo 100's latest authored year (2025) is ever
    # reported. If the structural exclusion regressed, this gate would fail
    # perpetually for every later year and this assertion would catch it.
    assert not any(str(year) in failure for year in range(2026, 2031) for failure in failures), failures


def test_allowance_suppresses_the_genuine_gap_and_reports_a_stale_entry() -> None:
    """A matching allowance suppresses its finding; a non-matching one is reported stale."""
    modelos, _catalogues = _committed_tree()
    mutated_modelos, relation = _m130_relation_reading_m100(
        modelos,
        target_binding="modelo-130-actividad-economica-ingresos-cumulative",
    )
    modelos_by_id = {modelo.id: modelo for modelo in mutated_modelos}

    matching_allowance = RelationSourceYearCoverageAllowance(
        relation_id=relation.id,
        source_modelo="100",
        source_period="0A",
        missing_from_year=2018,
        missing_through_year=2019,
        reason="test fixture: Modelo 100's own corpus floor (2020) postdates this relation's own start (2019).",
        discharge="Author Modelo 100 registry revisions for filing years 2018 and 2019.",
    )
    stale_allowance = RelationSourceYearCoverageAllowance(
        relation_id=relation.id,
        source_modelo="100",
        source_period="0A",
        missing_from_year=2015,
        missing_through_year=2016,
        reason="test fixture: an allowance that does not match any real finding.",
        discharge="n/a -- this entry exists only to prove staleness detection.",
    )
    failures = validate_relation_closure(
        mutated_modelos,
        modelos_by_id,
        source_year_coverage_allowances=(matching_allowance, stale_allowance),
    )

    assert not any("2018-2019" in failure and "lacks" in failure for failure in failures), failures
    assert any(
        "stale relation source-year-coverage allowance" in failure and "2015" in failure and "2016" in failure
        for failure in failures
    ), failures


def test_a_widened_gap_is_not_silently_absorbed_by_the_narrower_allowance() -> None:
    """The same START year with a LARGER end must not match the documented allowance.

    Dropping Modelo 100's 2020 revision from the candidate set widens the
    relation's missing range from 2018-2019 to 2018-2020. An allowance
    naming 2018 THROUGH 2019 specifically must not silently absorb the
    wider gap -- the match is exact, not start-year-only.
    """
    modelos, _catalogues = _committed_tree()
    mutated_modelos, relation = _m130_relation_reading_m100(
        modelos,
        target_binding="modelo-130-actividad-economica-ingresos-cumulative",
    )
    modelo_100 = _modelo(mutated_modelos, "100")
    mutated_100 = modelo_100.model_copy(
        update={"revisions": {rid: rev for rid, rev in modelo_100.revisions.items() if rid != "2020"}},
    )
    mutated_modelos = _replace_modelo(mutated_modelos, mutated_100)
    modelos_by_id = {modelo.id: modelo for modelo in mutated_modelos}

    matching_allowance = RelationSourceYearCoverageAllowance(
        relation_id=relation.id,
        source_modelo="100",
        source_period="0A",
        missing_from_year=2018,
        missing_through_year=2019,
        reason="test fixture, deliberately too narrow for the widened gap below.",
        discharge="n/a",
    )
    failures = validate_relation_closure(
        mutated_modelos,
        modelos_by_id,
        source_year_coverage_allowances=(matching_allowance,),
    )

    assert any("2018-2020" in failure and relation.id in failure for failure in failures), failures
    assert any("stale relation source-year-coverage allowance" in failure for failure in failures), failures


class TestSourceUpperBound:
    """Pure unit coverage for the future-year structural exclusion helpers."""

    def test_an_open_ended_candidate_has_no_ceiling(self) -> None:
        from .._validate_relation_periods import _is_beyond_latest_modelled_source_year, _source_upper_bound

        modelos, _catalogues = _committed_tree()
        m115_revision = _modelo(modelos, "115").revisions["2019-y-siguientes"]

        assert _source_upper_bound((m115_revision,)) is None
        assert _is_beyond_latest_modelled_source_year(2099, (m115_revision,)) is False

    def test_closed_per_year_candidates_bound_at_the_latest_year(self) -> None:
        from .._validate_relation_periods import _is_beyond_latest_modelled_source_year, _source_upper_bound

        modelos, _catalogues = _committed_tree()
        m100_revisions = tuple(_modelo(modelos, "100").revisions.values())

        assert _source_upper_bound(m100_revisions) == 2025
        assert _is_beyond_latest_modelled_source_year(2026, m100_revisions) is True
        assert _is_beyond_latest_modelled_source_year(2025, m100_revisions) is False
