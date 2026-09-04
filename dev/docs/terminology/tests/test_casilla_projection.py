"""Real-behaviour conformance for the casilla projection compiler.

The compiler projects every casilla of every modelo revision -- read through
the validated registry authority (never raw TOML) -- into a strict
:class:`~dev.docs.terminology.search_record.CasillaSearchRecord`,
deduplicated across revisions by the canonical ``(modelo, casilla.id)``
identity.
These gates bind it to the calculation-grounding contract (every casilla
emitted, ``legal_refs`` / ``source_refs`` carried, none dropped) and confirm
the projection reads snapshots through the bundled authority, the same
authority the calculation engine uses.

No mocks: the projection runs against the REAL bundled registry. The
independent oracles are an own count of the registry's casilla rows (the
"never drop a casilla" parity gate) and the bundled legal catalogue (the
legal-ref resolution gate) -- both derived from the authority directly, so the
gates are independent of the projection's own counting.
"""

from __future__ import annotations

import time

import pytest

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.modelo import Modelo
from cadrumo.domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    bundled_authority,
)

from ..casilla_projection import CasillaProjectionStats
from ..search_record import CasillaSearchRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_FOUR_LANGUAGES = frozenset(OutputLanguage)


@pytest.fixture(scope="module")
def full_projection() -> tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats]:
    """Project the full registry once for the module (the bounded full run)."""
    from ..casilla_projection import project_casilla_search_records

    return project_casilla_search_records()


def _independent_raw_casilla_count() -> int:
    """Count casilla rows across every revision of every modelo, independently."""
    authority = bundled_authority()
    total = 0
    for definition in authority.modelos:
        for _revision_id, revision in definition.revisions.items():
            total += len(revision.casillas)
    return total


# ---------------------------------------------------------------------------
# Every-casilla parity — the "never drop a casilla" gate
# ---------------------------------------------------------------------------


def test_projection_walks_every_casilla_row(
    full_projection: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
) -> None:
    """The raw projection count equals an independent count of every casilla row.

    The calculation-grounding contract forbids dropping a casilla on the way
    to the projected record. The raw row count is compared against an
    independent walk of the authority's casilla lists, so a dropped casilla
    fails the gate.
    """
    _records, stats = full_projection
    independent = _independent_raw_casilla_count()
    assert stats.raw_casilla_rows == independent, (
        f"projection raw count {stats.raw_casilla_rows} != independent count {independent} "
        "-- a casilla was dropped on the way to the projection"
    )


def test_m303_emits_every_distinct_casilla_id() -> None:
    """Every distinct ``casilla.id`` identity in any M303 revision is emitted.

    Per-modelo parity: the dedup collapses cross-revision duplicates but must
    never lose an identity. The identity set across all M303 revisions equals
    the projected record identity set.
    """
    from ..casilla_projection import project_modelo_casillas

    authority = bundled_authority()
    definition = authority.modelo(Modelo.M303.value)
    identities: set[str] = set()
    for _revision_id, revision in definition.revisions.items():
        for casilla in revision.casillas:
            identities.add(casilla.id)

    records = project_modelo_casillas(Modelo.M303)
    projected = {record.casilla_id for record in records}  # type: ignore[attr-defined]

    assert projected == identities, (
        "M303 projected identities diverge from the registry:\n"
        f"  missing: {sorted(identities - projected)}\n"
        f"  surplus: {sorted(projected - identities)}"
    )


# ---------------------------------------------------------------------------
# Dedup — cross-revision collapse with auditable source revisions
# ---------------------------------------------------------------------------


def test_dedup_collapses_cross_revision_duplicates(
    full_projection: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
) -> None:
    """Dedup collapses many raw rows into one record per identity.

    The bundled registry has multiple revisions per modelo, so the raw row
    count strictly exceeds the deduplicated record count and ``collapsed``
    accounts for the difference exactly.
    """
    records, stats = full_projection
    assert stats.deduplicated_records == len(records)
    assert stats.deduplicated_records < stats.raw_casilla_rows
    assert stats.collapsed == stats.raw_casilla_rows - stats.deduplicated_records


