"""Secrets held for the person in this machine's protected credential store, in either direction.

Recovery enrolment mints a code that belongs to the person. The runtime and
the profile's custody never store it: they hand it over once and install the
enrolment only after it is read back. At a terminal the person copies it down
there and then. Through MCP there is no terminal, and a tool result is read by
the model and kept in its transcript, so the code never enters one. This
server keeps one copy in the native credential store that also holds an
enrolled key, under a reference of its own, and the tool result names only the
reference. The copy stays there until the person reads it at a terminal of
their own with ``cadrumo-mcp --show-held-secret REFERENCE`` and confirms they
have kept it, or deletes it unread; then it is removed from the store.

A secret a tool takes travels the other way, and typed into a tool call it has
passed through the model and the host's transcript before it reaches this
server. The person keeps it out of the conversation by entering it here
instead: ``cadrumo-mcp --hold-secret`` asks for it at their terminal without
echo, holds it under a new reference, and prints only the reference. A tool
call then names the reference, and this server reads the secret from the store
straight into the buffer it sends on the runtime's protected secret frame.

An entered secret stays until the person deletes it, so a connection can sign
in again after a lock or an expiry without the password reaching anyone. Held
with ``--once`` it is deleted by the first call that presents its reference.

A tool call may present either kind of reference. A recovery code held for the
person to read can be used at once, as it can at a terminal where it is shown:
a call that names its reference sends the code to the runtime and shows it to
nobody. Using it that way is not the person reading it. The copy stays held
and listed until they read it and confirm they kept it, or delete it.

The store's enrolled-key records cannot hold either kind: each is bound to a
grant, a key and a review, and is refused unless its secret derives that key's
id. What is held here is a record of its own kind in a namespace of its own.

The native store answers only for an exact name and lists nothing, so the
references held for one storage root are kept in one index item beside the
records. That is what lets the person find a code nobody has read yet.
"""

from __future__ import annotations

import getpass
import warnings
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Literal, TextIO
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, Field, SecretBytes, ValidationError

from cadrumo.adapters.persistence.storage.custody.automation_secret_target import AUTOMATION_NAMESPACE_PREFIX
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from cadrumo.core.base64_codec import b64_decode_canonical, b64_encode
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.locks_errors import LockAcquisitionError
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from cadrumo.core.paths import effective_storage_root
from cadrumo.core.storage_environment import prepare_temporary_directory
from cadrumo.core.time.clock import now

HELD_SECRET_NAMESPACE: Final = f"{AUTOMATION_NAMESPACE_PREFIX}held-secret.v1"
"""Where a held secret lives in the native store; its account is the reference."""

HELD_SECRET_INDEX_NAMESPACE: Final = f"{AUTOMATION_NAMESPACE_PREFIX}held-secret-index.v1"
"""Where the references held for one storage root are listed; its account names that root."""

MAX_HELD_SECRETS: Final = 60
"""Most secrets held unread for one storage root: what one native item can list."""

SHOW_HELD_OPTION: Final = "--show-held-secret"
"""The option of this server's own command that shows a held secret to the person."""

LIST_HELD_OPTION: Final = "--list-held-secrets"
"""The option that lists what is held, showing no secret."""

DELETE_HELD_OPTION: Final = "--delete-held-secret"
"""The option that deletes a held secret without showing it."""

HOLD_OPTION: Final = "--hold-secret"
"""The option that asks the person for a secret and holds it for a tool to take by reference."""

ONCE_OPTION: Final = "--once"
"""Beside the hold option: the secret is deleted by the first call that presents its reference."""

MAX_ENTERED_SECRET_BYTES: Final = 512
"""The longest secret the person can enter: with its label it still fits one native item."""

MAX_ENTERED_LABEL_CHARACTERS: Final = 120
"""The longest label the person can give an entered secret."""

_KEPT: Final = "kept"
_DELETE: Final = "delete"
_NOT_A_TERMINAL: Final = (
    "Held secrets are entered, read, listed and deleted only at a terminal. Run this command yourself, "
    "without redirecting its input or its output.\n"
)


class _HeldSecretRecord(BaseModel):
    """The private native item; never a tool result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    schema_version: Literal[1] = 1
    reference: UUID
    origin: str = Field(min_length=1, max_length=512)
    held_at: AwareDatetime
    secret_b64: str = Field(min_length=1, max_length=1024, repr=False)
    entered: bool = False
    single_use: bool = False


class _HeldSecretIndex(BaseModel):
    """The references held for one storage root, oldest first. It carries no secret."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    schema_version: Literal[1] = 1
    references: tuple[UUID, ...] = Field(max_length=MAX_HELD_SECRETS)


