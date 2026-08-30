"""Unit tests for Modelo 349 typed row models and NIF-IVA validation."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import IntracomOperationType
from ....core.errors import CadrumoError, get_registered_error_code, resolve_error_message
from ..row_models import (
    Modelo349CountryPrefixContextError,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
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

_M349_INVALID_RECTIFICATION_ROW_CASES = (
    _ValidationErrorCase(
        "negative-base-rectificada",
        lambda: Modelo349RectificacionRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Entidad DE",
            clave_operacion="E",
            ejercicio="2025",
            periodo="2T",
            base_rectificada=Decimal("-1"),
            base_anterior=Decimal("1000"),
        ),
        "non-negative",
    ),
    _ValidationErrorCase(
        "negative-base-anterior",
        lambda: Modelo349RectificacionRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Entidad DE",
            clave_operacion="E",
            ejercicio="2025",
            periodo="2T",
            base_rectificada=Decimal("1100"),
            base_anterior=Decimal("-1"),
        ),
        "non-negative",
    ),
    _ValidationErrorCase(
        "invalid-ejercicio",
        lambda: Modelo349RectificacionRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Entidad DE",
            clave_operacion="E",
            ejercicio="20A5",
            periodo="2T",
            base_rectificada=Decimal("1100"),
            base_anterior=Decimal("1000"),
        ),
        "four-digit year",
    ),
    _ValidationErrorCase(
        "invalid-periodo",
        lambda: Modelo349RectificacionRow.model_validate(
            {
                "codigo_pais": "DE",
                "nif_comunitario": "DE123456789",
                "razon_social": "Entidad DE",
                "clave_operacion": "E",
                "ejercicio": "2025",
                "periodo": "13",
                "base_rectificada": Decimal("1100"),
                "base_anterior": Decimal("1000"),
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
    # Belgium accepts both the historical '0' lead digit and the '1' lead digit
    # used for newer registrations since 2007 (VIES structure rule), routed
    # through the canonical core NIF_IVA_FORMATS authority.
    _BooleanCase("valid-be-legacy-zero-lead", "BE0123456789", "BE", True),
    _BooleanCase("valid-be-modern-one-lead", "BE1234567890", "BE", True),
    _BooleanCase("be-rejects-other-lead-digit", "BE9123456789", "BE", False),
    # Ireland accepts the two-letter suffix form and the '+'/'*' second-block
    # variants documented by VIES, routed through the core authority.
    _BooleanCase("valid-ie-two-letter-suffix", "IE1234567TW", "IE", True),
    _BooleanCase("valid-ie-plus-block", "IE1+23456W", "IE", True),
    # Cyprus is 8 digits + 1 trailing letter per the VIES structure rule; the
    # core authority enforces this exact shape (a bare 9-character alphanumeric
    # body, as the pre-migration Modelo 349 pattern allowed, is not a valid
    # Cypriot NIF-IVA and must be rejected).
    _BooleanCase("valid-cy", "CY12345678L", "CY", True),
    _BooleanCase("cy-rejects-all-digit-body", "CY123456789", "CY", False),
    _BooleanCase("cy-rejects-non-terminal-letter", "CY1234567L8", "CY", False),
    # GB retains its own Modelo 349 Brexit-transition pattern (post-Brexit UK
    # carries no entry in the general EU NIF-IVA authority).
    _BooleanCase("valid-gb-nine-digit", "GB123456789", "GB", True),
    _BooleanCase("valid-gb-government-department", "GBGD001", "GB", True),
    _BooleanCase("gb-rejects-bad-shape", "GB12345", "GB", False),
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

    def test_current_intracom_operation_claves_are_accepted(self) -> None:
        for operation_type in IntracomOperationType:
            row = Modelo349OperadorRow(
                codigo_pais="DE",
                nif_comunitario="DE123456789",
                razon_social="Deutschland GmbH",
                clave_operacion=operation_type.value,
                importe=Decimal("1"),
            )

            assert row.clave_operacion == operation_type.value, operation_type.value

    def test_invalid_operador_rows_rejected(self) -> None:
        for case in _M349_INVALID_ROW_CASES:
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


class TestModelo349RectificacionRow:
    def test_valid_rectification_row_round_trips(self) -> None:
        row = Modelo349RectificacionRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Deutschland GmbH",
            clave_operacion="E",
            ejercicio="2025",
            periodo="2T",
            base_rectificada=Decimal("1100.00"),
            base_anterior=Decimal("1000.00"),
        )

        assert row.row_type == "rectificacion"
        assert row.codigo_pais == "DE"
        assert row.nif_comunitario == "DE123456789"
        assert row.razon_social == "Deutschland GmbH"
        assert row.clave_operacion == "E"
        assert row.ejercicio == "2025"
        assert row.periodo == "2T"
        assert row.base_rectificada == Decimal("1100.00")
        assert row.base_anterior == Decimal("1000.00")

    def test_periodo_is_uppercased_before_closed_set_validation(self) -> None:
        row = Modelo349RectificacionRow.model_validate(
            {
                "codigo_pais": "DE",
                "nif_comunitario": "DE123456789",
                "razon_social": "Deutschland GmbH",
                "clave_operacion": "E",
                "ejercicio": "2025",
                "periodo": "2t",
                "base_rectificada": Decimal("1100.00"),
                "base_anterior": Decimal("1000.00"),
            },
        )

        assert row.periodo == "2T"

    def test_current_intracom_operation_claves_are_accepted(self) -> None:
        for operation_type in IntracomOperationType:
            row = Modelo349RectificacionRow(
                codigo_pais="DE",
                nif_comunitario="DE123456789",
                razon_social="Deutschland GmbH",
                clave_operacion=operation_type.value,
                ejercicio="2025",
                periodo="2T",
                base_rectificada=Decimal("1100.00"),
                base_anterior=Decimal("1000.00"),
            )

            assert row.clave_operacion == operation_type.value, operation_type.value

    def test_invalid_rectification_rows_rejected(self) -> None:
        for case in _M349_INVALID_RECTIFICATION_ROW_CASES:
            _assert_validation_error(case)


class TestValidateM349NifFormat:
    def test_country_specific_nif_formats(self) -> None:
        for case in _M349_NIF_FORMAT_CASES:
            assert validate_m349_nif_format(case.nif, case.pais) is case.expected, case.case_id


class TestValidateM349CountryPrefixContext:
    def test_allowed_country_prefix_contexts(self) -> None:
        for case in _M349_CONTEXT_ALLOWED_CASES:
            case.call()

    def test_rejected_country_prefix_contexts(self) -> None:
        for case in _M349_CONTEXT_REJECTED_CASES:
            assert case.match is not None, case.case_id
            with pytest.raises(Modelo349CountryPrefixContextError) as exc:
                case.call()
            assert isinstance(exc.value, CadrumoError), case.case_id
            assert isinstance(exc.value, ValueError), case.case_id
            code = get_registered_error_code(exc.value)
            assert code.code == "REFUSED_MODELO_349_COUNTRY_PREFIX_CONTEXT", case.case_id
            message = resolve_error_message(exc.value)
            assert "Modelo 349" in message, case.case_id
            assert "AEAT Brexit IVA NIF-IVA" in message, case.case_id
            assert case.match in message, case.case_id
            if case.must_contain is not None:
                assert case.must_contain in message, case.case_id


class TestM349NifNumberForExport:
    def test_strips_country_prefix_for_boe_nif_subfield(self) -> None:
        assert m349_nif_number_for_export("DE123456789", "DE") == "123456789"
        assert m349_nif_number_for_export("FR12345678901", "FR") == "12345678901"

    def test_rejects_invalid_or_mismatched_prefixed_nif(self) -> None:
        with pytest.raises(ValueError, match="expected NIF-IVA format"):
            m349_nif_number_for_export("FR12345678901", "DE")
