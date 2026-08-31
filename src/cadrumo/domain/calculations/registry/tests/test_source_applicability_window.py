"""Revision-scoped evidence references must apply to the revision citing them.

``SourceReference`` carries ``applies_from`` / ``applies_to`` but validated only
that the two dates were internally ordered. Nothing intersected that window with
the revision it was cited by, so a source stale for the revision stayed
authoritative evidence inside a successful snapshot -- and a filing grounded on
it could not be defended. ``LegalReference`` had the same gap for its
``effective_from`` / ``effective_to`` window outside ``orden_aplicabilidad``.

These tests drive the real bundled M100 2025 authority through the real
``build_snapshot`` path (no doubles), copying genuine legal and source references
into stale and future windows to prove the refusal, and pin the exclusions the
gates deliberately keep: modelo-level refs (the modelo's authority corpus across
every filing year) and the boundary dates themselves.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from .....core.resources._boundary import bundled_path
from .._snapshot_internals import _SUBSTANTIVE_LAW_KINDS, collect_snapshot_ref_ids
from .._validate_orden_aplicabilidad import RevisionLegalApplicabilityWindow
from ..errors import RegistryValidationError
from ..schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ..schema_references import LegalReference
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "100"
_FILING_YEAR = 2025
_PERIOD = "0A"
_REVISION = "2025"


def _modelo_and_catalogues() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo(_MODELO)


def _revision_scoped_source_ids(modelo: ModeloDefinition) -> set[str]:
    """Return the source ids the revision owns, matching the gate's own scope.

    The revision's top-level ``source_refs`` are a subset of the modelo's, so the
    revision-scoped evidence lives on its nested records (casillas, formulas,
    bindings). This mirrors the gate rather than re-deriving a narrower set.
    """
    _legal_ids, source_ids = collect_snapshot_ref_ids(modelo, modelo.revisions[_REVISION])
    return source_ids - set(modelo.source_refs)


def _revision_scoped_legal_ids(modelo: ModeloDefinition) -> set[str]:
    """Return the legal ids the revision owns, matching the gate's own scope."""
    legal_ids, _source_ids = collect_snapshot_ref_ids(modelo, modelo.revisions[_REVISION])
    return legal_ids - set(modelo.legal_refs)


def _revision_scoped_legal_id(modelo: ModeloDefinition) -> str:
    """Return one legal id the 2025 revision owns and the modelo does not."""
    scoped = _revision_scoped_legal_ids(modelo)
    assert scoped, "the M100 2025 revision must own at least one legal ref of its own"
    return sorted(scoped)[0]


def _revision_scoped_source_id(modelo: ModeloDefinition, catalogues: RegistryCatalogues) -> str:
    """Return one non-record-design scoped source id the 2025 revision owns.

    A RECORD DESIGN is excluded for the same reason
    :func:`_revision_scoped_procedural_legal_id` excludes substantive law: it is
    checked by a DIFFERENT rule that fires first. A record-design source carries
    a ``record_design_epoch``, and validation refuses an epoch its window no
    longer governs -- so moving such a source's window to probe the applicability
    check instead reports "declares epoch '2025' but applies to 2024-12-31" and
    the test never reaches the boundary it is asking about.

    That is not hypothetical: the scoped set holds exactly one record design,
    ``aeat-dr-184-2025``, and it sorts first, so taking ``sorted(...)[0]`` picked
    precisely the one source these probes cannot use.
    """
    scoped = _revision_scoped_source_ids(modelo)
    usable = sorted(
        source_id for source_id in scoped if getattr(catalogues.sources[source_id], "kind", None) != "record_design"
    )
    assert usable, "the M100 2025 revision must own at least one non-design source ref of its own"
    return usable[0]


