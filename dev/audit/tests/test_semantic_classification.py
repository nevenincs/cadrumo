"""Tests for the semantic audit's leak classification.

`dev.quality.module_test_reach` listed `dev/audit/semantic.py` as unreached. Its
search and health calls need the resident RAG daemon, which is not connected
here, but the classification is pure: given a snippet and a path, is this a
domain calculation that leaked into an adapter or an entrypoint?

That judgement had nothing checking it, and it was wrong. ``sum`` was matched as
a raw SUBSTRING, so it also fired on ``resume``, ``consume``, ``assume`` and
``summary`` - all of which occur in this tree, ``resume_profile_session`` among
them. An adapter merely resuming a session was classified as computing a tax
base and reported as a hexagonal leak. Verified against the real predicate
before the change: all four returned ``True``.

The long tokens are still substring matches and that is deliberate; they have no
common false friends, and matching them loosely keeps ``recalculate`` and
``precompute`` in scope. Both directions are pinned below, because a fix that
narrowed the predicate until it caught nothing would look just as green.
"""

from __future__ import annotations

import ast

import pytest

from ..semantic import (
    _is_calculation,
    _is_tax_base_target,
    _is_transcribed_value,
    _name_words,
    is_violation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _expression(source: str) -> ast.expr:
    return ast.parse(source, mode="eval").body


@pytest.mark.parametrize("call", ["resume(session)", "consume(row)", "assume(fact)", "summary(rows)"])
def test_a_word_merely_containing_sum_is_not_a_calculation(call: str) -> None:
    """The false positives. ``resume_profile_session`` is a real symbol here.

    Reporting one of these as a tax-base calculation inside an adapter files a
    hexagonal-leak finding against code that computes nothing, and a reviewer
    who checks one and finds it hollow trusts the next one less.
    """
    assert not _is_calculation(_expression(call))


@pytest.mark.parametrize(
    "call",
    ["sum(values)", "sum_totals(rows)", "totalSum(rows)", "calculate_total(x)", "recalculate(x)", "precompute(x)"],
)
def test_a_genuine_calculation_is_still_caught(call: str) -> None:
    """The other direction: a narrowed predicate that caught nothing would also pass.

    ``recalculate`` and ``precompute`` are the reason the longer tokens stay
    substring matches, and ``totalSum`` is why the word split handles camelCase.
    """
    assert _is_calculation(_expression(call))


def test_arithmetic_is_a_calculation_whatever_it_is_called() -> None:
    """An operator needs no name to compute a base."""
    assert _is_calculation(_expression("base - deductions"))
    assert _is_calculation(_expression("-base"))


def test_a_calculation_nested_in_an_argument_is_found() -> None:
    """Wrapping a computation in a coercion does not make it transcription."""
    assert _is_calculation(_expression("Decimal(calculate_total(rows))"))


def test_reading_a_stated_document_value_is_transcription() -> None:
    """The distinction the audit exists to draw: read versus derive."""
    assert _is_transcribed_value(_expression("element.text"))
    assert _is_transcribed_value(_expression("findtext('base')"))
    assert _is_transcribed_value(_expression("Decimal(element.text)"))


def test_a_computed_value_is_not_transcription() -> None:
    """A coercion around arithmetic is still arithmetic."""
    assert not _is_transcribed_value(_expression("base - deductions"))


@pytest.mark.parametrize("target", ["tax_base", "taxable_base", "self.tax_base", "TAX_BASE"])
def test_the_tax_base_target_is_recognised(target: str) -> None:
    """Case and attribute access both name the same audited value."""
    assert _is_tax_base_target(_expression(target))


def test_an_unrelated_target_is_not_the_tax_base() -> None:
    """Otherwise every assignment in an adapter becomes a candidate leak."""
    assert not _is_tax_base_target(_expression("total"))


@pytest.mark.parametrize(
    "path",
    [
        "src/cadrumo/adapters/inbound/declaracion/reader.py",
        "src/cadrumo/entrypoints/cli/modelo/work.py",
        "src" + chr(92) + "cadrumo" + chr(92) + "adapters" + chr(92) + "reader.py",
    ],
)
def test_a_calculation_in_an_adapter_or_entrypoint_is_a_violation(path: str) -> None:
    """Including the Windows-separated form, since paths arrive both ways here."""
    assert is_violation(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/cadrumo/domain/calculations/registry/schema.py",
        "src/cadrumo/adapters/inbound/declaracion/tests/test_reader.py",
        "src/cadrumo/entrypoints/cli/test_work.py",
        "src/cadrumo/adapters/outbound/config.yml",
    ],
)
def test_domain_code_tests_and_documents_are_not_violations(path: str) -> None:
    """Domain code is where calculation belongs; tests and data are not code leaks."""
    assert not is_violation(path)


def test_identifier_words_split_on_both_conventions() -> None:
    """The word split is what makes the short token safe, so it is pinned directly."""
    assert _name_words("resume_profile_session") == {"resume", "profile", "session"}
    assert _name_words("totalSum") == {"total", "sum"}
    assert _name_words("sum") == {"sum"}
