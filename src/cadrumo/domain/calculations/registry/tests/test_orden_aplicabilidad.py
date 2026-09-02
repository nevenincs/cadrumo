"""Real-behaviour tests for the orden_aplicabilidad gate.

Tests cover:
- Any unstamped revision is a hard failure.
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

No mocks, no skips, no xfail.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources.bundled_data import bundled_path
from .....tests.registry_snapshot import build_snapshot
from .._validate_orden_aplicabilidad import validate_orden_aplicabilidad
from ..errors import RegistryValidationError
from ..ids import LegalRefId, SourceRefId
from ..schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ..schema_base import EvidenceTier
from ..schema_references import LegalReference, PeriodSelector
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_VALID_LEGAL_REF_ID: LegalRefId = "orden-test-0001:art-1"
_NON_ORDEN_LEGAL_REF: LegalRefId = "ley-58-2003:art-29"

# Minimal synthetic legal catalogue entry for tests.
_VALID_LEGAL_REF = LegalReference(
    id=_VALID_LEGAL_REF_ID,
    evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
    authority="boe",
    kind="orden",
    corpus_ref="corpus/normatives/html/orden-test-0001.html#a1",
    document_id="BOE-A-2000-00001",
    permalink="https://www.boe.es/eli/es/o/2000/01/01/test-0001",
    effective_from=date(2000, 1, 1),
    review_status="operator_reviewed",
    reviewed_at=date(2026, 7, 1),
    reviewed_by="codex test fixture",
    required_text=("Artículo 1",),
)
# Minimal source ref used wherever a test revision needs one valid source
# reference before the orden_aplicabilidad gate can run.
_MINIMAL_SOURCE_REF: SourceRefId = "src-test-0001"

_VALID_CATALOGUE: dict[str, LegalReference] = {
    _VALID_LEGAL_REF_ID: _VALID_LEGAL_REF,
}


def _make_revision(
    *,
    revision_id: str,
    valid_from: date,
    valid_to: date | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    years: tuple[int, ...] = (),
    periods: tuple[str, ...] = ("1T",),
    legal_refs: tuple[LegalRefId, ...] | None = None,
    orden_aplicabilidad: tuple[LegalRefId, ...] = (),
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
    effective_legal_refs: tuple[LegalRefId, ...] = legal_refs if legal_refs is not None else (_NON_ORDEN_LEGAL_REF,)
    return ModeloRevision(
        id=revision_id,
        localization_key=f"test.schema.revision.{revision_id}.label",
        valid_from=valid_from,
        valid_to=valid_to,
        period_selector=selector,
        legal_refs=effective_legal_refs,
        source_refs=(_MINIMAL_SOURCE_REF,),
        orden_aplicabilidad=orden_aplicabilidad,
    )


# ---------------------------------------------------------------------------
# Missing orden_aplicabilidad is a hard failure
# ---------------------------------------------------------------------------


def test_missing_orden_aplicabilidad_is_hard_failure() -> None:
    """Any revision without orden_aplicabilidad is a hard failure."""
    revision = _make_revision(
        revision_id="test-unstamped",
        valid_from=date(2019, 1, 1),
        valid_to=date(2019, 12, 31),
        years=(2019,),
        periods=("1T",),
        # legal_refs defaults to a non-orden legal entry (min_length=1 satisfied)
        orden_aplicabilidad=(),
    )

    hard = validate_orden_aplicabilidad(
        "modelo test revision test-unstamped",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 1, f"Expected one hard failure, got {hard}"
    assert "MUST declare" in hard[0]
    assert "orden_aplicabilidad" in hard[0]


# ---------------------------------------------------------------------------
# Stamped entry resolves cleanly when catalogue, corpus_ref, legal_refs OK
# ---------------------------------------------------------------------------


def test_valid_orden_aplicabilidad_passes_all_checks() -> None:
    """A stamped revision with a valid catalogue entry, corpus_ref, and the entry
    also present in legal_refs produces no hard failures.
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
    hard = validate_orden_aplicabilidad(
        "modelo test revision test-stamped-valid",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 0, f"Unexpected hard failures: {hard}"


def _modelo_100_2025() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = _committed_registry_tree()
    modelo = next(modelo for modelo in modelos if modelo.id == "100")
    return modelo, catalogues


def _catalogues_with_m100_2025_order_window(
    catalogues: RegistryCatalogues,
    *,
    effective_from: date,
    effective_to: date | None = None,
) -> RegistryCatalogues:
    ref_id = "orden-hac-277-2026:art-3"
    reference = catalogues.legal[ref_id].model_copy(
        update={"effective_from": effective_from, "effective_to": effective_to},
    )
    return catalogues.model_copy(update={"legal": {**catalogues.legal, ref_id: reference}})


def test_m100_2025_accepts_form_order_effective_in_presentation_window() -> None:
    """The 2025 form order takes effect in 2026 before its filing campaign."""
    modelo, catalogues = _modelo_100_2025()

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )

    reference = snapshot.legal["orden-hac-277-2026:art-3"]
    assert reference.effective_from == date(2026, 3, 28)
    assert max(window.closes_on for window in snapshot.deadline_windows.values()) == date(2026, 6, 30)


