"""Skipping an unmatchable rule, and reusing a redacted CLI string, never change the output."""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

import pytest

from ....tests.aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE
from ... import tests as core_tests_package
from ...classification.policies import RedactionRule, SensitivityClass, default_policy_for
from ...errors.hierarchy import RedactionError
from ..rules import (
    _CLI_STRING_CACHE_MAX_LENGTH,
    _REDACTION_KEY_SEPARATOR_RE,
    _apply_one,
    _redact_cli_string_uncached,
    default_rules_for,
    default_rules_for_class,
    normalise_redaction_key,
    redact,
    redact_for_cli_output,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Shapes every rule arm reacts to, including the spans the identity arms
#: exempt, so the corpus exercises matches, gated refusals and exemptions.
_SHAPES = (
    "B12345674",
    "12345678Z",
    "B.1234567.4",
    "ESB12345674 y",
    "de SE556677889901",
    "FR XX 999999999",
    "ES91 2100 0418 4502 0005 1332",
    "GB82WEST12345698765432",
    "2025-12-31T09:32:12.345678Z",
    "1470176e-bf82-490d-a09d-1234567890ab",
    f"{SEDE_ROOT_URL_FIXTURE}path?q=1",
    "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijk",
    "Cierre 2025",
    "Probe 3902",
    "line one\nB12345674 on line two",
)


#: The redaction suites this corpus harvests live beside the rest of the
#: ``core`` suites, so the directory is named through the owning test package
#: rather than through this module's own location.
_REDACTION_SUITE_ROOT = Path(core_tests_package.__path__[0])


@cache
def _corpus() -> tuple[str, ...]:
    """String constants of the redaction suites, plus combined shapes."""
    strings: set[str] = set(_SHAPES)
    strings.update(f"{left} {right}" for left in _SHAPES for right in _SHAPES)
    for path in (*_REDACTION_SUITE_ROOT.glob("test_redaction*.py"), Path(__file__)):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                strings.add(node.value)
    return tuple(sorted(strings))


def _unfiltered(value: str, rules: tuple[RedactionRule, ...]) -> str:
    for rule in rules:
        value = _apply_one(rule, value)
    return value


def _rule_sets() -> list[tuple[RedactionRule, ...]]:
    sets: list[tuple[RedactionRule, ...]] = []
    for sensitivity in SensitivityClass:
        try:
            sets.append(default_rules_for_class(sensitivity))
        except RedactionError:
            continue
    return [rules for rules in sets if rules]


def test_the_corpus_reaches_every_rule() -> None:
    """FIXTURE ANCHOR: every declared rule matches something, so skipping is really exercised."""
    rules = {rule.name: rule for rules in _rule_sets() for rule in rules}
    unmatched = [name for name, rule in rules.items() if all(_apply_one(rule, value) == value for value in _corpus())]

    assert len(_corpus()) >= 300
    assert unmatched == []


@pytest.mark.parametrize("rules", _rule_sets(), ids=lambda rules: "+".join(rule.name for rule in rules))
def test_prefiltered_redaction_equals_applying_every_rule(rules: tuple[RedactionRule, ...]) -> None:
    mismatches = [value for value in _corpus() if redact(value, rules=rules) != _unfiltered(value, rules)]

    assert mismatches == []


def test_the_cached_class_rules_are_the_policy_rules() -> None:
    for sensitivity in SensitivityClass:
        try:
            expected = default_rules_for(default_policy_for(sensitivity))
        except RedactionError:
            continue
        assert default_rules_for_class(sensitivity) == expected


@pytest.mark.parametrize("reveal_identifiers", [False, True])
def test_a_repeated_cli_string_redacts_as_a_fresh_one(reveal_identifiers: bool) -> None:
    mismatches = [
        value
        for value in _corpus()
        for _ in range(2)
        if redact_for_cli_output(value, reveal_identifiers=reveal_identifiers)
        != _redact_cli_string_uncached(value, reveal_identifiers)
    ]

    assert mismatches == []


def test_the_reveal_flag_is_part_of_what_is_reused() -> None:
    """STALE KEY: a string redacted under one reveal mode is not served to the other."""
    profile_path = "buckets/1470176e-bf82-490d-a09d-1234567890ab"

    hidden = redact_for_cli_output(profile_path)
    revealed = redact_for_cli_output(profile_path, reveal_identifiers=True)

    assert hidden != revealed
    assert redact_for_cli_output(profile_path) == hidden


def test_a_long_string_is_redacted_without_reuse() -> None:
    long_text = "B12345674 " * (_CLI_STRING_CACHE_MAX_LENGTH // 5)
    assert len(long_text) > _CLI_STRING_CACHE_MAX_LENGTH

    assert redact_for_cli_output(long_text) == _redact_cli_string_uncached(long_text, False)


@pytest.mark.parametrize(
    "key",
    ["tax_id", "Tax-ID", "  bucket id ", "ACTIVE.PROFILE", "Straße_Nr", "__", "", 7, None, ("tax", "id")],
)
def test_a_reused_key_fold_equals_a_fresh_one(key: object) -> None:
    expected = "" if key is None else _REDACTION_KEY_SEPARATOR_RE.sub("_", str(key).casefold()).strip("_")

    assert normalise_redaction_key(key) == expected
    assert normalise_redaction_key(key) == expected
