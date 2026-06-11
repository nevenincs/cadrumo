"""AEAT GROI Spanish-ROI consult oracle.

The GROI servlet at www2.agenciatributaria.gob.es certifies whether
a given Spanish NIF is registered in the AEAT Registro de Operadores
Intracomunitarios. Live probing on 2026-05-07 confirmed the surface
is reachable under cl@ve-movil authentication; the live driver lives
at ``aeat.adapters.outbound.aeat.sede._groi_check`` and this module
wraps it as a ``LiveParityOracle``.

The oracle is the SPANISH-counterparty sibling of
``_aeat_nif_iva_oracle`` (foreign-EU VIES proxy). Both share the
``iva_id_check`` surface kind and pair with cross-references whose
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

Defense-in-depth nonetheless: the registry's ``RemoteStateGuard``
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

GROI_ORACLE_ID = "aeat-groi-spanish-roi-checker"


class GroiObservation(_CheckerBaseModel):
    """Observed Spanish-ROI verdicts returned by an executable adapter.

    ``values`` keys are upper-cased Spanish NIFs; ``values`` values are
    lowercase verdict tokens (``valid`` / ``invalid`` / ``unknown``).
    """

    values: dict[str, str] = Field(default_factory=dict)
    raw_evidence_locator: str | None = Field(default=None, max_length=512)

    @field_validator("values")
    @classmethod
    def _trimmed(cls, value: dict[str, str]) -> dict[str, str]:
        return normalize_verdict_mapping(
            value,
            blank_message="GROI observations must not contain blank keys or values",
        )


class GroiDriver(Protocol):
    """Execution boundary for GROI live or replay adapters."""

    @property
    def mode(self) -> Literal["live", "replay"]:
        """Discriminate which execution surface this driver speaks to.

        Returns either ``"live"`` (a driver that drives the real AEAT GROI
        servlet through an authenticated browser session) or ``"replay"`` (a
        driver that decodes a previously captured response from local corpus
        bytes). ``GroiOracle`` reads this to label evidence provenance and to
        decide whether a run touched the network.

        Returns:
            The literal ``"live"`` or ``"replay"``.
        """
        ...

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Declare the remote operations this driver intends to perform.

        The operations are pre-flighted through the registry's remote-state
        guard before any of them runs, so the read-only invariant can be
        enforced by construction. The driver returns the sequence it would
        execute for the given probe rather than executing it.

        Args:
            payload: Raw adapter input bytes (a live request envelope or a
                captured replay document, depending on the driver mode).
            expected: Mapping of Spanish NIF (the per-taxpayer fiscal
                identifier) to its expected ROI-registration verdict; ROI is
                the AEAT Registro de Operadores Intracomunitarios, the
                register of operators cleared for intra-EU trade.

        Returns:
            The ordered :class:`RemoteOperation` tuple this driver would emit.
        """
        ...

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> GroiObservation:
        """Execute the GROI probe and return the observed verdicts.

        Args:
            payload: Raw adapter input bytes for this driver mode.
            expected: Mapping of Spanish NIF to its expected ROI-registration
                verdict, used by live drivers to scope which identifiers to
                query.

        Returns:
            A :class:`GroiObservation` whose ``values`` map upper-cased NIFs to
            lowercase verdict tokens (``valid`` / ``invalid`` / ``unknown``).
        """
        ...


