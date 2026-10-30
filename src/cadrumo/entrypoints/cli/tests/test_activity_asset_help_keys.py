"""Activity-asset read commands use a closed help-key vocabulary."""

from __future__ import annotations

import pytest

from .._app_ledger_actividad_asset_command_specs import _read_leaf

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("token", ["list", "plan", "timeline", "form-options", "acquisition-candidates"])
def test_read_command_help_keeps_its_canonical_key(token: str) -> None:
    command = _read_leaf(token)
    assert command.help_key is not None
    assert command.help_key.value == f"cli.app.ledger.actividad_asset.{token.replace('-', '_')}_help"


@pytest.mark.parametrize("token", ["unknown", "list_help", "form_options", ""])
def test_unknown_read_command_cannot_construct_a_locale_key(token: str) -> None:
    with pytest.raises(KeyError):
        _read_leaf(token)
