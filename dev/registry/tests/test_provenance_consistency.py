"""The provenance screen reports a child citation outside its manifest, and reads resolved export fields.

Detector teeth on constructed revisions: a casilla citing only manifest refs is
clean; a casilla citing an extra legal ref is reported as a ``legal`` finding
naming exactly that ref; an export field citing an extra source ref is
reported as an ``export_field`` finding through the resolved surface, with the
field's resolved coordinates as its id.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.schema import CasillaDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ..analysis.provenance_consistency import provenance_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-35-2006:art-test"
_EXTRA_LEGAL_REF = "ley-37-1992:art-extra"
_SOURCE_REF = "aeat-test-source-001"
_EXTRA_SOURCE_REF = "aeat-test-source-002"
_CASILLA_01 = validated_casilla_id("01", surface="_CASILLA_01")


def _casilla(*, legal_refs: tuple[str, ...]) -> CasillaDefinition:
    return CasillaDefinition(
        id=_CASILLA_01,
        number="01",
        localization_keys=("test.schema.casilla.label",),
        section=("totales",),
        input_kind=InputKind.MANUAL,
        legal_refs=legal_refs,
        source_refs=(_SOURCE_REF,),
    )


def _layout(*, field_source_refs: tuple[str, ...]) -> ExportLayoutDefinition:
    field = ExportFieldDefinition(
        id="importe",
        offset=1,
        length=10,
        kind=CasillaFieldKind.CASILLA,
        casilla_id=_CASILLA_01,
        data_type=CasillaDataType.MONEY,
        required=False,
        padding="left_zero",
        justification="right",
        signed=False,
        legal_refs=(_LEGAL_REF,),
        source_refs=field_source_refs,
    )
    record = ExportRecordDefinition(
        id="declaracion",
        record_type="declaracion",
        order=1,
        encoding=ExportEncoding.ASCII,
        line_ending="none",
        fields=(field,),
    )
    return ExportLayoutDefinition(id="layout", legal_refs=(_LEGAL_REF,), source_refs=(_SOURCE_REF,), records=(record,))


def _revision(
    *, casillas: tuple[CasillaDefinition, ...], layouts: tuple[ExportLayoutDefinition, ...]
) -> ModeloRevision:
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        casillas=casillas,
        export_layouts=layouts,
    )


def test_child_inside_manifest_is_clean() -> None:
    revision = _revision(
        casillas=(_casilla(legal_refs=(_LEGAL_REF,)),), layouts=(_layout(field_source_refs=(_SOURCE_REF,)),)
    )

    assert provenance_findings(revision, modelo_id="000") == ()


def test_casilla_citing_outside_legal_ref_is_reported_with_the_ref() -> None:
    revision = _revision(casillas=(_casilla(legal_refs=(_LEGAL_REF, _EXTRA_LEGAL_REF)),), layouts=())

    (finding,) = provenance_findings(revision, modelo_id="000")

    assert (finding.child_kind, finding.child_id, finding.ref_kind) == ("casilla", str(_CASILLA_01), "legal")
    assert finding.outside == (_EXTRA_LEGAL_REF,)


def test_resolved_export_field_citing_outside_source_is_reported() -> None:
    revision = _revision(
        casillas=(_casilla(legal_refs=(_LEGAL_REF,)),),
        layouts=(_layout(field_source_refs=(_SOURCE_REF, _EXTRA_SOURCE_REF)),),
    )

    (finding,) = provenance_findings(revision, modelo_id="000")

    assert (finding.child_kind, finding.child_id, finding.ref_kind) == (
        "export_field",
        "layout.declaracion.importe",
        "source",
    )
    assert finding.outside == (_EXTRA_SOURCE_REF,)


def test_a_reference_absent_from_every_revision_is_distinguished_from_partial_drift() -> None:
    """The two shapes look identical in the per-revision index and are not.

    A reference the modelo never declares anywhere is one omission. A reference
    present in some revisions and absent from others is drift between manifests
    that were meant to agree, and each gap is its own correction. Both appear in
    the index as several rows carrying the same reference.
    """
    from ..analysis.provenance_consistency import outside_reference_scope

    index = {
        ("100", "2023", "legal", "ley-1:art-1"): 5,
        ("100", "2024", "legal", "ley-1:art-1"): 7,
        ("100", "2023", "legal", "ley-2:art-2"): 3,
    }
    scopes = {item.reference: item for item in outside_reference_scope(index, {"100": 2})}
    assert scopes["ley-1:art-1"].spans_every_revision is True
    assert scopes["ley-1:art-1"].revisions == ("2023", "2024")
    assert scopes["ley-1:art-1"].sites == 12
    assert scopes["ley-2:art-2"].spans_every_revision is False


def test_a_modelo_absent_from_the_revision_counts_is_never_called_systemic() -> None:
    """An unknown denominator produces no claim rather than a false one.

    Reporting "absent from every revision" requires knowing how many revisions
    there are. Defaulting a missing count to zero would make any single row
    match and mark it systemic, which is a claim built out of ignorance.
    """
    from ..analysis.provenance_consistency import outside_reference_scope

    scopes = outside_reference_scope({("999", "r", "legal", "ley-1:art-1"): 1}, {})
    assert [item.spans_every_revision for item in scopes] == [False]


def test_the_scope_projection_agrees_with_the_index_it_reduces() -> None:
    """No site is lost or invented between the index and its reduction.

    The two are separate collapses of the same measurement, so they can drift.
    Total sites must be equal and the reference set must be the index's own.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.corpus import bundled_modelo_ids
    from ..analysis.provenance_consistency import (
        outside_reference_index,
        outside_reference_scope,
        screen_authority,
    )

    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    index = outside_reference_index(screen_authority(authority, modelo_ids))
    assert index, "the index is empty, so this proves nothing"
    counts = {modelo: len(authority.modelo(modelo).revisions) for modelo in modelo_ids}
    scopes = outside_reference_scope(index, counts)
    assert sum(item.sites for item in scopes) == sum(index.values())
    assert {(item.modelo, item.ref_kind, item.reference) for item in scopes} == {
        (modelo, ref_kind, reference) for modelo, _, ref_kind, reference in index
    }


