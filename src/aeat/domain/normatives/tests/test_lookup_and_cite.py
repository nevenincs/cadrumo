"""Unit tests for lookup helpers and the citation renderer."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import AnyHttpUrl

from .. import (
    Articulo,
    NormativeCatalogue,
    NormativeKind,
    NormativeNotFoundError,
    NormativeReference,
    cite,
    find_articulo,
    find_reference,
    short_title,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue() -> NormativeCatalogue:
    articulo = Articulo(
        numero="32",
        titulo={"es": "Reducciones"},
        summary={"es": "Resumen del artículo."},
        permalink=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32"),
    )
    reference = NormativeReference(
        id="ley-35-2006",
        kind=NormativeKind.LEY,
        number="35/2006",
        title={"es": "Ley 35/2006 del IRPF"},
        published_at=date(2006, 11, 29),
        boe_url=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764"),
        boe_id="BOE-A-2006-20764",
        articulos=(articulo,),
        tags=("irpf",),
        last_reviewed_at=date(2026, 4, 12),
        reviewed_by="wgergely",
    )
    return NormativeCatalogue(references={reference.id: reference})


class TestLookup:
    """Coverage for :func:`aeat.domain.normatives.find_reference` and :func:`aeat.domain.normatives.find_articulo`."""

    def test_find_reference_hit(self) -> None:
        catalogue = _catalogue()
        assert find_reference(catalogue, "ley-35-2006").id == "ley-35-2006"

    def test_find_reference_miss(self) -> None:
        catalogue = _catalogue()
        with pytest.raises(NormativeNotFoundError, match=r"ley-0-0000|reference"):
            find_reference(catalogue, "ley-0-0000")

    def test_find_articulo_hit(self) -> None:
        catalogue = _catalogue()
        articulo = find_articulo(catalogue, "ley-35-2006", "32")
        assert articulo.numero == "32"

    def test_find_articulo_miss_reference(self) -> None:
        catalogue = _catalogue()
        with pytest.raises(NormativeNotFoundError, match=r"ley-0-0000|reference"):
            find_articulo(catalogue, "ley-0-0000", "32")

    def test_find_articulo_miss_numero(self) -> None:
        catalogue = _catalogue()
        with pytest.raises(NormativeNotFoundError, match=r"999|articulo|numero"):
            find_articulo(catalogue, "ley-35-2006", "999")


class TestCite:
    """Coverage for :func:`aeat.domain.normatives.short_title` and :func:`aeat.domain.normatives.cite`."""

    def test_short_title_ley(self) -> None:
        reference = find_reference(_catalogue(), "ley-35-2006")
        assert short_title(reference) == "Ley 35/2006"

    def test_canonical_citation_is_stable(self) -> None:
        catalogue = _catalogue()
        reference = find_reference(catalogue, "ley-35-2006")
        articulo = find_articulo(catalogue, "ley-35-2006", "32")
        assert cite(reference, articulo) == "Ley 35/2006, art. 32 (BOE-A-2006-20764)"
