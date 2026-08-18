"""Real-binary tests for the reviewed DP30302 semantic field matrix."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core import M303RegimenSimplificadoFact, compile_filing_projection_ref
from cadrumo.domain.calculations.registry import (
    RegistryValidationError,
    bundled_authority,
)
from dev._paths import REPO_ROOT

from ..analysis import _dp30302_field_matrix
from ..analysis._dp30302_field_matrix import (
    DP30302_EPOCH_COORDINATES,
    DP30302_EPOCHS,
    DP30302EpochFieldMatrix,
    DP30302FieldPartition,
    DP30302RepeatingModuleFamily,
    DP30302RepeatingModuleFamilyEpoch,
    classify_dp30302_field_description,
    dp30302_activity_slot,
    generalize_dp30302_field_description,
    load_dp30302_epoch_intermediates,
    load_dp30302_field_matrix,
    measure_dp30302_field_matrix,
    resolve_dp30302_module_sub_indices,
)
from ..pipeline._record_design_ir import RecordDesignIntermediateField

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ARTEFACT_PATH = Path(__file__).resolve().parent.parent / "dp30302_field_matrix.toml"


def _dp30302_sheets() -> dict[str, tuple[RecordDesignIntermediateField, ...]]:
    """Load every epoch's real DP30302 field set through validated snapshots."""
    out: dict[str, tuple[RecordDesignIntermediateField, ...]] = {}
    for intermediate in load_dp30302_epoch_intermediates(bundled_authority()):
        sheet = next(sheet for sheet in intermediate.sheets if sheet.record_identity == "DP30302")
        out[intermediate.source.design_epoch] = sheet.fields
    return out


# --- classification exhaustiveness (structural property, not a tally) ------


def test_every_real_dp30302_field_across_all_five_epochs_classifies_without_refusal() -> None:
    """The six reviewed partitions must be exhaustive over every real anchor."""
    for epoch, fields in _dp30302_sheets().items():
        partitions = [classify_dp30302_field_description(field.normalized_description) for field in fields]
        assert len(partitions) == len(fields), epoch
        # Disjointness and exhaustiveness are structural: classify returns exactly
        # one enum member per field or raises, so summing per-partition counts
        # always reconstructs the total by construction. The real assertion is
        # that no field required the fail-closed branch below.
        assert all(isinstance(partition, DP30302FieldPartition) for partition in partitions)


def test_classify_refuses_a_description_outside_the_six_reviewed_shapes() -> None:
    """A description matching none of the reviewed shapes must fail closed."""
    with pytest.raises(RegistryValidationError, match="does not resolve to a reviewed partition"):
        classify_dp30302_field_description("Something AEAT never actually printed")


def test_classify_distinguishes_numbered_boxes_from_per_activity_letter_operands() -> None:
    """A trailing single-letter operand must never be mistaken for an official box."""
    assert (
        classify_dp30302_field_description(
            "Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Cuota mínima [L]",
        )
        is DP30302FieldPartition.NO_AGRICOLA
    )
    assert (
        classify_dp30302_field_description(
            "Liquidación (3) - RS - Resultado RS ( [54] - [57] ) [58]",
        )
        is DP30302FieldPartition.NUMBERED
    )


# --- sub-index resolution (structural property) -----------------------------


def test_module_sub_indices_are_contiguous_and_gapless_against_real_fields() -> None:
    """Every repeating module family must resolve to a dense 1..N sub-index run."""
    for epoch, fields in _dp30302_sheets().items():
        sub_indices = resolve_dp30302_module_sub_indices(fields)
        groups: dict[tuple[int, str], list[int]] = {}
        for field in fields:
            slot = dp30302_activity_slot(field.normalized_description)
            if slot is None:
                continue
            key = (slot, generalize_dp30302_field_description(field.normalized_description))
            groups.setdefault(key, []).append(sub_indices[field.ordinal])
        for key, indices in groups.items():
            assert sorted(indices) == list(range(1, len(indices) + 1)), (epoch, key, indices)


def test_resolve_module_sub_indices_refuses_a_duplicate_ordinal_within_one_group() -> None:
    """A corrupted or re-partitioned anchor sharing an ordinal must refuse, not guess an order."""
    fields = _dp30302_sheets()["2023"]
    mesas_capacidad = [
        field
        for field in fields
        if generalize_dp30302_field_description(field.normalized_description).endswith("Módulo Mesas - Capacidad")
        and dp30302_activity_slot(field.normalized_description) == 1
    ]
    assert len(mesas_capacidad) >= 2
    corrupted = mesas_capacidad[0].model_copy(update={"ordinal": mesas_capacidad[1].ordinal})
    perturbed = (corrupted, mesas_capacidad[1], *mesas_capacidad[2:])

    with pytest.raises(RegistryValidationError, match="duplicate ordinals"):
        resolve_dp30302_module_sub_indices(perturbed)


# --- persisted artefact freshness (anti-drift roundtrip) --------------------


