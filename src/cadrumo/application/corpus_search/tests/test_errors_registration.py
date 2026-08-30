"""The corpus-search errors are registered CadrumoError codes, not bare Exceptions.

A corpus-search failure that reaches the CLI boundary must render as its proper
category envelope — a ``REFUSED`` input/dependency refusal, an ``ERROR`` base —
rather than collapsing into the generic ``INTERNAL`` unexpected-boundary path
(the same mis-classification the exit-6 hint fix addressed). These tests lock
that: each class binds a registered code, the envelope carries the right
category, and the raise-site ergonomics (free-form message, dict context,
without a local suggestion channel) survive the promotion.
"""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import ErrorCategory, build_error_envelope
from ....core.errors.hierarchy import CadrumoError
from ..errors import CorpusSearchError, CorpusSearchInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_all_corpus_errors_are_registry_bound_cadrumo_errors() -> None:
    for cls in (CorpusSearchError, CorpusSearchInputError):
        assert issubclass(cls, CadrumoError)
        assert cls.code.code  # a bound, registered ErrorCode


def test_input_error_renders_as_refused_not_internal() -> None:
    error = CorpusSearchInputError(reason="query_empty", context={"query": ""})
    envelope = build_error_envelope(error)
    assert envelope.category == ErrorCategory.REFUSED.value
    assert envelope.code == "REFUSED_CORPUS_SEARCH_INPUT"
    # The specific detail rides on context; the localized message comes from the
    # registered message_key (never the generic INTERNAL boundary text).
    assert envelope.context is not None
    assert envelope.context.get("query") == ""
    assert "INTERNAL" not in envelope.category


def test_input_error_has_context_but_no_local_suggestion_channel() -> None:
    error = CorpusSearchInputError(
        reason="citation_id_unknown",
        context={"citation_id": "ley-58-2003:art-999"},
    )
    envelope = build_error_envelope(error)
    assert envelope.category == ErrorCategory.REFUSED.value
    assert error.context == {"reason": "citation_id_unknown", "citation_id": "ley-58-2003:art-999"}
    # The condition travels as a discriminant, never as a sentence: str(exc)
    # prefers a positional argument over the registered key, so an authored
    # message here would reach tracebacks and logs in English in every locale.
    assert str(error) == error.translated_message, f"the constructor authors a sentence: {str(error)!r}"
    assert not hasattr(error, "suggestion")
    assert "suggestion" not in envelope.model_dump()


def test_context_stays_a_dict_even_when_unset() -> None:
    # The surface's always-a-dict `.context` contract must survive promotion
    # (CadrumoError's own base leaves it None when unset).
    assert CorpusSearchError(reason="probe").context == {"reason": "probe"}