def _revision_scoped_procedural_legal_id(modelo: ModeloDefinition, catalogues: RegistryCatalogues) -> str:
    """Return one non-substantive-law scoped legal id (e.g. an orden ministerial).

    ``_legal_window_covers_devengo`` checks a substantive-law reference
    (``kind`` in ``_SUBSTANTIVE_LAW_KINDS`` -- a rate scale, a deduction limit)
    against the revision's own devengo date (``revision.valid_to``), never the
    presentation-tolerant :class:`RevisionLegalApplicabilityWindow`. The
    applicability-window boundary tests exercise that presentation-tolerant
    window specifically, so they need a procedural/administrative reference
    (an ``orden``, not a ``ley``), not merely any revision-scoped id.
    """
    scoped = _revision_scoped_legal_ids(modelo)
    procedural = sorted(
        legal_id for legal_id in scoped if catalogues.legal[legal_id].kind not in _SUBSTANTIVE_LAW_KINDS
    )
    assert procedural, "the M100 2025 revision must own at least one procedural legal ref of its own"
    return procedural[0]


def _rebuild_with_legal_window(
    legal_id: str,
    *,
    effective_from: date,
    effective_to: date | None,
) -> RegistrySnapshot:
    """Rebuild the M100 2025 snapshot with one legal ref moved into a new window."""
    modelo, catalogues = _modelo_and_catalogues()
    reference = catalogues.legal[legal_id]
    restaged = reference.model_copy(update={"effective_from": effective_from, "effective_to": effective_to})
    catalogues = catalogues.model_copy(
        update={"legal": {**catalogues.legal, legal_id: restaged}},
    )
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )


def _rebuild_with_source_window(
    source_id: str,
    *,
    applies_from: date | None,
    applies_to: date | None,
) -> RegistrySnapshot:
    """Rebuild the M100 2025 snapshot with one source moved into a new window."""
    modelo, catalogues = _modelo_and_catalogues()
    source = catalogues.sources[source_id]
    restaged = source.model_copy(update={"applies_from": applies_from, "applies_to": applies_to})
    catalogues = catalogues.model_copy(
        update={"sources": {**catalogues.sources, source_id: restaged}},
    )
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )


def test_shipped_registry_snapshot_builds_with_every_evidence_window_intact() -> None:
    """The positive control: the real corpus satisfies the gate unmodified."""
    snapshot = _committed_snapshot(_MODELO, _FILING_YEAR, _PERIOD)

    assert snapshot.revision.id == _REVISION
    assert snapshot.legal, "the snapshot must carry the legal authority it grounds on"
    assert snapshot.sources, "the snapshot must carry the source evidence it grounds on"
    assert {"orden-hac-277-2026:art-7", "orden-hac-277-2026:art-10"} <= set(snapshot.legal)
    assert "real-decreto-ley-4-2024:art-3" not in snapshot.legal
    assert "real-decreto-ley-13-2025:art-2" in snapshot.legal


def test_snapshot_refuses_a_legal_ref_that_expired_before_the_revision_opened() -> None:
    """A law version expired in 2024 cannot ground the 2025 revision."""
    modelo, _catalogues = _modelo_and_catalogues()
    legal_id = _revision_scoped_legal_id(modelo)

    with pytest.raises(RegistryValidationError, match="outside their effective window"):
        _rebuild_with_legal_window(
            legal_id,
            effective_from=date(2020, 1, 1),
            effective_to=date(2024, 12, 31),
        )


def test_snapshot_refuses_a_legal_ref_that_only_takes_effect_after_the_revision_closed() -> None:
    """A future-only authority cannot ground an earlier revision."""
    modelo, _catalogues = _modelo_and_catalogues()
    legal_id = _revision_scoped_legal_id(modelo)

    with pytest.raises(RegistryValidationError, match="outside their effective window"):
        _rebuild_with_legal_window(
            legal_id,
            effective_from=date(2030, 1, 1),
            effective_to=date(2031, 12, 31),
        )


