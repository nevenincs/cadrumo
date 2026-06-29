"""Unit tests for Modelo 347 row models and mixed detail-row revision ids."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .._row_models import (
    M347_THRESHOLD_EUR,
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
)
from ._row_model_support import (
    _assert_validation_error,
    _BaseRevisionIdKwargs,
    _ValidationErrorCase,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_M347_INVALID_CASES = (
    _ValidationErrorCase(
        "invalid-pais-codigo",
        lambda: Modelo347ContraparteRow(nif="12345678A", pais_codigo="ESP"),
    ),
    _ValidationErrorCase(
        "blank-nif",
        lambda: Modelo347ContraparteRow(nif="   "),
    ),
)


class TestModelo347ContraparteRow:
    def test_valid_contraparte_row_round_trips(self) -> None:
        row = Modelo347ContraparteRow(
            nif="12345678A",
            nombre="Proveedor SL",
            importe_Q1=Decimal("10000"),
            importe_Q2=Decimal("5000"),
            importe_Q3=Decimal("8000"),
            importe_Q4=Decimal("7000"),
            clave_operacion="A",
        )
        assert row.nif == "12345678A"
        assert row.nombre == "Proveedor SL"
        assert row.importe_total == Decimal("30000")
        assert row.clave_operacion == "A"
        assert row.pais_codigo is None
        assert row.row_type == "contraparte"

    def test_nif_uppercased(self) -> None:
        row = Modelo347ContraparteRow(nif="12345678a", importe_Q1=Decimal("4000"))
        assert row.nif == "12345678A"

    def test_quarterly_importes_default_zero(self) -> None:
        row = Modelo347ContraparteRow(nif="12345678A")
        assert row.importe_Q1 == Decimal("0")
        assert row.importe_Q2 == Decimal("0")
        assert row.importe_Q3 == Decimal("0")
        assert row.importe_Q4 == Decimal("0")

    def test_importe_total_sums_quarters(self) -> None:
        row = Modelo347ContraparteRow(
            nif="12345678A",
            importe_Q1=Decimal("1000"),
            importe_Q2=Decimal("1000"),
            importe_Q3=Decimal("1000"),
            importe_Q4=Decimal("1005.06"),
        )
        assert row.importe_total == Decimal("4005.06")

    def test_pais_codigo_none_for_domestic(self) -> None:
        row = Modelo347ContraparteRow(nif="12345678A", pais_codigo=None)
        assert row.pais_codigo is None

    def test_pais_codigo_uppercased(self) -> None:
        row = Modelo347ContraparteRow(nif="12345678A", pais_codigo="de")
        assert row.pais_codigo == "DE"

    @pytest.mark.parametrize("case", _M347_INVALID_CASES, ids=lambda case: case.case_id)
    def test_invalid_contraparte_rows_rejected(self, case: _ValidationErrorCase) -> None:
        _assert_validation_error(case)

    def test_frozen_model_immutable(self) -> None:
        row = Modelo347ContraparteRow(nif="12345678A")
        with pytest.raises((ValidationError, TypeError)):
            row.__setattr__("nif", "99999999Z")

    def test_threshold_constant_matches_rd_1065_2007(self) -> None:
        assert Decimal("3005.06") == M347_THRESHOLD_EUR

    def test_two_rows_distinguish_by_quarterly_importe(self) -> None:
        row1 = Modelo347ContraparteRow(nif="11111111A", importe_Q1=Decimal("5000"))
        row2 = Modelo347ContraparteRow(nif="11111111A", importe_Q1=Decimal("8000"))
        assert row1.importe_total != row2.importe_total
        assert row2.importe_Q1 == Decimal("8000")


class TestRevisionIdAcrossAllFourRowTypes:
    @staticmethod
    def _member_row() -> Modelo184MemberRow:
        return Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("100"), importe=Decimal("1000"))

    @staticmethod
    def _vinculada_row() -> Modelo232VinculadaRow:
        return Modelo232VinculadaRow(nif="22222222B", importe=Decimal("2000"))

    @staticmethod
    def _operador_row() -> Modelo349OperadorRow:
        return Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Deutschland GmbH",
            clave_operacion="E",
            importe=Decimal("3000"),
        )

    @staticmethod
    def _contraparte_row() -> Modelo347ContraparteRow:
        return Modelo347ContraparteRow(nif="44444444C", importe_Q1=Decimal("4000"))

    def test_each_row_type_derives_without_crash(self) -> None:
        from .._calculation_revision import derive_calculation_revision_id

        base: _BaseRevisionIdKwargs = {
            "work_unit_id": "a" * 64,
            "input_values_by_casilla_id": {},
            "binding_overrides": {},
            "casilla_values": {},
        }
        for row in (
            self._member_row(),
            self._vinculada_row(),
            self._operador_row(),
            self._contraparte_row(),
        ):
            rev_id = derive_calculation_revision_id(**base, detail_rows=(row,))
            assert len(rev_id) == 64
            assert rev_id == rev_id.lower()

    def test_mixed_union_payload_sorts_without_crash(self) -> None:
        from .._calculation_revision import derive_calculation_revision_id

        rows = (
            self._member_row(),
            self._vinculada_row(),
            self._operador_row(),
            self._contraparte_row(),
        )
        rev_id = derive_calculation_revision_id(
            work_unit_id="b" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            detail_rows=rows,
        )
        assert len(rev_id) == 64

    def test_operador_nif_comunitario_change_changes_id(self) -> None:
        from .._calculation_revision import derive_calculation_revision_id

        base: _BaseRevisionIdKwargs = {
            "work_unit_id": "c" * 64,
            "input_values_by_casilla_id": {},
            "binding_overrides": {},
            "casilla_values": {},
        }
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
        )
        assert id_de != id_fr

    def test_sort_canonical_across_all_four_types(self) -> None:
        from .._calculation_revision import derive_calculation_revision_id

        base: _BaseRevisionIdKwargs = {
            "work_unit_id": "d" * 64,
            "input_values_by_casilla_id": {},
            "binding_overrides": {},
            "casilla_values": {},
        }
        member = self._member_row()
        vinculada = self._vinculada_row()
        operador = self._operador_row()
        contraparte = self._contraparte_row()
        id_forward = derive_calculation_revision_id(
            **base,
            detail_rows=(member, vinculada, operador, contraparte),
        )
        id_reversed = derive_calculation_revision_id(
            **base,
            detail_rows=(contraparte, operador, vinculada, member),
        )
        assert id_forward == id_reversed
