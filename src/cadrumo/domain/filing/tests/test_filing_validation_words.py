"""Filing record refusals carry catalogue words in every supported locale.

The schema models raise their cross-field refusals as registered errors; the
pydantic boundary keeps the registered error as the cause of the ``ValueError``
it hands pydantic, so the words are read from that cause.
"""

from __future__ import annotations

import ast
import re
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.aggregation import BindingSourceKind
from ....core.errors.error_codes import resolve_error_message
from ....core.i18n.render import tr
from ..errors import FilingValidationError
from ..schema import (
    ModeloBindingValue,
    ModeloValue,
    ModeloValueKind,
    _require_unique_binding_coordinates,
    _require_unique_casilla_coordinates,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_LOCALES = ("en", "es", "ca", "hu")
_SCHEMA = Path(__file__).resolve().parents[1] / "schema.py"
_PLACEHOLDER = re.compile(r"%\{(\w+)\}")


def _assert_words(error: BaseException) -> None:
    key = getattr(error, "translated_message", None)
    assert isinstance(key, str) and key
    for locale in _LOCALES:
        words = resolve_error_message(error, locale=locale)
        assert words, (locale, key)
        assert words != key, (locale, key)
        assert "%{" not in words, (locale, words)


def _registered_cause(raised: ValidationError) -> BaseException:
    cause = raised.errors()[0]["ctx"]["error"].__cause__
    assert isinstance(cause, FilingValidationError)
    return cause


def test_empty_kind_with_a_value_refusal_is_catalogue_words() -> None:
    with pytest.raises(ValidationError) as raised:
        ModeloValue(casilla_id="03", value=Decimal("1"), kind=ModeloValueKind.EMPTY, source="registry schema")
    _assert_words(_registered_cause(raised.value))


def test_literal_kind_with_a_trace_refusal_is_catalogue_words() -> None:
    with pytest.raises(ValidationError) as raised:
        ModeloValue(
            casilla_id="03",
            value=Decimal("1"),
            kind=ModeloValueKind.LITERAL,
            source="registry input",
            formula_trace_casilla_ids=(),
        )
    cause = _registered_cause(raised.value)
    _assert_words(cause)
    for locale in _LOCALES:
        assert "03" in resolve_error_message(cause, locale=locale)


def test_repeated_casilla_refusal_names_the_casilla() -> None:
    values = tuple(
        ModeloValue(casilla_id="07", value=Decimal(1), kind=ModeloValueKind.LITERAL, source="registry input")
        for _ in range(2)
    )
    with pytest.raises(FilingValidationError) as raised:
        _require_unique_casilla_coordinates(values)
    _assert_words(raised.value)
    for locale in _LOCALES:
        assert "07" in resolve_error_message(raised.value, locale=locale)


def test_repeated_binding_refusal_names_the_binding() -> None:
    values = tuple(
        ModeloBindingValue(
            binding_id="b-one",
            value=Decimal(1),
            kind=ModeloValueKind.LITERAL,
            source=BindingSourceKind.MANUAL_INPUT,
            legal_refs=("ley-35-2006:art-99",),
            source_refs=("aeat-dr-130-2019",),
            row_index=2,
        )
        for _ in range(2)
    )
    with pytest.raises(FilingValidationError) as raised:
        _require_unique_binding_coordinates(values)
    _assert_words(raised.value)
    for locale in _LOCALES:
        assert "b-one" in resolve_error_message(raised.value, locale=locale)


def test_every_key_the_schema_names_renders_words_in_all_locales() -> None:
    tree = ast.parse(_SCHEMA.read_text(encoding="utf-8"))
    keys = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("errors.integrity.")
    }
    assert len(keys) == 12
    for key in sorted(keys):
        english = tr(key, locale="en")
        assert english != key, key
        fill = {name: "x" for name in _PLACEHOLDER.findall(english)}
        for locale in _LOCALES:
            words = tr(key, locale=locale, **fill)
            assert words and words != key, (locale, key)
            assert "%{" not in words, (locale, key, words)
