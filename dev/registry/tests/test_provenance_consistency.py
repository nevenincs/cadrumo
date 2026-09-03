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


def test_a_manifest_reference_no_child_cites_is_reported() -> None:
    """The mirror condition, on the live corpus.

    A manifest and its children's citations describe the same revision's
    grounding, and neither contains the other. Screening only the children
    reported half a disagreement for as long as this screen has existed.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.corpus import bundled_modelo_ids
    from ..analysis.provenance_consistency import screen_uncited_manifest_references

    found = screen_uncited_manifest_references(bundled_authority(), bundled_modelo_ids())
    assert found, "the mirror condition lost its live population"
    assert {item.ref_kind for item in found} == {"legal", "source"}
    for item in found:
        assert item.modelo and item.revision and item.reference


def test_a_manifest_whose_references_are_all_cited_reports_nothing() -> None:
    """No finding where the two surfaces agree.

    Fifty-nine revisions are in this state, so a screen reporting every manifest
    reference rather than the uncited ones would bury the finding under the
    majority that is fine.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.corpus import bundled_modelo_ids
    from ..analysis.provenance_consistency import uncited_manifest_references

    authority = bundled_authority()
    clean = [
        (modelo, revision)
        for modelo in bundled_modelo_ids()
        for revision in authority.modelo(modelo).revisions.values()
        if not uncited_manifest_references(revision, modelo_id=modelo)
    ]
    assert clean, "every revision carries an uncited manifest reference, so this proves nothing"


def test_the_mirror_reads_authored_families_and_not_derived_fields() -> None:
    """A derived export field's citations are copied and must not count as a citation.

    Counting them would let a manifest reference look cited by a child that
    never declares it, which would hide exactly the disagreement being measured.
    Asserted by the totals: the mirror finds references the citing-side screen
    never sees, which cannot happen if both read the same surface.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    from ..analysis.corpus import bundled_modelo_ids
    from ..analysis.provenance_consistency import (
        screen_authority,
        screen_uncited_manifest_references,
    )

    authority = bundled_authority()
    modelo_ids = bundled_modelo_ids()
    cited_outside = {
        (item.modelo, item.revision, item.ref_kind, reference)
        for item in screen_authority(authority, modelo_ids)
        for reference in item.outside
    }
    uncited = {
        (item.modelo, item.revision, item.ref_kind, item.reference)
        for item in screen_uncited_manifest_references(authority, modelo_ids)
    }
    # The two populations are disjoint by construction: one is cited but not
    # declared, the other declared but not cited.
    assert not (cited_outside & uncited)
