"""Encrypted persistence for past-filing casilla observations.

Stores :class:`~domain.calculations.registry.RegistryModeloObservation`
records — ``(modelo, filing_year, period, casilla_values)`` — as encrypted audit
envelopes in the
:class:`~adapters.persistence.storage.SecureObjectRepository`.
Past-filing value rows are bound to
:data:`~adapters.persistence.storage.CALCULATION_OBSERVATIONS_NAMESPACE`;
IVA wallet decisions are split between the latest-state
:data:`~adapters.persistence.storage.IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE`
and immutable
:data:`~adapters.persistence.storage.IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE`
namespaces.
The records are the substrate read by
:class:`~._multi_year.PreviousFilingSourceResolver` and
:class:`~._relation_prefill.RelationPrefillSourceResolver` so annual modelos
can roll up prior quarterlies, IVA prorrata can compute its four-year backward
mean, IS BIN carryforward can replay prior-year bases imponibles negativas, and
IVA regularización inversiones can apply its 5/10 year straight-line schedule.

Producers are out of scope for this module: the modelo filing flow
will write here when an operator successfully files via the app,
and the live-AEAT capture path will write here when justificantes
are parsed. This module exposes only the typed read/write surface.

Sensitivity is :class:`~adapters.persistence.storage.SensitivityClass`
``AUDIT`` — these records reconstruct exactly what was filed and so are
identity-bearing tax substrate. They are stored encrypted at rest through an
:class:`~adapters.persistence.storage.Envelope`-wrapped repository.

The store is value-centric. Clean-state proof still has to join these rows with
filing records, verification reports, and justificante evidence through
:func:`~.cross_period_clean_state.evaluate_cross_period_clean_state`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime
from enum import StrEnum
from typing import ClassVar, Literal, override

from pydantic import BaseModel, Field, field_validator, model_validator

from ...adapters.persistence.storage import (
    CALCULATION_OBSERVATIONS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE,
    Envelope,
    SecureBoundRepository,
    SensitivityClass,
    safe_repository_id,
)
from ...core import (
    STRICT_FROZEN_CONFIG,
    ObservedHeaderFact,
    Period,
    PriorDomiciliationElection,
    ResultDisposition,
    SecureObjectWrite,
)
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.identity import FilingRecordId, same_tax_identifier, tax_id_identity_token
from ...core.resources import bundled_path
from ...core.time import UtcInstant, now
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.calculations.registry.casilla_membership import undeclared_casilla_ids
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.temporal import select_revision
from ...domain.iva_compensation import IvaCompensationReconciliationDecision
from .errors import (
    CalculationRefusalPrecondition,
    ObservationCasillaReferenceError,
    ObservationEvidenceDisplacementError,
    ObservationKeyError,
    calculation_no_recovery_verdict,
)


class ObservationSourceKind(StrEnum):
    """Origin of a persisted calculation observation.

    This classifies the observation provenance before a filing's separate
    :class:`~domain.modelos.ExternalEvidenceKind` is materialised. Only the
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
    def _parse_election(cls, value: object) -> PriorDomiciliationElection:
        return PriorDomiciliationElection(value)

    @model_validator(mode="after")
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


