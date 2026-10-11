"""A secret held for the person: kept in the credential store, entered, listed, read and deleted only by them.

Most cases run on the in-memory port the custody package's own tests use for
the native store, so they run everywhere. The last case runs the same journey
on the platform's real credential store.
"""

from __future__ import annotations

import getpass
import io
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody import automation_secret_store as native_secret_store
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import WindowsAutomationSecretStore
from cadrumo.adapters.persistence.storage.custody.automation_secret_target import require_automation_secret_target
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)
from cadrumo.core import logging as cadrumo_logging
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.time.clock import frozen_clock
from cadrumo.tests.os_keychain_hook import require_os_credential_store
from cadrumo_harness.mcp import main as mcp_main
from cadrumo_harness.mcp import server as mcp_server
from cadrumo_harness.mcp.held_secrets import (
    DELETE_HELD_OPTION,
    HELD_SECRET_INDEX_NAMESPACE,
    HELD_SECRET_NAMESPACE,
    HOLD_OPTION,
    LIST_HELD_OPTION,
    MAX_ENTERED_LABEL_CHARACTERS,
    MAX_ENTERED_SECRET_BYTES,
    MAX_HELD_SECRETS,
    ONCE_OPTION,
    SHOW_HELD_OPTION,
    HeldSecretCustody,
    HeldSecretEntry,
    _read_unseen,
    delete_held_secret,
    held_secret_retrieval,
    hold_secret,
    list_held_secrets,
    show_held_secret,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CODE = "ABCDE-FGHJK-LMNPQ-RSTUV-WXYZ2-34567"
_OTHER_CODE = "76543-2ZYXW-VUTSR-QPNML-KJHGF-EDCBA"
_ORIGIN = "recovery_enroll profile_id=synthetic"
_AT = datetime(2026, 10, 11, 9, 30, tzinfo=UTC)
_SINCE = "held since 2026-10-11 09:30 UTC"
_ENTERED = "synthetic-entered-text-41c7"
_LABEL = "synthetic profile password"


@pytest.fixture(autouse=True)
def _held_at_a_known_instant() -> Iterator[None]:
    """Hold every secret of a case at one instant, so a listing's text is exact."""
    with frozen_clock(_AT):
        yield


class _Terminal(io.StringIO):
    """A text stream that reports itself as a terminal, as a person's own console does."""

    @override
    def isatty(self) -> bool:
        return True


def _custody(store: AutomationSecretStore, root: Path) -> HeldSecretCustody:
    root.mkdir(parents=True, exist_ok=True)
    return HeldSecretCustody(store, root=root, scratch=root)


def _held(store: MemoryNativePort) -> set[str]:
    return {account for namespace, account in store.items if namespace == HELD_SECRET_NAMESPACE}


def test_a_held_secret_is_read_back_from_the_store_and_listed_under_a_fresh_reference(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)

    first = custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))
    second = custody.hold(origin="recovery_enroll profile_id=other", secret=bytearray(_OTHER_CODE, "utf-8"))

    assert first.secret.get_secret_value() == _CODE.encode()
    assert first.reference != second.reference
    assert _held(store) == {str(first.reference), str(second.reference)}
    again = custody.read(first.reference)
    assert (again.origin, again.secret.get_secret_value()) == (_ORIGIN, _CODE.encode())
    assert custody.entries() == (
        HeldSecretEntry(first.reference, _ORIGIN, _AT),
        HeldSecretEntry(second.reference, "recovery_enroll profile_id=other", _AT),
    )
    # Neither a held secret's own representation nor a listing entry carries the secret.
    assert _CODE not in repr(first) and _CODE not in repr(custody.entries())
    # The native stores accept both targets this module addresses.
    index_account = sha256_hex(str(tmp_path.resolve()).encode("utf-8"))
    require_automation_secret_target(HELD_SECRET_NAMESPACE, str(first.reference))
    require_automation_secret_target(HELD_SECRET_INDEX_NAMESPACE, index_account)
    assert (HELD_SECRET_INDEX_NAMESPACE, index_account) in store.items


