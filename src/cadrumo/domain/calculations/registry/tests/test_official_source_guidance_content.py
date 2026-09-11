"""An ``official_source_guidance`` claim is checked against the file, never trusted.

``evidence_tier = "official_source_guidance"`` is checked at four sites --
cross-reference applicability predicates, application links, verification
expectations and deadline windows -- but every one of those checks asked only
whether the CITED SOURCE carries the tier, never whether the source's own text
supports the claim the site makes. Two claims survived calibration as
independently testable without the over-fire risk ``_legal.py``'s dispositive-
content regex (630 of 633 false positives on its first draft, 59 on its
second) warns is the default outcome of a first attempt: a ``suppression_notice``
must itself say something was suppressed, and a ``deadline_window`` must cite a
source that itself states a filing deadline.

These tests pin the property, never a tally: the corpus's population will
change as sources are retiered or replaced, and asserting today's count would
train the next author to update a constant while detecting nothing. What must
hold is the implication -- a claim is reported exactly when its own file (or,
for the deadline check, EVERY one of its official_source_guidance sources)
fails the content predicate -- proven exhaustively over the real bundled
corpus, both directions, never sampled.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dev.registry.compiler.corpus_catalogue import verify_source_file
from dev.registry.compiler.validate_evidence import EvidenceValidator
from dev.registry.compiler.validate_official_source_guidance_content import (
    deadline_window_content_failures,
    validate_suppression_notice_content,
)

from .....core.resources.bundled_data import bundled_path
from .....domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from ..schema_references import SourceReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The one real defect this check was built to find. Re-anchored per source
#: id rather than content: the companion test below re-derives that it still
#: carries the properties it is named for, so a retier or a swapped file
#: makes the anchor fail loudly instead of every assertion passing vacuously
#: over an empty set.
_SUPPRESSION_ANCHOR_SOURCE_ID = "boe-modelo-037-historical-suppression"

#: The real defect the deadline-window check was built to find: all four of
#: modelo 115's quarterly windows cite two sources that ground WHO must
#: withhold on rental income, never WHEN the resulting declaration is due.
_DEADLINE_ANCHOR_MODELO_ID = "115"
_DEADLINE_ANCHOR_REVISION_ID = "2019-y-siguientes"
_DEADLINE_ANCHOR_WINDOW_ID = "modelo-115-2026-1t"
_DEADLINE_ANCHOR_SOURCE_ID = "aeat-calendario-contribuyente-2026"

#: A window whose own cited source genuinely states its filing deadline.
_DEADLINE_HONEST_MODELO_ID = "180"
_DEADLINE_HONEST_WINDOW_ID = "modelo-180-2024-0a"


def _bundled_sources() -> dict[str, SourceReference]:
    _modelos, catalogues = bundled_registry_tree()
    return {str(ref): source for ref, source in catalogues.sources.items()}


def _find_window(modelo_id: str, window_id: str):
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(m for m in modelos if m.id == modelo_id)
    for revision in modelo.revisions.values():
        for window in revision.deadline_windows:
            if window.id == window_id:
                return window
    raise AssertionError(f"deadline window {window_id!r} not found under modelo {modelo_id!r}")


def _evidence_validator(*, source_root) -> EvidenceValidator:
    _modelos, catalogues = bundled_registry_tree()
    return EvidenceValidator(legal_refs=catalogues.legal, source_refs=catalogues.sources, source_root=source_root)


# --------------------------------------------------------------------------
# suppression_notice content
# --------------------------------------------------------------------------


def test_the_suppression_anchor_still_carries_the_properties_it_is_named_for() -> None:
    """The anchor is still a suppression_notice/official_source_guidance claim.

    Without this, retiering or replacing the source would silently turn the
    reconciliation test below into a statement about an empty population.
    """
    source = _bundled_sources()[_SUPPRESSION_ANCHOR_SOURCE_ID]
    assert source.kind == "suppression_notice"
    assert source.evidence_tier == "official_source_guidance"


def test_the_suppression_gate_still_refuses_an_entry_into_force_clause() -> None:
    """A suppression claim over a WHEN clause is refused, naming the fix.

    The anchor once pointed at this order's ``disposicion final unica`` -- an
    entry-into-force clause carrying no suppression at all -- and was the real
    defect this gate was built to find. It has since been re-pointed to the
    amending article that performs the suppression, so the refusal direction
    needs a claim that still exhibits the defect.

    The clause is the REAL bundled file, still shipped and still cited as a
    corpus_ref elsewhere, mounted here under the anchor's own identity. A
    synthetic fixture would prove the regex runs; this proves the gate refuses
    the exact confusion an author actually makes.
    """
    anchor = _bundled_sources()[_SUPPRESSION_ANCHOR_SOURCE_ID]
    when_not_what = anchor.model_copy(
        update={"corpus_path": "corpus/normatives/html/orden-hac-1526-2024-df-unica.html"},
    )

    failures = validate_suppression_notice_content(
        {_SUPPRESSION_ANCHOR_SOURCE_ID: when_not_what},
        source_root=bundled_path(),
    )

    assert failures, "a suppression_notice claim over an entry-into-force clause must be refused"
    assert "carries no suppression-establishing text" in failures[0]
    assert "amending article" in failures[0]


def test_a_genuine_suppression_notice_satisfies_the_claim(tmp_path: Path) -> None:
    """The public validator accepts a bundled-shape suppression notice fixture."""
    relative_path = "corpus/normatives/html/suppression-notice.html"
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True)
    path.write_text(
        "<html><body><p>Artículo único. Se suprime el modelo 099.</p>"
        "<p>Se deroga la disposición adicional tercera.</p></body></html>",
        encoding="utf-8",
    )
    source = _bundled_sources()[_SUPPRESSION_ANCHOR_SOURCE_ID].model_copy(
        update={"corpus_path": relative_path},
    )
    assert (
        validate_suppression_notice_content(
            {_SUPPRESSION_ANCHOR_SOURCE_ID: source},
            source_root=tmp_path,
        )
        == []
    )


def test_entry_into_force_alone_does_not_satisfy_the_suppression_claim(tmp_path: Path) -> None:
    """The public validator rejects an entry-into-force-only fixture."""
    relative_path = "corpus/normatives/html/suppression-entry-into-force.html"
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True)
    path.write_text(
        "<html><body><p>La orden entra en vigor el día 3 de febrero de 2025.</p>"
        "<p>Se aplica por primera vez a los modelos 030 y 036.</p></body></html>",
        encoding="utf-8",
    )
    source = _bundled_sources()[_SUPPRESSION_ANCHOR_SOURCE_ID].model_copy(
        update={"corpus_path": relative_path},
    )
    assert validate_suppression_notice_content(
        {_SUPPRESSION_ANCHOR_SOURCE_ID: source},
        source_root=tmp_path,
    )


# --------------------------------------------------------------------------
# deadline_window content
# --------------------------------------------------------------------------


def test_the_deadline_anchor_cites_the_reviewed_2026_calendar_pdf_with_its_deadline_content() -> None:
    """The repaired anchor is a verified, in-scope AEAT calendar PDF.

    The source verifier owns byte-size, SHA-256, and manual-PDF structure
    validation; :class:`EvidenceValidator` owns its content-keyed sidecar
    admission.  Keeping both in this anchor prevents a catalogue-only
    replacement from turning the refusal proof below into a fabrication.
    """
    window = _find_window(_DEADLINE_ANCHOR_MODELO_ID, _DEADLINE_ANCHOR_WINDOW_ID)
    sources = _bundled_sources()
    osg_refs = [ref for ref in window.source_refs if sources[ref].evidence_tier == "official_source_guidance"]
    assert osg_refs, "the anchor window no longer cites any official_source_guidance source"
    assert _DEADLINE_ANCHOR_SOURCE_ID in osg_refs

    source = sources[_DEADLINE_ANCHOR_SOURCE_ID]
    assert (source.authority, source.evidence_tier, source.kind, source.review_status) == (
        "aeat",
        "official_source_guidance",
        "manual_pdf",
        "reviewed",
    )
    assert source.applies_from is not None
    assert source.applies_to is not None
    assert source.applies_from <= window.opens_on <= window.closes_on <= source.applies_to
    assert verify_source_file(bundled_path(), source) == bundled_path(*source.corpus_path.split("/"))

    evidence = _evidence_validator(source_root=bundled_path())
    text = evidence.source_text(source)
    assert text is not None, "the verified calendar PDF must have readable evidence text"
    assert "hasta el 20 de abril" in text
    assert "primer trimestre 2026: 111, 115" in text
    assert (
        deadline_window_content_failures(
            f"modelo {_DEADLINE_ANCHOR_MODELO_ID} revision {_DEADLINE_ANCHOR_REVISION_ID}",
            window,
            source_refs=sources,
            evidence=evidence,
        )
        == []
    )


def test_the_deadline_gate_still_refuses_a_window_citing_only_who_must_file_sources() -> None:
    """A window whose every OSG source is silent on WHEN is refused.

    This window was the real defect the gate was built to find: it cited only
    the censal guide and the activities folleto, both of which say WHO must
    file and never WHEN. It has since been grounded with the RIRPF article
    that states the deadline, so the refusal direction needs the pre-fix
    citation set to point at.

    Both remaining refs are the REAL bundled sources the window still cites,
    with only the deadline-bearing one dropped -- so this reproduces the exact
    historical state rather than inventing a synthetic silent source.
    """
    window = _find_window(_DEADLINE_ANCHOR_MODELO_ID, _DEADLINE_ANCHOR_WINDOW_ID)
    evidence = _evidence_validator(source_root=bundled_path())
    sources = _bundled_sources()
    silent_refs = tuple(ref for ref in window.source_refs if ref != _DEADLINE_ANCHOR_SOURCE_ID)
    assert silent_refs, "the anchor window no longer cites any WHO-must-file source to refuse"
    who_only = window.model_copy(update={"source_refs": silent_refs})

    failures = deadline_window_content_failures(
        f"modelo {_DEADLINE_ANCHOR_MODELO_ID} revision {_DEADLINE_ANCHOR_REVISION_ID}",
        who_only,
        source_refs=sources,
        evidence=evidence,
    )

    assert failures, f"{_DEADLINE_ANCHOR_WINDOW_ID} citing only WHO-must-file sources must be reported"
    assert "none of their bundled text states a filing deadline" in failures[0]


def test_an_honest_deadline_window_is_not_reported() -> None:
    window = _find_window(_DEADLINE_HONEST_MODELO_ID, _DEADLINE_HONEST_WINDOW_ID)
    evidence = _evidence_validator(source_root=bundled_path())
    failures = deadline_window_content_failures(
        "modelo 180 revision 2023-y-siguientes",
        window,
        source_refs=_bundled_sources(),
        evidence=evidence,
    )
    assert failures == []


def test_the_deadline_gate_yields_nothing_without_a_source_root() -> None:
    """No reachable corpus means no claim can be checked, and none is invented."""
    window = _find_window(_DEADLINE_ANCHOR_MODELO_ID, _DEADLINE_ANCHOR_WINDOW_ID)
    unreachable_evidence = EvidenceValidator(
        legal_refs={},
        source_refs=_bundled_sources(),
        source_root=None,
    )
    assert (
        deadline_window_content_failures(
            "x",
            window,
            source_refs=_bundled_sources(),
            evidence=unreachable_evidence,
        )
        == []
    )


def test_a_window_with_no_official_source_guidance_ref_is_not_this_checks_concern() -> None:
    """A window citing zero OSG-tier sources is a tier-membership failure elsewhere.

    ``require_source_tier`` already refuses that shape; this check adds
    nothing and reports nothing, rather than duplicating that failure under a
    different message.
    """
    window = _find_window(_DEADLINE_HONEST_MODELO_ID, _DEADLINE_HONEST_WINDOW_ID)
    non_osg_source_refs = {
        ref: source.model_copy(update={"evidence_tier": "layout_authority"})
        for ref, source in _bundled_sources().items()
        if ref in window.source_refs
    }
    evidence = _evidence_validator(source_root=None)
    assert (
        deadline_window_content_failures(
            "x",
            window,
            source_refs=non_osg_source_refs,
            evidence=evidence,
        )
        == []
    )
