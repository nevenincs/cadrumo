"""Explicit in-memory native-port fault injection for synthetic custody tests."""

from pydantic import SecretBytes

from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)


class MemoryNativePort:
    """Explicit fault injector, never used by production composition."""

    backend = NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], SecretBytes] = {}
        self.unavailable = False
        self.fail_write: str | None = None
        self.commit_before_failure = False
        self.fail_delete = False

    def read(self, namespace: str, account: str) -> SecretBytes | None:
        if self.unavailable:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return self.items.get((namespace, account))

    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        if self.unavailable:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        failing = self.fail_write == namespace
        if not failing or self.commit_before_failure:
            self.items[namespace, account] = value
        if failing:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def delete(self, namespace: str, account: str) -> None:
        if self.unavailable or self.fail_delete:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        self.items.pop((namespace, account), None)
