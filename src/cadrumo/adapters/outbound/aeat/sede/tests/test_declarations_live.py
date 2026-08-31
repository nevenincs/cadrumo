"""Live test for :func:`cadrumo.adapters.outbound.aeat.sede.walk_declarations_register`.

Drives the *Consultar declaraciones presentadas* form against
the real AEAT sede with a Cl@ve-móvil session. It is deselected when:

* ``CADRUMO_LIVE_TESTS_ENABLED`` is unset (every live test gates on
  this), OR
* Cl@ve-móvil credentials are not configured for the live backend.

After live opt-in, unavailable sessions or missing account data are failures.

The test drives read paths only. Note that this is a property the
package's guards MAINTAIN, not a structural incapability: the
forbidden-verb scan allows ``click``/``fill``, and
``_declarations`` does click
controls. See the module docstring of
``_schema`` for what actually
holds the read-only boundary and what the residual is.
"""

from __future__ import annotations

import pytest

from ......core.aeat_csv import is_aeat_csv
from ......tests.live_gate import requires_live_enabled
from ..declarations import Declaracion, capture_declaration, walk_declarations_register
from ..errors import SedeError
from ..schema import SedeCapture

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


async def _load_active_clave_session():
    """Return an active Cl@ve session or fail when live auth is unavailable.

    Returns:
        The :class:`AeatSession` reconstructed from the on-disk
        Cl@ve cookies.
    """
    # Local imports keep the test file lightweight when skipped.
    from ......application.auth.sessions import ensure_authenticated_aeat_session
    from ......core.auth_provider import AuthProviderKind
    from ......core.config import load_settings
    from ......core.errors.hierarchy import CadrumoError

    settings = load_settings()
    try:
        result = await ensure_authenticated_aeat_session(
            settings,
            kind=AuthProviderKind.CLAVE_MOVIL,
            operation="sede-declarations-live-test",
        )
        return result.session
    except CadrumoError as exc:
        pytest.fail(f"Cl@ve-móvil live authentication is not available after live opt-in: {exc}")


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
        pytest.fail(f"live walk failed after live opt-in: {exc}")

    # Ejercicio 2022 is the year operator's M100 fixture was captured;
    # the live account should still expose it.
    assert isinstance(declarations, tuple)
    assert all(isinstance(d, Declaracion) for d in declarations)
    assert declarations, "expected at least one Modelo 100 / 2022 declaration on the live account"
    first = declarations[0]
    assert first.modelo == "100"
    assert first.ejercicio == 2022
    assert first.expediente_id  # non-empty
    assert first.estado  # non-empty
    # The declared-shape marker only; it is not read in production and is
    # not itself a guard. The count previously claimed here ("five-layer")
    # was unverifiable, so it is not restated.
    assert first.mode == "read"


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
        pytest.fail(f"live walk failed after live opt-in: {exc}")

    assert declarations, "no Modelo 100 / 2022 declaration on this account; capture cannot run without a live row"

    try:
        capture = await capture_declaration(session, declarations[0])
    except SedeError as exc:
        pytest.fail(f"live capture failed after live opt-in: {exc}")

    assert isinstance(capture, SedeCapture)
    assert capture.pdf_bytes  # non-empty body
    assert capture.pdf_bytes.startswith(b"%PDF-")  # PDF magic header
    assert capture.pdf_sha256  # populated
    assert len(capture.pdf_sha256) == 64  # sha256 hex digest
    # The CSV passed canonical validation during extraction; verify the
    # round-trip carries that same canonical shape through SedeCapture.
    assert is_aeat_csv(capture.ref.csv)
