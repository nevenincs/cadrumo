"""Verifier behaviour tests.

The tests construct ``SetupAnswers`` instances that exercise each
``WizardCheck`` outcome shape and assert the per-check severity. The
checks themselves are not re-implemented in the test bodies; the tests
only verify the published contract (severity + finding name + the
locale-keyed message_key).
"""

from __future__ import annotations

import pytest

from ....core.setup_answers import SetupAnswers
from ....domain.contribuyente._ccaa import CCAA
from ....domain.deadlines._models import IVARegime
from .._verifier import (
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


def test_verify_emits_one_finding_per_registered_check() -> None:
    report = verify_setup_answers(_individual_answers())
    names = [finding.name for finding in report.findings]
    assert names == [
        "tax_id_present",
        "activity_present",
        "spouse_consistency",
        "eu_eea_country_consistency",
        "obligations_consistency",
        "joint_taxation_situacion_familiar",
        "monoparental_requires_hijos",
    ]


def test_verifier_is_green_on_well_formed_individual() -> None:
    report = verify_setup_answers(_individual_answers())
    severities = {finding.name: finding.severity for finding in report.findings}
    assert severities["tax_id_present"] is WizardCheckSeverity.OK
    assert severities["activity_present"] is WizardCheckSeverity.OK
    assert severities["spouse_consistency"] is WizardCheckSeverity.OK
    assert not report.has_errors


def test_verifier_finds_obligations_inconsistency() -> None:
    answers = _individual_answers(
        professional_income_withholding_ge_70pct=True,
        pays_professionals_with_retencion=False,
    )
    report = verify_setup_answers(answers)
    finding = next(item for item in report.findings if item.name == "obligations_consistency")
    assert finding.severity is WizardCheckSeverity.WARNING


def test_finding_message_keys_share_wizard_namespace() -> None:
    report = verify_setup_answers(_individual_answers())
    for finding in report.findings:
        assert finding.message_key.startswith("wizard.setup.verifier.")
