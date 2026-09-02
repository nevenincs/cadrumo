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
   IVA-ID checkers, pre-filing validators, AEAT integration test services).
   Every planned operation is pre-flighted against the cross-reference's
   :class:`RemoteStateGuardPolicy` before any HTTP or browser action runs;
   any policy-violating step is rejected before it leaves the process.

Each :class:`ModeloDefinition`'s registry TOML declares which oracle a
cross-reference is bound to via ``oracle_id``; this module owns the runtime
contract and the shared catalogue. Concrete oracle adapters live in sibling
modules so the abstraction stays free of network code.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from json import JSONDecodeError, loads
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator

from ....core.casilla_id import CasillaId
from ....core.logging import get_logger
from ....core.models import STRICT_FROZEN_CONFIG
from .condition_mode import ConditionMode, ConditionModeField
from .errors import RegistryValidationError
from .external_grounding import BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH
from .ids import CrossReferenceId, OracleId, RevisionId
from .remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operations_allowed,
    evaluate_remote_operation,
)
from .schedules import profile_condition_matches

if TYPE_CHECKING:
    from .schema import ModeloDefinition
    from .schema_verification import LiveCrossReferenceDecision

_log = get_logger(__name__)
_ORACLE_ID_ADAPTER: TypeAdapter[OracleId] = TypeAdapter(OracleId)

__all__ = [
    "CrossReferenceApplicability",
    "CrossReferenceApplicabilityDeclaracion",
    "LiveParityCatalogue",
    "LiveParityOracle",
    "OracleEnvironment",
    "OracleSurfaceKind",
    "ParityFieldComparison",
    "ParityResult",
    "ParityVerdict",
    "ReplayPayload",
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


class ParityVerdictKind(StrEnum):
    """How a live-parity comparison came out."""

    MATCH = "match"
    MISMATCH = "mismatch"
    UNVERIFIABLE = "unverifiable"
    BLOCKED = "blocked"
    """Reserved for a whole result, never for one field: a run can be blocked before
    any field is compared, and a field that was never compared is unverifiable rather
    than blocked."""


ParityVerdict = Literal[
    ParityVerdictKind.MATCH,
    ParityVerdictKind.MISMATCH,
    ParityVerdictKind.UNVERIFIABLE,
    ParityVerdictKind.BLOCKED,
]
"""Every verdict, for a result-level field."""

ParityFieldVerdict = Literal[
    ParityVerdictKind.MATCH,
    ParityVerdictKind.MISMATCH,
    ParityVerdictKind.UNVERIFIABLE,
]
"""The verdicts one FIELD can carry, which excludes ``BLOCKED``.

A genuine narrowing, written out three times before this existed -- once on the
comparison model and twice in the Renta WEB oracle. Keeping it named stops a blocked
run being recorded as a field-level outcome, which would report a comparison that never
happened as one that did."""
OracleSurfaceKind = Literal[
    "file_validator",
    "open_simulator",
    "iva_id_check",
    "pre_filing_validator",
    "integration_test_service",
]


class OracleEnvironment(StrEnum):
    """Runtime environment classification for oracle catalogue entries.

    ``PRODUCTION`` — the oracle is safe to call against the live AEAT surface.
    ``TEST_ENVIRONMENT`` — the oracle targets a sandboxed / integration-test
    surface only and must not be invoked from production callers.
    ``BOTH`` — the oracle is safe under either classification (e.g., public
    read-only surfaces that carry no production-state side-effect).
    """

    PRODUCTION = "production"
    TEST_ENVIRONMENT = "test_environment"
    BOTH = "both"


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
        ("public_read_surface", "iva_id_check"),
        ("public_read_surface", "file_validator"),
        ("authenticated_read_surface", "pre_filing_validator"),
        # AEAT IVA-ID consult surfaces (GROI today, IXVI under cert auth) are
        # callable verification surfaces gated on cl@ve-movil / certificate.
        ("authenticated_simulator", "iva_id_check"),
    },
)


class _ParityModel(BaseModel):
    """Strict frozen base for parity records."""

    model_config = STRICT_FROZEN_CONFIG


