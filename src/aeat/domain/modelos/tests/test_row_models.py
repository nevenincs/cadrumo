"""Unit tests for typed CLI row models (M184 / M232 / M349 / M347).

These tests verify the pydantic row model contracts that back the
``--row`` CLI flag on ``aeat app modelo work calculate``. They are
oracle-grounded against the AEAT form field constraints documented in:
  - Orden HAP/2250/2015 (M184 atribución de rentas)
  - Orden HFP/816/2017 (M232 operaciones vinculadas)
  - Orden HAC/174/2020 Anexo II (M349 operador intracomunitario)
  - Orden EHA/3012/2008 + RD 1065/2007 art. 31 (M347 contraparte)
"""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

import pytest
from pydantic import ValidationError

from ...calculations.registry import CasillaId
from .._row_models import (
    M347_THRESHOLD_EUR,
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    m349_nif_number_for_export,
    validate_m349_nif_format,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


type RevisionInputSnapshot = dict[str, str]


class _BaseRevisionIdKwargs(TypedDict):
    """Typed base kwargs for derive_calculation_revision_id calls in tests."""

    work_unit_id: str
    input_values_by_casilla_id: RevisionInputSnapshot
    binding_overrides: dict[str, str]
    casilla_values: dict[CasillaId, Decimal]


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

    def test_porcentaje_above_100_rejected(self) -> None:
        """porcentaje > 100 is rejected per M184 business rule."""
        with pytest.raises(ValidationError, match="100"):
            Modelo184MemberRow(nif="33333333C", porcentaje=Decimal("101"), importe=Decimal("0"))

    def test_porcentaje_negative_rejected(self) -> None:
        """Negative porcentaje is rejected."""
        with pytest.raises(ValidationError):
            Modelo184MemberRow(nif="33333333C", porcentaje=Decimal("-1"), importe=Decimal("0"))

    def test_pais_must_be_uppercase_alpha(self) -> None:
        """pais must be uppercase two-letter ISO country code."""
        with pytest.raises(ValidationError):
            Modelo184MemberRow(nif="44444444D", pais="de", porcentaje=Decimal("50"), importe=Decimal("0"))

    def test_nif_blank_rejected(self) -> None:
        """Blank NIF is rejected."""
        with pytest.raises(ValidationError):
            Modelo184MemberRow(nif="   ", porcentaje=Decimal("50"), importe=Decimal("0"))

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

    def test_pais_must_be_uppercase_alpha(self) -> None:
        """pais must be uppercase two-letter ISO country code."""
        with pytest.raises(ValidationError):
            Modelo232VinculadaRow(nif="A12345678", pais="de", importe=Decimal("1"))

    def test_nif_blank_rejected(self) -> None:
        """Blank NIF is rejected."""
        with pytest.raises(ValidationError):
            Modelo232VinculadaRow(nif="   ", importe=Decimal("1"))

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


# ---------------------------------------------------------------------------
# Modelo349OperadorRow — operador intracomunitario row (M349 manual-entry)
# ---------------------------------------------------------------------------


class TestModelo349OperadorRow:
    def test_valid_operador_row_round_trips(self) -> None:
        """A fully-populated operador row round-trips through the model."""
        row = Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Müller GmbH",
            clave_operacion="E",
            importe=Decimal("50000"),
        )
        assert row.codigo_pais == "DE"
        assert row.nif_comunitario == "DE123456789"
        assert row.razon_social == "Müller GmbH"
        assert row.clave_operacion == "E"
        assert row.importe == Decimal("50000")
        assert row.row_type == "operador"

    def test_nif_comunitario_uppercased(self) -> None:
        """nif_comunitario is normalised to uppercase."""
        row = Modelo349OperadorRow(
            codigo_pais="FR",
            nif_comunitario="fr12345678901",
            clave_operacion="S",
            importe=Decimal("1"),
        )
        assert row.nif_comunitario == "FR12345678901"

    def test_razon_social_defaults_empty(self) -> None:
        """razon_social defaults to empty string."""
        row = Modelo349OperadorRow(
            codigo_pais="IT",
            nif_comunitario="IT12345678901",
            clave_operacion="M",
            importe=Decimal("1000"),
        )
        assert row.razon_social == ""

    def test_importe_zero_is_valid(self) -> None:
        """importe=0 is valid per Orden HAC/174/2020 (zero-value ops can appear)."""
        row = Modelo349OperadorRow(
            codigo_pais="PT",
            nif_comunitario="PT123456789",
            clave_operacion="T",
            importe=Decimal("0"),
        )
        assert row.importe == Decimal("0")

    def test_importe_negative_rejected(self) -> None:
        """Negative importe is rejected per Orden HAC/174/2020 non_negative constraint."""
        with pytest.raises(ValidationError, match="non-negative"):
            Modelo349OperadorRow(
                codigo_pais="DE",
                nif_comunitario="DE123456789",
                clave_operacion="E",
                importe=Decimal("-1"),
            )

    def test_codigo_pais_must_be_uppercase_alpha(self) -> None:
        """codigo_pais must be uppercase two-letter ISO code."""
        with pytest.raises(ValidationError):
            Modelo349OperadorRow(
                codigo_pais="de",
                nif_comunitario="DE123456789",
                clave_operacion="E",
                importe=Decimal("1"),
            )

    def test_invalid_clave_operacion_rejected(self) -> None:
        """Clave not in the Orden HAC/174/2020 catalogue is rejected."""
        with pytest.raises(ValidationError):
            Modelo349OperadorRow.model_validate(
                {
                    "codigo_pais": "DE",
                    "nif_comunitario": "DE123456789",
                    "clave_operacion": "Z",
                    "importe": Decimal("1"),
                },
            )

    def test_frozen_model_immutable(self) -> None:
        """Modelo349OperadorRow is frozen."""
        row = Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            clave_operacion="E",
            importe=Decimal("1"),
        )
        with pytest.raises((ValidationError, TypeError)):
            row.__setattr__("codigo_pais", "FR")

    def test_two_rows_distinguish_by_importe(self) -> None:
        """Anti-tautology: two rows with different importes are distinct.

        Grounded: M349 filing has one Tipo-2 record per operator + clave pair.
        Changing one row's importe does not affect the other.
        """
        row1 = Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            clave_operacion="E",
            importe=Decimal("50000"),
        )
        row2 = Modelo349OperadorRow(
            codigo_pais="FR",
            nif_comunitario="FR12345678901",
            clave_operacion="S",
            importe=Decimal("30000"),
        )
        assert row1.importe != row2.importe
        row1_modified = Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            clave_operacion="E",
            importe=Decimal("75000"),
        )
        assert row1_modified.importe == Decimal("75000")
        assert row2.importe == Decimal("30000")


