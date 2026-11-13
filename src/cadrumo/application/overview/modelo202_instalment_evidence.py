"""Gather what one overview read's stores know about a Modelo 202 instalment's ingreso.

The art. 40.2 base is read only through the resolution of the instalment's base
binding, and only a filing that was presented decides it: a local PRESENTADO
revision of the earlier Modelo 200 or its captured AEAT evidence. A draft never
writes a filed observation, and an operator-entered observation is not a filing,
so neither decides. Where no such filing is held, the base the operator stated
on the instalment's own work unit stands for it. The instalment's own
calculation is read from that work unit's current revision, and counts as
current only while its registry stamp carries and its ledger anchor has not
moved against the live transaction catalogue.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from ...core.period import Period
from ...domain.calculations.registry.applicability_modelo202 import Modelo202BaseBasis, Modelo202Modality
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.result_casillas import canonical_result_amount, result_disposition_casilla_ids
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.transactions.models import TransactionCatalogue
from ...domain.user_profile.schema import ProfileSchemaDefinition
from ...domain.user_profile.values import UserProfileRecord
from ..aggregation.ledger_filing_snapshot import evaluate_ledger_filing_staleness
from ..calculations.cross_period_models import operator_value_attestations
from ..calculations.modelo_202_base_source import (
    MODELO_202_BASE_BINDING_ID,
    modelo_202_base_source_periods,
    modelo_202_base_source_requirement,
    modelo_202_form,
    modelo_202_instalment_has_no_prior_return,
)
from ..calculations.modelo_202_instalment_resolution import (
    Modelo202InstalmentResolution,
    Modelo202InstalmentResolver,
)
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    ObservationEnvelopePayload,
    ObservationSourceKind,
)
from ..calculations.relation_prefill import resolve_relations_from_local_store
from ..calculations.revision_carry_gate import revision_carry_outcome
from ..modelo.work_addressing import ModeloWorkAddress, resolve_optional_modelo_work_address
from ..user_profile.projections import record_to_values
from .calendar_warnings import MODELO_202_ELECTION_PROFILE_KEY
from .modelo202_instalment import (
    Modelo202BaseReading,
    Modelo202BaseSource,
    Modelo202CalculationReading,
    Modelo202InstalmentFacts,
    Modelo202InstalmentFactsReader,
    resolve_modelo_202_instalment,
)

_VERIFIED_STATES = frozenset({CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO})
_STATED_ELECTION: Final[Mapping[str, bool]] = MappingProxyType({"true": True, "false": False})


def art_40_3_election_reader(
    record: UserProfileRecord,
    *,
    schema: ProfileSchemaDefinition,
) -> Callable[[Period], bool | None]:
    """Read the art. 40.3 election in force at the start of each instalment's periodo impositivo.

    The election binds from the periodo impositivo it was made for until it is
    renounced, so an instalment reads the value effective on the first day of
    its own periodo impositivo, which for these instalments is the filing year.
    A value never stated reads as ``None``.

    Core types: :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """

    def election_for(instalment: Period) -> bool | None:
        values = record_to_values(record, schema=schema, as_of=date(instalment.filing_year, 1, 1))
        return _STATED_ELECTION.get(values.get(MODELO_202_ELECTION_PROFILE_KEY, ""))

    return election_for


def art_40_3_election_reader_for_bucket(
    bucket_id: str,
    *,
    operation: PinnedAuthorityOperation,
) -> Callable[[Period], bool | None]:
    """Read the art. 40.3 election from the bucket's stored profile, loaded on first use.

    The record is read through the current session the first time an
    instalment asks, so a read that decides no instalment never opens it. A
    bucket without a profile states no election.
    """
    from ...domain.user_profile.errors import ProfileNotFoundError
    from ..user_profile.profile_record_repository import ProfileRecordRepository

    readers: list[Callable[[Period], bool | None]] = []

    def election_for(instalment: Period) -> bool | None:
        if not readers:
            context = operation.profile_decode_context()
            try:
                record = ProfileRecordRepository.for_current_session(
                    bucket_id,
                    profile_decode_context=context,
                ).load(bucket_id)
            except ProfileNotFoundError:
                readers.append(lambda _instalment: None)
            else:
                readers.append(art_40_3_election_reader(record, schema=context.schema))
        return readers[0](instalment)

    return election_for


@dataclass(frozen=True, slots=True)
class Modelo202InstalmentStores:
    """The stores and declared facts one read decides Modelo 202 instalments on.

    Attributes:
        bucket_id: The profile bucket the read is bound to.
        observations: The filed-observation store the base binding resolves from.
        work_units: Loads the bucket's work-unit catalogue once per read.
        calculations: The bucket's calculation-revision store.
        transactions: Loads the bucket's live transaction catalogue; ``None`` where
            the read holds no ledger, so no elected calculation counts as current.
        activity_start_date: The declared activity start, if any.
        election_for: The art. 40.3 election in force for an instalment; ``None``
            when it was never stated.
    """

    bucket_id: str
    observations: CalculationObservationRepositoryProtocol
    work_units: Callable[[], WorkUnitCatalogue]
    calculations: CalculationRevisionCatalogueRepositoryProtocol
    transactions: Callable[[], TransactionCatalogue] | None
    activity_start_date: date | None
    election_for: Callable[[Period], bool | None]


def _decisive_basis(source_kind: ObservationSourceKind) -> Modelo202BaseBasis | None:
    if source_kind.is_official_aeat:
        return Modelo202BaseBasis.AEAT_EVIDENCE
    if source_kind is ObservationSourceKind.APP_FILING:
        return Modelo202BaseBasis.LOCAL_FILING
    return None


def _filed_base(
    instalment: Period,
    source: Modelo202BaseSource,
    stores: Modelo202InstalmentStores,
    *,
    operation: PinnedAuthorityOperation,
) -> Modelo202BaseReading | None:
    """Resolve the base binding and keep it only when a presented filing supplied it."""
    snapshot = operation.reading_snapshot(
        modelo_202_form(operation=operation),
        filing_year=instalment.filing_year,
        period=instalment.registry_token,
    )
    relation_values = resolve_relations_from_local_store(snapshot, operation=operation, repository=stores.observations)
    value = next(
        (item.value for item in relation_values.values if item.relation == MODELO_202_BASE_BINDING_ID),
        None,
    )
    if value is None:
        return None
    payload = stores.observations.load_observation(source.modelo, source.period)
    basis = None if payload is None else _decisive_basis(payload.source_kind)
    return None if basis is None else Modelo202BaseReading(value=Decimal(value), basis=basis)


def _attested_base(revision: CalculationRevision | None, source: Modelo202BaseSource) -> Modelo202BaseReading | None:
    stated = operator_value_attestations(revision).get(MODELO_202_BASE_BINDING_ID)
    if stated is None or not stated.covers(
        source_modelo=source.modelo,
        filing_year=source.period.filing_year,
        period_token=source.period.registry_token,
    ):
        return None
    return Modelo202BaseReading(value=Decimal(stated.value), basis=Modelo202BaseBasis.OPERATOR_ATTESTED)


def _calculation_is_current(
    revision: CalculationRevision,
    *,
    transactions: Callable[[], TransactionCatalogue] | None,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Report whether the revision's registry stamp carries and its ledger anchor has not moved.

    Without a ledger to compare against, an anchored revision cannot be shown
    current, so it is not.
    """
    if revision_carry_outcome(revision.registry_snapshot_ref, operation=operation).refused:
        return False
    anchor = revision.ledger_filing_snapshot
    if anchor is None:
        return True
    return transactions is not None and not evaluate_ledger_filing_staleness(anchor, transactions()).is_stale