@dataclass(frozen=True, slots=True)
class HeldSecret:
    """One secret read back from the store, with what it is held for and since when.

    ``origin`` is the act and arguments a delivered secret was handed over
    for, or the label the person gave a secret they entered. ``entered``
    tells the two apart, and ``single_use`` marks an entered secret that its
    first use deletes.
    """

    reference: UUID
    origin: str
    held_at: datetime
    secret: SecretBytes
    entered: bool = False
    single_use: bool = False


@dataclass(frozen=True, slots=True)
class HeldSecretEntry:
    """One held reference as a listing shows it: what it is held for and since when, and never the secret.

    ``origin`` and ``held_at`` are absent, and ``fault`` says why, when the
    store holds something under the reference that cannot be read as a held
    secret.
    """

    reference: UUID
    origin: str | None
    held_at: datetime | None = None
    fault: AutomationCustodyCode | None = None
    entered: bool = False
    single_use: bool = False


class HeldSecretCustody:
    """The secrets held for the person under one storage root, in one native store."""

    def __init__(self, store: AutomationSecretStore, *, root: Path, scratch: Path) -> None:
        """Bind the store to the root whose held secrets it lists and to where their index is locked."""
        self._store = store
        self._account = sha256_hex(str(root.resolve()).encode("utf-8"))
        self._lock_target = scratch / f"held-secrets-{self._account[:16]}"

    def hold(self, *, origin: str, secret: bytearray) -> HeldSecret:
        """Keep one delivered secret under a new reference and return the copy read back from the store.

        The returned copy is the stored one, so it proves possession of exactly
        what the person will later read. The reference is listed before the
        secret is written, so a secret is never held where a listing cannot
        find it. A write that fails may still have committed; nobody was given
        the new reference, so that item is discarded.

        Raises:
            AutomationCustodyError: The store could not hold the secret or
                return it, or it already holds as many as it can list.
        """
        return self._hold(origin=origin, secret=secret, entered=False, single_use=False)

    def hold_entered(self, *, label: str, secret: bytearray, single_use: bool) -> HeldSecret:
        """Keep one secret the person entered, under a new reference a tool call can present.

        Raises:
            AutomationCustodyError: The store could not hold the secret or
                return it, or it already holds as many as it can list.
        """
        return self._hold(origin=label, secret=secret, entered=True, single_use=single_use)

    def take(self, reference: UUID) -> bytearray:
        """Return the secret held under ``reference`` for one call, in a buffer the caller wipes.

        A secret the person entered for one use is deleted before it is
        returned, so a deletion that fails gives the secret to nobody. A
        secret held for the person to read is never deleted here: a call that
        uses it has not shown it to them. The copies the store itself hands
        back are immutable and outside the wipe.

        Raises:
            AutomationCustodyError: Nothing is held there, the item is not a
                held secret, or its one use could not be recorded.
        """
        held = self.read(reference)
        if held.entered and held.single_use:
            self.release(reference)
        return bytearray(held.secret.get_secret_value())

    def _hold(self, *, origin: str, secret: bytearray, entered: bool, single_use: bool) -> HeldSecret:
        reference = uuid4()
        record = _HeldSecretRecord(
            reference=reference,
            origin=origin,
            held_at=now().replace(microsecond=0),
            secret_b64=b64_encode(bytes(secret)),
            entered=entered,
            single_use=single_use,
        )
        with self._index_lock():
            references = self._read_index()
            if len(references) >= MAX_HELD_SECRETS:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._write_index([*references, reference])
        try:
            self._store.replace(
                HELD_SECRET_NAMESPACE, str(reference), SecretBytes(canonical_json_bytes(record.model_dump(mode="json")))
            )
            return self.read(reference)
        except AutomationCustodyError:
            # The refusal that stopped the hold is the one to report, whatever the discard does.
            with suppress(AutomationCustodyError):
                self.release(reference)
            raise

    def read(self, reference: UUID) -> HeldSecret:
        """Read the secret held under ``reference``.

        Raises:
            AutomationCustodyError: Nothing is held there, or the item is not a held secret.
        """
        stored = self._store.read(HELD_SECRET_NAMESPACE, str(reference))
        if stored is None:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        try:
            record = _HeldSecretRecord.model_validate_json(stored.get_secret_value())
            secret = b64_decode_canonical(record.secret_b64)
        except (ValidationError, ValueError):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
        if record.reference != reference:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return HeldSecret(
            reference=reference,
            origin=record.origin,
            held_at=record.held_at,
            secret=SecretBytes(secret),
            entered=record.entered,
            single_use=record.single_use,
        )

    def entries(self) -> tuple[HeldSecretEntry, ...]:
        """List what is held for this storage root, oldest first, without any secret.

        A reference whose secret is gone was released by a step that did not
        finish, and is dropped from the index here.

        Raises:
            AutomationCustodyError: The store could not be read.
        """
        entries: list[HeldSecretEntry] = []
        with self._index_lock():
            references = self._read_index()
            for reference in references:
                try:
                    held = self.read(reference)
                except AutomationCustodyError as refused:
                    if refused.reason is not AutomationCustodyCode.MISSING:
                        entries.append(HeldSecretEntry(reference, None, fault=refused.reason))
                else:
                    entries.append(_entry(held))
            listed = [entry.reference for entry in entries]
            if listed != references:
                self._write_index(listed)
        return tuple(entries)

    def release(self, reference: UUID) -> None:
        """Delete the secret held under ``reference`` and stop listing it.

        Raises:
            AutomationCustodyError: The store could not delete it; it may still be held.
        """
        self._store.delete(HELD_SECRET_NAMESPACE, str(reference))
        with self._index_lock():
            references = self._read_index()
            if reference in references:
                self._write_index([held for held in references if held != reference])

    @contextmanager
    def _index_lock(self) -> Iterator[None]:
        """Serialize every reader and writer of this root's index across processes."""
        with ExitStack() as held:
            try:
                held.enter_context(exclusive_file_lock(self._lock_target))
            except (LockAcquisitionError, OSError):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT) from None
            yield

    def _read_index(self) -> list[UUID]:
        stored = self._store.read(HELD_SECRET_INDEX_NAMESPACE, self._account)
        if stored is None:
            return []
        try:
            return list(_HeldSecretIndex.model_validate_json(stored.get_secret_value()).references)
        except ValidationError:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None

    def _write_index(self, references: Sequence[UUID]) -> None:
        if not references:
            self._store.delete(HELD_SECRET_INDEX_NAMESPACE, self._account)
            return
        index = _HeldSecretIndex(references=tuple(references))
        self._store.replace(
            HELD_SECRET_INDEX_NAMESPACE,
            self._account,
            SecretBytes(canonical_json_bytes(index.model_dump(mode="json"))),
        )