def test_persisted_matrix_matches_a_fresh_measurement_of_the_five_binaries() -> None:
    """The checked-in artefact must still describe the live hash-pinned binaries."""
    persisted = load_dp30302_field_matrix(_ARTEFACT_PATH)
    live = measure_dp30302_field_matrix(bundled_authority())
    assert persisted == live


def test_every_epoch_measurement_uses_its_selected_validated_registry_inspection() -> None:
    """The parser may read only the source the selected M303 revision admits."""
    authority = bundled_authority()
    intermediates = load_dp30302_epoch_intermediates(authority)
    assert len(intermediates) == len(DP30302_EPOCH_COORDINATES)
    for coordinate, intermediate in zip(DP30302_EPOCH_COORDINATES, intermediates, strict=True):
        inspection = authority.inspect_revision("303", filing_year=coordinate.filing_year, period=coordinate.period)
        assert intermediate.source.source_ref == coordinate.source_ref
        assert intermediate.source.source_ref in inspection.revision_source_refs
        assert inspection.sources[coordinate.source_ref].sha256 == intermediate.source.source_sha256


def test_persisted_matrix_reflects_the_two_corrected_constants() -> None:
    """The artefact must retain the two corrections, not the earlier deficit-audit constants."""
    persisted = load_dp30302_field_matrix(_ARTEFACT_PATH)
    by_epoch = {epoch.epoch: epoch for epoch in persisted.epochs}
    assert tuple(by_epoch[epoch].no_agricola for epoch in DP30302_EPOCHS) == (114, 110, 116, 122, 122)
    assert tuple(by_epoch[epoch].agricola for epoch in DP30302_EPOCHS) == (20, 20, 24, 20, 20)
    assert tuple(by_epoch[epoch].simplified for epoch in DP30302_EPOCHS) == (134, 130, 140, 142, 142)


def test_real_dp30302_anchors_keep_other_countries_refund_distinct_from_quarterly_quotas() -> None:
    """The two adjacent 4T concepts are distinct typed declarations, never a shared fact."""
    fields = _dp30302_sheets()["2023"]
    descriptions = tuple(field.normalized_description for field in fields)
    assert any("Devolución cuotas soportadas otros países" in item for item in descriptions)
    assert any("Cuotas soportadas - 4T" in item for item in descriptions)

    endpoint_path = (
        REPO_ROOT
        / "src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023/projection_endpoints"
        / "0001-projection-endpoints.toml"
    )
    payload = tomllib.loads(endpoint_path.read_text(encoding="utf-8"))
    refs = tuple(
        compile_filing_projection_ref(item["projection_ref"])
        for item in payload["revisions"]["2023"]["projection_endpoints"]
    )
    non_agricultural_slot_one = {
        ref.fact
        for ref in refs
        if getattr(ref, "projection_kind", None) == "m303_regimen_simplificado_fact"
        and ref.cohort.value == "no_agricola"
        and ref.slot == 1
    }
    assert M303RegimenSimplificadoFact.DEVOLUCION_CUOTAS_SOPORTADAS_OTROS_PAISES in non_agricultural_slot_one
    assert M303RegimenSimplificadoFact.CUOTAS_SOPORTADAS_CUARTO_TRIMESTRE in non_agricultural_slot_one


def test_real_dp30302_declarations_keep_the_reviewed_epoch_multiplicity() -> None:
    """The hash-pinned designs, rather than a generated count, govern every repeated fact."""
    root = REPO_ROOT / "src/cadrumo/_data/registry/aeat/modelos/303/revisions"
    expected = {
        "2023": (208, 134, {"superficie_horno_dias_cuarto_trimestre": {None}}),
        "2024-hasta-08-y-2t": (204, 130, {"superficie_horno_dias_cuarto_trimestre": {None}}),
        "2024-desde-09-y-3t": (214, 140, {"superficie_horno_dias_cuarto_trimestre": {None}}),
        "2025": (
            216,
            142,
            {
                "superficie_horno_dias_cuarto_trimestre": {1, 2, 3, 4},
                "superficie_horno_cuarto_trimestre": {1, 2, 3, 4},
            },
        ),
        "2026-y-siguientes": (
            216,
            142,
            {
                "superficie_horno_dias_cuarto_trimestre": {1, 2, 3, 4},
                "superficie_horno_cuarto_trimestre": {1, 2, 3, 4},
            },
        ),
    }
    always_repeated = {
        "mesas_capacidad",
        "mesas_dias_cuarto_trimestre",
        "mesas_numero",
    }

    for revision_id, (total, simplified, epoch_specific) in expected.items():
        path = root / revision_id / "projection_endpoints/0001-projection-endpoints.toml"
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        endpoints = payload["revisions"][revision_id]["projection_endpoints"]
        simplified_endpoints = tuple(
            item
            for item in endpoints
            if item["projection_ref"].get("projection_kind", "").startswith("m303_regimen_simplificado_")
        )
        simplified_refs = tuple(
            compile_filing_projection_ref(item["projection_ref"])
            for item in simplified_endpoints
            if item["projection_ref"].get("projection_kind") == "m303_regimen_simplificado_fact"
        )
        assert len(endpoints) == total
        assert len(simplified_endpoints) == simplified
        for fact in always_repeated:
            assert {
                ref.sub_index
                for ref in simplified_refs
                if ref.fact.value == fact and ref.cohort.value == "no_agricola" and ref.slot == 1
            } == {1, 2, 3, 4}
        for fact, sub_indices in epoch_specific.items():
            assert {
                ref.sub_index
                for ref in simplified_refs
                if ref.fact.value == fact and ref.cohort.value == "no_agricola" and ref.slot == 1
            } == sub_indices


