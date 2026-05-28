"""Real-behavior tests for SetupAnswers coercion raises WizardAnswerTypeError.

Pydantic wraps field-validator exceptions in ``ValidationError``. To exercise
each migrated raise site directly, the tests call the ``@classmethod``
validator methods on :class:`SetupAnswers` rather than going through the full
model constructor. This confirms the raise site exists and the typed exception
class is what gets raised at the coercion boundary, before pydantic wraps it.
"""

from __future__ import annotations

import pytest

from ...core.errors import ERROR_REGISTRY, build_error_envelope
from ._errors import WizardAnswerTypeError
from ._setup_answers import SetupAnswers

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# ── Registry / envelope contract ─────────────────────────────────────────────


def test_wizard_answer_type_error_is_registered_in_error_registry() -> None:
    assert "REFUSED_WIZARD_ANSWER_TYPE" in ERROR_REGISTRY


def test_wizard_answer_type_error_round_trips_through_build_error_envelope() -> None:
    exc = WizardAnswerTypeError("iva_regime must be an IVARegime member or string token")
    envelope = build_error_envelope(exc, trace_id=None)
    assert envelope.code == "REFUSED_WIZARD_ANSWER_TYPE"
    assert envelope.retryable is False


# ── Per-field real coercion raises (direct validator calls) ───────────────────
# Validators are called directly so the raise propagates without pydantic
# wrapping it in ValidationError. Each call is the real production code path.


def test_iva_regime_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="iva_regime"):
        SetupAnswers._parse_iva_regime(42)  # type: ignore[arg-type]


def test_entity_type_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="entity_type"):
        SetupAnswers._parse_entity_type(42)  # type: ignore[arg-type]


def test_legal_entity_form_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="legal_entity_form"):
        SetupAnswers._parse_legal_entity_form(42)  # type: ignore[arg-type]


def test_irpf_estimation_regime_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="irpf_estimation_regime"):
        SetupAnswers._parse_irpf_estimation_regime(42)  # type: ignore[arg-type]


def test_situacion_familiar_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="situacion_familiar"):
        SetupAnswers._parse_situacion_familiar(42)  # type: ignore[arg-type]


def test_unidad_familiar_descendientes_exclusivos_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="unidad_familiar_descendientes_exclusivos"):
        SetupAnswers._parse_unidad_familiar_descendientes_exclusivos(42)  # type: ignore[arg-type]


def test_irpf_special_regime_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="irpf_special_regime"):
        SetupAnswers._parse_irpf_special_regime(42)  # type: ignore[arg-type]


def test_fiscal_residency_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="fiscal_residency"):
        SetupAnswers._parse_fiscal_residency(42)  # type: ignore[arg-type]


def test_taxation_type_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="taxation_type"):
        SetupAnswers._parse_taxation_type(42)  # type: ignore[arg-type]


def test_taxpayer_sex_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="sex code"):
        SetupAnswers._parse_sex_code(42)  # type: ignore[arg-type]


def test_spouse_sex_raises_wizard_answer_type_error_for_invalid_type() -> None:
    # _parse_sex_code handles both taxpayer_sex and spouse_sex; any non-str/enum
    # input from either field hits the same raise site.
    with pytest.raises(WizardAnswerTypeError, match="sex code"):
        SetupAnswers._parse_sex_code(object())  # type: ignore[arg-type]


def test_taxpayer_marital_status_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="taxpayer_marital_status"):
        SetupAnswers._parse_marital_status(42)  # type: ignore[arg-type]


def test_taxpayer_disability_grade_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="disability grade"):
        SetupAnswers._parse_disability_grade(42)  # type: ignore[arg-type]


def test_spouse_disability_grade_raises_wizard_answer_type_error_for_invalid_type() -> None:
    # _parse_disability_grade handles both taxpayer_ and spouse_ fields.
    with pytest.raises(WizardAnswerTypeError, match="disability grade"):
        SetupAnswers._parse_disability_grade(object())  # type: ignore[arg-type]


def test_tax_residence_ccaa_raises_wizard_answer_type_error_for_invalid_type() -> None:
    with pytest.raises(WizardAnswerTypeError, match="tax_residence_ccaa"):
        SetupAnswers._parse_tax_residence_ccaa(42)  # type: ignore[arg-type]
