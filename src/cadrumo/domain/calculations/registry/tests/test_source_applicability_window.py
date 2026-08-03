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

from .....core.resources import bundled_path
from .._errors import RegistryValidationError
from .._schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from .._snapshot import _SUBSTANTIVE_LAW_KINDS, _collect_snapshot_ref_ids, build_snapshot
from .._validate_orden_aplicabilidad import RevisionLegalApplicabilityWindow
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
    _legal_ids, source_ids = _collect_snapshot_ref_ids(modelo, modelo.revisions[_REVISION])
    return source_ids - set(modelo.source_refs)


def _revision_scoped_legal_ids(modelo: ModeloDefinition) -> set[str]:
    """Return the legal ids the revision owns, matching the gate's own scope."""
    legal_ids, _source_ids = _collect_snapshot_ref_ids(modelo, modelo.revisions[_REVISION])
    return legal_ids - set(modelo.legal_refs)


def _revision_scoped_legal_id(modelo: ModeloDefinition) -> str:
    """Return one legal id the 2025 revision owns and the modelo does not."""
    scoped = _revision_scoped_legal_ids(modelo)
    assert scoped, "the M100 2025 revision must own at least one legal ref of its own"
    return sorted(scoped)[0]


def _revision_scoped_source_id(modelo: ModeloDefinition) -> str:
    """Return one source id the 2025 revision owns and the modelo does not."""
    scoped = _revision_scoped_source_ids(modelo)
    assert scoped, "the M100 2025 revision must own at least one source ref of its own"
    return sorted(scoped)[0]


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
    modelo, _catalogues = _modelo_and_catalogues()
    source_id = _revision_scoped_source_id(modelo)

    with pytest.raises(RegistryValidationError, match="outside their applicability window"):
        _rebuild_with_source_window(
            source_id,
            applies_from=date(2020, 1, 1),
            applies_to=date(2024, 12, 31),
        )


def test_snapshot_refuses_a_source_that_only_applies_after_the_revision_closed() -> None:
    """The mirror case: a future-only window is equally ungrounded."""
    modelo, _catalogues = _modelo_and_catalogues()
    source_id = _revision_scoped_source_id(modelo)

    with pytest.raises(RegistryValidationError, match="outside their applicability window"):
        _rebuild_with_source_window(
            source_id,
            applies_from=date(2030, 1, 1),
            applies_to=date(2031, 12, 31),
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
    modelo, _catalogues = _modelo_and_catalogues()
    source_id = _revision_scoped_source_id(modelo)

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
