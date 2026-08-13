"""Real-binary tests for the reviewed DP30302 semantic field matrix."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    RegistryValidationError,
    SourceReference,
    SourceRefId,
    load_catalogue_file,
)

from .. import _dp30302_field_matrix
from .._dp30302_field_matrix import (
    DP30302_EPOCHS,
    DP30302EpochFieldMatrix,
    DP30302FieldPartition,
    DP30302RepeatingModuleFamily,
    DP30302RepeatingModuleFamilyEpoch,
    classify_dp30302_field_description,
    dp30302_activity_slot,
    generalize_dp30302_field_description,
    load_dp30302_field_matrix,
    measure_dp30302_field_matrix,
    resolve_dp30302_module_sub_indices,
)
from .._record_design_ir import RecordDesignIntermediateField, load_record_design_intermediate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ARTEFACT_PATH = Path(__file__).resolve().parent.parent / "dp30302_field_matrix.toml"


def _iva_sources() -> Mapping[SourceRefId, SourceReference]:
    return load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml")).sources


def _dp30302_sheets() -> dict[str, tuple[RecordDesignIntermediateField, ...]]:
    """Load every epoch's real DP30302 field set through the shipped parser."""
    source_root = bundled_path()
    sources = _iva_sources()
    out: dict[str, tuple[RecordDesignIntermediateField, ...]] = {}
    for source_ref, filing_year, epoch in (
        ("aeat-dr-303-2023", 2023, "2023"),
        ("aeat-dr-303-2024-early", 2024, "2024-early"),
        ("aeat-dr-303-2024-late", 2024, "2024-late"),
        ("aeat-dr-303-2025", 2025, "2025"),
        ("aeat-dr-303-2026", 2026, "2026"),
    ):
        intermediate = load_record_design_intermediate(
            source_root,
            sources,
            source_ref=source_ref,
            filing_year=filing_year,
            design_epoch=epoch,
        )
        sheet = next(sheet for sheet in intermediate.sheets if sheet.record_identity == "DP30302")
        out[epoch] = sheet.fields
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
    live = measure_dp30302_field_matrix(bundled_path(), _iva_sources())
    assert persisted == live


def test_persisted_matrix_reflects_the_two_corrected_constants() -> None:
    """The artefact must retain the two corrections, not the earlier deficit-audit constants."""
    persisted = load_dp30302_field_matrix(_ARTEFACT_PATH)
    by_epoch = {epoch.epoch: epoch for epoch in persisted.epochs}
    assert tuple(by_epoch[epoch].no_agricola for epoch in DP30302_EPOCHS) == (114, 110, 116, 122, 122)
    assert tuple(by_epoch[epoch].agricola for epoch in DP30302_EPOCHS) == (20, 20, 24, 20, 20)
    assert tuple(by_epoch[epoch].simplified for epoch in DP30302_EPOCHS) == (134, 130, 140, 142, 142)


def test_persisted_matrix_carries_a_family_whose_cardinality_transitions_across_epochs() -> None:
    """At least one repeating family must genuinely vary rather than being a flat constant."""
    persisted = load_dp30302_field_matrix(_ARTEFACT_PATH)
    cardinalities_by_family = [
        {entry.epoch: entry.sub_index_cardinality for entry in family.epochs}
        for family in persisted.repeating_module_families
    ]
    assert any(len(set(cardinalities.values())) > 1 for cardinalities in cardinalities_by_family)


def test_a_reclassified_anchor_would_desynchronise_the_persisted_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulating a re-partitioned anchor must make the live measurement diverge from the artefact."""
    persisted = load_dp30302_field_matrix(_ARTEFACT_PATH)

    real_classify = _dp30302_field_matrix.classify_dp30302_field_description

    def _misclassify_one_no_agricola_field_as_constant(description: str) -> DP30302FieldPartition:
        if description == ("Liquidación (3) - RS - (B) Actividades en RS (exc. a, g y f) - Actividad 1 - Epigrafe IAE"):
            return DP30302FieldPartition.CONSTANT
        return real_classify(description)

    monkeypatch.setattr(
        _dp30302_field_matrix,
        "classify_dp30302_field_description",
        _misclassify_one_no_agricola_field_as_constant,
    )

    live_with_reclassification = measure_dp30302_field_matrix(bundled_path(), _iva_sources())
    assert live_with_reclassification != persisted
    reclassified_epoch = next(epoch for epoch in live_with_reclassification.epochs if epoch.epoch == "2023")
    persisted_epoch = next(epoch for epoch in persisted.epochs if epoch.epoch == "2023")
    assert reclassified_epoch.no_agricola == persisted_epoch.no_agricola - 1
    assert reclassified_epoch.constant == persisted_epoch.constant + 1


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
            numbered=12,
            constant=5,
            reserve=1,
            producer=0,  # deliberately wrong: sums to 152, not 153
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