def held_secret_custody(store: AutomationSecretStore) -> HeldSecretCustody:
    """Bind a native store to the held secrets of the effective storage root."""
    return HeldSecretCustody(store, root=effective_storage_root(), scratch=prepare_temporary_directory())


def installed_held_secret_custody() -> HeldSecretCustody:
    """Return the held secrets of this installation, in the platform's native credential store."""
    return held_secret_custody(installed_automation_secret_store())


def held_secret_retrieval(reference: UUID, *, in_force: bool) -> str:
    """Say how the person reads the secret held under ``reference``, for a tool result."""
    show = f"cadrumo-mcp {SHOW_HELD_OPTION} {reference}"
    others = (
        f"Until then the copy stays held: `cadrumo-mcp {LIST_HELD_OPTION}` lists what is held, showing no secret, "
        f"and `cadrumo-mcp {DELETE_HELD_OPTION} {reference}` deletes this one unread."
    )
    if in_force:
        return (
            "The secret this action hands to the person is held in this machine's protected credential store under "
            f"secret_reference and is in no tool result. The person reads it by running `{show}` in a terminal "
            f"of their own: that shows it to them and deletes the stored copy once they confirm they have kept it. "
            f"{others}"
        )
    return (
        "The action stopped after a secret was held under secret_reference, so that secret may or may not be in "
        f"force. No tool result carries it: the person reads it by running `{show}` in a terminal of their own, "
        f"which deletes the stored copy once they confirm they have kept it. {others}"
    )


