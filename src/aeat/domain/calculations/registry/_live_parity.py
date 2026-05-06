"""Modelo-agnostic live parity oracle backend.

This module sits one level above :mod:`_remote_state_guard` and ties the
existing fail-closed remote-state policy to a uniform contract for *read-only*
verification of registry-rendered payloads against AEAT live surfaces.

Two-fold hardening underpins the design:

1. Local hardening — already in place via the registry's static
   conformance tests (record-design positions, casilla widths, byte
   roundtrips, formula closure).
2. Live conformance — drive a synthetic, registry-rendered payload
   through an AEAT-published verification surface that **must not** modify
   remote state (open simulators, file validators like TGVI online, VIES
   VAT-ID checkers, pre-filing validators, AEAT integration test services).
   Every planned operation is pre-flighted against the cross-reference's
   :class:`RemoteStateGuardPolicy` before any HTTP or browser action runs;
   any policy-violating step is rejected before it leaves the process.

Each modelo's registry TOML declares which oracle a cross-reference is
bound to via ``oracle_id``; this module owns the runtime contract and the
shared catalogue. Concrete oracle adapters live in sibling modules so the
abstraction stays free of network code.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._errors import RegistryValidationError
from ._remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
    evaluate_remote_operation,
)

if TYPE_CHECKING:
    from ._schema import ModeloDefinition

__all__ = [
    "LiveParityCatalogue",
    "LiveParityOracle",
    "OracleEnvironment",
    "OracleSurfaceKind",
    "ParityFieldComparison",
    "ParityResult",
    "ParityVerdict",
    "audit_oracle_bindings",
    "audit_registry_oracle_bindings",
    "build_planned_operations",
    "pre_flight_oracle_operations",
    "resolve_cross_reference_oracle",
]

ParityVerdict = Literal["match", "mismatch", "unverifiable", "blocked"]
OracleSurfaceKind = Literal[
    "file_validator",
    "open_simulator",
    "vat_id_check",
    "pre_filing_validator",
    "integration_test_service",
]
OracleEnvironment = Literal["production", "test_environment", "both"]

# Allow-list of compatible (cross-reference surface, oracle surface_kind)
# pairs. Bindings whose pair is not listed here are flagged by the boot-time
# audit. ``static_official_documentation`` is intentionally absent: static-doc
# surfaces have no verifiable response and cannot be the target of any oracle.
# Adding a new oracle surface_kind or a new cross-reference surface in a
# follow-up must extend this set in the same commit.
_COMPATIBLE_SURFACE_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("open_simulator", "open_simulator"),
        ("integration_test_service", "integration_test_service"),
        ("public_read_surface", "vat_id_check"),
        ("public_read_surface", "file_validator"),
        ("authenticated_read_surface", "pre_filing_validator"),
    }
)


class _ParityModel(BaseModel):
    """Strict frozen base for parity records."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class ParityFieldComparison(_ParityModel):
    """One field-level comparison between an expected and observed value."""

    name: str = Field(min_length=1, max_length=160)
    expected: str
    observed: str
    verdict: Literal["match", "mismatch", "unverifiable"]


class ParityResult(_ParityModel):
    """Outcome of running a synthetic payload through a live parity oracle.

    The oracle layer never returns "filing succeeded" or any other side-effect
    confirmation; the only signal callers consume is whether AEAT's response
    confirms the registry-rendered payload conforms (``match``), diverges
    (``mismatch``), is structurally unanswerable by the surface
    (``unverifiable``), or was refused before it left the process by the
    remote-state guard (``blocked``).
    """

    oracle_id: str = Field(min_length=1, max_length=128)
    cross_reference_id: str = Field(min_length=1, max_length=128)
    verdict: ParityVerdict
    narrative: str = Field(min_length=1, max_length=2048)
    fields: tuple[ParityFieldComparison, ...] = ()
    raw_evidence_locator: str | None = Field(default=None, max_length=512)

    @field_validator("fields")
    @classmethod
    def _fields_unique(cls, value: tuple[ParityFieldComparison, ...]) -> tuple[ParityFieldComparison, ...]:
        seen: set[str] = set()
        for field in value:
            if field.name in seen:
                raise ValueError(f"duplicate parity field {field.name!r}")
            seen.add(field.name)
        return value


@runtime_checkable
class LiveParityOracle(Protocol):
    """Read-only AEAT verification surface contract.

    Every concrete oracle must satisfy two invariants:

    - ``planned_operations`` enumerates every HTTP request, browser action,
      or local computation it will perform, in the order they will run.
      The oracle must not perform any unlisted operation. Callers iterate the
      planned list through :func:`assert_remote_operation_allowed` *before*
      any side-effecting code is reached.
    - ``verify_payload`` returns a :class:`ParityResult`; it never raises on
      AEAT-side mismatch (mismatch is data, not an exception) and never
      returns ``"match"`` if any planned operation was skipped or rewritten.
    """

    @property
    def oracle_id(self) -> str: ...

    @property
    def surface_kind(self) -> OracleSurfaceKind: ...

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]: ...

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult: ...


