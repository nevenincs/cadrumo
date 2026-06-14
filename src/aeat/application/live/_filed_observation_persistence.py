"""Persist filed AEAT observations into calculation-history repositories.

Use of :class:`CasillaObservation` for compliance. Stamps matching
:class:`ModeloRecord` filings and appends the enrolment to the profile
:class:`BucketEventHistoryRepository` audit trail.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ...adapters.inbound.justificante import parse_justificante_bytes
from ...adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    ObservedCasillaValue,
    SedeParseError,
    registry_observation_from_filed_declaration,
)
from ...application.calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    iva_compensation_state_from_filed_observation,
    observation_key,
)
from ...core import Modelo, Period
from ...core.hashing import sha256_hex
from ...core.logging import get_logger
from ...core.resources import resources
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ...domain.iva_compensation._carry_forward import derive_303_compensation_available
from ...domain.justificante import Justificante, JustificanteRepository
from ...domain.modelos import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogueRepository,
    upsert_filing_record,
)
from ...domain.modelos._protocols import ModeloRecordCatalogueRepositoryProtocol
from ._errors import LiveApplicationError, LiveApplicationInputError

logger = get_logger(__name__)


@dataclass(frozen=True)
class FiledJustificanteEnrollmentResult:
    """Justificante metadata and current filing records enrolled from filed history."""

    justificante_csvs: tuple[str, ...] = ()
    filing_record_ids: tuple[str, ...] = ()
    conflicting_filing_record_ids: tuple[str, ...] = ()


_JUSTIFICANTE_VERIFIED_EXTERNAL_EVIDENCE_KINDS = frozenset(
    {
        ExternalEvidenceKind.AEAT_CSV_REGISTER,
        ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
    },
)


def persist_filed_calculation_observation(
    observation: FiledDeclaracionObservation,
    *,
    repository: CalculationObservationRepository | None = None,
    justificante_csvs: tuple[str, ...] = (),
) -> str:
    """Promote one AEAT filed-declaration observation into calculation history."""
    if not _is_active_filed_observation(observation):
        raise LiveApplicationInputError(
            f"refusing to persist non-active AEAT filed observation "
            f"{observation.modelo}/{observation.ejercicio}/{observation.period.registry_token} "
            f"with status {observation.status!r}",
        )
    registry_observation = registry_observation_from_filed_declaration(observation)
    registry_observation = _with_derived_303_compensation_available(registry_observation)
    repo = repository if repository is not None else CalculationObservationRepository()
    stamped_revision_id = _resolve_stamped_revision_id(
        registry_observation.modelo,
        Period.from_year_and_code(registry_observation.filing_year, registry_observation.period),
    )
    repo.save_observation(
        registry_observation,
        source_kind="aeat_sede_justificante",
        captured_at=observation.presented_at,
        stamped_revision_id=stamped_revision_id,
        source_metadata=_filed_observation_source_metadata(observation, justificante_csvs=justificante_csvs),
    )
    if observation.modelo == Modelo.M303:
        IvaCompensationHistoryRepository().save_period(
            iva_compensation_state_from_filed_observation(_calculation_observation(observation))
        )
    return observation_key(
        registry_observation.modelo,
        Period.from_year_and_code(registry_observation.filing_year, registry_observation.period),
    )


def persist_latest_filed_calculation_observations(
    observations: tuple[FiledDeclaracionObservation, ...],
    *,
    justificante_csvs_by_observation: Mapping[tuple[str, int, str, str], tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    """Persist only the latest captured observation per modelo/year/period."""
    latest: dict[tuple[str, int, Period], FiledDeclaracionObservation] = {}
    for observation in observations:
        key = (observation.modelo, observation.ejercicio, observation.period)
        current = latest.get(key)
        if current is None or _filed_observation_rank(observation) > _filed_observation_rank(current):
            latest[key] = observation
    keys: list[str] = []
    for _key, observation in sorted(
        latest.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2].registry_token),
    ):
        keys.extend(
            _persist_filed_calculation_observation_if_extractable(
                observation,
                justificante_csvs=_justificante_csvs_for_observation(observation, justificante_csvs_by_observation),
            ),
        )
    return tuple(keys)


def persist_filed_justificante_metadata(
    observation: FiledDeclaracionObservation,
    *,
    store: FiledDeclaracionObservationStore,
    repository: JustificanteRepository | None = None,
) -> tuple[str, ...]:
    """Persist parsed justificante metadata from a filed-declaration observation.

    The observation store owns encrypted artefact bytes. This function reads
    those bytes into memory, verifies the artefact manifest, parses the PDF
    without creating a plaintext temp file, and saves only justificantes that
    match the observation's modelo, ejercicio, typed period, and authenticated
    taxpayer identity.
    """
    if not _is_active_filed_observation(observation):
        return ()
    repo = repository or JustificanteRepository()
    saved_csvs: list[str] = []
    for artefact in observation.artefacts:
        if artefact.kind != "justificante_pdf" or artefact.storage_ref is None:
            continue
        justificante = _parse_matching_filed_justificante(observation, artefact, store)
        if justificante is None:
            continue
        repo.save(justificante)
        saved_csvs.append(justificante.csv)
    return tuple(dict.fromkeys(saved_csvs))


def enroll_filed_justificante_evidence(
    observation: FiledDeclaracionObservation,
    *,
    store: FiledDeclaracionObservationStore,
    bucket_id: str,
    justificante_repository: JustificanteRepository | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
) -> FiledJustificanteEnrollmentResult:
    """Persist matching justificante metadata and stamp matching current filings.

    Returns:
        A :class:`FiledJustificanteEnrollmentResult` of saved CSVs and stamped
        filing records.
    """
    if not _is_active_filed_observation(observation):
        return FiledJustificanteEnrollmentResult()

    justificante_repo = justificante_repository or JustificanteRepository()
    filing_repo = filing_repository or ModeloRecordCatalogueRepository()
    filing_catalogue = filing_repo.load()
    saved_csvs: list[str] = []
    stamped_record_ids: list[str] = []
    conflicting_record_ids: list[str] = []
    for artefact in observation.artefacts:
        if artefact.kind != "justificante_pdf" or artefact.storage_ref is None:
            continue
        justificante = _parse_matching_filed_justificante(observation, artefact, store)
        if justificante is None:
            continue
        justificante_repo.save(justificante)
        saved_csvs.append(justificante.csv)

        current = filing_catalogue.current_for(
            bucket_id=bucket_id,
            modelo=observation.modelo,
            filing_year=observation.ejercicio,
            period=observation.period,
        )
        if current is None:
            continue
        if not _filed_justificante_can_stamp_filing(
            justificante,
            observation=observation,
            filing=current,
        ):
            continue
        if current.aeat_accepted and current.external_evidence is not None:
            if _existing_justificante_evidence_matches(current, justificante):
                stamped_record_ids.append(current.filing_record_id)
                continue
            conflicting_record_ids.append(current.filing_record_id)
            logger.warning(
                "refusing to overwrite existing AEAT evidence on filing record %s from filed-history csv %s",
                current.filing_record_id,
                justificante.csv,
            )
            continue
        stamped = current.model_copy(
            update={
                "external_evidence": ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    reference_id=justificante.csv,
                    imported_at=artefact.captured_at,
                ),
                "aeat_accepted": True,
            },
        )
        filing_catalogue = upsert_filing_record(filing_catalogue, stamped)
        _emit_filed_justificante_evidence_event(
            bucket_id=bucket_id,
            filing=stamped,
            observation=observation,
            justificante=justificante,
            occurred_at=artefact.captured_at,
        )
        stamped_record_ids.append(stamped.filing_record_id)
    if stamped_record_ids:
        filing_repo.save(filing_catalogue)
    return FiledJustificanteEnrollmentResult(
        justificante_csvs=tuple(dict.fromkeys(saved_csvs)),
        filing_record_ids=tuple(dict.fromkeys(stamped_record_ids)),
        conflicting_filing_record_ids=tuple(dict.fromkeys(conflicting_record_ids)),
    )


def persist_iva_compensation_history_observations_strict(
    observations: tuple[FiledDeclaracionObservation, ...],
) -> tuple[str, ...]:
    """Persist latest Modelo 303 observations and verify each history row reloads."""
    latest: dict[tuple[int, Period], FiledDeclaracionObservation] = {}
    for observation in observations:
        if observation.modelo != Modelo.M303:
            raise LiveApplicationInputError(
                translated_message="live.errors.iva_history_modelo_303_only",
                context={"modelo": observation.modelo},
            )
        key = (observation.ejercicio, observation.period)
        current = latest.get(key)
        if current is None or _filed_observation_rank(observation) > _filed_observation_rank(current):
            latest[key] = observation

    keys: list[str] = []
    history_repo = IvaCompensationHistoryRepository()
    for (_year, _period), observation in sorted(
        latest.items(),
        key=lambda item: (item[0][0], item[0][1].registry_token),
    ):
        if not _is_active_filed_observation(observation):
            continue
        try:
            key = persist_filed_calculation_observation(observation)
        except SedeParseError as exc:
            raise LiveApplicationError(
                f"filed Modelo 303 {observation.period!s} could not be promoted into IVA compensation history",
            ) from exc
        if history_repo.load_period(observation.period) is None:
            raise LiveApplicationError(
                f"secure IVA compensation history did not reload after persisting Modelo 303 {observation.period!s}",
            )
        keys.append(key)
    return tuple(keys)


def latest_declarations_by_period(declarations: tuple[Declaracion, ...]) -> tuple[Declaracion, ...]:
    """Return the latest :class:`Declaracion` per period from register rows."""
    latest: dict[Period, Declaracion] = {}
    for declaration in declarations:
        current = latest.get(declaration.period)
        if current is None:
            latest[declaration.period] = declaration
            continue
        current_rank = (current.estado.upper() == "ALTA", current.presented_at, current.expediente_id)
        candidate_rank = (declaration.estado.upper() == "ALTA", declaration.presented_at, declaration.expediente_id)
        if candidate_rank > current_rank:
            latest[declaration.period] = declaration
    return tuple(latest[key] for key in sorted(latest, key=_history_period_sort_key))


def _emit_filed_justificante_evidence_event(
    *,
    bucket_id: str,
    filing: ModeloRecord,
    observation: FiledDeclaracionObservation,
    justificante: Justificante,
    occurred_at: datetime,
) -> None:
    event_payload = {
        "work_unit_id": filing.work_unit_id,
        "modelo": observation.modelo,
        "filing_year": str(observation.ejercicio),
        "period": observation.period.registry_token,
        "evidence_kind": ExternalEvidenceKind.AEAT_LIVE_CAPTURE.value,
        "evidence_reference_id": justificante.csv,
        "expediente_id": observation.expediente_id,
        "presented_at": observation.presented_at.isoformat(),
    }
    repository = BucketEventHistoryRepository()
    repository.save(
        append_bucket_event(
            repository.load(),
            BucketEvent(
                event_id=derive_bucket_event_id(
                    bucket_id=bucket_id,
                    event_type=BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,
                    occurred_at=occurred_at,
                    actor="aeat-filed-history",
                    object_type=BucketEventObjectType.FILING_RECORD,
                    object_id=filing.filing_record_id,
                    payload=event_payload,
                ),
                bucket_id=bucket_id,
                event_type=BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,
                occurred_at=occurred_at,
                actor="aeat-filed-history",
                object_type=BucketEventObjectType.FILING_RECORD,
                object_id=filing.filing_record_id,
                payload_version=1,
                payload=event_payload,
            ),
        ),
    )


def _existing_justificante_evidence_matches(filing: ModeloRecord, justificante: Justificante) -> bool:
    if filing.external_evidence is None:
        return False
    return (
        filing.external_evidence.kind in _JUSTIFICANTE_VERIFIED_EXTERNAL_EVIDENCE_KINDS
        and filing.external_evidence.reference_id.strip().upper() == justificante.csv.strip().upper()
    )


def _history_period_sort_key(period: Period) -> tuple[int, str]:
    upper = period.registry_token.upper()
    if upper.endswith("T") and upper[:-1].isdigit():
        return (int(upper[:-1]), upper)
    if upper.isdigit():
        return (int(upper), upper)
    return (100, upper)


def _persist_filed_calculation_observation_if_extractable(
    observation: FiledDeclaracionObservation,
    *,
    justificante_csvs: tuple[str, ...] = (),
) -> tuple[str, ...]:
    try:
        return (persist_filed_calculation_observation(observation, justificante_csvs=justificante_csvs),)
    except (LiveApplicationInputError, SedeParseError):
        return ()


def _parse_matching_filed_justificante(
    observation: FiledDeclaracionObservation,
    artefact: FiledDeclaracionArtefact,
    store: FiledDeclaracionObservationStore,
) -> Justificante | None:
    storage_ref = artefact.storage_ref
    if storage_ref is None:
        return None
    try:
        body = store.load_artefact(storage_ref)
    except Exception:
        logger.warning(
            "filed observation: ignored unreadable justificante artefact %s",
            storage_ref,
            exc_info=True,
        )
        return None
    if len(body) != artefact.byte_count or sha256_hex(body) != artefact.sha256:
        logger.warning(
            "filed observation: ignored justificante artefact %s with mismatched manifest",
            storage_ref,
        )
        return None
    try:
        justificante = parse_justificante_bytes(body)
    except Exception:
        logger.warning(
            "filed observation: ignored unparsable justificante artefact %s",
            storage_ref,
            exc_info=True,
        )
        return None
    if not _justificante_matches_filed_observation(justificante, observation):
        logger.warning(
            "filed observation: ignored justificante artefact %s that does not match %s/%s/%s",
            storage_ref,
            observation.modelo,
            observation.ejercicio,
            observation.period.registry_token,
        )
        return None
    return justificante


def _justificante_matches_filed_observation(
    justificante: Justificante,
    observation: FiledDeclaracionObservation,
) -> bool:
    presentation_id = (justificante.presentation_id or "").strip()
    if presentation_id and presentation_id.casefold() != observation.expediente_id.strip().casefold():
        return False
    return (
        justificante.modelo.strip() == observation.modelo
        and str(justificante.ejercicio or "").strip() == str(observation.ejercicio)
        and justificante.period == observation.period
        and justificante.tax_id.strip().upper() == observation.authenticated_identity.strip().upper()
    )


def _filed_justificante_can_stamp_filing(
    justificante: Justificante,
    *,
    observation: FiledDeclaracionObservation,
    filing: ModeloRecord,
) -> bool:
    from ._justificante import _expected_tax_id_for_filing_record, _justificante_matches_filing_record

    try:
        expected_tax_id = _expected_tax_id_for_filing_record(filing)
    except LiveApplicationInputError:
        logger.warning(
            "filed observation: could not resolve profile tax identity for filing record %s",
            filing.filing_record_id,
            exc_info=True,
        )
        return False
    if observation.authenticated_identity.strip().upper() != expected_tax_id.strip().upper():
        return False
    return _justificante_matches_filing_record(
        justificante,
        filing,
        expected_tax_id=expected_tax_id,
    )


def _is_active_filed_observation(observation: FiledDeclaracionObservation) -> bool:
    return observation.status.strip().upper() == "ALTA"


def _filed_observation_rank(observation: FiledDeclaracionObservation) -> tuple[bool, datetime, str]:
    return (_is_active_filed_observation(observation), observation.presented_at, observation.expediente_id)


def _filed_observation_source_metadata(
    observation: FiledDeclaracionObservation,
    *,
    justificante_csvs: tuple[str, ...] = (),
) -> dict[str, str]:
    metadata = {
        "aeat_register_status": observation.status.strip().upper(),
        "aeat_expediente_id": observation.expediente_id,
        "authenticated_identity": observation.authenticated_identity.strip().upper(),
    }
    unique_csvs = tuple(dict.fromkeys(csv.strip() for csv in justificante_csvs if csv.strip()))
    if len(unique_csvs) == 1:
        metadata["aeat_justificante_csv"] = unique_csvs[0]
    elif len(unique_csvs) > 1:
        metadata["aeat_justificante_csvs"] = ",".join(unique_csvs)
    return metadata


def _filed_observation_identity_key(observation: FiledDeclaracionObservation) -> tuple[str, int, str, str]:
    return (
        observation.modelo,
        observation.ejercicio,
        observation.period.registry_token,
        observation.expediente_id,
    )


def _justificante_csvs_for_observation(
    observation: FiledDeclaracionObservation,
    justificante_csvs_by_observation: Mapping[tuple[str, int, str, str], tuple[str, ...]] | None,
) -> tuple[str, ...]:
    if justificante_csvs_by_observation is None:
        return ()
    return justificante_csvs_by_observation.get(_filed_observation_identity_key(observation), ())


@dataclass(frozen=True)
class _FiledDeclaracionCalculationObservation:
    modelo: str
    ejercicio: int
    period: Period
    expediente_id: str
    status: str
    presented_at: datetime
    authenticated_identity: str
    artefacts: tuple[FiledDeclaracionArtefact, ...]
    casillas: tuple[ObservedCasillaValue, ...]


def _calculation_observation(
    observation: FiledDeclaracionObservation,
) -> _FiledDeclaracionCalculationObservation:
    return _FiledDeclaracionCalculationObservation(
        modelo=observation.modelo,
        ejercicio=observation.ejercicio,
        period=observation.period,
        expediente_id=observation.expediente_id,
        status=observation.status,
        presented_at=observation.presented_at,
        authenticated_identity=observation.authenticated_identity,
        artefacts=observation.artefacts,
        casillas=observation.casillas,
    )


def _with_derived_303_compensation_available(
    observation: RegistryModeloObservation,
) -> RegistryModeloObservation:
    """Add the internal Modelo 303 carry-forward value from official filed casillas."""
    if observation.modelo != Modelo.M303:
        return observation
    target_id = "iva.compensacion-disponible-fin-periodo"
    if target_id in observation.casilla_values:
        return observation
    posterior = _casilla_decimal(
        observation.casilla_values,
        "87",
        "iva.compensacion-pendiente-periodos-posteriores",
    )
    resultado = _casilla_decimal(observation.casilla_values, "69", "iva.resultado")
    if posterior is None or resultado is None:
        return observation

    available = derive_303_compensation_available(posterior=posterior, resultado=resultado)
    snapshot = resources().modelos.authority.snapshot(
        Modelo.M303.value,
        filing_year=observation.filing_year,
        period=observation.period,
    )
    casilla = next(item for item in snapshot.revision.casillas if item.id == target_id)
    formula = next(item for item in snapshot.revision.formulas if item.target == target_id)
    derived = CasillaObservation(
        casilla_id=target_id,
        value=available,
        formula_id=formula.id,
        operand_refs=("87", "69"),
        operand_values=(posterior, resultado),
        legal_refs=tuple(casilla.legal_refs),
        source_refs=tuple(casilla.source_refs),
    )
    return observation.model_copy(update={"observations": (*observation.observations, derived)})


def _casilla_decimal(values: Mapping[str, Decimal], *casilla_ids: str) -> Decimal | None:
    for casilla_id in casilla_ids:
        value = values.get(casilla_id)
        if value is not None:
            return value
    return None


def _resolve_stamped_revision_id(modelo: str, period: Period) -> str | None:
    """Resolve the registry revision id for (modelo, period) for provenance stamping.

    Returns the revision id from the law-determined :func:`select_revision` result
    (ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2), or ``None``
    on resolution failure so the stamp is never blocking at write time.
    """
    try:
        snapshot = resources().modelos.authority.snapshot(
            modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
        )
        return snapshot.revision.id
    except Exception:
        return None


__all__ = [
    "FiledJustificanteEnrollmentResult",
    "enroll_filed_justificante_evidence",
    "latest_declarations_by_period",
    "persist_filed_calculation_observation",
    "persist_filed_justificante_metadata",
    "persist_iva_compensation_history_observations_strict",
    "persist_latest_filed_calculation_observations",
]
