"""A formula's citation phrase must be able to fail.

``EvidenceValidator.validate_source_citations`` already proves every formula
``source_citation`` names a real bundled source and that its ``required_text``
appears in that source. What it cannot prove is that the phrase says anything:
``required_text = ["187"]`` against modelo 187's own procedure page is satisfied by
construction. The document is about modelo 187, so the phrase is present, so the
check passes -- and it would pass equally against any other document about the same
modelo. The citation substantiates the formula in the letter and not at all in
substance.

That is the M309 defect class seen from the other side. M309 was a citation whose
SOURCE could not substantiate it; this is a citation whose PHRASE cannot
discriminate. Neither is visible to a gate that only asks "is the phrase present".

The contrast that shows what a real phrase looks like is already in the tree:
modelo 126 and 128 cite a guidance-tier FORM-TEXT extract and quote the form's own
printed arithmetic -- "Resultado a ingresar ([03] - [06])", "Suma de retenciones e
ingresos a cuenta y regularizacion, en su caso ([02] + [06])". Those phrases fail
loudly against the wrong document, and they name the very computation the formula
performs.

WHY THE KNOWN OFFENDERS ARE ALLOWLISTED RATHER THAN FIXED. A formula may only cite
an ``official_source_guidance``-tier source (``_validate_formulas.py`` requires that
tier before validating the citation). For the modelos below, the ONLY guidance-tier
source is an AEAT procedure landing page that never mentions a box: measured,
``modelo-187-procedure.html`` carries "declaracion informativa" 73 times and zero
occurrences of "Importe total" or "Numero total". The sources that DO describe the
boxes -- the orden and the record design -- are ``layout_authority`` tier and are
therefore ineligible to be cited. So the weak phrase is forced by the tier rule, not
chosen: no phrase in the citable document could substantiate a box-level formula.
Clearing an entry means bundling a guidance-tier form-text extract for that modelo,
the way ``boe-modelo-128-form-text`` already is, and citing a printed phrase from it.

The allowlist is keyed by ``(modelo, revision, formula)`` and every entry carries its
reason. A stale entry FAILS rather than lingering: the test asserts each allowlisted
formula still exhibits the shape, so a fixed citation forces the entry's removal.
"""

from __future__ import annotations

import pytest

from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

#: ``(modelo, revision, formula)`` -> why the bare-modelo-number phrase stands.
#: Every entry means: this modelo has no ``official_source_guidance``-tier source
#: that describes its numbered boxes, so no citable phrase can substantiate the
#: formula. Remove the entry once such a source is bundled and cited.
_NO_GUIDANCE_TIER_SOURCE_DESCRIBES_THE_BOXES: dict[tuple[str, str, str], str] = {
    ("296", "2024-y-siguientes", "modelo-296-total"): (
        "modelo-296-procedure.html is an AEAT landing page with no box "
        "vocabulary, and the orden and record design are layout_authority tier "
        "and cannot be cited by a formula. Modelos 187, 188 and 194 carried "
        "identical entries until each annex was read, transcribed to a "
        "boe-modelo-NNN-form-text extract and cited; 296 is the last of the four "
        "and its annex has not been read. Unlike those three its casillas do "
        "carry export_refs into the record design, so its box set may well be "
        "right where theirs was not -- that is unmeasured, not assumed"
    ),
}


def _bare_modelo_number_citations() -> dict[tuple[str, str, str], tuple[str, ...]]:
    """Return every formula citation whose required phrase is just the modelo id."""
    modelos, _catalogues = _committed_registry_tree()
    found: dict[tuple[str, str, str], tuple[str, ...]] = {}
    for modelo in modelos:
        for revision_id, revision in modelo.revisions.items():
            for formula in revision.formulas:
                for citation in formula.source_citations:
                    offending = tuple(phrase for phrase in citation.required_text if phrase.strip() == modelo.id)
                    if offending:
                        found[(modelo.id, revision_id, formula.id)] = offending
    return found


def test_no_new_formula_cites_only_its_own_modelo_number() -> None:
    """A citation phrase equal to the modelo's own number cannot discriminate."""
    found = _bare_modelo_number_citations()

    unexplained = sorted(key for key in found if key not in _NO_GUIDANCE_TIER_SOURCE_DESCRIBES_THE_BOXES)

    assert not unexplained, (
        "formula citations whose required_text is the bare modelo number, which is "
        "satisfied by construction and substantiates nothing:\n"
        + "\n".join(f"  modelo {m} revision {r} formula {f}" for m, r, f in unexplained)
        + "\nCite a guidance-tier source that prints the box arithmetic (see "
        "boe-modelo-128-form-text), or add an allowlist entry stating why none exists."
    )


def test_every_allowlisted_citation_still_exhibits_the_shape() -> None:
    """A fixed citation must force its allowlist entry out.

    Without this the allowlist would quietly outlive the defect it documents, and a
    reader would take a stale entry as evidence the modelo is still unsourceable.
    """
    found = _bare_modelo_number_citations()

    stale = sorted(key for key in _NO_GUIDANCE_TIER_SOURCE_DESCRIBES_THE_BOXES if key not in found)

    assert not stale, (
        "allowlist entries whose formula no longer cites the bare modelo number - "
        "delete them:\n" + "\n".join(f"  modelo {m} revision {r} formula {f}" for m, r, f in stale)
    )
