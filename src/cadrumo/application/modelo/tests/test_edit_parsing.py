"""The edit parser reads each locale's entry grammar, never guesses and never rounds.

Expected readings are written out by hand from each locale's number
conventions (es/ca ``1.234,56``, hu ``1 234,56``, en ``1,234.56``), not taken
from the parser. The typed half is the same function the executor re-applies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.identity.documents import SpanishTaxIdFormat
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_base import CasillaDataType, CasillaSignConstraint
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.filing.schema import ModeloScalar
from ....domain.modelos.codes import ModeloCode
from ...operations.registry import OperationSchemaIdentityV1
from ..edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from ..edit_models import (
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditNormalisation,
    ModeloEditParsedValueV1,
    ModeloEditParseReason,
    ModeloEditParseRefusalV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSchemaIdentityV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from ..edit_parse_text import parse_refusal_text
from ..edit_parsing import ModeloEditParseRequestV1, parse_modelo_edit_lexeme, validate_modelo_edit_value
from ..edit_value_grammar import (
    ModeloEditChoiceV1,
    ModeloEditValueChannel,
    ModeloEditValueFamily,
    ModeloEditValueGrammarV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIGEST = "a" * 64

_MONEY = ModeloEditValueGrammarV1(
    data_type="money",
    family=ModeloEditValueFamily.DECIMAL,
    channel=ModeloEditValueChannel.DECIMAL,
    max_fraction_digits=2,
    money_operand_bound=True,
)
_NON_NEGATIVE_MONEY = _MONEY.model_copy(update={"sign": CasillaSignConstraint.NON_NEGATIVE})
_PERCENT = ModeloEditValueGrammarV1(
    data_type="ratio",
    family=ModeloEditValueFamily.DECIMAL,
    channel=ModeloEditValueChannel.DECIMAL,
    minimum="0",
    maximum="100",
    constraints_declared=True,
)
_INTEGER_MONTHS = ModeloEditValueGrammarV1(
    data_type="integer",
    family=ModeloEditValueFamily.INTEGER,
    channel=ModeloEditValueChannel.DECIMAL,
    max_fraction_digits=0,
    maximum="12",
    constraints_declared=True,
)
_BOOLEAN = ModeloEditValueGrammarV1(
    data_type="boolean", family=ModeloEditValueFamily.BOOLEAN, channel=ModeloEditValueChannel.DECIMAL
)
_DATE = ModeloEditValueGrammarV1(
    data_type="date", family=ModeloEditValueFamily.DATE, channel=ModeloEditValueChannel.UNAVAILABLE
)
_NIF = ModeloEditValueGrammarV1(data_type="nif", family=ModeloEditValueFamily.TEXT, channel=ModeloEditValueChannel.TEXT)
_IBAN = ModeloEditValueGrammarV1(
    data_type="iban", family=ModeloEditValueFamily.TEXT, channel=ModeloEditValueChannel.TEXT
)
_CHOICE = ModeloEditValueGrammarV1(
    data_type="text",
    family=ModeloEditValueFamily.TEXT,
    channel=ModeloEditValueChannel.TEXT,
    choices=(ModeloEditChoiceV1(code="efectivo"), ModeloEditChoiceV1(code="adeudo_en_cuenta")),
    constraints_declared=True,
)
_SHORT_TEXT = ModeloEditValueGrammarV1(
    data_type="text",
    family=ModeloEditValueFamily.TEXT,
    channel=ModeloEditValueChannel.TEXT,
    max_length=4,
    pattern=r"[A-Z]+",
    constraints_declared=True,
)
_RATIO_BINDING = ModeloEditValueGrammarV1(
    data_type="decimal", family=ModeloEditValueFamily.DECIMAL, channel=ModeloEditValueChannel.DECIMAL
)

_GRAMMARS: dict[str, ModeloEditValueGrammarV1] = {
    "01": _MONEY,
    "02": _NON_NEGATIVE_MONEY,
    "03": _PERCENT,
    "04": _INTEGER_MONTHS,
    "05": _BOOLEAN,
    "06": _DATE,
    "07": _NIF,
    "08": _IBAN,
    "09": _CHOICE,
    "10": _SHORT_TEXT,
}
_BINDING = "modelo-999-coeficiente"


def _baseline() -> ModeloEditBaselineV1:
    identity = OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)
    now = datetime.now(UTC)
    return ModeloEditBaselineV1(
        compatibility=ModeloEditCompatibilityTupleV1(
            contract_set_digest=_DIGEST,
            operation_definition_id="modelo.edit.apply",
            definition_contract_digest=_DIGEST,
            request_schema=identity,
            result_schema=identity,
            review_projection_contract_version=None,
            review_schema=None,
            workspace_refresh_target_schema=identity,
            financial_operand_schema=identity,
        ),
        bucket_id="parse-bucket",
        modelo=ModeloCode(Modelo("130").value),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        work_unit_id="b" * 64,
        work_unit_record_digest=_DIGEST,
        calculation_head_digest=_DIGEST,
        current_calculation_revision_id=None,
        law_selected_revision_id="2019-y-siguientes",
        schema_identity=ModeloEditSchemaIdentityV1(
            schema_id="modelo-130-schema", schema_fingerprint=_DIGEST, completeness_manifest_digest=_DIGEST
        ),
        schema_version=1,
        permitted_surface=(
            *(
                ModeloEditWritableScalarSurfaceEntryV1(
                    casilla_id=casilla_id,
                    data_type=CasillaDataType(grammar.data_type),
                    allowed_intents=(ModeloEditScalarIntentKind.SET_TYPED_VALUE,),
                    grammar=grammar,
                )
                for casilla_id, grammar in _GRAMMARS.items()
            ),
            ModeloEditWritableBindingOverrideSurfaceEntryV1(
                binding_id=_BINDING,
                allowed_intents=(ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,),
                grammar=_RATIO_BINDING,
            ),
        ),
        permitted_surface_digest=_DIGEST,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        baseline_id="d" * 64,
    )


@pytest.fixture(scope="module")
def tax_id_format(operation: PinnedAuthorityOperation) -> SpanishTaxIdFormat:
    return runtime_tax_id_format(authority=operation)


def _parse(
    casilla_id: str,
    lexeme: str,
    locale: OutputLanguage,
    tax_id_format: SpanishTaxIdFormat | None = None,
) -> ModeloEditParsedValueV1 | ModeloEditRefusedV1:
    return parse_modelo_edit_lexeme(
        ModeloEditParseRequestV1(
            address=ModeloEditScalarAddressV1(casilla_id=casilla_id), entry_locale=locale, lexeme=lexeme
        ),
        baseline=_baseline(),
        tax_id_format=tax_id_format,
    )


def _value(result: ModeloEditParsedValueV1 | ModeloEditRefusedV1) -> ModeloScalar:
    assert isinstance(result, ModeloEditParsedValueV1), result
    return result.value


def _reason(result: ModeloEditParsedValueV1 | ModeloEditRefusedV1) -> ModeloEditParseReason:
    assert isinstance(result, ModeloEditRefusedV1), result
    assert isinstance(result.refusal, ModeloEditParseRefusalV1)
    return result.refusal.reason


@pytest.mark.parametrize(
    ("locale", "lexeme", "expected"),
    [
        (OutputLanguage.ES, "1.234,56", Decimal("1234.56")),
        (OutputLanguage.ES, "1234,56", Decimal("1234.56")),
        (OutputLanguage.ES, "-12,5", Decimal("-12.5")),
        (OutputLanguage.ES, "1.234.567", Decimal("1234567")),
        (OutputLanguage.CA, "1.234,56", Decimal("1234.56")),
        (OutputLanguage.HU, "12 345,00", Decimal("12345.00")),
        (OutputLanguage.HU, f"12{chr(0x00A0)}345,5", Decimal("12345.5")),
        (OutputLanguage.EN, "1,234.56", Decimal("1234.56")),
        (OutputLanguage.EN, "1234.56", Decimal("1234.56")),
        (OutputLanguage.EN, "0", Decimal("0")),
    ],
)
def test_each_locale_reads_its_own_number_marks(locale: OutputLanguage, lexeme: str, expected: Decimal) -> None:
    assert _value(_parse("01", lexeme, locale)) == expected


def test_the_other_conventions_decimal_mark_is_read_when_it_cannot_be_a_grouping() -> None:
    result = _parse("01", "1234.56", OutputLanguage.ES)

    assert _value(result) == Decimal("1234.56")
    assert isinstance(result, ModeloEditParsedValueV1)
    assert ModeloEditNormalisation.FOREIGN_DECIMAL_MARK_READ in result.normalisations


@pytest.mark.parametrize(
    ("locale", "lexeme", "reason"),
    [
        (OutputLanguage.ES, "1.234", ModeloEditParseReason.AMBIGUOUS_SEPARATOR_READINGS),
        (OutputLanguage.CA, "10.500", ModeloEditParseReason.AMBIGUOUS_SEPARATOR_READINGS),
        (OutputLanguage.EN, "1,234", ModeloEditParseReason.AMBIGUOUS_SEPARATOR_READINGS),
        (OutputLanguage.HU, "1.234", ModeloEditParseReason.AMBIGUOUS_SEPARATOR_READINGS),
        (OutputLanguage.ES, "12.34.5", ModeloEditParseReason.BAD_GROUPING),
        (OutputLanguage.EN, "1,23,456.00", ModeloEditParseReason.BAD_GROUPING),
        (OutputLanguage.ES, "1 234,56", ModeloEditParseReason.BAD_GROUPING),
        (OutputLanguage.ES, "1e3", ModeloEditParseReason.SCIENTIFIC_NOTATION),
        (OutputLanguage.EN, "1.5E+2", ModeloEditParseReason.SCIENTIFIC_NOTATION),
        (OutputLanguage.EN, "NaN", ModeloEditParseReason.NON_FINITE),
        (OutputLanguage.EN, "-Infinity", ModeloEditParseReason.NON_FINITE),
        (OutputLanguage.ES, "+5", ModeloEditParseReason.EXPLICIT_PLUS),
        (OutputLanguage.ES, "doce", ModeloEditParseReason.NOT_A_NUMBER),
        (OutputLanguage.ES, "   ", ModeloEditParseReason.EMPTY),
        (OutputLanguage.EN, "1234.567", ModeloEditParseReason.TOO_MANY_DECIMALS),
        (OutputLanguage.ES, "0,001", ModeloEditParseReason.TOO_MANY_DECIMALS),
        (OutputLanguage.EN, "1000000000000", ModeloEditParseReason.OUT_OF_OPERAND_RANGE),
    ],
)
def test_a_number_that_cannot_be_read_exactly_is_refused_with_its_reason(
    locale: OutputLanguage, lexeme: str, reason: ModeloEditParseReason
) -> None:
    assert _reason(_parse("01", lexeme, locale)) == reason


@pytest.mark.parametrize(
    ("locale", "lexeme", "as_thousands", "as_decimal"),
    [
        (OutputLanguage.ES, "1.234", "1234", "1,234"),
        (OutputLanguage.EN, "1,234", "1234", "1.234"),
        (OutputLanguage.ES, "-1.234", "-1234", "-1,234"),
    ],
)
def test_a_two_way_number_is_refused_naming_both_readings(
    locale: OutputLanguage, lexeme: str, as_thousands: str, as_decimal: str
) -> None:
    result = _parse("01", lexeme, locale)

    assert isinstance(result, ModeloEditRefusedV1)
    assert isinstance(result.refusal, ModeloEditParseRefusalV1)
    assert result.refusal.reason is ModeloEditParseReason.AMBIGUOUS_SEPARATOR_READINGS
    sentence = parse_refusal_text(result.refusal, locale)
    assert as_thousands in sentence
    assert as_decimal in sentence
    assert "{" not in sentence


def test_a_refusal_carries_arguments_never_the_lexeme() -> None:
    result = _parse("01", "1234.567", OutputLanguage.EN)

    assert isinstance(result, ModeloEditRefusedV1)
    assert isinstance(result.refusal, ModeloEditParseRefusalV1)
    assert result.refusal.message_arguments == ("2",)
    assert "1234.567" not in result.model_dump_json()


def test_the_request_never_dumps_or_shows_its_lexeme() -> None:
    request = ModeloEditParseRequestV1(
        address=ModeloEditScalarAddressV1(casilla_id="01"), entry_locale=OutputLanguage.ES, lexeme="4.321,09"
    )

    assert "4.321,09" not in request.model_dump_json()
    assert "4.321,09" not in repr(request)


@pytest.mark.parametrize(
    ("casilla_id", "lexeme", "reason"),
    [
        ("02", "-1", ModeloEditParseReason.NEGATIVE_NOT_ALLOWED),
        ("03", "100,01", ModeloEditParseReason.ABOVE_MAXIMUM),
        ("04", "2,5", ModeloEditParseReason.NOT_AN_INTEGER),
        ("04", "13", ModeloEditParseReason.ABOVE_MAXIMUM),
        ("05", "quizá", ModeloEditParseReason.NOT_A_BOOLEAN),
        ("06", "31/03/2025", ModeloEditParseReason.CHANNEL_UNAVAILABLE),
        ("09", "tarjeta", ModeloEditParseReason.NOT_IN_CHOICES),
        ("10", "ABCDE", ModeloEditParseReason.TOO_LONG),
        ("10", "ab1", ModeloEditParseReason.PATTERN_MISMATCH),
        ("99", "1", ModeloEditParseReason.ADDRESS_NOT_WRITABLE),
    ],
)
def test_declared_constraints_refuse_with_their_reason(
    casilla_id: str, lexeme: str, reason: ModeloEditParseReason
) -> None:
    assert _reason(_parse(casilla_id, lexeme, OutputLanguage.ES)) == reason


def test_ratios_and_fine_decimals_are_not_held_to_the_money_scale() -> None:
    assert _value(_parse("03", "12,125", OutputLanguage.ES)) == Decimal("12.125")
    binding = parse_modelo_edit_lexeme(
        ModeloEditParseRequestV1(
            address=ModeloEditBindingAddressV1(binding_id=_BINDING), entry_locale=OutputLanguage.EN, lexeme="0.1575"
        ),
        baseline=_baseline(),
        tax_id_format=None,
    )
    assert _value(binding) == Decimal("0.1575")


def test_an_integer_written_with_a_zero_fraction_normalises() -> None:
    assert _value(_parse("04", "3,0", OutputLanguage.ES)) == Decimal("3")


@pytest.mark.parametrize(
    ("locale", "lexeme", "expected"),
    [
        (OutputLanguage.ES, "Sí", True),
        (OutputLanguage.CA, "no", False),
        (OutputLanguage.EN, "yes", True),
        (OutputLanguage.HU, "nem", False),
        (OutputLanguage.HU, "igen", True),
        (OutputLanguage.EN, "1", True),
        (OutputLanguage.ES, "0", False),
    ],
)
def test_booleans_read_each_locales_words(locale: OutputLanguage, lexeme: str, expected: bool) -> None:
    assert _value(_parse("05", lexeme, locale)) is expected


def test_a_choice_is_matched_to_its_stored_token() -> None:
    assert _value(_parse("09", " Efectivo ", OutputLanguage.ES)) == "efectivo"


def test_a_nif_is_validated_with_the_governed_format(tax_id_format: SpanishTaxIdFormat) -> None:
    accepted = _parse("07", "12345678-z", OutputLanguage.ES, tax_id_format)

    assert _value(accepted) == "12345678Z"
    assert isinstance(accepted, ModeloEditParsedValueV1)
    assert ModeloEditNormalisation.UPPER_CASED in accepted.normalisations
    assert _reason(_parse("07", "12345678A", OutputLanguage.ES, tax_id_format)) == ModeloEditParseReason.NIF_CHECKSUM
    assert _reason(_parse("07", "1234", OutputLanguage.ES, tax_id_format)) == ModeloEditParseReason.NIF_LENGTH


def test_a_nif_without_the_governed_format_is_refused_not_trusted() -> None:
    assert _reason(_parse("07", "12345678Z", OutputLanguage.ES)) == ModeloEditParseReason.CHANNEL_UNAVAILABLE


def test_an_iban_is_checked_for_shape_and_checksum() -> None:
    assert _value(_parse("08", "es91 2100 0418 4502 0005 1332", OutputLanguage.ES)) == "ES9121000418450200051332"
    assert _reason(_parse("08", "ES91 2100 0418 4502 0005 1333", OutputLanguage.ES)) == (
        ModeloEditParseReason.IBAN_CHECKSUM
    )
    assert _reason(_parse("08", "ES91", OutputLanguage.ES)) == ModeloEditParseReason.IBAN_SHAPE


@pytest.mark.parametrize(
    ("grammar", "value", "expected"),
    [
        (_MONEY, Decimal("12.50"), Decimal("12.50")),
        (_MONEY, "12.50", Decimal("12.50")),
        (_MONEY, 12, Decimal("12")),
        (_PERCENT, "1.234", Decimal("1.234")),
        (_BOOLEAN, True, True),
        (_BOOLEAN, "0", False),
    ],
)
def test_the_typed_half_reads_machine_canonical_values(
    grammar: ModeloEditValueGrammarV1, value: ModeloScalar, expected: ModeloScalar
) -> None:
    outcome = validate_modelo_edit_value(
        value, address=ModeloEditScalarAddressV1(casilla_id="01"), grammar=grammar, tax_id_format=None
    )

    assert isinstance(outcome, ModeloEditParsedValueV1)
    assert outcome.value == expected


@pytest.mark.parametrize(
    ("grammar", "value", "reason"),
    [
        (_MONEY, "1.234,56", ModeloEditParseReason.NOT_A_NUMBER),
        (_MONEY, "NaN", ModeloEditParseReason.NON_FINITE),
        (_MONEY, "1e3", ModeloEditParseReason.SCIENTIFIC_NOTATION),
        (_MONEY, Decimal("0.125"), ModeloEditParseReason.TOO_MANY_DECIMALS),
        (_MONEY, True, ModeloEditParseReason.NOT_A_NUMBER),
        (_BOOLEAN, "2", ModeloEditParseReason.NOT_A_BOOLEAN),
        (_DATE, "2025-03-31", ModeloEditParseReason.CHANNEL_UNAVAILABLE),
        (_CHOICE, 7, ModeloEditParseReason.NOT_TEXT),
    ],
)
def test_the_typed_half_refuses_what_the_engine_would_refuse(
    grammar: ModeloEditValueGrammarV1, value: ModeloScalar, reason: ModeloEditParseReason
) -> None:
    outcome = validate_modelo_edit_value(
        value, address=ModeloEditScalarAddressV1(casilla_id="01"), grammar=grammar, tax_id_format=None
    )

    assert isinstance(outcome, ModeloEditParseRefusalV1)
    assert outcome.reason == reason
