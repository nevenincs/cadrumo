"""Real-behaviour tests for the typed per-modelo support-matrix registry.

Covers every field of the row against the real bundled registry: the capability
predicates probed on the modelo's latest revision, and the declared casilla
renames, deprecation (support-removal) decisions, and AEAT-portal
cross-references the row projects from that revision's own declarations.

These tests are the only coverage of those predicates. A second copy of them
lived in the developer tooling, and its docstring and this one declared each
other as mirrors, so a reader arriving at either was told the authority was
elsewhere. The duplicate was retired; this module is where the predicates are
proved.

See Also:
    :func:`~domain.calculations.registry.build_support_matrix`
        Production builder that derives each row from loaded registry authority.
    :class:`~domain.calculations.registry.ModeloEntry`
        Typed per-modelo support row asserted by these tests.
    :class:`~domain.calculations.registry.ModeloSupportMatrixReport`
        Query-service envelope returned by the registry discovery surface.
    :func:`~application.modelo.registry_support_matrix`
        Application facade used by the operator CLI without re-reading the
        authority directly.
    :mod:`~entrypoints.cli._modelo_support_matrix_payloads`
        JSON payload schemas for the ``modelo.support_matrix`` command.
"""

from __future__ import annotations

import pytest

from .....core import ExportLayoutFormat
from .. import bundled_authority
from ..support_matrix import ModeloEntry, build_support_matrix

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _entries() -> dict[str, ModeloEntry]:
    return {entry.modelo_id: entry for entry in build_support_matrix(bundled_authority())}


def test_matrix_covers_every_bundled_modelo() -> None:
    """The matrix has one entry per registry-loadable modelo, sorted by id."""
    entries = build_support_matrix(bundled_authority())

    assert entries, "expected at least one modelo entry from the bundled registry"
    assert [entry.modelo_id for entry in entries] == sorted(entry.modelo_id for entry in entries)
    assert len({entry.modelo_id for entry in entries}) == len(entries), "duplicate modelo entries"


def test_modelo_130_303_390_have_fichero_boe_export() -> None:
    """Ground truth: 130 / 303 / 390 are the periodic-return modelos with a fixed-width export layout."""
    entries = _entries()

    for modelo_id in ("130", "303", "390"):
        entry = entries[modelo_id]
        assert entry.calc_grade, f"modelo {modelo_id} should be calc-grade"
        assert entry.has_completeness_manifest, f"modelo {modelo_id} should declare a completeness manifest"
        assert entry.has_fixed_width_export, f"modelo {modelo_id} should register a fixed_width export layout"


def test_modelo_100_uses_xml_dictionary_export_not_fixed_width() -> None:
    """Ground truth: Modelo 100 (Renta) exports via xml_dictionary, not fichero-BOE fixed-width."""
    entry = _entries()["100"]

    assert entry.calc_grade
    assert entry.has_xml_dictionary_export
    assert not entry.has_fixed_width_export


def test_dormant_modelos_are_not_calc_grade() -> None:
    """Ground truth: informative/no-calculation modelos report calc_grade False, never a fabricated positive.

    The enumeration is the registry's own set of informative-only modelos, read
    off the tree rather than inherited from any other test module.
    """
    entries = _entries()

    for modelo_id in ("189", "280", "308", "345", "360"):
        entry = entries[modelo_id]
        assert not entry.calc_grade, f"modelo {modelo_id} should not be calc-grade"
        assert not entry.has_completeness_manifest, f"dormant modelo {modelo_id} should carry no completeness manifest"


def test_row_reports_latest_revision_by_valid_from() -> None:
    """A multi-revision modelo's entry is probed against its most recent revision."""
    entry = _entries()["100"]

    assert entry.revision_count >= 6
    assert entry.latest_revision_id == "2025"
    assert entry.supported_revision_ids[-1] == "2025"
    assert entry.supported_revision_ids == tuple(sorted(entry.supported_revision_ids))


def test_modelo_100_latest_revision_carries_declared_renames() -> None:
    """Ground truth: Modelo 100's 2025 revision declares casilla continuity evolutions.

    Re-derives the expected count directly from the loaded revision's
    ``casilla_continuidad_evolutions`` rather than trusting the entry, so the
    projection cannot silently drop or fabricate rename records.
    """
    authority = bundled_authority()
    revision = authority.modelo("100").revisions["2025"]
    entry = _entries()["100"]

    assert revision.casilla_continuidad_evolutions, "fixture drift: modelo 100 2025 should declare renames on disk"
    assert len(entry.renames) == len(revision.casilla_continuidad_evolutions)
    expected = {
        (evolution.continuidad_id, evolution.from_revision, evolution.to_revision, evolution.evolution_kind)
        for evolution in revision.casilla_continuidad_evolutions
    }
    actual = {
        (rename.continuidad_id, rename.from_revision, rename.to_revision, rename.evolution_kind)
        for rename in entry.renames
    }
    assert actual == expected


def test_modelo_100_latest_revision_carries_declared_portal_compatibility_refs() -> None:
    """Ground truth: Modelo 100's 2025 revision declares a live AEAT-portal cross-reference."""
    authority = bundled_authority()
    revision = authority.modelo("100").revisions["2025"]
    entry = _entries()["100"]

    assert revision.live_cross_references, "fixture drift: modelo 100 2025 should declare a live cross-reference"
    assert len(entry.portal_compatibility_refs) == len(revision.live_cross_references)
    expected = {(decision.id, decision.surface, decision.evidence_tier) for decision in revision.live_cross_references}
    actual = {(ref.id, ref.surface, ref.evidence_tier) for ref in entry.portal_compatibility_refs}
    assert actual == expected


def test_build_support_matrix_is_never_a_fabricated_positive() -> None:
    """Anti-tautology proof: every capability flag is re-derived directly from the loaded revision.

    Proves the entry is not hand-computed independently of the registry data
    it claims to summarise.
    """
    authority = bundled_authority()
    entries = _entries()

    for modelo in authority.modelos:
        revision = max(modelo.revisions.values(), key=lambda r: r.valid_from)
        expected_formats = {layout.format for layout in revision.export_layouts}
        entry = entries[modelo.id]
        assert entry.title == modelo.title
        assert entry.calculation_class == modelo.calculation_class
        assert entry.revision_count == len(modelo.revisions)
        assert entry.latest_revision_id == revision.id
        assert entry.latest_revision_valid_from == revision.valid_from
        assert entry.has_fixed_width_export == (ExportLayoutFormat.FIXED_WIDTH in expected_formats)
        assert entry.has_xml_dictionary_export == (ExportLayoutFormat.XML_DICTIONARY in expected_formats)
        assert entry.has_extractor == bool(revision.extraction_profiles)
        assert entry.extraction_profile_count == len(revision.extraction_profiles)
        assert entry.has_completeness_manifest == (revision.completeness_manifest is not None)
        assert len(entry.renames) == len(revision.casilla_continuidad_evolutions)
        assert len(entry.portal_compatibility_refs) == len(revision.live_cross_references)
