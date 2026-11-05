"""Calculation revision ids over mixed detail-row unions."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from ..calculation_revision import derive_calculation_revision_id
from ..row_models import (
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo349OperadorRow,
)
from .row_model_support import BaseRevisionIdKwargs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

type _RevisionDetailRow = Modelo184MemberRow | Modelo232VinculadaRow | Modelo349OperadorRow
_DetailRowFactory = Callable[[], _RevisionDetailRow]


def _member_row() -> Modelo184MemberRow:
    return Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("100"), importe=Decimal("1000"), clave="D")


def _vinculada_row() -> Modelo232VinculadaRow:
    return Modelo232VinculadaRow(pais="ES", nif="22222222B", importe=Decimal("2000"))


def _operador_row() -> Modelo349OperadorRow:
    return Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        razon_social="Deutschland GmbH",
        clave_operacion="E",
        importe=Decimal("3000"),
    )


_REVISION_ROW_FACTORIES: tuple[tuple[str, _DetailRowFactory], ...] = (
    ("m184-member", _member_row),
    ("m232-vinculada", _vinculada_row),
    ("m349-operador", _operador_row),
)


def _revision_base(work_unit_id: str) -> BaseRevisionIdKwargs:
    return {
        "work_unit_id": work_unit_id,
        "input_values_by_casilla_id": {},
        "binding_overrides": {},
        "casilla_values": {},
    }


def _all_revision_rows() -> tuple[_RevisionDetailRow, ...]:
    return tuple(factory() for _, factory in _REVISION_ROW_FACTORIES)


class TestRevisionIdAcrossRowTypes:
    def test_each_row_type_derives_without_crash(self) -> None:
        for case_id, row_factory in _REVISION_ROW_FACTORIES:
            rev_id = derive_calculation_revision_id(
                **_revision_base("a" * 64),
                detail_rows=(row_factory(),),
                filing_instance_evidence=None,
                source_provenance=(),
            )
            assert len(rev_id) == 64, case_id
            assert rev_id == rev_id.lower(), case_id

    def test_mixed_union_payload_sorts_without_crash(self) -> None:
        rev_id = derive_calculation_revision_id(
            **_revision_base("b" * 64),
            detail_rows=_all_revision_rows(),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        assert len(rev_id) == 64

    def test_operador_nif_comunitario_change_changes_id(self) -> None:
        base = _revision_base("c" * 64)
        id_de = derive_calculation_revision_id(
            **base,
            detail_rows=(
                Modelo349OperadorRow(
                    codigo_pais="DE",
                    nif_comunitario="DE123456789",
                    razon_social="Deutschland GmbH",
                    clave_operacion="E",
                    importe=Decimal("1000"),
                ),
            ),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        id_fr = derive_calculation_revision_id(
            **base,
            detail_rows=(
                Modelo349OperadorRow(
                    codigo_pais="FR",
                    nif_comunitario="FR12345678901",
                    razon_social="France SARL",
                    clave_operacion="E",
                    importe=Decimal("1000"),
                ),
            ),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        assert id_de != id_fr

    def test_sort_canonical_across_all_row_types(self) -> None:
        base = _revision_base("d" * 64)
        member, vinculada, operador = _all_revision_rows()
        id_forward = derive_calculation_revision_id(
            **base,
            detail_rows=(member, vinculada, operador),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        id_reversed = derive_calculation_revision_id(
            **base,
            detail_rows=(operador, vinculada, member),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        assert id_forward == id_reversed


def _operador(importe: Decimal) -> Modelo349OperadorRow:
    return Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        razon_social="Deutschland GmbH",
        clave_operacion="E",
        importe=importe,
    )


def _id_of(row: Modelo349OperadorRow) -> str:
    return derive_calculation_revision_id(
        **_revision_base("e" * 64),
        detail_rows=(row,),
        filing_instance_evidence=None,
        source_provenance=(),
    )


class TestDetailRowAmountSpelling:
    @pytest.mark.parametrize("zero", ["-0", "-0.00", "0.00", "0E+3", "-0E-2"])
    def test_every_spelling_of_zero_derives_one_id(self, zero: str) -> None:
        assert _id_of(_operador(Decimal(zero))) == _id_of(_operador(Decimal("0")))

    def test_a_non_zero_amount_still_spells_as_the_stored_ids_were_derived(self) -> None:
        from ..calculation_revision_identity import detail_row_amount_text

        for amount in ("1000.00", "3000", "12.50", "0.0000001", "123456789.10", "-40.0", "7"):
            assert detail_row_amount_text(Decimal(amount)) == str(Decimal(amount).normalize()), amount

    def test_equal_non_zero_amounts_derive_one_id_and_unequal_ones_do_not(self) -> None:
        assert _id_of(_operador(Decimal("1000"))) == _id_of(_operador(Decimal("1000.00")))
        assert _id_of(_operador(Decimal("1000"))) != _id_of(_operador(Decimal("1000.01")))
