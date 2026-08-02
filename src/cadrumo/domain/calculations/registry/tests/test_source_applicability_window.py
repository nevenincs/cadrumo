"""Revision-scoped source references must apply to the revision citing them.

``SourceReference`` carries ``applies_from`` / ``applies_to`` but validated only
that the two dates were internally ordered. Nothing intersected that window with
the revision it was cited by, so a source stale for the revision stayed
authoritative evidence inside a successful snapshot -- and a filing grounded on
it could not be defended.

These tests drive the real bundled M100 2025 authority through the real
``build_snapshot`` path (no doubles), copying a genuine source reference into
stale and future windows to prove the refusal, and pin the two exclusions the
gate deliberately keeps: a modelo-level ref (the modelo's whole documentary
corpus across every filing year) and the boundary dates themselves.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .._errors import RegistryValidationError
from .._schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from .._snapshot import _collect_snapshot_ref_ids, build_snapshot
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


def _revision_scoped_source_id(modelo: ModeloDefinition) -> str:
    """Return one source id the 2025 revision owns and the modelo does not."""
    scoped = _revision_scoped_source_ids(modelo)
    assert scoped, "the M100 2025 revision must own at least one source ref of its own"
    return sorted(scoped)[0]


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


def test_shipped_registry_snapshot_builds_with_every_source_window_intact() -> None:
    """The positive control: the real corpus satisfies the gate unmodified."""
    snapshot = _committed_snapshot(_MODELO, _FILING_YEAR, _PERIOD)

    assert snapshot.revision.id == _REVISION
    assert snapshot.sources, "the snapshot must carry the source evidence it grounds on"


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
