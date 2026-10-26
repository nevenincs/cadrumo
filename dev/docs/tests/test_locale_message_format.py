"""Keep percentage prose translatable without dropping real format contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..locale_message_format import _validate_format_contract
from ..locale_mutation_contracts import DocumentationLocaleMutationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.mark.parametrize(
    "translated",
    [
        "24%-os általános kulcs; 2026-ban 13.5%, januártól pedig 12%.",
        "Un tipo general del 24%; 13.5% en 2026 y 12% a partir de enero.",
    ],
)
def test_numeric_percentage_prose_can_change_language(translated: str) -> None:
    """Rate descriptions and Hungarian percentage suffixes are ordinary prose."""
    source = "A 24% standard rate; 13.5% in 2026 and 12% from January."
    _validate_format_contract(source, "", translated, Path("rates.po"), ("", source))


@pytest.mark.parametrize(
    ("source", "translated"),
    [
        ("A 24% standard rate: %s", "24%-os általános kulcs: %d"),
        ("Value: 100%s", "Érték: 100%d"),
        ("Value: 100% f", "Érték: 100% d"),
        ("Value: % d", "Érték: % s"),
        ("Value: %-f", "Valor: %f"),
        ("Value: %(amount).2f", "Érték: %(total).2f"),
    ],
)
def test_real_percent_placeholders_still_require_exact_preservation(source: str, translated: str) -> None:
    """Prose classification must not hide changed Python conversions."""
    with pytest.raises(DocumentationLocaleMutationError, match="percent placeholder mismatch"):
        _validate_format_contract(source, "", translated, Path("rates.po"), ("", source))


def test_numeric_percentage_inside_code_is_still_an_exact_literal() -> None:
    """Inline code remains immutable even when it resembles percentage prose."""
    source = "Example: `24% standard`."
    with pytest.raises(DocumentationLocaleMutationError, match="inline backtick role/literal mismatch"):
        _validate_format_contract(source, "", "Példa: `24%-os általános`.", Path("rates.po"), ("", source))


def test_percent_format_prose_can_change_language() -> None:
    """Naming the formatting mechanism does not introduce a float placeholder."""
    source = "Messages, %-format arguments, exceptions; actual value: %-f."
    translated = "Mensajes, argumentos de formato %, excepciones; valor real: %-f."
    _validate_format_contract(source, "", translated, Path("logging.po"), ("", source))


def test_percent_format_inside_code_is_still_an_exact_literal() -> None:
    """A prose exception never relaxes the separate literal contract."""
    source = "Example: `%-format`."
    with pytest.raises(DocumentationLocaleMutationError, match="inline backtick role/literal mismatch"):
        _validate_format_contract(source, "", "Ejemplo: `formato %`.", Path("logging.po"), ("", source))
