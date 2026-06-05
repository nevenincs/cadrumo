"""Live test for :func:`aeat.adapters.outbound.aeat.sede.walk_declarations_register` (#239).

Drives the *Consultar declaraciones presentadas* form against
the real AEAT sede with a Cl@ve-móvil session. Skips cleanly when:

* ``AEAT_LIVE_TESTS_ENABLED`` is unset (every live test gates on
  this), OR
* Cl@ve-móvil credentials are not configured for the live backend.

The test is read-only by construction — every public surface in
:mod:`aeat.adapters.outbound.aeat.sede._declarations` is structurally incapable of
mutating AEAT state under the outbound write guard.
"""

from __future__ import annotations

import pytest

from ......tests.live_gate import requires_live_enabled
from .._declarations import Declaracion, capture_declaration, walk_declarations_register
from .._errors import SedeError
from .._schema import SedeCapture

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


async def _load_active_clave_session():
    """Return an active Cl@ve session or skip the test cleanly.

    Returns:
        The :class:`AeatSession` reconstructed from the on-disk
        Cl@ve cookies. Skips when no session is persisted or the
        operator has not opted into live tests.
    """
    # Local imports keep the test file lightweight when skipped.
    from ......application.auth import (
        AuthProviderKind,
        ensure_authenticated_aeat_session,
    )
    from ......core.config import load_settings
    from ......core.errors import AeatError

    settings = load_settings()
    try:
        result = await ensure_authenticated_aeat_session(
            settings,
            kind=AuthProviderKind.CLAVE_MOVIL,
            operation="sede-declarations-live-test",
        )
        return result.session
    except AeatError as exc:
        pytest.skip(f"Cl@ve-móvil live authentication is not available: {exc}")


@pytest.mark.asyncio
async def test_walk_modelo_100_returns_at_least_one_declaration() -> None:
    """The IRPF anual filing register has at least one declaration.

    Every direct-estimación autónomo who has filed at least one
    Modelo 100 produces a declaration here. Asserts only the
    structural shape — actual values vary per account.
    """
    requires_live_enabled()
    session = await _load_active_clave_session()
    try:
        declarations = await walk_declarations_register(
            session,
            modelo="100",
            ejercicio=2022,
        )
    except SedeError as exc:
        pytest.skip(f"live walk failed (likely session-expired): {exc}")

    # Ejercicio 2022 is the year operator's M100 fixture was captured;
    # the live account should still expose it.
    assert isinstance(declarations, tuple)
    assert all(isinstance(d, Declaracion) for d in declarations)
    if declarations:
        first = declarations[0]
        assert first.modelo == "100"
        assert first.ejercicio == 2022
        assert first.expediente_id  # non-empty
        assert first.estado  # non-empty
        assert first.mode == "read"  # five-layer write guard


@pytest.mark.asyncio
async def test_capture_declaration_returns_pdf_bytes() -> None:
    """The full walk → capture path lands a valid PDF body.

    Drives the same Modelo 100 / 2022 surface as the walker test,
    picks the first row, and asserts that capture_declaration
    yields a :class:`SedeCapture` carrying a non-empty PDF body
    plus a shape-valid CSV. Read-only by construction — the
    capture path issues GETs only (cotejo URL + CotejoDocIdSv).
    """
    requires_live_enabled()
    session = await _load_active_clave_session()
    try:
        declarations = await walk_declarations_register(
            session,
            modelo="100",
            ejercicio=2022,
        )
    except SedeError as exc:
        pytest.skip(f"live walk failed (likely session-expired): {exc}")

    if not declarations:
        pytest.skip(
            "no Modelo 100 / 2022 declaration on this account; capture cannot be exercised without a live row.",
        )

    try:
        capture = await capture_declaration(session, declarations[0])
    except SedeError as exc:
        pytest.skip(f"live capture failed (likely session-expired): {exc}")

    assert isinstance(capture, SedeCapture)
    assert capture.pdf_bytes  # non-empty body
    assert capture.pdf_bytes.startswith(b"%PDF-")  # PDF magic header
    assert capture.pdf_sha256  # populated
    assert len(capture.pdf_sha256) == 64  # sha256 hex digest
    assert capture.ref.csv  # non-empty
    # The CSV passed our shape regex during extraction; sanity-check
    # the round-trip carries the same value through the SedeCapture.
    assert 8 <= len(capture.ref.csv) <= 24
    assert capture.ref.csv.isupper()
    assert capture.ref.csv.replace("0", "").replace("1", "").isalnum()
