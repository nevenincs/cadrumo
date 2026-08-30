"""A registered error always carries readable text, however it was constructed.

``CadrumoError.__init__`` used to call ``super().__init__()`` with zero args
when no positional ``message`` was supplied, so ``str(exc)`` was the empty
string — not untranslated, empty. Measured across the tree, 556 raise sites
construct with ``translated_message`` only, so roughly one raise site in nine
produced an exception whose text was blank.

Most operator surfaces route through :func:`resolve_error_message`, which
resolves the translation key and never saw the blank. But a bare ``str(exc)``
reaches operators at several CLI boundaries, and reaches everyone in tracebacks
and logs, where an error with no readable text gives whoever meets it nothing
to act on.

The two properties below are load-bearing together: the text must be non-empty,
AND the canonical resolver's output must be unchanged. A fix that made
``str(exc)`` non-empty by disturbing what operators actually read would trade
one defect for a worse one.
"""

from __future__ import annotations

import pytest

from ...i18n import tr
from ...identity import IdentityError
from ..error_codes import resolve_error_message
from ..hierarchy import CadrumoError, CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TRANSLATION_KEY = "errors.identity.document_empty"


def _translated_only_error() -> CadrumoError:
    """Return a real registered error built the way 556 raise sites build one.

    :class:`IdentityError` is registered under ``INTEGRITY_IDENTITY_DOCUMENT``
    and is raised translated-message-only in production (the empty-document
    guard in :mod:`core.identity`), so it reproduces the exact construction
    shape under test. It is core-owned deliberately: the contract being
    measured belongs to :class:`CadrumoError`, so the test needs no error type
    from an outer layer to exercise it.
    """
    return IdentityError(translated_message=_TRANSLATION_KEY)


def test_translated_message_only_error_has_non_empty_text() -> None:
    """``str(exc)`` is never blank for a translated-message-only construction.

    This is the defect: the pre-fix base called ``super().__init__()`` with no
    args, so this assertion failed against the empty string.
    """
    error = _translated_only_error()

    assert str(error) != ""
    assert error.args


def test_blank_text_carries_the_translation_key_not_a_translation() -> None:
    """The stored fallback is the KEY, deliberately, not its rendered prose.

    Translating at construction would bind the text to the locale in force when
    the error was RAISED, while :func:`resolve_error_message` translates at
    render time. Storing the key keeps render-time localisation intact and
    leaves a stable, greppable identifier in logs where prose varies by locale.
    """
    error = _translated_only_error()

    assert str(error) == _TRANSLATION_KEY
    assert str(error) != tr(_TRANSLATION_KEY)


def test_resolver_output_is_unchanged_by_the_fallback() -> None:
    """The canonical operator-facing resolver still returns the translation.

    ``resolve_error_message`` checks ``translated_message`` before falling back
    to ``args[0]``, so populating ``args`` must not divert it onto the raw key.
    Without this, the fix could silently start showing operators translation
    keys at every surface that reads the resolver — the regression that would
    matter far more than the blank it replaced.
    """
    error = _translated_only_error()

    resolved = resolve_error_message(error)

    assert resolved == tr(_TRANSLATION_KEY)
    assert resolved != _TRANSLATION_KEY


def test_explicit_message_still_wins_over_the_translation_key() -> None:
    """A positional message is preserved; the fallback only fills a gap."""
    error = CoreValidationError("explicit operator text", translated_message=_TRANSLATION_KEY)

    assert str(error) == "explicit operator text"
    assert resolve_error_message(error) == tr(_TRANSLATION_KEY)


def test_error_with_neither_message_nor_key_is_still_constructible() -> None:
    """The no-argument construction stays legal and yields the empty string.

    Seven raise sites supply neither, and there is nothing to fall back to.
    They are honestly blank rather than newly broken, and the resolver still
    renders their registered code — so the fallback narrows the blank surface
    rather than pretending to eliminate it.
    """
    error = CoreValidationError()

    assert str(error) == ""
    assert resolve_error_message(error) != ""
