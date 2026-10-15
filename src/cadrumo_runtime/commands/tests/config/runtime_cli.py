"""Invocation helper that exercises the real cadrumo-runtime command parser."""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from typing import NotRequired, TypedDict, Unpack

import click
from click.testing import CliRunner, Result
from pydantic import ConfigDict

from cadrumo.core.json_contract import ENVELOPE_SCHEMA_VERSION, OutputSchema, SchemaEnvelope
from cadrumo.core.type_guards import is_str_keyed_dict
from cadrumo_runtime.commands.main import main


class _ArbitraryCommandResult(OutputSchema):
    """Validate the shared envelope while allowing each registered result body."""

    model_config = ConfigDict(extra="allow", frozen=True, strict=True, validate_assignment=True)


class RuntimeInvokeKwargs(TypedDict, total=False):
    """Supported Click runner options for one runtime command invocation."""

    env: NotRequired[dict[str, str | None] | None]
    color: NotRequired[bool]
    catch_exceptions: NotRequired[bool]
    input: NotRequired[str | bytes | None]
    obj: NotRequired[object]


@cache
def _runtime_command() -> click.Command:
    """Expose raw runtime argv to its production parser and error boundary."""

    @click.command(
        add_help_option=False,
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
        },
    )
    @click.argument("runtime_args", nargs=-1, type=click.UNPROCESSED)
    def invoke(runtime_args: tuple[str, ...]) -> None:
        exit_code = main(runtime_args)
        if exit_code:
            raise click.exceptions.Exit(exit_code)

    return invoke


_RUNNER = CliRunner()


def invoke_runtime_cli(args: Sequence[str], **kwargs: Unpack[RuntimeInvokeKwargs]) -> Result:
    """Run one command through ``cadrumo_runtime.commands.main.main``."""
    return _RUNNER.invoke(_runtime_command(), list(args), **kwargs)


def unwrap_cli_result(result: Result) -> dict[str, object]:
    """Validate and unwrap the standard success envelope emitted by runtime commands."""
    envelope = SchemaEnvelope[_ArbitraryCommandResult].model_validate_json(result.output)
    if envelope.schema_version != ENVELOPE_SCHEMA_VERSION:
        raise ValueError(f"unsupported runtime CLI envelope version: {envelope.schema_version!r}")
    value = envelope.result.model_dump(mode="json")
    if not is_str_keyed_dict(value):
        raise TypeError("runtime CLI result envelope body must be an object")
    return value
