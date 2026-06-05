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


def test_conjunta_eligible_returns_true_for_casado() -> None:
    assert SituacionFamiliar.CASADO.conjunta_eligible() is True


def test_conjunta_eligible_returns_true_for_pareja_registrada() -> None:
    assert SituacionFamiliar.PAREJA_HECHO_REGISTRADA.conjunta_eligible() is True


def test_conjunta_eligible_returns_false_for_pareja_no_registrada() -> None:
    # Pareja de hecho no registrada is the sole case explicitly blocked by
    # Art. 82.1.2° LIRPF — the verifier uses this to emit an ERROR.
    assert SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA.conjunta_eligible() is False


def test_requires_spouse_returns_true_for_casado() -> None:
    assert SituacionFamiliar.CASADO.requires_spouse_or_partner() is True


def test_requires_spouse_returns_true_for_pareja_registrada() -> None:
    assert SituacionFamiliar.PAREJA_HECHO_REGISTRADA.requires_spouse_or_partner() is True


def test_requires_spouse_returns_false_for_soltero() -> None:
    assert SituacionFamiliar.SOLTERO.requires_spouse_or_partner() is False


def test_requires_spouse_returns_false_for_pareja_no_registrada() -> None:
    assert SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA.requires_spouse_or_partner() is False


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


def test_situacion_familiar_blank_accepted() -> None:
    answers = _base_answers(situacion_familiar="")
    assert answers.situacion_familiar == ""


def test_situacion_familiar_casado_string_accepted() -> None:
    answers = _base_answers(situacion_familiar="casado")
    assert answers.situacion_familiar == SituacionFamiliar.CASADO


def test_situacion_familiar_enum_member_accepted() -> None:
    answers = _base_answers(situacion_familiar=SituacionFamiliar.PAREJA_HECHO_REGISTRADA)
    assert answers.situacion_familiar == SituacionFamiliar.PAREJA_HECHO_REGISTRADA


def test_situacion_familiar_invalid_token_rejected() -> None:
    with pytest.raises(ValidationError):
        _base_answers(situacion_familiar="viudo")


def test_unidad_familiar_descendientes_exclusivos_blank_accepted() -> None:
    answers = _base_answers(unidad_familiar_descendientes_exclusivos="")
    assert answers.unidad_familiar_descendientes_exclusivos == ""


def test_unidad_familiar_descendientes_exclusivos_true_string_accepted() -> None:
    answers = _base_answers(unidad_familiar_descendientes_exclusivos="true")
    assert answers.unidad_familiar_descendientes_exclusivos is True


def test_unidad_familiar_descendientes_exclusivos_bool_accepted() -> None:
    answers = _base_answers(unidad_familiar_descendientes_exclusivos=False)
    assert answers.unidad_familiar_descendientes_exclusivos is False


# ---------------------------------------------------------------------------
# joint_taxation_situacion_familiar check
# ---------------------------------------------------------------------------


def _finding(answers: SetupAnswers, name: str) -> WizardCheckFinding:
    report = verify_setup_answers(answers)
    return next(item for item in report.findings if item.name == name)


def test_check_ok_when_individual_taxation_regardless_of_situation() -> None:
    """Individual taxation never triggers the conjunta check."""
    answers = _base_answers(
        taxation_type="1",
        situacion_familiar=SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
    )
    finding = _finding(answers, "joint_taxation_situacion_familiar")
    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.joint_taxation_situacion_familiar_ok"


def test_check_ok_when_taxation_type_blank() -> None:
    """Undeclared taxation type passes the check regardless of situation."""
    answers = _base_answers(
        taxation_type="",
        situacion_familiar=SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
    )
    finding = _finding(answers, "joint_taxation_situacion_familiar")
    assert finding.severity is WizardCheckSeverity.OK


def test_check_ok_when_situacion_familiar_blank() -> None:
    """Undeclared situacion_familiar passes even for conjunta."""
    answers = _base_answers(
        taxation_type="2",
        situacion_familiar="",
        spouse_tax_id="87654321B",
    )
    finding = _finding(answers, "joint_taxation_situacion_familiar")
    assert finding.severity is WizardCheckSeverity.OK


def test_check_ok_when_casado_requests_conjunta() -> None:
    answers = _base_answers(
        taxation_type="2",
        situacion_familiar=SituacionFamiliar.CASADO,
        spouse_tax_id="87654321B",
    )
    finding = _finding(answers, "joint_taxation_situacion_familiar")
    assert finding.severity is WizardCheckSeverity.OK
    assert finding.message_key == "wizard.setup.verifier.joint_taxation_situacion_familiar_ok"


def test_check_ok_when_pareja_registrada_requests_conjunta() -> None:
    answers = _base_answers(
        taxation_type="2",
        situacion_familiar=SituacionFamiliar.PAREJA_HECHO_REGISTRADA,
        spouse_tax_id="87654321B",
    )
    finding = _finding(answers, "joint_taxation_situacion_familiar")
    assert finding.severity is WizardCheckSeverity.OK


def test_check_error_when_pareja_no_registrada_requests_conjunta() -> None:
    """Art. 82.1.2° LIRPF: unregistered de-facto couple cannot file jointly."""
    answers = _base_answers(
        taxation_type="2",
        situacion_familiar=SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA,
        spouse_tax_id="87654321B",
    )
    finding = _finding(answers, "joint_taxation_situacion_familiar")
    assert finding.severity is WizardCheckSeverity.ERROR
    assert finding.message_key == "wizard.setup.verifier.joint_taxation_situacion_familiar_refused"


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