def test_persisted_matrix_carries_a_family_whose_cardinality_transitions_across_epochs() -> None:
    """At least one repeating family must genuinely vary rather than being a flat constant."""
    persisted = load_dp30302_field_matrix(_ARTEFACT_PATH)
    cardinalities_by_family = [
        {entry.epoch: entry.sub_index_cardinality for entry in family.epochs}
        for family in persisted.repeating_module_families
    ]
    assert any(len(set(cardinalities.values())) > 1 for cardinalities in cardinalities_by_family)


def test_a_repartitioned_real_anchor_desynchronises_the_persisted_matrix() -> None:
    """A changed real input anchor must produce an observable persisted-matrix mismatch."""
    persisted = load_dp30302_field_matrix(_ARTEFACT_PATH)
    intermediate = next(
        item for item in load_dp30302_epoch_intermediates(bundled_authority()) if item.source.design_epoch == "2023"
    )
    sheet = next(item for item in intermediate.sheets if item.record_identity == "DP30302")
    anchor = next(
        field
        for field in sheet.fields
        if field.normalized_description
        == "Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Epigrafe IAE"
    )
    repartitioned_anchor = anchor.model_copy(update={"normalized_description": "Reservado para la AEAT"})
    repartitioned_sheet = sheet.model_copy(
        update={
            "fields": tuple(
                repartitioned_anchor if field.ordinal == anchor.ordinal else field for field in sheet.fields
            ),
        },
    )
    repartitioned_intermediate = intermediate.model_copy(
        update={
            "sheets": tuple(
                repartitioned_sheet if item.record_identity == "DP30302" else item for item in intermediate.sheets
            ),
        },
    )
    reclassified_epoch, _, _ = _dp30302_field_matrix._measure_dp30302_epoch(
        repartitioned_intermediate,
        epoch="2023",
    )
    persisted_epoch = next(epoch for epoch in persisted.epochs if epoch.epoch == "2023")
    assert reclassified_epoch.no_agricola == persisted_epoch.no_agricola - 1
    assert reclassified_epoch.reserve == persisted_epoch.reserve + 1


# --- schema invariants (bite-provable structurally, no real binary needed) --


def test_epoch_matrix_refuses_a_partition_sum_that_does_not_equal_the_total() -> None:
    with pytest.raises(ValidationError, match="expected total"):
        DP30302EpochFieldMatrix(
            epoch="2023",
            source_ref="aeat-dr-303-2023",
            source_sha256="0" * 64,
            total=153,
            agricola=20,
            no_agricola=114,
            simplified=134,
            numbered=12,
            constant=5,
            reserve=1,
            producer=0,  # deliberately wrong: sums to 152, not 153
        )


def test_epoch_matrix_refuses_a_simplified_count_that_is_not_its_two_cohort_total() -> None:
    with pytest.raises(ValidationError, match="must equal agrícola plus no agrícola"):
        DP30302EpochFieldMatrix(
            epoch="2023",
            source_ref="aeat-dr-303-2023",
            source_sha256="0" * 64,
            total=153,
            agricola=20,
            no_agricola=114,
            simplified=133,
            numbered=12,
            constant=5,
            reserve=1,
            producer=1,
        )


def test_repeating_family_refuses_a_cardinality_that_never_exceeds_one() -> None:
    with pytest.raises(ValidationError, match="never exceeds one occurrence per slot"):
        DP30302RepeatingModuleFamily(
            generalized_description="not actually repeating",
            epochs=(DP30302RepeatingModuleFamilyEpoch(epoch="2023", sub_index_cardinality=1),),
        )


def test_repeating_family_refuses_an_unknown_epoch_name() -> None:
    with pytest.raises(ValidationError, match="unknown epoch"):
        DP30302RepeatingModuleFamily(
            generalized_description="a family",
            epochs=(
                DP30302RepeatingModuleFamilyEpoch(epoch="2027", sub_index_cardinality=4),
                DP30302RepeatingModuleFamilyEpoch(epoch="2023", sub_index_cardinality=1),
            ),
        )


def test_load_dp30302_field_matrix_refuses_a_missing_path(tmp_path: Path) -> None:
    with pytest.raises(RegistryValidationError, match="must be a real file"):
        load_dp30302_field_matrix(tmp_path / "does-not-exist.toml")