def test_m100_2025_accepts_form_order_on_presentation_close_boundary() -> None:
    modelo, catalogues = _modelo_100_2025()
    boundary_catalogues = _catalogues_with_m100_2025_order_window(
        catalogues,
        effective_from=date(2026, 6, 30),
    )

    snapshot = build_snapshot(
        modelo,
        boundary_catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )

    assert snapshot.legal["orden-hac-277-2026:art-3"].effective_from == date(2026, 6, 30)


def test_m100_2025_rejects_form_order_after_presentation_close() -> None:
    modelo, catalogues = _modelo_100_2025()
    future_catalogues = _catalogues_with_m100_2025_order_window(
        catalogues,
        effective_from=date(2026, 7, 1),
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"takes effect on 2026-07-01 after .* closes on 2026-06-30",
    ):
        build_snapshot(
            modelo,
            future_catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period="0A",
        )


def test_m100_2025_rejects_form_order_expired_before_revision() -> None:
    modelo, catalogues = _modelo_100_2025()
    expired_catalogues = _catalogues_with_m100_2025_order_window(
        catalogues,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 12, 31),
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"expired on 2024-12-31 before .* starts on 2025-01-01",
    ):
        build_snapshot(
            modelo,
            expired_catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period="0A",
        )


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
    hard = validate_orden_aplicabilidad(
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
        # non-orden legal ref is present), but IS in the catalogue — triggers
        # check (iii) failure.
        legal_refs=(_NON_ORDEN_LEGAL_REF,),
        orden_aplicabilidad=("orden-test-0001:art-1",),
    )
    hard = validate_orden_aplicabilidad(
        "modelo test revision test-missing-from-legal-refs",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 1
    assert "not present in the revision's legal_refs" in hard[0]


# ---------------------------------------------------------------------------
# Open-ended *-y-siguientes without orden_aplicabilidad is a hard failure
# ---------------------------------------------------------------------------


def test_s24_open_ended_revision_without_orden_is_hard_failure() -> None:
    """An open-ended revision without orden_aplicabilidad is a hard failure."""
    revision = _make_revision(
        revision_id="test-open-ended-unstamped",
        valid_from=date(2019, 1, 1),
        valid_to=None,  # open-ended
        year_from=2019,
        periods=("1T",),
        # legal_refs defaults to a non-orden legal entry (min_length=1 satisfied)
        orden_aplicabilidad=(),
    )
    hard = validate_orden_aplicabilidad(
        "modelo test revision test-open-ended-unstamped",
        "test",
        revision,
        _VALID_CATALOGUE,
    )
    assert len(hard) == 1, f"Expected one hard failure, got {hard}"
    assert "MUST declare" in hard[0]
    assert "orden_aplicabilidad" in hard[0]


# ---------------------------------------------------------------------------
# Backfilled revisions in the committed registry load cleanly
# ---------------------------------------------------------------------------


def test_committed_registry_has_no_unstamped_revisions() -> None:
    """Every committed revision declares orden_aplicabilidad."""
    modelos, _catalogues = _committed_registry_tree()
    offenders = sorted(
        f"{modelo.id}/{revision_id}"
        for modelo in modelos
        for revision_id, revision in modelo.revisions.items()
        if not revision.orden_aplicabilidad
    )

    assert not offenders, "Committed revisions without orden_aplicabilidad:\n  " + "\n  ".join(offenders)


def _every_committed_revision() -> list[tuple[str, str]]:
    """Every (modelo, revision) pair the committed tree carries.

    This was a hand-listed inventory of about forty-five pairs. It covered half
    the tree, it silently stopped covering a revision the moment one was renamed
    -- the 2015-y-siguientes -> 2015-2022 split of modelo 151 left a pair naming
    a revision that no longer exists, and the case died on a lookup rather than
    on the property -- and a newly authored revision was never added to it at
    all. Deriving the population gates on the PROPERTY instead of on a tally, so
    a new revision is covered the day it lands.
    """
    modelos, _catalogues = _committed_registry_tree()
    return sorted((str(modelo.id), revision_id) for modelo in modelos for revision_id in modelo.revisions)


@pytest.mark.parametrize(("modelo_id", "revision_id"), _every_committed_revision())
def test_backfilled_revision_has_valid_orden_aplicabilidad(modelo_id: str, revision_id: str) -> None:
    """Each backfilled revision declares a non-empty orden_aplicabilidad that resolves
    in the legal catalogue with corpus_ref and is present in legal_refs — the three
    gate checks all pass, and the hard-failure list is empty.
    """
    modelos, catalogues = _committed_registry_tree()
    modelo = next((m for m in modelos if m.id == modelo_id), None)
    assert modelo is not None, f"Modelo {modelo_id!r} not found in committed registry"
    revision = modelo.revisions.get(revision_id)
    assert revision is not None, f"Revision {revision_id!r} not found in modelo {modelo_id!r}"

    assert len(revision.orden_aplicabilidad) > 0, (
        f"Backfilled revision {modelo_id}/{revision_id} has empty orden_aplicabilidad"
    )

    hard = validate_orden_aplicabilidad(
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


def _every_open_ended_revision() -> list[tuple[str, str]]:
    """Every committed revision that is genuinely open-ended (`valid_to is None`).

    This was hand-listed, and the list decayed in BOTH directions: it named
    revisions that had since been closed -- 193/2024, 303/2022, 303/2023,
    210/2025 and 308/2022 all carry a `valid_to` now, so the case failed on its
    own premise rather than on the property -- and it needed a curated comment
    explaining why 714/2021-y-siguientes had been removed when its enrollment
    window closed. Deriving the population from `valid_to is None` makes the
    membership question answer itself: a revision that closes leaves this gate
    automatically, and one that opens joins it.
    """
    modelos, _catalogues = _committed_registry_tree()
    return sorted(
        (str(modelo.id), revision_id)
        for modelo in modelos
        for revision_id, revision in modelo.revisions.items()
        if revision.valid_to is None
    )


@pytest.mark.parametrize(("modelo_id", "revision_id"), _every_open_ended_revision())
def test_s24_open_ended_backfilled_revision_has_orden_aplicabilidad(modelo_id: str, revision_id: str) -> None:
    """Every open-ended (*-y-siguientes / year_from with no valid_to) backfilled
    revision has orden_aplicabilidad declared — the open-ended applicability claim
    is BOE-anchored per the connective gate.
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
        f"— the *-y-siguientes claim is not BOE-anchored (the connective gate)"
    )