class ParityFieldComparison(_ParityModel):
    """One field-level comparison between an expected and observed value."""

    name: str = Field(min_length=1, max_length=160)
    expected: str
    observed: str
    verdict: ParityFieldVerdict


class ParityResult(_ParityModel):
    """Outcome of running a synthetic payload through a live parity oracle.

    The oracle layer never returns "filing succeeded" or any other side-effect
    confirmation; the only signal callers consume is whether AEAT's response
    confirms the registry-rendered payload conforms (``match``), diverges
    (``mismatch``), is structurally unanswerable by the surface
    (``unverifiable``), or was refused before it left the process by the
    remote-state guard (``blocked``).
    """

    oracle_id: OracleId
    cross_reference_id: CrossReferenceId
    verdict: ParityVerdict
    narrative: str = Field(min_length=1, max_length=2048)
    fields: tuple[ParityFieldComparison, ...] = ()
    # Bound shared with the bundled-oracle grounding contract rather than
    # restated: the same corpus is read by both, so a locator grounding
    # accepts must not be refused here. It stays OPTIONAL because not every
    # checker surface carries bundled-corpus evidence; surfaces that do
    # require it apply ``require_bundled_oracle_evidence_locator``.
    raw_evidence_locator: str | None = Field(
        default=None,
        max_length=BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH,
    )

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
    def oracle_id(self) -> OracleId:
        """Stable identifier this oracle registers under in the catalogue.

        A modelo (an AEAT tax form) binds one of its live cross-references to
        an oracle by naming this id in registry TOML; the runtime resolves the
        binding by looking the same id up in the ``LiveParityCatalogue``. The
        value must be non-empty and unique across the process-wide catalogue.

        Returns:
            The oracle's typed catalogue key.
        """
        ...

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        """Kind of AEAT verification surface this oracle drives.

        One of the ``OracleSurfaceKind`` literals (``file_validator``,
        ``open_simulator``, ``iva_id_check``, ``pre_filing_validator``,
        ``integration_test_service``). The boot-time binding audit cross-checks
        this value against the cross-reference's own surface using the
        ``_COMPATIBLE_SURFACE_PAIRS`` allow-list, so a mismatch is reported
        rather than silently called.

        Returns:
            The surface classification as an ``OracleSurfaceKind`` literal.
        """
        ...

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Enumerate every remote step this oracle will perform, in order.

        Returns the full, ordered set of HTTP requests, browser actions, or
        local computations the oracle intends to run for ``payload`` (the
        registry-rendered bytes to verify) and ``expected`` (the expected
        response values, keyed by label or casilla — a casilla being a
        numbered box on the form). The oracle must not perform any operation
        absent from this tuple; callers pre-flight each entry through the
        remote-state guard before any side-effecting code runs.

        Args:
            payload: The synthetic, registry-rendered bytes to verify.
            expected: Expected response values the oracle will compare against.

        Returns:
            The planned steps as a tuple of :class:`RemoteOperation`.
        """
        ...

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
        """Run the payload through the live surface and report parity.

        Pre-flights every planned operation against ``policy`` (the
        fail-closed remote-state guard for this cross-reference), then drives
        the surface and compares its response to ``expected``. Never raises on
        an AEAT-side divergence — a mismatch is data, surfaced as the verdict
        — and never reports ``"match"`` if any planned operation was skipped
        or rewritten. A step the policy forbids yields a ``"blocked"`` verdict
        instead of a remote call.

        Args:
            policy: The ``RemoteStateGuardPolicy`` gating remote operations.
            payload: The synthetic, registry-rendered bytes to verify.
            expected: Expected response values to compare against.

        Returns:
            A :class:`ParityResult` carrying the verdict and per-field comparisons.
        """
        ...


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
        """Initialise an empty environment-partitioned oracle registry."""
        self._oracles: dict[OracleId, LiveParityOracle] = {}
        self._environments: dict[OracleId, OracleEnvironment] = {}

    def register(
        self,
        oracle: LiveParityOracle,
        *,
        environment: OracleEnvironment,
    ) -> None:
        """Register an oracle under an explicit environment classification."""
        oracle_id = _validate_oracle_id(oracle.oracle_id)
        if oracle_id in self._oracles:
            raise RegistryValidationError(f"oracle_id {oracle_id!r} already registered")
        self._oracles[oracle_id] = oracle
        self._environments[oracle_id] = environment

    def lookup(
        self,
        oracle_id: OracleId,
        *,
        environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
    ) -> LiveParityOracle:
        """Return the registered oracle for the requested environment.

        Raises when the oracle is unknown, or when its declared environment
        does not include the requested context. Production lookups never
        return test-environment-only oracles; test-environment lookups never
        return production-only oracles.

        Returns:
            The :class:`LiveParityOracle` registered under ``oracle_id``.
        """
        oracle_id = _validate_oracle_id(oracle_id)
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
                f"caller asked for unrestricted 'both' which the catalogue does not vend",
            )
        if declared != environment:
            raise RegistryValidationError(
                f"oracle_id {oracle_id!r} declared environment {declared!r} is not available "
                f"under requested environment {environment!r}",
            )
        return oracle

    def environment_of(self, oracle_id: OracleId) -> OracleEnvironment:
        """Return the declared environment of a registered oracle.

        Returns:
            The :class:`OracleEnvironment` declared for ``oracle_id``.
        """
        oracle_id = _validate_oracle_id(oracle_id)
        try:
            return self._environments[oracle_id]
        except KeyError as exc:
            raise RegistryValidationError(f"unknown oracle_id {oracle_id!r}") from exc

    def is_registered(self, oracle_id: OracleId) -> bool:
        """Report whether an oracle is registered under ``oracle_id``.

        A membership check that ignores environment classification: it returns
        ``True`` for any registered oracle regardless of whether it is
        production-only, test-environment-only, or both. Use ``lookup`` when
        the environment-visibility rules must be enforced.

        Args:
            oracle_id: The catalogue key to test.

        Returns:
            ``True`` if an oracle is registered under ``oracle_id``.
        """
        oracle_id = _validate_oracle_id(oracle_id)
        return oracle_id in self._oracles

    def ids(self, *, environment: OracleEnvironment | None = None) -> tuple[OracleId, ...]:
        """Return oracle ids, optionally filtered to those visible under ``environment``."""
        if environment is None:
            return tuple(sorted(self._oracles))
        return tuple(
            sorted(
                [oracle_id for oracle_id, declared in self._environments.items() if declared in {"both", environment}],
            ),
        )


def _validate_oracle_id(value: str) -> OracleId:
    """Validate a catalogue key against the registry ``OracleId`` contract."""
    try:
        return _ORACLE_ID_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise RegistryValidationError(f"oracle_id {value!r} is not a valid OracleId: {exc}") from exc


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

    Returns:
        Tuple of :class:`RemoteOperation` steps planned by the oracle.
    """
    operations = oracle.planned_operations(payload, expected=expected)
    return operations


