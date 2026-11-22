"""The CLI keeps the runtime's post-sign-out access observation explicit."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
import typer
from typer.core import TyperCommand

from cadrumo.core.output_rendering import OutputFormat
from cadrumo_client.commands.profile_selection import LoginTarget
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.sign_in import HumanSignedOut

from .. import custody

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _signed_out(access_remains: bool | None) -> HumanSignedOut:
    return HumanSignedOut(
        request_id=UUID(int=1),
        runtime_boot_id=UUID(int=2),
        connection_id=UUID(int=3),
        profile_id=UUID(int=4),
        session_ids=(),
        receipt_removed=True,
        keychain_removed=True,
        automation_enabled=True,
        automation_access_remains=access_remains,
    )


@pytest.mark.parametrize("access_remains", [True, False, None])
def test_logout_projection_preserves_remaining_access_without_inference(access_remains: bool | None) -> None:
    result = custody.config_logout_result(
        _signed_out(access_remains),
        logged_out_profile="Selected profile",
        already_logged_out=False,
    )

    payload = result.model_dump(mode="json")
    assert payload["automation_enabled"] is True
    assert payload["automation_access_remains"] is access_remains
    assert payload["automation_revoked"] is False


def test_logout_without_a_runtime_observation_keeps_access_unknown() -> None:
    result = custody.config_logout_result(
        None,
        logged_out_profile=None,
        already_logged_out=True,
    )

    payload = result.model_dump(mode="json")
    assert payload["automation_enabled"] is None
    assert payload["automation_access_remains"] is None


def _json_context() -> typer.Context:
    return typer.Context(TyperCommand("logout"), obj={"format": OutputFormat.JSON})


def test_a_committed_sign_out_asks_the_runtime_nothing_more(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The run-5 teardown: the runtime retired the sign-in, then never answered the label lookup the
    # envelope made after it, and the committed sign-out was reported as refused with runtime_timeout.
    selected = str(UUID(int=4))
    asked: list[str] = []
    signed_out: list[bool] = []

    def runtime(question: str, answer: object) -> object:
        asked.append(question)
        if signed_out:
            raise RefusalError(RefusalCode.TIMEOUT)
        return answer

    target = LoginTarget(selected, "Selected profile")
    monkeypatch.setattr(custody.profile_selection, "runtime_selected_profile_id", lambda: runtime("selected", selected))
    monkeypatch.setattr(custody.profile_selection, "command_profile_id", lambda: runtime("command", selected))
    monkeypatch.setattr(custody.profile_selection, "runtime_login_target", lambda name: runtime("label", target))

    def sign_out(ctx: object, profile_id: str, secret: object, *, require_password: bool) -> HumanSignedOut:
        assert (profile_id, secret, require_password) == (selected, None, False)
        signed_out.append(True)
        return _signed_out(False)

    monkeypatch.setattr(custody, "_sign_out_profile", sign_out)
    ctx = _json_context()

    custody.config_logout(ctx)

    envelope = json.loads(capsys.readouterr().out)
    assert envelope["status"] == "success"
    assert envelope["result"]["human_receipt_revoked"] is True
    assert envelope["result"]["logged_out_profile"] == "Selected profile"
    assert signed_out == [True]
    # Every runtime question was asked before the sign-out; none after it.
    assert asked == ["selected", "label", "command"]


def test_a_named_sign_out_reads_the_selected_profiles_label_before_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    named, selected = LoginTarget(str(UUID(int=5)), "Named"), LoginTarget(str(UUID(int=6)), "Selected")
    events: list[str] = []
    monkeypatch.setattr(custody.profile_selection, "require_runtime_login_target", lambda name: named)
    monkeypatch.setattr(custody.profile_selection, "command_profile_id", lambda: selected.bucket_id)

    def label(name: str) -> LoginTarget:
        events.append(f"label {name}")
        return selected

    def sign_out(ctx: object, profile_id: str, secret: object, *, require_password: bool) -> HumanSignedOut:
        events.append(f"sign-out {profile_id}")
        return _signed_out(None)

    monkeypatch.setattr(custody.profile_selection, "runtime_login_target", label)
    monkeypatch.setattr(custody, "_sign_out_profile", sign_out)

    custody.config_logout(_json_context(), name="Named")

    envelope = json.loads(capsys.readouterr().out)
    assert envelope["result"]["logged_out_profile"] == "Named"
    assert events == [f"label {selected.bucket_id}", f"sign-out {named.bucket_id}"]
