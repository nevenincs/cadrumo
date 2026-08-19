"""Persist filed AEAT observations into calculation-history repositories.

Filed Sede rows are promoted to registry-grounded :class:`CasillaObservation`
records, matching :class:`ModeloRecord` filings are stamped with justificante
evidence, and the enrolment is appended through
:class:`BucketEventHistoryRepository`.

The module treats AEAT live captures as official external evidence only after
the captured justificante matches the filed observation and an existing current
:class:`ModeloRecord`. It never creates the filing record itself and refuses to
overwrite conflicting :class:`ExternalEvidence`.

See Also:
    :class:`cadrumo.domain.modelos.ExternalEvidenceKind`
        Closed evidence-kind catalogue; live captures stamp
        ``AEAT_LIVE_CAPTURE``.
    :class:`cadrumo.application.calculations.CalculationObservationRepository`
        Repository that receives the registry-grounded filed-declaration
        observations consumed by cross-period resolvers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ...adapters.inbound.justificante import parse_justificante_bytes
from ...adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    SedeParseError,
    extract_csv_from_url,
    registry_observation_from_filed_declaration,
)
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.justificante import JustificanteRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...application.calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    ObservationSourceKind,
    observation_key,
    persist_observation_envelope_and_iva_history,
)
from ...core import IvaCompensationStateProvenance, Modelo, Period, PeriodKind, normalise_aeat_csv
from ...core.hashing import sha256_hex
from ...core.identity import same_tax_identifier
from ...core.json_contract import Notice, NoticeSeverity
from ...core.logging import get_logger
from ...domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.iva_compensation import iva_compensation_period_sort_key
from ...domain.justificante import Justificante
from ...domain.modelos import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepositoryProtocol,
    is_justificante_backed_external_evidence,
    upsert_filing_record,
)
from ._errors import (
    LiveApplicationError,
    LiveApplicationInputError,
    LiveReadPrecondition,
    live_read_no_recovery_verdict,
)

logger = get_logger(__name__)


class FiledJustificanteUnreachedReason(StrEnum):
    """Why one stored justificante artefact produced no evidence.

    Every member is a distinct dead end that used to share one shape: a log
    line plus ``None``. A capture that extracted casillas while enrolling no
    justificante therefore reported an unexplained zero, which reads the same
    as a period with no receipt to enroll.

    Attributes:
        UNREADABLE_ARTEFACT: Secure storage could not return the bytes.
        MANIFEST_MISMATCH: The bytes disagree with the recorded length or digest.
        UNPARSABLE_PDF: The bytes are not a receipt this parser can read.
        CSV_UNRESOLVABLE: The artefact's source URL carries no recoverable csv,
            so the receipt cannot be checked against the csv its bytes were
            fetched under.
        CSV_MISMATCH: The receipt's own csv is not the csv its bytes were
            fetched under, so these bytes belong to a different filing.
        FILING_TARGET_MISMATCH: The receipt parsed and its csv agrees, but it
            does not describe this observation's modelo, ejercicio, period or
            taxpayer.
    """

    UNREADABLE_ARTEFACT = "unreadable_artefact"
    MANIFEST_MISMATCH = "manifest_mismatch"
    UNPARSABLE_PDF = "unparsable_pdf"
    CSV_UNRESOLVABLE = "csv_unresolvable"
    CSV_MISMATCH = "csv_mismatch"
    FILING_TARGET_MISMATCH = "filing_target_mismatch"


#: Notice code for an artefact that was present but yielded no evidence.
FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE = "live.filed.justificante_unreached"


@dataclass(frozen=True)
class _FiledJustificanteParse:
    """One artefact's parse outcome: a receipt, or the reason there is none."""

    justificante: Justificante | None = None
    reason: FiledJustificanteUnreachedReason | None = None


@dataclass(frozen=True)
class FiledJustificanteMetadataResult:
    """Justificante metadata persisted from one filed observation."""

    justificante_csvs: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class FiledJustificanteEnrollmentResult:
    """Justificante metadata and current filing records enrolled from filed history."""

    justificante_csvs: tuple[str, ...] = ()
    filing_record_ids: tuple[str, ...] = ()
    conflicting_filing_record_ids: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()