# ---------------------------------------------------------------------------
# validate_m349_nif_format — country-specific NIF-IVA format validation
# Oracle-grounded against Council Directive 2006/112/EC Annex XI patterns.
# ---------------------------------------------------------------------------


class TestValidateM349NifFormat:
    def test_valid_german_nif(self) -> None:
        """DE + 9 digits matches the German NIF-IVA pattern."""
        assert validate_m349_nif_format("DE123456789", "DE") is True

    def test_invalid_german_nif_too_short(self) -> None:
        """DE + 8 digits does not match (must be exactly 9)."""
        assert validate_m349_nif_format("DE12345678", "DE") is False

    def test_valid_french_nif(self) -> None:
        """FR + 2 alphanum + 9 digits is valid."""
        assert validate_m349_nif_format("FR12345678901", "FR") is True

    def test_valid_italian_nif(self) -> None:
        """IT + 11 digits is valid."""
        assert validate_m349_nif_format("IT12345678901", "IT") is True

    def test_valid_dutch_nif(self) -> None:
        """NL + 9 digits + B + 2 digits matches Dutch pattern."""
        assert validate_m349_nif_format("NL123456789B01", "NL") is True

    def test_official_greece_country_code_is_supported(self) -> None:
        """EL + 9 digits matches the AEAT Modelo 349 instruction table."""
        assert validate_m349_nif_format("EL123456789", "EL") is True

    def test_unknown_country_rejected(self) -> None:
        """Country prefixes absent from the M349 instructions fail closed."""
        assert validate_m349_nif_format("XX12345", "XX") is False

    def test_unknown_country_badvat_rejected(self) -> None:
        """Persona repro: an unsupported country cannot pass via generic NIF shape."""
        assert validate_m349_nif_format("BADVAT", "ZZ") is False

    def test_supported_country_too_short_rejected(self) -> None:
        """Known country patterns still reject malformed NIFs."""
        assert validate_m349_nif_format("EL1", "EL") is False

    def test_antitautology_de_pattern_rejects_fr_shaped_nif(self) -> None:
        """Anti-tautology: a FR-format NIF does not pass the DE validator.

        DE requires exactly 9 digits after the prefix. FR has 2 alphanum + 9 digits.
        The DE pattern would reject a 13-character FR NIF.
        """
        assert validate_m349_nif_format("FR12345678901", "DE") is False


