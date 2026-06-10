"""AEAT NIF-IVA other-EU-countries verification oracle.

AEAT publishes a public verification servlet under the
agenciatributaria.gob.es domain that confirms the validity of an EU IVA
identifier issued by another member state. The form accepts the country
code + IVA number, relays the query to the European Commission's VIES
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
from typing import Literal, Protocol, override

from pydantic import AnyUrl, Field, field_validator

from ....core.config import Settings
from ._checker_oracle_flow import (
    _CheckerBaseModel,
    compare_verdict_field,
    decode_replay_observation,
    normalize_expected_verdicts,
    normalize_verdict_mapping,
    observed_verdict,
    replay_parse_operation,
)
from ._errors import RegistryValidationError
from ._live_parity import (
    BaseCheckerOracle,
    LiveParityCatalogue,
    OracleEnvironment,
    OracleSurfaceKind,
    ParityFieldComparison,
)
from ._remote_state_guard import RemoteOperation

ORACLE_ID = "aeat-nif-iva-checker"


class AeatNifIvaObservation(_CheckerBaseModel):
    """Observed NIF-IVA verdicts returned by an executable adapter."""

    values: dict[str, str] = Field(default_factory=dict)
    raw_evidence_locator: str | None = Field(default=None, max_length=512)

    @field_validator("values")
    @classmethod
    def _trimmed(cls, value: dict[str, str]) -> dict[str, str]:
        return normalize_verdict_mapping(
            value,
            blank_message="AEAT NIF-IVA observations must not contain blank keys or values",
        )


class AeatNifIvaDriver(Protocol):
    """Execution boundary for AEAT NIF-IVA live or replay adapters."""

    @property
    def mode(self) -> Literal["live", "replay"]:
        """Discriminate whether this driver drives a live AEAT query or a replay.

        Returns:
            ``"live"`` for a driver that hits the AEAT-hosted verification
            form over the network, or ``"replay"`` for one that decodes a
            previously captured response from disk. Callers use this to gate
            network-touching behaviour without inspecting the concrete type.
        """
        ...

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Describe the remote steps this driver would take, without running them.

        Returns the ordered :class:`RemoteOperation` plan the driver intends to run
        for the given query, so the oracle can surface and guard the plan
        before any network or filesystem access. A :class:`RemoteOperation` is one
        recorded step in that plan (for example, a network request or a local
        file parse).

        Args:
            payload: Raw bytes the driver consumes. For a replay driver this is
                a captured response; a live driver ignores it or treats it as
                request context.
            expected: Mapping from an EU IVA identifier (a VAT number issued by
                an EU member state) to the verdict expected for it. A verdict
                is the validity outcome, such as valid or invalid. The mapping
                is keyed by the identifier string.

        Returns:
            The ordered tuple of planned :class:`RemoteOperation` records.
        """
        ...

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> AeatNifIvaObservation:
        """Execute the driver and return the observed AEAT NIF-IVA verdicts.

        A NIF-IVA is the Spanish tax identifier for VAT purposes; an observed
        verdict is the validity outcome (such as valid or invalid) the driver
        actually saw for each identifier.

        Args:
            payload: Raw bytes the driver consumes. For a replay driver this is
                a captured response; a live driver treats it as transport input.
            expected: Mapping from an EU IVA identifier (a VAT number issued by
                an EU member state) to its expected verdict, supplied so a live
                driver knows which identifiers to query.

        Returns:
            An :class:`AeatNifIvaObservation` carrying the per-identifier verdicts
            the adapter actually saw, plus a locator pointing to the raw
            evidence (the stored response the verdicts were read from).
        """
        ...