def persist_filed_calculation_observation(
    observation: FiledDeclaracionObservation,
    *,
    repository: CalculationObservationRepository | None = None,
    justificante_csvs: tuple[str, ...] = (),
) -> str:
    """Promote one AEAT filed-declaration observation into calculation history.

    The persisted row is a registry-grounded
    :class:`cadrumo.domain.calculations.registry.RegistryModeloObservation`
    stamped with the law-selected registry revision when it can be resolved.
    """
    if not _is_active_filed_observation(observation):
        raise LiveApplicationInputError(
            translated_message="application.live.filed_observations.errors.observation_not_active",
            context={
                "modelo": observation.modelo,
                "ejercicio": observation.ejercicio,
                "period": observation.period.registry_token,
                "status": observation.status,
            },
            precondition_verdict=live_read_no_recovery_verdict(
                LiveReadPrecondition.FILED_OBSERVATION_ACTIVE,
                facts={
                    "modelo": observation.modelo,
                    "ejercicio": observation.ejercicio,
                    "period": observation.period.registry_token,
                    "status": observation.status,
                    "observation_active": False,
                },
            ),
        )
    registry_observation = registry_observation_from_filed_declaration(observation)
    repo = repository if repository is not None else CalculationObservationRepository()
    payload = repo.prepare_observation_envelope(
        registry_observation,
        source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        captured_at=observation.presented_at,
        source_metadata=_filed_observation_source_metadata(observation, justificante_csvs=justificante_csvs),
        # Passed separately from source_metadata, and that is the whole point:
        # the metadata projection is built from a fixed key set, so a header
        # fact routed through it would be dropped here exactly as it was before.
        source_headers=observation.headers,
        # Canonical S05 ingress: official evidence must recover its one typed
        # disposition from the submitted-file header before it can participate
        # in M303 carry. No compensación default is admitted here.
        normalize_m303_carry=True,
    )
    if observation.modelo == Modelo.M303:
        source_artefact_sha256 = next(
            (artefact.sha256 for artefact in observation.artefacts if artefact.kind == "submitted_file"),
            None,
        )
        persist_observation_envelope_and_iva_history(
            observation_repository=repo,
            history_repository=IvaCompensationHistoryRepository(objects=repo.secure_object_repository),
            envelope=payload,
            taxpayer_nif=observation.authenticated_identity,
            provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
            expediente_id=observation.expediente_id,
            status=observation.status,
            source_observation_key=(
                f"303:{observation.ejercicio}:{observation.period.registry_token}:{observation.expediente_id}"
            ),
            source_artefact_sha256=source_artefact_sha256,
        )
    else:
        repo.save(payload)
    return observation_key(
        registry_observation.modelo,
        Period.from_year_and_code(registry_observation.filing_year, registry_observation.period),
    )


def select_latest_filed_observations_in_history_order(
    observations: tuple[FiledDeclaracionObservation, ...],
) -> tuple[FiledDeclaracionObservation, ...]:
    """Return the latest observation per (modelo, year, period) in deterministic history order.

    "Latest" is by :func:`_filed_observation_rank` (an ALTA registration beats a
    BAJA, then most-recent ``presented_at``, then ``expediente_id``). History order
    is :func:`_filed_observation_history_period_sort_key` (Modelo 303 IVA fiscal
    order, quarterly/monthly numeric order elsewhere). This is the single
    selection-and-ordering authority shared by the calculation-history persistence
    below and the filed-capture finalizer, so every capture route persists the same
    observations in the same order and cannot drift.
    """
    latest: dict[tuple[str, int, Period], FiledDeclaracionObservation] = {}
    for observation in observations:
        key = (observation.modelo, observation.ejercicio, observation.period)
        current = latest.get(key)
        if current is None or _filed_observation_rank(observation) > _filed_observation_rank(current):
            latest[key] = observation
    return tuple(
        observation
        for _key, observation in sorted(
            latest.items(),
            key=lambda item: (
                item[0][0],
                item[0][1],
                _filed_observation_history_period_sort_key(item[0][0], item[0][2]),
            ),
        )
    )


