"""Canonical flow for read-only identifier-checker oracles.

The shared checker contract owns one observation shape, driver protocol,
deterministic replay driver, declarative operation plan, and verification
orchestrator.  Concrete GROI and NIF-IVA modules declare only their AEAT
endpoint policy, catalogue identity, and surface classification.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from typing import Literal, Protocol

from pydantic import AnyUrl, BaseModel, Field, field_validator

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.identity import tax_id_identity_token
from .errors import RegistryValidationError
from .ids import OracleId
from .live_parity import (
    OracleSurfaceKind,
    ParityFieldComparison,
    ParityResult,
    ParityVerdict,
    assert_oracle_operations_allowed,
    decode_replay_json_payload,
)
from .remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
)


class CheckerObservation(BaseModel):
    """Normalized verdicts and raw-evidence locator from a checker surface."""

    model_config = STRICT_FROZEN_CONFIG

    values: dict[str, str] = Field(default_factory=dict)
    raw_evidence_locator: str | None = Field(default=None, max_length=512)

    @field_validator("values")
    @classmethod
    def _normalize_values(cls, value: dict[str, str]) -> dict[str, str]:
        return normalize_verdict_mapping(
            value,
            blank_message="Checker observations must not contain blank keys or values",
        )


class CheckerDriver(Protocol):
    """Execution boundary shared by live and replay checker adapters."""

    @property
    def mode(self) -> Literal["live", "replay"]:
        """Return whether this driver executes live operations or replays evidence."""
        ...

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Return the operations this driver would execute for the payload."""
        ...

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> CheckerObservation:
        """Return the canonical checker observation produced from the payload."""
        ...


class CheckerReplayDriver:
    """Deterministic replay driver parameterised by a surface label and action."""

    def __init__(self, *, surface_label: str, replay_action: str) -> None:
        """Initialize a replay driver with its surface label and local action."""
        self._surface_label = surface_label
        self._replay_action = replay_action

    @property
    def mode(self) -> Literal["replay"]:
        """Replay drivers decode local evidence and never touch the network."""
        return "replay"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Return the one local parse operation executed by a replay."""
        del payload, expected
        return replay_parse_operation(self._replay_action)

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> CheckerObservation:
        """Decode captured JSON evidence into the canonical observation."""
        del expected
        return decode_replay_observation(payload, surface_label=self._surface_label)


class CheckerOperationPlan(BaseModel):
    """Declarative, read-only live-operation sequence for an identifier checker."""

    model_config = STRICT_FROZEN_CONFIG

    preflight_urls: tuple[AnyUrl, ...]
    open_action: str
    check_action_prefix: str = "check-nif-"
    discard_action: str = "discard-session"

    def operations(self, expected_values: Mapping[str, str]) -> tuple[RemoteOperation, ...]:
        """Materialize sorted read-only operations for the declared identifiers."""
        operations: list[RemoteOperation] = [
            *(RemoteOperation(kind="http", method="GET", url=url) for url in self.preflight_urls),
            RemoteOperation(kind="browser_action", action=self.open_action),
        ]
        operations.extend(
            RemoteOperation(kind="browser_action", action=f"{self.check_action_prefix}{identifier}")
            for identifier in sorted(expected_values)
        )
        operations.append(RemoteOperation(kind="browser_action", action=self.discard_action))
        return tuple(operations)


class CheckerOracle:
    """Shared read-only verifier for normalized per-identifier verdicts."""

    surface_label: str
    expected_blank_message: str

    def __init__(self, *, driver: CheckerDriver | None = None) -> None:
        """Initialize the verifier with an optional live or replay driver."""
        self._driver = driver

    @property
    @abstractmethod
    def oracle_id(self) -> OracleId:
        """Return the stable catalogue identity for this checker surface."""
        ...

    @property
    @abstractmethod
    def surface_kind(self) -> OracleSurfaceKind:
        """Return the declared live-parity surface classification."""
        ...

    @abstractmethod
    def _default_operation_plan(self) -> CheckerOperationPlan:
        """Return the surface-specific, centrally materialised operation policy."""
        ...

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Plan a driver execution or materialize the declared live plan."""
        expected_values = self._expected_values(expected)
        if self._driver is not None:
            return self._driver.planned_operations(payload, expected=expected)
        return self._default_operation_plan().operations(expected_values)

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
        """Guard, execute, and compare a checker payload without hiding failures."""
        operations = self.planned_operations(payload, expected=expected)
        try:
            assert_oracle_operations_allowed(self, policy, operations)
        except RegistryValidationError as exc:
            return ParityResult(
                oracle_id=self.oracle_id,
                cross_reference_id=policy.id,
                verdict="blocked",
                narrative=f"{self.surface_label} oracle blocked by remote-state guard: {exc}",
            )
        driver = self._driver
        if driver is None:
            return ParityResult(
                oracle_id=self.oracle_id,
                cross_reference_id=policy.id,
                verdict="unverifiable",
                narrative=(
                    f"{self.surface_label} oracle has no executable driver configured. "
                    "Guard preflight passed, but no AEAT or replay observation was available "
                    "for comparison."
                ),
            )
        try:
            observation = driver.collect_observation(payload, expected=expected)
        except RegistryValidationError as exc:
            return ParityResult(
                oracle_id=self.oracle_id,
                cross_reference_id=policy.id,
                verdict="unverifiable",
                narrative=f"{self.surface_label} driver could not produce comparable observations: {exc}",
            )
        fields = tuple(
            compare_verdict_field(key, expected_value, observed=observed_verdict(observation.values, key))
            for key, expected_value in sorted(self._expected_values(expected).items())
        )
        verdict: ParityVerdict = "match" if fields and all(field.verdict == "match" for field in fields) else "mismatch"
        return ParityResult(
            oracle_id=self.oracle_id,
            cross_reference_id=policy.id,
            verdict=verdict,
            narrative=f"{self.surface_label} {driver.mode} comparison returned {verdict}.",
            fields=fields,
            raw_evidence_locator=observation.raw_evidence_locator,
        )

    def _expected_values(self, expected: Mapping[str, object]) -> dict[str, str]:
        if not expected:
            raise RegistryValidationError(
                f"{type(self).__name__}.planned_operations requires at least one expected NIF",
            )
        return normalize_expected_verdicts(expected, blank_message=self.expected_blank_message)


