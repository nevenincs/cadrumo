"""The AUTO-backend keychain read is bounded, and over-budget means locked.

macOS Keychain ACLs are per-binary: a process distinct from the one that
minted the master-key item must answer an authorization dialog, and a
headless, backgrounded, or warm-server context can never show it. The read
then blocks forever and the operator sees the command hang with no output.

These tests exercise the real bound against a REAL blocking read -- a
provider whose keychain call genuinely does not return -- rather than
simulating a timeout. The blocking is the point: the guard must convert an
unbounded wait into a typed refusal within its budget.

The refusal TYPE is the load-bearing assertion. A timed-out read is the
LOCKED case (the backend works, the entry is merely inaccessible), so it
must take the caller's divergence-safe branch. Reporting it as an unusable
backend would instead take the unconditional file-fallback branch and mint
a fresh master key while the real one sits behind the unanswered dialog,
silently diverging the two.

This bound is verifiable on any platform because it bounds elapsed TIME,
not a platform API: a read that exceeds its budget degrades identically
whatever made it slow.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Iterator

import pytest

from ...errors import KeyringUnavailableError, MasterKeyKeychainLockedError
from .._master_key import KeyringMasterKeyProvider, _read_master_key_within_budget

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUDGET_S = 0.5


@contextlib.contextmanager
def _active_keyring_backend(backend: object) -> Iterator[None]:
    """Install *backend* as the real process-wide keyring backend, then restore it."""
    import keyring

    previous = keyring.get_keyring()
    keyring.set_keyring(backend)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # reason: the probe fixtures are deliberately unusable stand-ins, not KeyringBackend subclasses
    try:
        yield
    finally:
        keyring.set_keyring(previous)


class _BlockingKeyringProvider:
    """A provider whose keychain read genuinely blocks, as macOS's does."""

    def __init__(self) -> None:
        self.released = threading.Event()
        self.entered = threading.Event()

    def get_master_key(self) -> bytes:
        """Block until explicitly released, mimicking an unanswered dialog."""
        self.entered.set()
        self.released.wait()
        return b"\x00" * 32


class _PromptKeyringProvider:
    """A provider that answers slowly but within budget."""

    def __init__(self, delay_s: float) -> None:
        self._delay_s = delay_s

    def get_master_key(self) -> bytes:
        """Return after a delay, mimicking an operator answering the prompt."""
        time.sleep(self._delay_s)
        return b"\x01" * 32


class TestOverBudgetReadIsLocked:
    """A read that does not return within budget refuses as locked."""

    def test_blocking_read_raises_locked_not_unavailable(self) -> None:
        provider = _BlockingKeyringProvider()
        try:
            with pytest.raises(MasterKeyKeychainLockedError) as caught:
                _read_master_key_within_budget(provider, timeout_s=_BUDGET_S)
        finally:
            provider.released.set()

        # Not the unusable-backend error: that one routes to an unconditional
        # file fallback and would mint a key diverging from the keychain's.
        assert not isinstance(caught.value, KeyringUnavailableError)
        assert provider.entered.is_set(), "the guard must actually attempt the read"

    def test_the_refusal_names_the_operator_escape_hatch(self) -> None:
        """A hang the operator cannot see needs a route out, not just a stop."""
        provider = _BlockingKeyringProvider()
        try:
            with pytest.raises(MasterKeyKeychainLockedError) as caught:
                _read_master_key_within_budget(provider, timeout_s=_BUDGET_S)
        finally:
            provider.released.set()

        assert "CADRUMO_SECRET_STORE_BACKEND=file" in str(caught.value)

    def test_the_wait_is_bounded_by_the_budget(self) -> None:
        """Anti-tautology: prove the budget bounds the wait, not the provider.

        Without this, a guard that returned instantly for an unrelated
        reason would satisfy every assertion above while bounding nothing.
        """
        provider = _BlockingKeyringProvider()
        started = time.monotonic()
        try:
            with pytest.raises(MasterKeyKeychainLockedError):
                _read_master_key_within_budget(provider, timeout_s=_BUDGET_S)
        finally:
            provider.released.set()
        elapsed = time.monotonic() - started

        assert elapsed >= _BUDGET_S, "returned before the budget elapsed; the wait is not real"
        assert elapsed < _BUDGET_S * 20, "did not return promptly after the budget; the bound did not fire"


class TestWithinBudgetIsUnchanged:
    """Reads that complete in time keep their existing behaviour verbatim."""

    def test_a_prompt_answered_within_budget_succeeds(self) -> None:
        _read_master_key_within_budget(_PromptKeyringProvider(0.01), timeout_s=_BUDGET_S)

    def test_an_unusable_backend_still_reports_unavailable(self) -> None:
        """The bound must not reclassify a genuine backend failure as locked.

        This drives the REAL provider against the REAL no-op placeholder
        backend the ``keyring`` package installs on a machine with no
        usable keychain, so production's own backend probe raises the
        error the guard has to pass through. The guard re-raises whatever
        the read raised, so covering the one real error the platform can
        actually produce covers the re-raise for every type.
        """
        from keyring.backends import fail

        started = time.monotonic()
        with _active_keyring_backend(fail.Keyring()), pytest.raises(KeyringUnavailableError) as caught:
            _read_master_key_within_budget(KeyringMasterKeyProvider(), timeout_s=_BUDGET_S)
        elapsed = time.monotonic() - started

        # Not the locked error: that one routes through pre-existing
        # file-fallback artefacts or refuses, where an unusable backend
        # may fall back unconditionally.
        assert not isinstance(caught.value, MasterKeyKeychainLockedError)
        # A fast real failure must surface as itself, not as a budget timeout.
        assert elapsed < _BUDGET_S, "the real error waited out the budget instead of propagating"
