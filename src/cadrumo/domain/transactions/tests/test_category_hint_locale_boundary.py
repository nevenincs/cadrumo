"""The classifier's category hints are pinned to Spanish, not the operator locale.

``_category_hint`` feeds :class:`CategoryChoice.hint`, which is spliced into the
LLM prompt body by ``_render_choices``. Its only consumer is the model, so it is
deliberately NOT localized: the classifier reasons over Spanish AEAT invoices,
and handing it Hungarian category names would silently degrade classification
accuracy for an operator who merely changed their display language.

That pin is a counter-intuitive exception, so it is the kind of thing a future
reader is tempted to "fix". These gates state the contract instead of leaving it
to a comment.

The assertions are structural — equality across locales, and a resolution check
that never names a translated string.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from ....core.config import override_settings
from ....core.i18n import clear_output_language_cache
from ...categories import SpendingCategory
from .._llm import _category_hint

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@contextmanager
def _output_language(language: str) -> Iterator[None]:
    """Pin ``cadrumo_output_language`` and flush the resolver cache on both edges."""
    with override_settings(cadrumo_output_language=language):
        clear_output_language_cache()
        try:
            yield
        finally:
            clear_output_language_cache()
    clear_output_language_cache()


def _hints() -> dict[SpendingCategory, str]:
    return {category: _category_hint(category, year=2025) for category in SpendingCategory}


def test_category_hints_do_not_follow_the_operator_language() -> None:
    """Rebuilding the hints under a different output language changes nothing.

    If any hint resolved through the operator's locale rather than the pin, the
    two mappings would diverge here.
    """
    with _output_language("es"):
        under_spanish = _hints()
    with _output_language("hu"):
        under_hungarian = _hints()
    with _output_language("en"):
        under_english = _hints()

    assert under_spanish == under_hungarian, (
        "category hints changed with the operator language; the prompt pin at "
        "_llm.py's _category_hint has been lost, and the classifier would be fed "
        "the operator's display language instead of AEAT Spanish"
    )
    assert under_spanish == under_english


def test_category_hints_carry_resolved_translations_not_key_fallbacks() -> None:
    """Anti-tautology control for the equality assertion above.

    Two catalogues that both fail to resolve a key return the same humanised
    fallback, so the equality test would pass vacuously on unauthored content —
    which is exactly the starting state this guards against. Require that the
    hints actually resolve, without asserting what they say.
    """
    with _output_language("hu"):
        hints = _hints()

    assert hints, "no spending categories were enumerated"
    unresolved = sorted(category.value for category, hint in hints.items() if "categories.registry." in hint)
    assert not unresolved, (
        f"category hints still contain unresolved registry keys for {unresolved}; "
        "the equality assertion above cannot discriminate while hints render as "
        "their own key or a humanised fragment of it"
    )
