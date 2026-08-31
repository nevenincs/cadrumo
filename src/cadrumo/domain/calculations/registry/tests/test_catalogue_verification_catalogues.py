"""Core shared-catalogue verification tests."""

from __future__ import annotations

import pytest

from .....core.resources.bundled_data import bundled_path
from .....tests import REPO_ROOT
from .._validate import RegistryValidator
from ..corpus_catalogue import verify_source_catalogue
from ..legal import verify_legal_catalogue_grounding
from ._catalogue_verification_support import _registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_committed_registry_tree_has_coherent_shared_catalogues() -> None:
    modelos, catalogues = _registry_tree()

    assert len(modelos) >= 5, "committed registry must declare several modelos"
    assert len(catalogues.legal) > 0, "shared legal catalogue must be non-empty"
    assert len(catalogues.sources) > 0, "shared sources catalogue must be non-empty"
    verify_legal_catalogue_grounding(catalogues.legal, source_root=bundled_path())
    verify_source_catalogue(REPO_ROOT, catalogues.sources)
    validator = RegistryValidator(catalogues, source_root=bundled_path())
    validator.validate_registry(modelos)


#: The deliberately year-vintaged excerpts a corpus forbidden-text clause must
#: never treat as a defect: each carries at least one phrase unique to its own
#: historical redaction, which is what pins its intended vintage. See the
#: grounding reference's "vintaged excerpts behave CORRECTLY" finding.
_DELIBERATELY_VINTAGED_EXCERPT_IDS = (
    "ley-35-2006:art-23-2021",
    "ley-35-2006:art-52-2015",
    "ley-35-2006:art-52-2021",
    "ley-35-2006:art-66-2021",
    "ley-35-2006:art-68-2018",
)


def test_forbidden_text_clause_is_additive_over_the_full_committed_legal_catalogue() -> None:
    """The new optional forbidden-text clause must not disturb any existing entry.

    A refusal firing on a synthetic fixture proves the clause CAN catch a
    repealed phrase; it proves nothing about whether the clause over-reaches on
    the real catalogue. This is the control that decides closure: every entry
    in the committed catalogue still loads and validates unchanged now that the
    schema carries the new clause. The deliberately year-vintaged excerpts are
    named explicitly because they legitimately contain text current law does
    not, and none of them is given a forbidden_text clause by this change.
    """
    _modelos, catalogues = _registry_tree()

    assert len(catalogues.legal) > 0, "control is meaningless against an empty catalogue"
    for vintaged_id in _DELIBERATELY_VINTAGED_EXCERPT_IDS:
        assert vintaged_id in catalogues.legal, f"{vintaged_id!r} must remain in the committed legal catalogue"
        assert catalogues.legal[vintaged_id].forbidden_text == (), (
            f"{vintaged_id!r} is a deliberately historical excerpt; this control authors no forbidden_text for it"
        )

    verify_legal_catalogue_grounding(catalogues.legal, source_root=bundled_path())


def test_no_legal_reference_grounds_a_normatives_citation_in_a_derived_artefact() -> None:
    """A ``corpus_ref`` under ``corpus/normatives/`` must name the source, not a build product.

    ``7cdae88dc1`` reverted 22 refs that pointed ``corpus_ref`` at a
    ``*.html.extracted.md`` sidecar -- a workaround for the anchor-resolution
    regression ``daa9876ed3`` fixed properly -- back onto their source
    ``*.html`` documents, because no code path resolves or expects a
    ``corpus_ref`` naming ``.extracted.md``: the resolver always derives its
    own ``<corpus_ref path>.extracted.json`` sidecar from the named ``.html``
    source. This gate keeps that reversion from silently drifting back.

    ``corpus/manuals/**/*.pdf.extracted.md`` refs are the deliberate
    exception, carved out by name rather than caught by this pattern: a PDF
    manual excerpt has no ``.html`` counterpart to point at, so its
    ``corpus_ref`` legitimately names the extracted markdown directly (see
    ``irpf-autonomica-madrid.toml``, 3 refs, committed long before the 22-ref
    regression this gate targets). A naive "no path ends in ``.extracted.md``"
    rule would red on those three legitimate refs; this one matches only the
    ``normatives``-rooted, ``.html.extracted.md``-suffixed shape the
    regression actually took.
    """
    _modelos, catalogues = _registry_tree()

    offending = sorted(
        f"{ref_id} -> {reference.corpus_ref!r}"
        for ref_id, reference in catalogues.legal.items()
        if reference.corpus_ref is not None
        and reference.corpus_ref.partition("#")[0].startswith("corpus/normatives/")
        and reference.corpus_ref.partition("#")[0].endswith(".html.extracted.md")
    )

    assert offending == [], (
        "legal reference(s) ground a citation in a derived .extracted.md artefact "
        f"instead of the .html source it was built from: {offending}"
    )


def test_the_derived_artefact_gate_still_admits_the_pdf_manual_exception() -> None:
    """The gate above must not have been satisfied by accidentally excluding the exception too.

    Proves the negative test isn't vacuous: the three legitimate
    ``corpus/manuals/**/*.pdf.extracted.md`` refs still exist in the committed
    catalogue and are exactly the ones the gate's ``corpus/normatives/`` scope
    exempts, not references that happen not to exist at all.
    """
    _modelos, catalogues = _registry_tree()

    manual_extracted_md_refs = [
        ref_id
        for ref_id, reference in catalogues.legal.items()
        if reference.corpus_ref is not None
        and reference.corpus_ref.partition("#")[0].startswith("corpus/manuals/")
        and reference.corpus_ref.partition("#")[0].endswith(".pdf.extracted.md")
    ]

    assert len(manual_extracted_md_refs) >= 3, (
        f"expected the committed Madrid autonomic-deduction manual refs to still be present, "
        f"found {manual_extracted_md_refs}"
    )