def show_held_secret(
    reference: UUID,
    *,
    terminal: TextIO,
    answers: TextIO,
    errors: TextIO,
    custody: Callable[[], HeldSecretCustody] = installed_held_secret_custody,
) -> int:
    """Show one held secret to the person and delete the stored copy once they say they kept it.

    The secret is written only when both the output and the input are a
    terminal. Output that is piped or captured is read by a program, and the
    secret is the person's. A secret the person entered is never shown back.

    Returns:
        The process exit status: 0 when the secret was shown, 2 when this is
        not a terminal, 1 when nothing readable is held under the reference,
        the secret is one the person entered, or the stored copy could not
        be deleted.
    """
    if not (terminal.isatty() and answers.isatty()):
        errors.write(_NOT_A_TERMINAL)
        return 2
    try:
        held_secrets = custody()
        held = held_secrets.read(reference)
    except AutomationCustodyError as refused:
        errors.write(f"No held secret could be read under that reference ({refused.reason.value}).\n")
        return 1
    if held.entered:
        # The person typed it themselves and needs no copy; showing it would only put it on a screen.
        errors.write(
            f"That reference holds a secret you entered ({_described(_entry(held))}); it is not shown. "
            f"Delete it with `cadrumo-mcp {DELETE_HELD_OPTION} {reference}`.\n"
        )
        return 1
    terminal.write(
        f"Held for: {_described(_entry(held))}\n\n"
        f"    {_shown(held.secret)}\n\n"
        "Write it down and keep it somewhere safe. Nobody can show it to you again once the stored copy is deleted.\n"
        f"Type '{_KEPT}' and press Enter to delete the stored copy, or press Enter alone to keep it: "
    )
    terminal.flush()
    if answers.readline().strip().lower() != _KEPT:
        terminal.write("The stored copy is kept under the same reference.\n")
        return 0
    try:
        held_secrets.release(reference)
    except AutomationCustodyError as refused:
        errors.write(f"The stored copy could not be deleted ({refused.reason.value}); it may still be held.\n")
        return 1
    terminal.write("The stored copy is deleted.\n")
    return 0


def list_held_secrets(
    *,
    terminal: TextIO,
    errors: TextIO,
    custody: Callable[[], HeldSecretCustody] = installed_held_secret_custody,
) -> int:
    """List each held reference with what it is held for, and nothing else.

    Returns:
        The process exit status: 0 when the listing was written, 2 when the
        output is not a terminal, 1 when the store could not be read.
    """
    if not terminal.isatty():
        errors.write(_NOT_A_TERMINAL)
        return 2
    try:
        entries = custody().entries()
    except AutomationCustodyError as refused:
        errors.write(f"The held secrets could not be listed ({refused.reason.value}).\n")
        return 1
    if not entries:
        terminal.write("No secret is held.\n")
        return 0
    for entry in entries:
        terminal.write(f"{entry.reference}  {_described(entry)}\n")
    return 0


def delete_held_secret(
    reference: UUID,
    *,
    terminal: TextIO,
    answers: TextIO,
    errors: TextIO,
    custody: Callable[[], HeldSecretCustody] = installed_held_secret_custody,
) -> int:
    """Delete one held secret without showing it, once the person confirms at a terminal.

    A recovery code deleted unread cannot be recovered: the person asks for
    it by typing the word, so a program that only runs the command deletes
    nothing.

    Returns:
        The process exit status: 0 when the person decided, 2 when this is
        not a terminal, 1 when nothing is held under the reference or it
        could not be deleted.
    """
    if not (terminal.isatty() and answers.isatty()):
        errors.write(_NOT_A_TERMINAL)
        return 2
    try:
        held_secrets = custody()
    except AutomationCustodyError as refused:
        errors.write(f"The held secrets could not be reached ({refused.reason.value}).\n")
        return 1
    try:
        held = held_secrets.read(reference)
        described, unread = _described(_entry(held)), not held.entered
    except AutomationCustodyError as refused:
        if refused.reason is not AutomationCustodyCode.INVALID:
            errors.write(f"No held secret could be found under that reference ({refused.reason.value}).\n")
            return 1
        # Something unreadable sits under the reference; it can still be deleted by its exact name.
        described, unread = _described(HeldSecretEntry(reference, None, fault=refused.reason)), True
    consequence = (
        "Deleting it does not show it. If nobody has kept this secret, it is lost for good."
        if unread
        else "Deleting it does not show it. A tool call that names this reference is refused from then on."
    )
    terminal.write(
        f"Held for: {described}\n"
        f"{consequence}\n"
        f"Type '{_DELETE}' and press Enter to delete it, or press Enter alone to keep it: "
    )
    terminal.flush()
    if answers.readline().strip().lower() != _DELETE:
        terminal.write("The stored copy is kept under the same reference.\n")
        return 0
    try:
        held_secrets.release(reference)
    except AutomationCustodyError as refused:
        errors.write(f"The stored copy could not be deleted ({refused.reason.value}); it may still be held.\n")
        return 1
    terminal.write("The stored copy is deleted.\n")
    return 0


