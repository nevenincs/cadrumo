"""Real-behaviour tests for the orden_aplicabilidad ratchet gate.

Tests cover:
- Ratchet: new unstamped revision is a hard failure; existing unstamped
  revision is a follow-up item (not a hard failure).
- A stamped entry that resolves in the catalogue with corpus_ref and is in
  legal_refs passes cleanly.
- A dangling (non-existent) orden_aplicabilidad entry is a hard failure.
- An orden_aplicabilidad entry present in the catalogue but absent from
  legal_refs is a hard failure.
- Backfilled revisions (M036, M100/2025, M130, M111, M123, M131, M202, M232,
  M303, M369)
  load from the committed registry without hard failures.
- Open-ended *-y-siguientes revisions in the backfilled set have
  orden_aplicabilidad declared (connective gate).

No mocks, no skips, no xfail.  The ratchet date is 2026-06-10.
"""

from __future__ import annotations

from datetime import date
from functools import cache

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree
from .._schema import (
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    PeriodSelector,
    RegistryCatalogues,
)
from .._validate_orden_aplicabilidad import (
    ORDEN_APLICABILIDAD_RATCHET_DATE,
    validate_orden_aplicabilidad,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_REGISTRY_ROOT = bundled_path("registry", "aeat")

# Minimal synthetic legal catalogue entry for tests.
_VALID_LEGAL_REF = LegalReference(
    id="orden-test-0001:art-1",
    evidence_tier="legal_authority",
    authority="boe",
    kind="orden",
    corpus_ref="corpus/normatives/html/orden-test-0001.html#a1",
    document_id="BOE-A-2000-00001",
    permalink="https://www.boe.es/eli/es/o/2000/01/01/test-0001",
    effective_from=date(2000, 1, 1),
    review_status="reviewed",
)
# Minimal source ref used wherever a test revision needs one valid reference
# before the orden_aplicabilidad gate can run.
_MINIMAL_SOURCE_REF = "src-test-0001"

_VALID_CATALOGUE: dict[str, LegalReference] = {
    "orden-test-0001:art-1": _VALID_LEGAL_REF,
}

_POST_RATCHET_DATE = ORDEN_APLICABILIDAD_RATCHET_DATE  # 2026-06-10


def _make_revision(
    *,
    revision_id: str,
    valid_from: date,
    valid_to: date | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    years: tuple[int, ...] = (),
    periods: tuple[str, ...] = ("1T",),
    legal_refs: tuple[str, ...] | None = None,
    orden_aplicabilidad: tuple[str, ...] = (),
) -> ModeloRevision:
    """Build a minimal ModeloRevision for gate testing.

    ``legal_refs`` defaults to the minimal source ref entry to satisfy
    ``LegalRefs`` ``min_length=1`` before gate validation. Pass an explicit
    tuple to override.
    """
    if year_from is not None:
        selector = PeriodSelector(year_from=year_from, year_to=year_to, periods=periods)
    elif years:
        selector = PeriodSelector(years=years, periods=periods)
    else:
        raise ValueError("supply either year_from or years")
    # LegalRefs and SourceRefs both require min_length=1 before this gate runs.
    effective_legal_refs: tuple[str, ...] = legal_refs if legal_refs is not None else (_MINIMAL_SOURCE_REF,)
    return ModeloRevision(
        id=revision_id,
        valid_from=valid_from,
        valid_to=valid_to,
        period_selector=selector,
        legal_refs=effective_legal_refs,
        source_refs=(_MINIMAL_SOURCE_REF,),
        orden_aplicabilidad=orden_aplicabilidad,
    )


# ---------------------------------------------------------------------------
# Ratchet: new unstamped revision is a hard failure
# ---------------------------------------------------------------------------


def test_ratchet_hard_fails_new_revision_without_orden_aplicabilidad() -> None:
    """A new revision (valid_from >= ratchet date) with no orden_aplicabilidad is a
    hard failure.  This is the ratchet gate: new revisions MUST be stamped.
    """
    revision = _make_revision(
        revision_id="test-new-unstamped",
        valid_from=_POST_RATCHET_DATE,  # on ratchet date
        valid_to=date(2026, 12, 31),
        years=(2026,),
        periods=("1T",),
        # legal_refs defaults to minimal entry (min_length=1 satisfied)
        orden_aplicabilidad=(),
    )
    hard, follow_up = validate_orden_aplicabilidad(
        "modelo test revision test-new-unstamped",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 1, f"Expected one hard failure, got {hard}"
    assert "MUST declare" in hard[0]
    assert "orden_aplicabilidad" in hard[0]
    assert len(follow_up) == 0


# ---------------------------------------------------------------------------
# Ratchet: existing (pre-ratchet) unstamped revision is a follow-up, not
# a hard failure — the registry MUST still load.
# ---------------------------------------------------------------------------


def test_ratchet_follow_up_for_existing_revision_without_orden_aplicabilidad() -> None:
    """A pre-ratchet revision without orden_aplicabilidad produces a follow-up item
    (not a hard failure) so the existing corpus continues to load.
    """
    pre_ratchet_date = date(2019, 1, 1)
    revision = _make_revision(
        revision_id="test-old-unstamped",
        valid_from=pre_ratchet_date,
        valid_to=date(2019, 12, 31),
        years=(2019,),
        periods=("1T",),
        # legal_refs defaults to minimal entry (min_length=1 satisfied)
        orden_aplicabilidad=(),
    )
    hard, follow_up = validate_orden_aplicabilidad(
        "modelo test revision test-old-unstamped",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 0, f"Expected no hard failures, got {hard}"
    assert len(follow_up) == 1
    assert "follow-up backfill" in follow_up[0].lower() or "backfill" in follow_up[0].lower()


# ---------------------------------------------------------------------------
# Stamped entry resolves cleanly when catalogue, corpus_ref, legal_refs OK
# ---------------------------------------------------------------------------


def test_valid_orden_aplicabilidad_passes_all_checks() -> None:
    """A stamped revision with a valid catalogue entry, corpus_ref, and the entry
    also present in legal_refs produces no hard failures and no follow-up items.
    """
    revision = _make_revision(
        revision_id="test-stamped-valid",
        valid_from=date(2020, 1, 1),
        valid_to=date(2020, 12, 31),
        years=(2020,),
        periods=("1T",),
        # Must include the orden in legal_refs to pass check (iii).
        legal_refs=("orden-test-0001:art-1",),
        orden_aplicabilidad=("orden-test-0001:art-1",),
    )
    hard, follow_up = validate_orden_aplicabilidad(
        "modelo test revision test-stamped-valid",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 0, f"Unexpected hard failures: {hard}"
    assert len(follow_up) == 0, f"Unexpected follow-up items: {follow_up}"


# ---------------------------------------------------------------------------
# Dangling orden_aplicabilidad entry (not in catalogue) is a hard failure
# ---------------------------------------------------------------------------


def test_dangling_orden_aplicabilidad_entry_is_hard_failure() -> None:
    """An orden_aplicabilidad entry that does not exist in the legal catalogue is
    a hard failure — fabricated/dangling ordenes MUST NOT pass the gate.
    """
    revision = _make_revision(
        revision_id="test-dangling",
        valid_from=date(2020, 1, 1),
        valid_to=date(2020, 12, 31),
        years=(2020,),
        periods=("1T",),
        legal_refs=("orden-test-0001:art-1", "orden-nonexistent-9999:art-1"),
        # This entry does not exist in _VALID_CATALOGUE:
        orden_aplicabilidad=("orden-nonexistent-9999:art-1",),
    )
    hard, _ = validate_orden_aplicabilidad(
        "modelo test revision test-dangling",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 1
    assert "does not resolve in the legal catalogue" in hard[0]


# ---------------------------------------------------------------------------
# Entry in catalogue but absent from legal_refs is a hard failure
# ---------------------------------------------------------------------------


def test_orden_aplicabilidad_absent_from_legal_refs_is_hard_failure() -> None:
    """An orden_aplicabilidad entry that resolves in the catalogue but is not in
    the revision's legal_refs is a hard failure — the snapshot ref-collection
    must carry the orden.
    """
    revision = _make_revision(
        revision_id="test-missing-from-legal-refs",
        valid_from=date(2020, 1, 1),
        valid_to=date(2020, 12, 31),
        years=(2020,),
        periods=("1T",),
        # orden-test-0001:art-1 is intentionally NOT in legal_refs (only the
        # minimal required ref is present), but IS in the catalogue — triggers
        # check (iii) failure.
        legal_refs=(_MINIMAL_SOURCE_REF,),
        orden_aplicabilidad=("orden-test-0001:art-1",),
    )
    hard, _ = validate_orden_aplicabilidad(
        "modelo test revision test-missing-from-legal-refs",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 1
    assert "not present in the revision's legal_refs" in hard[0]


# ---------------------------------------------------------------------------
# Open-ended *-y-siguientes without orden_aplicabilidad is a follow-up
# (pre-ratchet) — the connective gate applied as advisory backfill signal
# ---------------------------------------------------------------------------


def test_s24_open_ended_pre_ratchet_revision_without_orden_is_follow_up() -> None:
    """An open-ended (year_from set, valid_to None) pre-ratchet revision without
    orden_aplicabilidad is a follow-up item (connective gate).  It does NOT
    block load — it tracks the open-ended claim as needing BOE anchoring.
    """
    revision = _make_revision(
        revision_id="test-open-ended-pre-ratchet",
        valid_from=date(2019, 1, 1),
        valid_to=None,  # open-ended
        year_from=2019,
        periods=("1T",),
        # legal_refs defaults to minimal entry (min_length=1 satisfied)
        orden_aplicabilidad=(),
    )
    hard, follow_up = validate_orden_aplicabilidad(
        "modelo test revision test-open-ended-pre-ratchet",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 0, f"Expected no hard failures, got {hard}"
    assert len(follow_up) == 1
    # Connective gate message must mention open-ended / y siguientes / BOE
    msg = follow_up[0].lower()
    assert "open-ended" in msg or "y siguientes" in msg or "open_ended" in msg


# ---------------------------------------------------------------------------
# Backfilled revisions in the committed registry load cleanly
# ---------------------------------------------------------------------------


@cache
def _committed_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return tuple(modelos), catalogues


@pytest.mark.parametrize(
    ("modelo_id", "revision_id"),
    [
        ("036", "2025-02-03-y-siguientes"),
        ("100", "2020"),
        ("100", "2021"),
        ("100", "2022"),
        ("100", "2023"),
        ("100", "2024"),
        ("100", "2025"),
        ("111", "2019-y-siguientes"),
        ("115", "2019-y-siguientes"),
        ("123", "2019-2023"),
        ("123", "2024-y-siguientes"),
        ("130", "2019-y-siguientes"),
        ("131", "2019-2023"),
        ("131", "2024"),
        ("131", "2025"),
        ("131", "2026"),
        ("151", "2015-y-siguientes"),
        ("180", "2019-2022"),
        ("180", "2023-y-siguientes"),
        ("184", "2015-y-siguientes"),
        ("190", "2024-y-siguientes"),
        ("193", "2024-y-siguientes"),
        ("200", "2024-y-siguientes"),
        ("202", "2019-2022"),
        ("202", "2023-2024"),
        ("202", "2025-y-siguientes"),
        ("210", "2025"),
        ("232", "2016-2017"),
        ("232", "2018-y-siguientes"),
        ("303", "2023-y-siguientes"),
        ("303", "2009-y-siguientes"),
        ("322", "2008-y-siguientes"),
        ("308", "2009-y-siguientes"),
        ("309", "2004-y-siguientes"),
        ("347", "2008-y-siguientes"),
        ("353", "2008-y-siguientes"),
        ("360", "2010-y-siguientes"),
        ("369", "esquema-exterior"),
        ("369", "esquema-union"),
        ("369", "esquema-importacion"),
        ("390", "2010-y-siguientes"),
        ("349", "2020-y-siguientes"),
        ("714", "2021-y-siguientes"),
        ("720", "2013-y-siguientes"),
        ("840", "2003-y-siguientes"),
    ],
)
def test_backfilled_revision_has_valid_orden_aplicabilidad(modelo_id: str, revision_id: str) -> None:
    """Each backfilled revision declares a non-empty orden_aplicabilidad that resolves
    in the legal catalogue with corpus_ref and is present in legal_refs — the three
    ratchet gate checks all pass, and the hard-failure list is empty.
    """
    modelos, catalogues = _committed_registry_tree()
    modelo = next((m for m in modelos if m.id == modelo_id), None)
    assert modelo is not None, f"Modelo {modelo_id!r} not found in committed registry"
    revision = modelo.revisions.get(revision_id)
    assert revision is not None, f"Revision {revision_id!r} not found in modelo {modelo_id!r}"

    assert len(revision.orden_aplicabilidad) > 0, (
        f"Backfilled revision {modelo_id}/{revision_id} has empty orden_aplicabilidad"
    )

    hard, _ = validate_orden_aplicabilidad(
        f"modelo {modelo_id} revision {revision_id}",
        modelo_id,
        revision,
        catalogues.legal,
    )
    assert len(hard) == 0, f"Backfilled revision {modelo_id}/{revision_id} has hard gate failures: {hard}"


# ---------------------------------------------------------------------------
# Open-ended backfilled revisions have orden_aplicabilidad set
# (connective gate: the *-y-siguientes claim is BOE-anchored)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("modelo_id", "revision_id"),
    [
        ("036", "2025-02-03-y-siguientes"),
        ("111", "2019-y-siguientes"),
        ("115", "2019-y-siguientes"),
        ("123", "2024-y-siguientes"),
        ("130", "2019-y-siguientes"),
        ("151", "2015-y-siguientes"),
        ("180", "2023-y-siguientes"),
        ("184", "2015-y-siguientes"),
        ("190", "2024-y-siguientes"),
        ("193", "2024-y-siguientes"),
        ("200", "2024-y-siguientes"),
        ("202", "2025-y-siguientes"),
        ("210", "2025"),
        ("232", "2018-y-siguientes"),
        ("303", "2023-y-siguientes"),
        ("303", "2009-y-siguientes"),
        ("322", "2008-y-siguientes"),
        ("308", "2009-y-siguientes"),
        ("309", "2004-y-siguientes"),
        ("347", "2008-y-siguientes"),
        ("353", "2008-y-siguientes"),
        ("360", "2010-y-siguientes"),
        ("369", "esquema-exterior"),
        ("369", "esquema-union"),
        ("369", "esquema-importacion"),
        ("390", "2010-y-siguientes"),
        ("349", "2020-y-siguientes"),
        ("714", "2021-y-siguientes"),
        ("720", "2013-y-siguientes"),
        ("840", "2003-y-siguientes"),
    ],
)
def test_s24_open_ended_backfilled_revision_has_orden_aplicabilidad(modelo_id: str, revision_id: str) -> None:
    """Every open-ended (*-y-siguientes / year_from with no valid_to) backfilled
    revision has orden_aplicabilidad declared — the open-ended applicability claim
    is BOE-anchored per the connective gate (Ruling 5 boundary).
    """
    modelos, _catalogues = _committed_registry_tree()
    modelo = next((m for m in modelos if m.id == modelo_id), None)
    assert modelo is not None
    revision = modelo.revisions.get(revision_id)
    assert revision is not None

    # Confirm it IS open-ended.
    assert revision.valid_to is None, (
        f"{modelo_id}/{revision_id} was expected to be open-ended but has valid_to={revision.valid_to}"
    )

    # Confirm the connective gate is satisfied.
    assert len(revision.orden_aplicabilidad) > 0, (
        f"Open-ended revision {modelo_id}/{revision_id} has no orden_aplicabilidad "
        f"— the *-y-siguientes claim is not BOE-anchored (S24 connective gate)"
    )
