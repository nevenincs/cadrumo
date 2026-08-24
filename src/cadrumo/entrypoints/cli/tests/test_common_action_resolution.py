"""Real CLI bridge tests for fully materialised successful notice actions."""

from __future__ import annotations

import shutil

import anyio
import click
import pytest

from ....application.operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from ....core import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from ....core.json_contract import (
    Notice,
    NoticeSeverity,
    ResolvedActionArgument,
    ResolvedNoticeAction,
)
from .. import current_operator_surface_reconciliation
from .._common import (
    _OPERATOR_SURFACE_RECONCILIATION_META_KEY,
    _action_text_lines,
    _powershell_action_token,
    _resolve_notice_actions,
    resolve_cli_precondition_action,
    resolve_notice_action,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_POWERSHELL_LITERAL_SCRIPT = "& { param([string]$Value) [Console]::Out.Write($Value) }"


async def _run_powershell_literal(resolved_powershell: str, rendered: str) -> str:
    completed = await anyio.run_process(
        [
            resolved_powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _POWERSHELL_LITERAL_SCRIPT,
            rendered,
        ],
        check=True,
    )
    assert completed.stdout is not None
    return completed.stdout.decode("utf-8")


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
            "cli_path": ["app", "overview", "status"],
        },
        "argument_bindings": [],
    }

    # COVERAGE GAP, deliberately recorded rather than faked.
    #
    # This test also covered the required-input half: an action whose target
    # command declares a required parameter the caller has not bound must
    # refuse. It was pinned to `operator.profile.sandbox.restore`, which the
    # retired profile restore surface took with it.
    #
    # There is no substitute today. Resolving every entry in the live
    # catalogue with no bindings raises nothing at all, so no action currently
    # declares a refusing required argument. Re-pointing at any live id would
    # assert a refusal that cannot happen, and asserting "nothing refuses"
    # would gate on the gap rather than the property.
    #
    # Restore this half with the profile restore/import surface, whose verbs
    # take the required subject arguments the case needs.


def test_common_action_resolver_refuses_invalid_invocation_reconciliation() -> None:
    """A malformed invocation cache cannot silently weaken live action checks."""
    with click.Context(click.Command("operator-surface")) as context:
        context.meta[_OPERATOR_SURFACE_RECONCILIATION_META_KEY] = "not a reconciliation"
        with pytest.raises(TypeError, match="operator-surface reconciliation context contains an invalid value"):
            current_operator_surface_reconciliation()


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


def test_cli_precondition_projection_preserves_canonical_enum_members_without_value_conversion() -> None:
    """The application verdict and wire DTO carry the same enum identities."""
    verdict = PreconditionVerdict(
        failed_condition_id="profile.active.required",
        evidence=(
            ConditionEvidence(
                condition_id="profile.active.required",
                evidence_id="profile.active.state",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"profile_name": "Ada"},
            ),
        ),
        action=ActionReference(action_id="operator.profile.create"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="profile_name",
                status=ActionArgumentStatus.RESOLVED,
                value="Ada",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="profile_name",
            ),
        ),
        conditionality=ActionConditionality.IMMEDIATE,
    )

    projected = resolve_cli_precondition_action(verdict)

    assert projected.evidence[0].provenance is verdict.evidence[0].provenance
    assert projected.argument_bindings[0].status is verdict.argument_bindings[0].status
    assert projected.argument_bindings[0].source is verdict.argument_bindings[0].source
    assert projected.conditionality is verdict.conditionality


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
            "cli_path": ["app", "modelo", "work", "calculate"],
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
        (r"""C:\tmp\"quoted"\bundle.aeat""", r"""'C:\tmp\"quoted"\bundle.aeat'"""),
        (r"C:\O'Brien\bundle.aeat", r"'C:\O''Brien\bundle.aeat'"),
    ),
)
def test_powershell_action_token_is_literal_under_the_real_shell(value: str, rendered: str) -> None:
    assert _powershell_action_token(value) == rendered

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    assert powershell is not None
    assert anyio.run(_run_powershell_literal, powershell, rendered) == value


@pytest.mark.parametrize(
    ("action_id", "argument_name", "source_key", "value", "expected_tail"),
    (
        # A path-argument case belongs here too, but no action in the live
        # catalogue takes one: the profile import/export surface is retired
        # pending its rebuild. Restore a path case with that surface rather
        # than reaching for an action id the catalogue no longer declares.
        # The quoting itself stays covered against a REAL shell by
        # `test_powershell_action_token_is_literal_under_the_real_shell`,
        # which runs the `$(Write-Output PWN)` payload through pwsh.
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
    notice_action = notice.action
    assert isinstance(notice_action, ResolvedNoticeAction)
    assert notice_action.argument_bindings[0].value == value
    assert notice_action.action.cli_path is not None
