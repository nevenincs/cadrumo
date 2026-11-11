"""A refused inventory operation always names the sentence of its own reason."""

from __future__ import annotations

import re
from uuid import UUID

import pytest

from cadrumo.application.inventory.errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)
from cadrumo.application.inventory.refusal_words import served_refusal_words
from cadrumo.application.inventory.registered_executor import refusal_for_error
from cadrumo.application.inventory.registered_requests import InventoryInspectRequest, InventoryRefusalReason
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REQUEST = InventoryInspectRequest(
    profile_id=UUID("28282828-2828-4828-8828-282828282828"), actividad_id="A1", year=_YEAR
)
_FAMILY = "application.inventory.service.errors."


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (
            InventoryActividadConflictError(
                translated_message=f"{_FAMILY}activity_conflict", context={"actividad_id": "A1", "year": str(_YEAR)}
            ),
            "activity_conflict",
        ),
        (
            InventoryActividadNotFoundError(
                translated_message=f"{_FAMILY}activity_not_found", context={"actividad_id": "A1", "year": str(_YEAR)}
            ),
            "activity_not_found",
        ),
        (
            InventoryServiceInputError(translated_message="errors.refused.refused_profile_inventory_validation"),
            "inventory_validation",
        ),
    ],
)
def test_the_reason_key_is_the_family_key_of_the_reason(error: Exception, reason: str) -> None:
    refusal = refusal_for_error(request=_REQUEST, error=error)

    assert refusal is not None
    assert refusal.reason == reason
    assert refusal.reason_key == f"{_FAMILY}{reason}"


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (
            InventoryActividadConflictError(
                translated_message=f"{_FAMILY}activity_conflict", context={"actividad_id": "A1", "year": str(_YEAR)}
            ),
            "activity_conflict",
        ),
        (
            InventoryActividadNotFoundError(
                translated_message=f"{_FAMILY}activity_not_found", context={"actividad_id": "A1", "year": str(_YEAR)}
            ),
            "activity_not_found",
        ),
        (
            InventoryServiceInputError(translated_message="errors.refused.refused_profile_inventory_validation"),
            "inventory_validation",
        ),
    ],
)
def test_the_refusal_serves_the_catalogue_sentence_of_its_reason_in_the_workers_language(
    error: Exception, reason: str, language: OutputLanguage
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        refusal = refusal_for_error(request=_REQUEST, error=error)
        expected = tr(f"{_FAMILY}{reason}", locale=language.value, year=str(_YEAR))

    assert refusal is not None
    assert refusal.refusal_words == expected
    assert refusal.refusal_words_language is language
    assert "%{" not in expected


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize(
    "reason",
    [
        "activity_conflict",
        "activity_not_found",
        "invalid_valuation_method",
        "duplicate_movement_id",
        "inventory_validation",
        "closing_authority_conflict",
        "closing_authority_invalid",
        "evidence_file_not_admitted",
    ],
)
def test_every_reason_a_frontend_used_to_word_itself_serves_a_finished_sentence(
    reason: InventoryRefusalReason, language: OutputLanguage
) -> None:
    facts = {"actividad_id": "A1", "year": str(_YEAR), "valuation_method": "fifo"}
    with override_settings(cadrumo_output_language=language.value):
        words, served_language = served_refusal_words(reason, error_code="REFUSED_INVENTORY_SERVICE_INPUT", facts=facts)

    assert served_language is language
    assert len(words) > 20
    assert not re.search(r"%\{|\{|\}", words)
