"""Smoke check for the ``--assemble-observations`` flag on
``aeat config google sync calc pull``.

Guards three regressions:
- The flag stays registered on the typer command (rename or
  accidental delete would surface here, not silently at runtime).
- The localized help text resolves through ``tr()`` rather than
  falling back to the literal translation key.
- The flag default remains ``False`` so existing callers that omit
  it keep their fast-path behavior (no extra assembler dispatch).
"""

from __future__ import annotations

import inspect

import pytest

from .._google import google_sync_calc_pull

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_assemble_observations_flag_is_registered_on_pull_command() -> None:
    signature = inspect.signature(google_sync_calc_pull)
    assert "assemble_observations" in signature.parameters, (
        "google_sync_calc_pull must declare an `assemble_observations` parameter "
        "so the operator-facing CLI can invoke the row-set assembler"
    )


def test_assemble_observations_flag_defaults_to_false() -> None:
    signature = inspect.signature(google_sync_calc_pull)
    parameter = signature.parameters["assemble_observations"]
    default = parameter.default
    # `default` is a typer.Option; the underlying default value is on `.default`.
    underlying_default = getattr(default, "default", default)
    assert underlying_default is False, (
        f"--assemble-observations default must be False so existing pull callers "
        f"are not slowed down by the assembler dispatch; got {underlying_default!r}"
    )


def test_assemble_observations_flag_help_resolves_through_tr() -> None:
    signature = inspect.signature(google_sync_calc_pull)
    parameter = signature.parameters["assemble_observations"]
    help_text = getattr(parameter.default, "help", "") or ""
    # The translation key string would be something like
    # "cli.config.google.sync.calc.pull.assemble_observations_help".
    # Real Spanish output is e.g. "Tras recuperar, reensambla las celdas...".
    assert help_text, "--assemble-observations help text must be non-empty"
    assert "cli.config.google.sync.calc.pull.assemble_observations_help" not in help_text, (
        "help text fell back to the raw translation key — the locale catalogue is missing "
        "an entry for the active language"
    )
