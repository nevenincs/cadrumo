"""Per-check branch coverage for wizard._verifier.

`_verifier` runs five sub-checks through `verify_setup_answers`. The
existing `test_verifier.py` covers the finding-name ordering, the
happy-path OK shape, and one WARNING branch (obligations). This
module adds focused per-branch tests that pin each check's OK
message_key alongside its severity, and pins the reachable
WARNING / OK branches of `obligations_consistency`.

Note on dead-code branches: `_check_tax_id_present`,
`_check_activity_present`, `_check_spouse_consistency`, and
`_check_eu_eea_country_consistency` carry ERROR branches that are
defense-in-depth duplicates of `SetupAnswers`'s own field-level and
model-validator constraints (tax_id min_length=1, activity
min_length=1, spouse_tax_id required when joint taxation,
eu_eea_country required when EU/EEA-resident). Testing those
branches would require bypassing schema validation via
`model_construct` — the project rule "don't write tests for
scenarios that can't happen" applies, so those branches are
exercised only by the schema's own validators (which are themselves
covered elsewhere). Tests here pin only reachable branches.
"""

from __future__ import annotations

import pytest

from ....core.setup_answers import SetupAnswers
from ....domain.contribuyente._ccaa import CCAA
from ....domain.deadlines._models import IVARegime
from .._verifier import (
    WizardCheckFinding,
    WizardCheckSeverity,
    verify_setup_answers,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _individual_answers(**overrides: object) -> SetupAnswers:
    defaults: dict[str, object] = {
        "tax_id": "12345678Z",
        "activity": "software",
        "iva_regime": IVARegime.GENERAL,
        "tax_residence_ccaa": CCAA.MADRID,
    }
    defaults.update(overrides)
    return SetupAnswers.model_validate(defaults)


def _finding(answers: SetupAnswers, name: str) -> WizardCheckFinding:
    report = verify_setup_answers(answers)
    return next(item for item in report.findings if item.name == name)


# ---------------------------------------------------------------------------
# spouse_consistency — OK branches only (ERROR branch is dead code, mirrored
# by SetupAnswers' model_validator that already raises before _verifier runs)
# ---------------------------------------------------------------------------


def test_spouse_consistency_ok_when_joint_with_spouse_tax_id() -> None:
    """Joint taxation with a non-empty spouse_tax_id satisfies the
    check; the OK message_key is emitted."""
    answers = _individual_answers(taxation_type="2", spouse_tax_id="87654321B")

    finding = _finding(answers, "spouse_consistency")

    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.spouse_consistency_ok"


def test_spouse_consistency_ok_when_not_joint() -> None:
    """Individual taxation (taxation_type='1' or empty) skips the
    spouse-tax-id requirement entirely; emits the OK message_key."""
    answers = _individual_answers(taxation_type="1", spouse_tax_id="")

    finding = _finding(answers, "spouse_consistency")

    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.spouse_consistency_ok"


# ---------------------------------------------------------------------------
# eu_eea_country_consistency — OK branches only (ERROR branch is dead code,
# mirrored by SetupAnswers' model_validator)
# ---------------------------------------------------------------------------


def test_eu_eea_country_consistency_ok_when_resident_with_country() -> None:
    answers = _individual_answers(spouse_eu_eea_resident=True, spouse_eu_eea_country="FR")

    finding = _finding(answers, "eu_eea_country_consistency")

    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.eu_eea_country_ok"


def test_eu_eea_country_consistency_ok_when_not_resident() -> None:
    """`spouse_eu_eea_resident=False` skips the country requirement
    entirely, regardless of whether spouse_eu_eea_country is set."""
    answers = _individual_answers(spouse_eu_eea_resident=False, spouse_eu_eea_country="")

    finding = _finding(answers, "eu_eea_country_consistency")

    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.eu_eea_country_ok"


# ---------------------------------------------------------------------------
# obligations_consistency — both reachable branches (no schema-level mirror)
# ---------------------------------------------------------------------------


def test_obligations_consistency_warning_message_key_is_pinned() -> None:
    """The existing test_verifier covers the WARNING severity; this
    test pins the matching message_key so a per-branch i18n key
    regression surfaces immediately."""
    answers = _individual_answers(
        professional_income_withholding_ge_70pct=True,
        pays_professionals_with_retencion=False,
    )

    finding = _finding(answers, "obligations_consistency")

    assert finding.severity is WizardCheckSeverity.WARNING
    assert finding.message_key == "wizard.setup.verifier.obligations_inconsistent"


def test_obligations_consistency_ok_when_neither_flag_set() -> None:
    """The default SetupAnswers shape — both flags False — satisfies
    the check; the OK message_key is emitted."""
    answers = _individual_answers()

    finding = _finding(answers, "obligations_consistency")

    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.obligations_consistency_ok"


def test_obligations_consistency_ok_when_pays_professionals_set() -> None:
    """Having `pays_professionals_with_retencion=True` while
    `professional_income_withholding_ge_70pct=True` satisfies the
    check (no inconsistency — both obligations are active)."""
    answers = _individual_answers(
        professional_income_withholding_ge_70pct=True,
        pays_professionals_with_retencion=True,
    )

    finding = _finding(answers, "obligations_consistency")

    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.obligations_consistency_ok"


# ---------------------------------------------------------------------------
# tax_id_present / activity_present — happy paths pin the OK message_key
# (the ERROR branches are dead code mirrored by min_length=1 field
# constraints on SetupAnswers)
# ---------------------------------------------------------------------------


def test_tax_id_present_ok_message_key_is_pinned() -> None:
    answers = _individual_answers()

    finding = _finding(answers, "tax_id_present")

    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.tax_id_present"


def test_activity_present_ok_message_key_is_pinned() -> None:
    answers = _individual_answers()

    finding = _finding(answers, "activity_present")

    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.activity_present"
