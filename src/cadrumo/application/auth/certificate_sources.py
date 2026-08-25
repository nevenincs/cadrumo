"""Named multi-certificate source registry for the certificate auth provider.

A gestor managing several taxpayers typically holds several PKCS#12
certificates — their own personal certificate plus one apoderado
certificate per represented entity. Before this module, the certificate
auth provider carried exactly one ``certificate_path`` on
:class:`~application.auth.models.AuthState`, configured through
``aeat config auth configure --provider certificate --file PATH``: adopting
a different certificate meant re-running that command and losing track of
the previous path.

This module adds a named ``certificate_sources`` registry to
:class:`~application.auth.models.AuthState`:
:func:`~application.auth.certificate_sources.register_certificate_source` adds
or re-points a named source,
:func:`~application.auth.certificate_sources.list_certificate_sources`
enumerates them,
:func:`~application.auth.certificate_sources.select_certificate_source` marks
one active for the canonical credential resolver, and
:func:`~application.auth.certificate_sources.remove_certificate_source` retires
a registered source.

Rotation hooks (invalidating cached state when the active certificate
changes on disk), a filesystem-fallback loader, external keyring/1Password
backends, and service-account impersonation UX are explicitly out of scope
for this module.

See Also:
    :class:`~application.auth.models.AuthState`
        Persisted local auth selection embedded in workflow state.
    :func:`~application.auth.configure_operator_auth`
        Configures the active auth *provider*; this module manages
        certificate *sources* within the certificate provider.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from ...core.time import now
from .models import AuthState, CertificateSourceRecord
from .operator_results import CertificateSourceNotFoundError

if TYPE_CHECKING:
    from cadrumo.application.workflow.state_models import WorkflowState


class CertificateSourceNoActiveBucketError(Exception):
    """Raised when a certificate-source mutation runs before an active profile bucket exists."""

    __bare_base_rationale__: ClassVar[str] = (
        "certificate-source mutation precondition signal for an uninitialised local profile bucket"
    )


def auth_state(state: WorkflowState) -> AuthState:
    """Return ``state``'s typed authentication state."""
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
    file. Registering a source never changes which source
    is active; call
    :func:`~application.auth.certificate_sources.select_certificate_source`
    explicitly to activate it.

    Returns the updated :class:`~application.workflow.WorkflowState`.
    """
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("certificate source name must not be blank")
    auth = auth_state(state)
    record = CertificateSourceRecord(
        name=normalized_name,
        certificate_path=str(certificate_path),
        friendly_name=friendly_name.strip() if friendly_name else None,
        registered_at=now(),
    )
    sources = dict(auth.certificate_sources)
    sources[normalized_name] = record
    updates: dict[str, object] = {"certificate_sources": sources}
    if auth.active_certificate_source == normalized_name:
        updates["configured_at"] = record.registered_at
    return _with_auth_state(state, auth.model_copy(update=updates))


def list_certificate_sources(state: WorkflowState) -> tuple[CertificateSourceRecord, ...]:
    """Return every registered :class:`~application.auth.models.CertificateSourceRecord`."""
    auth = auth_state(state)
    return tuple(sorted(auth.certificate_sources.values(), key=lambda record: record.name))


def active_certificate_source(state: WorkflowState) -> CertificateSourceRecord | None:
    """Return the active :class:`~application.auth.models.CertificateSourceRecord`, if any."""
    auth = auth_state(state)
    if auth.active_certificate_source is None:
        return None
    return auth.certificate_sources.get(auth.active_certificate_source)


def select_certificate_source(state: WorkflowState, *, name: str) -> WorkflowState:
    """Mark the certificate source ``name`` active.

    Every other registered source stays registered but inactive. The
    provider selection (``AuthState.provider``) is left untouched:
    selecting a certificate source is orthogonal to choosing which auth
    provider is active, so an operator may register and select sources
    ahead of switching ``--provider certificate`` on.

    Raises:
        CertificateSourceNotFoundError: When ``name`` is not registered.

    Returns the updated :class:`~application.workflow.WorkflowState`.
    """
    auth = auth_state(state)
    normalized_name = name.strip()
    record = auth.certificate_sources.get(normalized_name)
    if record is None:
        raise CertificateSourceNotFoundError(
            translated_message="application.auth.operator.errors.certificate_source_not_found",
            context={"name": normalized_name},
        )
    updated_auth = auth.model_copy(
        update={
            "active_certificate_source": normalized_name,
            "configured_at": now(),
        },
    )
    return _with_auth_state(state, updated_auth)


def remove_certificate_source(state: WorkflowState, *, name: str) -> tuple[WorkflowState, bool]:
    """Remove the certificate source ``name`` from the registry.

    When ``name`` is the active source, the active selection is cleared.
    A same-path unnamed credential is cleared too; a removed named source
    must not remain effective through the unnamed field.

    Returns a ``(state, removed)`` tuple; ``removed`` is ``False`` when
    ``name`` was not registered (a no-op, not an error).
    """
    auth = auth_state(state)
    normalized_name = name.strip()
    if normalized_name not in auth.certificate_sources:
        return state, False
    sources = dict(auth.certificate_sources)
    del sources[normalized_name]
    update: dict[str, object] = {"certificate_sources": sources}
    if auth.active_certificate_source == normalized_name:
        update["active_certificate_source"] = None
        if auth.certificate_path == auth.certificate_sources[normalized_name].certificate_path:
            update["certificate_path"] = None
    return _with_auth_state(state, auth.model_copy(update=update)), True


__all__ = [
    "CertificateSourceNoActiveBucketError",
    "active_certificate_source",
    "auth_state",
    "list_certificate_sources",
    "register_certificate_source",
    "remove_certificate_source",
    "select_certificate_source",
]
