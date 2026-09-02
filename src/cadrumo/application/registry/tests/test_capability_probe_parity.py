"""Capability predicates are folded once, on the support authority.

The support matrix and the conformance composer both need "is this revision
calc grade", "does it register a fichero-BOE layout", and the rest of the same
predicate set. They used to fold those expressions independently, which made
the shipped support row and the conformance row two authorities for one answer
— equal today, free to drift the first time a primitive or a scope changed.
:func:`~domain.calculations.registry.revision_capability_probe` is now the
single fold and both consume it.

Read against the real bundled registry tree: no fixture stands between an
assertion and the shipped data. The parity claim alone would be weak — both
surfaces call one function, so equality is close to guaranteed — so the load
bearing test here is the DIVERGENCE one: it proves the two surfaces still
answer different questions (this revision vs the modelo's latest revision) and
have not been collapsed into one by the deduplication. It fails loudly rather
than passing vacuously when the tree offers no modelo whose latest revision
differs in capabilities from an earlier one.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.support_matrix import build_support_matrix, revision_capability_probe
from ....tests.registry_conformance import audit_bundled_registry_conformance

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Anti-vacuity floor, far below the tree's real size, so ordinary registry
#: growth never reds this while an empty or collapsed compose cannot clear it.
_MINIMUM_COMPARED_ROWS = 60


def test_every_conformance_row_matches_the_support_authority_probe() -> None:
    """Each row's capability facts equal the authority's probe of THAT revision."""
    authority = bundled_authority()
    profile = audit_bundled_registry_conformance()

    compared = 0
    divergent: list[str] = []
    for row in profile.rows:
        modelo = authority.modelo(str(row.modelo))
        revision = modelo.revisions[row.revision]
        probe = revision_capability_probe(revision, modelo_id=str(row.modelo))
        facts = row.capabilities
        compared += 1
        if (
            facts.calc_grade,
            facts.has_completeness_manifest,
            facts.has_fixed_width_export,
            facts.has_xml_dictionary_export,
            facts.extraction_profile_count,
        ) != (
            probe.calc_grade,
            probe.has_completeness_manifest,
            probe.has_fixed_width_export,
            probe.has_xml_dictionary_export,
            probe.extraction_profile_count,
        ):
            divergent.append(f"{row.modelo}/{row.revision}")

    assert compared >= _MINIMUM_COMPARED_ROWS, f"only {compared} rows compared; the profile collapsed"
    assert not divergent, f"conformance capability facts diverge from the support authority probe: {divergent}"


def test_support_matrix_rows_probe_the_latest_revision() -> None:
    """Each support-matrix row equals the probe of its modelo's latest revision."""
    authority = bundled_authority()
    entries = build_support_matrix(authority)

    assert entries, "the bundled registry produced no support-matrix rows"
    for entry in entries:
        modelo = authority.modelo(str(entry.modelo_id))
        latest = modelo.revisions[entry.latest_revision_id]
        probe = revision_capability_probe(latest, modelo_id=str(entry.modelo_id))
        assert entry.calc_grade == probe.calc_grade, entry.modelo_id
        assert entry.has_completeness_manifest == probe.has_completeness_manifest, entry.modelo_id
        assert entry.has_fixed_width_export == probe.has_fixed_width_export, entry.modelo_id
        assert entry.has_xml_dictionary_export == probe.has_xml_dictionary_export, entry.modelo_id
        assert entry.has_extractor == probe.has_extractor, entry.modelo_id
        assert entry.extraction_profile_count == probe.extraction_profile_count, entry.modelo_id


def test_this_revision_and_latest_revision_capabilities_stay_distinct() -> None:
    """A non-latest revision keeps its own capabilities, not the latest ones.

    This is what the shared fold must NOT erase. The conformance row describes
    the revision it names; the support probe on that same row describes the
    modelo's latest revision. Where the tree declares a modelo whose latest
    revision differs in capabilities from an earlier one, the two must report
    that difference rather than agreeing.
    """
    authority = bundled_authority()
    profile = audit_bundled_registry_conformance()

    observed_divergences: list[str] = []
    for row in profile.rows:
        support = row.latest_revision_support
        if support is None or support.describes_this_revision:
            continue
        modelo = authority.modelo(str(row.modelo))
        this_probe = revision_capability_probe(modelo.revisions[row.revision], modelo_id=str(row.modelo))
        latest_probe = revision_capability_probe(
            modelo.revisions[support.probed_revision],
            modelo_id=str(row.modelo),
        )
        if this_probe == latest_probe:
            continue
        observed_divergences.append(f"{row.modelo}/{row.revision}")
        # The row reports THIS revision; the support probe reports the latest.
        assert row.capabilities.calc_grade == this_probe.calc_grade
        assert row.capabilities.has_completeness_manifest == this_probe.has_completeness_manifest
        assert support.calc_grade == latest_probe.calc_grade
        assert support.has_completeness_manifest == latest_probe.has_completeness_manifest

    assert observed_divergences, (
        "no modelo in the bundled tree has a non-latest revision whose capabilities "
        "differ from its latest revision, so this gate proved nothing about "
        "latest-vs-this-revision scoping"
    )
