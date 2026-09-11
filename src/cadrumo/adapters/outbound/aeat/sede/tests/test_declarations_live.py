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
from ..declarations import open_declarations_register, walk_declarations_register
from ..declarations_remote import extract_csv_from_url
from ..declarations_schema import Declaracion
from ..errors import SedeError
from ..schema import FiledDeclaracionArtefact, FiledDeclaracionObservation

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
async def test_register_session_capture_observation_returns_pdf_bytes() -> None:
    """The normalized register capture path lands a valid PDF body.

    Drives the same Modelo 100 / 2022 surface as the walker test and captures
    the first row through the production session owner. The sink observes the
    exact bytes handed to persistence without adding a second fetch path.
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

    bodies: dict[str, bytes] = {}

    def retain_body(
        _observation_key: object,
        artefact: FiledDeclaracionArtefact,
        body: bytes,
    ) -> FiledDeclaracionArtefact:
        bodies[artefact.kind] = body
        return artefact

    try:
        async with open_declarations_register(session) as register:
            observation = await register.capture_observation(declarations[0], artefact_sink=retain_body)
    except SedeError as exc:
        pytest.fail(f"live capture failed after live opt-in: {exc}")

    assert isinstance(observation, FiledDeclaracionObservation)
    justificante = next(artefact for artefact in observation.artefacts if artefact.kind == "justificante_pdf")
    assert bodies["justificante_pdf"].startswith(b"%PDF-")
    assert justificante.byte_count == len(bodies["justificante_pdf"])
    assert len(justificante.sha256) == 64
    assert is_aeat_csv(extract_csv_from_url(str(justificante.source_url)))