class LiveParityCatalogue:
    """Registry of live parity oracles keyed by oracle_id.

    Every modelo that wants live conformance verification declares an
    ``oracle_id`` in its registry cross-reference; the runtime looks the
    oracle up here. Catalogue registration is process-wide so adapters
    can self-register at import time.

    Every registration declares an explicit environment classification so
    that adapters targeting AEAT pre-production / test-NIF surfaces cannot
    leak into production code paths. The :func:`lookup` call requires an
    environment context; oracles registered as ``"production"`` only are
    invisible to test-environment lookups and vice versa. ``"both"`` is
    reserved for adapters whose surface is provably safe under either
    classification (e.g., pure read-only public services that never touch
    AEAT NIF state under any environment).
    """

    def __init__(self) -> None:
        self._oracles: dict[str, LiveParityOracle] = {}
        self._environments: dict[str, OracleEnvironment] = {}

    def register(
        self,
        oracle: LiveParityOracle,
        *,
        environment: OracleEnvironment,
    ) -> None:
        """Register an oracle under an explicit environment classification."""

        oracle_id = oracle.oracle_id
        if not oracle_id:
            raise RegistryValidationError("oracle_id must be non-empty")
        if oracle_id in self._oracles:
            raise RegistryValidationError(f"oracle_id {oracle_id!r} already registered")
        self._oracles[oracle_id] = oracle
        self._environments[oracle_id] = environment

    def lookup(
        self,
        oracle_id: str,
        *,
        environment: OracleEnvironment = "production",
    ) -> LiveParityOracle:
        """Return the registered oracle for the requested environment.

        Raises when the oracle is unknown, or when its declared environment
        does not include the requested context. Production lookups never
        return test-environment-only oracles; test-environment lookups never
        return production-only oracles.
        """

        try:
            oracle = self._oracles[oracle_id]
        except KeyError as exc:
            raise RegistryValidationError(f"unknown oracle_id {oracle_id!r}") from exc
        declared = self._environments[oracle_id]
        if declared == "both":
            return oracle
        if environment == "both":
            raise RegistryValidationError(
                f"oracle_id {oracle_id!r} declared environment {declared!r}; "
                f"caller asked for unrestricted 'both' which the catalogue does not vend"
            )
        if declared != environment:
            raise RegistryValidationError(
                f"oracle_id {oracle_id!r} declared environment {declared!r} is not available "
                f"under requested environment {environment!r}"
            )
        return oracle

    def environment_of(self, oracle_id: str) -> OracleEnvironment:
        """Return the declared environment of a registered oracle."""

        try:
            return self._environments[oracle_id]
        except KeyError as exc:
            raise RegistryValidationError(f"unknown oracle_id {oracle_id!r}") from exc

    def is_registered(self, oracle_id: str) -> bool:
        return oracle_id in self._oracles

    def ids(self, *, environment: OracleEnvironment | None = None) -> tuple[str, ...]:
        """Return oracle ids, optionally filtered to those visible under ``environment``."""

        if environment is None:
            return tuple(sorted(self._oracles))
        return tuple(
            sorted(oracle_id for oracle_id, declared in self._environments.items() if declared in {"both", environment})
        )


def build_planned_operations(
    oracle: LiveParityOracle,
    payload: bytes,
    *,
    expected: Mapping[str, object],
) -> tuple[RemoteOperation, ...]:
    """Return the oracle's planned operations as an immutable tuple.

    A thin wrapper that lets callers obtain the plan without invoking the
    verification flow, useful for static-analysis tests that assert no
    oracle declares a forbidden operation under any policy.
    """

    operations = oracle.planned_operations(payload, expected=expected)
    if not isinstance(operations, tuple):
        raise RegistryValidationError(f"oracle {oracle.oracle_id!r} planned_operations must return a tuple")
    return operations


def pre_flight_oracle_operations(
    oracle: LiveParityOracle,
    policy: RemoteStateGuardPolicy,
    payload: bytes,
    *,
    expected: Mapping[str, object],
) -> tuple[RemoteOperation, ...]:
    """Pre-flight every planned operation through the remote-state guard.

    Returns the validated operation tuple if every operation is allowed.
    Raises :class:`RegistryValidationError` on the first refused operation;
    the oracle must not be invoked when this raises, since the planned set
    contains a step the policy forbids.
    """

    operations = build_planned_operations(oracle, payload, expected=expected)
    for index, operation in enumerate(operations):
        try:
            assert_remote_operation_allowed(policy, operation)
        except RegistryValidationError as exc:
            raise RegistryValidationError(
                f"oracle {oracle.oracle_id!r} planned operation {index} blocked by policy {policy.id!r}: {exc}"
            ) from exc
    return operations


