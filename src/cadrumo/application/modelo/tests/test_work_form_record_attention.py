"""A section serves what the last check found about the values of its tables of records, counted as the header counts."""

from __future__ import annotations

from typing import Final

import pytest

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
        ModeloFormRecordAttention(level=ModeloFormAttention.MISSING, count=2),
        ModeloFormRecordAttention(level=ModeloFormAttention.CHECK, count=1),
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
        ModeloFormRecordAttention(level=ModeloFormAttention.CHECK, count=1),
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
        ModeloFormRecordAttention(level=ModeloFormAttention.LIMITATION, count=1),
    )
