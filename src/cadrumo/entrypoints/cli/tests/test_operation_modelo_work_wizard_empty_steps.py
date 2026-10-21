"""Empty wizard discovery stays frontend-free at the CLI flow boundary."""

from __future__ import annotations

from typing import cast

import pytest

from cadrumo.application.modelo.work_wizard import ModeloWorkWizardRun
from cadrumo.entrypoints.cli import _modelo_work_wizard_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_empty_step_sequence_does_not_construct_a_frontend(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_frontend(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("empty step sequence must not construct a frontend")

    monkeypatch.setattr(_modelo_work_wizard_cli, "LineFlowFrontend", unexpected_frontend)
    wizard = cast(ModeloWorkWizardRun, object())

    assert _modelo_work_wizard_cli._run_wizard_steps(wizard, ()) == ()
