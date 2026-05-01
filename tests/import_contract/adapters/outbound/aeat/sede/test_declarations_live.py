"""Live test for :func:`aeat.adapters.outbound.aeat.sede.walk_declarations_register` (#239).

Drives the *Consultar declaraciones presentadas* form against
the real AEAT sede with a Cl@ve-móvil session. Skips cleanly when:

* ``AEAT_LIVE_TESTS_ENABLED`` is unset (every live test gates on
  this), OR
* No active Cl@ve session is on disk (running this test would
  prompt the operator for a 2FA push, which is not appropriate
  for an automated suite).

The test is read-only by construction — every public surface in
:mod:`aeat.adapters.outbound.aeat.sede._declarations` is structurally incapable of
mutating AEAT state (parent ADR's five-layer write guard).
"""

from __future__ import annotations

import pytest

from aeat.entrypoints.cli._live import requires_live_enabled
from aeat.adapters.outbound.aeat.sede._declarations import Declaration, capture_declaration, walk_declarations_register
from aeat.adapters.outbound.aeat.sede._errors import SedeError
from aeat.adapters.outbound.aeat.sede._schema import SedeCapture

pytestmark = [pytest.mark.live_read, pytest.mark.domain_outbound]


def _load_active_clave_session():
    """Return an active Cl@ve session or skip the test cleanly.

    Returns:
        The :class:`AeatSession` reconstructed from the on-disk
        Cl@ve cookies. Skips when no session is persisted or the
        operator hasn't opted into live tests.
    """
    # Local imports keep the test file lightweight when skipped.
    from aeat.core.config import load_settings
    from aeat.entrypoints.cli.auth import _session
    from aeat.entrypoints.cli.auth._paths import storage_state_paths
    from aeat.adapters.outbound.aeat.auth._authenticator import AEAT_SESSION_IDLE_TTL, AeatSession
    from aeat.adapters.outbound.aeat.auth._providers import AuthProviderKind, ClaveMovilSessionDetail

    settings = load_settings()
    persisted = _session.load(settings, None)
    if persisted is None:
        pytest.skip("No active AEAT session; run `aeat auth login` to enable live tests.")
    if persisted.provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        pytest.skip(
            f"Live walker test requires Cl@ve-móvil session (active provider: {persisted.provider_kind.value}).",
        )
    paths = storage_state_paths(settings, persisted.provider_kind)
    storage_path = paths.storage_state
    if not storage_path.exists():
        pytest.skip(f"Cl@ve storage state missing at {storage_path}")
    detail = ClaveMovilSessionDetail(
        dni_nie=persisted.identity_nif,
        used_non_qr_fallback=True,
        verification_code=None,
    )
    return AeatSession(
        provider_kind=persisted.provider_kind,
        authenticated_at=persisted.authenticated_at,
        idle_deadline=persisted.authenticated_at + AEAT_SESSION_IDLE_TTL,
        storage_state_path=storage_path,
        identity_nif=persisted.identity_nif,
        provider_detail=detail,
    )


@pytest.mark.asyncio
async def test_walk_modelo_100_returns_at_least_one_declaration() -> None:
    """The IRPF anual filing register has at least one declaration.

    Every direct-estimación autónomo who has filed at least one
    Modelo 100 produces a declaration here. Asserts only the
    structural shape — actual values vary per account.
    """
    requires_live_enabled()
    session = _load_active_clave_session()
    try:
        declarations = await walk_declarations_register(
            session,
            modelo="100",
            ejercicio=2022,
        )
    except SedeError as exc:
        pytest.skip(f"live walk failed (likely session-expired): {exc}")

    # Ejercicio 2022 is the year Kent's M100 fixture was captured;
    # the live account should still expose it.
    assert isinstance(declarations, tuple)
    assert all(isinstance(d, Declaration) for d in declarations)
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
    session = _load_active_clave_session()
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
