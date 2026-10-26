"""Proofs for the closed set of setup items the surfaces name."""

from __future__ import annotations

import pytest

from ..dependency_contracts import DependencyItemKind
from ..dependency_registry import LOCAL_AI_DECLARATION, dependency_item_declarations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_declarations_are_the_browser_then_the_local_ai_and_nothing_of_the_profile() -> None:
    declarations = dependency_item_declarations()
    assert [declaration.item_id for declaration in declarations] == ["browser", "local_ai"]
    assert [declaration.kind for declaration in declarations] == list(DependencyItemKind)
    assert LOCAL_AI_DECLARATION.display_key == "provisioning.dependency.local_ai.name"
    assert {declaration.recovery_action_id for declaration in declarations} == {
        "operator.provision.browser",
        "operator.provision.local_ai",
    }