def test_a_hold_the_store_cannot_keep_is_refused_and_leaves_nothing_held_or_listed(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    store.fail_write, store.commit_before_failure = HELD_SECRET_NAMESPACE, True

    with pytest.raises(AutomationCustodyError) as refused:
        custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))

    assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE
    # The write committed before it failed; nobody was given its reference, so it is discarded.
    assert store.items == {}
    store.fail_write = None
    assert custody.entries() == ()


def test_reading_a_reference_that_holds_nothing_or_something_else_is_refused(tmp_path: Path) -> None:
    store, reference = MemoryNativePort(), uuid4()
    custody = _custody(store, tmp_path)

    with pytest.raises(AutomationCustodyError) as missing:
        custody.read(reference)
    store.replace(HELD_SECRET_NAMESPACE, str(reference), SecretBytes(b"not a held secret"))
    with pytest.raises(AutomationCustodyError) as invalid:
        custody.read(reference)
    other = custody.hold(origin="synthetic", secret=bytearray(_CODE, "utf-8"))
    store.items[HELD_SECRET_NAMESPACE, str(reference)] = store.items[HELD_SECRET_NAMESPACE, str(other.reference)]
    with pytest.raises(AutomationCustodyError) as moved:
        custody.read(reference)

    assert missing.value.reason is AutomationCustodyCode.MISSING
    assert invalid.value.reason is AutomationCustodyCode.INVALID
    assert moved.value.reason is AutomationCustodyCode.INVALID


def test_a_listing_keeps_what_it_cannot_read_and_drops_a_reference_whose_secret_is_gone(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    kept = custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))
    damaged = custody.hold(origin="synthetic damaged", secret=bytearray(_CODE, "utf-8"))
    gone = custody.hold(origin="synthetic gone", secret=bytearray(_CODE, "utf-8"))
    store.items[HELD_SECRET_NAMESPACE, str(damaged.reference)] = SecretBytes(b"not a held secret")
    del store.items[HELD_SECRET_NAMESPACE, str(gone.reference)]

    listed = custody.entries()

    assert listed == (
        HeldSecretEntry(kept.reference, _ORIGIN, _AT),
        HeldSecretEntry(damaged.reference, None, fault=AutomationCustodyCode.INVALID),
    )
    # The dropped reference is gone from the index itself, not only from this answer.
    assert custody.entries() == listed
    assert str(gone.reference).encode() not in next(
        value.get_secret_value()
        for (namespace, _account), value in store.items.items()
        if namespace == HELD_SECRET_INDEX_NAMESPACE
    )


def test_each_storage_root_lists_only_what_was_held_for_it(tmp_path: Path) -> None:
    store = MemoryNativePort()
    first_root, second_root = _custody(store, tmp_path / "first"), _custody(store, tmp_path / "second")

    first = first_root.hold(origin="synthetic first", secret=bytearray(_CODE, "utf-8"))
    second = second_root.hold(origin="synthetic second", secret=bytearray(_OTHER_CODE, "utf-8"))

    assert [entry.reference for entry in first_root.entries()] == [first.reference]
    assert [entry.reference for entry in second_root.entries()] == [second.reference]
    # A reference is exact wherever it is read from.
    assert second_root.read(first.reference).secret.get_secret_value() == _CODE.encode()


