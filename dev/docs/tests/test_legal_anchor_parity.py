"""Legal deep-link and destination-grounding parity for the search injection.

Every projected legal provision must funnel into one unique ``LEGAL`` unified
record whose target is the generated legal-reference page (and, where the
renderer emits one, its provision anchor). The destination must also render
the authored BOE permalink carried by the ``LegalSearchRecord``; a plausible
URL or record-local metadata is not enough to establish grounding parity.

The gate uses the registry-backed legal projection and the real renderer
inventories, so it can fail when the projection, target authority, emitted
anchor, or destination RST drifts independently.
"""

from __future__ import annotations

import pytest

from ..._paths import REPO_ROOT
from ..legal_reference import LegalPage, LegalReferenceResult, render_legal_reference
from ..terminology._legal_projection import project_legal_search_records
from ..terminology._search_record import LegalSearchRecord, SearchRecordKind
from ..terminology._unified_record import SearchRecord, to_search_record

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT


@pytest.fixture(scope="module")
def projected() -> tuple[LegalSearchRecord, ...]:
    """Load every legal search record from the registry-backed projection."""
    return project_legal_search_records()


@pytest.fixture(scope="module")
def reference() -> LegalReferenceResult:
    """Render the legal reference and retain its real page inventories."""
    return render_legal_reference(_REPO_ROOT)


@pytest.fixture(scope="module")
def unified(projected: tuple[LegalSearchRecord, ...]) -> tuple[SearchRecord, ...]:
    """Funnel the projected legal records through the production seam."""
    return tuple(to_search_record(record) for record in projected)


def _pages_by_rst(reference: LegalReferenceResult) -> dict[str, LegalPage]:
    pages = {page.output_relpath: page for page in reference.pages}
    assert len(pages) == len(reference.pages), "renderer emitted duplicate legal page paths"
    return pages


def test_every_projected_legal_provision_has_one_unique_unified_record(
    projected: tuple[LegalSearchRecord, ...],
    reference: LegalReferenceResult,
    unified: tuple[SearchRecord, ...],
) -> None:
    """Every registry provision has one unique LEGAL record and renderer target."""
    assert len(projected) > 100, f"expected a substantive legal projection, got {len(projected)}"
    assert reference.page_count > 1, "renderer emitted no substantive legal page set"
    assert reference.provision_count == len(reference.targets)
    assert reference.provision_count == len(projected)
    assert reference.grounding_count == len(projected)

    legal_ids = tuple(record.legal_id for record in projected)
    assert len(set(legal_ids)) == len(legal_ids), "projection contains duplicate legal provision ids"
    assert len(unified) == len(projected)
    assert all(record.kind is SearchRecordKind.LEGAL for record in unified)
    assert len({record.id for record in unified}) == len(unified), "unified LEGAL record ids are not unique"
    assert {record.metadata.legal_id for record in unified} == set(legal_ids)

    for source, record in zip(projected, unified, strict=True):
        assert record.metadata.legal_id == source.legal_id
        assert source.target == reference.targets[source.legal_id]
        assert record.target == reference.targets[source.legal_id]


def test_every_projected_legal_target_resolves_to_emitted_page_or_anchor(
    projected: tuple[LegalSearchRecord, ...],
    reference: LegalReferenceResult,
    unified: tuple[SearchRecord, ...],
) -> None:
    """Every canonical legal target names a rendered page and valid fragment."""
    pages = _pages_by_rst(reference)
    dead: list[str] = []
    resolved = 0

    for source, record in zip(projected, unified, strict=True):
        assert record.target == reference.targets[source.legal_id]
        page_html, separator, fragment = record.target.partition("#")
        page_rst = page_html.removesuffix(".html") + ".rst"
        page = pages.get(page_rst)
        if page is None:
            dead.append(f"{source.legal_id}: generated page {page_html!r} is absent")
            continue
        if source.legal_id not in page.anchor_by_id:
            dead.append(f"{source.legal_id}: destination page has no renderer entry")
            continue

        emitted_anchor = page.anchor_by_id[source.legal_id]
        if separator and not fragment:
            dead.append(f"{source.legal_id}: target has an empty fragment")
        elif fragment:
            if emitted_anchor != fragment or fragment not in page.anchors:
                dead.append(
                    f"{source.legal_id}: target fragment #{fragment} is not the emitted anchor "
                    f"{emitted_anchor!r} on {page_html}"
                )
            elif f'id="{fragment}"' not in page.rst:
                dead.append(f"{source.legal_id}: emitted anchor #{fragment} is absent from destination RST")
            else:
                resolved += 1
        elif emitted_anchor is not None:
            dead.append(f"{source.legal_id}: page-level target hides emitted anchor #{emitted_anchor}")
        elif record.target != page.output_relpath.removesuffix(".rst") + ".html":
            dead.append(f"{source.legal_id}: page-level target is not the renderer's page target")
        else:
            resolved += 1

    assert not dead, "legal targets with no rendered destination:\n" + "\n".join(f"  - {item}" for item in dead[:40])
    assert resolved == len(unified)
    assert resolved > 100, f"expected substantive legal target coverage, resolved only {resolved}"


def test_every_legal_destination_renders_authored_boe_grounding(
    projected: tuple[LegalSearchRecord, ...],
    reference: LegalReferenceResult,
    unified: tuple[SearchRecord, ...],
) -> None:
    """Every target page inventories and renders its record's authored BOE URL."""
    pages = _pages_by_rst(reference)
    ungrounded: list[str] = []
    grounded = 0

    for source, record in zip(projected, unified, strict=True):
        page_html = record.target.partition("#")[0]
        page_rst = page_html.removesuffix(".html") + ".rst"
        page = pages.get(page_rst)
        if page is None:
            ungrounded.append(f"{source.legal_id}: destination page {page_html!r} is absent")
            continue

        inventory_permalink = page.grounding_by_id.get(source.legal_id)
        # Asserted on the link TARGET, never the link label: the label is
        # reader-facing presentation and may be reworded, while the permalink
        # is the grounding claim. A dropped or altered URL still fails.
        rendered_link = f"<{source.permalink}>`__"
        if inventory_permalink != source.permalink or rendered_link not in page.rst:
            ungrounded.append(
                f"{source.legal_id}: destination inventory {inventory_permalink!r} or RST link "
                f"{rendered_link!r} does not match the authored permalink"
            )
        else:
            grounded += 1

    assert not ungrounded, "legal destinations dropping BOE grounding:\n" + "\n".join(
        f"  - {item}" for item in ungrounded[:40]
    )
    assert grounded == len(unified)
    assert grounded > 100, f"expected substantive legal grounding coverage, grounded only {grounded}"
    assert reference.grounding_count == grounded
