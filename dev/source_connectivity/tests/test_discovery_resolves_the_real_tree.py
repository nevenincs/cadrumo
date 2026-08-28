"""Real-tree anchors for the capability detectors.

Every other proof in this package writes a synthetic module into ``tmp_path``
and asserts the detector reads it. That shape proves the AST walk is correct on
input the test authored, and it is silent about whether the detector still
reaches the REAL tree it exists to describe -- which is the only thing the
source-connectivity census consumes.

Two live defects shipped through that blind spot on the same day:

* ``discover_row_assemblers`` hard-codes one module path. A relocation promoted
  ``_row_set_assembly`` to its public name, the synthetic proof kept passing
  against its own ``tmp_path`` copy, and the detector raised
  :exc:`FileNotFoundError` against the repository.
* ``discover_ingress_surfaces`` resolves a leaf wrapper's arguments but not the
  module-level constants a spec module hoists its handler path into, so it
  raised :exc:`ValueError` on a spec it should have read.

Neither is expressible as a synthetic fixture, because both are properties of
the real tree's shape rather than of the walk. These anchors close that gap: a
detector that stops reaching production reds here instead of degrading the
census in silence.

Gated on the PROPERTY (the detector resolves and finds its subject), never on a
tally -- a pinned count encodes one moment, trains everyone to bump the
constant, and then detects nothing.

See Also:
    :mod:`dev.source_connectivity.discovery`
        The detectors under test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..discovery import (
    discover_calculation_helpers,
    discover_ingress_surfaces,
    discover_lexical_destination_advisories,
    discover_row_assemblers,
    discover_secure_repositories,
    discover_source_readiness,
    discovered_source_capability_evidence,
    discovered_source_capability_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Each detector must resolve against the real tree AND find its subject there.
#: The name is the failure message: a detector reaching zero production sites is
#: broken, not a tree that happens to have none.
_DETECTORS = (
    ("calculation helpers", discover_calculation_helpers),
    ("ingress surfaces", discover_ingress_surfaces),
    ("row assemblers", discover_row_assemblers),
    ("secure repositories", discover_secure_repositories),
    ("source readiness probes", discover_source_readiness),
    ("lexical destination advisories", discover_lexical_destination_advisories),
)


def test_the_repo_root_this_module_computes_is_the_real_one() -> None:
    """Anti-vacuity: every assertion below is worthless if the root is wrong."""
    assert (_REPO_ROOT / "src" / "cadrumo").is_dir(), f"computed repo root has no src/cadrumo: {_REPO_ROOT}"
    assert (_REPO_ROOT / "dev" / "source_connectivity").is_dir(), (
        f"computed repo root has no dev/source_connectivity: {_REPO_ROOT}"
    )


@pytest.mark.parametrize(("label", "detector"), _DETECTORS, ids=[label for label, _ in _DETECTORS])
def test_every_detector_resolves_against_the_real_tree(label: str, detector: object) -> None:
    """A detector must neither raise nor come back empty on the repository."""
    rows = detector(_REPO_ROOT)  # type: ignore[operator]

    assert rows, (
        f"the {label} detector resolved no production site in the real tree. It either lost the "
        "path it hard-codes (a relocation landed without sweeping this detector) or its structural "
        "resolution stopped matching the shape production now uses."
    )


def test_the_census_entry_points_resolve_against_the_real_tree() -> None:
    """The two aggregate entry points the census consumes must resolve too.

    They fan out over every detector, so a single detector raising takes the
    whole census with it -- which is how a hard-coded path that no longer
    exists reaches the census as an exception rather than as a gap.
    """
    capability_ids = discovered_source_capability_ids(_REPO_ROOT)
    evidence = discovered_source_capability_evidence(_REPO_ROOT)

    assert capability_ids, "the capability-id census resolved nothing against the real tree"
    assert evidence, "the capability-evidence census resolved nothing against the real tree"
    assert set(evidence) <= set(capability_ids), (
        "evidence names capability ids the census does not carry: "
        f"{sorted(set(evidence) - set(capability_ids))[:10]}"
    )
