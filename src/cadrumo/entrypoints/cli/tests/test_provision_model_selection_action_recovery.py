"""Typed CLI projection for model-selection refusals."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

import pytest
import typer
import typer.main

from ....application.provisioning import ProvisioningPreconditionCondition
from ....core.config import override_settings
from ....core.i18n.render import SUPPORTED_OUTPUT_LANGUAGES
from ....core.operator_action_enums import NoRecoveryOutcome
from .._config.provision_cli import _emit_provision_pull, _emit_provision_verify

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_Emitter = Callable[[typer.Context], None]


def _context(*, output_format: str) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    return typer.Context(typer.main.get_command(app), obj={"format": output_format})


def _invoke_refusal(
    emitter: _Emitter,
    *,
    locale: str,
    output_format: str,
    capsys: pytest.CaptureFixture[str],
) -> str:
    with (
        override_settings(
            cadrumo_llm_ollama_num_ctx=1_000_000,
            cadrumo_output_language=locale,
        ),
        pytest.raises(typer.Exit) as raised,
    ):
        emitter(_context(output_format=output_format))
    assert raised.value.exit_code == 2
    return capsys.readouterr().out


def _pull(ctx: typer.Context) -> None:
    _emit_provision_pull(ctx, model=None, role=None)


def _verify(ctx: typer.Context) -> None:
    _emit_provision_verify(ctx, model=None, role=None)


@pytest.mark.parametrize("emitter", [_pull, _verify])
def test_unsatisfied_model_selection_projects_the_exact_closed_outcome_in_every_locale(
    emitter: _Emitter,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline: dict[str, object] | None = None
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        output = _invoke_refusal(
            emitter,
            locale=locale,
            output_format="json",
            capsys=capsys,
        )
        envelope = cast(dict[str, object], json.loads(output))
        result = cast(dict[str, object], envelope["result"])
        action = cast(dict[str, object], result["precondition_action"])
        evidence = cast(list[dict[str, object]], action["evidence"])

        assert result["model"] is None
        assert result["facts"] == evidence[0]["values"]
        assert action["failed_condition_id"] == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE.value
        assert action["action"] is None
        assert action["no_recovery_outcome"] == NoRecoveryOutcome.OPERATOR_DECISION.value
        assert evidence[0]["condition_id"] == action["failed_condition_id"]
        assert cast(dict[str, object], result["facts"])["required_context_tokens"] == 1_000_000

        if baseline is None:
            baseline = result
        else:
            assert result == baseline


@pytest.mark.parametrize("emitter", [_pull, _verify])
def test_unsatisfied_model_selection_text_is_the_same_typed_projection_in_every_locale(
    emitter: _Emitter,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline: dict[str, object] | None = None
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        output = _invoke_refusal(
            emitter,
            locale=locale,
            output_format="text",
            capsys=capsys,
        )
        cells = dict(line.split("\t", 1) for line in output.splitlines())
        projection: dict[str, object] = {
            key.removeprefix("precondition_action."): json.loads(value)
            for key, value in cells.items()
            if key.startswith("precondition_action.")
        }

        assert projection["failed_condition_id"] == (ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE.value)
        assert projection["action"] is None
        assert projection["no_recovery_outcome"] == NoRecoveryOutcome.OPERATOR_DECISION.value
        if baseline is None:
            baseline = projection
        else:
            assert projection == baseline
