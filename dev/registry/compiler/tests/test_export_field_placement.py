"""Teeth for the fixed-width placement check on export records.

Every defect is planted in a COPY of the shipped Modelo 296 tree and reached
through the real loader and the real
:class:`~dev.registry.compiler.validator.RegistryValidator` entry point, never
through a hand-built model: the loader is what merges a record's fragments into
the single field list the check reads, and a defect that only a hand-built model
can express proves nothing about the corpus.

Modelo 296's ``perceptor`` record is the carrier because its opening fields are
adjacent single-digit and three-digit literals, so shortening one by two opens a
gap of exactly two positions and lengthening it by two claims exactly two
positions twice, with no other declaration disturbed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ...conformance.stamp import bundled_registry_root
from ..loader import load_modelo_directory, load_shared_catalogues
from ..validate_export_field_placement import (
    binding_export_spans,
    export_record_placement_advisories,
    record_placed_spans,
    validate_export_record_field_placement,
)
from ..validator import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_REVISION = "2024-y-siguientes"
_PERCEPTOR_RECORD = Path("revisions") / _REVISION / "export" / "0002-record-m296-perceptor.toml"

#: The shipped declaration of the second perceptor field: a three-position
#: literal at position 2, immediately followed by a field at position 5.
_SHIPPED_SECOND_FIELD = "id = 'm296-2024.perceptor.f002'\noffset = 2\nlength = 3\n"


def _modelo_296_with_second_field_length(tmp_path: Path, *, length: int) -> Path:
    """Copy the shipped Modelo 296 tree, re-declaring one field's position count."""
    modelo_dir = tmp_path / "296"
    shutil.copytree(bundled_registry_root() / "modelos" / "296", modelo_dir)
    record = modelo_dir / _PERCEPTOR_RECORD
    text = record.read_text(encoding="utf-8")
    assert _SHIPPED_SECOND_FIELD in text
    record.write_text(
        text.replace(_SHIPPED_SECOND_FIELD, _SHIPPED_SECOND_FIELD.replace("length = 3", f"length = {length}")),
        encoding="utf-8",
    )
    return modelo_dir