def test_no_more_is_held_than_one_listing_can_name(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    held = [
        custody.hold(origin=f"synthetic {index}", secret=bytearray(_CODE, "utf-8")) for index in range(MAX_HELD_SECRETS)
    ]

    with pytest.raises(AutomationCustodyError) as full:
        custody.hold(origin="synthetic one too many", secret=bytearray(_CODE, "utf-8"))

    assert full.value.reason is AutomationCustodyCode.CONFLICT
    assert _held(store) == {str(item.reference) for item in held}
    assert len(custody.entries()) == MAX_HELD_SECRETS
    custody.release(held[0].reference)
    assert custody.hold(origin="synthetic after one was read", secret=bytearray(_CODE, "utf-8")).origin


def test_holds_from_several_servers_at_once_are_all_listed(tmp_path: Path) -> None:
    store = MemoryNativePort()
    tmp_path.mkdir(parents=True, exist_ok=True)

    def hold_some(worker: int) -> list[UUID]:
        # Each server binds its own custody to the same store, root and lock.
        custody = HeldSecretCustody(store, root=tmp_path, scratch=tmp_path)
        return [
            custody.hold(origin=f"synthetic {worker}/{index}", secret=bytearray(_CODE, "utf-8")).reference
            for index in range(5)
        ]

    with ThreadPoolExecutor(max_workers=6) as pool:
        held = [reference for references in pool.map(hold_some, range(6)) for reference in references]

    listed = [entry.reference for entry in _custody(store, tmp_path).entries()]
    assert len(held) == 30 and sorted(listed, key=str) == sorted(held, key=str)


def test_the_person_reads_a_held_secret_at_a_terminal_and_it_is_deleted_only_when_they_say_it_is_kept(
    tmp_path: Path,
) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    held = custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))

    shown, errors = _Terminal(), io.StringIO()
    kept_in_store = show_held_secret(
        held.reference, terminal=shown, answers=_Terminal("\n"), errors=errors, custody=lambda: custody
    )
    assert kept_in_store == 0 and errors.getvalue() == ""
    assert _CODE in shown.getvalue() and _ORIGIN in shown.getvalue()
    assert custody.read(held.reference).secret.get_secret_value() == _CODE.encode()
    assert [entry.reference for entry in custody.entries()] == [held.reference]

    again = _Terminal()
    deleted = show_held_secret(
        held.reference, terminal=again, answers=_Terminal("kept\n"), errors=errors, custody=lambda: custody
    )
    assert deleted == 0 and _CODE in again.getvalue()
    # The secret and its listing are both gone from the store.
    assert store.items == {}

    gone, errors = _Terminal(), io.StringIO()
    missing = show_held_secret(
        held.reference, terminal=gone, answers=_Terminal("kept\n"), errors=errors, custody=lambda: custody
    )
    assert missing == 1 and gone.getvalue() == "" and "missing" in errors.getvalue()


def test_the_listing_names_each_reference_and_what_it_was_delivered_for_and_shows_no_secret(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    empty, errors = _Terminal(), io.StringIO()
    assert list_held_secrets(terminal=empty, errors=errors, custody=lambda: custody) == 0
    assert empty.getvalue() == "No secret is held.\n"
    first = custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))
    second = custody.hold(origin="recovery_enroll profile_id=other", secret=bytearray(_OTHER_CODE, "utf-8"))

    listing = _Terminal()
    status = list_held_secrets(terminal=listing, errors=errors, custody=lambda: custody)

    assert status == 0 and errors.getvalue() == ""
    assert listing.getvalue() == (
        f"{first.reference}  {_ORIGIN}, {_SINCE}\n{second.reference}  recovery_enroll profile_id=other, {_SINCE}\n"
    )
    assert _CODE not in listing.getvalue() and _OTHER_CODE not in listing.getvalue()
    # Listing changes nothing.
    assert _held(store) == {str(first.reference), str(second.reference)}


