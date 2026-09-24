"""Persist filed AEAT observations into calculation-history repositories.

Filed Sede rows are promoted to registry-grounded :class:`CasillaObservation`
records in the official observation layer, and every matching justificante is
reconciled with the period's filing chain through the single reconciliation
service; nothing here stamps AEAT acceptance itself.

The module treats AEAT live captures as official external evidence only after
the captured justificante matches the filed observation. An all-numeric casilla
manifest lets the reconciliation compare or record AEAT's content; justificante
metadata alone never claims casilla completeness.

See Also:
    :class:`~ExternalEvidenceKind`
        Closed evidence-kind catalogue; live captures stamp
        ``AEAT_LIVE_CAPTURE``.
    :class:`cadrumo.application.calculations.observations_repository.CalculationObservationRepositoryProtocol`
        Repository that receives the registry-grounded filed-declaration
        observations consumed by cross-period resolvers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from ..calculations.observations_repository import ObservationSourceKind, observation_key
from ...core.aeat_csv import normalise_aeat_csv
from ...core.casilla_id import CasillaId
from ...core.hashing import sha256_hex
from ...core.identity.tax_id import same_tax_identifier
from ...core.json_contract import Notice, NoticeSeverity
from ...core.logging import get_logger
from ...core.modelo import Modelo
from ...core.period import Period, PeriodKind
from ...domain.iva_compensation.carry_forward import iva_compensation_period_sort_key
from ...domain.justificante.schema import Justificante
from ...domain.modelos.filing_record import (
    AeatRegisterRef,
    ExternalEvidenceKind,
    declaration_kind_for_tipo_solicitud,
)
from ..modelo.action_errors import ExternalModeloImportError
from ..modelo.external_import_actions import ExternalFilingBaselineSource, external_filing_source_casillas
from ..modelo.filing_chain_reconciliation import (
    AeatRegisterEntry,
    FilingReconciliationOutcome,
    FilingReconciliationResult,
)
from .errors import (
    LiveApplicationError,
    LiveApplicationInputError,
    LiveReadPrecondition,
    live_read_no_recovery_verdict,
)
from .filed_observation_ports import (
    FiledDeclarationProtocol,
    FiledObservationArtefactProtocol,
    FiledObservationPersistencePorts,
    FiledObservationProtocol,
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
class FiledJustificanteEnrollmentResult:
    """Justificante metadata enrolled from filed history and the chain decisions it drove."""

    justificante_csvs: tuple[str, ...] = ()
    filing_record_ids: tuple[str, ...] = ()
    conflicting_filing_record_ids: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()
    reconciliation_results: tuple[FilingReconciliationResult, ...] = ()


def persist_filed_calculation_observation(
    observation: FiledObservationProtocol,
    *,
    ports: FiledObservationPersistencePorts,
    justificante_csvs: tuple[str, ...] = (),
) -> str:
    """Promote one AEAT filed-declaration observation into calculation history.

    The persisted row is a registry-grounded
    :class:`cadrumo.domain.calculations.registry.bindings.RegistryModeloObservation`
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
    registry_observation = ports.transformation.registry_observation(observation)
    repo = ports.calculation_repository
    payload = repo.prepare_observation_envelope(
        registry_observation,
        source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        stamped_revision_id=observation.registry_snapshot_ref.revision_id,
        captured_at=observation.presented_at,
        source_metadata=filed_observation_source_metadata(observation, justificante_csvs=justificante_csvs),
        # Passed separately from source_metadata, and that is the whole point:
        # the metadata projection is built from a fixed key set, so a header
        # fact routed through it would be dropped here exactly as it was before.
        source_headers=observation.headers,
        # Canonical ingress: official evidence must recover its one typed
        # disposition from the submitted-file header before it can participate
        # in M303 carry. No compensación default is admitted here.
    )
    if observation.modelo == Modelo("303"):
        source_artefact_sha256 = next(
            (artefact.sha256 for artefact in observation.artefacts if artefact.kind == "submitted_file"),
            None,
        )
        ports.iva_observation_persistence.persist(
            observation_repository=repo,
            history_repository=ports.iva_history_repository,
            envelope=payload,
            taxpayer_nif=observation.authenticated_identity,
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
    observations: tuple[FiledObservationProtocol, ...],
) -> tuple[FiledObservationProtocol, ...]:
    """Return the latest observation per (modelo, year, period) in deterministic history order.

    "Latest" is by :func:`_filed_observation_rank` (an ALTA registration beats a
    BAJA, then most-recent ``presented_at``, then ``expediente_id``). History order
    is :func:`_filed_observation_history_period_sort_key` (Modelo 303 IVA fiscal
    order, quarterly/monthly numeric order elsewhere). This is the single
    selection-and-ordering authority shared by the calculation-history persistence
    below and the filed-capture finalizer, so every capture route persists the same
    observations in the same order and cannot drift.
    """
    latest: dict[tuple[str, int, Period], FiledObservationProtocol] = {}
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


