"""Unit tests for typed CLI row models (M184 / M232).

These tests verify the pydantic row model contracts that back the
``--row`` CLI flag on ``aeat app modelo work calculate``. They are
oracle-grounded against the AEAT form field constraints documented in:
  - Orden HAP/2250/2015 (M184 atribución de rentas)
  - Orden HFP/816/2017 (M232 operaciones vinculadas)
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .._row_models import (
    Modelo184MemberRow,
    Modelo232VinculadaRow,
)
from ._row_model_support import (
    _assert_validation_error,
    _BaseRevisionIdKwargs,
    _ValidationErrorCase,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_M184_INVALID_CASES = (
    _ValidationErrorCase(
        "porcentaje-above-100",
        lambda: Modelo184MemberRow(nif="33333333C", porcentaje=Decimal("101"), importe=Decimal("0")),
        "100",
    ),
    _ValidationErrorCase(
        "porcentaje-negative",
        lambda: Modelo184MemberRow(nif="33333333C", porcentaje=Decimal("-1"), importe=Decimal("0")),
    ),
    _ValidationErrorCase(
        "pais-lowercase",
        lambda: Modelo184MemberRow(nif="44444444D", pais="de", porcentaje=Decimal("50"), importe=Decimal("0")),
    ),
    _ValidationErrorCase(
        "blank-nif",
        lambda: Modelo184MemberRow(nif="   ", porcentaje=Decimal("50"), importe=Decimal("0")),
    ),
)

_M232_INVALID_CASES = (
    _ValidationErrorCase(
        "pais-lowercase",
        lambda: Modelo232VinculadaRow(nif="A12345678", pais="de", importe=Decimal("1")),
    ),
    _ValidationErrorCase(
        "blank-nif",
        lambda: Modelo232VinculadaRow(nif="   ", importe=Decimal("1")),
    ),
)

# ---------------------------------------------------------------------------
# Modelo184MemberRow — atribución member row
# ---------------------------------------------------------------------------


class TestModelo184MemberRow:
    def test_valid_member_row_round_trips(self) -> None:
        """A fully-populated member row round-trips through the model."""
        row = Modelo184MemberRow(
            nif="12345678A",
            nombre="Núria García Pla",
            pais="ES",
            porcentaje=Decimal("40"),
            importe=Decimal("15000"),
        )
        assert row.nif == "12345678A"
        assert row.nombre == "Núria García Pla"
        assert row.pais == "ES"
        assert row.porcentaje == Decimal("40")
        assert row.importe == Decimal("15000")
        assert row.row_type == "miembro"

    def test_nif_uppercased(self) -> None:
        """NIF is normalised to uppercase."""
        row = Modelo184MemberRow(nif="12345678a", porcentaje=Decimal("50"), importe=Decimal("1"))
        assert row.nif == "12345678A"

    def test_pais_defaults_to_es(self) -> None:
        """pais defaults to ES (domestic member)."""
        row = Modelo184MemberRow(nif="12345678A", porcentaje=Decimal("30"), importe=Decimal("0"))
        assert row.pais == "ES"

    def test_nombre_defaults_empty(self) -> None:
        """nombre defaults to empty string."""
        row = Modelo184MemberRow(nif="12345678A", porcentaje=Decimal("30"), importe=Decimal("0"))
        assert row.nombre == ""

    def test_porcentaje_zero_is_valid(self) -> None:
        """porcentaje=0 is a valid lower-bound value."""
        row = Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("0"), importe=Decimal("0"))
        assert row.porcentaje == Decimal("0")

    def test_porcentaje_100_is_valid(self) -> None:
        """porcentaje=100 is valid (sole member)."""
        row = Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("100"), importe=Decimal("50000"))
        assert row.porcentaje == Decimal("100")

    @pytest.mark.parametrize("case", _M184_INVALID_CASES, ids=lambda case: case.case_id)
    def test_invalid_member_rows_rejected(self, case: _ValidationErrorCase) -> None:
        """Invalid M184 member-row inputs are rejected by the real model."""
        _assert_validation_error(case)

    def test_three_members_round_trip(self) -> None:
        """3-member scenario matching Núria round-17 fixture (40/35/25 split)."""
        rows = [
            Modelo184MemberRow(nif="11111111A", nombre="Sòcia 1", porcentaje=Decimal("40"), importe=Decimal("12000")),
            Modelo184MemberRow(nif="22222222B", nombre="Sòcia 2", porcentaje=Decimal("35"), importe=Decimal("10500")),
            Modelo184MemberRow(nif="33333333C", nombre="Sòcia 3", porcentaje=Decimal("25"), importe=Decimal("7500")),
        ]
        total = sum(r.porcentaje for r in rows)
        assert total == Decimal("100"), "Shares must sum to 100%"
        assert len(rows) == 3
        # Anti-tautology: changing one row's importe only affects that row
        modified = Modelo184MemberRow(
            nif="11111111A",
            nombre="Sòcia 1",
            porcentaje=Decimal("40"),
            importe=Decimal("13000"),
        )
        assert modified.importe != rows[0].importe
        assert rows[1].importe == Decimal("10500")
        assert rows[2].importe == Decimal("7500")

    def test_frozen_model_immutable(self) -> None:
        """Modelo184MemberRow is frozen — mutation attempts raise TypeError."""
        row = Modelo184MemberRow(nif="55555555E", porcentaje=Decimal("50"), importe=Decimal("0"))
        with pytest.raises((ValidationError, TypeError)):
            row.__setattr__("nif", "99999999Z")


# ---------------------------------------------------------------------------
# Modelo232VinculadaRow — operación vinculada row
# ---------------------------------------------------------------------------


class TestModelo232VinculadaRow:
    def test_valid_vinculada_row_round_trips(self) -> None:
        """A fully-populated vinculada row round-trips through the model."""
        row = Modelo232VinculadaRow(
            nif="A12345678",
            nombre="Entitat Vinculada SL",
            pais="ES",
            tipo_vinculacion="1",
            tipo_operacion="01",
            metodo="CUP",
            importe=Decimal("50000"),
        )
        assert row.nif == "A12345678"
        assert row.nombre == "Entitat Vinculada SL"
        assert row.pais == "ES"
        assert row.tipo_operacion == "01"
        assert row.metodo == "CUP"
        assert row.importe == Decimal("50000")
        assert row.row_type == "vinculada"

    def test_nif_uppercased(self) -> None:
        """NIF is normalised to uppercase."""
        row = Modelo232VinculadaRow(nif="a12345678", importe=Decimal("1"))
        assert row.nif == "A12345678"

    def test_pais_defaults_to_es(self) -> None:
        """pais defaults to ES."""
        row = Modelo232VinculadaRow(nif="A12345678", importe=Decimal("1"))
        assert row.pais == "ES"

    def test_metodo_defaults_empty(self) -> None:
        """metodo defaults to empty string."""
        row = Modelo232VinculadaRow(nif="A12345678", importe=Decimal("1"))
        assert row.metodo == ""

    def test_metodo_uppercased(self) -> None:
        """metodo is uppercased."""
        row = Modelo232VinculadaRow(nif="A12345678", metodo="cup", importe=Decimal("1"))
        assert row.metodo == "CUP"

    @pytest.mark.parametrize("case", _M232_INVALID_CASES, ids=lambda case: case.case_id)
    def test_invalid_vinculada_rows_rejected(self, case: _ValidationErrorCase) -> None:
        """Invalid M232 vinculada-row inputs are rejected by the real model."""
        _assert_validation_error(case)

    def test_two_related_party_rows_distinguish_by_importe(self) -> None:
        """Two related-party rows with different importes are distinct.

        Anti-tautology: changing one row's importe does not affect the other.
        Grounded against M232 form constraint (each operación is declared
        separately per counterparty + operation kind + method).
        """
        row1 = Modelo232VinculadaRow(nif="A12345678", tipo_operacion="01", importe=Decimal("50000"))
        row2 = Modelo232VinculadaRow(nif="B87654321", tipo_operacion="05", importe=Decimal("30000"))
        assert row1.importe != row2.importe
        assert row1.nif != row2.nif
        # Modify row1's importe → row2 unchanged
        row1_modified = Modelo232VinculadaRow(nif="A12345678", tipo_operacion="01", importe=Decimal("75000"))
        assert row1_modified.importe == Decimal("75000")
        assert row2.importe == Decimal("30000")

    def test_frozen_model_immutable(self) -> None:
        """Modelo232VinculadaRow is frozen."""
        row = Modelo232VinculadaRow(nif="A12345678", importe=Decimal("1"))
        with pytest.raises((ValidationError, TypeError)):
            row.__setattr__("nif", "Z99999999")


# ---------------------------------------------------------------------------
# derive_calculation_revision_id with detail_rows
# ---------------------------------------------------------------------------


class TestRevisionIdWithDetailRows:
    """The revision id must change when detail rows change.

    This is the anti-tautology proof for the content-addressing contract:
    two revisions with identical scalar inputs but different row lists
    must NOT share a revision id.
    """

    def test_revision_id_changes_when_rows_differ(self) -> None:
        from .._calculation_revision import derive_calculation_revision_id

        base_kwargs: _BaseRevisionIdKwargs = {
            "work_unit_id": "a" * 64,
            "input_values_by_casilla_id": {},
            "binding_overrides": {},
            "casilla_values": {},
        }
        id_no_rows = derive_calculation_revision_id(**base_kwargs)
        id_one_row = derive_calculation_revision_id(
            **base_kwargs,
            detail_rows=(Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("100"), importe=Decimal("10000")),),
        )
        id_two_rows = derive_calculation_revision_id(
            **base_kwargs,
            detail_rows=(
                Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("60"), importe=Decimal("6000")),
                Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("4000")),
            ),
        )
        # All three must differ
        assert id_no_rows != id_one_row
        assert id_no_rows != id_two_rows
        assert id_one_row != id_two_rows

    def test_revision_id_stable_when_rows_identical(self) -> None:
        """Same rows → same id regardless of call order."""
        from .._calculation_revision import derive_calculation_revision_id

        rows = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("40"), importe=Decimal("4000")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("60"), importe=Decimal("6000")),
        )
        first = derive_calculation_revision_id(
            work_unit_id="b" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            detail_rows=rows,
        )
        second = derive_calculation_revision_id(
            work_unit_id="b" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            detail_rows=rows,
        )
        assert first == second

    def test_row_order_canonical_same_id(self) -> None:
        """Row insertion order must NOT affect the id (rows are sorted by nif)."""
        from .._calculation_revision import derive_calculation_revision_id

        row_a = Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("40"), importe=Decimal("4000"))
        row_b = Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("60"), importe=Decimal("6000"))
        id_ab = derive_calculation_revision_id(
            work_unit_id="c" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            detail_rows=(row_a, row_b),
        )
        id_ba = derive_calculation_revision_id(
            work_unit_id="c" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            detail_rows=(row_b, row_a),
        )
        assert id_ab == id_ba

    def test_changing_one_row_importe_changes_id(self) -> None:
        """Anti-tautology: mutating one row's importe changes the revision id."""
        from .._calculation_revision import derive_calculation_revision_id

        def _id(importe_1: str, importe_2: str) -> str:
            return derive_calculation_revision_id(
                work_unit_id="d" * 64,
                input_values_by_casilla_id={},
                binding_overrides={},
                casilla_values={},
                detail_rows=(
                    Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("60"), importe=Decimal(importe_1)),
                    Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal(importe_2)),
                ),
            )

        base = _id("6000", "4000")
        row1_changed = _id("7000", "4000")
        row2_changed = _id("6000", "5000")
        assert base != row1_changed
        assert base != row2_changed
        assert row1_changed != row2_changed