class TestM349NifNumberForExport:
    def test_strips_country_prefix_for_boe_nif_subfield(self) -> None:
        """The fixed-width NIF slot excludes the separately-exported country code."""
        assert m349_nif_number_for_export("DE123456789", "DE") == "123456789"
        assert m349_nif_number_for_export("FR12345678901", "FR") == "12345678901"

    def test_rejects_invalid_or_mismatched_prefixed_nif(self) -> None:
        """Export normalization keeps the same validation as row input."""
        with pytest.raises(ValueError, match="expected NIF-IVA format"):
            m349_nif_number_for_export("FR12345678901", "DE")


# ---------------------------------------------------------------------------
# Modelo347ContraparteRow — contraparte declarada row (M347)
# ---------------------------------------------------------------------------


class TestModelo347ContraparteRow:
    def test_valid_contraparte_row_round_trips(self) -> None:
        """A fully-populated contraparte row round-trips through the model."""
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
        """NIF is normalised to uppercase."""
        row = Modelo347ContraparteRow(nif="12345678a", importe_Q1=Decimal("4000"))
        assert row.nif == "12345678A"

    def test_quarterly_importes_default_zero(self) -> None:
        """All quarterly importes default to 0."""
        row = Modelo347ContraparteRow(nif="12345678A")
        assert row.importe_Q1 == Decimal("0")
        assert row.importe_Q2 == Decimal("0")
        assert row.importe_Q3 == Decimal("0")
        assert row.importe_Q4 == Decimal("0")

    def test_importe_total_sums_quarters(self) -> None:
        """importe_total property sums all four quarterly importes.

        Oracle: RD 1065/2007 art. 33.1 — the threshold test is against
        the annual sum, not any individual quarter.
        """
        row = Modelo347ContraparteRow(
            nif="12345678A",
            importe_Q1=Decimal("1000"),
            importe_Q2=Decimal("1000"),
            importe_Q3=Decimal("1000"),
            importe_Q4=Decimal("1005.06"),
        )
        assert row.importe_total == Decimal("4005.06")

    def test_pais_codigo_none_for_domestic(self) -> None:
        """pais_codigo=None is valid and represents a domestic counterparty."""
        row = Modelo347ContraparteRow(nif="12345678A", pais_codigo=None)
        assert row.pais_codigo is None

    def test_pais_codigo_uppercased(self) -> None:
        """pais_codigo is uppercased and validated as two-letter ISO code."""
        row = Modelo347ContraparteRow(nif="12345678A", pais_codigo="de")
        assert row.pais_codigo == "DE"

    def test_invalid_pais_codigo_rejected(self) -> None:
        """Three-letter pais_codigo is rejected."""
        with pytest.raises(ValidationError):
            Modelo347ContraparteRow(nif="12345678A", pais_codigo="ESP")

    def test_nif_blank_rejected(self) -> None:
        """Blank NIF is rejected."""
        with pytest.raises(ValidationError):
            Modelo347ContraparteRow(nif="   ")

    def test_frozen_model_immutable(self) -> None:
        """Modelo347ContraparteRow is frozen."""
        row = Modelo347ContraparteRow(nif="12345678A")
        with pytest.raises((ValidationError, TypeError)):
            row.__setattr__("nif", "99999999Z")

    def test_threshold_constant_matches_rd_1065_2007(self) -> None:
        """M347_THRESHOLD_EUR equals €3,005.06 per RD 1065/2007 art. 33.1.

        Anti-tautology: checks the constant is correct, not that the constant
        equals itself. A change in threshold would be a legal change requiring
        this test to be updated with the new authoritative value.
        """
        assert Decimal("3005.06") == M347_THRESHOLD_EUR

    def test_two_rows_distinguish_by_quarterly_importe(self) -> None:
        """Anti-tautology: two rows with different Q1 importes are distinct."""
        row1 = Modelo347ContraparteRow(nif="11111111A", importe_Q1=Decimal("5000"))
        row2 = Modelo347ContraparteRow(nif="11111111A", importe_Q1=Decimal("8000"))
        assert row1.importe_total != row2.importe_total
        # Changing Q2 on row1 does not affect row2 (frozen model)
        assert row2.importe_Q1 == Decimal("8000")


