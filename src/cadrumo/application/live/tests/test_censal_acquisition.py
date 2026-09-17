"""Contracts of the live censal acquisition door.

Two things are proven here without contacting AEAT: the read is gated by
the live-read opt-in like every other remote navigation, and the door
depends only on its application-owned fetch capability. The second matters
because the censal consulta sits in an area AEAT titles "Consulta y
modificación" — the write sibling is one link away, and the acquisition
door must not know the concrete reader.

The parse and no-write-surface guarantees belong to the sede reader and
are proven in its own suite; the projection and adopt/defer split belong
to :mod:`user_profile` and are proven in theirs.
"""

from __future__ import annotations

import ast
import asyncio
import inspect

import pytest

from cadrumo.application.auth.protocols import BrowserSessionPort
from cadrumo.application.auth.session_types import AeatSession
from cadrumo.application.user_profile.censal_observation import CensalObservation
from cadrumo.core.config import Settings

from ....core.access_gate.errors import AeatLiveReadNotEnabledError
from ...auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from ..censo import (
    LIVE_CENSAL_READ_OPERATION,
    pull_censal_datos,
)
from ._operator_scope_fakes import build_inward_operator_scope_ports_for_active_route

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()
_CERTIFICATE_SECRET_BACKEND_FACTORY = InMemoryCertificateSecretBackendFactory()


async def _unused_browser_session_factory(settings: Settings) -> BrowserSessionPort:
    del settings
    raise AssertionError("the live-read gate must refuse before opening a browser")


async def _unused_censal_fetch(
    session: AeatSession,
    *,
    taxpayer_nif: str,
    settings: Settings,
) -> CensalObservation:
    del session, taxpayer_nif, settings
    raise AssertionError("the live-read gate must refuse before fetching censo data")


pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _sede_imports_in(source: str) -> set[str]:
    """Return every symbol a source fragment imports from the sede adapter."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("aeat.sede"):
            names.update(alias.name for alias in node.names)
    return names


def test_the_read_refuses_under_pytest_without_the_live_opt_in() -> None:
    """The acquisition enters through the live-read gate, so a test run cannot reach AEAT.

    Real behaviour, not inspection: the coroutine is driven to completion
    and refuses. A door that skipped the gate would instead proceed to
    open a browser session, which is exactly what the opt-in exists to
    prevent.
    """
    with pytest.raises(AeatLiveReadNotEnabledError):
        asyncio.run(
            pull_censal_datos(
                certificate_secret_backend_factory=_CERTIFICATE_SECRET_BACKEND_FACTORY,
                browser_session_factory=_unused_browser_session_factory,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                censal_fetch_port=_unused_censal_fetch,
                guarded_read_context="test_censal_acquisition",
            )
        )


def test_the_door_reaches_only_the_application_fetch_capability() -> None:
    """The application door imports no concrete Sede symbol.

    The consulta page AEAT serves carries controls, and the censal modification
    surface is reachable from it. The concrete reader is therefore an outer
    binding concern; this door accepts only the application-owned capability.
    """
    assert _sede_imports_in(inspect.getsource(pull_censal_datos)) == set()


def test_a_submitting_import_would_be_caught() -> None:
    """Anti-tautology: the import scan reports what a source actually declares.

    Without this, a scan that silently found nothing (a changed module
    path, a renamed package suffix) would return an empty set and the
    assertion above would be a permanent green regardless of what the
    door imports.
    """
    found = _sede_imports_in(
        "def read():\n    from ...adapters.outbound.aeat.sede import fetch_censal_datos, submit_censal_modification\n",
    )
    assert found == {"fetch_censal_datos", "submit_censal_modification"}
    assert found != {"fetch_censal_datos"}


def test_the_read_operation_names_the_surface_it_unlocks() -> None:
    """The operation label is censal-specific, so a provider prompt says what it is for."""
    assert LIVE_CENSAL_READ_OPERATION == "live-censal-read"
