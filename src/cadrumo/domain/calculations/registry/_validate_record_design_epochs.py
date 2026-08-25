"""Per-modelo uniqueness of record-design epoch tags.

A design's epoch is how it is addressed. Two designs on one modelo claiming the
same epoch makes that address ambiguous, and an ambiguous address resolves to
whichever entry the mapping happened to keep -- a filing year computed under
another year's layout, arrived at silently.

SCOPE, corrected. An earlier reading of this held that the epoch was never a
sole selection key -- that every consumer paired it with the canonical source id
or the content hash and failed closed on a mismatch, making these checks mere
hardening. That described ``resolve_record_design_binary``, which does perform
exactly those cross-checks and which **no shipped runtime path calls**: its only
non-test callers are the registry authoring export-tree generator.

What the shipped code actually does is use ``record_design_epoch is not None`` as
a bare PRESENCE filter at three sites, selecting on the ``applies_from`` /
``applies_to`` window instead, and then stamp the value verbatim into
``M303RegimenSimplificadoCalculationResult`` -- filing evidence. So an unenforced
free-form string reached a filed artefact with nothing between the declaration
and the artefact checking it. These checks are therefore narrower than the defect
but no longer decorative.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from typing import Final

from ....core import record_design_epoch_year
from .schema_references import SourceReference

#: The modelo a design belongs to, read from where the file LIVES rather than from
#: its id. The whole point of this check is to constrain a free-form string, so
#: deriving its grouping key from another free-form string it is written beside
#: would let one typo satisfy the other.
_CORPUS_MODELO: Final = re.compile(r"disenos_registro/(modelo_[0-9]+)/")


def validate_record_design_epoch_uniqueness(sources: Mapping[str, SourceReference]) -> list[str]:
    """Return one failure per modelo whose designs claim an epoch twice.

    Returns:
        Accumulated diagnostics; empty when every modelo's epochs are distinct.
    """
    by_modelo: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for ref, source in sources.items():
        epoch = source.record_design_epoch
        if epoch is None:
            continue
        matched = _CORPUS_MODELO.search(source.corpus_path.replace("\\", "/"))
        if matched is None:
            # A record design outside the per-modelo corpus tree cannot be grouped,
            # and guessing a grouping would make the check report on an invented
            # key. Reported rather than skipped: an ungroupable design is exactly
            # the case a uniqueness check cannot cover, so it must be visible.
            by_modelo["UNGROUPABLE (corpus_path is not under disenos_registro/modelo_NNN/)"][epoch].append(str(ref))
            continue
        by_modelo[matched.group(1)][epoch].append(str(ref))

    failures: list[str] = []
    for modelo, epochs in sorted(by_modelo.items()):
        if modelo.startswith("UNGROUPABLE"):
            for epoch, refs in sorted(epochs.items()):
                failures.append(
                    f"record-design source(s) {sorted(refs)} declare epoch {epoch!r} but their "
                    f"corpus_path is not under a per-modelo design directory, so epoch uniqueness "
                    f"cannot be checked for them: {modelo}",
                )
            continue
        for epoch, refs in sorted(epochs.items()):
            if len(refs) > 1:
                failures.append(
                    f"{modelo} declares record_design_epoch {epoch!r} on {len(refs)} designs "
                    f"({sorted(refs)}). An epoch names the filing period a design governs, so one "
                    f"modelo cannot have two designs governing the same period: either these are "
                    f"the SAME design bundled twice, in which case one declaration is redundant, "
                    f"or they govern different periods and one epoch is wrong. Where AEAT re-laid "
                    f"the form out mid-ejercicio, distinguish them with a sub-year label "
                    f"('{epoch}-early' / '{epoch}-late') rather than letting both claim {epoch!r}",
                )
    return failures


def validate_record_design_epoch_window(sources: Mapping[str, SourceReference]) -> list[str]:
    """Return one failure per design whose epoch falls outside its own applies window.

    THE CROSS-VALIDATION THE TAG LACKED. Shape and uniqueness constrain the string
    against itself and against its siblings; neither can tell whether the epoch
    describes the design it is attached to. This compares it against the
    ``applies_from`` / ``applies_to`` dates -- data the tag's author did not write
    as part of the tag -- so a design tagged for one ejercicio while declaring it
    governs another is refused rather than merely well-formed.

    That independence is the point. Every other free-form key in the export
    authority chain is cross-checked at build against something outside itself;
    this key was the one that was not, and a value nothing checks is stamped
    verbatim into filing evidence.

    Returns:
        Accumulated diagnostics; empty when every epoch sits inside its window.
    """
    failures: list[str] = []
    for ref, source in sorted(sources.items()):
        epoch = source.record_design_epoch
        if epoch is None:
            continue
        year = record_design_epoch_year(epoch)
        opens = source.applies_from
        closes = source.applies_to
        if opens is not None and year < opens.year:
            failures.append(
                f"record-design source {ref!r} declares epoch {epoch!r} but applies from "
                f"{opens.isoformat()}, so it is tagged for an ejercicio it does not yet govern. "
                f"Either the epoch names the wrong period or the window opens too late",
            )
        if closes is not None and year > closes.year:
            failures.append(
                f"record-design source {ref!r} declares epoch {epoch!r} but applies to "
                f"{closes.isoformat()}, so it is tagged for an ejercicio it no longer governs. "
                f"Either the epoch names the wrong period or the window closes too early",
            )
    return failures


__all__ = [
    "validate_record_design_epoch_uniqueness",
    "validate_record_design_epoch_window",
]