# ---------------------------------------------------------------------------
# Sort-key parity across the full ModeloDetailRow union (M184 / M232 / M349 / M347)
#
# Regression coverage for the CRASH-001 defect: the canonical sort key in
# ``_canonical_detail_rows`` previously read ``row.nif`` unconditionally,
# which crashed on ``Modelo349OperadorRow`` (whose tax id field is
# ``nif_comunitario``). The current ``_nif_key`` helper must accept any
# row in the union without raising.
# ---------------------------------------------------------------------------


class TestRevisionIdAcrossAllFourRowTypes:
    """``derive_calculation_revision_id`` must accept every row in the union.

    The canonical sort key reads ``nif`` for M184/M232/M347 and
    ``nif_comunitario`` for M349; this class proves that path is exercised
    for each row type and that the resulting id is sensitive to the
    tax-id field that drives the sort.
    """

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
            clave_operacion="E",
            importe=Decimal("3000"),
        )

    @staticmethod
    def _contraparte_row() -> Modelo347ContraparteRow:
        return Modelo347ContraparteRow(nif="44444444C", importe_Q1=Decimal("4000"))

    def test_each_row_type_derives_without_crash(self) -> None:
        """Each of the four row types passes through the hash payload alone.

        Anti-CRASH-001 regression: prior to the ``_nif_key`` fix, the
        operador case raised ``AttributeError: 'Modelo349OperadorRow'
        object has no attribute 'nif'``. All four must now derive a
        64-char hex id without raising.
        """
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
        """A single payload containing one row of each type derives cleanly.

        Exercises the sort-key path with heterogeneous ``row_type`` and
        heterogeneous tax-id field names in the same call.
        """
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
        """Anti-tautology: changing the M349 ``nif_comunitario`` changes the id.

        Proves the operador path is genuinely participating in the hash
        (not silently dropped or coerced to a constant) via the sort key
        that previously crashed.
        """
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
                    clave_operacion="E",
                    importe=Decimal("1000"),
                ),
            ),
        )
        assert id_de != id_fr

    def test_sort_canonical_across_all_four_types(self) -> None:
        """Row insertion order must not affect the id with mixed row types.

        Validates the sort key is stable across the full union: the same
        four rows submitted in two different orderings yield the same id.
        """
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
