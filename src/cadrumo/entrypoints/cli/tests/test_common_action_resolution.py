"""Real CLI bridge tests for fully materialised successful notice actions."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from ....application.operator_actions import ActionReference
from ....core.json_contract import (
    ActionArgumentSource,
    ActionArgumentStatus,
    Notice,
    NoticeSeverity,
    ResolvedActionArgument,
)
from .._common import (
    _action_text_lines,
    _powershell_action_token,
    _resolve_notice_actions,
    resolve_notice_action,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _render_action_line(
    *,
    action_id: str,
    argument_name: str,
    value: str,
    source_key: str,
) -> tuple[str, Notice]:
    action = resolve_notice_action(
        action=ActionReference(action_id=action_id),
        argument_bindings=(
            ResolvedActionArgument(
                argument_name=argument_name,
                status=ActionArgumentStatus.RESOLVED,
                value=value,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=source_key,
            ),
        ),
    )
    notice = Notice(
        severity=NoticeSeverity.INFO,
        code="test.action.rendering",
        message="Continue with the resolved action.",
        action=action,
    )
    resolved_notice = _resolve_notice_actions((notice,))[0]
    return _action_text_lines((resolved_notice,))[0], resolved_notice


def test_common_action_resolver_uses_the_live_surface_for_zero_and_required_inputs() -> None:
    zero_input_action = resolve_notice_action(
        action=ActionReference(action_id="operator.overview.status"),
    )

    assert zero_input_action.model_dump(mode="json") == {
        "action": {
            "action_id": "operator.overview.status",
            "target_command_key": "overview.status",
        },
        "argument_bindings": [],
    }

    with pytest.raises(ValueError, match=r"config\.profile\.sandbox\.restore: name"):
        resolve_notice_action(
            action=ActionReference(action_id="operator.profile.sandbox.restore"),
        )


def test_common_action_resolver_materialises_ledger_link_from_the_live_surface() -> None:
    action = resolve_notice_action(
        action=ActionReference(action_id="operator.ledger.link"),
        argument_bindings=(
            ResolvedActionArgument(
                argument_name="transaction_id",
                status=ActionArgumentStatus.RESOLVED,
                value="transaction-1",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="transaction_id",
            ),
            ResolvedActionArgument(
                argument_name="invoice_id",
                status=ActionArgumentStatus.RESOLVED,
                value="invoice-1",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="invoice_id",
            ),
        ),
    )

    assert action.action.target_command_key == "ledger.link"
    assert action.argument_bindings == (
        ResolvedActionArgument(
            argument_name="invoice_id",
            status=ActionArgumentStatus.RESOLVED,
            value="invoice-1",
            source=ActionArgumentSource.VERDICT_CONTEXT,
            source_key="invoice_id",
        ),
        ResolvedActionArgument(
            argument_name="transaction_id",
            status=ActionArgumentStatus.RESOLVED,
            value="transaction-1",
            source=ActionArgumentSource.VERDICT_CONTEXT,
            source_key="transaction_id",
        ),
    )


def test_common_action_resolver_accepts_modelo_calculate_verdict_context_binding() -> None:
    action = resolve_notice_action(
        action=ActionReference(action_id="operator.modelo.work.calculate"),
        argument_bindings=(
            ResolvedActionArgument(
                argument_name="work_unit_id",
                status=ActionArgumentStatus.RESOLVED,
                value="work-unit-1",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="work_unit_id",
            ),
        ),
    )

    assert action.model_dump(mode="json") == {
        "action": {
            "action_id": "operator.modelo.work.calculate",
            "target_command_key": "modelo.work.calculate",
        },
        "argument_bindings": [
            {
                "argument_name": "work_unit_id",
                "status": "resolved",
                "value": "work-unit-1",
                "source": "operator_action.verdict_context",
                "source_key": "work_unit_id",
                "source_evidence_id": None,
            },
        ],
    }


@pytest.mark.parametrize(
    ("value", "rendered"),
    (
        ("safe-token_1", "safe-token_1"),
        (r"C:\tmp\bundle.aeat", r"'C:\tmp\bundle.aeat'"),
        (r"C:\tmp folder\bundle.aeat", r"'C:\tmp folder\bundle.aeat'"),
        (r"C:\tmp\$(Write-Output PWN)\bundle.aeat", r"'C:\tmp\$(Write-Output PWN)\bundle.aeat'"),
        (r"C:\$env:TEMP\bundle.aeat", r"'C:\$env:TEMP\bundle.aeat'"),
        (r"C:\tmp\`quoted\bundle.aeat", r"'C:\tmp\`quoted\bundle.aeat'"),
        (r'''C:\tmp\"quoted"\bundle.aeat''', r"""'C:\tmp\"quoted"\bundle.aeat'"""),
        (r"C:\O'Brien\bundle.aeat", r"'C:\O''Brien\bundle.aeat'"),
    ),
)
def test_powershell_action_token_is_literal_under_the_real_shell(value: str, rendered: str) -> None:
    assert _powershell_action_token(value) == rendered

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    assert powershell is not None
    completed = subprocess.run(  # noqa: S603 - real-shell injection regression
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"& {{ param([string]$Value) [Console]::Out.Write($Value) }} {rendered}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == value


@pytest.mark.parametrize(
    ("action_id", "argument_name", "source_key", "value", "expected_tail"),
    (
        (
            "operator.profile.import",
            "path",
            "out",
            r"C:\tmp\$(Write-Output PWN)\bundle.aeat",
            r"config profile import 'C:\tmp\$(Write-Output PWN)\bundle.aeat'",
        ),
        (
            "operator.profile.login",
            "name",
            "name",
            "operator $env:USERNAME's profile",
            "config login 'operator $env:USERNAME''s profile'",
        ),
    ),
)
def test_action_text_uses_powershell_literal_arguments_and_preserves_json_binding(
    action_id: str,
    argument_name: str,
    source_key: str,
    value: str,
    expected_tail: str,
) -> None:
    line, notice = _render_action_line(
        action_id=action_id,
        argument_name=argument_name,
        value=value,
        source_key=source_key,
    )

    assert line == f"next_action\taeat {expected_tail}"
    assert notice.action is not None
    assert notice.action.argument_bindings[0].value == value
    assert notice.action.action.cli_path is not None