def persist_filed_justificante_metadata(
    observation: FiledDeclaracionObservation,
    *,
    store: FiledDeclaracionObservationStore,
    repository: JustificanteRepository | None = None,
) -> FiledJustificanteMetadataResult:
    """Persist parsed justificante metadata from a filed-declaration observation.

    The observation store owns encrypted artefact bytes. This function reads
    those bytes into memory, verifies the artefact manifest, parses the PDF
    without creating a plaintext temp file, and saves only justificantes whose
    csv agrees with the csv their bytes were fetched under and that match the
    observation's modelo, ejercicio, typed period, and authenticated taxpayer
    identity.
    """
    if not _is_active_filed_observation(observation):
        return FiledJustificanteMetadataResult()
    repo = repository or JustificanteRepository()
    saved_csvs: list[str] = []
    notices: list[Notice] = []
    for artefact in observation.artefacts:
        if artefact.kind != "justificante_pdf" or artefact.storage_ref is None:
            continue
        parsed = _parse_matching_filed_justificante(observation, artefact, store)
        if parsed.justificante is None:
            if parsed.reason is not None:
                notices.append(_unreached_justificante_notice(observation, parsed.reason))
            continue
        repo.save(parsed.justificante)
        saved_csvs.append(parsed.justificante.csv)
    return FiledJustificanteMetadataResult(
        justificante_csvs=tuple(dict.fromkeys(saved_csvs)),
        notices=tuple(notices),
    )


@dataclass(frozen=True, slots=True)
class _FilingStampOutcome:
    """What stamping one parsed justificante did to the filing catalogue.

    The id tuples carry at most one entry each; they are tuples so the caller
    folds them in without re-testing which of the two outcomes occurred.
    """

    catalogue: ModeloRecordCatalogue
    stamped_record_ids: tuple[str, ...] = ()
    conflicting_record_ids: tuple[str, ...] = ()


def _stamp_filing_with_filed_justificante(
    justificante: Justificante,
    *,
    observation: FiledDeclaracionObservation,
    artefact: FiledDeclaracionArtefact,
    bucket_id: str,
    catalogue: ModeloRecordCatalogue,
) -> _FilingStampOutcome:
    """Stamp the current filing record with this justificante's evidence.

    The filing is stamped only when the justificante matches the observation and
    the current :class:`ModeloRecord`. Existing matching evidence is accepted
    idempotently; conflicting evidence is reported rather than overwritten.
    """
    current = catalogue.current_for(
        bucket_id=bucket_id,
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
    )
    if current is None:
        return _FilingStampOutcome(catalogue)
    if not _filed_justificante_can_stamp_filing(
        justificante,
        observation=observation,
        filing=current,
    ):
        return _FilingStampOutcome(catalogue)
    if current.aeat_accepted and current.external_evidence is not None:
        if _existing_justificante_evidence_matches(current, justificante):
            return _FilingStampOutcome(catalogue, stamped_record_ids=(current.filing_record_id,))
        logger.warning(
            "refusing to overwrite existing AEAT evidence on filing record %s from filed-history csv %s",
            current.filing_record_id,
            justificante.csv,
        )
        return _FilingStampOutcome(catalogue, conflicting_record_ids=(current.filing_record_id,))
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
    updated = upsert_filing_record(catalogue, stamped)
    _emit_filed_justificante_evidence_event(
        bucket_id=bucket_id,
        filing=stamped,
        observation=observation,
        justificante=justificante,
        occurred_at=artefact.captured_at,
    )
    return _FilingStampOutcome(updated, stamped_record_ids=(stamped.filing_record_id,))


