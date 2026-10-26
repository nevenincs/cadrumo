"""Modelo 100 reads Modelo 131 only for the pagos fraccionados it settles.

Modelo 131 casilla 01 is the sum of the activities' annual net yields "a efectos
del pago fraccionado", computed from the datos-base of 1 January (RD 439/2007
art. 110.1.b; the AEAT Modelo 131 instructions for casilla 01), so every quarter
restates the same annual estimate. Modelo 100 casilla 1481 is each activity's
rendimiento neto reducido from the year's actual data (Renta manual, estimación
objetiva, fase 5.ª). No quarterly total of casilla 01 is casilla 1481, so no
edition may fold one into the other; the relation that stays is casilla 15, the
quarterly results that casilla 0604 sums as pagos fraccionados.
"""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ._modelo_100_registry_support import _loaded_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RENDIMIENTO_NETO_REDUCIDO = validated_casilla_id("1481", surface="test_modelo_100_modelo_131_relations")
_M131_SUMA_RENDIMIENTOS_NETOS = "01"
_M131_RESULTADO = "15"


def _editions() -> tuple[ModeloRevision, ...]:
    return tuple(_loaded_registry()[0]["100"].revisions.values())


def _modelo_131_sources(revision: ModeloRevision) -> set[str]:
    return {
        str(casilla_id)
        for binding in revision.bindings
        if isinstance(binding.provider, RelationPrefillProvider) and str(binding.provider.source_modelo) == "131"
        for casilla_id in binding.provider.declared_source_casilla_ids
    }


def test_no_edition_folds_modelo_131_casilla_01_into_modelo_100() -> None:
    for revision in _editions():
        (casilla,) = (casilla for casilla in revision.casillas if casilla.id == _RENDIMIENTO_NETO_REDUCIDO)

        assert casilla.binding is None, revision.id
        assert _M131_SUMA_RENDIMIENTOS_NETOS not in _modelo_131_sources(revision), revision.id


def test_every_edition_keeps_the_modelo_131_pagos_fraccionados_relation() -> None:
    for revision in _editions():
        assert _modelo_131_sources(revision) == {_M131_RESULTADO}, revision.id
