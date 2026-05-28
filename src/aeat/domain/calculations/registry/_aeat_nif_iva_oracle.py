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

Concrete execution is supplied through a driver boundary. Without a driver the
oracle still exposes planned operations and guard evaluation, but returns an
``unverifiable`` parity result instead of pretending that AEAT was checked.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, Protocol

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator

from ....core.config import Settings
from ._errors import RegistryValidationError
from ._live_parity import (
    BaseCheckerOracle,
    LiveParityCatalogue,
    OracleEnvironment,
    OracleSurfaceKind,
    ParityFieldComparison,
    decode_replay_json_payload,
)
from ._remote_state_guard import RemoteOperation

ORACLE_ID = "aeat-nif-iva-checker"

_EXTERNAL = Settings.external_constants()
AEAT_NIF_IVA_VERIFICATION_URL = AnyUrl(_EXTERNAL.aeat.oracles.nif_iva_verification)
# AEAT's public sede entry point for the verification flow. The form servlet
# above redirects to a sede error page when reached cold; the live Playwright
# driver must navigate to the entry point first to acquire the session
# cookies the servlet requires. The sede gestiones page lists the form among
# the VIES management actions.
AEAT_NIF_IVA_ENTRY_URL = AnyUrl(f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.help_pages.nif_iva_landing}")


class AeatNifIvaModel(BaseModel):
    """Strict frozen base for AEAT NIF-IVA parity records."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class AeatNifIvaObservation(AeatNifIvaModel):
    """Observed NIF-IVA verdicts returned by an executable adapter."""

    values: dict[str, str] = Field(default_factory=dict)
    raw_evidence_locator: str | None = Field(default=None, max_length=512)

    @field_validator("values")
    @classmethod
    def _trimmed(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned: dict[str, str] = {}
        for nif, verdict in value.items():
            normalized_nif = nif.strip().upper()
            normalized_verdict = verdict.strip().lower()
            if not normalized_nif or not normalized_verdict:
                raise RegistryValidationError("AEAT NIF-IVA observations must not contain blank keys or values")
            cleaned[normalized_nif] = normalized_verdict
        return cleaned


class AeatNifIvaDriver(Protocol):
    """Execution boundary for AEAT NIF-IVA live or replay adapters."""

    @property
    def mode(self) -> Literal["live", "replay"]: ...

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]: ...

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> AeatNifIvaObservation: ...


class AeatNifIvaReplayDriver:
    """Deterministic local replay driver for captured AEAT NIF-IVA outputs."""

    @property
    def mode(self) -> Literal["replay"]:
        return "replay"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        del payload, expected
        return (RemoteOperation(kind="local_workbook", action="parse-aeat-nif-iva-replay"),)

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> AeatNifIvaObservation:
        del expected
        document = decode_replay_json_payload(payload, surface_label="AEAT NIF-IVA replay")
        return AeatNifIvaObservation(values=dict(document.observed), raw_evidence_locator=document.raw_evidence_locator)


class AeatNifIvaCheckerOracle(BaseCheckerOracle[AeatNifIvaObservation]):
    """Read-only AEAT-mediated EU VAT-identifier validator.

    The adapter targets the public AEAT NIF-IVA verification page at
    sede.agenciatributaria.gob.es. The page proxies the query to the
    European Commission's VIES service and renders the response inline.
    No authentication, no NIF-history, no server-side state under the
    autonomo's account.
    """

    surface_label = "AEAT NIF-IVA"

    def __init__(self, *, driver: AeatNifIvaDriver | None = None) -> None:
        super().__init__(driver=driver)

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
        if not expected:
            raise RegistryValidationError(
                "AeatNifIvaCheckerOracle.planned_operations requires at least one expected NIF"
            )
        expected_values = self._expected_values(expected)
        if self._driver is not None:
            return self._driver.planned_operations(payload, expected=expected)
        operations: list[RemoteOperation] = [
            # Navigate to the sede entry point first so the session cookies the
            # servlet requires are acquired; then GET the form servlet itself.
            RemoteOperation(kind="http", method="GET", url=AEAT_NIF_IVA_ENTRY_URL),
            RemoteOperation(kind="http", method="GET", url=AEAT_NIF_IVA_VERIFICATION_URL),
            RemoteOperation(kind="browser_action", action="open-nif-iva-form"),
        ]
        for nif in sorted(expected_values):
            operations.append(
                RemoteOperation(
                    kind="browser_action",
                    action=f"check-nif-{nif}",
                )
            )
        operations.append(RemoteOperation(kind="browser_action", action="discard-session"))
        return tuple(operations)

    def _expected_values(self, expected: Mapping[str, object]) -> dict[str, str]:
        values: dict[str, str] = {}
        for nif, verdict in expected.items():
            normalized_nif = str(nif).strip().upper()
            normalized_verdict = str(verdict).strip().lower()
            if not normalized_nif or not normalized_verdict:
                raise RegistryValidationError("AEAT NIF-IVA expected values must not contain blanks")
            values[normalized_nif] = normalized_verdict
        return values

    def _observed_for(self, observation: AeatNifIvaObservation, key: str) -> str | None:
        return observation.values.get(key.upper())

    def _compare_field(self, key: str, expected: str, *, observed: str | None) -> ParityFieldComparison:
        if observed is None:
            return ParityFieldComparison(name=key, expected=expected, observed="<missing>", verdict="mismatch")
        normalized_observed = observed.strip().lower()
        return ParityFieldComparison(
            name=key,
            expected=expected,
            observed=normalized_observed,
            verdict="match" if normalized_observed == expected else "mismatch",
        )

    def _observation_locator(self, observation: AeatNifIvaObservation) -> str | None:
        return observation.raw_evidence_locator


def register_default(
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
) -> None:
    """Register the AEAT NIF-IVA adapter under the requested environment."""

    catalogue.register(AeatNifIvaCheckerOracle(), environment=environment)


__all__ = [
    "AEAT_NIF_IVA_ENTRY_URL",
    "AEAT_NIF_IVA_VERIFICATION_URL",
    "ORACLE_ID",
    "AeatNifIvaCheckerOracle",
    "AeatNifIvaDriver",
    "AeatNifIvaObservation",
    "AeatNifIvaReplayDriver",
    "register_default",
]
