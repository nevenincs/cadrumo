"""Recovery enrollment never acquires a prompt it was not given.

Enrollment must unwrap the master key before it can mint a candidate envelope,
so it needs the secret-store passphrase. Leaving that resolution to the storage
substrate's default hands the operation a bare terminal read that blocks on a
console-less host and can degrade to an echoing one — behaviour an application
caller never asked for and cannot see coming.

An interactive caller therefore supplies its own guarded prompt, and a caller
that supplies nothing gets the non-interactive resolver: it reads the
configured passphrase and refuses when there is none, rather than silently
escalating to a prompt. These drive the real production operation against a
real settings object, a real file secret store, real Argon2id key wrapping and
a real BIP-39 mint; no mocks, stubs, monkeypatches, skips, or expected-fail
markers. The ``confirm`` and ``passphrase_callback`` callables are the
production contract's caller-supplied callbacks, not doubles.

Each test runs inside a sessionless storage root so the custody audit event
degrades to its documented no-op instead of reaching for whichever profile the
developer's own pointer file happens to name.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from ....adapters.persistence.storage import (
    MasterKeyPassphraseMismatchError,
    MasterKeyUnavailableError,
    SecretStoreError,
)
from ....adapters.persistence.storage.master_key import FileFallbackMasterKeyProvider
from ....core.config import SecretStoreBackend, Settings
from ....tests.secure_sql import isolated_sessionless_storage_root
from .._custody import create_recovery_code

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_CALLBACK_PASSPHRASE = "enrollment-callback-store-passphrase-51ce"  # noqa: S105 - test fixture input
_CONFIGURED_PASSPHRASE = "enrollment-configured-passphrase-a7d0"  # noqa: S105 - test fixture input


def _settings(tmp_path: Path, *, passphrase: str | None) -> Settings:
    """Return a file-backed settings object bound to ``tmp_path``.

    The explicit ``cadrumo_secret_passphrase`` keyword keeps an ambient
    environment passphrase out of the run: an initialiser argument is the
    highest-priority settings source, so ``None`` here really means "no
    passphrase is configured" even on a machine that exports one. Verified by
    execution rather than assumed — without the keyword the environment value
    is visible, with it the field is ``None``.
    """
    return Settings(
        cadrumo_local_storage_root=tmp_path / "cadrumo-storage",
        cadrumo_secret_store_dir=tmp_path / "secrets",
        cadrumo_secret_store_backend=SecretStoreBackend.FILE,
        cadrumo_secret_passphrase=SecretStr(passphrase) if passphrase is not None else None,
    )


def _provision(tmp_path: Path, passphrase: str) -> None:
    """Mint a real file secret store under ``passphrase``.

    The store is provisioned deliberately, so an enrollment refusal below can
    only be about resolving the passphrase — an unprovisioned store refuses for
    an unrelated reason and would make the assertions pass vacuously.
    """
    FileFallbackMasterKeyProvider(
        store_dir=tmp_path / "secrets",
        passphrase_callback=lambda: passphrase,
    ).provision_master_key()


def test_enrollment_without_a_callback_refuses_rather_than_prompting(tmp_path: Path) -> None:
    """No configured passphrase and no callback is a typed refusal, not a prompt.

    A prompt reached here would block a non-interactive driver indefinitely.
    The store is fully provisioned and the recovery envelope absent, so the
    only thing standing between this call and a minted candidate is resolving
    the passphrase; the refusal is therefore attributable to that resolution
    and to nothing else.
    """
    _provision(tmp_path, _CALLBACK_PASSPHRASE)
    settings = _settings(tmp_path, passphrase=None)
    shown: list[str] = []

    def confirm(words: str) -> str:
        shown.append(words)
        return words

    with isolated_sessionless_storage_root(tmp_path=tmp_path), pytest.raises(SecretStoreError) as refusal:
        create_recovery_code(confirm=confirm, settings=settings)

    assert not isinstance(refusal.value, MasterKeyUnavailableError), (
        "the refusal must be about the absent passphrase channel, not about the key "
        f"material itself; got {type(refusal.value).__name__}"
    )
    assert shown == [], "the refusal must precede minting and displaying a candidate mnemonic"
    assert not (tmp_path / "secrets" / "master.recovery.key").exists(), (
        "a refused enrollment must not install a recovery envelope"
    )


def test_enrollment_callback_is_the_passphrase_authority(tmp_path: Path) -> None:
    """An explicit callback supersedes the configured value, not merely supplements it.

    This is what lets the interactive door keep its promise: the CLI passes a
    prompt-backed callback, and the configured environment value — a legitimate
    channel for a non-interactive driver to unlock the store directly — is not
    consulted behind the operator's back. Proven by provisioning the store
    under the callback's value while configuring a different one: the
    enrollment can only unwrap the master key if the callback won, and the
    configured value is shown to be genuinely wrong for this store.
    """
    _provision(tmp_path, _CALLBACK_PASSPHRASE)
    settings = _settings(tmp_path, passphrase=_CONFIGURED_PASSPHRASE)
    callback_calls: list[int] = []

    def passphrase_callback() -> str:
        callback_calls.append(1)
        return _CALLBACK_PASSPHRASE

    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        result = create_recovery_code(
            confirm=lambda words: words,
            passphrase_callback=passphrase_callback,
            settings=settings,
        )

    assert callback_calls, "the explicit callback must be the resolver the provider consults"
    assert result.rotated is False
    assert (tmp_path / "secrets" / "master.recovery.key").is_file()

    opened = FileFallbackMasterKeyProvider(
        store_dir=tmp_path / "secrets",
        passphrase_callback=lambda: _CALLBACK_PASSPHRASE,
    )
    assert len(opened.get_master_key()) == 32, "the store must open under the callback's passphrase"

    refused = FileFallbackMasterKeyProvider(
        store_dir=tmp_path / "secrets",
        passphrase_callback=lambda: _CONFIGURED_PASSPHRASE,
    )
    with pytest.raises(MasterKeyPassphraseMismatchError):
        refused.get_master_key()
