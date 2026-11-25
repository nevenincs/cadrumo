"""The credential guard names the profile-session entries a run left behind and passes a run that left none.

The listing parser reads the real ``cmdkey /list`` line shape; the comparison and the command run on synthetic
listings, so no credential of the machine is read or written.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import credential_guard
from ..credential_guard import SERVICE, entries_in, leaked, main, owned_profile_ids

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


def test_the_command_passes_a_run_that_left_nothing_and_fails_naming_each_own_leaked_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    own = tmp_path / "own"
    for profile in ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"):
        (own / "keystore" / profile).mkdir(parents=True)
    baseline = tmp_path / "baseline.json"
    old = f"cccccccc-cccc-4ccc-8ccc-cccccccccccc:s0@{SERVICE}"
    store: dict[str, frozenset[str]] = {"now": frozenset({old})}
    monkeypatch.setattr(credential_guard, "current_entries", lambda: store["now"])

    assert main(["snapshot", str(baseline)]) == 0
    assert main(["check", str(baseline), "--own-root", str(own)]) == 0

    left_a = f"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa:s1@{SERVICE}"
    left_b = f"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb:s2@{SERVICE}"
    store["now"] = frozenset({old, left_a, left_b})
    assert main(["check", str(baseline), "--own-root", str(own)]) == 1
    error = capsys.readouterr().err
    assert left_a in error
    assert left_b in error
    assert old not in error


def test_without_a_credential_listing_the_guard_passes_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(credential_guard, "current_entries", lambda: None)

    assert main(["snapshot", str(tmp_path / "baseline.json")]) == 0
    assert "nothing checked" in capsys.readouterr().err


_OWN_PROFILE = "11111111-1111-4111-8111-111111111111"
_OTHER_PROFILE = "22222222-2222-4222-8222-222222222222"


def _root(base: Path, name: str, profile: str) -> Path:
    root = base / name
    (root / "keystore" / profile).mkdir(parents=True)
    return root


def test_the_owned_profile_ids_are_the_keystore_and_bucket_folders_of_the_given_roots_only(tmp_path: Path) -> None:
    own = _root(tmp_path, "own", _OWN_PROFILE)
    (own / "buckets" / "33333333-3333-4333-8333-333333333333").mkdir(parents=True)
    _root(tmp_path, "other", _OTHER_PROFILE)

    assert owned_profile_ids([own]) == {_OWN_PROFILE, "33333333-3333-4333-8333-333333333333"}
    assert owned_profile_ids([tmp_path / "absent"]) == frozenset()


def test_a_concurrent_root_s_entry_is_listed_without_failing_and_only_the_run_s_own_entry_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    own = _root(tmp_path, "own", _OWN_PROFILE)
    _root(tmp_path, "other", _OTHER_PROFILE)
    baseline = tmp_path / "baseline.json"
    store: dict[str, frozenset[str]] = {"now": frozenset()}
    monkeypatch.setattr(credential_guard, "current_entries", lambda: store["now"])
    assert main(["snapshot", str(baseline)]) == 0
    foreign = f"{_OTHER_PROFILE}:s1@{SERVICE}"
    mine = f"{_OWN_PROFILE}:s2@{SERVICE}"

    store["now"] = frozenset({foreign})
    assert main(["check", str(baseline), "--own-root", str(own)]) == 0
    listed = capsys.readouterr()
    assert foreign in listed.out
    assert "not this run's" in listed.out

    store["now"] = frozenset({foreign, mine})
    assert main(["check", str(baseline), "--own-root", str(own)]) == 1
    failed = capsys.readouterr()
    assert mine in failed.err
    assert foreign not in failed.err
    assert foreign in failed.out


def test_without_an_own_root_nothing_is_the_run_s_own_and_added_entries_are_only_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = tmp_path / "baseline.json"
    store: dict[str, frozenset[str]] = {"now": frozenset()}
    monkeypatch.setattr(credential_guard, "current_entries", lambda: store["now"])
    assert main(["snapshot", str(baseline)]) == 0
    store["now"] = frozenset({f"{_OWN_PROFILE}:s@{SERVICE}"})

    assert main(["check", str(baseline)]) == 0
    assert f"{_OWN_PROFILE}:s@{SERVICE}" in capsys.readouterr().out
