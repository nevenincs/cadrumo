"""Exact noninteractive login-Keychain credential custody and verified replacement."""

from __future__ import annotations

import secrets
from collections.abc import Generator
from contextlib import contextmanager

from pydantic import SecretBytes

from .....application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    NativeSecretBackend,
)
from .macos_keychain_contracts import DUPLICATE, MAX_SECRET_BYTES, NOT_FOUND, KeychainApi, KeychainItemIdentity
from .macos_keychain_policy import keychain_refusal, require_keychain_status, require_keychain_target
from .macos_login_keychain import LoginKeychain


def _native_api() -> KeychainApi:
    try:
        return LoginKeychain()
    except (OSError, AttributeError, ValueError, KeyError):
        raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE) from None


class MacOSKeychainAutomationSecretStore:
    """Exact encrypted login-Keychain custody under the current OS account."""

    backend = NativeSecretBackend.MACOS_KEYCHAIN

    @staticmethod
    @contextmanager
    def _bound(namespace: str, account: str) -> Generator[tuple[KeychainApi, KeychainItemIdentity]]:
        require_keychain_target(namespace, account)
        try:
            api = _native_api()
            with api.session() as path:
                yield api, KeychainItemIdentity(namespace, account, path)
        except (OSError, AttributeError, ValueError, KeyError):
            raise keychain_refusal(AutomationCustodyCode.UNAVAILABLE) from None

    @staticmethod
    def _read(api: KeychainApi, identity: KeychainItemIdentity) -> SecretBytes | None:
        item = api.read(identity)
        if item is None:
            return None
        if (
            item.identity != identity
            or item.account_access is not True
            or not isinstance(item.data, bytes)
            or not 0 < len(item.data) <= MAX_SECRET_BYTES
        ):
            raise keychain_refusal()
        return SecretBytes(item.data)

    def read(self, namespace: str, account: str) -> SecretBytes | None:
        """Read one exact-bound native item with authentication UI disabled."""
        with self._bound(namespace, account) as (api, identity):
            return self._read(api, identity)

    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        """Update or add then read-back-verify; never delete before replacement."""
        require_keychain_target(namespace, account)
        raw = value.get_secret_value()
        if not 0 < len(raw) <= MAX_SECRET_BYTES:
            raise keychain_refusal()
        with self._bound(namespace, account) as (api, identity):
            self._read(api, identity)
            status = api.update(identity, raw)
            if status == NOT_FOUND:
                status = api.add(identity, raw)
                if status == DUPLICATE:
                    self._read(api, identity)
                    status = api.update(identity, raw)
            if status in (NOT_FOUND, DUPLICATE):
                raise keychain_refusal(AutomationCustodyCode.CONFLICT)
            require_keychain_status(status)
            observed = self._read(api, identity)
            if observed is None or not secrets.compare_digest(observed.get_secret_value(), raw):
                raise keychain_refusal()

    def delete(self, namespace: str, account: str) -> None:
        """Delete only a validated exact item and verify its absence."""
        with self._bound(namespace, account) as (api, identity):
            self._read(api, identity)
            status = api.delete(identity)
            if status != NOT_FOUND:
                require_keychain_status(status)
            if self._read(api, identity) is not None:
                raise keychain_refusal()