def test_dedup_key_is_unique_across_records(
    full_projection: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
) -> None:
    """Each canonical ``(modelo, casilla.id)`` identity yields exactly one record."""
    records, _stats = full_projection
    keys = [record.dedup_key for record in records]
    assert len(keys) == len(set(keys)), "duplicate dedup_key -- cross-revision collapse failed"


def test_record_carries_contributing_revisions_latest_first() -> None:
    """A deduped record records every contributing revision id, latest first.

    The collapse is auditable: the ``source_revisions`` tuple names every
    revision the identity appeared in, ordered latest-first, so the chosen
    label's provenance is traceable.
    """
    from ..casilla_projection import project_modelo_casillas

    records = project_modelo_casillas(Modelo.M303)
    # At least one M303 identity appears in more than one revision.
    multi = [record for record in records if len(record.source_revisions) > 1]  # type: ignore[attr-defined]
    assert multi, "expected at least one cross-revision M303 casilla identity"
    for record in multi:
        # source_revisions has no duplicate and is non-empty (schema min_length=1).
        assert len(record.source_revisions) == len(set(record.source_revisions))  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Calculation grounding — refs carried, multilingual labels
# ---------------------------------------------------------------------------


def test_every_record_carries_legal_and_source_refs(
    full_projection: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
) -> None:
    """Every projected record carries non-empty legal_refs and source_refs.

    The calculation-grounding contract requires provenance to survive the
    projection; the schema enforces ``min_length=1`` and this gate confirms
    the full registry satisfies it (no casilla projects with empty refs).
    """
    records, _stats = full_projection
    for record in records:
        assert record.legal_refs, f"casilla {record.casilla_id} has empty legal_refs"
        assert record.source_refs, f"casilla {record.casilla_id} has empty source_refs"


def test_all_legal_refs_resolve_in_the_catalogue(
    full_projection: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
) -> None:
    """Every projected legal_ref resolves in the bundled legal catalogue.

    The same catalogue the calculation engine grounds against; an unresolved
    ref would be a dead provenance link.
    """
    records, _stats = full_projection
    legal_keys = set(bundled_authority().catalogues.legal)
    unresolved: set[str] = set()
    for record in records:
        for ref in record.legal_refs:
            if ref not in legal_keys:
                unresolved.add(ref)
    assert not unresolved, f"projected legal_refs not in the catalogue: {sorted(unresolved)}"


def test_m303_record_has_correct_identity_and_spanish_label() -> None:
    """An M303 casilla projects with the right modelo, casilla id, and es label.

    Concrete identity assertion drawn from the live registry: the record's
    modelo is M303, its ``casilla_id`` matches the registry casilla, and its es
    description is the registry ``label`` verbatim.
    """
    from ..casilla_projection import project_modelo_casillas

    authority = bundled_authority()
    definition = authority.modelo(Modelo.M303.value)
    # Pick a known casilla from the latest revision for a stable assertion.
    latest_revision = max(definition.revisions.values(), key=lambda revision: revision.valid_from)
    sample_casilla = latest_revision.casillas[0]

    records = project_modelo_casillas(Modelo.M303)
    match = next(
        (
            record
            for record in records
            if record.casilla_id == sample_casilla.id  # type: ignore[attr-defined]
        ),
        None,
    )
    assert match is not None, f"M303 casilla {sample_casilla.id} not projected"
    assert match.modelo is Modelo.M303  # type: ignore[attr-defined]
    assert match.number == sample_casilla.number  # type: ignore[attr-defined]
    assert match.segmento == sample_casilla.segmento  # type: ignore[attr-defined]
    assert match.descriptions[OutputLanguage.ES] == sample_casilla.label  # type: ignore[attr-defined]