@pytest.mark.parametrize(
    ("effective_from", "effective_to"),
    [
        pytest.param(date(2026, 6, 30), None, id="effective_from-on-applicability-close"),
        pytest.param(date(2020, 1, 1), date(2025, 1, 1), id="effective_to-on-applicability-start"),
    ],
)
def test_snapshot_accepts_legal_windows_that_touch_the_applicability_boundary(
    effective_from: date,
    effective_to: date | None,
) -> None:
    """A legal window touching either applicability boundary still overlaps it."""
    modelo, catalogues = _modelo_and_catalogues()
    legal_id = _revision_scoped_procedural_legal_id(modelo, catalogues)
    applicability_window = RevisionLegalApplicabilityWindow.from_revision(modelo.revisions[_REVISION])
    assert applicability_window.closes_on is not None
    if effective_to is None:
        assert effective_from == applicability_window.closes_on
    else:
        assert effective_to == applicability_window.starts_on

    snapshot = _rebuild_with_legal_window(
        legal_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )

    assert snapshot.revision.id == _REVISION


def test_modelo_level_legal_refs_stay_exempt_from_the_revision_window() -> None:
    """A modelo's cross-year legal corpus is not a revision-specific claim."""
    modelo, catalogues = _modelo_and_catalogues()
    modelo_level = sorted(set(modelo.legal_refs) - set(modelo.revisions[_REVISION].orden_aplicabilidad))
    assert modelo_level, "M100 must have a modelo-level legal ref for this exclusion to matter"
    stale_id = modelo_level[0]
    assert stale_id not in _revision_scoped_legal_ids(modelo)

    snapshot = _rebuild_with_legal_window(
        stale_id,
        effective_from=date(2020, 1, 1),
        effective_to=date(2020, 12, 31),
    )

    assert snapshot.revision.id == _REVISION
    assert catalogues.legal[stale_id].id == stale_id


def test_snapshot_refuses_a_source_that_expired_before_the_revision_opened() -> None:
    """The audit's probe: a stale 2020..2024 window must not stay authoritative."""
    modelo, catalogues = _modelo_and_catalogues()
    source_id = _revision_scoped_source_id(modelo, catalogues)

    with pytest.raises(RegistryValidationError, match="outside their applicability window"):
        _rebuild_with_source_window(
            source_id,
            applies_from=date(2020, 1, 1),
            applies_to=date(2024, 12, 31),
        )


def test_snapshot_refuses_a_source_that_only_applies_after_the_revision_closed() -> None:
    """The mirror case: a future-only window is equally ungrounded."""
    modelo, catalogues = _modelo_and_catalogues()
    source_id = _revision_scoped_source_id(modelo, catalogues)

    with pytest.raises(RegistryValidationError, match="outside their applicability window"):
        _rebuild_with_source_window(
            source_id,
            applies_from=date(2030, 1, 1),
            applies_to=date(2031, 12, 31),
        )


def test_snapshot_refuses_invalid_legal_window_before_invalid_source_window() -> None:
    """Legal-window refusal remains earlier than source-window refusal."""
    modelo, catalogues = _modelo_and_catalogues()
    legal_id = _revision_scoped_legal_id(modelo)
    source_id = _revision_scoped_source_id(modelo, catalogues)
    legal_reference = catalogues.legal[legal_id].model_copy(
        update={"effective_from": date(2020, 1, 1), "effective_to": date(2024, 12, 31)},
    )
    source_reference = catalogues.sources[source_id].model_copy(
        update={"applies_from": date(2020, 1, 1), "applies_to": date(2024, 12, 31)},
    )
    restaged_catalogues = catalogues.model_copy(
        update={
            "legal": {**catalogues.legal, legal_id: legal_reference},
            "sources": {**catalogues.sources, source_id: source_reference},
        },
    )

    with pytest.raises(RegistryValidationError, match="outside their effective window"):
        build_snapshot(
            modelo,
            restaged_catalogues,
            source_root=bundled_path(),
            filing_year=_FILING_YEAR,
            period=_PERIOD,
        )