def enroll_filed_justificante_evidence(
    observation: FiledDeclaracionObservation,
    *,
    store: FiledDeclaracionObservationStore,
    bucket_id: str,
    justificante_repository: JustificanteRepository | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
) -> FiledJustificanteEnrollmentResult:
    """Persist matching justificante metadata and stamp matching current filings.

    A filing is stamped only when the parsed :class:`Justificante` matches the
    observation, the authenticated identity, and the current
    :class:`ModeloRecord`. Existing matching evidence is accepted idempotently;
    conflicting evidence is reported rather than overwritten.

    Returns:
        A :class:`FiledJustificanteEnrollmentResult` of saved CSVs and stamped
        filing records.
    """
    if not _is_active_filed_observation(observation):
        return FiledJustificanteEnrollmentResult()

    justificante_repo = justificante_repository or JustificanteRepository()
    filing_repo = filing_repository or ModeloRecordCatalogueRepository()
    saved_csvs: list[str] = []
    stamped_record_ids: list[str] = []
    conflicting_record_ids: list[str] = []
    notices: list[Notice] = []
    # Parsing is done FIRST and the stamping afterwards, rather than interleaved
    # with the catalogue write, because the catalogue is a singleton row: reading
    # it here and writing it after N PDFs have been parsed leaves a window wide
    # enough for another caller's filing record to land and be discarded. The
    # parsed receipts are collected instead, and every stamping is applied inside
    # one guarded unit of work below.
    stampable: list[tuple[Justificante, object]] = []
    for artefact in observation.artefacts:
        if artefact.kind != "justificante_pdf" or artefact.storage_ref is None:
            continue
        parsed = _parse_matching_filed_justificante(observation, artefact, store)
        if parsed.justificante is None:
            if parsed.reason is not None:
                notices.append(_unreached_justificante_notice(observation, parsed.reason))
            continue
        justificante = parsed.justificante
        # The receipt lands before any record cites it, so a failure between the
        # two leaves an orphan receipt rather than a filing record pointing at
        # evidence that does not load.
        justificante_repo.save(justificante)
        saved_csvs.append(justificante.csv)
        stampable.append((justificante, artefact))

    if stampable:

        def _stamp_all(current: ModeloRecordCatalogue) -> ModeloRecordCatalogue:
            """Re-apply every stamping to whichever catalogue this attempt read.

            Pure in the catalogue it is handed and in the already-parsed
            receipts, so a retry re-stamps against the catalogue the write
            actually lands on without re-reading or re-parsing a single PDF.
            """
            stamped_record_ids.clear()
            conflicting_record_ids.clear()
            catalogue = current
            for justificante, artefact in stampable:
                outcome = _stamp_filing_with_filed_justificante(
                    justificante,
                    observation=observation,
                    artefact=artefact,
                    bucket_id=bucket_id,
                    catalogue=catalogue,
                )
                catalogue = outcome.catalogue
                stamped_record_ids.extend(outcome.stamped_record_ids)
                conflicting_record_ids.extend(outcome.conflicting_record_ids)
            return catalogue

        filing_repo.mutate(_stamp_all)
    return FiledJustificanteEnrollmentResult(
        justificante_csvs=tuple(dict.fromkeys(saved_csvs)),
        filing_record_ids=tuple(dict.fromkeys(stamped_record_ids)),
        conflicting_filing_record_ids=tuple(dict.fromkeys(conflicting_record_ids)),
        notices=tuple(notices),
    )