def test_a_held_secret_is_deleted_unread_only_when_the_person_types_the_word(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    held = custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))
    errors = io.StringIO()

    for answer in ("\n", "kept\n", "yes\n"):
        asked = _Terminal()
        status = delete_held_secret(
            held.reference, terminal=asked, answers=_Terminal(answer), errors=errors, custody=lambda: custody
        )
        assert status == 0 and _ORIGIN in asked.getvalue() and _CODE not in asked.getvalue()
        assert custody.read(held.reference).secret.get_secret_value() == _CODE.encode()

    asked = _Terminal()
    deleted = delete_held_secret(
        held.reference, terminal=asked, answers=_Terminal("delete\n"), errors=errors, custody=lambda: custody
    )
    assert deleted == 0 and errors.getvalue() == ""
    assert _CODE not in asked.getvalue()
    assert store.items == {}

    again, errors = _Terminal(), io.StringIO()
    missing = delete_held_secret(
        held.reference, terminal=again, answers=_Terminal("delete\n"), errors=errors, custody=lambda: custody
    )
    assert missing == 1 and again.getvalue() == "" and "missing" in errors.getvalue()


def test_something_unreadable_under_a_reference_can_still_be_deleted(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    held = custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))
    store.items[HELD_SECRET_NAMESPACE, str(held.reference)] = SecretBytes(b"not a held secret")
    asked, errors = _Terminal(), io.StringIO()

    status = delete_held_secret(
        held.reference, terminal=asked, answers=_Terminal("delete\n"), errors=errors, custody=lambda: custody
    )

    assert status == 0 and "unreadable (invalid)" in asked.getvalue()
    assert store.items == {}


@pytest.mark.parametrize("command", ["show", "list", "delete"])
@pytest.mark.parametrize("piped", ["output", "input"])
def test_nothing_is_shown_listed_or_deleted_on_a_stream_that_is_not_a_terminal(
    tmp_path: Path, command: str, piped: str
) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    held = custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))
    output = io.StringIO() if piped == "output" else _Terminal()
    answers = io.StringIO("kept\ndelete\n") if piped == "input" else _Terminal("kept\ndelete\n")
    errors = io.StringIO()

    if command == "show":
        status = show_held_secret(
            held.reference, terminal=output, answers=answers, errors=errors, custody=lambda: custody
        )
    elif command == "delete":
        status = delete_held_secret(
            held.reference, terminal=output, answers=answers, errors=errors, custody=lambda: custody
        )
    else:
        status = list_held_secrets(terminal=output, errors=errors, custody=lambda: custody)

    if command == "list" and piped == "input":
        # A listing reads no answer, so only where it is written decides.
        assert status == 0 and _CODE not in output.getvalue()
    else:
        assert status == 2
        assert output.getvalue() == "" and "terminal" in errors.getvalue()
    assert _CODE not in errors.getvalue()
    # Nothing was deleted either: the person can still read it at their own terminal.
    assert custody.read(held.reference).secret.get_secret_value() == _CODE.encode()