@pytest.mark.parametrize(
    ("applies_from", "applies_to"),
    [
        pytest.param(date(2025, 12, 31), None, id="applies_from-on-revision-valid_to"),
        pytest.param(None, date(2025, 1, 1), id="applies_to-on-revision-valid_from"),
        pytest.param(None, None, id="unbounded-window"),
    ],
)
def test_snapshot_accepts_windows_that_touch_the_revision_boundary(
    applies_from: date | None,
    applies_to: date | None,
) -> None:
    """The refusal is for windows that miss the revision, not ones that touch it."""
    modelo, catalogues = _modelo_and_catalogues()
    source_id = _revision_scoped_source_id(modelo, catalogues)

    snapshot = _rebuild_with_source_window(source_id, applies_from=applies_from, applies_to=applies_to)

    assert snapshot.revision.id == _REVISION


def test_modelo_level_source_refs_stay_exempt_from_the_revision_window() -> None:
    """A modelo's corpus spans every filing year, so it is not revision-scoped.

    M100 lists each year's XSD, dictionary, and manual at the modelo level; every
    revision's snapshot inherits all of them. Intersecting those with one
    revision's window would reject the shipped tree by design, so the gate covers
    only the refs a revision itself claims.
    """
    modelo, catalogues = _modelo_and_catalogues()
    modelo_level = sorted(set(modelo.source_refs))
    assert modelo_level, "M100 must declare modelo-level source refs for this exclusion to matter"
    stale_id = modelo_level[0]
    assert stale_id not in _revision_scoped_source_ids(modelo)

    snapshot = _rebuild_with_source_window(
        stale_id,
        applies_from=date(2020, 1, 1),
        applies_to=date(2020, 12, 31),
    )

    assert snapshot.revision.id == _REVISION
    assert catalogues.sources[stale_id].id == stale_id


# A period's filing deadline lawfully falls after the period itself ends: the
# fourth-quarter return of one year is filed in the January of the next, so the
# calendario that states its deadline is the FOLLOWING year's. These cover the
# axis that citation is validated against.

_DEADLINE_MODELO = "123"
_DEADLINE_REVISION = "2019-2023"
_DEADLINE_FILING_YEAR = 2023
_DEADLINE_PERIOD = "4T"
_NEXT_YEAR_CALENDARIO = "aeat-calendario-contribuyente-2024"


def _rebuild_m123_with_source_window(
    source_id: str,
    *,
    applies_from: date | None,
    applies_to: date | None,
) -> RegistrySnapshot:
    """Rebuild the M123 2023 4T snapshot with one source moved into a new window."""
    modelo, catalogues = _committed_modelo(_DEADLINE_MODELO)
    source = catalogues.sources[source_id]
    restaged = source.model_copy(update={"applies_from": applies_from, "applies_to": applies_to})
    catalogues = catalogues.model_copy(
        update={"sources": {**catalogues.sources, source_id: restaged}},
    )
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=_DEADLINE_FILING_YEAR,
        period=_DEADLINE_PERIOD,
    )


def test_a_deadline_window_source_is_validated_against_the_window_not_the_revision() -> None:
    """The shipped 4T citation must survive, and not vacuously.

    The preconditions are asserted rather than assumed: if the calendario ever
    stopped starting after the revision closed, this test would pass while
    proving nothing about the axis.
    """
    modelo, catalogues = _committed_modelo(_DEADLINE_MODELO)
    revision = modelo.revisions[_DEADLINE_REVISION]
    calendario = catalogues.sources[_NEXT_YEAR_CALENDARIO]

    assert revision.valid_to is not None
    assert calendario.applies_from is not None
    assert calendario.applies_from > revision.valid_to, (
        "precondition: the next-year calendario must start after the revision closes"
    )
    fourth_quarter = next(window for window in revision.deadline_windows if window.id.endswith("2023-4t"))
    assert _NEXT_YEAR_CALENDARIO in fourth_quarter.source_refs
    assert fourth_quarter.closes_on > revision.valid_to

    snapshot = _committed_snapshot(_DEADLINE_MODELO, _DEADLINE_FILING_YEAR, _DEADLINE_PERIOD)

    assert snapshot.revision.id == _DEADLINE_REVISION


