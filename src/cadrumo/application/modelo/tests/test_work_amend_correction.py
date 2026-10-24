"""A correction of a filed declaration lists the wizard's boxes, in words, and reads corrected values as it does.

Driven over the published registry: the rows, kinds and motives come from the
same producers the amendment context executor calls. Expected figures are
written from each language's number conventions, and the accepted corrected
values are checked against the amendment request's own override shape, the
independent contract the command-line wizard's values must satisfy. All data
is synthetic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ....core.decimal.grammar import try_parse_canonical_decimal
from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.amendment_regime_policy import permitted_amendment_kind_values_for_period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind, M303RectificativaMotive
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    derive_filing_record_id,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..edit_models import (
    ModeloEditCorrectionAddressV1,
    ModeloEditParsedValueV1,
    ModeloEditParseReason,
    ModeloEditParseRequestV1,
    ModeloEditRefusedV1,
)
from ..edit_parsing import parse_modelo_edit_lexeme, validate_modelo_edit_value
from ..registry_discovery import registry_casillas_for_registry_scope
from ..work_amend_contracts import ModeloWorkAmendOverride
from ..work_amend_correction import (
    ModeloAmendmentCorrectionContextV1,
    amendable_casilla_rows,
    correction_value_grammars,
    worded_amendment_context,
)
from ..work_form_service import modelo_form_snapshot
from .test_edit_parsing import _baseline

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = "5aa00000-0000-4000-8000-0000000000aa"
_FILED_AT = datetime(2026, 4, 18, 9, 0, tzinfo=UTC)
_FILED = {"01": Decimal("1000.00"), "02": Decimal("250.00")}


def _unit_and_record(operation: PinnedAuthorityOperation, modelo: str, code: str) -> tuple[WorkUnit, ModeloRecord]:
    period = Period.from_year_and_code(2026, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=2026, period=period.registry_token).id)
    unit_id = derive_work_unit_id(
        bucket_id=_PROFILE, modelo=modelo, filing_year=2026, period=period, revision_id=revision_id
    )
    head = "a" * 64
    filing_id = derive_filing_record_id(work_unit_id=unit_id, calculation_revision_id=head, filed_by="synthetic")
    unit = WorkUnit(
        work_unit_id=unit_id,
        bucket_id=_PROFILE,
        modelo=modelo,
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name="Synthetic return",
        created_at=_FILED_AT,
        updated_at=_FILED_AT,
        current_calculation_revision_id=head,
        filed_calculation_revision_id=head,
        current_filing_record_id=filing_id,
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=unit_id,
        calculation_revision_id=head,
        bucket_id=_PROFILE,
        modelo=modelo,
        filing_year=2026,
        period=period,
        filed_at=_FILED_AT,
        filed_by="synthetic",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    return unit, record


def _context(
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
    *,
    modelo: str = "130",
    code: str = "1T",
    motive_applicable: bool = False,
) -> ModeloAmendmentCorrectionContextV1:
    unit, record = _unit_and_record(operation, modelo, code)
    with validating_governed_facts(operation):
        permitted = permitted_amendment_kind_values_for_period(modelo, unit.period)
    rows = registry_casillas_for_registry_scope(
        modelo, filing_year=2026, period=unit.period.registry_token, operation=operation
    ).rows
    return worded_amendment_context(
        record=record,
        unit=unit,
        snapshot=modelo_form_snapshot(operation, unit.modelo, 2026, unit.period, unit.revision_id),
        casilla_rows=rows,
        filed_values=_FILED,
        permitted_kinds=tuple(kind for kind in CalculationRevisionAmendmentKind if kind.value in permitted),
        motive_applicable=motive_applicable,
        language=language,
    )


def test_the_correction_lists_the_boxes_the_wizard_lists_with_their_filed_figures(
    operation: PinnedAuthorityOperation,
) -> None:
    rows = registry_casillas_for_registry_scope("130", filing_year=2026, period="1T", operation=operation).rows
    spanish = _context(operation, OutputLanguage.ES)
    english = _context(operation, OutputLanguage.EN)

    wizard_boxes = tuple(row.casilla_id for row in amendable_casilla_rows(rows, _FILED))
    assert tuple(row.casilla_id for row in spanish.rows) == wizard_boxes == ("01", "02")
    first_es, first_en = spanish.rows[0], english.rows[0]
    assert (first_es.filed_value, first_en.filed_value) == ("1000", "1000")
    assert "1.000,00" in first_es.filed_value_text and "1,000.00" in first_en.filed_value_text
    assert first_es.label != first_en.label
    assert first_es.edit_address == ModeloEditCorrectionAddressV1(casilla_id=validated_casilla_id("01"))
    assert spanish.filed.filing_record_id == english.filed.filing_record_id
    assert spanish.filed.period_words != english.filed.period_words


def test_the_kinds_are_the_period_permits_each_worded_and_motives_only_where_they_apply(
    operation: PinnedAuthorityOperation,
) -> None:
    plain = _context(operation, OutputLanguage.EN)
    spanish = _context(operation, OutputLanguage.ES)
    m303 = _context(operation, OutputLanguage.ES, modelo="303", code="1T", motive_applicable=True)
    m303_unknown = _context(operation, OutputLanguage.ES, modelo="303", code="1T", motive_applicable=False)

    with validating_governed_facts(operation):
        permitted = permitted_amendment_kind_values_for_period("130", Period.from_year_and_code(2026, "1T"))
    assert {option.kind.value for option in plain.kinds} == permitted
    for english, spanish_option in zip(plain.kinds, spanish.kinds, strict=True):
        assert english.help != spanish_option.help
        assert english.words and english.help
    assert not plain.motive_applies and plain.motives == () and plain.motive_help is None
    assert m303.motive_applies and m303.motive_kind is CalculationRevisionAmendmentKind.RECTIFICATIVA
    assert tuple(option.motive for option in m303.motives) == tuple(M303RectificativaMotive)
    assert m303.motive_help is not None
    assert not m303_unknown.motive_applies and m303_unknown.motives == ()
    assert plain.reason_prompt != spanish.reason_prompt


def _read(operation: PinnedAuthorityOperation, text: str, language: OutputLanguage, *, casilla: str = "01"):
    snapshot = modelo_form_snapshot(
        operation, _baseline().modelo, 2025, Period.from_year_and_code(2025, "1T"), "2019-y-siguientes"
    )
    return parse_modelo_edit_lexeme(
        ModeloEditParseRequestV1(
            address=ModeloEditCorrectionAddressV1(casilla_id=validated_casilla_id(casilla)),
            entry_locale=language,
            lexeme=text,
        ),
        baseline=_baseline(),
        tax_id_format=None,
        correction_grammars=correction_value_grammars(snapshot),
    )


@pytest.mark.parametrize(
    ("text", "language", "expected"),
    [
        ("1.100,50", OutputLanguage.ES, Decimal("1100.50")),
        ("1,100.50", OutputLanguage.EN, Decimal("1100.50")),
        ("1 100,50", OutputLanguage.HU, Decimal("1100.50")),
        ("-12,125", OutputLanguage.CA, Decimal("-12.125")),
    ],
)
def test_a_corrected_value_reads_in_the_filers_language(
    operation: PinnedAuthorityOperation, text: str, language: OutputLanguage, expected: Decimal
) -> None:
    outcome = _read(operation, text, language)

    assert isinstance(outcome, ModeloEditParsedValueV1)
    assert outcome.value == expected


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("1,1234567", ModeloEditParseReason.TOO_MANY_DECIMALS),
        ("1000000000000000", ModeloEditParseReason.ABOVE_MAXIMUM),
        ("doce", ModeloEditParseReason.NOT_A_NUMBER),
    ],
)
def test_a_corrected_value_the_amendment_would_refuse_is_refused(
    operation: PinnedAuthorityOperation, text: str, reason: ModeloEditParseReason
) -> None:
    outcome = _read(operation, text, OutputLanguage.ES)

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert outcome.refusal.reason is reason


def test_a_correction_entry_without_its_revisions_grammars_is_not_writable() -> None:
    outcome = parse_modelo_edit_lexeme(
        ModeloEditParseRequestV1(
            address=ModeloEditCorrectionAddressV1(casilla_id=validated_casilla_id("01")),
            entry_locale=OutputLanguage.ES,
            lexeme="1",
        ),
        baseline=_baseline(),
        tax_id_format=None,
    )

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert outcome.refusal.reason is ModeloEditParseReason.ADDRESS_NOT_WRITABLE


@pytest.mark.parametrize(
    "text",
    ["0", "1100", "-1100.5", "0.000001", "0.0000001", "999999999999999.999999", "1000000000000000", "-0"],
)
def test_the_correction_grammar_accepts_exactly_what_the_amendment_override_accepts(
    operation: PinnedAuthorityOperation, text: str
) -> None:
    """The wizard's canonical amounts and the override shape agree with the one correction grammar."""
    snapshot = modelo_form_snapshot(
        operation, _baseline().modelo, 2025, Period.from_year_and_code(2025, "1T"), "2019-y-siguientes"
    )
    grammar = correction_value_grammars(snapshot)[validated_casilla_id("01")]
    amount = try_parse_canonical_decimal(text)
    assert amount is not None
    try:
        ModeloWorkAmendOverride(casilla_id="01", value=text)
        override_accepts = True
    except ValidationError:
        override_accepts = False

    outcome = validate_modelo_edit_value(
        amount,
        address=ModeloEditCorrectionAddressV1(casilla_id=validated_casilla_id("01")),
        grammar=grammar,
        tax_id_format=None,
    )

    assert isinstance(outcome, ModeloEditParsedValueV1) is override_accepts
