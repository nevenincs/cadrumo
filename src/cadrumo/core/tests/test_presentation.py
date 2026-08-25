"""Contracts for layer-neutral immutable presentation values."""

from __future__ import annotations

import pytest

from ..presentation import FormChoice, FormField, FormFieldKind, FormPage, form_choices, multi_choice_tokens

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_form_contracts_resolve_once_through_the_neutral_owner() -> None:
    """Every entrypoint receives the same canonical form definitions."""
    assert FormChoice.__module__ == "cadrumo.core.presentation"
    assert FormField.__module__ == "cadrumo.core.presentation"
    assert FormFieldKind.__module__ == "cadrumo.core.presentation"
    assert FormPage.__module__ == "cadrumo.core.presentation"
    assert form_choices((("yes", "Yes"),)) == (FormChoice("yes", "Yes"),)
    assert multi_choice_tokens("a,,b") == ("a", "b")
