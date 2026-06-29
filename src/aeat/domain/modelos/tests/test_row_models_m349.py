"""Unit tests for Modelo 349 typed row models and NIF-IVA validation."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.errors import AeatError, get_registered_error_code, resolve_error_message
from .._row_models import (
    Modelo349CountryPrefixContextError,
    Modelo349OperadorRow,
    m349_nif_number_for_export,
    validate_m349_country_prefix_context,
    validate_m349_nif_format,
)
from ._row_model_support import (
    _assert_validation_error,
    _BooleanCase,
    _CountryContextCase,
    _ValidationErrorCase,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_M349_INVALID_ROW_CASES = (
    _ValidationErrorCase(
        "missing-razon-social",
        lambda: Modelo349OperadorRow.model_validate(
            {
                "codigo_pais": "DE",
                "nif_comunitario": "DE123456789",
                "clave_operacion": "E",
                "importe": Decimal("1"),
            },
        ),
        "razon_social",
    ),
    _ValidationErrorCase(
        "blank-razon-social",
        lambda: Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="   ",
            clave_operacion="E",
            importe=Decimal("1"),
        ),
        "razon_social",
    ),
    _ValidationErrorCase(
        "negative-importe",
        lambda: Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Entidad DE",
            clave_operacion="E",
            importe=Decimal("-1"),
        ),
        "non-negative",
    ),
    _ValidationErrorCase(
        "lowercase-country",
        lambda: Modelo349OperadorRow(
            codigo_pais="de",
            nif_comunitario="DE123456789",
            razon_social="Entidad DE",
            clave_operacion="E",
            importe=Decimal("1"),
        ),
    ),
    _ValidationErrorCase(
        "invalid-clave",
        lambda: Modelo349OperadorRow.model_validate(
            {
                "codigo_pais": "DE",
                "nif_comunitario": "DE123456789",
                "razon_social": "Entidad DE",
                "clave_operacion": "Z",
                "importe": Decimal("1"),
            },
        ),
    ),
)

_M349_NIF_FORMAT_CASES = (
    _BooleanCase("valid-de", "DE123456789", "DE", True),
    _BooleanCase("de-too-short", "DE12345678", "DE", False),
    _BooleanCase("valid-fr", "FR12345678901", "FR", True),
    _BooleanCase("valid-it", "IT12345678901", "IT", True),
    _BooleanCase("valid-nl", "NL123456789B01", "NL", True),
    _BooleanCase("valid-el", "EL123456789", "EL", True),
    _BooleanCase("valid-xi", "XI123456789", "XI", True),
    _BooleanCase("unknown-country", "XX12345", "XX", False),
    _BooleanCase("unknown-country-badvat", "BADVAT", "ZZ", False),
    _BooleanCase("supported-country-too-short", "EL1", "EL", False),
    _BooleanCase("de-rejects-fr-shape", "FR12345678901", "DE", False),
)

_M349_CONTEXT_ALLOWED_CASES = (
    _CountryContextCase(
        "xi-goods-2025",
        lambda: validate_m349_country_prefix_context(
            country_code="XI",
            clave_operacion="E",
            filing_year=2025,
            period="4T",
        ),
    ),
    _CountryContextCase(
        "gb-first-2021-transition-goods",
        lambda: validate_m349_country_prefix_context(
            country_code="GB",
            clave_operacion="E",
            filing_year=2021,
            period="1T",
        ),
    ),
    _CountryContextCase(
        "gb-pre-2021-rectification",
        lambda: validate_m349_country_prefix_context(
            country_code="GB",
            clave_operacion="S",
            filing_year=2025,
            period="4T",
            is_rectification=True,
            rectified_year=2020,
            rectified_period="4T",
        ),
    ),
)

_M349_CONTEXT_REJECTED_CASES = (
    _CountryContextCase(
        "xi-services",
        lambda: validate_m349_country_prefix_context(
            country_code="XI",
            clave_operacion="S",
            filing_year=2025,
            period="4T",
        ),
        "service keys",
    ),
    _CountryContextCase(
        "gb-ordinary-2025",
        lambda: validate_m349_country_prefix_context(
            country_code="GB",
            clave_operacion="E",
            filing_year=2025,
            period="4T",
        ),
        "post-transition",
        "AEAT Brexit IVA NIF-IVA",
    ),
)


class TestModelo349OperadorRow:
    def test_valid_operador_row_round_trips(self) -> None:
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
        row = Modelo349OperadorRow(
            codigo_pais="FR",
            nif_comunitario="fr12345678901",
            razon_social="France SARL",
            clave_operacion="S",
            importe=Decimal("1"),
        )
        assert row.nif_comunitario == "FR12345678901"

    def test_importe_zero_is_valid(self) -> None:
        row = Modelo349OperadorRow(
            codigo_pais="PT",
            nif_comunitario="PT123456789",
            razon_social="Portugal LDA",
            clave_operacion="T",
            importe=Decimal("0"),
        )
        assert row.importe == Decimal("0")

    @pytest.mark.parametrize("case", _M349_INVALID_ROW_CASES, ids=lambda case: case.case_id)
    def test_invalid_operador_rows_rejected(self, case: _ValidationErrorCase) -> None:
        _assert_validation_error(case)

    def test_frozen_model_immutable(self) -> None:
        row = Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Deutschland GmbH",
            clave_operacion="E",
            importe=Decimal("1"),
        )
        with pytest.raises((ValidationError, TypeError)):
            row.__setattr__("codigo_pais", "FR")

    def test_two_rows_distinguish_by_importe(self) -> None:
        row1 = Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Deutschland GmbH",
            clave_operacion="E",
            importe=Decimal("50000"),
        )
        row2 = Modelo349OperadorRow(
            codigo_pais="FR",
            nif_comunitario="FR12345678901",
            razon_social="France SARL",
            clave_operacion="S",
            importe=Decimal("30000"),
        )
        assert row1.importe != row2.importe
        row1_modified = Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Deutschland GmbH",
            clave_operacion="E",
            importe=Decimal("75000"),
        )
        assert row1_modified.importe == Decimal("75000")
        assert row2.importe == Decimal("30000")


class TestValidateM349NifFormat:
    @pytest.mark.parametrize("case", _M349_NIF_FORMAT_CASES, ids=lambda case: case.case_id)
    def test_country_specific_nif_formats(self, case: _BooleanCase) -> None:
        assert validate_m349_nif_format(case.nif, case.pais) is case.expected


class TestValidateM349CountryPrefixContext:
    @pytest.mark.parametrize("case", _M349_CONTEXT_ALLOWED_CASES, ids=lambda case: case.case_id)
    def test_allowed_country_prefix_contexts(self, case: _CountryContextCase) -> None:
        case.call()

    @pytest.mark.parametrize("case", _M349_CONTEXT_REJECTED_CASES, ids=lambda case: case.case_id)
    def test_rejected_country_prefix_contexts(self, case: _CountryContextCase) -> None:
        assert case.match is not None
        with pytest.raises(Modelo349CountryPrefixContextError) as exc:
            case.call()
        assert isinstance(exc.value, AeatError)
        assert isinstance(exc.value, ValueError)
        code = get_registered_error_code(exc.value)
        assert code.code == "REFUSED_MODELO_349_COUNTRY_PREFIX_CONTEXT"
        message = resolve_error_message(exc.value)
        assert "Modelo 349" in message
        assert "AEAT Brexit IVA NIF-IVA" in message
        assert case.match in message
        if case.must_contain is not None:
            assert case.must_contain in message


class TestM349NifNumberForExport:
    def test_strips_country_prefix_for_boe_nif_subfield(self) -> None:
        assert m349_nif_number_for_export("DE123456789", "DE") == "123456789"
        assert m349_nif_number_for_export("FR12345678901", "FR") == "12345678901"

    def test_rejects_invalid_or_mismatched_prefixed_nif(self) -> None:
        with pytest.raises(ValueError, match="expected NIF-IVA format"):
            m349_nif_number_for_export("FR12345678901", "DE")