def persist_iva_compensation_history_observations_strict(
    observations: tuple[FiledDeclaracionObservation, ...],
) -> tuple[str, ...]:
    """Persist latest Modelo 303 observations and verify each history row reloads."""
    for observation in observations:
        if observation.modelo != Modelo.M303:
            raise LiveApplicationInputError(
                translated_message="live.errors.iva_history_modelo_303_only",
                context={"modelo": observation.modelo},
            )

    keys: list[str] = []
    history_repo = IvaCompensationHistoryRepository()
    for observation in select_latest_filed_observations_in_history_order(observations):
        if not _is_active_filed_observation(observation):
            continue
        try:
            key = persist_filed_calculation_observation(observation)
        except SedeParseError as exc:
            raise LiveApplicationError(
                translated_message="application.live.filed_observations.errors.iva_history_promotion_failed",
                context={"modelo": Modelo.M303.value, "period": str(observation.period)},
            ) from exc
        if history_repo.load_period(observation.period) is None:
            raise LiveApplicationError(
                translated_message="application.live.filed_observations.errors.iva_history_reload_missing",
                context={"modelo": Modelo.M303.value, "period": str(observation.period)},
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
    return tuple(
        declaration
        for _period, declaration in sorted(
            latest.items(),
            key=lambda item: _filed_observation_history_period_sort_key(item[1].modelo, item[0]),
        )
    )


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
    evidence = filing.external_evidence
    if evidence is None or not is_justificante_backed_external_evidence(evidence.kind):
        return False
    return normalise_aeat_csv(evidence.reference_id) == normalise_aeat_csv(justificante.csv)


def _filed_observation_history_period_sort_key(modelo: str, period: Period) -> tuple[int, str]:
    """Use IVA filing order for Modelo 303 and historic numeric order elsewhere."""
    if modelo == Modelo.M303.value:
        return iva_compensation_period_sort_key(period)
    if period.is_quarterly:
        quarter_ordinal = period.quarter_ordinal
        if quarter_ordinal is None:
            raise LiveApplicationError(
                translated_message="application.live.filed_observations.errors.quarter_ordinal_missing",
                context={"modelo": modelo, "period": period.registry_token},
            )
        return (quarter_ordinal, period.registry_token)
    if period.kind is PeriodKind.MONTHLY:
        return (int(period.registry_token), period.registry_token)
    return (100, period.registry_token)


def _parse_matching_filed_justificante(
    observation: FiledDeclaracionObservation,
    artefact: FiledDeclaracionArtefact,
    store: FiledDeclaracionObservationStore,
) -> _FiledJustificanteParse:
    """Parse one stored justificante artefact, or name the reason there is no receipt.

    The csv equality check compares two independently-sourced values, which is
    the only reason it means anything: ``artefact.source_url`` is the cotejo
    document URL the capture built around the csv AEAT's own cotejo redirect
    supplied, while ``justificante.csv`` is read from the PDF body. Recovering
    the first from that URL keeps the two channels distinct at no
    persistence cost.

    Building ``source_url`` from the receipt's own csv, or from a period-level
    template, would collapse the comparison into a value checked against itself
    and it would pass unconditionally while still reading as a real check.
    """
    storage_ref = artefact.storage_ref
    if storage_ref is None:
        return _FiledJustificanteParse(reason=FiledJustificanteUnreachedReason.UNREADABLE_ARTEFACT)
    try:
        body = store.load_artefact(storage_ref)
    except Exception:
        logger.warning(
            "filed observation: ignored unreadable justificante artefact %s",
            storage_ref,
            exc_info=True,
        )
        return _FiledJustificanteParse(reason=FiledJustificanteUnreachedReason.UNREADABLE_ARTEFACT)
    if len(body) != artefact.byte_count or sha256_hex(body) != artefact.sha256:
        logger.warning(
            "filed observation: ignored justificante artefact %s with mismatched manifest",
            storage_ref,
        )
        return _FiledJustificanteParse(reason=FiledJustificanteUnreachedReason.MANIFEST_MISMATCH)
    try:
        justificante = parse_justificante_bytes(body)
    except Exception:
        logger.warning(
            "filed observation: ignored unparsable justificante artefact %s",
            storage_ref,
            exc_info=True,
        )
        return _FiledJustificanteParse(reason=FiledJustificanteUnreachedReason.UNPARSABLE_PDF)
    try:
        captured_csv = extract_csv_from_url(str(artefact.source_url))
    except SedeParseError:
        logger.warning(
            "filed observation: ignored justificante artefact %s whose source URL carries no recoverable csv",
            storage_ref,
            exc_info=True,
        )
        return _FiledJustificanteParse(reason=FiledJustificanteUnreachedReason.CSV_UNRESOLVABLE)
    if normalise_aeat_csv(captured_csv) != normalise_aeat_csv(justificante.csv):
        logger.warning(
            "filed observation: ignored justificante artefact %s whose receipt csv %s "
            "disagrees with the csv %s its bytes were fetched under",
            storage_ref,
            justificante.csv,
            captured_csv,
        )
        return _FiledJustificanteParse(reason=FiledJustificanteUnreachedReason.CSV_MISMATCH)
    if not _justificante_matches_filed_observation(justificante, observation):
        logger.warning(
            "filed observation: ignored justificante artefact %s that does not match %s/%s/%s",
            storage_ref,
            observation.modelo,
            observation.ejercicio,
            observation.period.registry_token,
        )
        return _FiledJustificanteParse(reason=FiledJustificanteUnreachedReason.FILING_TARGET_MISMATCH)
    return _FiledJustificanteParse(justificante=justificante)


def _unreached_justificante_notice(
    observation: FiledDeclaracionObservation,
    reason: FiledJustificanteUnreachedReason,
) -> Notice:
    """Project one unreached-evidence reason onto the shared notice channel."""
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
        message=(
            f"AEAT filed {observation.modelo} {observation.ejercicio} "
            f"{observation.period.registry_token} carries a justificante artefact that produced no "
            f"evidence ({reason.value})"
        ),
        context={
            "modelo": observation.modelo,
            "filing_year": str(observation.ejercicio),
            "period": observation.period.registry_token,
            "expediente_id": observation.expediente_id,
            "reason": reason.value,
        },
    )