def _placement_refusal_lines(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Return the PLACEMENT lines the real validator accumulates for one modelo.

    The validator raises on its whole accumulated failure list, and the shared
    catalogues carry grounding failures of their own that have nothing to do
    with placement. Filtering to the placement lines keeps these teeth measuring
    the check under test instead of the catalogue's current state, and keeps a
    silent expectation expressible: no placement line at all.
    """
    validator = RegistryValidator(load_shared_catalogues(bundled_registry_root()), source_root=bundled_path())
    try:
        validator.validate_modelo(modelo)
    except RegistryValidationError as refusal:
        return tuple(line for line in str(refusal).splitlines() if "OVERLAP:" in line or "GAP:" in line)
    return ()


def _placement_advisories(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Collect the placement advisories every record of one modelo reports."""
    return tuple(
        advisory
        for revision_id, revision in modelo.revisions.items()
        for layout in revision.export_layouts
        for record in layout.records
        for advisory in export_record_placement_advisories(
            prefix=f"modelo {modelo.id} revision {revision_id}",
            record=record,
            binding_spans=binding_export_spans(revision),
        )
    )


def test_a_planted_overlap_is_refused_naming_the_fields_and_the_positions(tmp_path: Path) -> None:
    """Two positions claimed twice must refuse, and say which two.

    Lengthening the three-position literal at position 2 to five makes it run to
    position 6 while its neighbour still starts at 5, so positions 5 and 6 carry
    two declarations. A refusal that named only the record would leave the
    author to find the pair by hand.
    """
    modelo = load_modelo_directory(_modelo_296_with_second_field_length(tmp_path, length=5))

    refusals = _placement_refusal_lines(modelo)

    assert len(refusals) == 1
    assert "OVERLAP" in refusals[0]
    assert "'m296-perceptor'" in refusals[0]
    assert "'m296-2024.perceptor.f002'" in refusals[0]
    assert "'m296-2024.perceptor.f003'" in refusals[0]
    assert "positions 5-6 are written twice" in refusals[0]


def test_a_planted_gap_is_reported_naming_the_fields_and_the_positions(tmp_path: Path) -> None:
    """Two positions nobody writes must be reported, and say which two.

    Shortening the same literal to one position leaves 3 and 4 undeclared. The
    report is an advisory rather than a refusal while the authored corpus still
    carries the population the check's module docstring measures, so the gate is
    the advisory's content, not an exception.
    """
    modelo = load_modelo_directory(_modelo_296_with_second_field_length(tmp_path, length=1))

    planted = [
        advisory
        for advisory in _placement_advisories(modelo)
        if "'m296-2024.perceptor.f002'" in advisory and "'m296-perceptor'" in advisory
    ]

    assert len(planted) == 1
    assert "GAP" in planted[0]
    assert "'m296-2024.perceptor.f003'" in planted[0]
    assert "leaving positions 3-4 unwritten" in planted[0]


def test_the_shipped_perceptor_record_reports_neither_defect(tmp_path: Path) -> None:
    """The unmodified carrier is silent, so both teeth prove the plant and not the record."""
    modelo_dir = tmp_path / "296"
    shutil.copytree(bundled_registry_root() / "modelos" / "296", modelo_dir)
    modelo = load_modelo_directory(modelo_dir)

    assert _placement_advisories(modelo) == ()
    assert _placement_refusal_lines(modelo) == ()


def test_a_casilla_split_across_two_consecutive_fields_passes() -> None:
    """One casilla rendered as two adjacent slots is coverage-complete.

    Modelo 296's 2024 casilla 03 is declared as an integer part at position 160
    running 13 positions and its fractional digits at 173 running 2. The two
    slots meet exactly, so placement is complete and the split must not be read
    as either defect. Asserted against the shipped declaration so the case stays
    the real one.
    """
    modelo = load_modelo_directory(bundled_registry_root() / "modelos" / "296")
    declarante = next(
        record
        for layout in modelo.revisions[_REVISION].export_layouts
        for record in layout.records
        if record.id == "m296-declarante"
    )
    split = tuple(field for field in declarante.fields if str(field.casilla_id) == "03")

    assert tuple((field.offset, field.length) for field in split) == ((160, 13), (173, 2))
    prefix = f"modelo {modelo.id} revision {_REVISION}"
    assert validate_export_record_field_placement(prefix=prefix, record=declarante) == []
    assert export_record_placement_advisories(prefix=prefix, record=declarante) == ()


def test_a_binding_derived_record_is_judged_on_its_binding_spans_too() -> None:
    """Modelo 720's head is declared by bindings, and must not read as unwritten.

    The ``type_1`` record declares ONE inline field, a reserved tail at position
    181. Its first 180 positions come from the fixed export selectors of the
    bindings naming ``type_1``. Judged on the inline field alone the record
    looks like 180 unclaimed opening positions; judged on both declaration
    sites it is contiguous from position 1. This is the case that decides
    whether the check reports a real defect or its own blind spot.
    """
    modelo = load_modelo_directory(bundled_registry_root() / "modelos" / "720")
    revision_id, revision = next(iter(modelo.revisions.items()))
    record = next(
        candidate
        for layout in revision.export_layouts
        for candidate in layout.records
        if candidate.id == "modelo-720-type-1"
    )
    prefix = f"modelo {modelo.id} revision {revision_id}"
    spans = binding_export_spans(revision)

    inline_only = record_placed_spans(record)
    assert len(inline_only) == 1
    assert inline_only[0].offset == 181
    assert export_record_placement_advisories(prefix=prefix, record=record)[0].startswith(
        f"{prefix}: export record 'modelo-720-type-1' RECORD_STARTS_LATE",
    )

    with_bindings = record_placed_spans(record, spans)
    assert len(with_bindings) > len(inline_only)
    assert with_bindings[0].offset == 1
    assert export_record_placement_advisories(prefix=prefix, record=record, binding_spans=spans) == ()
    assert validate_export_record_field_placement(prefix=prefix, record=record, binding_spans=spans) == []
