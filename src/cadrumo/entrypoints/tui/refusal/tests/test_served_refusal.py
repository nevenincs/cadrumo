"""A recorded stop becomes the refusal it served: the backend's sentence and its recorded verdict, nothing else."""

from __future__ import annotations

import pytest

from .....application.operations.error_detail import (
    OperationErrorContextEntryV1,
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    build_operation_error_detail,
    operation_catalogue_refusal_words,
)
from .....application.operator_actions.preconditions import profile_setup_incomplete_verdict
from .....core.config import override_settings
from .....core.errors.error_codes import get_registered_error_code_by_code
from .....core.errors.hierarchy import RecordedRegisteredError
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ..served import served_refusal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CODE = "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO"
_MESSAGE_KEY = "aggregation.grouping.errors.unsupported_modelo"
_CONTEXT = (
    OperationErrorContextEntryV1(key="aggregator_label", value="probe"),
    OperationErrorContextEntryV1(key="modelo", value="111"),
)
#: A code whose registered message is itself the public sentence.
_PUBLIC_CODE = "REFUSED_ACTIVIDAD_ASSET_ACCELERATED_DA18_DEPRECIATION_NOT_COMPUTED"
#: A code whose registered message needs the context a bare code does not keep.
_PRIVATE_CODE = "REFUSED_DOMAIN_BUCKET_IMPORT"


def test_the_served_sentence_and_the_recorded_verdict_are_carried_unchanged() -> None:
    verdict = profile_setup_incomplete_verdict(modelo="303", missing_required_field_count=1)
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code=_CODE,
        message_key=_MESSAGE_KEY,
        context=_CONTEXT,
        precondition_verdict_json=verdict.model_dump_json(),
        refusal_words="Served sentence.",
        refusal_words_language=OutputLanguage.CA,
    )

    refusal = served_refusal(detail, refusal_code=_PUBLIC_CODE)

    assert refusal is not None
    assert refusal.refusal_words is not None
    assert (refusal.refusal_words.words, refusal.refusal_words.language) == ("Served sentence.", OutputLanguage.CA)
    assert refusal.verdict is not None
    assert refusal.verdict.to_verdict() == verdict
    assert refusal.primary_action_words is None
    assert refusal.alternative_action_words == ()


def test_a_detail_built_from_a_real_refusal_serves_the_sentence_the_worker_worded() -> None:
    error = RecordedRegisteredError(_CODE, context={"aggregator_label": "probe", "modelo": "111"})
    detail = build_operation_error_detail(error)
    assert detail is not None

    refusal = served_refusal(detail)

    assert refusal is not None
    assert refusal.sentence == detail.refusal_words
    assert refusal.verdict is None


def test_a_detail_recorded_before_sentences_were_served_is_worded_as_the_backend_words_it() -> None:
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR, error_code=_CODE, message_key=_MESSAGE_KEY, context=_CONTEXT
    )
    with override_settings(cadrumo_output_language="es"):
        words, language = operation_catalogue_refusal_words(_CODE, _MESSAGE_KEY, detail.context_mapping())
        refusal = served_refusal(detail)

    assert refusal is not None
    assert refusal.refusal_words is not None
    assert (refusal.refusal_words.words, refusal.refusal_words.language) == (words, language)
    assert language is OutputLanguage.ES


def test_without_a_detail_only_a_public_registry_sentence_is_shown() -> None:
    with override_settings(cadrumo_output_language="en"):
        public = served_refusal(None, refusal_code=_PUBLIC_CODE)
        expected = tr(get_registered_error_code_by_code(_PUBLIC_CODE).message_key, locale="en")

    assert public is not None
    assert public.sentence == expected
    assert public.verdict is None
    assert served_refusal(None, refusal_code=_PRIVATE_CODE) is None
    assert served_refusal(None, refusal_code=None) is None


def test_a_record_fault_that_served_no_sentence_and_no_verdict_shows_nothing() -> None:
    fault = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.RECORD_VALIDATION,
        error_code=None,
        message_key=None,
        context=(OperationErrorContextEntryV1(key="failing_record", value="BucketEvent"),),
    )

    assert served_refusal(fault) is None