class AeatNifIvaReplayDriver:
    """Deterministic local replay driver for captured AEAT NIF-IVA outputs."""

    @property
    def mode(self) -> Literal["replay"]:
        """Identify this driver as a replay driver.

        Returns:
            The literal ``"replay"``. This driver never touches the network;
            it decodes a captured AEAT NIF-IVA response from a local payload,
            so its mode is fixed.
        """
        return "replay"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Report the single local-parse step a replay performs.

        A replay does no remote work, so the plan is one :class:`RemoteOperation`
        of kind ``local_workbook`` that parses the captured payload. A
        :class:`RemoteOperation`` is one recorded step in a driver plan. Both
        arguments are accepted to match the shared ``AeatNifIvaDriver``
        interface but are unused here.

        Args:
            payload: The captured response bytes (ignored for planning).
            expected: Expected per-identifier verdicts, where a verdict is the
                validity outcome such as valid or invalid (ignored for
                planning).

        Returns:
            A one-element tuple holding the local-parse :class:`RemoteOperation`.
        """
        del payload, expected
        return replay_parse_operation("parse-aeat-nif-iva-replay")

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> AeatNifIvaObservation:
        """Decode the captured payload into observed NIF-IVA verdicts.

        Parses ``payload`` as a replay JSON document and lifts its observed
        verdict map and raw-evidence locator into an :class:`AeatNifIvaObservation`.
        A verdict is the validity outcome (such as valid or invalid) recorded
        for each identifier; the raw-evidence locator points back to the
        stored response.

        Args:
            payload: The captured AEAT NIF-IVA response, as replay JSON bytes.
            expected: Accepted to match the shared driver interface but unused;
                a replay reports only what was recorded and never re-queries by
                expectation.

        Returns:
            An :class:`AeatNifIvaObservation` built from the decoded document.
        """
        del expected
        return decode_replay_observation(
            payload,
            surface_label="AEAT NIF-IVA replay",
            observation_type=AeatNifIvaObservation,
        )


class AeatNifIvaCheckerOracle(BaseCheckerOracle[AeatNifIvaObservation]):
    """Read-only AEAT-mediated EU IVA-identifier validator.

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
    @override
    def oracle_id(self) -> str:
        """Return the stable catalogue identifier for this oracle.

        Returns:
            The constant ``"aeat-nif-iva-checker"``. The live-parity catalogue
            keys oracles by this id, so it must stay stable across releases.
        """
        return ORACLE_ID

    @property
    @override
    def surface_kind(self) -> OracleSurfaceKind:
        """Classify the kind of AEAT surface this oracle verifies.

        Returns:
            The ``OracleSurfaceKind`` value ``"iva_id_check"``. It marks this
            oracle as a validator of EU IVA identifiers (a VAT number issued by
            another EU member state, which AEAT relays to the European
            Commission's VIES service for checking) rather than a modelo filing
            surface. A modelo is an AEAT tax form; this oracle checks
            identifiers, not the casillas (the numbered boxes) on such a form.
        """
        return "iva_id_check"

    @override
    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Build the ordered remote plan for verifying the expected identifiers.

        When a driver is bound, the plan is delegated to that driver.
        Otherwise the oracle emits its own default browser plan: GET the AEAT
        sede (the AEAT electronic-office website) landing page to acquire the
        session cookies the form servlet needs, GET the form servlet, open the
        form, issue one check per expected identifier in sorted order, then
        discard the anonymous (unauthenticated) session. Endpoint hosts are
        read from ``Settings.external_constants()`` so they stay inside the
        remote-state-guard host allowlist (the set of hosts the guard permits).

        Args:
            payload: Raw bytes forwarded to a bound driver; unused by the
                default plan.
            expected: Mapping from an EU IVA identifier (a VAT number issued by
                an EU member state) to its expected verdict, where a verdict is
                the validity outcome such as valid or invalid. Must be
                non-empty.

        Returns:
            The ordered tuple of planned :class:`RemoteOperation` records, where each
            :class:`RemoteOperation` is one recorded step in the plan.

        Raises:
            RegistryValidationError: If ``expected`` is empty, or if any
                identifier or verdict normalizes to blank.
        """
        if not expected:
            raise RegistryValidationError(
                "AeatNifIvaCheckerOracle.planned_operations requires at least one expected NIF"
            )
        expected_values = self._expected_values(expected)
        if self._driver is not None:
            return self._driver.planned_operations(payload, expected=expected)
        _ext = Settings.external_constants()
        operations: list[RemoteOperation] = [
            # Navigate to the sede entry point first so the session cookies the
            # servlet requires are acquired; then GET the form servlet itself.
            RemoteOperation(
                kind="http", method="GET", url=AnyUrl(f"{_ext.aeat.domains.sede}{_ext.aeat.help_pages.nif_iva_landing}")
            ),
            RemoteOperation(kind="http", method="GET", url=AnyUrl(_ext.aeat.oracles.nif_iva_verification)),
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

    @override
    def _expected_values(self, expected: Mapping[str, object]) -> dict[str, str]:
        return normalize_expected_verdicts(
            expected,
            blank_message="AEAT NIF-IVA expected values must not contain blanks",
        )

    @override
    def _observed_for(self, observation: AeatNifIvaObservation, key: str) -> str | None:
        return observed_verdict(observation.values, key)

    @override
    def _compare_field(self, key: str, expected: str, *, observed: str | None) -> ParityFieldComparison:
        return compare_verdict_field(key, expected, observed=observed)

    @override
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
    "ORACLE_ID",
    "AeatNifIvaCheckerOracle",
    "AeatNifIvaDriver",
    "AeatNifIvaObservation",
    "AeatNifIvaReplayDriver",
    "register_default",
]