class GroiReplayDriver:
    """Deterministic local replay driver for captured GROI outputs.

    Payload shape::

        {
          "observed": {"A28015865": "valid", "B12345678": "invalid"},
          "raw_evidence_locator": "corpus/aeat_official/groi_response_samples/..."
        }
    """

    @property
    def mode(self) -> Literal["replay"]:
        """Identify this driver as a deterministic local replay.

        Always ``"replay"``: this driver decodes a captured GROI response from
        local corpus bytes and never touches the network, making it the
        offline counterpart used by the parity test suite.

        Returns:
            The literal ``"replay"``.
        """
        return "replay"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Declare the single local-parse operation a replay performs.

        Both arguments are ignored: a replay reads a fixed captured document
        and performs no network or browser action, so it returns exactly one
        :class:`RemoteOperation` of kind ``local_workbook`` with action
        ``parse-groi-replay``. The remote-state guard still pre-flights this
        list for uniformity with the live path.

        Args:
            payload: Captured replay bytes; ignored.
            expected: Expected NIF-to-verdict mapping; ignored.

        Returns:
            A one-element tuple naming the local replay-parse :class:`RemoteOperation`.
        """
        del payload, expected
        return replay_parse_operation("parse-groi-replay")

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> GroiObservation:
        """Decode the captured replay payload into observed verdicts.

        The ``expected`` mapping is ignored; the observation is read straight
        from the captured document. The payload is a JSON envelope with an
        ``observed`` object (NIF to verdict) and an optional
        ``raw_evidence_locator`` pointing at the corpus sample on disk.

        Args:
            payload: JSON replay bytes; decoded via the shared replay decoder.
            expected: Expected NIF-to-verdict mapping; ignored.

        Returns:
            A :class:`GroiObservation` carrying the captured verdicts and evidence
            locator.

        Raises:
            RegistryValidationError: If the payload is malformed or carries
                blank NIF keys or verdict values.
        """
        del expected
        return decode_replay_observation(
            payload,
            surface_label="GROI replay",
            observation_type=GroiObservation,
        )


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
    @override
    def oracle_id(self) -> str:
        """Return the stable catalogue identifier for this oracle.

        The value is the module-level ``GROI_ORACLE_ID`` constant
        (``aeat-groi-spanish-roi-checker``), used as the key under which the
        oracle registers in the live-parity catalogue.

        Returns:
            The catalogue registration key.
        """
        return GROI_ORACLE_ID

    @property
    @override
    def surface_kind(self) -> OracleSurfaceKind:
        """Return the surface-kind tag that gates cross-reference pairing.

        Always ``"iva_id_check"``: the same tag carried by the VIES sibling
        oracle. VIES (VAT Information Exchange System) is the EU service that
        checks foreign-EU VAT identifiers, the GROI equivalent for the rest of
        the EU. Sharing the tag lets the registry's surface-kind
        compatibility table pair GROI checks against ``public_read_surface``
        cross-references (other read-only public lookups).

        Returns:
            The ``OracleSurfaceKind`` literal ``"iva_id_check"``.
        """
        return "iva_id_check"

    @override
    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Declare the remote operations a GROI verification would perform.

        The operations are pre-flighted through the remote-state guard before
        any browser action runs, enforcing the read-only AEAT mandate by
        construction. With a driver configured the call delegates to that
        driver. With no driver configured the oracle synthesises the canonical
        live sequence directly: a GET against the GROI servlet URL pulled from
        central config, a browser action to open the form, one
        ``check-nif-<nif>`` action per expected NIF in sorted order, and a
        final ``discard-session`` action.

        Args:
            payload: Raw adapter input bytes, forwarded to a configured driver.
            expected: Non-empty mapping of Spanish NIF to its expected
                ROI-registration verdict; NIF is the per-taxpayer fiscal
                identifier and ROI is the AEAT register of intra-EU operators.

        Returns:
            The ordered :class:`RemoteOperation` tuple for this verification.

        Raises:
            RegistryValidationError: If ``expected`` is empty, or if any NIF
                key or verdict value is blank.
        """
        if not expected:
            raise RegistryValidationError("GroiOracle.planned_operations requires at least one expected NIF")
        expected_values = self._expected_values(expected)
        if self._driver is not None:
            return self._driver.planned_operations(payload, expected=expected)
        operations: list[RemoteOperation] = [
            RemoteOperation(
                kind="http", method="GET", url=AnyUrl(Settings.external_constants().aeat.oracles.groi_check),
            ),
            RemoteOperation(kind="browser_action", action="open-groi-form"),
        ]
        for nif in sorted(expected_values):
            operations.append(RemoteOperation(kind="browser_action", action=f"check-nif-{nif}"))
        operations.append(RemoteOperation(kind="browser_action", action="discard-session"))
        return tuple(operations)

    @override
    def _expected_values(self, expected: Mapping[str, object]) -> dict[str, str]:
        return normalize_expected_verdicts(
            expected,
            blank_message="GROI expected values must not contain blanks",
        )

    @override
    def _observed_for(self, observation: GroiObservation, key: str) -> str | None:
        return observed_verdict(observation.values, key)

    @override
    def _compare_field(self, key: str, expected: str, *, observed: str | None) -> ParityFieldComparison:
        return compare_verdict_field(key, expected, observed=observed)

    @override
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