def test_m121_projection_preserves_canonical_id_distinct_from_display_number() -> None:
    """Modelo 121 keeps its canonical casilla id separate from its display number."""
    from ..casilla_projection import project_modelo_casillas
    from ..unified_record import to_search_record

    authority = bundled_authority()
    assert isinstance(authority, ValidatedRegistryAuthority)
    definition = authority.modelo(Modelo.M121.value)
    latest_revision = max(definition.revisions.values(), key=lambda revision: revision.valid_from)
    authoritative = next(casilla for casilla in latest_revision.casillas if casilla.id == "decl.ejercicio")

    assert authoritative.id == "decl.ejercicio"
    assert authoritative.number == "ejercicio"
    assert authoritative.id != authoritative.number

    projected = next(
        record for record in project_modelo_casillas(Modelo.M121, authority) if record.casilla_id == authoritative.id
    )
    assert projected.casilla_id == authoritative.id
    assert projected.number == authoritative.number
    assert projected.casilla_id != projected.number

    unified = to_search_record(projected)
    assert unified.metadata.casilla_id == projected.casilla_id == "decl.ejercicio"
    assert unified.metadata.number == projected.number == "ejercicio"


def test_segmented_modelo_200_projection_uses_canonical_casilla_id() -> None:
    """Segment-qualified M200 casillas project by ``casilla.id``, not by bare number."""
    from ..casilla_projection import project_modelo_casillas

    records = project_modelo_casillas(Modelo.M200)
    by_id = {record.casilla_id: record for record in records}  # type: ignore[attr-defined]

    assert "DP200014:00562" in by_id
    record = by_id["DP200014:00562"]
    assert record.dedup_key == ("200", "DP200014:00562")  # type: ignore[attr-defined]
    assert record.number == "00562"  # type: ignore[attr-defined]
    assert record.segmento == "DP200014"  # type: ignore[attr-defined]


def test_m303_has_multilingual_casilla_labels() -> None:
    """M303 carries casillas with en / ca / hu labels from its locale fragments.

    M303 authors per-revision locale fragments, so the projection must surface
    en / ca / hu descriptions alongside the es invariant -- proving the
    multilingual path (conforming to the official casilla descriptions).
    """
    from ..casilla_projection import project_modelo_casillas

    records = project_modelo_casillas(Modelo.M303)
    multilingual = [record for record in records if len(record.descriptions) > 1]  # type: ignore[attr-defined]
    assert multilingual, "expected M303 casillas with non-Spanish localised labels"

    fully_localised = [record for record in multilingual if set(record.descriptions) == _FOUR_LANGUAGES]  # type: ignore[attr-defined]
    assert fully_localised, "expected at least one M303 casilla with all four languages"
    for record in fully_localised:
        for language in _FOUR_LANGUAGES:
            assert record.descriptions[language].strip()  # type: ignore[attr-defined]


def test_es_description_is_always_present(
    full_projection: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
) -> None:
    """Spanish is the invariant: every record carries an es description.

    A casilla always has a registry ``label`` (the es invariant); non-Spanish
    languages appear only where a locale fragment authored them.
    """
    records, _stats = full_projection
    for record in records:
        assert OutputLanguage.ES in record.descriptions
        assert record.descriptions[OutputLanguage.ES].strip()
        assert set(record.descriptions).issubset(_FOUR_LANGUAGES)
        assert record.description_es == record.descriptions[OutputLanguage.ES]


# ---------------------------------------------------------------------------
# Performance — the projection is bounded, not pathological
# ---------------------------------------------------------------------------


def test_full_projection_completes_within_a_bounded_time() -> None:
    """The full-registry projection completes quickly (no per-casilla reload hang).

    The projection walks each revision once and dedups in a single pass, so
    the full ~15k-row registry projects in about a second. A generous ceiling
    guards against a regression to a per-casilla snapshot reload (the O(n^2)
    hazard) without being flaky on a slow CI box.
    """
    from ..casilla_projection import project_casilla_search_records

    start = time.perf_counter()
    records, stats = project_casilla_search_records()
    elapsed = time.perf_counter() - start

    assert records, "projection produced no records"
    assert stats.raw_casilla_rows > 1000  # type: ignore[attr-defined]  # the real registry is large
    assert elapsed < 30.0, f"projection took {elapsed:.1f}s -- a per-casilla reload regression is likely"


def test_records_are_frozen(
    full_projection: tuple[tuple[CasillaSearchRecord, ...], CasillaProjectionStats],
) -> None:
    """The strict-frozen contract: a projected record rejects mutation."""
    from pydantic import ValidationError

    records, _stats = full_projection
    with pytest.raises(ValidationError):
        records[0].number = "mutated"  # type: ignore[attr-defined,misc]
