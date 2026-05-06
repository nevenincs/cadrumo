"""Renta WEB Open parity oracle for Modelo 100.

Renta WEB Open is the AEAT-classified open simulator surface declared by
the ``modelo-100-renta-web-open`` cross-reference in
``registry/aeat/modelos/100.toml`` (``surface = "open_simulator"``,
``synthetic_data_allowed = true``, ``requires_authentication = false``,
``forbidden_actions`` covering every authenticated-Renta-WEB / fiscal-data
/ borrador / declaration / signing / presentation / payment / amendment /
cancellation / document-submission / declaration-submission action).

This adapter satisfies the :class:`LiveParityOracle` Protocol declared by
the live parity oracle backend (see ``_live_parity.py``). It declares its
planned operations up-front (one HTTP GET for the landing page, then one
browser action per expected casilla scrape) so the remote-state guard
rejects any policy violation before any side-effecting code runs.

The Playwright-driven execution layer is intentionally not implemented in
this module; ``verify_payload`` raises ``NotImplementedError`` until the
follow-up slice lands the headless-Chromium driver. Adapter registration
into the global :class:`LiveParityCatalogue` is gated on that
implementation arriving so consumers cannot accidentally bind to a
half-built oracle.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import AnyUrl

from ._errors import RegistryValidationError
from ._live_parity import OracleSurfaceKind, ParityResult
from ._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy

RENTA_WEB_OPEN_LANDING_URL = AnyUrl(
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/"
    "renta-ayuda-tecnica/renta-web-open.html"
)


class RentaWebOpenOracle:
    """Open-simulator oracle for Modelo 100 Renta WEB Open."""

    @property
    def oracle_id(self) -> str:
        return "modelo-100-renta-web-open"

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        return "open_simulator"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        if not expected:
            raise RegistryValidationError(
                "RentaWebOpenOracle.planned_operations requires at least one expected casilla"
            )
        operations: list[RemoteOperation] = [
            RemoteOperation(kind="http", method="GET", url=RENTA_WEB_OPEN_LANDING_URL),
            RemoteOperation(kind="browser_action", action="navigate-to-simulator"),
            RemoteOperation(kind="browser_action", action="fill-synthetic-profile"),
        ]
        for casilla_id in sorted(expected):
            operations.append(
                RemoteOperation(
                    kind="browser_action",
                    action=f"scrape-casilla-{casilla_id}",
                )
            )
        operations.append(RemoteOperation(kind="browser_action", action="discard-session"))
        return tuple(operations)

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
        raise NotImplementedError(
            "Renta WEB Open Playwright driver is not implemented yet. The contract "
            "in this adapter is the spec target. Implement the headless drive that "
            "navigates from RENTA_WEB_OPEN_LANDING_URL, fills the synthetic profile "
            "form, scrapes the expected casilla outputs, and returns a ParityResult. "
            "Honour the modelo-100-renta-web-open cross-reference policy at every "
            "step and never invoke any unlisted operation."
        )


__all__ = ["RENTA_WEB_OPEN_LANDING_URL", "RentaWebOpenOracle"]
