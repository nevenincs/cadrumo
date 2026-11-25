"""The recorded operations of each action target are the ones the command-operation table lists."""

from __future__ import annotations

import pytest

from cadrumo_client.contracts.command_program import CommandProgram

from ....application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ....application.operator_surface.action_target_operations import (
    ACTION_TARGET_OPERATION_IDS,
    target_operation_ids,
)
from ....application.operator_surface.action_targets import ACTION_TARGETS
from ..command_operation_table import COMMAND_OPERATION_ROWS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _table_operations(cli_path: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(operation for path, operation in COMMAND_OPERATION_ROWS if path == cli_path and operation is not None)


def test_each_action_target_records_exactly_the_operations_its_command_submits() -> None:
    expected = {
        target.command_key: operations
        for target in ACTION_TARGETS
        if target.program is CommandProgram.AEAT and (operations := _table_operations(target.cli_path))
    }

    assert dict(ACTION_TARGET_OPERATION_IDS) == expected


def test_every_catalogue_target_is_a_recorded_action_target() -> None:
    recorded = {target.command_key for target in ACTION_TARGETS}

    assert {entry.target_command_key for entry in OPERATOR_ACTION_CATALOGUE.entries} <= recorded


def test_one_several_and_no_operations_are_served_in_table_order() -> None:
    assert target_operation_ids("modelo.iva_wallet.override") == ("modelo.iva-wallet.override",)
    assert target_operation_ids("modelo.work.calculate") == ("modelo.work.calculate", "modelo.work.metadata")
    assert target_operation_ids("config.profile.list") == ()
    assert target_operation_ids("config.auth.login") == ()
