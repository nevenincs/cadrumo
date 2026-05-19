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

from abc import abstractmethod
from collections.abc import Iterable, Mapping
from json import JSONDecodeError, loads
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._errors import RegistryValidationError
from ._remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
    evaluate_remote_operation,
)
from ._schedules import profile_condition_matches

if TYPE_CHECKING:
    from ._schema import LiveCrossReferenceDecision, ModeloDefinition

__all__ = [
    "BaseCheckerOracle",
    "CrossReferenceApplicability",
    "CrossReferenceApplicabilityDeclaracion",
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
    "collect_applicability_declarations",
    "collect_orphan_oracle_ids",
    "decode_replay_json_payload",
    "evaluate_cross_reference_applicability",
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
# Any new oracle surface_kind or cross-reference surface must extend this set
# in the same change that introduces it.
_COMPATIBLE_SURFACE_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("open_simulator", "open_simulator"),
        ("integration_test_service", "integration_test_service"),
        ("public_read_surface", "vat_id_check"),
        ("public_read_surface", "file_validator"),
        ("authenticated_read_surface", "pre_filing_validator"),
        # AEAT VAT-ID consult surfaces (GROI today, IXVI under cert auth) are
        # callable verification surfaces gated on cl@ve-movil / certificate.
        # The pair is added per the authenticated-synthetic-surface-taxonomy
        # ADR (2026-05-07).
        ("authenticated_simulator", "vat_id_check"),
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
                raise RegistryValidationError(f"duplicate parity field {field.name!r}")
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


class CrossReferenceApplicability(_ParityModel):
    """Profile-applicability outcome for one live cross-reference decision.

    The model is the typed signal callers consume to decide whether to
    invoke a cross-reference at all. ``applicable=True`` with no
    predicates declared is the default backwards-compatible case (every
    binding declared before the applicability gate landed).
    """

    cross_reference_id: str = Field(min_length=1, max_length=128)
    applicable: bool
    matched_explanations: tuple[str, ...] = ()
    unmet_predicate_fields: tuple[str, ...] = ()


def evaluate_cross_reference_applicability(
    decision: LiveCrossReferenceDecision,
    profile_facts: Mapping[str, object] | object,
) -> CrossReferenceApplicability:
    """Evaluate a cross-reference's applicability against a profile.

    Returns a typed :class:`CrossReferenceApplicability` rather than a
    bare bool so callers (resolver, audit, live tests) consume a
    single shape. The function is profile-state evaluation only; it
    performs no network or catalogue lookup.

    A decision with no applicability_predicates is unconditionally
    applicable (backwards-compat). When predicates are declared, mode
    governs combination: ``all`` requires every predicate to match;
    ``any`` requires at least one match.
    """

    if not decision.applicability_predicates:
        return CrossReferenceApplicability(
            cross_reference_id=decision.id,
            applicable=True,
        )
    matched: list[str] = []
    unmet: list[str] = []
    for predicate in decision.applicability_predicates:
        if profile_condition_matches(predicate, profile_facts):
            matched.append(predicate.explanation)
        else:
            unmet.append(predicate.field)
    applicable = not unmet if decision.applicability_condition_mode == "all" else bool(matched)
    return CrossReferenceApplicability(
        cross_reference_id=decision.id,
        applicable=applicable,
        matched_explanations=tuple(matched),
        unmet_predicate_fields=tuple(unmet),
    )


def resolve_cross_reference_oracle(
    *,
    cross_reference_id: str,
    oracle_id: str | None,
    catalogue: LiveParityCatalogue,
    environment: OracleEnvironment = "production",
    decision: LiveCrossReferenceDecision | None = None,
    profile_facts: Mapping[str, object] | object | None = None,
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

    Optional applicability gate: when both ``decision`` and
    ``profile_facts`` are supplied, ``evaluate_cross_reference_applicability``
    runs first and the resolver raises a typed
    :class:`RegistryValidationError` naming the unmet predicate fields if
    the binding is not applicable to the profile. Callers that don't
    thread profile facts (legacy adapters, the audit) keep the old
    catalogue-only resolution path by omitting both arguments.
    """

    if oracle_id is None:
        raise RegistryValidationError(f"cross-reference {cross_reference_id!r} has no oracle binding to resolve")
    if decision is not None and profile_facts is not None:
        applicability = evaluate_cross_reference_applicability(decision, profile_facts)
        if not applicability.applicable:
            unmet = ", ".join(applicability.unmet_predicate_fields) or "<unmet>"
            raise RegistryValidationError(
                f"cross-reference {cross_reference_id!r} is not applicable to the supplied "
                f"profile: unmet predicate fields ({unmet})"
            )
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


class CrossReferenceApplicabilityDeclaracion(_ParityModel):
    """A registry-declared applicability shape for one cross-reference.

    The model is a structural read of the registry data — the audit
    surface emits this so CI / dashboards can see which bindings are
    profile-gated without re-evaluating any predicate. Decoupled from
    :class:`CrossReferenceApplicability` (the run-time evaluation
    result).
    """

    modelo_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)
    cross_reference_id: str = Field(min_length=1, max_length=128)
    applicability_condition_mode: Literal["all", "any"]
    predicate_fields: tuple[str, ...]


def collect_applicability_declarations(
    modelos: Iterable[ModeloDefinition],
) -> tuple[CrossReferenceApplicabilityDeclaracion, ...]:
    """Surface every cross-reference that declares applicability predicates.

    Pure registry-data introspection: never reads profile facts, never
    invokes the evaluator. Cross-references with no predicates are
    omitted (the unconditionally-applicable default). Order is
    ``(modelo_id, revision_id, cross_reference_id)`` for deterministic
    audit output.
    """

    declarations: list[CrossReferenceApplicabilityDeclaracion] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for cross_reference in revision.live_cross_references:
                if not cross_reference.applicability_predicates:
                    continue
                declarations.append(
                    CrossReferenceApplicabilityDeclaracion(
                        modelo_id=modelo.id,
                        revision_id=revision.id,
                        cross_reference_id=cross_reference.id,
                        applicability_condition_mode=cross_reference.applicability_condition_mode,
                        predicate_fields=tuple(
                            predicate.field for predicate in cross_reference.applicability_predicates
                        ),
                    )
                )
    return tuple(declarations)


def collect_orphan_oracle_ids(
    modelos: Iterable[ModeloDefinition],
    catalogue: LiveParityCatalogue,
) -> tuple[str, ...]:
    """Return catalogue oracle ids that no cross-reference binds.

    A registered-but-unused oracle indicates one of:
    - the oracle was registered for a future binding still in flight,
    - a cross-reference's oracle_id was renamed without updating the
      catalogue,
    - the binding was retired but the catalogue registration stayed.

    The audit surfaces the set so CI / dashboards can flag drift.
    Order is the catalogue's lexicographic order for deterministic
    output.
    """

    bound: set[str] = set()
    modelo_tuple = tuple(modelos)
    for modelo in modelo_tuple:
        for revision in modelo.revisions.values():
            for cross_reference in revision.live_cross_references:
                if cross_reference.oracle_id is not None:
                    bound.add(cross_reference.oracle_id)
    return tuple(sorted(set(catalogue.ids()) - bound))


def decode_replay_json_payload(raw: bytes, *, surface_label: str) -> dict[str, Any]:
    """Decode a UTF-8 JSON replay payload to a top-level JSON object.

    Shared by replay drivers: enforces UTF-8 encoding, valid JSON, and a
    top-level object (dict) shape. ``surface_label`` is interpolated into
    the error messages so callers can identify their oracle in failures
    (e.g. ``"AEAT NIF-IVA replay"``).
    """

    try:
        document = loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise RegistryValidationError(f"{surface_label} payload must be UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise RegistryValidationError(f"{surface_label} payload must be a JSON object")
    return document


class _CheckerDriver[CheckerObservation](Protocol):
    """Structural type of a checker-style replay/live driver."""

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
    ) -> CheckerObservation: ...


class BaseCheckerOracle[CheckerObservation]:
    """Shared orchestrator for checker-style oracles.

    Encapsulates the common ``verify_payload`` template used by per-key
    verdict checkers (NIF-IVA, GROI, and analogous future surfaces):
    guard pre-flight, driver presence branch, driver-error → unverifiable
    translation, per-key field comparison, overall verdict, and result
    packing. Subclasses provide the surface-specific bits: the planned
    operations builder, expected-value normaliser, observed-value lookup,
    per-field comparison, and human narrative label.

    Per-domain typed observation models (NIF/IVA vs GROI) stay in the
    concrete adapter modules; this base composes them generically.
    """

    surface_label: str

    def __init__(self, *, driver: _CheckerDriver[CheckerObservation] | None = None) -> None:
        self._driver: _CheckerDriver[CheckerObservation] | None = driver

    @property
    @abstractmethod
    def oracle_id(self) -> str: ...

    @property
    @abstractmethod
    def surface_kind(self) -> OracleSurfaceKind: ...

    @abstractmethod
    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]: ...

    @abstractmethod
    def _expected_values(self, expected: Mapping[str, object]) -> dict[str, str]: ...

    @abstractmethod
    def _observed_for(
        self,
        observation: CheckerObservation,
        key: str,
    ) -> str | None: ...

    @abstractmethod
    def _compare_field(self, key: str, expected: str, *, observed: str | None) -> ParityFieldComparison: ...

    @abstractmethod
    def _observation_locator(self, observation: CheckerObservation) -> str | None: ...

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
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
            self._compare_field(key, expected_value, observed=self._observed_for(observation, key))
            for key, expected_value in sorted(self._expected_values(expected).items())
        )
        verdict: ParityVerdict = (
            "match" if fields and all(field.verdict == "match" for field in fields) else "mismatch"
        )
        return ParityResult(
            oracle_id=self.oracle_id,
            cross_reference_id=policy.id,
            verdict=verdict,
            narrative=f"{self.surface_label} {driver.mode} comparison returned {verdict}.",
            fields=fields,
            raw_evidence_locator=self._observation_locator(observation),
        )


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