def _entry_point_status(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> tuple[object, list[dict[str, object]]]:
    """Run the installed entry point on these arguments; return its exit status and what it asked to be served."""
    served: list[dict[str, object]] = []
    monkeypatch.setenv("PYDANTIC_DISABLE_PLUGINS", "__all__")
    monkeypatch.setattr(sys, "argv", ["cadrumo-mcp", *arguments])
    monkeypatch.setattr(cadrumo_logging, "configure_logging", lambda: None)
    monkeypatch.setattr(mcp_server, "serve", lambda **options: served.append(options))
    with pytest.raises(SystemExit) as stopped:
        mcp_main.main()
    return stopped.value.code, served


def test_the_retrieval_sentence_names_the_options_the_entry_point_serves(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    reference = uuid4()
    for in_force in (True, False):
        sentence = held_secret_retrieval(reference, in_force=in_force)
        assert f"`cadrumo-mcp {SHOW_HELD_OPTION} {reference}`" in sentence
        assert f"`cadrumo-mcp {LIST_HELD_OPTION}`" in sentence
        assert f"`cadrumo-mcp {DELETE_HELD_OPTION} {reference}`" in sentence
        assert "secret_reference" in sentence and "confirm they have kept it" in sentence

    # The captured streams of a test run are not a terminal, so each option refuses and serves nothing.
    for arguments in ([SHOW_HELD_OPTION, str(reference)], [LIST_HELD_OPTION], [DELETE_HELD_OPTION, str(reference)]):
        status, served = _entry_point_status(monkeypatch, arguments)
        captured = capsys.readouterr()
        assert status == 2 and served == []
        assert captured.out == "" and "terminal" in captured.err

    # The three are one choice: the entry point refuses two of them together.
    status, served = _entry_point_status(monkeypatch, [LIST_HELD_OPTION, SHOW_HELD_OPTION, str(reference)])
    assert status == 2 and served == []
    assert "not allowed with" in capsys.readouterr().err


class _Typed:
    """What the person types at the unseen prompts, in order; the prompts asked for are kept."""

    def __init__(self, *entries: str) -> None:
        self._entries = list(entries)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._entries.pop(0)


def _enter(
    custody: HeldSecretCustody, typed: _Typed, *, label: str = _LABEL, single_use: bool = False
) -> tuple[int, str, str]:
    """Run the hold command at a terminal; return its status and what it wrote to the terminal and to errors."""
    terminal, errors = _Terminal(), io.StringIO()
    status = hold_secret(
        single_use=single_use,
        terminal=terminal,
        answers=_Terminal(f"{label}\n"),
        errors=errors,
        read_unseen=typed,
        custody=lambda: custody,
    )
    return status, terminal.getvalue(), errors.getvalue()


def test_a_secret_the_person_enters_is_held_and_only_its_reference_is_printed(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    typed = _Typed(_ENTERED, _ENTERED)

    status, written, errors = _enter(custody, typed)

    assert status == 0 and errors == ""
    (entry,) = custody.entries()
    assert entry == HeldSecretEntry(entry.reference, _LABEL, _AT, entered=True, single_use=False)
    # The reference is the last thing printed, on a line of its own, and the secret is printed nowhere.
    assert written.splitlines()[-1] == str(entry.reference)
    assert _ENTERED not in written and len(typed.prompts) == 2
    assert f"`cadrumo-mcp {DELETE_HELD_OPTION} {entry.reference}`" in written
    # A call takes it as a buffer of its own, and it stays held for the next call.
    for _use in range(2):
        taken = custody.take(entry.reference)
        assert isinstance(taken, bytearray) and bytes(taken) == _ENTERED.encode()
    assert _held(store) == {str(entry.reference)}


def test_a_secret_entered_for_one_use_is_deleted_by_the_call_that_takes_it(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)

    status, written, _errors = _enter(custody, _Typed(_ENTERED, _ENTERED), single_use=True)

    assert status == 0 and "deleted by the first tool call" in written
    (entry,) = custody.entries()
    assert entry.single_use and entry.entered
    assert bytes(custody.take(entry.reference)) == _ENTERED.encode()
    with pytest.raises(AutomationCustodyError) as spent:
        custody.take(entry.reference)
    assert spent.value.reason is AutomationCustodyCode.MISSING
    assert store.items == {}


def test_a_one_use_secret_that_cannot_be_deleted_is_given_to_nobody(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    held = custody.hold_entered(label=_LABEL, secret=bytearray(_ENTERED, "utf-8"), single_use=True)
    store.fail_delete = True

    with pytest.raises(AutomationCustodyError) as refused:
        custody.take(held.reference)

    assert refused.value.reason is AutomationCustodyCode.UNAVAILABLE
    store.fail_delete = False
    assert bytes(custody.take(held.reference)) == _ENTERED.encode()


def test_a_call_that_uses_a_secret_held_for_the_person_to_read_neither_shows_nor_deletes_it(
    tmp_path: Path,
) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    delivered = custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))

    for _use in range(2):
        taken = custody.take(delivered.reference)
        assert isinstance(taken, bytearray) and bytes(taken) == _CODE.encode()
    # Using it is not the person reading it: it is still held, listed, and theirs to read and confirm.
    assert custody.entries() == (HeldSecretEntry(delivered.reference, _ORIGIN, _AT),)
    shown = _Terminal()
    status = show_held_secret(
        delivered.reference, terminal=shown, answers=_Terminal("kept\n"), errors=io.StringIO(), custody=lambda: custody
    )
    assert status == 0 and _CODE in shown.getvalue() and store.items == {}
    # A reference that names nothing held is still nothing to take.
    with pytest.raises(AutomationCustodyError) as absent:
        custody.take(uuid4())
    assert absent.value.reason is AutomationCustodyCode.MISSING


@pytest.mark.parametrize(
    ("label", "entries", "told"),
    [
        (_LABEL, (_ENTERED, _OTHER_CODE), "The two entries differ"),
        (_LABEL, ("", ""), f"1 to {MAX_ENTERED_SECRET_BYTES} bytes"),
        (_LABEL, ((MAX_ENTERED_SECRET_BYTES + 1) * "x",) * 2, f"1 to {MAX_ENTERED_SECRET_BYTES} bytes"),
        ("", (_ENTERED, _ENTERED), f"1 to {MAX_ENTERED_LABEL_CHARACTERS} characters"),
        ((MAX_ENTERED_LABEL_CHARACTERS + 1) * "x", (_ENTERED, _ENTERED), "characters"),
    ],
    ids=["entries-differ", "empty-secret", "secret-too-long", "no-label", "label-too-long"],
)
def test_an_entry_that_is_refused_holds_nothing_and_repeats_no_secret(
    tmp_path: Path, label: str, entries: tuple[str, str], told: str
) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)

    status, written, errors = _enter(custody, _Typed(*entries), label=label)

    assert status == 1 and told in errors and "Nothing was held" in errors
    assert store.items == {}
    assert not any(entry and entry in written + errors for entry in entries)


def test_a_terminal_that_cannot_hide_the_typing_is_refused_and_holds_nothing(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)

    def echoing(_prompt: str) -> str:
        raise getpass.GetPassWarning("synthetic: echo cannot be turned off")

    terminal, errors = _Terminal(), io.StringIO()
    status = hold_secret(
        single_use=False,
        terminal=terminal,
        answers=_Terminal(f"{_LABEL}\n"),
        errors=errors,
        read_unseen=echoing,
        custody=lambda: custody,
    )

    assert status == 1 and "without showing it" in errors.getvalue()
    assert store.items == {}


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="elsewhere the reader opens the controlling terminal itself")
def test_the_unseen_reader_refuses_to_read_where_it_would_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    """With an input that is not the console, the standard reader would echo: this one raises before reading."""
    typed = io.StringIO(f"{_ENTERED}\n")
    monkeypatch.setattr(sys, "stdin", typed)

    with pytest.raises(getpass.GetPassWarning):
        _read_unseen("synthetic prompt: ")

    assert typed.tell() == 0


