"""A section serves what the last check found about the values of its tables of records, counted as the header counts."""

from __future__ import annotations

from typing import Final

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..work_form_findings import EXPLANATORY_FINDING_MESSAGE_KEYS, ModeloFormAttention
from ..work_form_models import (
    ModeloFormRecordAttention,
    ModeloFormRepeatingBlock,
    ModeloFormSection,
    ModeloWorkForm,
)
from ..work_form_record_attention import record_attention
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEGAL_REF: Final[str] = "ley-37-1992:art-99"
_COUNTRY: Final[str] = "op.codigo-pais"
_NIF_COMUNITARIO: Final[str] = "op.nif-comunitario"


def _missing(casilla_id: str) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.missing_required_casilla",
        message_facts={"casilla_id": casilla_id},
        legal_refs=(_LEGAL_REF,),
    )


def _warning(casilla_id: str) -> ModeloVerificationFinding:
    return _missing(casilla_id).model_copy(
        update={
            "kind": ModeloVerificationFindingKind.RECONCILIATION_MISMATCH,
            "severity": ModeloVerificationFindingSeverity.WARNING,
        }
    )


def _form_349(operation: PinnedAuthorityOperation, findings: tuple[ModeloVerificationFinding, ...]) -> ModeloWorkForm:
    return built_form(operation, "349", operation.supported_filing_years().horizon, "1T", findings=findings)


def _records_section(form: ModeloWorkForm) -> ModeloFormSection:
    return next(
        section
        for page in form.pages
        for section in page.sections
        if any(
            _COUNTRY in block.column_casilla_ids
            for block in section.blocks
            if isinstance(block, ModeloFormRepeatingBlock)
        )
    )


def test_a_section_counts_the_findings_about_its_record_columns_by_level(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    form = _form_349(authority_operation, (_missing(_COUNTRY), _missing(_NIF_COMUNITARIO), _warning(_COUNTRY)))

    assert _records_section(form).record_attention == (
        ModeloFormRecordAttention.counted(ModeloFormAttention.MISSING, 2),
        ModeloFormRecordAttention.counted(ModeloFormAttention.CHECK, 1),
    )
    holding = {
        section.id: section.record_attention
        for page in form.pages
        for section in page.sections
        if any(
            _COUNTRY in block.column_casilla_ids
            for block in section.blocks
            if isinstance(block, ModeloFormRepeatingBlock)
        )
    }
    assert len(holding) > 1, "every 349 table carrying the operator's country counts the finding about it"
    assert set(holding.values()) == {_records_section(form).record_attention}
    assert not any(
        section.record_attention for page in form.pages for section in page.sections if section.id not in holding
    )


def test_a_section_without_findings_about_its_records_counts_none(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    form = _form_349(authority_operation, ())

    assert _records_section(form).record_attention == ()


def test_nothing_is_counted_once_the_declaration_is_recorded_as_filed(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    form = _form_349(authority_operation, (_missing(_COUNTRY), _warning(_COUNTRY)))
    issues = form.issues

    assert record_attention(_records_section(form), issues, recorded=True, applies=True) == ()


def test_a_section_on_a_page_that_does_not_apply_counts_only_what_is_worth_checking(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    form = _form_349(authority_operation, (_missing(_COUNTRY), _warning(_NIF_COMUNITARIO)))

    assert record_attention(_records_section(form), form.issues, recorded=False, applies=False) == (
        ModeloFormRecordAttention.counted(ModeloFormAttention.CHECK, 1),
    )


def test_a_limitation_keeps_its_own_level_and_an_explanation_counts_nowhere(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    limitation = _warning(_COUNTRY).model_copy(update={"disclosed_limitation": True})
    explanation = _warning(_COUNTRY).model_copy(
        update={
            "kind": ModeloVerificationFindingKind.ADVISORY,
            "message_locale_key": next(iter(sorted(EXPLANATORY_FINDING_MESSAGE_KEYS))),
        }
    )
    form = _form_349(authority_operation, (limitation, explanation))

    assert [issue.attention for issue in form.issues] == [ModeloFormAttention.LIMITATION, ModeloFormAttention.INFO]
    assert _records_section(form).record_attention == (
        ModeloFormRecordAttention.counted(ModeloFormAttention.LIMITATION, 1),
    )


@pytest.mark.parametrize(
    ("level", "counts_as", "asks_filer"),
    [
        (ModeloFormAttention.BLOCKS, ModeloFormAttention.BLOCKS, True),
        (ModeloFormAttention.MISSING, ModeloFormAttention.MISSING, True),
        (ModeloFormAttention.CONFIRM, ModeloFormAttention.CONFIRM, True),
        (ModeloFormAttention.CHECK, ModeloFormAttention.CHECK, False),
        (ModeloFormAttention.LIMITATION, ModeloFormAttention.CHECK, False),
    ],
)
def test_each_count_is_served_with_its_place_on_the_section_scale(
    level: ModeloFormAttention, counts_as: ModeloFormAttention, asks_filer: bool
) -> None:
    served = ModeloFormRecordAttention.counted(level, 3)

    assert (served.counts_as, served.asks_filer, served.count) == (counts_as, asks_filer, 3)


def test_a_limitation_on_a_records_table_is_served_as_worth_checking_and_asks_nothing(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    limitation = _warning(_COUNTRY).model_copy(update={"disclosed_limitation": True})
    form = _form_349(authority_operation, (limitation,))

    (served,) = _records_section(form).record_attention
    assert (served.level, served.counts_as, served.asks_filer) == (
        ModeloFormAttention.LIMITATION,
        ModeloFormAttention.CHECK,
        False,
    )


@pytest.mark.parametrize(
    "placement",
    [
        {"level": ModeloFormAttention.LIMITATION, "counts_as": ModeloFormAttention.LIMITATION, "asks_filer": False},
        {"level": ModeloFormAttention.MISSING, "counts_as": ModeloFormAttention.MISSING, "asks_filer": False},
        {"level": ModeloFormAttention.INFO, "counts_as": ModeloFormAttention.CHECK, "asks_filer": False},
    ],
)
def test_a_count_placed_off_its_level_is_refused(placement: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ModeloFormRecordAttention.model_validate({**placement, "count": 1})
