"""CLI surface tests for the ``aeat app ledger`` command tree.

contract: Pin the id-prefix fallthrough locale path.

The catch-all branch in ``_resolve_id`` routes unknown
``TransactionIdPrefixError`` messages through the locale catalogue
under the key ``cli.ledger.errors.id_prefix_unknown``.  These tests
verify:

1. The key exists in every supported locale catalogue and interpolates
   the ``%{message}`` placeholder.
2. The key is distinct across all four locales (no silent identical-
   translation regression).
"""

from __future__ import annotations

import pytest

from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_KEY = "cli.ledger.errors.id_prefix_unknown"
_SENTINEL = "synthetic-unforeseen-domain-error"


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_id_prefix_unknown_key_renders_per_locale(locale: str) -> None:
    """``cli.ledger.errors.id_prefix_unknown`` renders in every supported locale.

    The key must exist in each catalogue, accept the ``message``
    interpolation parameter, and embed the sentinel value so the
    operator sees the original error detail rather than a blank
    placeholder.
    """
    rendered = tr(_KEY, locale=locale, message=_SENTINEL)

    assert rendered, f"locale={locale!r}: got empty string"
    assert _SENTINEL in rendered, (
        f"locale={locale!r}: sentinel {_SENTINEL!r} not found in rendered "
        f"output {rendered!r}; the %{{message}} placeholder may be missing "
        f"from the {locale} catalogue entry."
    )
    # Reject the raw key falling through as the translation value.
    assert rendered != _KEY, (
        f"locale={locale!r}: tr() returned the key itself, indicating the key is missing from the {locale} catalogue."
    )


def test_id_prefix_unknown_key_distinguishes_locales() -> None:
    """The ``id_prefix_unknown`` rendering differs across at least one locale pair.

    All four translations must not collapse to an identical string —
    that would indicate one or more entries are copy-pasted without
    translation.
    """
    rendered_values = {locale: tr(_KEY, locale=locale, message=_SENTINEL) for locale in SUPPORTED_OUTPUT_LANGUAGES}
    # At minimum the prefix of the message (before the sentinel) should
    # differ across locales since each catalogue has its own phrasing.
    prefixes = {v.split(_SENTINEL)[0] for v in rendered_values.values()}
    assert len(prefixes) > 1, (
        "All locales rendered identical text before the sentinel — the "
        "translations may be untranslated copies:\n"
        + "\n".join(f"  {loc}: {val!r}" for loc, val in rendered_values.items())
    )