def test_a_deadline_window_citing_outside_its_manifest_is_reported() -> None:
    """A window's citations reach outside like any other child's.

    Eighty-four did while this family was missing from the walk, so the screen
    reported a revision as consistent whose due-date grounding named an orden
    the manifest never applies.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.corpus import bundled_modelo_ids
    from ..analysis.provenance_consistency import screen_authority

    findings = screen_authority(bundled_authority(), bundled_modelo_ids())
    windows = [item for item in findings if item.child_kind == "deadline_window"]
    assert windows, "no deadline window cites outside its manifest, so this proves nothing"
    for item in windows:
        assert item.outside
        assert item.ref_kind in {"legal", "source"}


def test_the_walked_families_and_the_declared_child_kinds_agree() -> None:
    """Every kind the vocabulary names is walked, except the derived one.

    `ProvenanceChildKind` is the vocabulary and `citing_children` is the walk,
    and a kind added to one without the other is invisible in exactly the way
    `deadline_window` was: named nowhere, walked nowhere, and reported as an
    absence rather than a gap. `export_field` is the one kind deliberately not
    walked here - it exists only after derivation and its citations are copied
    from a template - and the screen adds it separately.
    """
    import typing

    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.provenance_consistency import ProvenanceChildKind, citing_children

    declared = set(typing.get_args(ProvenanceChildKind.__value__))
    assert declared, "the child-kind vocabulary is empty, so this proves nothing"

    revision = bundled_authority().modelo("303").revisions["2025"]
    walked = {kind for kind, _ in citing_children(revision)}
    assert walked == declared - {"export_field"}


def test_both_provenance_screens_walk_the_same_families() -> None:
    """One declaration, two consumers, and no second copy of the list.

    The list was written longhand in both screens and the omission of a family
    propagated from one to the other. This asserts they now agree by
    construction: the mirror's family walk is this module's, so any family added
    here reaches both screens without a second edit.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.manifest_uncited_references import uncited_manifest_references
    from ..analysis.provenance_consistency import citing_children

    authority = bundled_authority()
    revision = authority.modelo("303").revisions["2025"]
    walked = {kind for kind, items in citing_children(revision) if items}
    assert "deadline_window" in walked, "the family that motivated this is not walked"

    # The mirror consumes the same walk, so a reference cited by any walked
    # family is not reported as uncited.
    cited = {
        str(reference)
        for _, items in citing_children(revision)
        for item in items
        for reference in (*item.legal_refs, *item.source_refs)
    }
    reported = {item.reference for item in uncited_manifest_references(revision, modelo_id="303")}
    assert not (cited & reported)
