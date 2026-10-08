"""Canonical audit evidence for an export recorded in a disposable sandbox.

An audit event correctly names its real absolute destination. Its hash can only
be made portable after verifying that complete event, never by masking an ID.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, JsonValue, ValidationError

from cadrumo.application.export.tabular import ExportSerializationFormat
from cadrumo.application.ledger.actions_export import derive_ledger_export_id
from cadrumo.application.modelo.export_projection import (
    ModeloIvaWalletDecisionPublicProvenance,
    ModeloPriorDomiciliationPublicProvenance,
)
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.hashing import canonical_json_bytes, content_hash_hex
from cadrumo.core.hex import Hex64Str
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType, derive_bucket_event_id
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.modelos.work_unit import derive_work_unit_id

_EVIDENCE_PROOF_DESTINATION = "<verified-export-destination>"


class _RowIdentity(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    transaction_id: Hex64Str


class _ExportEvidence(BaseModel):
    """Only the finite public facts used by the canonical export event."""

    model_config = STRICT_FROZEN_CONFIG
    bucket_id: str
    export_id: Hex64Str
    export_format: ExportSerializationFormat
    sha256: Hex64Str
    output_path: str
    row_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)
    bucket_event_ids: list[Hex64Str] = Field(min_length=1, max_length=1)
    rows: list[_RowIdentity]


class _ModeloExportEvidence(BaseModel):
    """Public BOE and XML receipt coordinates that reconstruct their audit payload.

    Account and other unprojected payload branches cannot pass the exact event
    derivation below; their event IDs remain visible in comparison.
    """

    model_config = STRICT_FROZEN_CONFIG
    operation: Literal["modelo.export"]
    bucket_id: str
    work_unit_id: Hex64Str
    calculation_revision_id: Hex64Str
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int
    period: PublicPeriod
    output_path: str
    byte_size: int = Field(ge=0)
    file_sha256: Hex64Str
    format: Literal["fichero-boe", "xml-dictionary"]
    bucket_event_id: Hex64Str
    resolved_result_disposition: ResultDisposition | None
    payment_election: PaymentElection | None
    refund_election: RefundElection | None
    prior_domiciliation_election: ModeloPriorDomiciliationPublicProvenance
    iva_wallet_decision_provenance: ModeloIvaWalletDecisionPublicProvenance | None = None


def _option(argv: tuple[str, ...], name: str) -> str | None:
    value = None
    for index, argument in enumerate(argv):
        if argument == name and index + 1 < len(argv):
            value = argv[index + 1]
        elif argument.startswith(name + "="):
            value = argument[len(name) + 1 :]
    return value


def _export_work_unit_argument(argv: tuple[str, ...]) -> str | None:
    """Read only the enrolled exact-ID position immediately after the export verb."""
    for index in range(len(argv) - 2):
        if argv[index : index + 3] == ("app", "modelo", "export"):
            tail = argv[index + 3 :]
            return tail[0] if tail and not tail[0].startswith("--") else None
    return None


def _modelo_export_selector_matches(
    evidence: _ModeloExportEvidence,
    *,
    argv: tuple[str, ...],
    profile_id: str,
    registry_revision_id: RevisionId | None = None,
) -> bool:
    """Bind either enrolled selector form to the receipt's actual filing target.

    Exact IDs replace the visible flags only when both IDs agree and the work
    identity can be independently derived from the law-selected registry revision.
    """
    coordinates = tuple(_option(argv, name) for name in ("--modelo", "--year", "--period"))
    calculation_revision = _option(argv, "--revision")
    if evidence.period.filing_year != evidence.filing_year:
        return False
    if calculation_revision is not None and calculation_revision != evidence.calculation_revision_id:
        return False
    work_unit = _export_work_unit_argument(argv)
    if work_unit is None:
        return coordinates == (
            evidence.modelo,
            str(evidence.filing_year),
            evidence.period.to_period().registry_token,
        )
    if (
        any(value is not None for value in coordinates)
        or _option(argv, "--registry-revision") is not None
        or calculation_revision is None
        or work_unit != evidence.work_unit_id
        or registry_revision_id is None
    ):
        return False
    return evidence.work_unit_id == derive_work_unit_id(
        bucket_id=profile_id,
        modelo=evidence.modelo,
        filing_year=evidence.filing_year,
        period=evidence.period.to_period(),
        revision_id=registry_revision_id,
    )


def normalise_ledger_export_evidence(
    document: dict[str, JsonValue],
    *,
    argv: tuple[str, ...],
    profile_id: str,
    instant: datetime,
    workdir: str,
    destination_token: str,
) -> dict[str, JsonValue]:
    """Rename a verified sandbox destination in the event's canonical hash.

    Invalid, foreign or incomplete evidence remains byte-exact. Every public
    result field and the command arguments still participate in comparison.
    """
    result = document.get("result")
    if document.get("command") != "ledger.export" or not isinstance(result, dict):
        return document
    authored = _option(argv, "--output")
    if authored is None or result.get("output_path") != str(Path(authored)):
        return document
    root = Path(workdir)
    destination = (root / authored).absolute()
    try:
        relative = destination.resolve().relative_to(root.resolve())
        rows = result.get("rows")
        if not isinstance(rows, list):
            return document
        identities = []
        for row in rows:
            if not isinstance(row, dict):
                return document
            identities.append({"transaction_id": row.get("transaction_id")})
        evidence = _ExportEvidence.model_validate_json(
            canonical_json_bytes(
                {
                    **{key: result[key] for key in _ExportEvidence.model_fields if key != "rows"},
                    "rows": identities,
                },
            ),
        )
    except (KeyError, ValueError, ValidationError, OSError):
        return document
    if evidence.bucket_id not in {profile_id, "<bucket-id>"} or evidence.row_count != len(evidence.rows):
        return document
    ids = tuple(row.transaction_id for row in evidence.rows)
    if evidence.export_id != derive_ledger_export_id(
        bucket_id=profile_id, export_format=evidence.export_format.value, sha256=evidence.sha256, transaction_ids=ids
    ):
        return document
    include_inactive = False
    for argument in argv:
        if argument in {"--include-inactive", "--no-include-inactive"}:
            include_inactive = argument == "--include-inactive"
    payload = {
        "source_command": "aeat app ledger export",
        "export_format": evidence.export_format.value,
        "include_inactive": str(include_inactive).lower(),
        "row_count": str(evidence.row_count),
        "byte_size": str(evidence.byte_size),
        "sha256": evidence.sha256,
        "output_path": str(destination),
        "transaction_ids_sha256": content_hash_hex(ids),
        "first_transaction_id": ids[0] if ids else "",
        "last_transaction_id": ids[-1] if ids else "",
    }

    def event_id(event_payload: dict[str, str]) -> str:
        return derive_bucket_event_id(
            bucket_id=profile_id,
            event_type=BucketEventType.LEDGER_TRANSACTION_EXPORTED,
            occurred_at=instant,
            actor=_option(argv, "--actor") or profile_id,
            object_type=BucketEventObjectType.LEDGER_EXPORT,
            object_id=evidence.export_id,
            payload=event_payload,
        )

    if evidence.bucket_event_ids != [event_id(payload)]:
        return document
    canonical = event_id({**payload, "output_path": destination_token + "/" + relative.as_posix()})
    return {**document, "result": {**result, "bucket_event_ids": [canonical]}}


def normalise_modelo_export_evidence(
    document: dict[str, JsonValue],
    *,
    argv: tuple[str, ...],
    profile_id: str,
    instant: datetime,
    workdir: str,
    destination_token: str,
) -> dict[str, JsonValue]:
    """Tokenize only a destination bound to the complete real modelo event.

    This preserves the real production event identity. Invalid evidence,
    outside destinations and unprojected payload branches stay unnormalized.
    """
    result = document.get("result")
    if document.get("command") != "modelo.export" or not isinstance(result, dict):
        return document
    authored = _option(argv, "--output")
    if authored is None:
        return document
    try:
        root = Path(workdir).resolve()
        destination = (root / authored).resolve()
        relative = destination.relative_to(root)
        evidence = _ModeloExportEvidence.model_validate_json(
            canonical_json_bytes({key: result[key] for key in _ModeloExportEvidence.model_fields if key in result}),
        )
    except (ValueError, ValidationError, OSError):
        return document
    if evidence.bucket_id not in {profile_id, "<bucket-id>"} or evidence.output_path != str(destination):
        return document
    registry_revision_id = None
    if _export_work_unit_argument(argv) is not None:
        from cadrumo.application.modelo.work_addressing import law_selected_revision_for_work_target
        from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

        try:
            with bundled_indexed_authority().operation() as operation:
                registry_revision_id = law_selected_revision_for_work_target(
                    modelo=evidence.modelo,
                    filing_year=evidence.filing_year,
                    period=evidence.period.to_period(),
                    operation=operation,
                )
        except CadrumoError:
            return document
    if not _modelo_export_selector_matches(
        evidence, argv=argv, profile_id=profile_id, registry_revision_id=registry_revision_id
    ):
        return document
    actor = _option(argv, "--actor") or document.get("active_profile") or profile_id
    if not isinstance(actor, str):
        return document
    payload = {
        "calculation_revision_id": evidence.calculation_revision_id,
        "work_unit_id": evidence.work_unit_id,
        "output_path": evidence.output_path,
        "byte_size": str(evidence.byte_size),
        "file_sha256": evidence.file_sha256,
        "format": evidence.format,
        "modelo": evidence.modelo,
        "filing_year": str(evidence.filing_year),
        "period": evidence.period.to_period().registry_token,
        "prior_domiciliation_election": evidence.prior_domiciliation_election.election.value,
    }
    disposition = evidence.resolved_result_disposition
    if disposition is not None:
        payload["resolved_result_disposition"] = disposition.value
    if disposition in {
        ResultDisposition.INGRESO,
        ResultDisposition.DOMICILIACION,
        ResultDisposition.CUENTA_CORRIENTE_INGRESO,
    }:
        if evidence.payment_election is None:
            return document
        payload["payment_election"] = evidence.payment_election.value
    if disposition in {
        ResultDisposition.COMPENSACION,
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
    }:
        if evidence.refund_election is None:
            return document
        payload["refund_election"] = evidence.refund_election.value
    prior = evidence.prior_domiciliation_election
    if prior.baseline_filing_record_id is not None:
        payload.update(
            {
                "prior_domiciliation_baseline_filing_record_id": prior.baseline_filing_record_id,
                "prior_domiciliation_baseline_evidence_reference_id": prior.baseline_evidence_reference_id or "",
                "prior_domiciliation_baseline_result_disposition": (
                    prior.baseline_result_disposition.value if prior.baseline_result_disposition is not None else ""
                ),
                "prior_domiciliation_baseline_source_header_locator": prior.baseline_source_header_locator or "",
            },
        )
    wallet = evidence.iva_wallet_decision_provenance
    if wallet is not None:
        payload.update(
            {
                "iva_wallet_decision_ref": wallet.decision_ref,
                "iva_wallet_selected_authority": wallet.selected_authority,
                "iva_wallet_divergence": wallet.divergence,
                "iva_wallet_target_year": str(wallet.target_year),
                "iva_wallet_target_period": wallet.target_period.to_period().registry_token,
                "iva_wallet_authority_source_kinds": ",".join(wallet.authority_source_kinds),
                "iva_wallet_authority_source_refs": ",".join(wallet.authority_source_refs),
            },
        )

    def event_id(event_payload: dict[str, str]) -> str:
        return derive_bucket_event_id(
            bucket_id=profile_id,
            event_type=BucketEventType.MODELO_EXPORTED,
            occurred_at=instant,
            actor=actor,
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id=evidence.calculation_revision_id,
            payload=event_payload,
        )

    if evidence.bucket_event_id != event_id(payload):
        return document
    canonical = event_id({**payload, "output_path": destination_token + "/" + relative.as_posix()})
    return {**document, "result": {**result, "bucket_event_id": canonical}}


def modelo_export_evidence_problem(
    document: dict[str, JsonValue],
    *,
    argv: tuple[str, ...],
    profile_id: str,
    instant: datetime,
    workdir: str,
) -> str | None:
    """Verify live BOE and XML evidence before release-dependent fields are masked.

    The central release mask legitimately permits another product version's
    file digest. It cannot establish that this run's digest and event describe
    its actual artifact. Unsupported private event branches remain an explicit
    evidence failure rather than disappearing through that mask.
    """
    result = document.get("result")
    if (
        document.get("command") != "modelo.export"
        or not isinstance(result, dict)
        or result.get("format") not in ("fichero-boe", "xml-dictionary")
    ):
        return None
    label = "fichero" if result["format"] == "fichero-boe" else "XML"
    verified = normalise_modelo_export_evidence(
        document,
        argv=argv,
        profile_id=profile_id,
        instant=instant,
        workdir=workdir,
        destination_token=_EVIDENCE_PROOF_DESTINATION,
    )
    if verified is document:
        return f"{label} receipt does not prove its canonical export event and sandbox destination"
    try:
        evidence = _ModeloExportEvidence.model_validate_json(
            canonical_json_bytes({key: result[key] for key in _ModeloExportEvidence.model_fields if key in result}),
        )
        artifact = Path(evidence.output_path)
        if artifact.stat().st_size != evidence.byte_size:
            return f"{label} artifact size differs from its export receipt"
        with artifact.open("rb") as stream:
            actual_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    except (ValidationError, ValueError, OSError):
        return f"{label} export artifact cannot be verified"
    if actual_digest != evidence.file_sha256:
        return f"{label} artifact digest differs from its export receipt"
    return None
