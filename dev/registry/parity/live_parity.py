"""Modelo-agnostic live parity oracle backend.

This module sits one level above :mod:`remote_state_guard` and ties the
existing fail-closed remote-state policy to a uniform contract for *read-only*
verification of registry-rendered payloads against AEAT live surfaces.

Two-fold hardening underpins the design:

1. Local hardening -- already in place via the registry's static
   conformance tests (record-design positions, casilla widths, byte
   roundtrips, formula closure).
2. Live conformance -- drive a synthetic, registry-rendered payload
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

from pydantic import BaseModel, Field, field_validator

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.logging import get_logger
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import CrossReferenceId, OracleId
from cadrumo.domain.calculations.registry.remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operations_allowed,
)

from .external_grounding import BUNDLED_ORACLE_EVIDENCE_LOCATOR_MAX_LENGTH

if TYPE_CHECKING:
    pass

_log = get_logger(__name__)

__all__ = [
    "LiveParityOracle",
    "OracleSurfaceKind",
    "ParityFieldComparison",
    "ParityResult",
    "ParityVerdict",
    "ReplayPayload",
    "decode_replay_json_payload",
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


# Allow-list of compatible (cross-reference surface, oracle surface_kind)
# pairs. Bindings whose pair is not listed here are flagged by the boot-time
# audit. ``static_official_documentation`` is intentionally absent: static-doc
# surfaces have no verifiable response and cannot be the target of any oracle.
# Any new oracle surface_kind or cross-reference surface must extend this set
# in the same change that introduces it.


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
        response values, keyed by label or casilla -- a casilla being a
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
        an AEAT-side divergence -- a mismatch is data, surfaced as the verdict
        -- and never reports ``"match"`` if any planned operation was skipped
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


class ReplayPayload(_ParityModel):
    """Typed envelope for a decoded replay JSON payload.

    Every replay driver shares the same top-level JSON contract: an
    ``observed`` mapping of captured surface strings to string values (kept
    only as audit evidence, not as a comparison key surface) and an optional
    ``raw_evidence_locator`` that links back to the raw HTTP response
    artifact for audit trails.

    Replay fixtures on disk are captured response artefacts and carry
    additional documented metadata that pre-dates the tightened schema:

    * ``scenario_id`` -- fixture-author label that identifies the
      operator scenario the payload was captured against;
    * ``profile_overrides`` -- per-fixture profile overrides used to
      drive the registry comparison;
    * ``expected`` -- captured human-readable labels paired with their
      expected values, retained only for audit readability;
    * ``expected_by_casilla_id`` -- registry-casilla-id-keyed expected
      values, used by the oracle's matcher;
    * ``observed_by_casilla_id`` -- registry-casilla-id-keyed observed
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