def enroll_filed_justificante_evidence(
    observation: FiledObservationProtocol,
    *,
    ports: FiledObservationPersistencePorts,
    bucket_id: str,
) -> FiledJustificanteEnrollmentResult:
    """Persist matching justificante metadata and reconcile the filing chain with it.

    Every parsed receipt that matches the observation becomes one AEAT register
    entry for :func:`~cadrumo.application.modelo.filing_chain_reconciliation.reconcile_aeat_register_entry`,
    carrying the observation's numeric casillas when all of them are numeric.
    A chain whose in-force entry belongs to another taxpayer identity is left
    untouched.

    Returns:
        A :class:`FiledJustificanteEnrollmentResult` of saved CSVs, the chain
        entries the reconciliations settled on, contradicted pending entries,
        and every reconciliation result.
    """
    if not _is_active_filed_observation(observation):
        return FiledJustificanteEnrollmentResult()

    saved_csvs: list[str] = []
    notices: list[Notice] = []
    receipts: list[tuple[Justificante, FiledObservationArtefactProtocol]] = []
    for artefact in observation.artefacts:
        if artefact.kind != "justificante_pdf" or artefact.storage_ref is None:
            continue
        parsed = _parse_matching_filed_justificante(observation, artefact, ports)
        if parsed.justificante is None:
            if parsed.reason is not None:
                notices.append(_unreached_justificante_notice(observation, parsed.reason))
            continue
        # The receipt lands before any chain entry cites it, so a failure between
        # the two leaves an orphan receipt rather than a filing record pointing at
        # evidence that does not load.
        ports.justificante_repository.save(parsed.justificante)
        saved_csvs.append(parsed.justificante.csv)
        receipts.append((parsed.justificante, artefact))

    results: list[FilingReconciliationResult] = []
    if receipts and _chain_identity_matches(observation, bucket_id=bucket_id, ports=ports):
        for justificante, artefact in receipts:
            lexicals, casilla_values = _register_casillas(observation, receipt_csv=justificante.csv)
            results.append(
                ports.filing_reconciliation.reconcile(
                    _register_entry(
                        observation,
                        justificante,
                        bucket_id=bucket_id,
                        casilla_values=casilla_values,
                        source_lexicals=lexicals,
                    ),
                    actor="aeat-filed-history",
                    clock=artefact.captured_at,
                ),
            )
    return FiledJustificanteEnrollmentResult(
        justificante_csvs=tuple(dict.fromkeys(saved_csvs)),
        filing_record_ids=tuple(
            dict.fromkeys(
                result.filing_record_id
                for result in results
                if result.filing_record_id is not None
                and result.outcome is not FilingReconciliationOutcome.UNVERIFIABLE
            ),
        ),
        conflicting_filing_record_ids=tuple(
            dict.fromkeys(
                record_id
                for result in results
                if result.outcome is FilingReconciliationOutcome.CONTRADICTED
                for record_id in result.affected_filing_record_ids
            ),
        ),
        notices=tuple(notices),
        reconciliation_results=tuple(results),
    )


def _chain_identity_matches(
    observation: FiledObservationProtocol,
    *,
    bucket_id: str,
    ports: FiledObservationPersistencePorts,
) -> bool:
    """Return whether the period's in-force entry belongs to the authenticated taxpayer."""
    from .justificante import expected_tax_id_for_filing_record

    current = ports.filing_repository.load().current_for(
        bucket_id=bucket_id,
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
    )
    if current is None:
        return True
    try:
        expected_tax_id = expected_tax_id_for_filing_record(current)
    except LiveApplicationInputError:
        logger.warning(
            "filed observation: could not resolve profile tax identity for filing record %s",
            current.filing_record_id,
            exc_info=True,
        )
        return False
    return same_tax_identifier(observation.authenticated_identity, expected_tax_id)


def _register_casillas(
    observation: FiledObservationProtocol,
    *,
    receipt_csv: str,
) -> tuple[dict[CasillaId, str] | None, dict[CasillaId, Decimal] | None]:
    """Return the complete numeric content AEAT holds for the presentation, when the capture carries it.

    A capture with a non-numeric casilla, no casillas, or Modelo 303 (whose
    content is recorded only with its filing-instance evidence) yields no
    content. An incomplete numeric manifest is refused rather than recorded.
    """
    if (
        not observation.casillas
        or observation.modelo == Modelo("303")
        or any(casilla.value_kind.value != "numeric" for casilla in observation.casillas)
    ):
        return None, None
    lexicals = {casilla.casilla_id: casilla.value for casilla in observation.casillas}
    if len(lexicals) != len(observation.casillas):
        raise LiveApplicationInputError(
            translated_message="application.live.filed_observations.errors.duplicate_casilla",
            context={
                "modelo": observation.modelo,
                "ejercicio": observation.ejercicio,
                "period": observation.period.registry_token,
            },
        )
    source = ExternalFilingBaselineSource(
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
        evidence_kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
        evidence_reference_id=receipt_csv,
        tax_id=observation.authenticated_identity,
        casilla_lexicals=lexicals,
    )
    try:
        return external_filing_source_casillas(source)
    except ExternalModeloImportError as exc:
        raise LiveApplicationError(
            translated_message=exc.translated_message,
            context={"operation": "prepare_filed_register_casillas", "cause_type": type(exc).__name__},
        ) from exc


