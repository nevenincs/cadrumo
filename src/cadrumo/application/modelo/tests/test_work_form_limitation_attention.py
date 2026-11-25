"""A finding that discloses a limitation of the calculation has its own level on the attention scale.

The level comes from the finding's own marker and from nothing else: the same message without
the marker stays an ordinary check. The form's counts, its issue lines and the header's words
account the level apart from checks, in every language the product speaks.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ..work_form_findings import ModeloFormAttention, ModeloFormIssue, finding_attention
from ..work_form_header import attention_counts
from ..work_form_issue_lines import form_issue_lines
from ..work_form_models import ModeloWorkForm
from ..work_form_next_step import check_count, limitation_count
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LIMITATION_KEY = "application.modelo.findings.trabajo_deduction_not_computed"
_CHIP_KEY = "workspace.modelo.header.chip.limitation"
_YEAR = filing_year_envelope().horizon
_LEGAL_REF = "ley-35-2006:art-19"
_LANGUAGES = tuple(OutputLanguage)


def _advisory(*, disclosed: bool, key: str = _LIMITATION_KEY) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key=key,
        legal_refs=(_LEGAL_REF,),
        disclosed_limitation=disclosed,
    )


def _with_issues(form: ModeloWorkForm, *findings: ModeloVerificationFinding) -> ModeloWorkForm:
    return form.model_copy(
        update={
            "verification": VerificationCompletenessStatus.COMPLETE,
            "issues": tuple(ModeloFormIssue(finding=finding) for finding in findings),
        }
    )


def test_the_marker_alone_decides_the_level() -> None:
    marked = _advisory(disclosed=True)
    unmarked = _advisory(disclosed=False)

    assert finding_attention(marked) is ModeloFormAttention.LIMITATION
    assert finding_attention(unmarked) is ModeloFormAttention.CHECK
    assert ModeloFormIssue(finding=marked).attention is ModeloFormAttention.LIMITATION
    assert ModeloFormIssue(finding=unmarked).attention is ModeloFormAttention.CHECK


def test_the_marker_outranks_the_explanatory_set_and_never_touches_what_blocks_or_is_missing() -> None:
    explanatory = "application.modelo.findings.cross_period_zero_value_previous_filing"
    assert finding_attention(_advisory(disclosed=False, key=explanatory)) is ModeloFormAttention.INFO
    assert finding_attention(_advisory(disclosed=True, key=explanatory)) is ModeloFormAttention.LIMITATION

    blocking = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key=_LIMITATION_KEY,
        legal_refs=(_LEGAL_REF,),
    )
    missing = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key=_LIMITATION_KEY,
        legal_refs=(_LEGAL_REF,),
    )
    assert finding_attention(blocking) is ModeloFormAttention.BLOCKS
    assert finding_attention(missing) is ModeloFormAttention.MISSING


def test_an_issue_cannot_claim_a_level_its_finding_does_not_derive_to() -> None:
    with pytest.raises(ValidationError, match="attention must be the one its finding classifies to"):
        ModeloFormIssue(finding=_advisory(disclosed=True), attention=ModeloFormAttention.CHECK)
    with pytest.raises(ValidationError, match="attention must be the one its finding classifies to"):
        ModeloFormIssue(finding=_advisory(disclosed=False), attention=ModeloFormAttention.LIMITATION)


def test_the_scale_orders_the_level_after_checks_and_before_information() -> None:
    order = tuple(ModeloFormAttention)

    assert order.index(ModeloFormAttention.CHECK) < order.index(ModeloFormAttention.LIMITATION)
    assert order.index(ModeloFormAttention.LIMITATION) < order.index(ModeloFormAttention.INFO)


@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_counts_keep_limitations_apart_from_checks_in_the_forms_language(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    form = _with_issues(
        built_form(operation, "100", _YEAR, "0A", language=language),
        _advisory(disclosed=True),
        _advisory(disclosed=False),
        _advisory(disclosed=False, key="application.modelo.findings.dt12a_reduccion_possible"),
    )

    counts = {count.level: count for count in attention_counts(form, language, recorded=False)}

    assert limitation_count(form) == 1
    assert check_count(form) == 2
    assert counts[ModeloFormAttention.LIMITATION].count == 1
    assert counts[ModeloFormAttention.CHECK].count == 2
    assert counts[ModeloFormAttention.LIMITATION].words == tr(_CHIP_KEY, count=1, locale=language.value)
    assert counts[ModeloFormAttention.LIMITATION].words != counts[ModeloFormAttention.CHECK].words
    assert "{count}" not in counts[ModeloFormAttention.LIMITATION].words


def test_the_chip_words_differ_in_every_language() -> None:
    words = {language: tr(_CHIP_KEY, count=3, locale=language.value) for language in _LANGUAGES}

    assert len(set(words.values())) == len(_LANGUAGES)
    assert all("3" in text and "{count}" not in text and "%{" not in text for text in words.values())


def test_no_count_is_made_for_a_form_without_a_limitation(operation: PinnedAuthorityOperation) -> None:
    form = _with_issues(built_form(operation, "100", _YEAR, "0A"), _advisory(disclosed=False))

    levels = {count.level for count in attention_counts(form, OutputLanguage.EN, recorded=False)}

    assert ModeloFormAttention.LIMITATION not in levels
    assert limitation_count(form) == 0


def test_the_issue_lines_carry_the_level_after_the_checks(operation: PinnedAuthorityOperation) -> None:
    form = _with_issues(
        built_form(operation, "100", _YEAR, "0A"),
        _advisory(disclosed=True),
        _advisory(disclosed=False, key="application.modelo.findings.dt12a_reduccion_possible"),
    )

    lines = form_issue_lines(form, OutputLanguage.EN)

    assert [line.level for line in lines] == [ModeloFormAttention.CHECK, ModeloFormAttention.LIMITATION]