def normalize_verdict_mapping(values: Mapping[str, str], *, blank_message: str) -> dict[str, str]:
    """Normalize identifier/verdict mappings and reject blank entries."""
    cleaned: dict[str, str] = {}
    for identifier, verdict in values.items():
        normalized_identifier = tax_id_identity_token(identifier)
        normalized_verdict = verdict.strip().lower()
        if not normalized_identifier or not normalized_verdict:
            raise RegistryValidationError(blank_message)
        cleaned[normalized_identifier] = normalized_verdict
    return cleaned


def normalize_expected_verdicts(expected: Mapping[str, object], *, blank_message: str) -> dict[str, str]:
    """Normalize expected identifier/verdict mappings and reject blank entries."""
    values: dict[str, str] = {}
    for identifier, verdict in expected.items():
        normalized_identifier = tax_id_identity_token(str(identifier))
        normalized_verdict = str(verdict).strip().lower()
        if not normalized_identifier or not normalized_verdict:
            raise RegistryValidationError(blank_message)
        values[normalized_identifier] = normalized_verdict
    return values


def replay_parse_operation(action: str) -> tuple[RemoteOperation, ...]:
    """Return the single local replay-parse :class:`RemoteOperation` tuple."""
    return (RemoteOperation(kind="local_workbook", action=action),)


def decode_replay_observation(payload: bytes, *, surface_label: str) -> CheckerObservation:
    """Decode replay JSON into the canonical checker observation."""
    document = decode_replay_json_payload(payload, surface_label=surface_label)
    return CheckerObservation.model_validate(
        {"values": dict(document.observed), "raw_evidence_locator": document.raw_evidence_locator},
    )


def observed_verdict(values: Mapping[str, str], key: str) -> str | None:
    """Return the observed verdict for ``key`` after identifier normalization."""
    return values.get(key.upper())


def compare_verdict_field(key: str, expected: str, *, observed: str | None) -> ParityFieldComparison:
    """Compare one expected verdict against one observed verdict."""
    if observed is None:
        return ParityFieldComparison(name=key, expected=expected, observed="<missing>", verdict="mismatch")
    normalized_observed = observed.strip().lower()
    return ParityFieldComparison(
        name=key,
        expected=expected,
        observed=normalized_observed,
        verdict="match" if normalized_observed == expected else "mismatch",
    )
