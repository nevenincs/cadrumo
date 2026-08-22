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

from .._calculation_revision import derive_calculation_revision_id
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


def _vinculada_from_operator_input(**overrides: str) -> Modelo232VinculadaRow:
    """Build a vinculada row the way the CLI does — untyped key=value text.

    Every field but the one under test is a value the model accepts, so a
    refusal can only have come from the overridden code. ``importe`` is a real
    :class:`~decimal.Decimal`: the strict model rejects a string there, and a
    string would make each case pass on the amount rather than the catalogue.
    """
    return Modelo232VinculadaRow.model_validate(
        {"row_type": "vinculada", "nif": "A12345678", "pais": "ES", "importe": Decimal("1"), **overrides},
    )


def test_vinculada_operator_input_helper_builds_a_valid_row() -> None:
    """The refusal helper's baseline must VALIDATE, or every refusal case is vacuous.

    Anti-tautology guard for :data:`_M232_INVALID_CASES`: without it, a typo in
    an untested field would refuse every case and the catalogue enforcement
    would be proven by nothing.
    """
    row = _vinculada_from_operator_input()
    assert row.nif == "A12345678"
    assert (row.tipo_vinculacion, row.tipo_operacion, row.metodo) == ("", "", "")


_M232_INVALID_CASES = (
    _ValidationErrorCase(
        "pais-lowercase",
        lambda: Modelo232VinculadaRow(nif="A12345678", pais="de", importe=Decimal("1")),
    ),
    _ValidationErrorCase(
        "blank-nif",
        lambda: Modelo232VinculadaRow(pais="ES", nif="   ", importe=Decimal("1")),
    ),
    # Off-catalogue codes arrive the way the CLI delivers them -- as untyped
    # `--row vinculada k=v` text through `model_validate` -- so these exercise
    # the runtime refusal on the real operator path, not a typed constructor
    # the operator never reaches.
    #
    # DR23200 Tabla A runs A-H in a single alphanumeric position; a numeric
    # code and a two-character one are both off-catalogue and unrepresentable.
    _ValidationErrorCase(
        "tipo-vinculacion-numeric",
        lambda: _vinculada_from_operator_input(tipo_vinculacion="1"),
    ),
    _ValidationErrorCase(
        "tipo-vinculacion-off-catalogue-letter",
        lambda: _vinculada_from_operator_input(tipo_vinculacion="Z"),
    ),
    # Orden HFP/816/2017 art. 3.1.f enumerates eleven claves; nothing above 11.
    _ValidationErrorCase(
        "tipo-operacion-above-catalogue",
        lambda: _vinculada_from_operator_input(tipo_operacion="99"),
    ),
    _ValidationErrorCase(
        "tipo-operacion-unpadded",
        lambda: _vinculada_from_operator_input(tipo_operacion="1"),
    ),
    # DR23200 Tabla B codes are 1A-1E in two positions; the OECD abbreviations
    # for the same art. 18.4 methods are not AEAT's codes and do not fit.
    _ValidationErrorCase(
        "metodo-oecd-abbreviation",
        lambda: _vinculada_from_operator_input(metodo="TNMM"),
    ),
    _ValidationErrorCase(
        "metodo-off-catalogue",
        lambda: _vinculada_from_operator_input(metodo="ZZ"),
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

    def test_member_row_scalar_contracts(self) -> None:
        """Scalar normalization, defaults, and documented bounds use the real model."""
        cases = (
            (
                Modelo184MemberRow(nif="12345678a", porcentaje=Decimal("50"), importe=Decimal("1")),
                "nif",
                "12345678A",
            ),
            (
                # A member row stating no country carries NONE, not Spain. The
                # field defaulted to "ES", so a foreign member whose country
                # nobody supplied was declared domestic -- and this case
                # asserted that default, which made the defect the contract.
                Modelo184MemberRow(nif="12345678A", porcentaje=Decimal("30"), importe=Decimal("0")),
                "pais",
                None,
            ),
            (
                Modelo184MemberRow(nif="12345678A", porcentaje=Decimal("30"), importe=Decimal("0")),
                "nombre",
                "",
            ),
            (
                Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("0"), importe=Decimal("0")),
                "porcentaje",
                Decimal("0"),
            ),
            (
                Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("100"), importe=Decimal("50000")),
                "porcentaje",
                Decimal("100"),
            ),
        )
        for row, field_name, expected in cases:
            assert getattr(row, field_name) == expected, field_name

    def test_invalid_member_rows_rejected(self) -> None:
        """Invalid M184 member-row inputs are rejected by the real model."""
        for case in _M184_INVALID_CASES:
            try:
                _assert_validation_error(case)
            except AssertionError as exc:
                raise AssertionError(case.case_id) from exc

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
            tipo_vinculacion="A",
            tipo_operacion="01",
            metodo="1A",
            importe=Decimal("50000"),
        )
        assert row.nif == "A12345678"
        assert row.nombre == "Entitat Vinculada SL"
        assert row.pais == "ES"
        assert row.tipo_operacion == "01"
        assert row.tipo_vinculacion == "A"
        assert row.metodo == "1A"
        assert row.importe == Decimal("50000")
        assert row.row_type == "vinculada"

    def test_vinculada_row_scalar_contracts(self) -> None:
        """Scalar normalization and defaults use the real model."""
        cases = (
            (Modelo232VinculadaRow(pais="ES", nif="a12345678", importe=Decimal("1")), "nif", "A12345678"),
            (Modelo232VinculadaRow(pais="ES", nif="A12345678", importe=Decimal("1")), "pais", "ES"),
            (Modelo232VinculadaRow(pais="ES", nif="A12345678", importe=Decimal("1")), "metodo", ""),
            (Modelo232VinculadaRow(pais="ES", nif="A12345678", metodo="1a", importe=Decimal("1")), "metodo", "1A"),
            (
                Modelo232VinculadaRow(pais="ES", nif="A12345678", tipo_vinculacion="d", importe=Decimal("1")),
                "tipo_vinculacion",
                "D",
            ),
            (Modelo232VinculadaRow(pais="ES", nif="A12345678", importe=Decimal("1")), "tipo_operacion", ""),
        )
        for row, field_name, expected in cases:
            assert getattr(row, field_name) == expected, field_name

    def test_invalid_vinculada_rows_rejected(self) -> None:
        """Invalid M232 vinculada-row inputs are rejected by the real model."""
        for case in _M232_INVALID_CASES:
            try:
                _assert_validation_error(case)
            except AssertionError as exc:
                raise AssertionError(case.case_id) from exc

    def test_two_related_party_rows_distinguish_by_importe(self) -> None:
        """Two related-party rows with different importes are distinct.

        Anti-tautology: changing one row's importe does not affect the other.
        Grounded against M232 form constraint (each operación is declared
        separately per counterparty + operation kind + method).
        """
        row1 = Modelo232VinculadaRow(pais="ES", nif="A12345678", tipo_operacion="01", importe=Decimal("50000"))
        row2 = Modelo232VinculadaRow(pais="ES", nif="B87654321", tipo_operacion="05", importe=Decimal("30000"))
        assert row1.importe != row2.importe
        assert row1.nif != row2.nif
        # Modify row1's importe → row2 unchanged
        row1_modified = Modelo232VinculadaRow(pais="ES", nif="A12345678", tipo_operacion="01", importe=Decimal("75000"))
        assert row1_modified.importe == Decimal("75000")
        assert row2.importe == Decimal("30000")


