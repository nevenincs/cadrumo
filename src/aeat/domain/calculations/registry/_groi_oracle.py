"""AEAT GROI Spanish-ROI consult oracle.

The GROI servlet at www2.agenciatributaria.gob.es certifies whether
a given Spanish NIF is registered in the AEAT Registro de Operadores
Intracomunitarios. Live probing on 2026-05-07 confirmed the surface
is reachable under cl@ve-movil authentication; the live driver lives
at ``aeat.adapters.outbound.aeat.sede._groi_check`` and this module
wraps it as a ``LiveParityOracle``.

The oracle is the SPANISH-counterparty sibling of
``_aeat_nif_iva_oracle`` (foreign-EU VIES proxy). Both share the
``vat_id_check`` surface kind and pair with cross-references whose
surface is ``public_read_surface``; the registry's surface-kind
compatibility table at ``_live_parity._COMPATIBLE_SURFACE_PAIRS``
already declares that pair.

READ-ONLY MANDATE
-----------------

AEAT writes are PERMANENTLY FORBIDDEN. The GROI form's submit handler
is an HTTP POST to ``ConsultaOperadorSedeGroiServlet`` — but per AEAT
service contract this POST is a CONSULT (a SELECT against the ROI
registry) and modifies no AEAT-side state. The submitting NIF is not
recorded against the queried NIF, no draft is created, no filing
history entry is generated. Every observation captured during live
probing 2026-05-07 confirmed the form's only side effect is rendering
a verdict page back to the caller.

Defense-in-depth nonetheless: the registry's :class:`RemoteStateGuard`
fence intercepts every operation the oracle emits BEFORE any browser
action runs. Any guard policy attached to a GROI cross-reference MUST
declare ``forbidden_actions`` containing the canonical
:data:`AEAT_WRITE_FORBIDDEN_ACTIONS` set so that, were a future driver
refactor to mislabel an operation (or were AEAT to silently change the
endpoint to a state-modifying action), the guard rejects the
operation BEFORE it leaves the process. The unit and live tests
exercise the guard with deliberately fabricated write operations to
prove the read-only invariant by construction.
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

GROI_ORACLE_ID = "aeat-groi-spanish-roi-checker"


class _GroiModel(BaseModel):
    """Strict frozen base for GROI parity records."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class GroiObservation(_GroiModel):
    """Observed Spanish-ROI verdicts returned by an executable adapter.

    ``values`` keys are upper-cased Spanish NIFs; ``values`` values are
    lowercase verdict tokens (``valid`` / ``invalid`` / ``unknown``).
    """

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
                raise RegistryValidationError("GROI observations must not contain blank keys or values")
            cleaned[normalized_nif] = normalized_verdict
        return cleaned


class GroiDriver(Protocol):
    """Execution boundary for GROI live or replay adapters."""

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
    ) -> GroiObservation: ...


class GroiReplayDriver:
    """Deterministic local replay driver for captured GROI outputs.

    Payload shape:

        {
          "observed": {"A28015865": "valid", "B12345678": "invalid"},
          "raw_evidence_locator": "corpus/aeat_official/groi_response_samples/..."
        }
    """

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
        return (RemoteOperation(kind="local_workbook", action="parse-groi-replay"),)

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> GroiObservation:
        del expected
        document = decode_replay_json_payload(payload, surface_label="GROI replay")
        return GroiObservation(values=dict(document.observed), raw_evidence_locator=document.raw_evidence_locator)


class GroiOracle(BaseCheckerOracle[GroiObservation]):
    """AEAT-mediated Spanish-ROI registration validator.

    Wraps a ``GroiDriver`` (live or replay). When no driver is
    configured the oracle still pre-flights the planned operations
    through the remote-state guard; ``verify_payload`` then returns
    ``unverifiable`` because no observation was available for
    comparison. With a driver configured the oracle compares the
    expected verdict per NIF against the driver-emitted observation
    and returns ``match`` / ``mismatch`` accordingly.
    """

    surface_label = "GROI"

    def __init__(self, *, driver: GroiDriver | None = None) -> None:
        super().__init__(driver=driver)

    @property
    def oracle_id(self) -> str:
        return GROI_ORACLE_ID

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
            raise RegistryValidationError("GroiOracle.planned_operations requires at least one expected NIF")
        expected_values = self._expected_values(expected)
        if self._driver is not None:
            return self._driver.planned_operations(payload, expected=expected)
        operations: list[RemoteOperation] = [
            RemoteOperation(kind="http", method="GET", url=AnyUrl(Settings.external_constants().aeat.oracles.groi_check)),
            RemoteOperation(kind="browser_action", action="open-groi-form"),
        ]
        for nif in sorted(expected_values):
            operations.append(RemoteOperation(kind="browser_action", action=f"check-nif-{nif}"))
        operations.append(RemoteOperation(kind="browser_action", action="discard-session"))
        return tuple(operations)

    def _expected_values(self, expected: Mapping[str, object]) -> dict[str, str]:
        values: dict[str, str] = {}
        for nif, verdict in expected.items():
            normalized_nif = str(nif).strip().upper()
            normalized_verdict = str(verdict).strip().lower()
            if not normalized_nif or not normalized_verdict:
                raise RegistryValidationError("GROI expected values must not contain blanks")
            values[normalized_nif] = normalized_verdict
        return values

    def _observed_for(self, observation: GroiObservation, key: str) -> str | None:
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

    def _observation_locator(self, observation: GroiObservation) -> str | None:
        return observation.raw_evidence_locator


def register_default(
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
) -> None:
    """Register the GROI Spanish-ROI oracle under the requested environment."""

    catalogue.register(GroiOracle(), environment=environment)


__all__ = [
    "GROI_ORACLE_ID",
    "GroiDriver",
    "GroiObservation",
    "GroiOracle",
    "GroiReplayDriver",
    "register_default",
]