@pytest.mark.parametrize("piped", ["output", "input"])
def test_nothing_is_asked_for_or_held_on_a_stream_that_is_not_a_terminal(tmp_path: Path, piped: str) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    typed = _Typed(_ENTERED, _ENTERED)
    output = io.StringIO() if piped == "output" else _Terminal()
    answers = io.StringIO(f"{_LABEL}\n") if piped == "input" else _Terminal(f"{_LABEL}\n")
    errors = io.StringIO()

    status = hold_secret(
        single_use=False, terminal=output, answers=answers, errors=errors, read_unseen=typed, custody=lambda: custody
    )

    assert status == 2 and "terminal" in errors.getvalue()
    assert output.getvalue() == "" and typed.prompts == [] and store.items == {}


def test_an_entered_secret_is_listed_by_its_label_never_shown_back_and_deleted_on_request(tmp_path: Path) -> None:
    store = MemoryNativePort()
    custody = _custody(store, tmp_path)
    kept = custody.hold_entered(label=_LABEL, secret=bytearray(_ENTERED, "utf-8"), single_use=False)
    once = custody.hold_entered(label="synthetic export text", secret=bytearray(_OTHER_CODE, "utf-8"), single_use=True)
    errors = io.StringIO()

    listing = _Terminal()
    assert list_held_secrets(terminal=listing, errors=errors, custody=lambda: custody) == 0
    assert listing.getvalue() == (
        f"{kept.reference}  {_LABEL}, entered by you, {_SINCE}, until you delete it\n"
        f"{once.reference}  synthetic export text, entered by you, {_SINCE}, for one use\n"
    )

    shown, refused = _Terminal(), io.StringIO()
    status = show_held_secret(
        kept.reference, terminal=shown, answers=_Terminal("kept\n"), errors=refused, custody=lambda: custody
    )
    assert status == 1 and shown.getvalue() == ""
    assert "not shown" in refused.getvalue() and _ENTERED not in refused.getvalue()
    assert bytes(custody.take(kept.reference)) == _ENTERED.encode()

    asked = _Terminal()
    deleted = delete_held_secret(
        kept.reference, terminal=asked, answers=_Terminal("delete\n"), errors=errors, custody=lambda: custody
    )
    assert deleted == 0 and errors.getvalue() == ""
    assert "refused from then on" in asked.getvalue() and _ENTERED not in asked.getvalue()
    assert [entry.reference for entry in custody.entries()] == [once.reference]


