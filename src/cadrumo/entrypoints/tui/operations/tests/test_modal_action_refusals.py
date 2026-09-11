"""A refused cancel, apply, or reject tells the operator why.

Both handlers ended in a branch whose arms did nothing: on success they
returned, and on refusal control fell off the end of the method. The button
stayed enabled and the screen did not change, so the only feedback a refusal
produced was that pressing the control appeared to do nothing -- which reads as
an unresponsive widget rather than a decision, and the natural response is to
press it again. The detach handler next door acts on its outcome, which is what
made the omission look deliberate.

The copy is keyed off each refusal code's own enum value rather than a
hand-written table, so the enums decide which catalogue keys must exist. That
matters because ``tr`` does not raise on a missing key -- it humanises the last
segment -- so an unnamed code would render English-looking text in every locale
and nothing would fail. The coverage test here is what makes that impossible.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from .....application.operations.frontend_requests import (
    OperationCancellationRefusalCode,
    OperationResponseControlRefusalCode,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[4] / "locales"


def _refusal_codes() -> tuple[str, ...]:
    """Every code either control surface can refuse with."""
    return tuple(
        sorted(
            {member.value for member in OperationCancellationRefusalCode}
            | {member.value for member in OperationResponseControlRefusalCode},
        ),
    )


def _refusal_block(locale: str) -> dict[str, str]:
    """Read one catalogue's refusal wording, coerced rather than asserted.

    ``yaml.safe_load`` returns ``Any``; the comprehension makes the shape this
    module relies on concrete at the boundary instead of narrowing it with an
    ``assert`` that says nothing about the file's real contents.
    """
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "common.yml").read_text(encoding="utf-8"))
    return {str(code): str(text) for code, text in catalogue["operation"]["modal"]["refusal"].items()}


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_refusal_code_is_worded_in_every_supported_locale(locale: str) -> None:
    """A code with no copy renders a humanised token, not a translation."""
    block = _refusal_block(locale)

    missing = [code for code in _refusal_codes() if code not in block]
    assert not missing, f"{locale} has no wording for: {missing}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_refusal_copy_outlives_the_code_it_described(locale: str) -> None:
    """The other direction: retired codes must not leave copy behind.

    Without this the block would accumulate wording for refusals the product
    can no longer produce, which reads as reviewed coverage while naming
    nothing.
    """
    codes = set(_refusal_codes())

    assert not [key for key in _refusal_block(locale) if key not in codes]


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_refusal_wording_is_a_real_translation(locale: str) -> None:
    """Copy must be worded, not a placeholder or an echoed identifier."""
    for code, text in _refusal_block(locale).items():
        assert text.strip(), f"{locale}:{code} is blank"
        assert code not in text, f"{locale}:{code} echoes its own identifier"


def test_the_two_control_surfaces_agree_on_their_shared_codes() -> None:
    """Both enums declare the same wording for a refusal that means one thing.

    ``unknown_operation`` and ``stale_operation_revision`` appear on both
    surfaces. Keying copy off the value rather than off the enum class is what
    keeps a single meaning from acquiring two descriptions.
    """
    shared = {member.value for member in OperationCancellationRefusalCode} & {
        member.value for member in OperationResponseControlRefusalCode
    }

    assert shared == {"unknown_operation", "stale_operation_revision"}
    for locale in _LOCALES:
        block = _refusal_block(locale)
        assert all(code in block for code in shared)
