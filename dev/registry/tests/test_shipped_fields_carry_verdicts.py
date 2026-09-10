"""Every shipped generated field records its verdict against the official row it derives from.

Loading a manifest recomputes each stored verdict from the parser row beside
the emitted field, so a manifest whose verdicts load is one whose fields agree
with their design or carry the ruling that explains why not. This gate adds the
coverage half: a tree whose manifest carries no verdicts has never been attested
at all, and only the trees that cannot yet be republished may stay that way.
"""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..pipeline.export_fragment_provenance import load_export_fragment_provenance_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Trees whose manifests predate verdicts, each with why it cannot be republished
#: to gain them. Checked in both directions: a tree gaining its verdicts must
#: leave this table, and no other tree may be missing them.
_UNATTESTED: dict[str, str] = {
    "185/2025-y-siguientes": (
        "publication demands a calculation-grade revision and this one is honestly graded "
        "applicability; raising the grade to publish would be the under-declaration it prevents"
    ),
    "222/2025-y-siguientes": (
        "publication demands a calculation-grade revision and this one is honestly graded "
        "applicability; raising the grade to publish would be the under-declaration it prevents"
    ),
}


def _manifest_verdict_coverage() -> dict[str, tuple[int, int]]:
    """Return ``{modelo/revision: (fields, fields carrying a verdict)}`` for every shipped manifest."""
    coverage: dict[str, tuple[int, int]] = {}
    root = bundled_path("registry", "aeat", "modelos")
    for manifest_path in sorted(root.glob("*/revisions/*/export/_generation.provenance.json")):
        manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
        subject = f"{manifest.modelo}/{manifest.revision_id}"
        attested = sum(1 for item in manifest.field_derivations if item.verdict is not None)
        coverage[subject] = (len(manifest.field_derivations), attested)
    return coverage


def test_every_shipped_field_carries_a_verdict_unless_its_tree_cannot_be_republished() -> None:
    coverage = _manifest_verdict_coverage()

    assert coverage, "no generated manifest was found, so this gate compared nothing"
    partial = {subject: counts for subject, counts in coverage.items() if 0 < counts[1] < counts[0]}
    assert not partial, f"a manifest attests only some of its fields: {partial!r}"
    unattested = {subject for subject, (_fields, attested) in coverage.items() if attested == 0}
    assert unattested == set(_UNATTESTED), (
        f"unattested trees {sorted(unattested)!r} differ from the declared exceptions {sorted(_UNATTESTED)!r}"
    )