def test_the_entry_point_serves_the_hold_option_only_at_a_terminal_and_once_only_beside_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The captured streams of a test run are not a terminal, so the option refuses and serves nothing.
    for arguments in ([HOLD_OPTION], [HOLD_OPTION, ONCE_OPTION]):
        status, served = _entry_point_status(monkeypatch, arguments)
        captured = capsys.readouterr()
        assert status == 2 and served == []
        assert captured.out == "" and "terminal" in captured.err

    status, served = _entry_point_status(monkeypatch, [ONCE_OPTION, "--profile-id", str(uuid4())])
    assert status == 2 and served == []
    assert f"{ONCE_OPTION} belongs with {HOLD_OPTION}" in capsys.readouterr().err

    status, served = _entry_point_status(monkeypatch, [HOLD_OPTION, LIST_HELD_OPTION])
    assert status == 2 and served == []
    assert "not allowed with" in capsys.readouterr().err


class _CredentialApi:
    """An in-memory raw-byte seam under the Windows store adapter, where the Win32 credential calls sit."""

    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    def read(self, target: str) -> bytes | None:
        return self.items.get(target)

    def write(self, target: str, account: str, value: bytes) -> None:
        del account
        self.items[target] = bytes(value)

    def delete(self, target: str) -> None:
        self.items.pop(target, None)


def test_a_full_listing_fits_the_native_stores_item_size_through_the_real_store_adapter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The adapter's own target and blob-size rules accept every item, at the most this module holds."""
    api = _CredentialApi()
    monkeypatch.setattr(native_secret_store.sys, "platform", "win32")
    monkeypatch.setattr(native_secret_store, "_windows_credential_api", lambda: api)
    custody = _custody(WindowsAutomationSecretStore(), tmp_path)
    origin = "recovery_enroll profile_id=6f1c1a52-3b55-4d0b-9c0e-0d6b7c4c8f11"

    held = [custody.hold(origin=origin, secret=bytearray(_CODE, "utf-8")) for _ in range(MAX_HELD_SECRETS)]

    assert [entry.reference for entry in custody.entries()] == [item.reference for item in held]
    assert all(entry.origin == origin for entry in custody.entries())
    assert len(api.items) == MAX_HELD_SECRETS + 1
    assert max(len(value) for value in api.items.values()) <= 2560
    assert custody.read(held[-1].reference).secret.get_secret_value() == _CODE.encode()
    custody.release(held[0].reference)
    # The longest secret under the longest label a person can enter is one item too, whatever the label's script.
    widest = custody.hold_entered(
        label="\u00f1" * MAX_ENTERED_LABEL_CHARACTERS,
        secret=bytearray(MAX_ENTERED_SECRET_BYTES * b"x"),
        single_use=True,
    )
    assert max(len(value) for value in api.items.values()) <= 2560
    assert bytes(custody.take(widest.reference)) == MAX_ENTERED_SECRET_BYTES * b"x"
    for item in held[1:]:
        custody.release(item.reference)
    assert api.items == {}