class ObservationEnvelopePayload(BaseModel):
    """Canonical public persistence payload for filed observations.

    This strict, frozen model is returned by
    :class:`CalculationObservationRepository` reads and iteration. It keeps the
    :class:`RegistryModeloObservation` calculation evidence separate from the
    application capture provenance: ``captured_at``, constrained
    ``source_kind``, optional ``member_nif``, required
    ``stamped_revision_id``, and source-specific ``source_metadata``. The model
    does not encrypt that metadata; the secure repository envelope does.

    ``captured_at`` is the canonical :data:`~core.time.UtcInstant`. A bare
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
    m303_compensation_basis: Literal["generated", "resultado", "refunded"] | None = Field(
        default=None,
        description=(
            "Disposition-aware carry derivation basis after canonical Modelo "
            "303 ingress has made available compensation explicit."
        ),
    )

    @field_validator("source_kind", mode="before")
    @classmethod
    def _parse_source_kind(cls, value: object) -> ObservationSourceKind:
        """Parse encrypted JSON provenance into the closed source taxonomy."""
        return ObservationSourceKind(value)


class IvaWalletDecisionEnvelopePayload(BaseModel):
    """Serialisable wrapper for an IVA wallet reconciliation decision."""

    model_config = STRICT_FROZEN_CONFIG

    decision: IvaCompensationReconciliationDecision


def _decision_payload_digest(decision: IvaCompensationReconciliationDecision) -> str:
    return sha256_hex(decision.model_dump_json().encode(UTF_8_ENCODING))


def _require_observation_period(period: Period) -> Period:
    # Deliberate runtime guard: annotations are not enforced at call time and this
    # value composes a persisted observation key, so a wrong type would surface as
    # an unreadable record rather than a refusal here.
    if not isinstance(period, Period):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ObservationKeyError(
            translated_message="application.calculations.observations.errors.period_type_invalid",
            context={"observed_type": type(period).__name__},
        )
    return period


def observation_key_for_token(modelo: str, filing_year: int, period_token: str) -> str:
    """Stable repository key for a modelo/year/raw registry-period token triple.

    Censo modelos can declare non-date registry tokens such as ``alta`` or
    ``modificacion`` that are not valid :class:`Period` codes. The encrypted
    observation store still keys them by the same logical triple.
    """
    safe_repository_id(modelo, context="modelo")
    safe_repository_id(period_token, context="period")
    if not 2000 <= filing_year <= 2099:
        raise ObservationKeyError(
            translated_message="application.calculations.observations.errors.filing_year_out_of_range",
            context={"filing_year": filing_year, "minimum": 2000, "maximum": 2099},
        )
    return f"{modelo}:{filing_year}:{period_token}"


def observation_key(modelo: str, period: Period) -> str:
    """Stable repository key for a ``(modelo, Period)`` pair.

    Validated through :func:`~adapters.persistence.storage.safe_repository_id`
    so each component is constrained to the
    :class:`~adapters.persistence.storage.SecureObjectRepository`
    id contract before composition.
    """
    filing_period = _require_observation_period(period)
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
    :func:`~core.identity.tax_id_identity_token`, the same normalise-then-digest
    step every other identifier-bearing object key in the registry takes. The
    normalisation is the load-bearing half: appending the declared value
    verbatim made two spellings of ONE member address two rows, so a member
    whose identifier arrived lower-cased in one capture and space-padded in the
    next was counted twice by the very fan-in this widening exists to serve.
    The digest is the hygiene half -- it keeps a real identifier out of the
    natural-key surface, which is addressing metadata rather than encrypted
    payload.
    """
    filing_period = _require_observation_period(period)
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
    filing_period = _require_observation_period(target_period)
    target_year = filing_period.filing_year
    target_period_token = filing_period.registry_token
    taxpayer_token = tax_id_identity_token(taxpayer_nif)
    if not taxpayer_token:
        raise ObservationKeyError(
            translated_message="application.calculations.observations.errors.taxpayer_nif_blank",
            context={"field": "taxpayer_nif"},
        )
    safe_repository_id(target_period_token, context="target_period")
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
                _decision_payload_digest(decision),
            ),
        ).encode(UTF_8_ENCODING),
    )
    return f"iva-wallet-decision-event:{digest}"


