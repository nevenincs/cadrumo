"""An operator-named supply-nature model is selected whatever this computer's free memory says.

The supply-nature role resolves through catalogue selection like the column
mapper: left at its default, the catalogue picks the smallest candidate this
computer's free memory admits; named, the model is honoured. The hardware
reaching these selections is injected through
:func:`~application.provisioning.probe_hardware_profile`'s own arguments, so
nothing about this host's memory can decide a result.
"""

from __future__ import annotations

import pytest

from ...core.hardware import AcceleratorKind
from ...core.model_catalogue import ModelRole, candidates_for_role, default_model_runtime_id
from ...tests.fixtures.settings import EnvFileFreeSettings
from ..local_reader import select_role_model
from ..provisioning import AcceleratorReading, HardwareProfile, SystemMemoryReading, probe_hardware_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROLE = ModelRole.SUPPLY_NATURE_PROPOSAL
_NAMED = next(
    candidate.runtime_id
    for candidate in candidates_for_role(_ROLE)
    if candidate.runtime_id != default_model_runtime_id(_ROLE)
)


def _starved() -> HardwareProfile:
    """A computer with far less free memory than any supply-nature candidate needs."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=16 * 1024**3, free_bytes=64 * 1024**2),
        accelerator=AcceleratorReading(kind=AcceleratorKind.NONE, detail="injected: no devices"),
    )


def test_the_default_setting_leaves_the_choice_to_the_catalogue_and_its_headroom_bar() -> None:
    """Control: without a named model a starved computer selects nothing and setup cannot change that."""
    selection = select_role_model(_ROLE, EnvFileFreeSettings(), profile=_starved())

    assert not selection.selected
    assert selection.precondition_verdict is not None
    assert selection.precondition_verdict.action is None


def test_a_named_model_is_selected_whatever_the_free_memory() -> None:
    settings = EnvFileFreeSettings(cadrumo_llm_ollama_supply_nature_model=_NAMED)

    selection = select_role_model(_ROLE, settings, profile=_starved())

    assert selection.selected
    assert selection.runtime_id == _NAMED