# ---------------------------------------------------------------------------
# derive_calculation_revision_id with detail_rows
# ---------------------------------------------------------------------------


def test_row_models_are_frozen() -> None:
    """Row models are immutable once validated."""
    cases = (
        (Modelo184MemberRow(nif="55555555E", porcentaje=Decimal("50"), importe=Decimal("0")), "99999999Z"),
        (Modelo232VinculadaRow(pais="ES", nif="A12345678", importe=Decimal("1")), "Z99999999"),
    )
    for row, replacement_nif in cases:
        with pytest.raises((ValidationError, TypeError)):
            row.__setattr__("nif", replacement_nif)


class TestRevisionIdWithDetailRows:
    """The revision id must change when detail rows change.

    This is the anti-tautology proof for the content-addressing contract:
    two revisions with identical scalar inputs but different row lists
    must NOT share a revision id.
    """

    def test_revision_id_changes_when_rows_differ(self) -> None:
        base_kwargs: _BaseRevisionIdKwargs = {
            "work_unit_id": "a" * 64,
            "input_values_by_casilla_id": {},
            "binding_overrides": {},
            "casilla_values": {},
        }
        id_no_rows = derive_calculation_revision_id(**base_kwargs, filing_instance_evidence=None, source_provenance=())
        id_one_row = derive_calculation_revision_id(
            **base_kwargs,
            detail_rows=(Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("100"), importe=Decimal("10000")),),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        id_two_rows = derive_calculation_revision_id(
            **base_kwargs,
            detail_rows=(
                Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("60"), importe=Decimal("6000")),
                Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("4000")),
            ),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        # All three must differ
        assert id_no_rows != id_one_row
        assert id_no_rows != id_two_rows
        assert id_one_row != id_two_rows

    def test_revision_id_stable_when_rows_identical(self) -> None:
        """Same rows → same id regardless of call order."""
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
            filing_instance_evidence=None,
            source_provenance=(),
        )
        second = derive_calculation_revision_id(
            work_unit_id="b" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            detail_rows=rows,
            filing_instance_evidence=None,
            source_provenance=(),
        )
        assert first == second

    def test_row_order_canonical_same_id(self) -> None:
        """Row insertion order must NOT affect the id (rows are sorted by nif)."""
        row_a = Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("40"), importe=Decimal("4000"))
        row_b = Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("60"), importe=Decimal("6000"))
        id_ab = derive_calculation_revision_id(
            work_unit_id="c" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            detail_rows=(row_a, row_b),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        id_ba = derive_calculation_revision_id(
            work_unit_id="c" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            detail_rows=(row_b, row_a),
            filing_instance_evidence=None,
            source_provenance=(),
        )
        assert id_ab == id_ba

    def test_changing_one_row_importe_changes_id(self) -> None:
        """Anti-tautology: mutating one row's importe changes the revision id."""

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
                filing_instance_evidence=None,
                source_provenance=(),
            )

        base = _id("6000", "4000")
        row1_changed = _id("7000", "4000")
        row2_changed = _id("6000", "5000")
        assert base != row1_changed
        assert base != row2_changed
        assert row1_changed != row2_changed
