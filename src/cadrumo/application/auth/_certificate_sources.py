"""Named multi-certificate source registry for the certificate auth provider.

A gestor managing several taxpayers typically holds several PKCS#12
certificates — their own personal certificate plus one apoderado
certificate per represented entity. Before this module, the certificate
auth provider carried exactly one certificate path
(:attr:`~application.auth.AuthState.certificate_path`), configured through
``aeat config auth configure --provider certificate --file PATH``: adopting
a different certificate meant re-running that command and losing track of
the previous path.

This module adds a named registry
(:attr:`~application.auth.AuthState.certificate_sources`) on top of the existing
single-path field:
:func:`~application.auth._certificate_sources.register_certificate_source` adds
or re-points a named source,
:func:`~application.auth._certificate_sources.list_certificate_sources`
enumerates them,
:func:`~application.auth._certificate_sources.select_certificate_source` marks
one active and mirrors its path onto ``certificate_path`` (so every existing
consumer — the backend health probe, live login preconditions, ``auth status`` /
``auth test`` — keeps reading the one field it already knows about), and
:func:`~application.auth._certificate_sources.remove_certificate_source` retires
a registered source.

Rotation hooks (invalidating cached state when the active certificate
changes on disk), a filesystem-fallback loader, external keyring/1Password
backends, and service-account impersonation UX are explicitly out of scope
for this module.

See Also:
    :class:`~application.auth.AuthState`
        Persisted local auth selection embedded in workflow state; carries
        the ``certificate_sources`` registry and ``certificate_path``
        mirror this module maintains.
    :func:`~application.auth.configure_operator_auth`
        Configures the active auth *provider*; this module manages
        certificate *sources* within the certificate provider.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core.time import now
from ._models import AuthState, CertificateSourceRecord

if TYPE_CHECKING:
    from ..workflow import WorkflowState


class CertificateSourceNoActiveBucketError(Exception):
    """Raised when a certificate-source mutation runs before an active profile bucket exists."""


class CertificateSourceNotFoundError(KeyError):
    """Raised when a requested certificate source name is not registered."""


def _auth_state(state: WorkflowState) -> AuthState:
    auth = state.auth
    if isinstance(auth, dict):
        return AuthState.model_validate(auth)
    return auth


def _with_auth_state(state: WorkflowState, auth: AuthState) -> WorkflowState:
    return state.model_copy(update={"auth": auth, "updated_at": now()})


def register_certificate_source(
    state: WorkflowState,
    *,
    name: str,
    certificate_path: Path,
    friendly_name: str | None = None,
) -> WorkflowState:
    """Register (or re-point) a named certificate source in ``state``.

    Adding a source with a ``name`` that already exists overwrites its
    ``certificate_path``/``friendly_name`` and refreshes
    ``registered_at`` rather than erroring — re-registration is the
    supported way to point an existing name at a renewed certificate
    file. Registering a source never changes which source is active;
    call
    :func:`~application.auth._certificate_sources.select_certificate_source`
    explicitly to activate it.

    Returns the updated :class:`~application.workflow.WorkflowState`.
    """
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("certificate source name must not be blank")
    auth = _auth_state(state)
    record = CertificateSourceRecord(
        name=normalized_name,
        certificate_path=str(certificate_path),
        friendly_name=friendly_name.strip() if friendly_name else None,
        registered_at=now(),
    )
    sources = dict(auth.certificate_sources)
    sources[normalized_name] = record
    return _with_auth_state(state, auth.model_copy(update={"certificate_sources": sources}))


def list_certificate_sources(state: WorkflowState) -> tuple[CertificateSourceRecord, ...]:
    """Return every registered :class:`~application.auth.CertificateSourceRecord`."""
    auth = _auth_state(state)
    return tuple(sorted(auth.certificate_sources.values(), key=lambda record: record.name))


def active_certificate_source(state: WorkflowState) -> CertificateSourceRecord | None:
    """Return the active :class:`~application.auth.CertificateSourceRecord`, if any."""
    auth = _auth_state(state)
    if auth.active_certificate_source is None:
        return None
    return auth.certificate_sources.get(auth.active_certificate_source)


def select_certificate_source(state: WorkflowState, *, name: str) -> WorkflowState:
    """Mark the certificate source ``name`` active and mirror its path onto ``certificate_path``.

    Every other registered source stays registered but inactive. The
    provider selection (``AuthState.provider``) is left untouched:
    selecting a certificate source is orthogonal to choosing which auth
    provider is active, so an operator may register and select sources
    ahead of switching ``--provider certificate`` on.

    Raises:
        CertificateSourceNotFoundError: When ``name`` is not registered.

    Returns the updated :class:`~application.workflow.WorkflowState`.
    """
    auth = _auth_state(state)
    normalized_name = name.strip()
    record = auth.certificate_sources.get(normalized_name)
    if record is None:
        raise CertificateSourceNotFoundError(normalized_name)
    updated_auth = auth.model_copy(
        update={
            "active_certificate_source": normalized_name,
            "certificate_path": record.certificate_path,
            "configured_at": now(),
        },
    )
    return _with_auth_state(state, updated_auth)


def remove_certificate_source(state: WorkflowState, *, name: str) -> tuple[WorkflowState, bool]:
    """Remove the certificate source ``name`` from the registry.

    When ``name`` is the active source, the active selection is cleared
    (``active_certificate_source`` becomes ``None``); ``certificate_path``
    is left as-is, matching the pre-existing single-certificate contract
    where clearing provider custody is a distinct ``auth reset`` operation.

    Returns a ``(state, removed)`` tuple; ``removed`` is ``False`` when
    ``name`` was not registered (a no-op, not an error).
    """
    auth = _auth_state(state)
    normalized_name = name.strip()
    if normalized_name not in auth.certificate_sources:
        return state, False
    sources = dict(auth.certificate_sources)
    del sources[normalized_name]
    update: dict[str, object] = {"certificate_sources": sources}
    if auth.active_certificate_source == normalized_name:
        update["active_certificate_source"] = None
    return _with_auth_state(state, auth.model_copy(update=update)), True


__all__ = [
    "CertificateSourceNoActiveBucketError",
    "CertificateSourceNotFoundError",
    "active_certificate_source",
    "list_certificate_sources",
    "register_certificate_source",
    "remove_certificate_source",
    "select_certificate_source",
]
