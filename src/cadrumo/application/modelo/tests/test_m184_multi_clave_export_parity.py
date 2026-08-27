"""Modelo 184 socio export renders one occurrence per (member, clave, subclave).

The record used to render a single fixed occurrence (S289's own finding), and
its natural key was ``nif`` alone, so a member declaring income under two
different claves -- an ordinary case, e.g. capital mobiliario alongside
capital inmobiliario -- either truncated to one clave or collided the two
rows into one during the two-source union. This module proves both defects
are gone against the REAL bundled registry revision and the real production
code paths: :func:`resolve_atribucion_binding_row_values`,
:func:`_record_render_rows`, and :func:`union_detail_rows_by_identity`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.detail_record_bindings import (
    AtributionMemberObservation,
    resolve_atribucion_binding_row_values,
)
from ....domain.calculations.registry.export import derive_export_layouts_from_bindings
from ....domain.calculations.registry.loader import load_registry_tree
from ....domain.calculations.registry.schema_exports import ExportRecordDefinition
from ....domain.modelos import Modelo184MemberRow
from ...filing._record_renderer import _record_render_rows
from .._action_errors import ModeloAggregationBindingError
from .._calculation_modelo_adjustments import union_detail_rows_by_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REVISION = "2025-y-siguientes"


def _revision():
    from ....core.resources import bundled_path

    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return next(modelo for modelo in modelos if modelo.id == "184").revisions[_REVISION]


def _socio_record(revision) -> ExportRecordDefinition:
    return next(
        candidate
        for layout in derive_export_layouts_from_bindings(revision)
        for candidate in layout.records
        if candidate.id == "m184-socio"
    )


def _observation(
    *,
    source_id: str,
    nif: str,
    name: str,
    share: str,
    base: str,
    clave: str,
    subclave: str | None = None,
    **extra: object,
) -> AtributionMemberObservation:
    from datetime import date

    return AtributionMemberObservation(
        source_id=source_id,
        member_tax_id=nif,
        member_legal_name=name,
        transaction_date=date(2025, 1, 1),
        share_percentage=Decimal(share),
        base_imponible_assigned=Decimal(base),
        clave=clave,
        subclave=subclave,
        **extra,
    )


def test_socio_record_is_wired_for_row_indexed_binding_rendering() -> None:
    """Guard the premise: the record this module measures is the fixed shape.

    Without this, every assertion below would pass vacuously against a record
    that reverted to a single fixed occurrence.
    """
    record = _socio_record(_revision())

    assert record.repeat == "binding_rows"
    assert record.binding_record == "miembro"


def test_two_members_each_declaring_one_clave_resolve_two_distinct_rows() -> None:
    """The baseline shape: two members, one clave each, two row indices."""
    revision = _revision()
    observations = (
        _observation(source_id="m1", nif="11111111A", name="Uno", share="60", base="6000", clave="D"),
        _observation(source_id="m2", nif="22222222B", name="Dos", share="40", base="4000", clave="C"),
    )

    resolved = resolve_atribucion_binding_row_values(revision, observations)
    row_indexes = {row_index for (_binding_id, row_index) in resolved}

    assert row_indexes == {1, 2}


def test_one_member_under_two_claves_resolves_two_rows_not_one() -> None:
    """The S289 regression, reproduced and proven fixed.

    The SAME member, same nif, declares income under two different claves --
    capital mobiliario and capital inmobiliario, an ordinary real-world case.
    Both must resolve as their OWN row rather than one clobbering the other.
    """
    revision = _revision()
    observations = (
        _observation(source_id="m1-a", nif="11111111A", name="Uno", share="100", base="6000", clave="C"),
        _observation(source_id="m1-b", nif="11111111A", name="Uno", share="100", base="1500", clave="D"),
    )

    resolved = resolve_atribucion_binding_row_values(revision, observations)
    row_indexes = {row_index for (_binding_id, row_index) in resolved}

    assert len(row_indexes) == 2, "one member under two claves must resolve as two distinct rows, not one"

    clave_binding = next(
        binding_id
        for (binding_id, _row_index) in resolved
        if binding_id.endswith("-clave") and "declarado" not in binding_id
    )
    claves_by_row = {row_index: resolved[(clave_binding, row_index)] for row_index in row_indexes}
    assert set(claves_by_row.values()) == {"C", "D"}


def test_clave_conditional_fields_resolve_only_for_the_row_that_declares_them() -> None:
    """A clave-D row's clave-C inmueble fields, and vice versa, are absent.

    Proves the "legitimately absent, not a missing-value refusal" contract:
    resolving must not raise for a row whose clave does not license a
    clave-C-only or clave-D-only field, and must not fabricate a value for it
    either.
    """
    revision = _revision()
    observations = (
        _observation(
            source_id="m1",
            nif="11111111A",
            name="Uno",
            share="100",
            base="6000",
            clave="C",
            naturaleza_inmueble="1",
            situacion_inmueble="1",
        ),
        _observation(
            source_id="m2",
            nif="22222222B",
            name="Dos",
            share="100",
            base="2000",
            clave="D",
            subclave="03",
            rendimiento_neto_previo_eo=Decimal("500"),
        ),
    )

    resolved = resolve_atribucion_binding_row_values(revision, observations)

    naturaleza_binding = next(
        binding_id for (binding_id, _row_index) in resolved if binding_id.endswith("-naturaleza-inmueble")
    )
    rendimiento_binding = next(
        binding_id for (binding_id, _row_index) in resolved if binding_id.endswith("-rendimiento-neto-previo-eo")
    )
    naturaleza_rows = {row_index for (binding_id, row_index) in resolved if binding_id == naturaleza_binding}
    rendimiento_rows = {row_index for (binding_id, row_index) in resolved if binding_id == rendimiento_binding}

    assert len(naturaleza_rows) == 1, "the clave-D row must not carry a naturaleza-inmueble value"
    assert len(rendimiento_rows) == 1, "the clave-C row must not carry a rendimiento-neto-previo-eo value"
    assert naturaleza_rows != rendimiento_rows


def test_binding_rows_rendering_emits_one_occurrence_per_resolved_row() -> None:
    """The renderer itself, not just the resolver, emits every distinct row."""
    revision = _revision()
    record = _socio_record(revision)
    observations = (
        _observation(source_id="m1-a", nif="11111111A", name="Uno", share="100", base="6000", clave="C"),
        _observation(source_id="m1-b", nif="11111111A", name="Uno", share="100", base="1500", clave="D"),
        _observation(source_id="m2", nif="22222222B", name="Dos", share="100", base="3000", clave="A"),
    )

    resolved = resolve_atribucion_binding_row_values(revision, observations)
    rows = _record_render_rows(record, resolved, {})

    assert len({row.row_index for row in rows}) == 3


def test_two_rows_for_one_member_under_different_claves_survive_the_union() -> None:
    """The exact S298 collision this Step's scope names.

    ``_ROW_IDENTITY_FIELDS`` widened to ``(nif, clave, subclave)`` so the
    two-source union treats these as two different real-world things, not a
    resolver/caller duplicate of the same one.
    """
    resolver_row = Modelo184MemberRow(
        nif="11111111A", nombre="Uno", porcentaje=Decimal("100"), importe=Decimal("6000"), clave="C"
    )
    caller_row = Modelo184MemberRow(
        nif="11111111A", nombre="Uno", porcentaje=Decimal("100"), importe=Decimal("1500"), clave="D"
    )

    unioned = union_detail_rows_by_identity(resolver_rows=(resolver_row,), caller_rows=(caller_row,))

    assert len(unioned) == 2
    assert {row.clave for row in unioned if isinstance(row, Modelo184MemberRow)} == {"C", "D"}


def test_two_supply_paths_naming_the_same_member_clave_subclave_still_union_to_one() -> None:
    """The non-regression the widened key must not break: a genuine duplicate still unions."""
    resolver_row = Modelo184MemberRow(
        nif="11111111A", nombre="Uno", porcentaje=Decimal("100"), importe=Decimal("6000"), clave="C"
    )
    caller_row = Modelo184MemberRow(
        nif="11111111A", nombre="Uno", porcentaje=Decimal("100"), importe=Decimal("6000"), clave="C"
    )

    unioned = union_detail_rows_by_identity(resolver_rows=(resolver_row,), caller_rows=(caller_row,))

    assert len(unioned) == 1


def test_two_rows_sharing_the_full_widened_identity_but_disagreeing_still_refuse() -> None:
    """The widening must not turn a genuine conflict into two "distinct" rows.

    Same nif, same clave, same subclave (both None here, since clave C
    carries none) -- the full widened identity matches -- but the two
    supply paths disagree on the declared amount. This must still refuse,
    naming the divergent field, exactly as it did before the identity
    widened. If it silently unioned or silently treated the two as distinct,
    the widening would have quietly turned a real conflict into
    invisible data loss.
    """
    resolver_row = Modelo184MemberRow(
        nif="11111111A", nombre="Uno", porcentaje=Decimal("100"), importe=Decimal("6000"), clave="C"
    )
    caller_row = Modelo184MemberRow(
        nif="11111111A", nombre="Uno", porcentaje=Decimal("100"), importe=Decimal("9999"), clave="C"
    )

    with pytest.raises(ModeloAggregationBindingError) as excinfo:
        union_detail_rows_by_identity(resolver_rows=(resolver_row,), caller_rows=(caller_row,))

    assert "importe" in excinfo.value.context["divergent_fields"]


def test_clave_a_reduccion_is_refused_at_the_row_boundary() -> None:
    """The ADR's clave-A block, enforced in code rather than only in prose.

    Modelling reducción as ONE shared field (matching the diseño's own
    physical layout for positions 109-119) makes it reachable under clave A
    unless refused explicitly -- its governing provision is unconfirmed
    (the diseño's own LIRPF art. 24.2 citation does not exist), so a
    populated value there must refuse rather than silently file an
    ungrounded amount.
    """
    with pytest.raises(ValidationError, match="clave A reducción is blocked"):
        Modelo184MemberRow(
            nif="11111111A",
            nombre="Uno",
            porcentaje=Decimal("100"),
            importe=Decimal("6000"),
            clave="A",
            reduccion=Decimal("500"),
        )


def test_clave_c_and_clave_d_reduccion_still_populate() -> None:
    """The non-regression the clave-A block must not break: C and D still work."""
    clave_c_row = Modelo184MemberRow(
        nif="11111111A",
        nombre="Uno",
        porcentaje=Decimal("100"),
        importe=Decimal("6000"),
        clave="C",
        reduccion=Decimal("500"),
    )
    clave_d_row = Modelo184MemberRow(
        nif="22222222B",
        nombre="Dos",
        porcentaje=Decimal("100"),
        importe=Decimal("4000"),
        clave="D",
        reduccion=Decimal("300"),
    )

    assert clave_c_row.reduccion == Decimal("500")
    assert clave_d_row.reduccion == Decimal("300")


def test_clave_a_without_reduccion_is_still_accepted() -> None:
    """The block targets a POPULATED reducción, not the clave itself."""
    row = Modelo184MemberRow(
        nif="11111111A", nombre="Uno", porcentaje=Decimal("100"), importe=Decimal("6000"), clave="A"
    )

    assert row.reduccion is None


def test_an_ordinary_multi_member_attribution_emits_one_row_per_member_with_the_right_values() -> None:
    """S289's own defect, reproduced with plain distinct members (no clave variation).

    Four ordinary members, all under the same clave -- no exotic multi-clave
    shape needed to trigger the truncation this Step names. Before the
    binding_rows migration the export record rendered a single fixed
    occurrence regardless of how many members the resolver produced, so
    every member past the first silently vanished from the fichero. Proves
    both that every member resolves its OWN row index and that the render
    layer emits one occurrence per resolved index, each carrying that
    member's own nif -- not a truncated or overwritten value.
    """
    revision = _revision()
    record = _socio_record(revision)
    members = (
        ("11111111A", "Uno", "1500"),
        ("22222222B", "Dos", "2500"),
        ("33333333C", "Tres", "3500"),
        ("44444444D", "Cuatro", "4500"),
    )
    observations = tuple(
        _observation(source_id=f"m-{nif}", nif=nif, name=name, share="25", base=base, clave="D")
        for nif, name, base in members
    )

    resolved = resolve_atribucion_binding_row_values(revision, observations)
    nif_binding = next(binding_id for (binding_id, _row_index) in resolved if binding_id.endswith("-nif"))
    base_binding = next(binding_id for (binding_id, _row_index) in resolved if binding_id.endswith("-base-assigned"))

    # Every member resolves to its OWN row index, and none collide.
    nifs_by_row = {row_index: value for (binding_id, row_index), value in resolved.items() if binding_id == nif_binding}
    bases_by_row = {row_index: value for (binding_id, row_index), value in resolved.items() if binding_id == base_binding}

    assert len(nifs_by_row) == 4, "every one of the four members must resolve its own row"
    assert set(nifs_by_row.values()) == {nif for nif, _name, _base in members}
    for row_index, nif in nifs_by_row.items():
        expected_base = next(Decimal(base) for candidate_nif, _name, base in members if candidate_nif == nif)
        assert bases_by_row[row_index] == expected_base, f"row {row_index} carries the wrong member's base_imponible_assigned"

    rendered = _record_render_rows(record, resolved, {})
    assert len({row.row_index for row in rendered}) == 4, "the render layer must emit one occurrence per member"
