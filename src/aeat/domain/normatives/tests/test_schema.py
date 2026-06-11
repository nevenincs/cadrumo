"""Unit tests for the strict pydantic v2 schema in :mod:`aeat.domain.normatives`.

Exercises :class:`aeat.domain.normatives.Articulo` and
:class:`aeat.domain.normatives.NormativeReference` validation, frozen-model
semantics, and rejection of forbidden extra fields.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import AnyHttpUrl, ValidationError

from .. import (
    Articulo,
    NormativeKind,
    NormativeReference,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _articulo(numero: str = "32") -> Articulo:
    return Articulo(
        numero=numero,
        titulo={"es": "Reducciones"},
        summary={"es": "Resumen del artículo."},
        permalink=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32"),
    )


def _reference(
    *,
    ref_id: str = "ley-35-2006",
    articulos: tuple[Articulo, ...] | None = None,
) -> NormativeReference:
    return NormativeReference(
        id=ref_id,
        kind=NormativeKind.LEY,
        number="35/2006",
        title={"es": "Ley 35/2006 del IRPF"},
        published_at=date(2006, 11, 29),
        boe_url=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764"),
        boe_id="BOE-A-2006-20764",
        articulos=articulos if articulos is not None else (_articulo(),),
        tags=("irpf",),
        last_reviewed_at=date(2026, 4, 12),
        reviewed_by="wgergely",
    )


class TestArticulo:
    """Validation behaviour of :class:`aeat.domain.normatives.Articulo`."""

    def test_happy_path(self) -> None:
        articulo = _articulo()
        assert articulo.numero == "32"
        assert articulo.titulo  # populated translation key, not asserted on its rendered value

    def test_missing_spanish_title_rejected(self) -> None:
        # A localized-text mapping without the authoritative 'es' entry
        # is rejected by the _require_spanish model validator.
        with pytest.raises(ValidationError, match=r"titulo: missing authoritative Spanish"):
            Articulo(
                numero="32",
                titulo={"en": "Reductions"},
                summary={"es": "Resumen del artículo."},
                permalink=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32"),
            )

    def test_missing_spanish_summary_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"summary: missing authoritative Spanish"):
            Articulo(
                numero="32",
                titulo={"es": "Reducciones"},
                summary={"en": "Article summary."},
                permalink=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32"),
            )

    def test_frozen(self) -> None:
        articulo = _articulo()
        with pytest.raises(ValidationError, match=r"frozen"):
            articulo.notes = "mutated"


class TestNormativeReference:
    """Validation behaviour of :class:`aeat.domain.normatives.NormativeReference`."""

    def test_happy_path(self) -> None:
        ref = _reference()
        assert ref.id == "ley-35-2006"
        assert ref.kind is NormativeKind.LEY

    def test_duplicate_articulo_numero_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"duplicate articulo numero"):
            _reference(articulos=(_articulo("32"), _articulo("32")))

    def test_permalink_without_boe_id_rejected(self) -> None:
        bad = Articulo(
            numero="99",
            titulo={"es": "Artículo de otra norma"},
            summary={"es": "Resumen de otra norma."},
            permalink=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a99"),
        )
        with pytest.raises(ValidationError, match=r"does not reference boe_id"):
            _reference(articulos=(bad,))

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            NormativeReference.model_validate(
                {
                    "id": "ley-35-2006",
                    "kind": "ley",
                    "number": "35/2006",
                    "title": {"es": "x"},
                    "published_at": "2006-11-29",
                    "boe_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
                    "boe_id": "BOE-A-2006-20764",
                    "articulos": [],
                    "tags": [],
                    "last_reviewed_at": "2026-04-12",
                    "reviewed_by": "wgergely",
                    "unknown_field": "drift",
                },
            )