def test_construct_deadline_closure_does_not_reclassify_its_calendar_as_a_generic_source() -> None:
    """Construct aggregation preserves the member deadline's presentation axis."""
    modelo, catalogues = _committed_modelo(_DEADLINE_MODELO)
    revision = modelo.revisions[_DEADLINE_REVISION]
    window = next(item for item in revision.deadline_windows if item.id.endswith("2023-4t"))
    construct = revision.constructs[0]
    closed_construct = construct.model_copy(
        update={
            "deadline_windows": (window.id,),
            "legal_refs": tuple(dict.fromkeys((*construct.legal_refs, *window.legal_refs))),
            "source_refs": tuple(dict.fromkeys((*construct.source_refs, *window.source_refs))),
        },
    )
    closed_revision = revision.model_copy(
        update={"constructs": (closed_construct, *revision.constructs[1:])},
    )
    closed_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: closed_revision}},
    )

    snapshot = build_snapshot(
        closed_modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=_DEADLINE_FILING_YEAR,
        period=_DEADLINE_PERIOD,
    )

    assert snapshot.revision.constructs[0].deadline_windows == (window.id,)


def test_construct_owned_source_without_deadline_member_provenance_keeps_revision_axis() -> None:
    """A construct-only source cannot borrow an unrelated deadline member's axis."""
    modelo, catalogues = _committed_modelo(_DEADLINE_MODELO)
    revision = modelo.revisions[_DEADLINE_REVISION]
    construct = revision.constructs[0]
    stale_id = "aeat-calendario-contribuyente-2026"
    stale_source = catalogues.sources[stale_id].model_copy(
        update={"applies_from": date(2030, 1, 1), "applies_to": date(2030, 12, 31)},
    )
    catalogues = catalogues.model_copy(
        update={"sources": {**catalogues.sources, stale_id: stale_source}},
    )
    stale_construct = construct.model_copy(
        update={"source_refs": (*construct.source_refs, stale_id)},
    )
    stale_revision = revision.model_copy(
        update={"constructs": (stale_construct, *revision.constructs[1:])},
    )
    stale_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: stale_revision}},
    )

    with pytest.raises(RegistryValidationError, match=stale_id):
        build_snapshot(
            stale_modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=_DEADLINE_FILING_YEAR,
            period=_DEADLINE_PERIOD,
        )


def test_a_deadline_source_outside_both_the_revision_and_its_window_still_refuses() -> None:
    """The window axis is a real bound, not a blanket exemption for deadline refs."""
    with pytest.raises(RegistryValidationError, match=_NEXT_YEAR_CALENDARIO):
        _rebuild_m123_with_source_window(
            _NEXT_YEAR_CALENDARIO,
            applies_from=date(2030, 1, 1),
            applies_to=date(2030, 12, 31),
        )


def test_a_source_cited_outside_any_deadline_window_keeps_the_revision_axis() -> None:
    """The exemption follows the deadline-window citation, not the calendar date.

    A design source is cited by casillas, so falling inside some window's dates
    earns it nothing: it still has to overlap the revision it grounds.
    """
    design_source = "aeat-dr-123-2019-2023-v13"
    modelo, _catalogues = _committed_modelo(_DEADLINE_MODELO)
    revision = modelo.revisions[_DEADLINE_REVISION]
    window_source_ids = {ref for window in revision.deadline_windows for ref in window.source_refs}
    assert design_source not in window_source_ids

    with pytest.raises(RegistryValidationError, match=design_source):
        _rebuild_m123_with_source_window(
            design_source,
            applies_from=date(2024, 1, 1),
            applies_to=date(2024, 1, 22),
        )


