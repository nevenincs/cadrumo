"""Real-behavior tests for SetupAnswers answer-type validation.

Pydantic wraps field-validator exceptions in ``ValidationError``. To exercise
each migrated raise site through the public production boundary, the tests call
``SetupAnswers.model_validate(...)`` and assert the wrapped validation message
identifies the rejected field/type contract.

Since :class:`SetupAnswers` is now canonical in :mod:`cadrumo.core.setup_answers`, its
validators raise :class:`~cadrumo.core.errors.ProfileAnswerTypeError` directly.
:class:`~cadrumo.application.wizard.errors.WizardAnswerTypeError` is a subclass
of ``ProfileAnswerTypeError`` — the registry / envelope tests below verify that
the application-layer subclass still resolves correctly.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.errors import ERROR_REGISTRY, build_error_envelope
from ....core.setup_answers import SetupAnswers
from ..errors import WizardAnswerTypeError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ── Registry / envelope contract ─────────────────────────────────────────────


def test_wizard_answer_type_error_is_registered_in_error_registry() -> None:
    assert "REFUSED_WIZARD_ANSWER_TYPE" in ERROR_REGISTRY


def test_wizard_answer_type_error_round_trips_through_build_error_envelope() -> None:
    exc = WizardAnswerTypeError("iva_regime must be an IVARegime member or string token")
    envelope = build_error_envelope(exc, trace_id=None)
    assert envelope.code == "REFUSED_WIZARD_ANSWER_TYPE"
    assert envelope.retryable is False


# ── Per-field real coercion raises (public model boundary) ────────────────────


def test_setup_answer_model_rejects_invalid_answer_types() -> None:
    for field_name, invalid_value, message in (
        ("iva_regime", 42, "iva_regime"),
        ("entity_type", 42, "entity_type"),
        ("legal_entity_form", 42, "legal_entity_form"),
        ("irpf_estimation_regime", 42, "irpf_estimation_regime"),
        ("situacion_familiar", 42, "situacion_familiar"),
        (
            "unidad_familiar_descendientes_exclusivos",
            42,
            "unidad_familiar_descendientes_exclusivos",
        ),
        ("irpf_special_regime", 42, "irpf_special_regime"),
        ("fiscal_residency", 42, "fiscal_residency"),
        ("taxation_type", 42, "taxation_type"),
        ("taxpayer_sex", 42, "sex code"),
        ("spouse_sex", object(), "sex code"),
        ("taxpayer_marital_status", 42, "taxpayer_marital_status"),
        ("taxpayer_disability_grade", 42, "disability grade"),
        ("spouse_disability_grade", object(), "disability grade"),
        ("tax_residence_ccaa", 42, "tax_residence_ccaa"),
    ):
        with pytest.raises(ValidationError, match=message):
            SetupAnswers.model_validate({"tax_id": "00000000T", field_name: invalid_value})


def test_setup_answer_model_rejects_an_unknown_situacion_familiar_token() -> None:
    with pytest.raises(ValidationError, match="situacion_familiar"):
        SetupAnswers.model_validate({"tax_id": "00000000T", "situacion_familiar": "casadoX"})
