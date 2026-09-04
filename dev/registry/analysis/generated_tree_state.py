"""Classify every enrolled generated export tree by what repairing it would take.

Twenty-six trees fail their reproduction test today and the plan describes them
as one repair. They are three, with three different remedies, and one of the
three must NOT have the repair applied to it. Deriving that split by reading a
test log is how it was found; this is how it stays available.

Four states are reported, and every row names one of them:

- ``reproducible`` - a fresh render of the current inputs reproduces the
  committed tree exactly. Nothing to do.
- ``manifest_only_stale`` - every record file reproduces byte-for-byte and only
  the generation manifest differs. Safe to republish, and it arrives in bulk:
  any refactor of the generator invalidates every manifest at once, which is why
  the disposition ledger deliberately does not record these.
- ``record_drift`` - a record file differs as well, so the committed bytes and
  the current inputs disagree about filing data. Republishing ships whatever the
  inputs now say, which may be worse than what is there; the disposition ledger
  carries a reason for each of these and republication must wait on it.
- ``never_committed`` - the revision renders and no tree is committed. It needs
  publication, which is a different act from republication and is not blocked by
  the same evidence.

The comparison is not reimplemented. It comes from
:func:`~dev.registry.pipeline.render_check.compare_revision_against_committed`,
which already reports which files differ and which exist on only one side; this
module decides only what those differences MEAN for a repair. A second
comparison would be a second answer to a question the pipeline owns.

This is deliberately not a screen. Classifying a tree renders it, so a full pass
costs minutes rather than the seconds the screen runner promises, and enrolling
it would make the suite's quick census slow enough that people stop running it.
Run it when planning a republication.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..pipeline._provenance_manifest import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..pipeline.render_check import compare_revision_against_committed
from .corpus import bundled_modelo_ids

__all__ = [
    "STATES",
    "GeneratedTreeState",
    "classify_comparison",
    "tree_states",
]

#: Every state this report can assign, declared once and used at each emission
#: site so the set cannot be recovered by reading the source wrong.
STATES: Final[tuple[str, ...]] = (
    "reproducible",
    "manifest_only_stale",
    "record_drift",
    "never_committed",
)


@dataclass(frozen=True, slots=True)
class GeneratedTreeState:
    """One enrolled tree and what repairing it would take."""

    modelo: str
    revision: str
    state: str
    differing: tuple[str, ...]
    #: Files differing only in serialisation form, which carry no change of
    #: meaning and are excluded before the state is decided.
    serialization_only: tuple[str, ...]
    detail: str


def classify_comparison(
    differing: tuple[str, ...],
    *,
    committed: bool,
    serialization_only: tuple[str, ...] = (),
) -> str:
    """Return the state a comparison result implies.

    ``serialization_only`` files are subtracted first, and getting that wrong
    inverts the advice this report exists to give. The comparison reports a file
    as differing when its bytes differ, including when only its serialisation
    form changed: modelo 322's 2023 tree lists six differing files of which five
    are reformattings and one is the manifest. Classified on the raw list it
    reads as record drift and "do not republish"; classified on the meaningful
    difference it is manifest-only staleness and safe. The first version of this
    function reported twenty-seven trees as drifting where the reproduction test
    reports twenty-three as safe.

    Separated from the walk so every state is reachable from a test with input
    written in it. A state with no live instance and no constructed proof is one
    that stops being reported without anyone noticing.
    """
    if not committed:
        return "never_committed"
    meaningful = set(differing) - set(serialization_only)
    if not meaningful:
        return "reproducible"
    if meaningful == {EXPORT_FRAGMENT_PROVENANCE_FILENAME}:
        return "manifest_only_stale"
    return "record_drift"


def tree_states(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> tuple[GeneratedTreeState, ...]:
    """Classify every revision that can render, committed or not."""
    states: list[GeneratedTreeState] = []
    for modelo_id in modelo_ids:
        for revision_id in authority.modelo(modelo_id).revisions:
            revision = str(revision_id)
            export_root = bundled_path("registry", "aeat", "modelos", modelo_id, "revisions", revision, "export")
            committed = (export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME).is_file()
            try:
                comparison = compare_revision_against_committed(authority, modelo=modelo_id, revision=revision)
            except (ValueError, KeyError, FileNotFoundError, OSError):
                if not committed:
                    continue
                comparison = None
            differing = tuple(comparison.differing) if comparison is not None else ()
            serialization_only = tuple(comparison.serialization_only) if comparison is not None else ()
            state = classify_comparison(differing, committed=committed, serialization_only=serialization_only)
            states.append(
                GeneratedTreeState(
                    modelo=modelo_id,
                    revision=revision,
                    state=state,
                    differing=differing,
                    serialization_only=serialization_only,
                    detail=(
                        f"{len(set(differing) - set(serialization_only))} meaningful of "
                        f"{len(differing)} differing file(s)"
                        if differing
                        else ("no committed tree" if not committed else "reproduces exactly")
                    ),
                )
            )
    return tuple(states)


def main() -> int:
    """Print one row per tree and a closing census; always exit 0."""
    authority = bundled_authority()
    states = tree_states(authority, bundled_modelo_ids())
    for item in states:
        sys.stdout.write(
            f"generated_tree_state modelo={item.modelo} revision={item.revision} state={item.state} "
            f"differing={','.join(item.differing) or 'none'} detail={item.detail!r}\n"
        )
    tally: collections.Counter[str] = collections.Counter(item.state for item in states)
    census = " ".join(f"{state}={tally[state]}" for state in STATES)
    sys.stdout.write(f"summary trees={len(states)} {census}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
