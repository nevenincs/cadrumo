"""Real-behavior coverage for localized modelo calculation input errors."""

from __future__ import annotations

import pytest

from ....core.errors import CadrumoError, build_error_envelope, resolve_error_message
from ....domain.calculations.registry.authority import bundled_authority
from .._calculate_input import (
    ModeloCalculateDecimalInputError,
    ModeloCalculateRelationInputError,
    ModeloCalculateTextInputError,
    _decimal,
    _projected_m210_tipo_renta_code,
    _text_value,
    _validated_m210_official_tipo_renta_code,
    _validated_relation_id,
)
from .._selectors import ModeloCalculationRevisionSelector
from ..work_addressing import ModeloRevisionPick, ModeloRevisionPickError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_decimal_override_error_is_typed_registered_and_localized() -> None:
    with pytest.raises(ModeloCalculateDecimalInputError) as exc_info:
        _decimal("not-decimal", flag="--relation", key="iva_base")

    error = exc_info.value
    assert isinstance(error, CadrumoError)
    assert error.translated_message == "application.modelo.errors.calculate_decimal_input_invalid"
    assert error.context == {"flag": "--relation", "key": "iva_base", "value": "not-decimal"}
    assert build_error_envelope(error).code
    assert "iva_base" in resolve_error_message(error)


def test_empty_text_override_error_is_typed_registered_and_localized() -> None:
    with pytest.raises(ModeloCalculateTextInputError) as exc_info:
        _text_value("   ", key="tipo_renta")

    error = exc_info.value
    assert isinstance(error, CadrumoError)
    assert error.translated_message == "application.modelo.errors.calculate_text_input_empty"
    assert error.context == {"key": "tipo_renta", "value": "   "}
    assert build_error_envelope(error).code
    message = resolve_error_message(error)
    assert message != error.translated_message
    assert "--casilla" in message


def test_m210_tipo_renta_accepts_a_declared_code_and_projects_to_its_concept() -> None:
    # A declared official code is accepted and PROJECTED to the TipoRentaIrnr
    # rate-concept token the engine keys on (code 18 -> pension, 01 -> general).
    assert (
        _projected_m210_tipo_renta_code(_validated_m210_official_tipo_renta_code("18", key="tipo_renta")) == "pension"
    )
    assert (
        _projected_m210_tipo_renta_code(_validated_m210_official_tipo_renta_code("  01 ", key="tipo_renta"))
        == "general"
    )


def test_m210_tipo_renta_fetch_gated_code_refuses_as_fetch_gated_not_invalid() -> None:
    # Code 13 (asistencia técnica) is a REAL official code whose rate is not yet
    # grounded — the operator must be told "fetch-gated", never "invalid".
    with pytest.raises(ModeloCalculateTextInputError) as exc_info:
        _validated_m210_official_tipo_renta_code("13", key="tipo_renta")

    error = exc_info.value
    assert isinstance(error, CadrumoError)
    assert error.translated_message == "application.modelo.errors.calculate_m210_tipo_renta_fetch_gated"
    assert error.context is not None
    assert error.context["value"] == "13"
    assert isinstance(error.context["accepted"], str)
    # The accepted set lists the declared codes (e.g. 18); it never lists the fetch-gated 13.
    assert "18" in error.context["accepted"]
    assert "13" not in error.context["accepted"]
    assert build_error_envelope(error).code


def test_m210_tipo_renta_unknown_code_refuses_and_lists_accepted_and_fetch_gated() -> None:
    # A value that is not any official code is refused, naming both the accepted
    # declared codes and the fetch-gated (pending-grounding) ones.
    with pytest.raises(ModeloCalculateTextInputError) as exc_info:
        _validated_m210_official_tipo_renta_code("99", key="tipo_renta")

    error = exc_info.value
    assert error.translated_message == "application.modelo.errors.calculate_m210_tipo_renta_unknown"
    assert error.context is not None
    assert error.context["value"] == "99"
    assert isinstance(error.context["accepted"], str)
    assert isinstance(error.context["fetch_gated"], str)
    assert "18" in error.context["accepted"]
    assert "13" in error.context["fetch_gated"]
    message = resolve_error_message(error)
    assert message != error.translated_message


def test_unknown_relation_override_error_names_revision_relation_ids() -> None:
    revision = bundled_authority().validate_modelo("200").revisions["2024"]
    relation_ids = {relation.id for relation in revision.relations}
    accepted_relation = "modelo-200-2024-rel-202-pagos-fraccionados"
    assert accepted_relation in relation_ids

    with pytest.raises(ModeloCalculateRelationInputError) as exc_info:
        _validated_relation_id("Bad Relation", relation_ids)

    error = exc_info.value
    assert isinstance(error, CadrumoError)
    assert error.translated_message == "application.modelo.errors.calculate_relation_unknown"
    assert error.context is not None
    assert error.context["key"] == "Bad Relation"
    assert accepted_relation in str(error.context["accepted"])
    # The rejected token rides on context, never in the exception's own text:
    # str(exc) prefers a positional argument over the registered key, so an
    # authored sentence here would reach tracebacks and logs in English in
    # every locale while this test stayed green on the key above.
    assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"


def test_revision_pick_error_is_typed_registered_and_localized() -> None:
    with pytest.raises(ModeloRevisionPickError) as exc_info:
        ModeloRevisionPick(selector=ModeloCalculationRevisionSelector.EXPLICIT)

    error = exc_info.value
    assert isinstance(error, CadrumoError)
    assert error.translated_message == "application.modelo.errors.revision_pick_explicit_id_required"
    assert build_error_envelope(error).code
    assert "calculation_revision_id" in resolve_error_message(error)