def pre_flight_oracle_operations(
    oracle: LiveParityOracle,
    policy: RemoteStateGuardPolicy,
    payload: bytes,
    *,
    expected: Mapping[str, object],
) -> tuple[RemoteOperation, ...]:
    """Pre-flight every planned :class:`RemoteOperation` through the remote-state guard.

    Returns the validated operation tuple if every operation is allowed.
    Raises :class:`RegistryValidationError` on the first refused operation;
    the oracle must not be invoked when this raises, since the planned set
    contains a step the policy forbids.
    """
    operations = build_planned_operations(oracle, payload, expected=expected)
    return assert_remote_operations_allowed(
        policy,
        operations,
        context=f"oracle {oracle.oracle_id!r} planned operation",
    )


def evaluate_planned_operations(
    oracle: LiveParityOracle,
    policy: RemoteStateGuardPolicy,
    payload: bytes,
    *,
    expected: Mapping[str, object],
) -> ParityResult | tuple[RemoteOperation, ...]:
    """Evaluate planned :class:`RemoteOperation` items against the policy without raising.

    Returns either a ``blocked``-verdict :class:`ParityResult` (when any
    planned operation is rejected) or the validated :class:`RemoteOperation` tuple itself.
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
    assert_remote_operations_allowed(policy, operations, context=f"oracle {oracle.oracle_id!r} operation")


class CrossReferenceApplicability(_ParityModel):
    """Profile-applicability outcome for one live cross-reference decision.

    The model is the typed signal callers consume to decide whether to
    invoke a cross-reference at all. ``applicable=True`` with no
    predicates declared is the explicit unconditionally-applicable case.
    """

    cross_reference_id: CrossReferenceId
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
    applicable. When predicates are declared, mode
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
    applicable = not unmet if decision.applicability_condition_mode is ConditionMode.ALL else bool(matched)
    return CrossReferenceApplicability(
        cross_reference_id=decision.id,
        applicable=applicable,
        matched_explanations=tuple(matched),
        unmet_predicate_fields=tuple(unmet),
    )


def resolve_cross_reference_oracle(
    *,
    cross_reference_id: CrossReferenceId,
    oracle_id: OracleId | None,
    catalogue: LiveParityCatalogue,
    environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
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
    thread profile facts (for example, audit code) use catalogue-only
    resolution by omitting both arguments.

    Returns:
        The :class:`LiveParityOracle` bound to the cross-reference.
    """
    if oracle_id is None:
        raise RegistryValidationError(f"cross-reference {cross_reference_id!r} has no oracle binding to resolve")
    if decision is not None and profile_facts is not None:
        applicability = evaluate_cross_reference_applicability(decision, profile_facts)
        if not applicability.applicable:
            unmet = ", ".join(applicability.unmet_predicate_fields) or "<unmet>"
            raise RegistryValidationError(
                f"cross-reference {cross_reference_id!r} is not applicable to the supplied "
                f"profile: unmet predicate fields ({unmet})",
            )
    try:
        return catalogue.lookup(oracle_id, environment=environment)
    except RegistryValidationError as exc:
        raise RegistryValidationError(
            f"cross-reference {cross_reference_id!r} bound oracle {oracle_id!r}: {exc}",
        ) from exc


