"""The real Modelo 100 projection serves its unresolved credit and totals in words, in every language.

The projection is read through the production service over a seeded profile with
a declared work income class and no payer record, then published through the
registered operation's public result. The expected words come from the catalogue
keys of the sentences themselves, so a translation that is missing, English or a
raw token fails the check.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.application.modelo.projection_operation import ModeloProjectOperationProjection
from cadrumo.application.modelo.projection_unresolved import UNRESOLVED_OPERAND_REASON
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision_sources import CalculationNoteSentence
from cadrumo.domain.user_profile.values import UserProfileFact

from .projection_m130_seeding_support import run_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_TRABAJO_BINDING = "renta-retencion-soportada-trabajo"
_INCOME_CLASS_KEY = "application.modelo.calc_diagnostic_words.income_class.trabajo"
_SOURCE_KEY = "flows.modelo_review.filter.option.binding_source.retencion_soportada"
_OPERAND_KEY = "application.modelo.projection_words.casilla_reason.unresolved_operand"


def test_an_unresolved_credit_and_the_totals_computed_from_it_are_served_in_every_language(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    # The activity's epigraph is outside group 861, so it is not an urban rental and the only credit left
    # without evidence is the declared work income's.
    result = run_projection(
        tmp_path,
        operation,
        income_categories="actividad_economica,trabajo",
        profile_facts=(UserProfileFact(path="activities.iae_epigraph", value="844"),),
    )
    generation = operation.generation.logical_generation

    served: dict[str, ModeloProjectOperationProjection] = {}
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            served[language] = ModeloProjectOperationProjection.from_service(
                _PROFILE, result, authority_generation=generation
            )

    for language, projection in served.items():
        assert projection.result_version == 3
        assert projection.words_language is OutputLanguage(language)
        (credit,) = projection.unresolved_bindings
        # The tokens are the service's, unchanged; the words are added beside them.
        assert credit.binding_id == _TRABAJO_BINDING
        assert credit.casilla_id == "0596"
        assert credit.note == CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED.value
        assert credit.source_words == lookup_translation(_SOURCE_KEY, locale=language)
        income_class = lookup_translation(_INCOME_CLASS_KEY, locale=language)
        assert income_class is not None
        assert income_class in credit.words
        assert "_" not in credit.words
        totals = {row.casilla_id: row for row in projection.unresolved_casillas}
        assert {"0609", "0610"} <= set(totals)
        assert totals["0609"].reason == UNRESOLVED_OPERAND_REASON
        assert totals["0609"].reason_words == lookup_translation(_OPERAND_KEY, locale=language)
        assert all(row.reason_words and "_" not in row.reason_words for row in projection.unresolved_casillas)
        # Words never stand in for a value: the unresolved boxes still carry none.
        assert not {"0596", "0609", "0610"} & {row.casilla_id for row in projection.casilla_observations}

    credit_words = {language: projection.unresolved_bindings[0].words for language, projection in served.items()}
    operand_words = {
        language: projection.unresolved_casillas[0].reason_words for language, projection in served.items()
    }
    assert len(set(credit_words.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
    assert len(set(operand_words.values())) == len(SUPPORTED_OUTPUT_LANGUAGES)