def _justificante_matches_filed_observation(
    justificante: Justificante,
    observation: FiledDeclaracionObservation,
) -> bool:
    return justificante.matches_filing_target(
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
        tax_id=observation.authenticated_identity,
    )


def _filed_justificante_can_stamp_filing(
    justificante: Justificante,
    *,
    observation: FiledDeclaracionObservation,
    filing: ModeloRecord,
) -> bool:
    from ._justificante import expected_tax_id_for_filing_record, justificante_matches_filing_record

    try:
        expected_tax_id = expected_tax_id_for_filing_record(filing)
    except LiveApplicationInputError:
        logger.warning(
            "filed observation: could not resolve profile tax identity for filing record %s",
            filing.filing_record_id,
            exc_info=True,
        )
        return False
    if not same_tax_identifier(observation.authenticated_identity, expected_tax_id):
        return False
    return justificante_matches_filing_record(
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
    """Project one filed observation's register provenance into persisted metadata.

    ``aeat_tipo_solicitud`` carries AEAT's own request-type signal off the
    register row -- the one field that distinguishes an original filing from an
    amendment. It was previously read into the raw observation and then dropped
    here, because the source metadata was built from a fixed key set, so the
    signal existed at capture and was gone by the time anything downstream could
    read it.

    Carrying it is deliberately NOT the same as electing on it: no selection
    logic reads this key, and which identifier an amendment-aware election should
    key on stays an open decision. What changes is that the evidence survives, so
    that decision can be made later against persisted data rather than requiring
    a re-capture.

    The key is omitted rather than written empty when the register row carried no
    request type. An empty string would be indistinguishable from AEAT declaring
    one, and absence here means "the row did not say", which is the honest
    reading.

    The CSV references are written in the shared comparison form, because this
    is the writing side of a key the cross-period clean-state gate reads back
    and compares. Deduplicating on a trim alone left two spellings of one
    identifier surviving as two entries, which is the same second-key defect the
    comparison side was carrying.
    """
    metadata = {
        "aeat_register_status": observation.status.strip().upper(),
        "aeat_expediente_id": observation.expediente_id,
        "authenticated_identity": observation.authenticated_identity.strip().upper(),
    }
    tipo_solicitud = observation.metadata.get("tipo_solicitud", "").strip()
    if tipo_solicitud:
        metadata["aeat_tipo_solicitud"] = tipo_solicitud
    unique_csvs = tuple(dict.fromkeys(normalise_aeat_csv(csv) for csv in justificante_csvs if csv.strip()))
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


filed_observation_identity_key = _filed_observation_identity_key
justificante_csvs_for_observation = _justificante_csvs_for_observation


__all__ = [
    "FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE",
    "FiledJustificanteEnrollmentResult",
    "FiledJustificanteMetadataResult",
    "FiledJustificanteUnreachedReason",
    "enroll_filed_justificante_evidence",
    "latest_declarations_by_period",
    "persist_filed_calculation_observation",
    "persist_filed_justificante_metadata",
    "persist_iva_compensation_history_observations_strict",
    "select_latest_filed_observations_in_history_order",
]