def audit_oracle_bindings(
    modelo: ModeloDefinition,
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
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

    Args:
        modelo: The :class:`ModeloDefinition` whose cross-reference bindings to audit.
        catalogue: :class:`LiveParityCatalogue` registering known oracles by id
            and environment; bindings unresolved against it produce failures.
        environment: :class:`OracleEnvironment` (defaults to ``PRODUCTION``)
            each binding must be registered under to be considered resolved.
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
                    f"{cross_reference.id} bound oracle {oracle_id!r}: {exc}",
                )
                continue
            if (cross_reference.surface, oracle.surface_kind) not in _COMPATIBLE_SURFACE_PAIRS:
                failures.append(
                    f"modelo {modelo.id} revision {revision.id} cross-reference "
                    f"{cross_reference.id} surface {str(cross_reference.surface)!r} is not "
                    f"compatible with oracle {oracle_id!r} surface_kind {oracle.surface_kind!r}",
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
    revision_id: RevisionId
    cross_reference_id: CrossReferenceId
    applicability_condition_mode: ConditionModeField
    predicate_fields: tuple[str, ...]


def collect_applicability_declarations(
    modelos: Iterable[ModeloDefinition],
) -> tuple[CrossReferenceApplicabilityDeclaracion, ...]:
    """Return :class:`CrossReferenceApplicabilityDeclaracion` items for every cross-reference with predicates.

    Pure registry-data introspection: never reads profile facts, never
    invokes the evaluator. Cross-references with no predicates are
    omitted (the unconditionally-applicable default). Order is
    ``(modelo_id, revision_id, cross_reference_id)`` for deterministic
    audit output.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` entries to scan.
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
                    ),
                )
    return tuple(declarations)


def collect_orphan_oracle_ids(
    modelos: Iterable[ModeloDefinition],
    catalogue: LiveParityCatalogue,
) -> tuple[OracleId, ...]:
    """Return catalogue oracle ids that no cross-reference binds.

    A registered-but-unused oracle indicates one of:

    - the oracle was registered for a future binding still in flight,
    - a cross-reference's oracle_id was renamed without updating the
      catalogue,
    - the binding was retired but the catalogue registration stayed.

    The audit surfaces the set so CI / dashboards can flag drift.
    Order is the catalogue's lexicographic order for deterministic
    output.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances whose
            cross-reference bindings determine which oracle ids are in use.
        catalogue: The live parity catalogue to check for orphaned entries.
    """
    bound: set[OracleId] = set()
    modelo_tuple = tuple(modelos)
    for modelo in modelo_tuple:
        for revision in modelo.revisions.values():
            for cross_reference in revision.live_cross_references:
                if cross_reference.oracle_id is not None:
                    bound.add(cross_reference.oracle_id)
    return tuple(sorted(set(catalogue.ids()) - bound))


class ReplayPayload(_ParityModel):
    """Typed envelope for a decoded replay JSON payload.

    Every replay driver shares the same top-level JSON contract: an
    ``observed`` mapping of captured surface strings to string values (kept
    only as audit evidence, not as a comparison key surface) and an optional
    ``raw_evidence_locator`` that links back to the raw HTTP response
    artifact for audit trails.

    Replay fixtures on disk are captured response artefacts and carry
    additional documented metadata that pre-dates the tightened schema:

    * ``scenario_id`` — fixture-author label that identifies the
      operator scenario the payload was captured against;
    * ``profile_overrides`` — per-fixture profile overrides used to
      drive the registry comparison;
    * ``expected`` — captured human-readable labels paired with their
      expected values, retained only for audit readability;
    * ``expected_by_casilla_id`` — registry-casilla-id-keyed expected
      values, used by the oracle's matcher;
    * ``observed_by_casilla_id`` — registry-casilla-id-keyed observed
      values, used by the oracle's matcher.

    ``model_config`` inherits ``strict=True, frozen=True, extra="forbid"``
    from :class:`_ParityModel`. The documented fields above are typed
    explicitly; any other unknown key still raises at validation.
    """

    observed: Mapping[str, str]
    # Bound shared with the bundled-oracle grounding contract rather than
    # restated: the same corpus is read by both, so a locator grounding
    # accepts must not be refused here. It stays OPTIONAL because not every
    # checker surface carries bundled-corpus evidence; surfaces that do
    # require it apply ``require_bundled_oracle_evidence_locator``.
    raw_evidence_locator: str | None = Field(
        default=None,
        max_length=BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH,
    )
    scenario_id: str | None = Field(default=None, max_length=256)
    profile_overrides: Mapping[str, str] = Field(default_factory=dict)
    expected: Mapping[str, str] = Field(default_factory=dict)
    expected_by_casilla_id: Mapping[CasillaId, str] = Field(default_factory=dict)
    observed_by_casilla_id: Mapping[CasillaId, str] = Field(default_factory=dict)


def decode_replay_json_payload(raw: bytes, *, surface_label: str) -> ReplayPayload:
    """Decode a UTF-8 JSON replay payload into a typed :class:`ReplayPayload`.

    Shared by replay drivers: enforces UTF-8 encoding, valid JSON, a
    top-level object (dict) shape, and the :class:`ReplayPayload` schema.
    ``surface_label`` is interpolated into the error messages so callers
    can identify their oracle in failures (e.g. ``"AEAT NIF-IVA replay"``).
    """
    try:
        document = loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError) as exc:
        raise RegistryValidationError(f"{surface_label} payload must be UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise RegistryValidationError(f"{surface_label} payload must be a JSON object")
    _log.debug("decoding replay payload for %s", surface_label)
    return ReplayPayload.model_validate(document)


def audit_registry_oracle_bindings(
    modelos: Iterable[ModeloDefinition],
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
) -> tuple[str, ...]:
    """Aggregate ``audit_oracle_bindings`` over an iterable of modelos.

    Application bootstrap calls this once per startup to surface every
    binding-vs-catalogue mismatch in a single report alongside the
    registry-validator's own failures. The function preserves the order
    of the input iterable so the report is deterministic.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances to audit.
        catalogue: The live parity catalogue to validate against.
        environment: Target oracle environment classification.
    """
    failures: list[str] = []
    for modelo in modelos:
        failures.extend(audit_oracle_bindings(modelo, catalogue, environment=environment))
    return tuple(failures)