def evaluate_planned_operations(
    oracle: LiveParityOracle,
    policy: RemoteStateGuardPolicy,
    payload: bytes,
    *,
    expected: Mapping[str, object],
) -> ParityResult | tuple[RemoteOperation, ...]:
    """Evaluate planned operations against the policy without raising.

    Returns either a ``blocked``-verdict :class:`ParityResult` (when any
    planned operation is rejected) or the validated operation tuple itself.
    Callers that prefer an exception-free interface use this; tests and
    dry-runs use it to inspect blocked verdicts.
    """

    operations = build_planned_operations(oracle, payload, expected=expected)
    blocked_reasons: list[str] = []
    for index, operation in enumerate(operations):
        decision = evaluate_remote_operation(policy, operation)
        if decision.decision == "blocked":
            blocked_reasons.append(f"step {index}: {decision.reason}")
    if blocked_reasons:
        return ParityResult(
            oracle_id=oracle.oracle_id,
            cross_reference_id=policy.id,
            verdict="blocked",
            narrative="; ".join(blocked_reasons),
        )
    return operations


def assert_oracle_operations_allowed(
    oracle: LiveParityOracle,
    policy: RemoteStateGuardPolicy,
    operations: Iterable[RemoteOperation],
) -> None:
    """Raise unless every operation in ``operations`` is allowed by ``policy``.

    Concrete oracle adapters call this at the entry of ``verify_payload`` so
    that the guard is the *only* gate before any side-effecting code, even
    when the oracle reuses an externally constructed operation list.
    """

    for index, operation in enumerate(operations):
        try:
            assert_remote_operation_allowed(policy, operation)
        except RegistryValidationError as exc:
            raise RegistryValidationError(
                f"oracle {oracle.oracle_id!r} operation {index} blocked by policy {policy.id!r}: {exc}"
            ) from exc


def resolve_cross_reference_oracle(
    *,
    cross_reference_id: str,
    oracle_id: str | None,
    catalogue: LiveParityCatalogue,
    environment: OracleEnvironment = "production",
) -> LiveParityOracle:
    """Resolve a cross-reference's bound oracle through the catalogue.

    Re-frames every catalogue lookup error so the message names the
    cross-reference id alongside the oracle id. Callers consume the result
    inside the calculation engine; the resolver does not perform any
    network operation by itself.

    The resolver requires the cross-reference to declare a binding. Cross-
    references with no oracle are not resolved here; their absence is a
    distinct case from "binding present but unresolvable" and the caller
    handles it before delegating.
    """

    if oracle_id is None:
        raise RegistryValidationError(f"cross-reference {cross_reference_id!r} has no oracle binding to resolve")
    try:
        return catalogue.lookup(oracle_id, environment=environment)
    except RegistryValidationError as exc:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} bound oracle {oracle_id!r}: {exc}"
        ) from exc


def audit_oracle_bindings(
    modelo: ModeloDefinition,
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = "production",
) -> tuple[str, ...]:
    """Inspect every cross-reference binding in a modelo against the catalogue.

    Returns a tuple of human-readable failure strings, one per cross-
    reference whose bound oracle id either is not registered in the
    catalogue or is registered under an incompatible environment. Cross-
    references with no binding are skipped silently.

    A declared binding must resolve through the supplied catalogue. An
    empty catalogue is valid only when no cross-reference declares an
    oracle binding.

    The function never raises and never performs any network operation.
    Failure aggregation is the caller's job.
    """

    failures: list[str] = []
    for revision in modelo.revisions.values():
        for cross_reference in revision.live_cross_references:
            oracle_id = cross_reference.oracle_id
            if oracle_id is None:
                continue
            try:
                oracle = catalogue.lookup(oracle_id, environment=environment)
            except RegistryValidationError as exc:
                failures.append(
                    f"modelo {modelo.id} revision {revision.id} cross-reference "
                    f"{cross_reference.id} bound oracle {oracle_id!r}: {exc}"
                )
                continue
            if (cross_reference.surface, oracle.surface_kind) not in _COMPATIBLE_SURFACE_PAIRS:
                failures.append(
                    f"modelo {modelo.id} revision {revision.id} cross-reference "
                    f"{cross_reference.id} surface {cross_reference.surface!r} is not "
                    f"compatible with oracle {oracle_id!r} surface_kind {oracle.surface_kind!r}"
                )
    return tuple(failures)


def audit_registry_oracle_bindings(
    modelos: Iterable[ModeloDefinition],
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = "production",
) -> tuple[str, ...]:
    """Aggregate ``audit_oracle_bindings`` over an iterable of modelos.

    Application bootstrap calls this once per startup to surface every
    binding-vs-catalogue mismatch in a single report alongside the
    registry-validator's own failures. The function preserves the order
    of the input iterable so the report is deterministic.
    """

    failures: list[str] = []
    for modelo in modelos:
        failures.extend(audit_oracle_bindings(modelo, catalogue, environment=environment))
    return tuple(failures)
