"""Public compatibility surface for relocated AEAT auth contracts."""

from __future__ import annotations

from .adapters.outbound.aeat.auth import (
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatSession,
    ClaveMovilAuthProvider,
)
from .application.auth import select_provider
from .core.access_gate import (
    AeatAccessGate,
    AeatGateEnvSnapshot,
    AeatLiveReadNotEnabledError,
)
from .core.file_permissions import restrict_file_permissions
from .domain.auth import AuthProvider, AuthProviderKind

__all__ = [
    "AeatAccessGate",
    "AeatAuthenticator",
    "AeatGateEnvSnapshot",
    "AeatLiveReadNotEnabledError",
    "AeatLoginAssertion",
    "AeatSession",
    "AuthProvider",
    "AuthProviderKind",
    "ClaveMovilAuthProvider",
    "restrict_file_permissions",
    "select_provider",
]
