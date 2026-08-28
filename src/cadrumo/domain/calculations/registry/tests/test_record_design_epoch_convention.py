"""A record-design epoch tag has a shape and is unique within its modelo.

The tag is how a design is addressed. It was the only free-form key in the export
authority chain with neither shape nor uniqueness enforcement -- a ``str`` with
length bounds and nothing else -- while every other free-form key in that chain
is cross-validated at build time against something independent of the string.

THE CONVENTION IS DERIVED, NOT CHOSEN. Every tag that predates any enforcement is
a bare four-digit ejercicio, and none carries a document-version suffix, so
``aeat-dr-111-2019-v18`` is epoch ``2019``: v18 is which revision of the PDF AEAT
published and says nothing about which filings the design governs. A convention
read off the existing entries is one nobody can violate by accident -- but only
once something checks it, and until now nothing did.

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

import pytest

from .....core import RECORD_DESIGN_EPOCH_PATTERN
from .....tests.registry_tree import bundled_registry_tree
from .._validate_record_design_epochs import (
    validate_record_design_epoch_uniqueness,
    validate_record_design_epoch_window,
)
from ..errors import RegistryValidationError
from ..schema_references import SourceReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CORPUS_MODELO = re.compile(r"disenos_registro/(modelo_[0-9]+)/")


def _tagged_sources() -> dict[str, SourceReference]:
    _modelos, catalogues = bundled_registry_tree()
    return {str(ref): source for ref, source in catalogues.sources.items() if source.record_design_epoch is not None}


def _rebuild(source: SourceReference, **changes: object) -> SourceReference:
    """Return a copy of a real bundled source with fields replaced, re-validated.

    Built from a REAL declaration rather than a hand-written fixture so the
    mutation exercises the same model the tree loads through. A synthetic source
    could satisfy the check while diverging from what the registry actually holds.
    """
    return SourceReference.model_validate(source.model_dump() | changes)


def test_every_bundled_epoch_tag_satisfies_the_derived_shape() -> None:
    """THE HALF THAT MATTERS MOST: the live tree must stay valid.

    A pattern wrong in the strict direction invalidates every tag in the tree at
    once, which is a far more expensive failure than the looseness it replaced and
    an easy one to ship while concentrating on the rejection cases below. Asserted
    over the real bundled declarations rather than a sample.
    """
    tagged = _tagged_sources()
    assert tagged, "no bundled source declares a record_design_epoch; this gate would pass vacuously"

    for ref, source in sorted(tagged.items()):
        # Round-tripping through the model is what re-runs the validator; simply
        # reading the attribute would assert nothing about the check.
        assert _rebuild(source).record_design_epoch == source.record_design_epoch, ref


def test_a_document_version_suffix_is_refused_as_an_epoch() -> None:
    """``2019-v18`` is a version, not an epoch, and the shape must say so.

    This is the exact confusion the convention exists to prevent: two designs
    differing only by which PDF revision AEAT published are the SAME epoch, and
    admitting the suffix would let both claim distinct epochs and defeat the
    uniqueness check below without either being wrong on its face.
    """
    source = next(iter(_tagged_sources().values()))
    for rejected in ("2019-v18", "v18", "2019v18", "ejercicio-2019", "2019-EARLY", "19", "20244", ""):
        with pytest.raises((RegistryValidationError, ValueError)):
            _rebuild(source, record_design_epoch=rejected)


def test_a_sub_year_relayout_label_is_accepted_as_an_epoch() -> None:
    """AEAT splits an ejercicio mid-course, so the shape must admit both halves.

    Modelo 303 does it live: ``2024-early`` and ``2024-late`` are two designs
    governing different parts of one filing year. A pattern accepting only bare
    years would refuse the tree's own declarations.
    """
    source = next(iter(_tagged_sources().values()))
    for accepted in ("2024-early", "2024-late", "2026", "2003"):
        assert _rebuild(source, record_design_epoch=accepted).record_design_epoch == accepted


def test_no_modelo_declares_one_epoch_on_two_designs() -> None:
    """Uniqueness over the real tree -- the second half of the live-validity proof."""
    assert validate_record_design_epoch_uniqueness(_tagged_sources()) == []


def test_a_duplicate_epoch_within_one_modelo_is_refused() -> None:
    """The bite: two designs of one modelo claiming one epoch must fail.

    Built by taking a real modelo's two distinct-epoch designs and forcing the
    second onto the first's epoch, so the duplicate is constructed from genuine
    declarations rather than from a fixture that might not resemble them.
    """
    tagged = _tagged_sources()
    by_modelo: dict[str, list[tuple[str, SourceReference]]] = defaultdict(list)
    for ref, source in tagged.items():
        matched = _CORPUS_MODELO.search(source.corpus_path.replace("\\", "/"))
        if matched is not None:
            by_modelo[matched.group(1)].append((ref, source))

    modelo, pair = next((modelo, entries) for modelo, entries in sorted(by_modelo.items()) if len(entries) >= 2)
    (first_ref, first), (second_ref, second) = pair[0], pair[1]
    assert first.record_design_epoch != second.record_design_epoch, (
        f"{modelo} no longer has two distinct-epoch designs; pick another anchor"
    )

    collided = dict(tagged)
    collided[second_ref] = _rebuild(second, record_design_epoch=first.record_design_epoch)

    failures = validate_record_design_epoch_uniqueness(collided)
    assert failures, f"a duplicate epoch on {modelo} was not reported"
    assert any(modelo in failure and repr(first.record_design_epoch) in failure for failure in failures), failures
    assert any(first_ref in failure and second_ref in failure for failure in failures), (
        "the diagnostic must name BOTH colliding sources; naming one leaves the reader to find the other"
    )


def test_the_same_epoch_on_two_different_modelos_is_not_a_collision() -> None:
    """Uniqueness is PER MODELO -- most modelos publish a 2025 design.

    The anti-over-reach control. A global uniqueness rule would refuse the corpus
    outright, since ejercicio 2025 designs exist for many modelos at once.
    """
    tagged = _tagged_sources()
    epochs_by_modelo: dict[str, set[str]] = defaultdict(set)
    for source in tagged.values():
        matched = _CORPUS_MODELO.search(source.corpus_path.replace("\\", "/"))
        if matched is not None and source.record_design_epoch is not None:
            epochs_by_modelo[matched.group(1)].add(source.record_design_epoch)

    shared = [
        epoch
        for epoch in {epoch for epochs in epochs_by_modelo.values() for epoch in epochs}
        if sum(1 for epochs in epochs_by_modelo.values() if epoch in epochs) > 1
    ]
    assert shared, (
        "no epoch is shared across modelos, so this control proves nothing -- either the corpus "
        "shrank or the grouping key has broken"
    )
    assert validate_record_design_epoch_uniqueness(tagged) == []


def test_every_bundled_epoch_sits_inside_its_own_applies_window() -> None:
    """The live half of the cross-validation: the tree must already be consistent."""
    assert validate_record_design_epoch_window(_tagged_sources()) == []


def test_an_epoch_outside_its_declared_window_is_refused() -> None:
    """The bite, in both directions of the window.

    Shape and uniqueness constrain the string against itself and its siblings.
    Neither can say whether the tag describes the design it is attached to. This
    compares it against the applies dates -- data the tag's author did not write as
    part of the tag -- which is the independence every other free-form key in the
    export authority chain already had and this one did not.
    """
    tagged = _tagged_sources()
    ref, source = next(
        (ref, source)
        for ref, source in sorted(tagged.items())
        if source.applies_from is not None and source.record_design_epoch is not None
    )
    opens = source.applies_from
    assert opens is not None

    too_early = _rebuild(source, record_design_epoch=f"{opens.year - 1:04d}")
    failures = validate_record_design_epoch_window({ref: too_early})
    assert failures and "does not yet govern" in failures[0], failures

    if source.applies_to is not None:
        too_late = _rebuild(source, record_design_epoch=f"{source.applies_to.year + 1:04d}")
        late_failures = validate_record_design_epoch_window({ref: too_late})
        assert late_failures and "no longer govern" in late_failures[0], late_failures


def test_the_filed_artefact_refuses_an_epoch_the_registry_would_refuse() -> None:
    """The artefact boundary must not be weaker than the boundary that declares it.

    ``M303RegimenSimplificadoCalculationResult.record_design_epoch`` is stamped into
    filing evidence, and it carried ``min_length=1`` only -- so a value the registry
    would have rejected was acceptable once it reached the artefact. Two boundaries
    disagreeing about what an epoch is, with the weaker one downstream, is how an
    unchecked string ends up in a filed record.

    Asserted through the shared pattern rather than a restated one: a second copy is
    exactly the drift this closes.
    """
    from ....modelos.calculation_revision import M303RegimenSimplificadoCalculationResult

    field = M303RegimenSimplificadoCalculationResult.model_fields["record_design_epoch"]
    patterns = [getattr(item, "pattern", None) for item in field.metadata]
    assert RECORD_DESIGN_EPOCH_PATTERN in patterns, (
        "the filing-evidence field does not constrain the epoch to the canonical shape, so the "
        f"artefact accepts values the registry refuses; constraints were {field.metadata}"
    )