class _TrackedNativeStore:
    """The platform's real credential store, remembering what this test put there so it can take it out."""

    def __init__(self, native: AutomationSecretStore) -> None:
        self._native = native
        self.created: set[tuple[str, str]] = set()

    @property
    def backend(self) -> NativeSecretBackend:
        return self._native.backend

    def read(self, namespace: str, account: str) -> SecretBytes | None:
        return self._native.read(namespace, account)

    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        self.created.add((namespace, account))
        self._native.replace(namespace, account, value)

    def delete(self, namespace: str, account: str) -> None:
        self._native.delete(namespace, account)

    def remaining(self) -> list[tuple[str, str]]:
        return sorted(target for target in self.created if self._native.read(*target) is not None)


@pytest.fixture
def native_store() -> Iterator[_TrackedNativeStore]:
    require_os_credential_store()
    tracked = _TrackedNativeStore(installed_automation_secret_store())
    try:
        yield tracked
    finally:
        for namespace, account in tracked.remaining():
            tracked.delete(namespace, account)
        assert tracked.remaining() == []


@pytest.mark.os_keychain
def test_the_real_credential_store_holds_lists_shows_and_deletes_a_secret(
    native_store: _TrackedNativeStore, tmp_path: Path
) -> None:
    custody = _custody(native_store, tmp_path)
    first = custody.hold(origin=_ORIGIN, secret=bytearray(_CODE, "utf-8"))
    second = custody.hold(origin="recovery_enroll profile_id=other", secret=bytearray(_OTHER_CODE, "utf-8"))
    errors = io.StringIO()

    # The copy read back is the stored one, and a second binding of the same store and root finds both.
    assert first.secret.get_secret_value() == _CODE.encode()
    reopened = _custody(native_store, tmp_path)
    listing = _Terminal()
    assert list_held_secrets(terminal=listing, errors=errors, custody=lambda: reopened) == 0
    assert listing.getvalue() == (
        f"{first.reference}  {_ORIGIN}, {_SINCE}\n{second.reference}  recovery_enroll profile_id=other, {_SINCE}\n"
    )

    shown = _Terminal()
    assert (
        show_held_secret(
            first.reference, terminal=shown, answers=_Terminal("kept\n"), errors=errors, custody=lambda: reopened
        )
        == 0
    )
    assert _CODE in shown.getvalue()
    assert native_store.read(HELD_SECRET_NAMESPACE, str(first.reference)) is None
    assert [entry.reference for entry in reopened.entries()] == [second.reference]

    asked = _Terminal()
    assert (
        delete_held_secret(
            second.reference, terminal=asked, answers=_Terminal("delete\n"), errors=errors, custody=lambda: reopened
        )
        == 0
    )
    assert _OTHER_CODE not in asked.getvalue() and errors.getvalue() == ""
    # A secret the person entered is taken by a call from the same store, and one held for one use is gone after.
    entered = reopened.hold_entered(label=_LABEL, secret=bytearray(_ENTERED, "utf-8"), single_use=True)
    assert bytes(_custody(native_store, tmp_path).take(entered.reference)) == _ENTERED.encode()
    # Nothing this journey wrote is left in the real store, the index included.
    assert reopened.entries() == ()
    assert native_store.remaining() == []
