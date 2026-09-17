"""Application contracts for past-filing casilla observations.

Stores :class:`~domain.calculations.registry.bindings.RegistryModeloObservation`
records — ``(modelo, filing_year, period, casilla_values)`` — as encrypted audit
envelopes in the
:class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`.
Past-filing value rows are bound to
:data:`~adapters.persistence.storage.secure_object_namespaces.CALCULATION_OBSERVATIONS_NAMESPACE`;
IVA wallet decisions are split between the latest-state
:data:`~adapters.persistence.storage.secure_object_namespaces.IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE`
and immutable
:data:`~adapters.persistence.storage.secure_object_namespaces.IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE`
namespaces.
The records are the substrate read by
:class:`~._multi_year.PreviousFilingSourceResolver` and
:class:`~.relation_prefill.RelationPrefillSourceResolver` so annual modelos
can roll up prior quarterlies, IVA prorrata can compute its four-year backward
mean, IS BIN carryforward can replay prior-year bases imponibles negativas, and
IVA regularización inversiones can apply its 5/10 year straight-line schedule.

Producers are out of scope for this module: the modelo filing flow
will write here when an operator successfully files via the app,
and the live-AEAT capture path will write here when justificantes
are parsed. This module exposes only the typed read/write surface.

Sensitivity is :class:`~core.classification.policies.SensitivityClass`
``AUDIT`` — these records reconstruct exactly what was filed and so are
identity-bearing tax substrate. They are stored encrypted at rest through an
:class:`~adapters.persistence.storage.envelope.contract.Envelope`-wrapped repository.

The store is value-centric. Clean-state proof still has to join these rows with
filing records, verification reports, and justificante evidence through
:func:`~.cross_period_clean_state.evaluate_cross_period_clean_state`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final, Literal, Protocol, cast, runtime_checkable

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.identity.hex_ids import FilingRecordId
from ...core.identity.tax_id import tax_id_identity_token
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.observed_header_fact import ObservedHeaderFact
from ...core.period import Period
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.result_disposition import ResultDisposition
from ...core.secure_object_write import SecureObjectWrite
from ...core.time.utc import UtcInstant
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.calculations.registry.casilla_membership import undeclared_casilla_ids
from ...domain.calculations.registry.errors import AmbiguousRevisionSelectionError, RegistrySnapshotError
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.iva_compensation.filed_derivation import M303CompensationBasisValue
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...domain.modelos.filing_text import ModeloActorLabel, OperatorReason
from .errors import (
    ObservationCasillaReferenceError,
    ObservationKeyError,
)
from .revision_carry_gate import revision_carry_outcome


def require_decision_registry_coordinates_current(
    decision: IvaCompensationReconciliationDecision,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse a persisted IVA decision whose target or source revision diverges."""
    for snapshot_ref in (decision.target_registry_snapshot_ref, *decision.source_registry_snapshot_refs):
        outcome = revision_carry_outcome(snapshot_ref, operation=operation)
        if outcome.refused:
            raise RegistrySnapshotError(
                "persisted IVA compensation decision registry coordinate cannot be re-confirmed: "
                f"{snapshot_ref.modelo}/{snapshot_ref.modelo_year}/{snapshot_ref.period}/"
                f"{snapshot_ref.revision_id}: {outcome.detail}"
            )


class ObservationSourceKind(StrEnum):
    """Origin of a persisted calculation observation.

    This classifies the observation provenance before a filing's separate
    :class:`~ExternalEvidenceKind` is materialised. Only the
    three AEAT origins are official filing evidence; local app and operator
    rows may support calculation prefill but cannot establish filing-grade
    cross-period readiness.
    """

    APP_FILING = "app_filing"
    OPERATOR_MANUAL = "operator_manual"
    AEAT_SEDE_JUSTIFICANTE = "aeat_sede_justificante"
    AEAT_SEDE_LIVE_CAPTURE = "aeat_sede_live_capture"
    AEAT_CSV_REGISTER = "aeat_csv_register"

    @property
    def is_official_aeat(self) -> bool:
        """Whether this provenance was observed from an AEAT source."""
        return self in (
            self.AEAT_SEDE_JUSTIFICANTE,
            self.AEAT_SEDE_LIVE_CAPTURE,
            self.AEAT_CSV_REGISTER,
        )


