"""Operator-facing refusal context labels render in the operator's language."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

from ...config import override_settings
from ...external_constants import OutputLanguage
from ...i18n.render import tr
from ..error_codes import ERROR_CONTEXT_LABEL_KEYS, INTERNAL_CONTEXT_KEYS, render_error_text
from ..hierarchy import InternalInvariantError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE_ROOT = Path(__file__).resolve().parents[3]

# Operator-facing keys that reach refusals from the CLI boundary or from many raise sites.
_OPERATOR_LABELS = (
    "remedy",
    "field",
    "path",
    "limit",
    "count",
    "value",
    "expected",
    "modelo",
    "period",
    "filing_year",
    "ejercicio",
)

# Frequent raise-site keys that name internals; their humanized fallback label is a diagnostic aid.
_DIAGNOSTIC_KEYS = frozenset(
    {
        "namespace",
        "stage",
        "cause_type",
        "op",
        "surface",
        "object_key",
        "method",
        "origin",
        "data_type",
        "action",
        "landing_url",
        "validation_rule",
        "effect",
        "error_type",
        "rate_kind",
        "divergence",
    }
)

_FREQUENT_KEY_COUNT = 10


def _refusal_lines(language: OutputLanguage, context: dict[str, str]) -> list[str]:
    with override_settings(cadrumo_output_language=language.value):
        rendered = render_error_text(InternalInvariantError("probe"), context=context)
    return rendered.splitlines()[1:]


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_remedy_label_is_translated_in_every_language(language: OutputLanguage) -> None:
    lines = _refusal_lines(language, {"remedy": "start the runtime"})
    remedy_line = next(line for line in lines if line.endswith(": start the runtime"))

    with override_settings(cadrumo_output_language=language.value):
        expected = tr("errors.context_labels.remedy")
    assert remedy_line == f"  {expected}: start the runtime"
    assert "Remedy" not in remedy_line
    if language is not OutputLanguage.EN:
        assert expected != "remedy"


@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("key", _OPERATOR_LABELS)
def test_operator_facing_context_keys_render_through_the_catalogue(language: OutputLanguage, key: str) -> None:
    lines = _refusal_lines(language, {key: "sample"})
    with override_settings(cadrumo_output_language=language.value):
        expected = tr(f"errors.context_labels.{key}")

    assert f"  {expected}: sample" in lines
    fallback = key.replace("_", " ").capitalize()
    if expected != fallback:
        assert f"  {fallback}: sample" not in lines


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_vocabulary_key_has_a_label_in_every_language(language: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=language.value):
        for key in ERROR_CONTEXT_LABEL_KEYS:
            label = tr(f"errors.context_labels.{key}")
            assert label.strip()
            assert label != f"errors.context_labels.{key}"


def test_vocabulary_is_unique_and_sorted() -> None:
    assert list(ERROR_CONTEXT_LABEL_KEYS) == sorted(set(ERROR_CONTEXT_LABEL_KEYS))


def _source_files() -> list[Path]:
    return [
        path
        for path in sorted(_SOURCE_ROOT.rglob("*.py"))
        if "tests" not in path.parts and not path.name.startswith("test_")
    ]


def _context_dict_keys(call: ast.Call) -> list[str]:
    keys: list[str] = []
    for keyword in call.keywords:
        if keyword.arg == "context" and isinstance(keyword.value, ast.Dict):
            keys.extend(
                key.value for key in keyword.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
    return keys


def _literal_context_keys() -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                counts.update(_context_dict_keys(node))
    return counts


def test_frequent_raise_site_context_keys_are_labelled_or_declared_diagnostic() -> None:
    unlabelled = sorted(
        key
        for key, count in _literal_context_keys().items()
        if count >= _FREQUENT_KEY_COUNT
        and not key.endswith(("_id", "_ids"))
        and key not in ERROR_CONTEXT_LABEL_KEYS
        and key not in INTERNAL_CONTEXT_KEYS
        and key not in _DIAGNOSTIC_KEYS
    )

    assert unlabelled == []