def _validate_observation_casilla_ids(observation: RegistryModeloObservation) -> str:
    observed_casilla_ids = frozenset(observation.casilla_values)
    operand_casilla_refs = frozenset(
        operand_ref for item in observation.observations for operand_ref in item.operand_casilla_refs
    )
    referenced_casilla_ids = observed_casilla_ids | operand_casilla_refs
    try:
        modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
        modelo = next((candidate for candidate in modelos if candidate.id == observation.modelo), None)
        if modelo is None:
            raise RegistrySnapshotError(f"modelo {observation.modelo!r} is not present in the calculation registry")
        revision = select_revision(
            modelo,
            filing_year=observation.filing_year,
            period=observation.period,
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


class CalculationObservationRepository(SecureBoundRepository[ObservationEnvelopePayload]):
    """Repository over encrypted SQL-backed past-filing observations.

    Stores :class:`RegistryModeloObservation` rows for
    :func:`~._binding_prefill.resolve_bindings_from_local_store`,
    :func:`~._relation_prefill.resolve_relations_from_local_store`, and
    :func:`~.cross_period_clean_state.evaluate_cross_period_clean_state`.
    It owns encrypted value history only; filing-grade source proof is assembled
    by the clean-state service from this repository plus filing, verification,
    and justificante repositories.

    The repository binds each
    :class:`~adapters.persistence.storage.Envelope` payload to
    :data:`~adapters.persistence.storage.CALCULATION_OBSERVATIONS_NAMESPACE`
    through
    :class:`~adapters.persistence.storage.SecureBoundRepository`.
    """

    namespace: ClassVar[str] = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = CALCULATION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = CALCULATION_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = ObservationEnvelopePayload

    @override
    def extract_identifier(self, payload: ObservationEnvelopePayload) -> str:
        observation = payload.observation
        period = observation.filing_period
        if period is None:
            return member_observation_key_for_token(
                observation.modelo,
                observation.filing_year,
                observation.period,
                payload.member_nif,
            )
        return member_observation_key(
            observation.modelo,
            period,
            payload.member_nif,
        )

    def load_observation(
        self,
        modelo: str,
        period: Period,
    ) -> ObservationEnvelopePayload | None:
        """Return the persisted observation for one (modelo, year, period token) or None."""
        filing_period = _require_observation_period(period)
        return self.load(observation_key(modelo, filing_period))

    def prepare_observation_envelope(
        self,
        observation: RegistryModeloObservation,
        *,
        source_kind: ObservationSourceKind | str,
        captured_at: datetime | None = None,
        member_nif: str | None = None,
        stamped_revision_id: RevisionId | None = None,
        source_metadata: Mapping[str, str] | None = None,
        source_headers: tuple[ObservedHeaderFact, ...] = (),
        result_disposition: ResultDispositionProjection | None = None,
        prior_domiciliation_election: PriorDomiciliationElectionProjection | None = None,
        normalize_m303_carry: bool = False,
        replace_official_evidence: bool = False,
    ) -> ObservationEnvelopePayload:
        """Build one validated observation envelope without writing it.

        Every writer traverses this method, so it is where the official-evidence
        guard lives -- see :meth:`_refuse_official_evidence_displacement`, which
        also states which store that guard covers and which sibling observation
        repositories it does not.

        ``member_nif`` is an optional grupo-de-entidades member NIF. When
        supplied, the storage identifier is widened (see
        :func:`member_observation_key`) so distinct members' filings for the
        same (modelo, filing_year, period) persist as separate rows instead of
        overwriting — the cross-member fan-in the 353<-322 ``per_grupo_member``
        aggregation enumerates. When ``None`` the single-filer key is unchanged.

        ``stamped_revision_id`` is the registry revision id the source filing
        resolved to at capture time. Producers that hold a
        :class:`~domain.calculations.registry.RegistrySnapshot` MUST pass
        ``snapshot.revision.id`` here. If omitted, the repository resolves the
        law-determined revision from the observation's ``(modelo, filing_year,
        period)`` before persisting; the persisted payload always carries a
        required, non-null stamp.

        ``source_metadata`` is source-specific encrypted provenance. It is never
        part of repository keys and must only contain data that belongs inside
        the AUDIT-class secure payload; live AEAT captures use it for register
        status, expediente identity, and authenticated taxpayer/member identity
        consumed by the cross-period clean-state proof.

        ``source_headers`` carries the filed fichero's typed diseño header facts.
        It is a SEPARATE parameter rather than more ``source_metadata`` keys
        because that mapping is assembled from a fixed key set by its producer,
        so a fact not named there never reaches storage -- which is exactly how
        the header projection was landing at capture and vanishing before
        persistence.

        ``normalize_m303_carry`` is the explicit canonical ingress used by the
        official filed-capture and local-filing routes. It refuses incomplete or
        conflicting declaration-disposition evidence before persisting a
        carry-capable Modelo 303 row. Generic observation storage intentionally
        remains readable for legacy evidence and unrelated consumers. Callers
        that co-emit this envelope with a history projection use
        ``to_secure_object_write`` and the storage backend's batch boundary
        so the pair cannot half-persist.
        """
        law_revision_id = _validate_observation_casilla_ids(observation)
        resolved_source_kind = ObservationSourceKind(source_kind)
        when = captured_at if captured_at is not None else now()
        payload = ObservationEnvelopePayload(
            observation=observation,
            captured_at=when,
            source_kind=resolved_source_kind,
            member_nif=member_nif,
            stamped_revision_id=law_revision_id if stamped_revision_id is None else stamped_revision_id,
            source_metadata=dict(source_metadata or {}),
            source_headers=source_headers,
            result_disposition=result_disposition,
            prior_domiciliation_election=prior_domiciliation_election,
        )
        if normalize_m303_carry:
            # Keep the serialisable envelope model independent from the
            # application policy that normalizes it.
            from ._m303_carry_ingress import normalize_m303_carry_observation_envelope

            payload = normalize_m303_carry_observation_envelope(payload)
        # Checked HERE, and here only, because every writer prepares its
        # envelope through this method. The operator verb persists the returned
        # payload through the inherited repository save; the live capture and
        # local filing flows turn it into a prepared write batch so the
        # observation and its IVA history land in one transaction. This runs
        # before any write is prepared, so a refusal never has to reason about
        # staged work inside a transaction.
        if not replace_official_evidence:
            self._refuse_official_evidence_displacement(payload)
        return payload

    def _refuse_official_evidence_displacement(self, payload: ObservationEnvelopePayload) -> None:
        """Refuse a non-official write onto a slot already holding AEAT evidence.

        Compares MEMBERSHIP only -- existing is official, incoming is not. The
        provenance taxonomy has no ordering, so a general "downgrade" rule would
        invent an axis the registry does not publish; official-to-official and
        anything-to-non-official stay permitted.

        The occupancy read uses :meth:`extract_identifier`, the same derivation
        the write uses, so the slot inspected is the slot that would be written
        rather than a re-derived approximation of it.

        WHICH STORE THIS COVERS, stated here because the guard's name does not
        say it and a reader will otherwise assume every observation write is
        protected. It covers THIS repository only -- the ``(modelo, filing_year,
        period[, member])`` slot. Two sibling repositories persist observations
        at a finer key with their own save and their own set-replace path:
        ``application/aggregation/_retencion_observations_repository.py`` keyed
        by NIF and scheme, and ``_percepciones_observations_repository.py`` keyed
        by NIF, clave and subclave. They are a different store, not writers that
        slipped past this check, and nothing here refuses on their behalf.
        """
        if payload.source_kind.is_official_aeat:
            return
        existing = self.load(self.extract_identifier(payload))
        if existing is None or not existing.source_kind.is_official_aeat:
            return
        observation = payload.observation
        context = {
            "modelo": observation.modelo,
            "filing_year": str(observation.filing_year),
            "period": str(observation.period),
            "existing_source_kind": existing.source_kind.value,
            "incoming_source_kind": payload.source_kind.value,
        }
        # Displacing captured AEAT evidence is unrecoverable through any path
        # this repository exposes, so the refusal states that in typed form
        # rather than leaving a boundary to project a retry of the same write.
        verdict = calculation_no_recovery_verdict(
            CalculationRefusalPrecondition.OFFICIAL_EVIDENCE_PRESERVED,
            facts={
                "modelo": str(observation.modelo),
                "filing_year": str(observation.filing_year),
                "period": str(observation.period),
                "existing_source_kind": existing.source_kind.value,
                "incoming_source_kind": payload.source_kind.value,
            },
        )
        # Two raises with LITERAL keys rather than one raise selecting a key by
        # expression: the locale scaffold discovers keys by reading the literal
        # argument, so a computed key is invisible to it and the parity gate
        # would never learn the string exists. The duplication is the price of
        # the key being discoverable.
        if payload.source_kind is ObservationSourceKind.APP_FILING:
            raise ObservationEvidenceDisplacementError(
                translated_message="application.calculations.errors.observation_displaces_official_evidence_app_filing",
                context=context,
                precondition_verdict=verdict,
            )
        raise ObservationEvidenceDisplacementError(
            translated_message="application.calculations.errors.observation_displaces_official_evidence_manual",
            context=context,
            precondition_verdict=verdict,
        )

    def iter_modelo(self, modelo: str) -> Iterator[ObservationEnvelopePayload]:
        """Yield every persisted observation for ``modelo`` in unspecified order.

        Used by grouped previous-filing and clean-state readers to enumerate all
        known source rows for a modelo, including member-widened keys.

        The base scan verifies each row's key before yielding it, which this
        filter depends on: the ``modelo`` test below
        reads the payload's own coordinates, so a row filed under another
        ``(modelo, filing_year, period, member)`` key would enter the window it
        describes rather than the one it is stored in, and carry-forward and
        aggregation readers would fold a foreign period's figures into this
        modelo. The verified scan recomputes the natural key from each payload
        and refuses a mismatch instead of yielding it.
        """
        safe_repository_id(modelo, context="modelo")
        for payload in self.iter_records():
            if payload.observation.modelo == modelo:
                yield payload


class IvaWalletDecisionRepository(SecureBoundRepository[IvaWalletDecisionEnvelopePayload]):
    """Repository over encrypted SQL-backed IVA wallet reconciliation decisions.

    Holds one latest decision per ``(taxpayer_nif, target_year, target_period)``
    triple for calculation lookup, and also writes every distinct decision to
    an immutable audit-event namespace. Decisions are AUDIT-class — they record
    the resolved gap between a taxpayer's local IVA compensation recurrence and
    the live AEAT wallet, which downstream calculation chains consult through
    :class:`~._iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`.

    Latest-state rows use
    :data:`~adapters.persistence.storage.IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE`;
    immutable audit events use
    :data:`~adapters.persistence.storage.IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE`.
    Both store :class:`IvaCompensationReconciliationDecision` payloads in
    :class:`~adapters.persistence.storage.Envelope` records through
    :class:`~adapters.persistence.storage.SecureBoundRepository`.
    """

    namespace: ClassVar[str] = IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.namespace
    history_namespace: ClassVar[str] = IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE.schema_version
    history_schema_version: ClassVar[int] = IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = IvaWalletDecisionEnvelopePayload

    @override
    def extract_identifier(self, payload: IvaWalletDecisionEnvelopePayload) -> str:
        decision = payload.decision
        return iva_wallet_decision_key(decision.taxpayer_nif, decision.target_period)

    def save_decision(self, decision: IvaCompensationReconciliationDecision) -> None:
        """Persist ``decision`` to latest lookup and immutable audit history.

        Both rows commit in ONE transaction. Writing the latest state and then
        appending the audit event as a second, independent write left a window
        in which a failure between them persisted a decision the immutable
        history has no record of -- the history exists precisely to explain how
        the latest state was reached, so a latest row with no event is a
        decision that cannot be audited. The substrate already owns the
        transaction boundary; this composes both writes into it.
        """
        payload = IvaWalletDecisionEnvelopePayload(decision=decision)
        latest_write = self.to_secure_object_write(payload)
        history_envelope = Envelope[IvaWalletDecisionEnvelopePayload](
            schema_version=self.history_schema_version,
            written_at=latest_write.written_at,
            classification=self.sensitivity,
            payload=payload,
        )
        history_write = SecureObjectWrite(
            namespace=self.history_namespace,
            object_key=iva_wallet_decision_event_key(decision),
            classification=self.sensitivity,
            schema_version=self.history_schema_version,
            written_at=history_envelope.written_at,
            payload=history_envelope.model_dump_json().encode(UTF_8_ENCODING),
        )
        self._objects.apply_batch((latest_write, history_write))

    def load_decision(
        self,
        taxpayer_nif: str,
        target_period: Period,
    ) -> IvaCompensationReconciliationDecision | None:
        """Return the latest persisted :class:`IvaCompensationReconciliationDecision` for the given period."""
        payload = super().load(iva_wallet_decision_key(taxpayer_nif, target_period))
        return payload.decision if payload is not None else None

    def list_decisions(self) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """Return the latest persisted IVA wallet decisions in target-period order.

        Each element is an :class:`IvaCompensationReconciliationDecision` sorted
        by ``(target_year, target_period, taxpayer_nif, decided_at)``.

        The base scan verifies each row's key before yielding it, which this
        listing depends on. The latest-decision key is a
        hash of the taxpayer and target period, so a decision filed under
        another taxpayer's or period's key is invisible to any check that reads
        the decrypted decision alone; it would then sort into this list as that
        other subject's latest decision and enter reconciliation. The verified
        scan recomputes the hashed key from each payload and refuses a
        mismatch.
        """
        return tuple(
            sorted(
                (payload.decision for payload in self.iter_records()),
                key=lambda decision: (
                    decision.target_year,
                    decision.target_period.registry_token,
                    decision.taxpayer_nif,
                    decision.decided_at,
                ),
            ),
        )

    def load_decision_history(
        self,
        taxpayer_nif: str,
        target_period: Period,
    ) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """Return decision history for one taxpayer and target period.

        Returns an immutable tuple of :class:`IvaCompensationReconciliationDecision`.
        """
        filing_period = _require_observation_period(target_period)
        decisions: list[IvaCompensationReconciliationDecision] = []
        for record in self._objects.list_records(
            self.history_namespace,
            expected_class=self.sensitivity,
            max_supported_version=self.history_schema_version,
        ):
            envelope = Envelope[IvaWalletDecisionEnvelopePayload].model_validate_json(
                record.payload.decode(UTF_8_ENCODING),
            )
            decision = envelope.payload.decision
            if same_tax_identifier(decision.taxpayer_nif, taxpayer_nif) and decision.target_period == filing_period:
                decisions.append(decision)
        return tuple(sorted(decisions, key=lambda item: (item.decided_at, item.wallet_captured_at or item.decided_at)))


__all__ = [
    "CalculationObservationRepository",
    "IvaWalletDecisionRepository",
    "iva_wallet_decision_event_key",
    "iva_wallet_decision_key",
    "member_observation_key",
    "member_observation_key_for_token",
    "observation_key",
    "observation_key_for_token",
]