def _register_entry(
    observation: FiledObservationProtocol,
    justificante: Justificante,
    *,
    bucket_id: str,
    casilla_values: dict[CasillaId, Decimal] | None,
    source_lexicals: dict[CasillaId, str] | None,
) -> AeatRegisterEntry:
    tipo_solicitud = observation.metadata.get("tipo_solicitud", "").strip() or None
    presented_at = observation.presented_at if observation.presented_at.tzinfo is not None else None
    return AeatRegisterEntry(
        bucket_id=bucket_id,
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
        register=AeatRegisterRef(
            expediente_id=observation.expediente_id,
            csv=justificante.csv,
            justificante_number=justificante.presentation_id,
            tipo_solicitud=tipo_solicitud,
            presented_at=presented_at,
        ),
        evidence_kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
        tax_id=observation.authenticated_identity,
        declared_kind=declaration_kind_for_tipo_solicitud(tipo_solicitud),
        justificante=justificante,
        casilla_values=casilla_values,
        source_lexicals=source_lexicals,
    )


def persistiva_compensation_history_observations_strict(
    observations: tuple[FiledObservationProtocol, ...],
    *,
    ports: FiledObservationPersistencePorts,
) -> tuple[str, ...]:
    """Persist latest Modelo 303 observations and verify each history row reloads."""
    for observation in observations:
        if observation.modelo != Modelo("303"):
            raise LiveApplicationInputError(
                translated_message="live.errors.iva_history_modelo_303_only",
                context={"modelo": observation.modelo},
            )

    keys: list[str] = []
    history_repo = ports.iva_history_repository
    for observation in select_latest_filed_observations_in_history_order(observations):
        if not _is_active_filed_observation(observation):
            continue
        try:
            key = persist_filed_calculation_observation(observation, ports=ports)
        except LiveApplicationError as exc:
            raise LiveApplicationError(
                translated_message="application.live.filed_observations.errors.iva_history_promotion_failed",
                context={"modelo": Modelo("303").value, "period": str(observation.period)},
            ) from exc
        if history_repo.load_period(observation.period) is None:
            raise LiveApplicationError(
                translated_message="application.live.filed_observations.errors.iva_history_reload_missing",
                context={"modelo": Modelo("303").value, "period": str(observation.period)},
            )
        keys.append(key)
    return tuple(keys)


def latest_declarations_by_period(
    declarations: tuple[FiledDeclarationProtocol, ...],
) -> tuple[FiledDeclarationProtocol, ...]:
    """Return the latest period-bearing declaration row per period."""
    latest: dict[Period, FiledDeclarationProtocol] = {}
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


def _filed_observation_history_period_sort_key(modelo: str, period: Period) -> tuple[int, str]:
    """Use IVA filing order for Modelo 303 and historic numeric order elsewhere."""
    if modelo == Modelo("303").value:
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
    observation: FiledObservationProtocol,
    artefact: FiledObservationArtefactProtocol,
    ports: FiledObservationPersistencePorts,
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
        body = ports.observation_persistence.load_artefact(storage_ref)
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
        justificante = ports.parser.parse_justificante(body)
    except Exception:
        logger.warning(
            "filed observation: ignored unparsable justificante artefact %s",
            storage_ref,
            exc_info=True,
        )
        return _FiledJustificanteParse(reason=FiledJustificanteUnreachedReason.UNPARSABLE_PDF)
    try:
        captured_csv = ports.parser.csv_from_source_url(str(artefact.source_url))
    except Exception:
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
    observation: FiledObservationProtocol,
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
    observation: FiledObservationProtocol,
) -> bool:
    return justificante.matches_filing_target(
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
        tax_id=observation.authenticated_identity,
    )


def _is_active_filed_observation(observation: FiledObservationProtocol) -> bool:
    return observation.status.strip().upper() == "ALTA"


def _filed_observation_rank(observation: FiledObservationProtocol) -> tuple[bool, datetime, str]:
    return (_is_active_filed_observation(observation), observation.presented_at, observation.expediente_id)


def filed_observation_source_metadata(
    observation: FiledObservationProtocol,
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


def _filed_observation_identity_key(observation: FiledObservationProtocol) -> tuple[str, int, str, str]:
    return (
        observation.modelo,
        observation.ejercicio,
        observation.period.registry_token,
        observation.expediente_id,
    )


def _justificante_csvs_for_observation(
    observation: FiledObservationProtocol,
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
    "FiledJustificanteUnreachedReason",
    "enroll_filed_justificante_evidence",
    "filed_observation_source_metadata",
    "latest_declarations_by_period",
    "persist_filed_calculation_observation",
    "persistiva_compensation_history_observations_strict",
    "select_latest_filed_observations_in_history_order",
]
