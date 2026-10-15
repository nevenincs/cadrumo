"""Keep standalone person sessions distinct from attested desktop sessions."""

from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session_port import profile_login_session_port
from cadrumo_runtime.host import session_hold

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "arguments,expected",
    [([], OperationFrontendProjection.DESKTOP), (["--frontend", "cli"], OperationFrontendProjection.CLI)],
)
def test_holder_selects_the_declared_human_frontend(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str], expected: OperationFrontendProjection
) -> None:
    profile_id = uuid4()
    observed = []
    caller_port = profile_login_session_port()

    async def hold(profile: UUID, *, password_stdin: bool, frontend: OperationFrontendProjection) -> int:
        assert profile_login_session_port() is not caller_port
        observed.append((profile, password_stdin, frontend))
        return 0

    monkeypatch.setattr(session_hold, "_hold", hold)
    assert session_hold.main(["--profile-id", str(profile_id), *arguments]) == 0
    assert observed == [(profile_id, False, expected)]
    assert profile_login_session_port() is caller_port


def test_holder_cannot_select_a_delegated_frontend() -> None:
    with pytest.raises(SystemExit) as refusal:
        session_hold.main(["--profile-id", str(uuid4()), "--frontend", "external-client"])
    assert refusal.value.code == 2
