"""The credential guard names the profile-session entries a run left behind and passes a run that left none.

The listing parser reads the real ``cmdkey /list`` line shape; the comparison and the command run on synthetic
listings, so no credential of the machine is read or written.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import credential_guard
from ..credential_guard import SERVICE, entries_in, leaked, main

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = "b4d601da-1369-45a1-b9f7-5c09a3dddace"
_SESSION = "74005ffc-137d-4954-9c34-8fcb94f6c0b5"
_LISTING = (
    "Currently stored credentials:\n\n"
    f"    Target: LegacyGeneric:target={_PROFILE}:{_SESSION}@{SERVICE}\n"
    "    Type: Generic\n"
    "    User: someone\n\n"
    "    Target: LegacyGeneric:target=other-service@something-else\n"
    "    Type: Generic\n"
)


def test_the_listing_yields_only_the_profile_session_targets() -> None:
    assert entries_in(_LISTING) == {f"{_PROFILE}:{_SESSION}@{SERVICE}"}
    assert entries_in("") == frozenset()


def test_an_entry_present_after_and_not_before_is_a_leak_and_a_removed_one_is_not() -> None:
    assert leaked({"a@s", "b@s"}, {"b@s", "c@s", "d@s"}) == ["c@s", "d@s"]
    assert leaked({"a@s"}, {"a@s"}) == []
    assert leaked({"a@s", "b@s"}, set()) == []


def test_the_command_passes_a_run_that_left_nothing_and_fails_naming_each_leaked_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = tmp_path / "baseline.json"
    store: dict[str, frozenset[str]] = {"now": frozenset({"old@" + SERVICE})}
    monkeypatch.setattr(credential_guard, "current_entries", lambda: store["now"])

    assert main(["snapshot", str(baseline)]) == 0
    assert main(["check", str(baseline)]) == 0

    store["now"] = frozenset({"old@" + SERVICE, "left-a@" + SERVICE, "left-b@" + SERVICE})
    assert main(["check", str(baseline)]) == 1
    error = capsys.readouterr().err
    assert "left-a@" + SERVICE in error
    assert "left-b@" + SERVICE in error
    assert "old@" + SERVICE not in error


def test_without_a_credential_listing_the_guard_passes_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(credential_guard, "current_entries", lambda: None)

    assert main(["snapshot", str(tmp_path / "baseline.json")]) == 0
    assert "nothing checked" in capsys.readouterr().err