def _read_unseen(prompt: str) -> str:
    """Read one line from the person's terminal without echo, or refuse where echo cannot be turned off."""
    with warnings.catch_warnings():
        # The standard reader falls back to an echoed read and only warns; a secret is never read that way.
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt)


def hold_secret(
    *,
    single_use: bool,
    terminal: TextIO,
    answers: TextIO,
    errors: TextIO,
    read_unseen: Callable[[str], str] = _read_unseen,
    custody: Callable[[], HeldSecretCustody] = installed_held_secret_custody,
) -> int:
    """Ask the person for a secret without echo, hold it, and print only the reference it is held under.

    The person names what the secret is with a label, enters it twice, and
    gives the reference to whoever calls a tool with it. Nothing is asked
    for or held unless both the input and the output are a terminal, so the
    secret is typed by the person and never arrives through a pipe, an
    argument or a transcript.

    Returns:
        The process exit status: 0 when the secret is held, 2 when this is
        not a terminal, 1 when the label or the secret was refused, the two
        entries differ, echo could not be turned off, or the store could
        not hold it.
    """
    if not (terminal.isatty() and answers.isatty()):
        errors.write(_NOT_A_TERMINAL)
        return 2
    terminal.write("Label for this secret, so you can tell it apart in a listing (for example: profile password): ")
    terminal.flush()
    label = " ".join(answers.readline().split())
    if not label or len(label) > MAX_ENTERED_LABEL_CHARACTERS:
        errors.write(f"A label is 1 to {MAX_ENTERED_LABEL_CHARACTERS} characters. Nothing was held.\n")
        return 1
    try:
        first = bytearray(read_unseen("Secret (not shown as you type): "), "utf-8")
        second = bytearray(read_unseen("Enter it again to confirm: "), "utf-8")
    except (getpass.GetPassWarning, EOFError, OSError):
        errors.write("The secret could not be read without showing it on this terminal. Nothing was held.\n")
        return 1
    try:
        if first != second:
            errors.write("The two entries differ. Nothing was held.\n")
            return 1
        if not first or len(first) > MAX_ENTERED_SECRET_BYTES:
            errors.write(f"A secret is 1 to {MAX_ENTERED_SECRET_BYTES} bytes. Nothing was held.\n")
            return 1
        try:
            held = custody().hold_entered(label=label, secret=first, single_use=single_use)
        except AutomationCustodyError as refused:
            errors.write(f"The secret could not be held ({refused.reason.value}).\n")
            return 1
    finally:
        first[:] = bytes(len(first))
        second[:] = bytes(len(second))
    lifetime = (
        "It is deleted by the first tool call that presents this reference."
        if single_use
        else f"It stays until you delete it with `cadrumo-mcp {DELETE_HELD_OPTION} {held.reference}`."
    )
    terminal.write(
        f"Held as: {_described(_entry(held))}\n"
        f"{lifetime} `cadrumo-mcp {LIST_HELD_OPTION}` lists what is held, showing no secret.\n"
        "Give only this reference to the agent, which puts it in the tool argument that ends in _reference:\n"
        f"{held.reference}\n"
    )
    return 0


def _entry(held: HeldSecret) -> HeldSecretEntry:
    """Reduce a held secret to what a listing may say of it."""
    return HeldSecretEntry(held.reference, held.origin, held.held_at, entered=held.entered, single_use=held.single_use)


def _described(entry: HeldSecretEntry) -> str:
    """Say what one reference is held for and since when, in the words a listing prints."""
    if entry.origin is not None and entry.held_at is not None:
        since = f"held since {entry.held_at:%Y-%m-%d %H:%M} UTC"
        if not entry.entered:
            return f"{entry.origin}, {since}"
        lifetime = "for one use" if entry.single_use else "until you delete it"
        return f"{entry.origin}, entered by you, {since}, {lifetime}"
    fault = AutomationCustodyCode.INVALID if entry.fault is None else entry.fault
    return f"unreadable ({fault.value})"


def _shown(secret: SecretBytes) -> str:
    """Return a secret as the text the person copies down."""
    raw = secret.get_secret_value()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return f"base64:{b64_encode(raw)}"
