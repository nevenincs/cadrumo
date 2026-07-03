"""Verifier + schema tests for the Art. 82 LIRPF situacion_familiar axis.

Covers:
- SituacionFamiliar.conjunta_eligible() and requires_spouse_or_partner()
- SetupAnswers field validation: accepted tokens, blank passthrough, rejection
- _check_joint_taxation_situacion_familiar: OK paths and the refused ERROR path
- Anti-tautology: mutating the enum value produces a different verifier outcome
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.setup_answers import SetupAnswers
from ....domain.contribuyente import CCAA, SituacionFamiliar
from ....domain.deadlines import IVARegime
from .._verifier import (
    WizardCheckFinding,
    WizardCheckSeverity,
    verify_setup_answers,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# SituacionFamiliar enum helpers
# ---------------------------------------------------------------------------


def test_conjunta_eligible() -> None:
    for situacion_familiar, expected in (
        (SituacionFamiliar.CASADO, True),
        (
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
            True,
        ),
        (
            SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
            False,
        ),
    ):
        assert situacion_familiar.conjunta_eligible() is expected, situacion_familiar


def test_requires_spouse_or_partner() -> None:
    for situacion_familiar, expected in (
        (SituacionFamiliar.CASADO, True),
        (
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
            True,
        ),
        (SituacionFamiliar.SOLTERO, False),
        (
            SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
            False,
        ),
    ):
        assert situacion_familiar.requires_spouse_or_partner() is expected, situacion_familiar


# ---------------------------------------------------------------------------
# SetupAnswers field validation
# ---------------------------------------------------------------------------


def _base_answers(**overrides: object) -> SetupAnswers:
    defaults: dict[str, object] = {
        "tax_id": "12345678Z",
        "activity": "consultora",
        "iva_regime": IVARegime.GENERAL,
        "tax_residence_ccaa": CCAA.MADRID,
    }
    defaults.update(overrides)
    return SetupAnswers.model_validate(defaults)


def test_situacion_familiar_validation() -> None:
    for raw_value, expected in (
        ("", ""),
        ("casado", SituacionFamiliar.CASADO),
        (
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
        ),
    ):
        answers = _base_answers(situacion_familiar=raw_value)
        assert answers.situacion_familiar == expected, raw_value


def test_situacion_familiar_invalid_token_rejected() -> None:
    with pytest.raises(ValidationError):
        _base_answers(situacion_familiar="viudo")


def test_unidad_familiar_descendientes_exclusivos_validation() -> None:
    for raw_value, expected in (
        ("", ""),
        ("true", True),
        (False, False),
    ):
        answers = _base_answers(unidad_familiar_descendientes_exclusivos=raw_value)
        assert answers.unidad_familiar_descendientes_exclusivos == expected, raw_value


# ---------------------------------------------------------------------------
# joint_taxation_situacion_familiar check
# ---------------------------------------------------------------------------


def _finding(answers: SetupAnswers, name: str) -> WizardCheckFinding:
    report = verify_setup_answers(answers)
    return next(item for item in report.findings if item.name == name)


def test_joint_taxation_situacion_familiar_cases() -> None:
    for case_id, overrides, expected_severity, expected_message_key in (
        (
            "individual-taxation",
            {
                "taxation_type": "1",
                "situacion_familiar": SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
        ),
        (
            "taxation-type-blank",
            {
                "taxation_type": "",
                "situacion_familiar": SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
        ),
        (
            "situacion-blank",
            {
                "taxation_type": "2",
                "situacion_familiar": "",
                "spouse_tax_id": "87654321B",
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
        ),
        (
            "casado-conjunta",
            {
                "taxation_type": "2",
                "situacion_familiar": SituacionFamiliar.CASADO,
                "spouse_tax_id": "87654321B",
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
        ),
        (
            "pareja-registrada-conjunta",
            {
                "taxation_type": "2",
                "situacion_familiar": SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
                "spouse_tax_id": "87654321B",
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
        ),
        (
            "pareja-no-registrada-conjunta",
            {
                "taxation_type": "2",
                "situacion_familiar": SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
                "spouse_tax_id": "87654321B",
            },
            WizardCheckSeverity.ERROR,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_refused",
        ),
    ):
        answers = _base_answers(**overrides)
        finding = _finding(answers, "joint_taxation_situacion_familiar")
        assert finding.severity is expected_severity, case_id
        assert finding.message_key == expected_message_key, case_id


# ---------------------------------------------------------------------------
# Anti-tautology: changing the situation changes the verdict
# ---------------------------------------------------------------------------


def test_antitautology_different_situacion_yields_different_severity() -> None:
    """If the check were tautological it would return the same severity for both
    CASADO and PAREJA_HECHO_NO_REGISTRADA when taxation_type='2'."""
    answers_ok = _base_answers(
        taxation_type="2",
        situacion_familiar=SituacionFamiliar.CASADO,
        spouse_tax_id="87654321B",
    )
    answers_refused = _base_answers(
        taxation_type="2",
        situacion_familiar=SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
        spouse_tax_id="87654321B",
    )
    finding_ok = _finding(answers_ok, "joint_taxation_situacion_familiar")
    finding_refused = _finding(answers_refused, "joint_taxation_situacion_familiar")

    assert finding_ok.severity is not finding_refused.severity
