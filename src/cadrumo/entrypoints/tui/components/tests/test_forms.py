"""Public facade contract for immutable TUI form components."""

from __future__ import annotations

import pytest

from cadrumo.entrypoints.tui.components import (
    FormChoice,
    FormField,
    FormFieldKind,
    FormPage,
    form_choices,
    multi_choice_tokens,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_form_contracts_resolve_once_through_the_owner_facade() -> None:
    """Cross-package consumers receive the canonical form definitions."""

    assert FormChoice.__module__.endswith(".components.forms")
    assert FormField.__module__.endswith(".components.forms")
    assert FormFieldKind.__module__.endswith(".components.forms")
    assert FormPage.__module__.endswith(".components.forms")
    assert form_choices((("yes", "Yes"),)) == (FormChoice("yes", "Yes"),)
    assert multi_choice_tokens("a,,b") == ("a", "b")
