"""The corpus-search errors are registered AeatError codes, not bare Exceptions.

A corpus-search failure that reaches the CLI boundary must render as its proper
category envelope — a ``REFUSED`` input/dependency refusal, an ``ERROR`` base —
rather than collapsing into the generic ``INTERNAL`` unexpected-boundary path
(the same mis-classification the exit-6 hint fix addressed). These tests lock
that: each class binds a registered code, the envelope carries the right
category, and the raise-site ergonomics (free-form message, dict context, the
install-hint suggestion) survive the promotion.
"""

from __future__ import annotations

import pytest

from ....core.errors import AeatError, ErrorCategory, build_error_envelope
from .._errors import CorpusSearchDependencyError, CorpusSearchError, CorpusSearchInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_all_corpus_errors_are_registry_bound_aeat_errors() -> None:
    for cls in (CorpusSearchError, CorpusSearchInputError, CorpusSearchDependencyError):
        assert issubclass(cls, AeatError)
        assert cls.code.code  # a bound, registered ErrorCode


def test_input_error_renders_as_refused_not_internal() -> None:
    error = CorpusSearchInputError("retrieval query must be non-empty", context={"query": ""})
    envelope = build_error_envelope(error)
    assert envelope.category == ErrorCategory.REFUSED.value
    assert envelope.code == "REFUSED_CORPUS_SEARCH_INPUT"
    # The specific detail rides on context; the localized message comes from the
    # registered message_key (never the generic INTERNAL boundary text).
    assert envelope.context is not None
    assert envelope.context.get("query") == ""
    assert "INTERNAL" not in envelope.category


def test_dependency_error_carries_its_install_hint_suggestion() -> None:
    error = CorpusSearchDependencyError(
        "semantic query embedder needs the search extra",
        suggestion='pip install "aeat-cli[search]"',
    )
    envelope = build_error_envelope(error)
    assert envelope.category == ErrorCategory.REFUSED.value
    # The raise-site suggestion overrides the registered default and survives.
    assert envelope.suggestion == 'pip install "aeat-cli[search]"'


def test_context_stays_a_dict_even_when_unset() -> None:
    # The surface's always-a-dict `.context` contract must survive promotion
    # (AeatError's own base leaves it None when unset).
    assert CorpusSearchError("x").context == {}
