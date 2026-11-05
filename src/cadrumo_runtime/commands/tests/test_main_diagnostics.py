"""Runtime refusals log durably only after the admitted leaf behavior starts."""

from __future__ import annotations

from inspect import signature
from types import SimpleNamespace

import pytest

from cadrumo_client.commands.errors import CliRefusedBoundaryError, CliUnexpectedBoundaryError
from cadrumo_runtime.commands import main as runtime_main

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("phase", ["admission", "behavior"])
@pytest.mark.parametrize("unexpected", [False, True])
def test_runtime_failure_durability_follows_actual_handler_entry(
    monkeypatch: pytest.MonkeyPatch, phase: str, *, unexpected: bool
) -> None:
    error = (
        RuntimeError("fixture handler failed")
        if unexpected
        else CliRefusedBoundaryError(translated_message="errors.refused.refused_cli_validation_boundary")
    )
    spec = next(
        spec for spec in runtime_main.RUNTIME_COMMAND_GRAPH.by_schema_identity().values() if spec.kind == "leaf"
    )

    def refuse() -> None:
        raise error

    def dispatch(graph, selected, bound, behavior):
        if phase == "admission":
            raise error
        return behavior()

    def compiled_command(graph, *, dispatcher):
        def run(**kwargs):
            return dispatcher(graph, spec, signature(refuse).bind(), refuse)

        return SimpleNamespace(main=run)

    records = []
    was_deferred = runtime_main.logging_configuration_deferred()

    def log(boundary, failure, *, durable):
        assert runtime_main.logging_configuration_deferred() is (phase == "admission")
        records.append((boundary, failure, durable))
        return "fixture-trace"

    monkeypatch.setattr(runtime_main, "dispatch_runtime_behavior", dispatch)
    monkeypatch.setattr(runtime_main, "build_command_app", compiled_command)
    monkeypatch.setattr(runtime_main, "get_command", lambda app: app)
    monkeypatch.setattr(runtime_main, "log_cli_boundary_failure", log)
    monkeypatch.setattr(runtime_main, "render_error", lambda *args, **kwargs: 2)
    monkeypatch.setattr(runtime_main, "register_client_logging_namespace", lambda: None)
    monkeypatch.setattr(runtime_main, "configure_stdio_for_utf8", lambda: None)
    monkeypatch.setattr(runtime_main, "disable_rich_cli_rendering", lambda: None)

    assert runtime_main.run_command([]) == 2
    assert runtime_main.logging_configuration_deferred() is was_deferred
    assert len(records) == 1
    boundary, logged_error, durable = records[0]
    assert boundary == "runtime_cli"
    assert durable is (phase == "behavior")
    if unexpected:
        assert isinstance(logged_error, CliUnexpectedBoundaryError)
        assert logged_error.original_exception is error
    else:
        assert logged_error is error