def _calculation_reading(
    revision: CalculationRevision,
    *,
    modelo: str,
    transactions: Callable[[], TransactionCatalogue] | None,
    operation: PinnedAuthorityOperation,
) -> Modelo202CalculationReading | None:
    result_ids = result_disposition_casilla_ids(modelo)
    if result_ids is None:
        return None
    values = {
        casilla_id: revision.casilla_values[casilla_id]
        for casilla_id in result_ids
        if casilla_id in revision.casilla_values
    }
    if not values:
        return None
    result = canonical_result_amount(modelo, values)
    if result is None:
        return None
    return Modelo202CalculationReading(
        result=result,
        current=_calculation_is_current(revision, transactions=transactions, operation=operation),
        verified=revision.state in _VERIFIED_STATES,
    )


def _instalment_work_unit(
    instalment: Period,
    *,
    modelo: str,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> WorkUnit | None:
    address = ModeloWorkAddress(modelo=modelo, filing_year=instalment.filing_year, period=instalment)
    try:
        return resolve_optional_modelo_work_address(address, catalogue=catalogue, bucket_id=bucket_id).work_unit
    except ModeloError:
        return None


def bind_modelo_202_instalment_facts(
    stores: Modelo202InstalmentStores,
    *,
    operation: PinnedAuthorityOperation,
) -> Modelo202InstalmentFactsReader:
    """Bind the facts reader to one read's stores; each store is read at most once per read."""
    modelo = modelo_202_form(operation=operation)
    work_units: list[WorkUnitCatalogue] = []
    revisions: list[CalculationRevisionCatalogue] = []
    ledgers: list[TransactionCatalogue] = []

    def transactions() -> TransactionCatalogue:
        if not ledgers and stores.transactions is not None:
            ledgers.append(stores.transactions())
        return ledgers[0]

    def catalogue() -> WorkUnitCatalogue:
        if not work_units:
            work_units.append(stores.work_units())
        return work_units[0]

    def current_revision(unit: WorkUnit | None) -> CalculationRevision | None:
        if unit is None or unit.current_calculation_revision_id is None:
            return None
        if not revisions:
            revisions.append(stores.calculations.load(operation=operation))
        return revisions[0].get(unit.current_calculation_revision_id)

    def read(instalment: Period) -> Modelo202InstalmentFacts:
        unit = _instalment_work_unit(instalment, modelo=modelo, catalogue=catalogue(), bucket_id=stores.bucket_id)
        revision = current_revision(unit)
        requirement = modelo_202_base_source_requirement(instalment, operation=operation)
        source = (
            None
            if requirement is None
            else Modelo202BaseSource(
                modelo=requirement.source_modelo, period=modelo_202_base_source_periods(requirement)[0]
            )
        )
        base = None
        if source is not None:
            base = _filed_base(instalment, source, stores, operation=operation) or _attested_base(revision, source)
        return Modelo202InstalmentFacts(
            instalment=instalment,
            election_stated=stores.election_for(instalment),
            base_source=source,
            no_prior_return=modelo_202_instalment_has_no_prior_return(
                instalment,
                activity_start_date=stores.activity_start_date,
                operation=operation,
            ),
            base=base,
            work_unit_id=None if unit is None else unit.work_unit_id,
            calculation=None
            if revision is None
            else _calculation_reading(
                revision,
                modelo=modelo,
                transactions=None if stores.transactions is None else transactions,
                operation=operation,
            ),
        )

    return read


def _presented_filing(
    instalment: Period,
    stores: Modelo202InstalmentStores,
    *,
    operation: PinnedAuthorityOperation,
) -> ObservationEnvelopePayload | None:
    """Return the instalment's presented filing: its local filing or captured AEAT evidence, if held."""
    effective = stores.observations.load_observation_layers(modelo_202_form(operation=operation), instalment).effective
    if effective is None or _decisive_basis(effective.source_kind) is None:
        return None
    return effective


def bind_modelo_202_instalment_resolver(
    stores: Modelo202InstalmentStores,
    *,
    modality: Modelo202Modality | None,
    operation: PinnedAuthorityOperation,
) -> Modelo202InstalmentResolver:
    """Bind the instalment resolution to one read's stores and the ejercicio's derived modality.

    ``modality`` is the Modelo 202 modality derived for the instalments'
    ejercicio; ``None`` when it could not be derived, which leaves every unfiled
    instalment unresolved.
    """
    facts_for = bind_modelo_202_instalment_facts(stores, operation=operation)

    def resolve(instalment: Period) -> Modelo202InstalmentResolution:
        return resolve_modelo_202_instalment(
            facts_for(instalment),
            filing=_presented_filing(instalment, stores, operation=operation),
            modality=modality,
            operation=operation,
        )

    return resolve


__all__ = [
    "Modelo202InstalmentStores",
    "art_40_3_election_reader",
    "art_40_3_election_reader_for_bucket",
    "bind_modelo_202_instalment_facts",
    "bind_modelo_202_instalment_resolver",
]
