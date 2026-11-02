"""Inert write-side methods for in-memory prior-filing observation repositories."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from ....core.observed_header_fact import ObservedHeaderFact
from ....core.period import Period
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import RevisionId
from ....domain.modelos.filing_kind_evidence import ObservedFilingKind
from ..observations_repository import (
    ObservationEnvelopePayload,
    ObservationLayers,
    ObservationOverride,
    ObservationSourceKind,
    PriorDomiciliationElectionProjection,
    ResultDispositionProjection,
)


class ObservationRepositoryStubs:
    """Layers read empty, writes do nothing and envelope preparation is refused."""

    def load_observation_layers(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
    ) -> ObservationLayers:
        return ObservationLayers(
            modelo=modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
            member_nif=member_nif,
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
        del modelo, period, member_nif, source_kind, source_metadata, captured_at
        return ()

    def clear_pending_local(
        self,
        modelo: str,
        period: Period,
        *,
        member_nif: str | None = None,
        replacement_official: ObservationEnvelopePayload | None = None,
    ) -> tuple[SecureObjectWrite, ...]:
        del modelo, period, member_nif, replacement_official
        return ()

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
        filing_kind: ObservedFilingKind | None = None,
    ) -> ObservationEnvelopePayload:
        del (
            observation,
            source_kind,
            stamped_revision_id,
            captured_at,
            member_nif,
            source_metadata,
            source_headers,
            result_disposition,
            prior_domiciliation_election,
            override,
            filing_kind,
        )
        raise AssertionError("this observation repository stub does not prepare envelopes")