APP_FILING_SOURCE_KIND: Final[ObservationSourceKind] = ObservationSourceKind.APP_FILING
"""Non-official provenance stamped on observations filed through the app."""


def is_official_aeat_observation_source(source_kind: ObservationSourceKind | str) -> bool:
    """Return whether an observation provenance is official AEAT evidence.

    Unknown and aggregate values (for example ``"mixed"`` group evidence)
    fail closed as non-official rather than silently gaining filing authority.
    """
    try:
        return ObservationSourceKind(source_kind).is_official_aeat
    except ValueError:
        return False


class ResultDispositionProjection(BaseModel):
    """Validated Modelo 303 disposition evidence owned by an observation envelope.

    The filed ``declaration_type`` is not a casilla.  Keeping it here means a
    :class:`RegistryModeloObservation` remains a calculation-only record while
    the envelope retains the typed disposition and how it was established.
    """

    model_config = STRICT_FROZEN_CONFIG

    disposition: ResultDisposition
    provenance_kind: Literal["source_header", "app_filing"]
    provenance_locator: str = Field(min_length=1, max_length=512)

    @field_validator("disposition", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_disposition(cls, value: object) -> ResultDisposition:
        return ResultDisposition(value)


class PriorDomiciliationElectionProjection(BaseModel):
    """Safe provenance for a Modelo 303 rectificativa's prior-debit election.

    A cancellation/modification is actionable only when the application has
    already joined the rectificativa to an AEAT-attested baseline filing and to
    that filed declaration's submitted-file ``U`` header.  The projection keeps
    the semantic election and redacted join coordinates, never an account or
    rendered header value.
    """

    model_config = STRICT_FROZEN_CONFIG

    election: PriorDomiciliationElection
    baseline_filing_record_id: FilingRecordId | None = None
    baseline_evidence_reference_id: str | None = Field(default=None, min_length=1, max_length=128)
    baseline_result_disposition: ResultDisposition | None = None
    baseline_source_header_locator: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("election", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_election(cls, value: object) -> PriorDomiciliationElection:
        return PriorDomiciliationElection(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _enforce_baseline_proof_shape(self) -> PriorDomiciliationElectionProjection:
        proof = (
            self.baseline_filing_record_id,
            self.baseline_evidence_reference_id,
            self.baseline_result_disposition,
            self.baseline_source_header_locator,
        )
        if self.election is PriorDomiciliationElection.KEEP:
            if any(value is not None for value in proof):
                raise ValueError("KEEP prior domiciliation election must not carry baseline provenance")
            return self
        if any(value is None for value in proof):
            raise ValueError("CANCEL_OR_MODIFY prior domiciliation election requires complete baseline-U provenance")
        if self.baseline_result_disposition is not ResultDisposition.DOMICILIACION:
            raise ValueError("CANCEL_OR_MODIFY prior domiciliation election requires baseline disposition U")
        return self


class ObservationOverride(BaseModel):
    """Audit of one operator figure that replaced the effective observation of a coordinate.

    ``replaced_source_kind`` and ``replaced_values`` describe the envelope that
    was effective when the operator recorded the figure; both are empty when
    the coordinate held nothing. The replaced envelope itself is not destroyed:
    an official layer stays stored beside the pending-local one.
    """

    model_config = STRICT_FROZEN_CONFIG

    actor: ModeloActorLabel
    reason: OperatorReason
    recorded_at: UtcInstant
    replaced_source_kind: ObservationSourceKind | None = None
    replaced_values: dict[CasillaId, str] = Field(default_factory=dict)


class ObservationEnvelopePayload(BaseModel):
    """Canonical public persistence payload for filed observations.

    This strict, frozen model is returned by
    :class:`CalculationObservationRepository` reads and iteration. It keeps the
    :class:`RegistryModeloObservation` calculation evidence separate from the
    application capture provenance: ``captured_at``, constrained
    ``source_kind``, optional ``member_nif``, required
    ``stamped_revision_id``, and source-specific ``source_metadata``. The model
    does not encrypt that metadata; the secure repository envelope does.

    ``captured_at`` is the canonical :data:`~core.time.utc.UtcInstant`. A bare
    ``datetime`` field admitted a naive value, so a capture instant with no
    zone reached persistence and every later comparison against a UTC-aware
    instant was answering a different question than it appeared to.

    Every persisted observation carries its source registry revision stamp so
    carry reads can reconfirm the value against the law-determined revision.
    A missing or structurally invalid stamp refuses at load; a valid but
    divergent stamp is refused later by the carry gate.
    """

    model_config = STRICT_FROZEN_CONFIG

    observation: RegistryModeloObservation
    captured_at: UtcInstant
    source_kind: ObservationSourceKind = Field(
        description="Typed provenance of this calculation observation.",
    )
    member_nif: str | None = Field(
        default=None,
        max_length=16,
        description=(
            "Optional grupo-de-entidades member NIF. When set, the storage "
            "identifier is widened so distinct members' filings for the same "
            "(modelo, filing_year, period) persist as separate rows rather than "
            "overwriting one another — the cross-member fan-in the 353<-322 "
            "per_grupo_member aggregation enumerates. None preserves the "
            "single-filer (modelo, filing_year, period) key bit-for-bit."
        ),
    )
    stamped_revision_id: RevisionId = Field(
        description=(
            "Registry revision id the source filing resolved to at capture time "
            "so carry-read code can re-confirm the value against the law-determined "
            "registry revision."
        ),
    )
    source_metadata: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Encrypted source-specific provenance for the observation. Live AEAT "
            "filed observations use this for register status, expediente id, and "
            "authenticated identity so downstream readers can audit what official "
            "register row produced the calculation history."
        ),
    )
    source_headers: tuple[ObservedHeaderFact, ...] = Field(
        default=(),
        description=(
            "Typed diseño header facts AEAT stated in the filed fichero -- the "
            "tipo de declaración, the sin-actividad and REDEME markers -- each "
            "carrying the export record position it was read from. Typed rather "
            "than folded into source_metadata because that map is built from a "
            "fixed key set, so anything not named there is dropped at "
            "persistence, and because a flat string pair cannot carry the "
            "record-design locator that makes a header fact auditable back to "
            "the bytes. Nothing elects on these; they are evidence."
        ),
    )
    result_disposition: ResultDispositionProjection | None = Field(
        default=None,
        description=(
            "Validated Modelo 303 declaration disposition with the source that "
            "established it. It is envelope evidence, never a synthetic casilla."
        ),
    )
    prior_domiciliation_election: PriorDomiciliationElectionProjection | None = Field(
        default=None,
        description=(
            "Semantic prior-direct-debit election and, for X, the safe join to "
            "the externally evidenced baseline U declaration. This is never bank data."
        ),
    )

    @property
    def registry_snapshot_ref(self) -> RegistrySnapshotRef:
        """Return the one canonical coordinate represented by this envelope."""
        observation = self.observation
        return RegistrySnapshotRef(
            modelo=observation.modelo,
            revision_id=self.stamped_revision_id,
            modelo_year=observation.filing_year,
            period=observation.period,
        )

    m303_compensation_basis: M303CompensationBasisValue | None = Field(
        default=None,
        description=(
            "Disposition-aware carry derivation basis after canonical Modelo "
            "303 ingress has made available compensation explicit."
        ),
    )
    override: ObservationOverride | None = Field(
        default=None,
        description="Audit of the operator override this local envelope records, when it is one.",
    )

    @field_validator("source_kind", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_source_kind(cls, value: object) -> ObservationSourceKind:
        """Parse encrypted JSON provenance into the closed source taxonomy."""
        return ObservationSourceKind(value)

    @property
    def is_pending_local(self) -> bool:
        """Return whether this envelope belongs to the pending-local layer."""
        return not self.source_kind.is_official_aeat

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_override_on_local_layer(self) -> ObservationEnvelopePayload:
        """Keep operator overrides out of official AEAT evidence."""
        if self.override is not None and self.source_kind.is_official_aeat:
            raise ValueError("an official AEAT observation cannot carry an operator override")
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_canonical_m303_shape(self, info: ValidationInfo) -> ObservationEnvelopePayload:
        """Reject persisted M303 envelopes that predate canonical carry ingress."""
        if str(self.observation.modelo) != "303":
            return self
        ingress_candidate = False
        if isinstance(info.context, Mapping):
            context = cast(Mapping[str, object], info.context)
            ingress_candidate = context.get("canonical_m303_ingress_candidate") is True
        if ingress_candidate:
            return self
        if self.result_disposition is None or self.m303_compensation_basis is None:
            raise RegistrySnapshotError(
                "Modelo 303 observation requires canonical result disposition and compensation basis"
            )
        return self


class ObservationLayers(BaseModel):
    """Both stored observation layers of one ``(modelo, filing_year, period, member)`` coordinate.

    ``official`` holds evidence observed from AEAT. ``pending_local`` holds a
    local filing or an operator figure that AEAT has not confirmed. Readers
    that want one answer use :attr:`effective`; the pending layer keeps its
    non-official ``source_kind``, so filing-grade gates still refuse it.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1)
    filing_year: int
    period: str = Field(min_length=1)
    member_nif: str | None = None
    official: ObservationEnvelopePayload | None = None
    pending_local: ObservationEnvelopePayload | None = None

    @property
    def effective(self) -> ObservationEnvelopePayload | None:
        """Return the pending-local envelope when present, otherwise the official one."""
        return self.pending_local if self.pending_local is not None else self.official

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_layer_membership(self) -> ObservationLayers:
        if self.official is not None and self.official.is_pending_local:
            raise ValueError("the official observation layer only holds AEAT evidence")
        if self.pending_local is not None and not self.pending_local.is_pending_local:
            raise ValueError("the pending-local observation layer cannot hold AEAT evidence")
        coordinate = (self.modelo, self.filing_year, self.period, self.member_nif)
        for layer in (self.official, self.pending_local):
            if layer is None:
                continue
            observation = layer.observation
            layer_coordinate = (str(observation.modelo), observation.filing_year, observation.period, layer.member_nif)
            if layer_coordinate != coordinate:
                raise ValueError(f"observation layer {layer_coordinate!r} does not belong to {coordinate!r}")
        return self


def require_observation_envelope_coordinates_current(
    payload: ObservationEnvelopePayload,
    *,
    operation: PinnedAuthorityOperation,
) -> ObservationEnvelopePayload:
    """Return a persisted observation only when its producing coordinate re-confirms."""
    outcome = revision_carry_outcome(payload.registry_snapshot_ref, operation=operation)
    if outcome.refused:
        snapshot_ref = payload.registry_snapshot_ref
        raise RegistrySnapshotError(
            "persisted observation registry coordinate cannot be re-confirmed: "
            f"{snapshot_ref.modelo}/{snapshot_ref.modelo_year}/{snapshot_ref.period}/"
            f"{snapshot_ref.revision_id}: {outcome.detail}"
        )
    return payload


class IvaWalletDecisionEnvelopePayload(BaseModel):
    """Serialisable wrapper for an IVA wallet reconciliation decision."""

    model_config = STRICT_FROZEN_CONFIG

    decision: IvaCompensationReconciliationDecision


def decision_payload_digest(decision: IvaCompensationReconciliationDecision) -> str:
    """Return the stable digest used to identify a reconciliation decision."""
    return sha256_hex(decision.model_dump_json().encode(UTF_8_ENCODING))


def require_observation_period(period: Period) -> Period:
    """Refuse a non-period value before it enters a persisted observation key."""
    # Deliberate runtime guard: annotations are not enforced at call time and this
    # value composes a persisted observation key, so a wrong type would surface as
    # an unreadable record rather than a refusal here.
    if not isinstance(period, Period):
        raise ObservationKeyError(
            translated_message="application.calculations.observations.errors.period_type_invalid",
            context={"observed_type": type(period).__name__},
        )
    return period


def _validate_repository_component(token: str, *, context: str) -> str:
    """Validate a key component without coupling application code to storage paths."""
    if not token:
        raise ObservationKeyError(
            f"{context} must be non-empty",
            context={"path_context": context, "violation": "empty_repository_id"},
        )
    if "/" in token or "\\" in token:
        raise ObservationKeyError(
            f"{context} must not contain path separators",
            context={"path_context": context, "violation": "repository_id_separator"},
        )
    if token in {".", ".."} or token.startswith("."):
        raise ObservationKeyError(
            f"{context} must not be a relative-path token",
            context={"path_context": context, "violation": "repository_id_dot_token"},
        )
    return token


def observation_key_for_token(modelo: str, filing_year: int, period_token: str) -> str:
    """Stable repository key for a modelo/year/raw registry-period token triple.

    Censo modelos can declare non-date registry tokens such as ``alta`` or
    ``modificacion`` that are not valid :class:`Period` codes. The encrypted
    observation store still keys them by the same logical triple.
    """
    _validate_repository_component(modelo, context="modelo")
    _validate_repository_component(period_token, context="period")
    if not 2000 <= filing_year <= 2099:
        raise ObservationKeyError(
            translated_message="application.calculations.observations.errors.filing_year_out_of_range",
            context={"filing_year": filing_year, "minimum": 2000, "maximum": 2099},
        )
    return f"{modelo}:{filing_year}:{period_token}"


def observation_key(modelo: str, period: Period) -> str:
    """Stable repository key for a ``(modelo, Period)`` pair.

    Validated through :func:`~adapters.persistence.storage.path_safety.safe_repository_id`
    so each component is constrained to the
    :class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
    id contract before composition.
    """
    filing_period = require_observation_period(period)
    return observation_key_for_token(modelo, filing_period.filing_year, filing_period.registry_token)


def member_observation_key_for_token(
    modelo: str,
    filing_year: int,
    period_token: str,
    member_nif: str | None,
) -> str:
    """Storage key for an observation keyed by a raw registry period token."""
    base = observation_key_for_token(modelo, filing_year, period_token)
    if member_nif is None:
        return base
    member_token = tax_id_identity_token(member_nif)
    if not member_token:
        raise ObservationKeyError(
            translated_message="application.calculations.observations.errors.member_nif_blank",
            context={"field": "member_nif"},
        )
    return f"{base}:{sha256_hex(member_token.encode(UTF_8_ENCODING))}"


def member_observation_key(modelo: str, period: Period, member_nif: str | None) -> str:
    """Storage key for an observation, widened by a grupo member NIF when present.

    When ``member_nif`` is ``None`` the key is the single-filer
    ``observation_key`` unchanged, so every existing consumer (the default
    previous_filing path, the multi-year resolver) keys identically. When set,
    a member segment is appended so two members' filings for the same
    ``(modelo, filing_year, period)`` persist as distinct rows — the cross-member
    fan-in the 353<-322 ``per_grupo_member`` aggregation enumerates and sums.

    That segment is the sha256 of the member's
    :func:`~core.identity.tax_id.tax_id_identity_token`, the same normalise-then-digest
    step every other identifier-bearing object key in the registry takes. The
    normalisation is the load-bearing half: appending the declared value
    verbatim made two spellings of ONE member address two rows, so a member
    whose identifier arrived lower-cased in one capture and space-padded in the
    next was counted twice by the very fan-in this widening exists to serve.
    The digest is the hygiene half -- it keeps a real identifier out of the
    natural-key surface, which is addressing metadata rather than encrypted
    payload.
    """
    filing_period = require_observation_period(period)
    return member_observation_key_for_token(
        modelo,
        filing_period.filing_year,
        filing_period.registry_token,
        member_nif,
    )


def iva_wallet_decision_key(taxpayer_nif: str, target_period: Period) -> str:
    """Opaque latest-decision key for one taxpayer and Modelo 303 target period.

    Secure-object payloads are encrypted, but object keys are storage metadata.
    Hash the taxpayer/period tuple so the repository does not expose NIF/NIE
    values in cleartext database rows.
    """
    filing_period = require_observation_period(target_period)
    target_year = filing_period.filing_year
    target_period_token = filing_period.registry_token
    taxpayer_token = tax_id_identity_token(taxpayer_nif)
    if not taxpayer_token:
        raise ObservationKeyError(
            translated_message="application.calculations.observations.errors.taxpayer_nif_blank",
            context={"field": "taxpayer_nif"},
        )
    _validate_repository_component(target_period_token, context="target_period")
    if not 2000 <= target_year <= 2099:
        raise ObservationKeyError(
            translated_message="application.calculations.observations.errors.iva_wallet_target_year_out_of_range",
            context={"target_year": target_year, "minimum": 2000, "maximum": 2099},
        )
    digest = sha256_hex(
        "\x1f".join((taxpayer_token, str(target_year), target_period_token)).encode(UTF_8_ENCODING),
    )
    return f"iva-wallet-decision:{digest}"


def iva_wallet_decision_event_key(decision: IvaCompensationReconciliationDecision) -> str:
    """Opaque immutable event key for one persisted reconciliation decision."""
    taxpayer_token = tax_id_identity_token(decision.taxpayer_nif)
    if not taxpayer_token:
        raise ObservationKeyError(
            translated_message="application.calculations.observations.errors.decision_taxpayer_nif_blank",
            context={"field": "decision.taxpayer_nif"},
        )
    digest = sha256_hex(
        "\x1f".join(
            (
                taxpayer_token,
                str(decision.target_year),
                decision.target_period.registry_token,
                decision.decided_at.isoformat(),
                decision.wallet_captured_at.isoformat() if decision.wallet_captured_at is not None else "",
                decision_payload_digest(decision),
            ),
        ).encode(UTF_8_ENCODING),
    )
    return f"iva-wallet-decision-event:{digest}"


def validate_observation_casilla_ids(
    observation: RegistryModeloObservation,
    *,
    operation: PinnedAuthorityOperation,
    stamped_revision_id: str | None = None,
) -> str:
    """Validate all observed and operand casillas against the selected revision.

    The revision is chosen by law from the observation's coordinates. Only when
    those coordinates alone are ambiguous -- a filing year split between editions
    at a dated boundary, which an observation carries no date to resolve -- does
    ``stamped_revision_id`` decide, and only among the law's own candidates.
    """
    observed_casilla_ids = frozenset(observation.casilla_values)
    operand_casilla_refs = frozenset(
        operand_ref for item in observation.observations for operand_ref in item.operand_casilla_refs
    )
    referenced_casilla_ids = observed_casilla_ids | operand_casilla_refs
    try:
        try:
            revision = operation.revision_for_context(
                observation.modelo,
                filing_year=observation.filing_year,
                period=observation.period,
            )
        except AmbiguousRevisionSelectionError as ambiguity:
            if stamped_revision_id is None or stamped_revision_id not in ambiguity.candidate_ids:
                raise
            revision = operation.revision_for_context(
                observation.modelo,
                filing_year=observation.filing_year,
                period=observation.period,
                revision_id=stamped_revision_id,
            )
    except RegistrySnapshotError as exc:
        raise ObservationCasillaReferenceError(
            translated_message="application.calculations.observations.errors.registry_snapshot_missing",
            context={
                "modelo": observation.modelo,
                "filing_year": observation.filing_year,
                "period": observation.period,
            },
        ) from exc

    invalid = undeclared_casilla_ids(revision, referenced_casilla_ids) if referenced_casilla_ids else ()
    if not invalid:
        return str(revision.id)
    raise ObservationCasillaReferenceError(
        translated_message="application.calculations.observations.errors.casilla_ids_noncanonical",
        context={
            "modelo": observation.modelo,
            "filing_year": observation.filing_year,
            "period": observation.period,
            "revision_id": revision.id,
            "casilla_ids": invalid,
            "observation_casilla_ids": undeclared_casilla_ids(revision, observed_casilla_ids),
            "operand_casilla_refs": undeclared_casilla_ids(revision, operand_casilla_refs),
        },
    )


@runtime_checkable
class CalculationObservationStorageProtocol(Protocol):
    """Application-facing storage capability for atomic observation writes."""

    def apply_batch(self, writes: tuple[SecureObjectWrite, ...]) -> None:
        """Commit prepared observation/history writes atomically."""
        ...

    @property
    def engine(self) -> object:
        """Expose only backend identity needed for same-store validation."""
        ...


@runtime_checkable
class CalculationObservationRepositoryProtocol(Protocol):
    """Application-owned read/write capability for filed observations."""

    def load_observation(self, modelo: str, period: Period) -> ObservationEnvelopePayload | None:
        """Load the effective observation of one single-filer coordinate."""
        ...

    def iter_modelo(self, modelo: str) -> Iterator[ObservationEnvelopePayload]:
        """Iterate the effective observation of every coordinate of one modelo."""
        ...

    def iter_records(self) -> Iterator[ObservationEnvelopePayload]:
        """Iterate the effective observation of every stored coordinate."""
        ...

    def prepare_observation_envelope(
        self,
        observation: RegistryModeloObservation,
        *,
        source_kind: ObservationSourceKind | str,
        stamped_revision_id: RevisionId,
        captured_at: datetime | None = None,
        member_nif: str | None = None,
        source_metadata: Mapping[str, str] | None = None,
        source_headers: tuple[ObservedHeaderFact, ...] = (),
        result_disposition: ResultDispositionProjection | None = None,
        prior_domiciliation_election: PriorDomiciliationElectionProjection | None = None,
        override: ObservationOverride | None = None,
    ) -> ObservationEnvelopePayload:
        """Validate and normalize one observation before persistence."""
        ...

    def load_observation_layers(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
    ) -> ObservationLayers:
        """Return both stored layers of one coordinate; absent layers are ``None``."""
        ...

    def save(self, payload: ObservationEnvelopePayload) -> None:
        """Persist one validated observation into the layer its source kind selects."""
        ...

    def promote_pending_local(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
        source_kind: ObservationSourceKind,
        source_metadata: Mapping[str, str],
        captured_at: datetime,
    ) -> tuple[SecureObjectWrite, ...]:
        """Prepare the writes that make the pending-local layer the official one.

        Used when AEAT confirms a pending local filing: the pending-local
        envelope's casilla values become the official layer under the official
        ``source_kind`` and ``source_metadata``, and the pending-local layer is
        removed. Removal is expressed as upserts so the writes join the
        caller's unit of work. Returns ``()`` when the coordinate has no
        pending-local layer.
        """
        ...

    def clear_pending_local(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
    ) -> tuple[SecureObjectWrite, ...]:
        """Prepare the writes that remove the pending-local layer of one coordinate.

        The official layer is left untouched. Removal is expressed as upserts
        so the writes join the caller's unit of work. Returns ``()`` when the
        coordinate has no pending-local layer.
        """
        ...

    def to_secure_object_write(self, payload: ObservationEnvelopePayload) -> SecureObjectWrite:
        """Prepare the write placing one observation into its layer, for an outer transaction."""
        ...

    @property
    def secure_object_repository(self) -> CalculationObservationStorageProtocol:
        """Return the storage capability used for atomic co-commit."""
        ...


@runtime_checkable
class IvaWalletDecisionRepositoryProtocol(Protocol):
    """Application-owned capability for IVA wallet decisions."""

    def load_decision(
        self,
        taxpayer_nif: str,
        target_period: Period,
    ) -> IvaCompensationReconciliationDecision | None:
        """Load the latest decision for one period."""
        ...

    def list_decisions(self) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """List latest decisions in deterministic order."""
        ...

    def load_decision_history(
        self,
        taxpayer_nif: str,
        target_period: Period,
    ) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """Load immutable decision history for one period."""
        ...

    def save_decision(self, decision: IvaCompensationReconciliationDecision) -> None:
        """Persist the decision and its immutable event atomically."""
        ...

    @property
    def secure_object_repository(self) -> CalculationObservationStorageProtocol:
        """Return the storage capability used by this decision port."""
        ...


@dataclass(frozen=True, slots=True)
class CalculationObservationPorts:
    """Required observation capabilities for one profile calculation context."""

    observation_repository: CalculationObservationRepositoryProtocol
    iva_wallet_decision_repository: IvaWalletDecisionRepositoryProtocol


__all__ = [
    "APP_FILING_SOURCE_KIND",
    "CalculationObservationPorts",
    "CalculationObservationRepositoryProtocol",
    "CalculationObservationStorageProtocol",
    "IvaWalletDecisionEnvelopePayload",
    "IvaWalletDecisionRepositoryProtocol",
    "ObservationEnvelopePayload",
    "ObservationLayers",
    "ObservationOverride",
    "ObservationSourceKind",
    "PriorDomiciliationElectionProjection",
    "ResultDispositionProjection",
    "decision_payload_digest",
    "is_official_aeat_observation_source",
    "iva_wallet_decision_event_key",
    "iva_wallet_decision_key",
    "member_observation_key",
    "member_observation_key_for_token",
    "observation_key",
    "observation_key_for_token",
    "require_decision_registry_coordinates_current",
    "require_observation_envelope_coordinates_current",
    "require_observation_period",
    "validate_observation_casilla_ids",
]
