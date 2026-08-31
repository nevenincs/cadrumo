"""H5 conformance gate: the declared MCP localization boundary.

The localization policy rules the boundary
explicitly, so the next audit does not read English tool descriptions as locale
drift and the locale-parity gates know where their remit stops:

- The **model-facing** surface is deliberately English. Tool NAMES and tool
  DESCRIPTIONS built by :func:`build_tool_descriptors` are assembled from
  ASCII English (an ``aeat app ...`` command form plus the family's English
  ``operator_question`` intent); they never flow through :func:`tr`, so they do
  not change with the operator's configured output language.
- The **operator-facing** surface is localized. Elicitation prompts and refusal
  messages (``confirmation_request`` / ``refusal_message``) render through the
  locale catalogues via :func:`tr`, so a Spanish operator reads Spanish prose
  (accented characters -> non-ASCII).

The gate locks both halves: descriptions/names stay ASCII and are byte-identical
across output languages (proving they are not localized), while at least one
operator-facing message genuinely differs and turns non-ASCII under a non-English
locale (proving the localization machinery is real and would be caught by the
ASCII check if a description ever flowed through it).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from cadrumo.core.config import override_settings
from cadrumo.core.i18n._render import clear_output_language_cache

from .._elicitation import ConfirmRoute, confirmation_request, refusal_message
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_HANDOFF = "modelo.export"


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


def test_tool_names_and_descriptions_are_ascii_english() -> None:
    # Every model-facing tool name and description is ASCII English: no localized
    # Spanish prose (which would carry accented, non-ASCII characters) reaches the
    # surface the model reads.
    with _output_language("en"):
        descriptors = build_tool_descriptors()

    assert descriptors, "no tool descriptors were built"
    non_ascii_names = [d.name for d in descriptors if not d.name.isascii()]
    non_ascii_descriptions = [d.command_key for d in descriptors if not d.description.isascii()]
    assert non_ascii_names == [], f"non-ASCII tool names leak localization: {non_ascii_names}"
    assert non_ascii_descriptions == [], f"non-ASCII tool descriptions leak localization: {non_ascii_descriptions}"
    # Descriptions are non-empty model-facing prose, not blank stubs.
    assert all(d.description.strip() for d in descriptors)


def test_descriptions_do_not_flow_through_localization() -> None:
    # The strongest proof the model-facing surface is NOT localized: rebuilding
    # the descriptors under a Spanish output language yields byte-identical names
    # and descriptions. If any description rode ``tr()`` it would change here.
    with _output_language("en"):
        english = {d.command_key: (d.name, d.description) for d in build_tool_descriptors()}
    with _output_language("es"):
        spanish = {d.command_key: (d.name, d.description) for d in build_tool_descriptors()}

    assert english == spanish, "tool names/descriptions changed with output language (unexpected localization)"
    # And still ASCII under the Spanish locale.
    with _output_language("es"):
        assert all(d.description.isascii() and d.name.isascii() for d in build_tool_descriptors())


def test_operator_facing_messages_are_localized() -> None:
    # Positive control + anti-tautology: the operator-facing elicitation and
    # refusal strings DO ride ``tr()``. Under English they are ASCII; under
    # Spanish they differ and turn non-ASCII (accented prose). This proves the
    # ASCII assertion above is discriminating: a localized description would be
    # caught by it.
    with _output_language("en"):
        english_confirm = confirmation_request(command_key=_HANDOFF).message
        english_refusal = refusal_message(ConfirmRoute.REFUSE_BLOCKED, command_key=_HANDOFF)
    with _output_language("es"):
        spanish_confirm = confirmation_request(command_key=_HANDOFF).message
        spanish_refusal = refusal_message(ConfirmRoute.REFUSE_BLOCKED, command_key=_HANDOFF)

    assert english_confirm.isascii(), "English confirmation prose should be ASCII"
    assert english_refusal.isascii(), "English refusal prose should be ASCII"
    assert not spanish_confirm.isascii(), "Spanish confirmation prose should carry accented (non-ASCII) characters"
    assert not spanish_refusal.isascii(), "Spanish refusal prose should carry accented (non-ASCII) characters"
    assert english_confirm != spanish_confirm, "confirmation message is not localized across locales"
    assert english_refusal != spanish_refusal, "refusal message is not localized across locales"
    # The command key (a stable model-facing identifier) is interpolated verbatim
    # into both localized renderings — the identifier axis is never translated.
    assert _HANDOFF in spanish_confirm
    assert _HANDOFF in spanish_refusal
