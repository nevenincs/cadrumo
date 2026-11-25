"""Host-composed admission gate for tax identities found by redaction.

Redaction scans wide and admits narrowly: a span shaped like a Spanish NIF/CIF
or a prefixed NIF-IVA is only hashed when it really is one, because the same
shapes cover ordinary operator output (``SE-2026-000412``, ``F-2026-0142``, the
groups of a printed IBAN). Deciding that needs the Spanish control-character
tables and the dated per-Member-State NIF-IVA formats, which are published
registry authority this core module cannot import.

The process host binds the authority-backed gate. Without one -- or when the
bound gate reports that its authority is unavailable -- redaction admits on
lexical shape alone, which over-redacts ordinary output rather than letting a
real identity through.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Protocol

from ..process_binding import ProcessScopedBinding


class TaxIdentityAdmission(Protocol):
    """Decide whether a normalised span is a real tax identity.

    Each method returns ``None`` when its authority cannot be consulted, so the
    caller applies its own fail-safe instead of treating absence as refusal.
    """

    def admits_spanish_identity(self, normalised: str) -> bool | None:
        """Return whether ``normalised`` is a valid Spanish NIF, NIE, or CIF."""
        ...

    def admits_nif_iva(self, normalised: str) -> bool | None:
        """Return whether ``normalised`` matches its Member State's NIF-IVA format."""
        ...


_TAX_IDENTITY_ADMISSION: ProcessScopedBinding[TaxIdentityAdmission] = ProcessScopedBinding(
    "cadrumo_tax_identity_admission",
)


@contextmanager
def bind_tax_identity_admission(admission: TaxIdentityAdmission | None) -> Generator[TaxIdentityAdmission | None]:
    """Publish ``admission`` process-wide for the scope, restoring the previous gate after.

    ``None`` suspends the gate for the scope, leaving redaction on its fallback.

    Process-wide rather than context-local: redaction callers can run on worker
    threads and fresh event-loop contexts that never inherit a context variable.
    """
    previous = _TAX_IDENTITY_ADMISSION.get()
    _TAX_IDENTITY_ADMISSION.bind(admission)
    try:
        yield admission
    finally:
        _TAX_IDENTITY_ADMISSION.bind(previous)


def tax_identity_admission() -> TaxIdentityAdmission | None:
    """Return the host-bound admission gate, or ``None`` when none is bound."""
    return _TAX_IDENTITY_ADMISSION.get()


@contextmanager
def lexical_tax_identity_redaction() -> Generator[None]:
    """Use conservative shape redaction without borrowing application authority.

    A diagnostic thread must not hold registry locks while opening authority
    files: application work needs those same locks. The context-only override
    leaves other threads' admission unchanged and hashes identity lookalikes
    rather than waiting for their registry-backed validation.
    """
    with _TAX_IDENTITY_ADMISSION.override(None):
        yield


__all__ = [
    "TaxIdentityAdmission",
    "bind_tax_identity_admission",
    "lexical_tax_identity_redaction",
    "tax_identity_admission",
]
