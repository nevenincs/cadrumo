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
from ....domain.contribuyente._ccaa import CCAA
from ....domain.contribuyente._renta_codes import SituacionFamiliar
from ....domain.deadlines._models import IVARegime
from .._verifier import (
    WizardCheckFinding,
    WizardCheckSeverity,
    verify_setup_answers,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# SituacionFamiliar enum helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("situacion_familiar", "expected"),
    (
        pytest.param(SituacionFamiliar.CASADO, True, id="casado"),
        pytest.param(
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
            True,
            id="pareja-registrada",
        ),
        pytest.param(
            SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
            False,
            id="pareja-no-registrada",
        ),
    ),
)
def test_conjunta_eligible(
    situacion_familiar: SituacionFamiliar,
    expected: bool,
) -> None:
    assert situacion_familiar.conjunta_eligible() is expected


@pytest.mark.parametrize(
    ("situacion_familiar", "expected"),
    (
        pytest.param(SituacionFamiliar.CASADO, True, id="casado"),
        pytest.param(
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
            True,
            id="pareja-registrada",
        ),
        pytest.param(SituacionFamiliar.SOLTERO, False, id="soltero"),
        pytest.param(
            SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
            False,
            id="pareja-no-registrada",
        ),
    ),
)
def test_requires_spouse_or_partner(
    situacion_familiar: SituacionFamiliar,
    expected: bool,
) -> None:
    assert situacion_familiar.requires_spouse_or_partner() is expected


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


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    (
        pytest.param("", "", id="blank"),
        pytest.param("casado", SituacionFamiliar.CASADO, id="string-token"),
        pytest.param(
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
            SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
            id="enum-member",
        ),
    ),
)
def test_situacion_familiar_validation(
    raw_value: object,
    expected: object,
) -> None:
    answers = _base_answers(situacion_familiar=raw_value)
    assert answers.situacion_familiar == expected


def test_situacion_familiar_invalid_token_rejected() -> None:
    with pytest.raises(ValidationError):
        _base_answers(situacion_familiar="viudo")


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    (
        pytest.param("", "", id="blank"),
        pytest.param("true", True, id="true-string"),
        pytest.param(False, False, id="bool-false"),
    ),
)
def test_unidad_familiar_descendientes_exclusivos_validation(
    raw_value: object,
    expected: object,
) -> None:
    answers = _base_answers(unidad_familiar_descendientes_exclusivos=raw_value)
    assert answers.unidad_familiar_descendientes_exclusivos == expected


# ---------------------------------------------------------------------------
# joint_taxation_situacion_familiar check
# ---------------------------------------------------------------------------


def _finding(answers: SetupAnswers, name: str) -> WizardCheckFinding:
    report = verify_setup_answers(answers)
    return next(item for item in report.findings if item.name == name)


@pytest.mark.parametrize(
    ("overrides", "expected_severity", "expected_message_key"),
    (
        pytest.param(
            {
                "taxation_type": "1",
                "situacion_familiar": SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
            id="individual-taxation",
        ),
        pytest.param(
            {
                "taxation_type": "",
                "situacion_familiar": SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
            id="taxation-type-blank",
        ),
        pytest.param(
            {
                "taxation_type": "2",
                "situacion_familiar": "",
                "spouse_tax_id": "87654321B",
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
            id="situacion-blank",
        ),
        pytest.param(
            {
                "taxation_type": "2",
                "situacion_familiar": SituacionFamiliar.CASADO,
                "spouse_tax_id": "87654321B",
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
            id="casado-conjunta",
        ),
        pytest.param(
            {
                "taxation_type": "2",
                "situacion_familiar": SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
                "spouse_tax_id": "87654321B",
            },
            WizardCheckSeverity.OK,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
            id="pareja-registrada-conjunta",
        ),
        pytest.param(
            {
                "taxation_type": "2",
                "situacion_familiar": SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
                "spouse_tax_id": "87654321B",
            },
            WizardCheckSeverity.ERROR,
            "wizard.setup.verifier.joint_taxation_situacion_familiar_refused",
            id="pareja-no-registrada-conjunta",
        ),
    ),
)
def test_joint_taxation_situacion_familiar_cases(
    overrides: dict[str, object],
    expected_severity: WizardCheckSeverity,
    expected_message_key: str,
) -> None:
    answers = _base_answers(**overrides)
    finding = _finding(answers, "joint_taxation_situacion_familiar")
    assert finding.severity is expected_severity
    assert finding.message_key == expected_message_key


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
