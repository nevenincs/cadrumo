"""Patch routing keeps installed edits on their injected persistence boundary."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ..commands import _run_wizard_persistence_path
from ..errors import WizardEditUnsupportedConsoleError
from ..models import WizardFlow
from ..patch_edit import cleared_profile_paths
from .registry_setup_flow_support import registry_setup_flow as registry_setup_flow

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_installed_patch_uses_injected_persister_without_opening_local_record(
    registry_setup_flow: WizardFlow,
) -> None:
    observed: list[tuple[str, dict[str, str], bool | None]] = []

    def persist(
        *, profile_id: str, supplied: Mapping[str, str], colegio_concertado: bool | None
    ) -> tuple[dict[str, str], bool]:
        observed.append((profile_id, dict(supplied), colegio_concertado))
        return {"withholding.colegio_concertado": "false"}, True

    with bundled_indexed_authority().operation() as operation:
        values, changed = _run_wizard_persistence_path(
            registry_setup_flow,
            "edit",
            {},
            {},
            scalar_profile_values={"withholding.colegio_concertado": "false"},
            quiet=False,
            accept_defaults=False,
            profile_name="existing",
            profile_id="existing-profile",
            operation=operation,
            patch_persister=persist,
        )
    assert observed == [("existing-profile", {}, False)]
    assert values == {"withholding.colegio_concertado": "false"}
    assert changed


def test_edit_without_noninteractive_opt_in_refuses_before_any_persistence(
    registry_setup_flow: WizardFlow,
) -> None:
    called = False

    def persist(
        *, profile_id: str, supplied: Mapping[str, str], colegio_concertado: bool | None
    ) -> tuple[dict[str, str], bool]:
        nonlocal called
        called = True
        return {}, False

    with bundled_indexed_authority().operation() as operation, pytest.raises(WizardEditUnsupportedConsoleError):
        _run_wizard_persistence_path(
            registry_setup_flow,
            "edit",
            {},
            {},
            scalar_profile_values={},
            quiet=False,
            accept_defaults=False,
            profile_name="existing",
            profile_id="existing-profile",
            operation=operation,
            patch_persister=persist,
        )
    assert not called


def test_explicit_blank_optional_question_is_retained_as_clear(registry_setup_flow: WizardFlow) -> None:
    optional = next(
        question
        for section in registry_setup_flow.sections
        for question in section.questions
        if question.profile_key is not None and not question.required
    )
    assert cleared_profile_paths(registry_setup_flow, {optional.id: " "}) == (optional.profile_key,)
    assert cleared_profile_paths(registry_setup_flow, {}) == ()
