"""Unit tests for Modelo 347 row models and mixed detail-row revision ids."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import M347_THRESHOLD_EUR
from ..calculation_revision import derive_calculation_revision_id
from ..row_models import (
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

_DetailRowFactory = Callable[
    [],
    Modelo184MemberRow | Modelo232VinculadaRow | Modelo349OperadorRow | Modelo347ContraparteRow,
]


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


def _contraparte_row() -> Modelo347ContraparteRow:
    return Modelo347ContraparteRow(nif="44444444C", importe_Q1=Decimal("4000"))


_REVISION_ROW_FACTORIES: tuple[tuple[str, _DetailRowFactory], ...] = (
    ("m184-member", _member_row),
    ("m232-vinculada", _vinculada_row),
    ("m349-operador", _operador_row),
    ("m347-contraparte", _contraparte_row),
)


def _revision_base(work_unit_id: str) -> _BaseRevisionIdKwargs:
    return {
        "work_unit_id": work_unit_id,
        "input_values_by_casilla_id": {},
        "binding_overrides": {},
        "casilla_values": {},
    }


def _all_revision_rows() -> tuple[
    Modelo184MemberRow | Modelo232VinculadaRow | Modelo349OperadorRow | Modelo347ContraparteRow,
    ...,
]:
    return tuple(factory() for _, factory in _REVISION_ROW_FACTORIES)


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

    def test_pais_codigo_normalized(self) -> None:
        cases = (
            ("domestic", None, None),
            ("foreign", "de", "DE"),
        )

        for case_id, pais_codigo, expected in cases:
            row = Modelo347ContraparteRow(nif="12345678A", pais_codigo=pais_codigo)
            assert row.pais_codigo == expected, case_id

    def test_invalid_contraparte_rows_rejected(self) -> None:
        for case in _M347_INVALID_CASES:
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

    def test_sort_canonical_across_all_four_types(self) -> None:
        base = _revision_base("d" * 64)
        member, vinculada, operador, contraparte = _all_revision_rows()
        id_forward = derive_calculation_revision_id(
            **base,
            detail_rows=(member, vinculada, operador, contraparte),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        id_reversed = derive_calculation_revision_id(
            **base,
            detail_rows=(contraparte, operador, vinculada, member),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        assert id_forward == id_reversed
