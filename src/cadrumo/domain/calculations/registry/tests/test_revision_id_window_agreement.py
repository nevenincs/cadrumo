"""The revision-id window-agreement gate, and the vocabulary it depends on.

The gate refuses a revision whose id claims an open-ended window its own
declarations close. It is only as good as its marker: a pattern that quietly
stopped matching would report zero contradictions and read as health, so the
vocabulary is re-derived from the tree here rather than trusted.
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree
from .._validate_revision_id_window_agreement import (
    revision_id_claims_open_window,
    revision_window_closures,
    validate_revision_id_window_agreement,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Revision-id tails this tree is known to use, beyond a bare four-digit year.
#: Anything else is unrecognised vocabulary and must be classified before the
#: marker can be trusted to have seen it.
_KNOWN_ID_TAILS = frozenset(
    {
        "",
        "-y-siguientes",
        "-02-03-y-siguientes",
        "-01-31-y-siguientes",
        "-desde-09-y-3t",
        "-hasta-08-y-2t",
        "-2017",
        "-2022",
        "-2023",
        "-2024",
        "esquema-exterior",
        "esquema-importacion",
        "esquema-union",
    },
)


def _committed_revisions():
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return tuple((modelo.id, revision) for modelo in modelos for revision in modelo.revisions.values())


def test_no_revision_id_uses_vocabulary_the_marker_has_not_been_checked_against() -> None:
    """A newly coined id tail must be classified, not silently unmatched.

    This is what keeps the marker honest. The gate finds contradictions only among
    ids it recognises as making a claim, so an unrecognised tail is indistinguishable
    from a revision with nothing to check -- and a coinage such as ``-en-adelante``
    would make the gate quietly stop covering it.
    """
    unrecognised = sorted(
        {
            f"{modelo_id}:{revision.id}"
            for modelo_id, revision in _committed_revisions()
            if re.sub(r"^\d{4}", "", str(revision.id)) not in _KNOWN_ID_TAILS
        },
    )

    assert not unrecognised, (
        "these revision ids carry a tail the window-agreement marker has never been checked "
        "against. Decide whether each asserts an open-ended window: if it does, teach the "
        "marker; if it does not, add the tail to the known set. Do not leave it unclassified, "
        "because an unmatched id and a compliant one look identical from here:\n  " + "\n  ".join(unrecognised)
    )


def test_the_marker_recognises_the_open_ended_ids_the_tree_actually_carries() -> None:
    """The control: without this the marker could match nothing and every test above passes."""
    open_ended = [
        f"{modelo_id}:{revision.id}"
        for modelo_id, revision in _committed_revisions()
        if revision_id_claims_open_window(str(revision.id))
    ]

    assert len(open_ended) > 50, (
        f"the marker recognises only {len(open_ended)} open-ended revision ids, which is far "
        "below what this tree carries. It has probably stopped matching, and a gate that "
        "recognises nothing reports no contradictions and reads as health."
    )


def test_a_mid_year_split_id_is_not_read_as_an_open_ended_claim() -> None:
    """``-desde-09-y-3t`` contains ``y`` as a separator and asserts no open window."""
    assert not revision_id_claims_open_window("2024-desde-09-y-3t")
    assert not revision_id_claims_open_window("2024-hasta-08-y-2t")
    assert revision_id_claims_open_window("2021-y-siguientes")
    assert revision_id_claims_open_window("2025-02-03-y-siguientes")


def test_an_uninformative_id_is_neither_refused_nor_cleared() -> None:
    """A revision naming no window makes no claim, so there is no contradiction to find.

    Asserted explicitly so the gate cannot drift into a naming-convention linter:
    a closed revision named ``2025`` is correct and must stay silent here.
    """
    failures: list[str] = []
    for modelo_id, revision in _committed_revisions():
        if str(revision.id) == "2025" and revision.valid_to is not None:
            failures.extend(validate_revision_id_window_agreement(prefix=f"modelo {modelo_id}", revision=revision))
    assert failures == []


def test_the_gate_names_every_axis_that_closes_a_contradicting_revision() -> None:
    """A revision closed on both axes reports both, not the first one found."""
    contradictions = {
        f"{modelo_id}:{revision.id}": revision_window_closures(revision)
        for modelo_id, revision in _committed_revisions()
        if revision_id_claims_open_window(str(revision.id)) and revision_window_closures(revision)
    }

    assert contradictions, (
        "no revision contradicts its own id. If the tree was repaired this test should be "
        "rewritten against a constructed revision rather than deleted, because it is the only "
        "proof the gate fires on real data."
    )
    for subject, closures in contradictions.items():
        assert closures, subject


def test_the_gate_refuses_a_constructed_contradiction_and_passes_its_open_twin() -> None:
    """Both halves, on one real revision: close it and it refuses, leave it open and it passes."""
    genuinely_open = next(
        revision
        for _modelo_id, revision in _committed_revisions()
        if revision_id_claims_open_window(str(revision.id)) and not revision_window_closures(revision)
    )

    passing = validate_revision_id_window_agreement(prefix="modelo TEST", revision=genuinely_open)
    assert passing == [], f"a genuinely open-ended revision was refused: {genuinely_open.id}"

    closed = genuinely_open.model_copy(update={"valid_to": date(2025, 12, 31)})
    refusing = validate_revision_id_window_agreement(prefix="modelo TEST", revision=closed)

    assert len(refusing) == 1
    # Keyed on the two facts the refusal must carry -- which axis closed the window
    # and at what value -- rather than on the rendered "axis = value" string. The
    # formatting may be rewritten; a refusal that stops naming the axis or the
    # value sends the reader looking for a closure it never identified.
    message = refusing[0]
    assert "open-ended" in message, "the refusal no longer says what the id claimed"
    assert "valid_to" in message, "the refusal does not name the axis that closed the window"
    assert "2025-12-31" in message, "the refusal does not name the value the window closed at"
