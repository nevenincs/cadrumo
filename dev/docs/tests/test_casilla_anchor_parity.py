"""Casilla deep-link anchor parity for the search injection.

Every injected casilla search record deep-links to its entry on the per-modelo
casilla reference page (``_generated/casillas/<modelo>.html#casilla-<slug>``).
The card and the landing page both derive that anchor from the ONE slug
authority (:func:`~dev.docs.terminology._casilla_anchor.casilla_page_anchor`),
so they can never disagree - the docs-side one-aggregation-path discipline the
CLI-target break motivated.

These gates prove, at the RST/render level (the ``test_glossary_anchor_parity``
shape generalised to the casilla kind):

- :func:`test_slug_reproduces_html_id_scheme` locks the slug against
  hand-derived casilla-id/anchor pairs, so a fold-algorithm drift fails loudly.
- :func:`test_every_projected_casilla_target_resolves` proves every projected
  casilla record's target page+anchor is in the generator's own emitted anchor
  inventory, so a casilla card can never ship a dead deep link.
- :func:`test_destination_renders_record_grounding` proves the D6
  destination-grounding contract: a record carrying ``legal_refs`` whose page
  entry renders none of them is a gate failure.
- :func:`test_duplicate_anchor_is_a_build_failure` proves the collision guard
  refuses two casilla ids folding to the same per-page anchor (never a silent
  merge, which would red the ``-n -W`` build with an ambiguous fragment).
"""

from __future__ import annotations

import pytest

from ..._paths import REPO_ROOT
from ..casilla_reference import CasillaReferenceError, CasillaReferenceResult, render_casilla_reference
from ..terminology import project_casilla_search_records
from ..terminology._casilla_anchor import casilla_page_anchor
from ..terminology.search_record import CasillaSearchRecord, SearchRecordKind
from ..terminology.unified_record import to_search_record

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT


@pytest.fixture(scope="module")
def projected() -> tuple[CasillaSearchRecord, ...]:
    """The full registry casilla projection (the records the search injects)."""
    records, _stats = project_casilla_search_records()
    return records


@pytest.fixture(scope="module")
def reference(projected: tuple[CasillaSearchRecord, ...]) -> CasillaReferenceResult:
    """Render the full casilla reference from the same projection (one pass)."""
    return render_casilla_reference(_REPO_ROOT, records=projected)


@pytest.fixture(scope="module")
def anchors_by_modelo(reference: CasillaReferenceResult) -> dict[str, set[str]]:
    """``modelo -> the set of anchor ids the generator emitted on its page``."""
    return {page.modelo: set(page.anchors) for page in reference.pages}


@pytest.mark.parametrize(
    ("casilla_id", "anchor"),
    [
        ("10", "casilla-10"),
        ("01", "casilla-01"),
        ("DP200014:00562", "casilla-dp200014-00562"),
        ("decl.ejercicio", "casilla-decl-ejercicio"),
        ("contraparte.clave-operacion", "casilla-contraparte-clave-operacion"),
    ],
)
def test_slug_reproduces_html_id_scheme(casilla_id: str, anchor: str) -> None:
    """The slug helper folds casilla ids to the id the generator stamps verbatim."""
    assert casilla_page_anchor("000", casilla_id) == anchor


def test_every_projected_casilla_target_resolves(
    projected: tuple[CasillaSearchRecord, ...],
    reference: CasillaReferenceResult,
    anchors_by_modelo: dict[str, set[str]],
) -> None:
    """Every injected casilla deep link targets a real page and a real anchor."""
    pages = {page.output_relpath for page in reference.pages}
    dead: list[str] = []
    for record in projected:
        unified = to_search_record(record)
        assert unified.kind is SearchRecordKind.CASILLA
        page_part, _, anchor = unified.target.partition("#")
        rel = page_part.replace(".html", ".rst")
        modelo = record.modelo.value
        if rel not in pages:
            dead.append(f"{unified.target}: page {rel} not generated")
        elif anchor not in anchors_by_modelo.get(modelo, set()):
            dead.append(f"{unified.target}: anchor {anchor} absent from modelo {modelo} page")
    assert not dead, "casilla deep links with no rendered destination:\n" + "\n".join(f"  - {d}" for d in dead[:40])


def test_destination_renders_record_grounding(
    projected: tuple[CasillaSearchRecord, ...],
    reference: CasillaReferenceResult,
) -> None:
    """D6: every record's ``legal_refs`` render on its destination entry.

    A record carrying ``legal_refs`` whose page entry renders none of them is a
    gate failure. The page renders every ref (a resolvable one as a BOE
    permalink, an unresolvable one as inline literal), so the destination is at
    parity with what the card carries.
    """
    rendered_by_modelo = {page.modelo: page.rendered_legal_refs for page in reference.pages}
    ungrounded: list[str] = []
    grounded = 0
    for record in projected:
        if not record.legal_refs:
            continue
        anchor = casilla_page_anchor(record.modelo, record.casilla_id)
        rendered = rendered_by_modelo.get(record.modelo.value, {}).get(anchor)
        if rendered is None or not set(record.legal_refs).issubset(rendered):
            ungrounded.append(f"{record.modelo.value}/{record.casilla_id}: refs {record.legal_refs} not rendered")
        else:
            grounded += 1
    assert grounded > 0, "no grounded casilla entries — the projection carries no legal_refs?"
    assert not ungrounded, "casilla entries dropping their legal grounding (D6 breach):\n" + "\n".join(
        f"  - {u}" for u in ungrounded[:40]
    )


def test_duplicate_anchor_is_a_build_failure(projected: tuple[CasillaSearchRecord, ...]) -> None:
    """Two casilla ids folding to one per-page anchor is refused, never merged."""
    seed = projected[0]
    twin = seed.model_copy(update={"casilla_id": f"{seed.casilla_id}."})
    assert casilla_page_anchor(seed.modelo, seed.casilla_id) == casilla_page_anchor(seed.modelo, twin.casilla_id)
    with pytest.raises(CasillaReferenceError):
        render_casilla_reference(_REPO_ROOT, records=(seed, twin))


def test_reference_reports_real_counts(reference: CasillaReferenceResult) -> None:
    """The render summary reports the real per-modelo / per-casilla counts."""
    assert reference.modelo_count == len(reference.pages)
    assert reference.casilla_count == sum(len(page.anchors) for page in reference.pages)
    assert reference.casilla_count > 1000  # the real registry is large
    assert reference.legal_links > 0
