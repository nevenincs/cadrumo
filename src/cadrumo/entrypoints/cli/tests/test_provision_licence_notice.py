"""Restricted overrides retain a visible warning on real provisioning paths."""

from __future__ import annotations

import json

import pytest
import typer
import typer.main

from ....core.config import override_settings
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.model_catalogue import ModelRole, candidates_for_role
from ..config.provision_cli import provision_pull, provision_verify

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("emitter", [provision_pull, provision_verify])
@pytest.mark.parametrize("output_format", ["json", "text"])
def test_restricted_override_warning_reaches_operator_in_every_locale(
    emitter, output_format: str, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate = next(
        row for row in candidates_for_role(ModelRole.VISION_TRANSCRIPTION) if not row.licence.commercial_use_permitted
    )
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        context = typer.Context(typer.main.get_command(app), obj={"format": output_format})
        with (
            override_settings(
                cadrumo_output_language=locale, cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"
            ),
            pytest.raises(typer.Exit) as raised,
        ):
            emitter(context, model=candidate.runtime_id, role=ModelRole.VISION_TRANSCRIPTION)
        assert raised.value.exit_code == 2
        output = capsys.readouterr().out
        if output_format == "json":
            notices = json.loads(output)["notices"]
            warning = next(row for row in notices if row["code"] == "provisioning.model.licence.non_commercial")
            assert warning["severity"] == "warning"
            message = warning["message"]
        else:
            message = output
        assert candidate.runtime_id in message
        assert candidate.licence.name in message
        assert "provisioning.model.licence.non_commercial_advisory" not in message
        assert "%{" not in message
