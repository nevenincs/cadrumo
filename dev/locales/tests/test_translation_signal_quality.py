"""Focused quality gates for translation prose heuristics."""

from __future__ import annotations

import pytest

from .._signal import _has_unaccented_word, _suspicious_translation_locales

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_similarity_ignores_stable_transport_tokens() -> None:
    source = "Uno de: app_prompted_and_accepted, app_prompted_not_accepted, app_did_not_prompt, operator_did_not_check."
    target = "Un de: app_prompted_and_accepted, app_prompted_not_accepted, app_did_not_prompt, operator_did_not_check."

    assert (
        _suspicious_translation_locales(
            "cli.phone_state",
            {"es": {"cli.phone_state": source}, "ca": {"cli.phone_state": target}},
        )
        == set()
    )


def test_unaccented_signal_ignores_structured_transport_fields() -> None:
    value = "Formato: NACIMIENTO=AAAA-MM-DD[,DECLARACION_PROPIA=true|false][,GASTOS_GUARDERIA=N]."

    assert not _has_unaccented_word("es", value)


def test_similarity_still_flags_long_copied_human_prose() -> None:
    source = "Importe total de la deducción tributaria aplicable en esta autoliquidación anual."

    assert _suspicious_translation_locales(
        "modelo.help",
        {"es": {"modelo.help": source}, "en": {"modelo.help": source}},
    ) == {"en"}
