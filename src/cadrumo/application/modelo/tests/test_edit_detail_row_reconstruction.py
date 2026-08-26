"""Real-model tests for the detail-row whole-set reconstruction (S288).

Proves the natural-key-addressed ADD/UPDATE/DELETE/MOVE reconstruction the
guarded executor performs before every calculate call, mirroring
``RetencionObservationRepository.replace_observations``'s established
whole-set-replacement convention: rows are addressed by their own
already-declared business key, never position or a minted identity, and a
row absent from the result is simply not declared -- there is no separate
"explicitly deleted" axis.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.modelos import Modelo347ContraparteRow, Modelo349OperadorRow, Modelo349RectificacionRow
from .._edit_execution import _reconstruct_detail_rows
from .._edit_models import (
    ModeloDetailRowEditIntentV1,
    ModeloEditDetailRowAddressV1,
    ModeloEditDetailRowIntentKind,
    ModeloEditExecutionNoEffectV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _contraparte(nif: str, importe: str) -> Modelo347ContraparteRow:
    return Modelo347ContraparteRow(nif=nif, importe_Q1=Decimal(importe))


def _operador(nif_comunitario: str, importe: str) -> Modelo349OperadorRow:
    return Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario=nif_comunitario,
        razon_social="ALEMAN GMBH",
        clave_operacion="E",
        importe=Decimal(importe),
    )


def _rectificacion(nif_comunitario: str) -> Modelo349RectificacionRow:
    return Modelo349RectificacionRow(
        codigo_pais="DE",
        nif_comunitario=nif_comunitario,
        razon_social="ALEMAN GMBH",
        clave_operacion="E",
        ejercicio="2025",
        periodo="2T",
        base_rectificada=Decimal("1100.00"),
        base_anterior=Decimal("1000.00"),
    )


def _address(natural_key: str) -> ModeloEditDetailRowAddressV1:
    return ModeloEditDetailRowAddressV1(detail_row_kind="contraparte", natural_key=natural_key)


def test_add_row_appends_to_an_empty_set() -> None:
    row = _contraparte("11111111H", "5000")
    intent = ModeloDetailRowEditIntentV1(address=_address("11111111H"), kind=ModeloEditDetailRowIntentKind.ADD_ROW, row=row)

    result = _reconstruct_detail_rows(current_detail_rows=(), detail_row_intents=(intent,))

    assert result == (row,)


def test_update_row_replaces_content_in_place_preserving_position() -> None:
    first = _contraparte("11111111H", "5000")
    second = _contraparte("22222222J", "1000")
    updated_first = _contraparte("11111111H", "9999")
    intent = ModeloDetailRowEditIntentV1(
        address=_address("11111111H"), kind=ModeloEditDetailRowIntentKind.UPDATE_ROW, row=updated_first
    )

    result = _reconstruct_detail_rows(current_detail_rows=(first, second), detail_row_intents=(intent,))

    assert result == (updated_first, second)


def test_update_row_refuses_an_unknown_natural_key() -> None:
    existing = _contraparte("11111111H", "5000")
    ghost = _contraparte("99999999Z", "1")
    intent = ModeloDetailRowEditIntentV1(
        address=_address("99999999Z"), kind=ModeloEditDetailRowIntentKind.UPDATE_ROW, row=ghost
    )

    result = _reconstruct_detail_rows(current_detail_rows=(existing,), detail_row_intents=(intent,))

    assert isinstance(result, ModeloEditExecutionNoEffectV1)


def test_delete_row_removes_by_key_leaving_the_rest_untouched() -> None:
    first = _contraparte("11111111H", "5000")
    second = _contraparte("22222222J", "1000")
    intent = ModeloDetailRowEditIntentV1(address=_address("11111111H"), kind=ModeloEditDetailRowIntentKind.DELETE_ROW)

    result = _reconstruct_detail_rows(current_detail_rows=(first, second), detail_row_intents=(intent,))

    assert result == (second,)


def test_delete_row_refuses_an_unknown_natural_key() -> None:
    existing = _contraparte("11111111H", "5000")
    intent = ModeloDetailRowEditIntentV1(address=_address("99999999Z"), kind=ModeloEditDetailRowIntentKind.DELETE_ROW)

    result = _reconstruct_detail_rows(current_detail_rows=(existing,), detail_row_intents=(intent,))

    assert isinstance(result, ModeloEditExecutionNoEffectV1)


def test_move_row_is_not_a_member_of_the_detail_row_intent_kind() -> None:
    """No MOVE intent exists: the revision id is order-blind, so a reorder would be silently absorbed.

    ``_calculation_revision._canonical_detail_rows`` sorts rows by
    ``(row_type, nif-like)`` before hashing specifically so insertion order
    never affects the revision id. A MOVE_ROW intent would therefore compute
    the same id as the existing revision and be discarded by the guarded
    duplicate-result branch rather than actually reorder anything.
    """
    assert not hasattr(ModeloEditDetailRowIntentKind, "MOVE_ROW")


def test_editing_one_m349_row_kind_never_touches_the_sibling_kind() -> None:
    """Deleting an operador row must not disturb a rectificacion row on the same revision.

    M349's two row kinds are distinct fichero record types; the reconstruction
    groups by ``row_type`` precisely so one kind's edit cannot cross-contaminate
    the other.
    """
    operador = _operador("DE111111111", "1500")
    rectificacion = _rectificacion("DE222222222")
    intent = ModeloDetailRowEditIntentV1(
        address=ModeloEditDetailRowAddressV1(detail_row_kind="operador", natural_key="DE111111111|E"),
        kind=ModeloEditDetailRowIntentKind.DELETE_ROW,
    )

    result = _reconstruct_detail_rows(current_detail_rows=(operador, rectificacion), detail_row_intents=(intent,))

    assert result == (rectificacion,)


def test_no_intents_returns_the_current_set_unchanged() -> None:
    existing = (_contraparte("11111111H", "5000"),)

    result = _reconstruct_detail_rows(current_detail_rows=existing, detail_row_intents=())

    assert result == existing