# A retroactive provision governs tax periods that closed before it existed, so
# its citation defends a reach its in-force window does not describe.

_RETRO_MODELO = "190"
_RETRO_REVISION = "2024"
_RETRO_FILING_YEAR = 2024
_RETRO_PERIOD = "0A"
_RETRO_LEGAL_ID = "real-decreto-ley-13-2025:art-2"


def _rebuild_m190_with_legal_reach(**update: object) -> RegistrySnapshot:
    """Rebuild the M190 2024 snapshot with the retroactive RDL's reach restaged."""
    modelo, catalogues = _committed_modelo(_RETRO_MODELO)
    reference = catalogues.legal[_RETRO_LEGAL_ID]
    restaged = reference.model_copy(update=update)
    catalogues = catalogues.model_copy(
        update={"legal": {**catalogues.legal, _RETRO_LEGAL_ID: restaged}},
    )
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=_RETRO_FILING_YEAR,
        period=_RETRO_PERIOD,
    )


def test_a_declared_retroactive_provision_grounds_a_devengo_before_it_took_force() -> None:
    """The shipped M190 2024 citation must survive, and not vacuously.

    Both halves of the divergence are asserted: the RDL takes force after the
    2024 devengo, and its declared reach covers it. If either stopped being true
    the test would pass while proving nothing about the axis.
    """
    modelo, catalogues = _committed_modelo(_RETRO_MODELO)
    revision = modelo.revisions[_RETRO_REVISION]
    reference = catalogues.legal[_RETRO_LEGAL_ID]

    assert revision.valid_to is not None
    assert reference.kind in _SUBSTANTIVE_LAW_KINDS, "the devengo axis only applies to substantive law"
    assert reference.effective_from > revision.valid_to, (
        "precondition: the RDL must take force after the devengo it grounds"
    )
    assert reference.governs_periods_from is not None
    assert reference.governs_periods_from <= revision.valid_to

    snapshot = _committed_snapshot(_RETRO_MODELO, _RETRO_FILING_YEAR, _RETRO_PERIOD)

    assert snapshot.revision.id == _RETRO_REVISION


def test_the_same_provision_without_a_declared_reach_still_refuses() -> None:
    """Reach is an explicit claim; withdrawing it restores the in-force test.

    This is the anti-vacuity proof for the field: if the snapshot still built
    with the declaration removed, the devengo gate would be passing for some
    other reason and the declaration would be decorative.
    """
    with pytest.raises(RegistryValidationError, match=_RETRO_LEGAL_ID):
        _rebuild_m190_with_legal_reach(governs_periods_from=None, governs_periods_to=None)


def test_a_forward_reaching_declaration_is_refused_at_the_model_boundary() -> None:
    """The field declares retroactive reach only.

    A forward value would let a citation ground a period its norm never governed
    -- the same failure the gate exists to catch, smuggled through the exemption.
    """
    _modelo, catalogues = _committed_modelo(_RETRO_MODELO)
    reference = catalogues.legal[_RETRO_LEGAL_ID]
    forward = reference.model_dump() | {"governs_periods_from": date(2026, 1, 1)}

    with pytest.raises(ValidationError, match="RETROACTIVE reach only"):
        LegalReference.model_validate(forward)


def test_a_governed_period_end_without_a_start_is_refused() -> None:
    """``governs_periods_to`` alone states a reach with no beginning."""
    _modelo, catalogues = _committed_modelo(_RETRO_MODELO)
    reference = catalogues.legal[_RETRO_LEGAL_ID]
    dangling = reference.model_dump() | {"governs_periods_from": None}

    with pytest.raises(ValidationError, match="governs_periods_to without governs_periods_from"):
        LegalReference.model_validate(dangling)
