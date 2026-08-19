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

THE ALLOWLIST IS NOW EMPTY, AND THAT IS THE POINT. It once held four entries --
modelos 187, 188, 194 and 296 -- each justified the same way: a formula may only
cite an ``official_source_guidance``-tier source (``_validate_formulas.py`` requires
that tier), and for those four the only guidance-tier source was an AEAT procedure
landing page that never mentions a box, while the sources that DO describe the boxes
were ``layout_authority`` tier and ineligible. The weak phrase was forced by the
tier rule rather than chosen.

Every one was cleared the way the entries said it had to be: read the printed annex
in the approving orden, transcribe it to a guidance-tier ``boe-modelo-NNN-form-text``
extract beside ``boe-modelo-128-form-text``, and cite it. What that reading found
was that none of the four formulas should have existed -- each was an identity
``add`` over a single casilla, and in every case the box it targeted was either
absent from the printed form or a different figure entirely. So the formulas were
deleted rather than re-cited, and the allowlist emptied with them.

An empty allowlist makes this a pure ratchet: a new bare-modelo-number citation
fails outright. Re-adding an entry is legitimate only for a formula that genuinely
must exist and genuinely has no citable guidance-tier source -- state which, and
say why the annex route does not apply.

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
_NO_GUIDANCE_TIER_SOURCE_DESCRIBES_THE_BOXES: dict[tuple[str, str, str], str] = {}


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
