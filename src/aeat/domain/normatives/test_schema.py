"""Unit tests for the strict pydantic v2 schema in :mod:`aeat.domain.normatives`.

Exercises :class:`aeat.domain.normatives.Articulo` and
:class:`aeat.domain.normatives.NormativeReference` validation, frozen-model
semantics, and rejection of forbidden extra fields.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import AnyHttpUrl, ValidationError

from . import (
    Articulo,
    NormativeKind,
    NormativeReference,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _articulo(numero: str = "32") -> Articulo:
    return Articulo(
        numero=numero,
        titulo="normatives.test_schema.titulo_908834",
        summary="normatives.test_schema.summary_296440",
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
        title="normatives.test_schema.title_440480",
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
        with pytest.raises(ValidationError):
            Articulo(
                numero="32",
                titulo="translation",
                summary="normatives.test_schema.summary_132271",
                permalink=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32"),
            )

    def test_missing_spanish_summary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Articulo(
                numero="32",
                titulo="normatives.test_schema.titulo_466358",
                summary="translation",
                permalink=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32"),
            )

    def test_frozen(self) -> None:
        articulo = _articulo()
        with pytest.raises(ValidationError):
            articulo.notes = "mutated"  # type: ignore[misc]


class TestNormativeReference:
    """Validation behaviour of :class:`aeat.domain.normatives.NormativeReference`."""

    def test_happy_path(self) -> None:
        ref = _reference()
        assert ref.id == "ley-35-2006"
        assert ref.kind is NormativeKind.LEY

    def test_duplicate_articulo_numero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _reference(articulos=(_articulo("32"), _articulo("32")))

    def test_permalink_without_boe_id_rejected(self) -> None:
        bad = Articulo(
            numero="99",
            titulo="normatives.test_schema.titulo_446515",
            summary="normatives.test_schema.summary_391415",
            permalink=AnyHttpUrl("https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a99"),
        )
        with pytest.raises(ValidationError):
            _reference(articulos=(bad,))

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
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
                }
            )
