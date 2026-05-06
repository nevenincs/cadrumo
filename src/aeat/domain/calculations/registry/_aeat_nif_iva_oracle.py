"""AEAT NIF-IVA other-EU-countries verification oracle.

AEAT publishes a public verification servlet under the
agenciatributaria.gob.es domain that confirms the validity of an EU VAT
identifier issued by another member state. The form accepts the country
code + VAT number, relays the query to the European Commission's VIES
service, and renders the response. The form is anonymous (no clave-móvil
session, no NIF-history written for the calling autonomo) and creates no
AEAT-side state under the autonomo's account.

This adapter targets that AEAT-hosted form (``www1.agenciatributaria.gob.es``)
so it stays inside the existing remote-state-guard host-pinning allow-list
(matched by the ``agenciatributaria.gob.es`` suffix) and does not require
a host-list expansion. Same verdict authority as direct EU VIES because
AEAT delegates to VIES under the hood.

The Playwright-driven execution layer is intentionally not implemented in
this slice; ``verify_payload`` raises ``NotImplementedError`` after the
guard pre-flight succeeds, mirroring the precedent set by
``_renta_web_open_oracle``. Adapter registration into the global
catalogue is gated on the live driver arriving.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import AnyUrl

from ._errors import RegistryValidationError
from ._live_parity import (
    LiveParityCatalogue,
    OracleEnvironment,
    OracleSurfaceKind,
    ParityResult,
    assert_oracle_operations_allowed,
)
from ._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy

ORACLE_ID = "aeat-nif-iva-checker"

AEAT_NIF_IVA_VERIFICATION_URL = AnyUrl("https://www1.agenciatributaria.gob.es/wlpl/IXVI-JDIT/ConsultaIntracomunitarios")
# AEAT's public sede entry point for the verification flow. The form servlet
# above redirects to a sede error page when reached cold; the live Playwright
# driver must navigate to the entry point first to acquire the session
# cookies the servlet requires. The sede gestiones page lists the form among
# the VIES management actions.
AEAT_NIF_IVA_ENTRY_URL = AnyUrl(
    "https://sede.agenciatributaria.gob.es/Sede/iva/iva-operaciones-comercio-exterior/"
    "identificacion-realizar-operaciones-otros-empresarios-ue/vies.html"
)


class AeatNifIvaCheckerOracle:
    """Read-only AEAT-mediated EU VAT-identifier validator.

    The adapter targets the public AEAT NIF-IVA verification page at
    sede.agenciatributaria.gob.es. The page proxies the query to the
    European Commission's VIES service and renders the response inline.
    No authentication, no NIF-history, no server-side state under the
    autonomo's account.
    """

    @property
    def oracle_id(self) -> str:
        return ORACLE_ID

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        return "vat_id_check"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        del payload
        if not expected:
            raise RegistryValidationError(
                "AeatNifIvaCheckerOracle.planned_operations requires at least one expected NIF"
            )
        operations: list[RemoteOperation] = [
            # Navigate to the sede entry point first so the session cookies the
            # servlet requires are acquired; then GET the form servlet itself.
            RemoteOperation(kind="http", method="GET", url=AEAT_NIF_IVA_ENTRY_URL),
            RemoteOperation(kind="http", method="GET", url=AEAT_NIF_IVA_VERIFICATION_URL),
            RemoteOperation(kind="browser_action", action="open-nif-iva-form"),
        ]
        for nif in sorted(self._iter_nifs(expected)):
            operations.append(
                RemoteOperation(
                    kind="browser_action",
                    action=f"check-nif-{nif}",
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
        del payload
        operations = self.planned_operations(b"", expected=expected)
        assert_oracle_operations_allowed(self, policy, operations)
        raise NotImplementedError(
            "AEAT NIF-IVA Playwright driver is not implemented yet. The contract "
            "in this adapter is the spec target. Implement the headless drive that "
            "navigates to AEAT_NIF_IVA_VERIFICATION_URL, fills the country-code + "
            "VAT-number form per declared NIF, scrapes the rendered validity, and "
            "returns a ParityResult. Honour the cross-reference policy at every "
            "step and never invoke any unlisted operation."
        )

    @staticmethod
    def _iter_nifs(expected: Mapping[str, object]) -> tuple[str, ...]:
        return tuple(str(key) for key in expected)


def register_default(
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = "production",
) -> None:
    """Register the AEAT NIF-IVA adapter under the requested environment.

    Adapter registration is intentionally gated on the live Playwright
    driver landing. Until then this helper exists for the test surface
    and follow-up wiring; production callers wait until the driver
    follow-up commits.
    """

    catalogue.register(AeatNifIvaCheckerOracle(), environment=environment)


__all__ = [
    "AEAT_NIF_IVA_ENTRY_URL",
    "AEAT_NIF_IVA_VERIFICATION_URL",
    "ORACLE_ID",
    "AeatNifIvaCheckerOracle",
    "register_default",
]
