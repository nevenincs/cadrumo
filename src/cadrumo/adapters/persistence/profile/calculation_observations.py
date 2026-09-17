"""Encrypted persistence adapters for calculation observations and IVA wallet decisions.

The application owns payloads, key derivation, validation, and capability
contracts. This module binds those contracts to encrypted secure-object storage.

Core types:
:class:`~cadrumo.core.classification.policies.SensitivityClass`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel, ValidationError

from cadrumo.application.calculations.m303_carry_ingress import normalize_m303_carry_observation_envelope
from cadrumo.application.calculations.observations_repository import (
    IvaWalletDecisionEnvelopePayload,
    ObservationEnvelopePayload,
    ObservationLayers,
    ObservationOverride,
    ObservationSourceKind,
    PriorDomiciliationElectionProjection,
    ResultDispositionProjection,
    iva_wallet_decision_event_key,
    iva_wallet_decision_key,
    member_observation_key,
    member_observation_key_for_token,
    observation_key,
    require_decision_registry_coordinates_current,
    require_observation_period,
    validate_observation_casilla_ids,
)
from cadrumo.application.persistence_errors import PersistenceDegradationError
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.config import Settings
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.identity.tax_id import same_tax_identifier
from cadrumo.core.observed_header_fact import ObservedHeaderFact
from cadrumo.core.period import Period
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision

from ..storage.envelope.contract import Envelope
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import StorageError
from ..storage.path_safety import safe_repository_id
from ..storage.secure_object_namespaces import (
    CALCULATION_OBSERVATIONS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE,
    IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE,
)
from ..storage.sql.secure_objects import SecureObjectRepository


def _translate_storage_failure[T](operation: str, callback: Callable[[], T]) -> T:
    """Translate known persistence failures at the application port boundary."""
    try:
        return callback()
    except PersistenceDegradationError:
        raise
    except (StorageError, OSError, ValidationError, UnicodeDecodeError) as exc:
        raise PersistenceDegradationError(operation) from exc


class _ObservationLayerStore(SecureBoundRepository[ObservationLayers]):
    """Encrypted rows holding both observation layers of one coordinate."""

    namespace: ClassVar[str] = CALCULATION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = CALCULATION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = CALCULATION_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = ObservationLayers

    @override
    def extract_identifier(self, payload: ObservationLayers) -> str:
        return member_observation_key_for_token(payload.modelo, payload.filing_year, payload.period, payload.member_nif)


def _layers_for(payload: ObservationEnvelopePayload) -> ObservationLayers:
    observation = payload.observation
    return ObservationLayers(
        modelo=str(observation.modelo),
        filing_year=observation.filing_year,
        period=observation.period,
        member_nif=payload.member_nif,
    )


class CalculationObservationRepository:
    """Repository over encrypted SQL-backed past-filing observations.

    Stores :class:`RegistryModeloObservation` rows for
    :func:`~._binding_prefill.resolve_bindings_from_local_store`,
    :func:`~.relation_prefill.resolve_relations_from_local_store`, and
    :func:`~.cross_period_clean_state.evaluate_cross_period_clean_state`.
    It owns encrypted value history only; filing-grade source proof is assembled
    by the clean-state service from this repository plus filing, verification,
    and justificante repositories.

    Each ``(modelo, filing_year, period[, member])`` coordinate is one row
    holding an :class:`ObservationLayers` payload: the official layer observed
    from AEAT and the pending-local layer written by local filings and operator
    figures. A write replaces only the layer its source kind selects, so a
    local figure never destroys captured AEAT evidence. Envelope reads return
    the effective layer, the pending-local one when present.

    Rows are bound to
    :data:`~adapters.persistence.storage.secure_object_namespaces.CALCULATION_OBSERVATIONS_NAMESPACE`
    through
    :class:`~adapters.persistence.storage.envelope.secure_bound_repository.SecureBoundRepository`.
    """

    namespace: ClassVar[str] = _ObservationLayerStore.namespace
    sensitivity: ClassVar[SensitivityClass] = _ObservationLayerStore.sensitivity
    schema_version: ClassVar[int] = _ObservationLayerStore.schema_version
    payload_type: ClassVar[type[BaseModel]] = ObservationLayers

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Bind the repository to one secure-object store (see :class:`SecureBoundRepository`)."""
        self._layers = _ObservationLayerStore(bucket_id=bucket_id, objects=objects, settings=settings)

    @classmethod
    def payload_model(cls) -> type[ObservationLayers]:
        """Return the stored row payload model."""
        return ObservationLayers

    @property
    def secure_object_repository(self) -> SecureObjectRepository:
        """Return the concrete secure-object backend shared by co-committed writes."""
        return self._layers.secure_object_repository

    def extract_identifier(self, payload: ObservationLayers) -> str:
        """Return the storage key of one stored layer row."""
        return self._layers.extract_identifier(payload)

    def envelope_identifier(self, payload: ObservationEnvelopePayload) -> str:
        """Return the storage key of the coordinate ``payload`` belongs to."""
        return self._layers.extract_identifier(_layers_for(payload))

    def _load_layers(self, identifier: str) -> ObservationLayers | None:
        return _translate_storage_failure(
            "calculation_observation_load",
            lambda: self._layers.load(identifier),
        )

    def load(self, identifier: str) -> ObservationEnvelopePayload | None:
        """Return the effective envelope stored under ``identifier``."""
        layers = self._load_layers(identifier)
        return layers.effective if layers is not None else None

    def load_observation(
        self,
        modelo: str,
        period: Period,
    ) -> ObservationEnvelopePayload | None:
        """Return the effective observation for one single-filer coordinate, or None."""
        filing_period = require_observation_period(period)
        return self.load(observation_key(modelo, filing_period))

    def load_observation_layers(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
    ) -> ObservationLayers:
        """Return both layers of one coordinate; a coordinate never written has neither."""
        filing_period = require_observation_period(period)
        stored = self._load_layers(member_observation_key(modelo, filing_period, member_nif))
        if stored is not None:
            return stored
        return ObservationLayers(
            modelo=modelo,
            filing_year=filing_period.filing_year,
            period=filing_period.registry_token,
            member_nif=member_nif,
        )

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
        """Build one validated observation envelope without writing it.

        Every writer traverses this method, so the registry and Modelo 303
        carry checks below run before any write is prepared.

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
        so a fact not named there never reaches storage.

        ``override`` records the audit of an operator figure; only a
        non-official envelope can carry one.

        Every Modelo 303 envelope crosses the canonical disposition-aware
        normalization ingress. Incomplete or conflicting evidence is refused;
        there is no generic unnormalized storage shape. Callers that co-emit
        this envelope with a history projection use
        ``to_secure_object_write`` and the storage backend's batch boundary
        so the pair cannot half-persist.
        """
        with bundled_indexed_authority().operation() as operation:
            law_revision_id = validate_observation_casilla_ids(
                observation,
                operation=operation,
                stamped_revision_id=stamped_revision_id,
            )
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
                    "override": override,
                },
                context={"canonical_m303_ingress_candidate": True},
            )
            # Keep the serialisable envelope model independent from the application
            # policy that normalizes it, while making this sole write door canonical.
            payload = normalize_m303_carry_observation_envelope(payload, operation=operation)
        return ObservationEnvelopePayload.model_validate(payload.model_dump())

    def iter_modelo(self, modelo: str) -> Iterator[ObservationEnvelopePayload]:
        """Yield the effective observation of every stored coordinate of ``modelo``.

        Used by grouped previous-filing and clean-state readers to enumerate all
        known source rows for a modelo, including member-widened keys.

        The base scan verifies each row's key before yielding it, which this
        filter depends on: the ``modelo`` test below reads the payload's own
        coordinates, so a row filed under another key would enter the window it
        describes rather than the one it is stored in. The verified scan
        recomputes the natural key from each payload and refuses a mismatch
        instead of yielding it.
        """
        try:
            safe_repository_id(modelo, context="modelo")
            for payload in self.iter_records():
                if payload.observation.modelo == modelo:
                    yield payload
        except PersistenceDegradationError:
            raise
        except (StorageError, OSError, ValidationError, UnicodeDecodeError) as exc:
            raise PersistenceDegradationError("calculation_observation_iter_modelo") from exc

    def iter_layers(self) -> Iterator[ObservationLayers]:
        """Iterate every stored coordinate's layers while translating storage failures inward."""
        try:
            yield from self._layers.iter_records()
        except PersistenceDegradationError:
            raise
        except (StorageError, OSError, ValidationError, UnicodeDecodeError) as exc:
            raise PersistenceDegradationError("calculation_observation_iter_records") from exc

    def iter_records(self) -> Iterator[ObservationEnvelopePayload]:
        """Iterate the effective envelope of every stored coordinate."""
        for layers in self.iter_layers():
            effective = layers.effective
            if effective is not None:
                yield effective

    def _placed(self, payload: ObservationEnvelopePayload) -> ObservationLayers:
        """Return the stored layers with ``payload`` placed in the layer its source kind selects."""
        stored = self._load_layers(self.envelope_identifier(payload)) or _layers_for(payload)
        layer = "pending_local" if payload.is_pending_local else "official"
        return ObservationLayers.model_validate({**dict(stored), layer: payload})

    def save(self, payload: ObservationEnvelopePayload) -> None:
        """Persist one envelope into its layer while translating storage failures inward."""
        _translate_storage_failure(
            "calculation_observation_save",
            lambda: self._layers.save(self._placed(payload)),
        )

    def to_secure_object_write(
        self,
        payload: ObservationEnvelopePayload,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare the write placing one envelope into its layer, for an outer transaction."""
        return self._layers_write(self._placed(payload), expected_revision_id=expected_revision_id)

    def _layers_write(
        self,
        layers: ObservationLayers,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return _translate_storage_failure(
            "calculation_observation_prepare",
            lambda: self._layers.to_secure_object_write(layers, expected_revision_id=expected_revision_id),
        )

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
        """Prepare the write that makes the pending-local layer the official one.

        An operator override is not AEAT's answer, so a pending layer carrying
        one is left in place and nothing is written.
        """
        layers = self.load_observation_layers(modelo, period, member_nif=member_nif)
        pending = layers.pending_local
        if pending is None or pending.override is not None:
            return ()
        promoted = ObservationEnvelopePayload.model_validate(
            {
                **dict(pending),
                "source_kind": source_kind,
                "source_metadata": dict(source_metadata),
                "captured_at": captured_at,
            },
        )
        return (
            self._layers_write(
                ObservationLayers.model_validate({**dict(layers), "official": promoted, "pending_local": None}),
            ),
        )

    def clear_pending_local(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
        replacement_official: ObservationEnvelopePayload | None = None,
    ) -> tuple[SecureObjectWrite, ...]:
        """Prepare the write that removes the pending-local layer, optionally replacing the official one."""
        layers = self.load_observation_layers(modelo, period, member_nif=member_nif)
        if layers.pending_local is None:
            return ()
        official = replacement_official if replacement_official is not None else layers.official
        return (
            self._layers_write(
                ObservationLayers.model_validate({**dict(layers), "official": official, "pending_local": None}),
            ),
        )


class IvaWalletDecisionRepository(SecureBoundRepository[IvaWalletDecisionEnvelopePayload]):
    """Repository over encrypted SQL-backed IVA wallet reconciliation decisions.

    Holds one latest decision per ``(taxpayer_nif, target_year, target_period)``
    triple for calculation lookup, and also writes every distinct decision to
    an immutable audit-event namespace. Decisions are AUDIT-class — they record
    the resolved gap between a taxpayer's local IVA compensation recurrence and
    the live AEAT wallet, which downstream calculation chains consult through
    :class:`~.iva_wallet_reconciliation.IvaWalletDecisionSourceResolver`.

    Latest-state rows use
    :data:`~adapters.persistence.storage.secure_object_namespaces.IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE`;
    immutable audit events use
    :data:`~adapters.persistence.storage.secure_object_namespaces.IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE`.
    Both store :class:`IvaCompensationReconciliationDecision` payloads in
    :class:`~adapters.persistence.storage.envelope.contract.Envelope` records through
    :class:`~adapters.persistence.storage.envelope.secure_bound_repository.SecureBoundRepository`.
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
        with bundled_indexed_authority().operation() as operation:
            require_decision_registry_coordinates_current(decision, operation=operation)
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
        with bundled_indexed_authority().operation() as operation:
            require_decision_registry_coordinates_current(payload.decision, operation=operation)
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
        with bundled_indexed_authority().operation() as operation:
            for decision in decisions:
                require_decision_registry_coordinates_current(decision, operation=operation)
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
        with bundled_indexed_authority().operation() as operation:
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
                    require_decision_registry_coordinates_current(decision, operation=operation)
                    decisions.append(decision)
        return tuple(sorted(decisions, key=lambda item: (item.decided_at, item.wallet_captured_at or item.decided_at)))


__all__ = [
    "CalculationObservationRepository",
    "IvaWalletDecisionRepository",
]
