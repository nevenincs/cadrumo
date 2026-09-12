"""Encrypted persistence adapters for calculation observations and IVA wallet decisions.

The application owns payloads, key derivation, validation, and capability
contracts. This module binds those contracts to encrypted secure-object storage.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel

from cadrumo.application.calculations.errors import (
    CalculationRefusalPrecondition,
    ObservationCasillaReferenceError,
    ObservationEvidenceDisplacementError,
    ObservationKeyError,
    calculation_no_recovery_verdict,
)
from cadrumo.application.calculations.m303_carry_ingress import normalize_m303_carry_observation_envelope
from cadrumo.application.calculations.observations_repository import (
    IvaWalletDecisionEnvelopePayload,
    ObservationEnvelopePayload,
    ObservationSourceKind,
    PriorDomiciliationElectionProjection,
    ResultDispositionProjection,
    decision_payload_digest,
    iva_wallet_decision_event_key,
    iva_wallet_decision_key,
    member_observation_key,
    member_observation_key_for_token,
    observation_key,
    require_decision_registry_coordinates_current,
    require_observation_period,
    validate_observation_casilla_ids,
)
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.identity.tax_id import same_tax_identifier
from cadrumo.core.observed_header_fact import ObservedHeaderFact
from cadrumo.core.period import Period
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ..storage.envelope.contract import Envelope
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.path_safety import safe_repository_id
from ..storage.secure_object_namespaces import (
    CALCULATION_OBSERVATIONS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE,
)

class CalculationObservationRepository(SecureBoundRepository[ObservationEnvelopePayload]):
    """Repository over encrypted SQL-backed past-filing observations.

    Stores :class:`RegistryModeloObservation` rows for
    :func:`~._binding_prefill.resolve_bindings_from_local_store`,
    :func:`~.relation_prefill.resolve_relations_from_local_store`, and
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
        filing_period = require_observation_period(period)
        return self.load(observation_key(modelo, filing_period))

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

        ``stamped_revision_id`` is the required registry revision id the source
        filing resolved to at capture time. There is no inferred or legacy
        fallback: every producer must pass its authoritative coordinate, which
        this boundary checks against the law-determined revision.

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

        Every Modelo 303 envelope crosses the canonical disposition-aware
        normalization ingress. Incomplete or conflicting evidence is refused;
        there is no generic unnormalized storage shape. Callers that co-emit
        this envelope with a history projection use
        ``to_secure_object_write`` and the storage backend's batch boundary
        so the pair cannot half-persist.
        """
        law_revision_id = validate_observation_casilla_ids(observation)
        if stamped_revision_id != law_revision_id:
            raise RegistrySnapshotError(
                "observation stamp differs from the law-determined registry revision: "
                f"stamped={stamped_revision_id!r}, selected={law_revision_id!r}"
            )
        resolved_source_kind = ObservationSourceKind(source_kind)
        when = captured_at if captured_at is not None else now()
        payload = ObservationEnvelopePayload.model_validate(
            {
                "observation": observation,
                "captured_at": when,
                "source_kind": resolved_source_kind,
                "member_nif": member_nif,
                "stamped_revision_id": stamped_revision_id,
                "source_metadata": dict(source_metadata or {}),
                "source_headers": source_headers,
                "result_disposition": result_disposition,
                "prior_domiciliation_election": prior_domiciliation_election,
            },
            context={"canonical_m303_ingress_candidate": True},
        )
        # Keep the serialisable envelope model independent from the application
        # policy that normalizes it, while making this sole write door canonical.
        payload = normalize_m303_carry_observation_envelope(payload)
        payload = ObservationEnvelopePayload.model_validate(payload.model_dump())
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
    :class:`~.iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`.

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
        require_decision_registry_coordinates_current(decision)
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
        if payload is None:
            return None
        require_decision_registry_coordinates_current(payload.decision)
        return payload.decision

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
        decisions = tuple(
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
        for decision in decisions:
            require_decision_registry_coordinates_current(decision)
        return decisions

    def load_decision_history(
        self,
        taxpayer_nif: str,
        target_period: Period,
    ) -> tuple[IvaCompensationReconciliationDecision, ...]:
        """Return decision history for one taxpayer and target period.

        Returns an immutable tuple of :class:`IvaCompensationReconciliationDecision`.
        """
        filing_period = require_observation_period(target_period)
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
                require_decision_registry_coordinates_current(decision)
                decisions.append(decision)
        return tuple(sorted(decisions, key=lambda item: (item.decided_at, item.wallet_captured_at or item.decided_at)))



__all__ = [
    "CalculationObservationRepository",
    "IvaWalletDecisionRepository",
]
