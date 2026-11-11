"""Build the exact requests of the live-capture, live-read and export operations."""

from __future__ import annotations

from decimal import Decimal

from ...adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ...adapters.persistence.profile.verify_observations import VerifyObservationRepository
from ...application.live.verify import VerifyService, VerifySurface
from ...core.identity_check_verdict import IdentityCheckVerdict
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.period import Period
from ...core.time.clock import now
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from .registered_executor_payload_context import PayloadBuilder, PayloadContext, PayloadResult
from .registered_executor_seeding_support import (
    CONFORMANCE_PRIOR_YEAR,
    seeded_expedientes_snapshot,
    seeded_justificante_snapshot,
    seeded_notification_document,
    seeded_notifications_snapshot,
)


def _live_sede_view(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "css_width": 1280, "css_height": 800, "scale": 1.0},
    )


def _live_expedientes_capture_single(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject, {"profile_id": ctx.profile_id, "modelo": "303", "year": CONFORMANCE_PRIOR_YEAR}
    )


def _live_expedientes_capture_bulk(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "modelos": ("303",),
            "year_from": CONFORMANCE_PRIOR_YEAR,
            "year_to": CONFORMANCE_PRIOR_YEAR,
        },
    )


def _live_filed_capture_single(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "output_root": ctx.tmp_path / "filed-single",
            "modelo": "303",
            "year": CONFORMANCE_PRIOR_YEAR,
            "period": "1T",
        },
    )


def _live_filed_capture_bulk(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "output_root": ctx.tmp_path / "filed-bulk",
            "year_from": CONFORMANCE_PRIOR_YEAR,
            "year_to": CONFORMANCE_PRIOR_YEAR,
            "modelos": ("303",),
        },
    )


def _live_filed_capture_source(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "output_root": ctx.tmp_path / "filed-source",
            "modelo": "303",
            "year": CONFORMANCE_PRIOR_YEAR,
            "period": "1T",
        },
    )


def _live_filed_list(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "modelo": "303",
            "year_from": CONFORMANCE_PRIOR_YEAR,
            "year_to": CONFORMANCE_PRIOR_YEAR,
        },
    )


def _live_profile_only(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _live_justificante_list(ctx: PayloadContext) -> PayloadResult:
    seeded_justificante_snapshot(ctx.profile_id)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _live_justificante_capture(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "modelo": "130", "year": CONFORMANCE_PRIOR_YEAR, "period": "1T"},
    )


def _live_justificante_show(ctx: PayloadContext) -> PayloadResult:
    snapshot = seeded_justificante_snapshot(ctx.profile_id)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "snapshot_id": snapshot.snapshot_id})


def _live_expedientes_seeded_profile_only(ctx: PayloadContext) -> PayloadResult:
    seeded_expedientes_snapshot(ctx.profile_id)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _live_expedientes_show(ctx: PayloadContext) -> PayloadResult:
    snapshot = seeded_expedientes_snapshot(ctx.profile_id)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "snapshot_id": snapshot.snapshot_id})


def _live_notifications_seeded_profile_only(ctx: PayloadContext) -> PayloadResult:
    seeded_notifications_snapshot(ctx.profile_id)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _live_notifications_show(ctx: PayloadContext) -> PayloadResult:
    snapshot = seeded_notifications_snapshot(ctx.profile_id)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "snapshot_id": snapshot.snapshot_id})


def _live_notifications_document_view(ctx: PayloadContext) -> PayloadResult:
    record = seeded_notification_document(ctx.profile_id)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "certificado_id": record.certificado_id})


def _live_notifications_document_history(ctx: PayloadContext) -> PayloadResult:
    seeded_notification_document(ctx.profile_id)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _live_notifications_document_capture(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "certificado_id": "2699101808461"})


def _live_verify_remote(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "nif": "12345678Z"})


def _live_verify_recorded(ctx: PayloadContext) -> PayloadResult:
    observation = VerifyService(persistence=VerifyObservationRepository(bucket_id=str(ctx.profile_id))).record(
        bucket_id=str(ctx.profile_id),
        surface=VerifySurface.NIF_IVA,
        nif="12345678Z",
        verdict=IdentityCheckVerdict.VALID,
        checked_at=now(),
    )
    values: dict[str, object] = {"profile_id": ctx.profile_id}
    if ctx.definition_id == "live.verify.view":
        values["observation_id"] = observation.observation_id
    elif ctx.definition_id == "live.verify.latest":
        values.update(surface=VerifySurface.NIF_IVA, nif="12345678Z")
    return ctx.request(ctx.profile_subject, values)


def _live_filed_history_pull(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "output_root": ctx.tmp_path / "filed-history", "dry_run": True},
    )


def _live_iva_wallet_history(ctx: PayloadContext) -> PayloadResult:
    period = Period.from_year_and_code(CONFORMANCE_PRIOR_YEAR, "1T")
    history_state = IvaCompensationPeriodState(
        provenance=IvaCompensationStateProvenance.APP_FILING,
        taxpayer_nif="12345678Z",
        filing_year=CONFORMANCE_PRIOR_YEAR,
        period=period,
        registry_snapshot_ref=ctx.operation.snapshot(
            "303", filing_year=CONFORMANCE_PRIOR_YEAR, period=period.registry_token
        ).snapshot_ref,
        presented_at=now(),
        prior_pending_amount=Decimal("0"),
        applied_amount=Decimal("0"),
        pending_for_later_amount=Decimal("40.00"),
        period_result_amount=Decimal("-40.00"),
        final_result_amount=Decimal("-40.00"),
        generated_amount=Decimal("40.00"),
        available_end_amount=Decimal("40.00"),
        source_observation_key="conformance:iva-history:2025:1T",
    )
    IvaCompensationHistoryRepository().save_period(history_state)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "as_of_year": CONFORMANCE_PRIOR_YEAR})


def _live_iva_wallet_capture(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "target_year": CONFORMANCE_PRIOR_YEAR, "target_period": "1T"},
    )


def _live_iva_wallet_evidence_capture(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "output_root": ctx.tmp_path / "iva-evidence",
            "year_from": CONFORMANCE_PRIOR_YEAR,
            "year_to": CONFORMANCE_PRIOR_YEAR,
            "target_year": CONFORMANCE_PRIOR_YEAR,
            "target_period": "1T",
        },
    )


def _live_iva_wallet_history_capture(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "output_root": ctx.tmp_path / "iva-history-capture",
            "year_from": CONFORMANCE_PRIOR_YEAR,
            "year_to": CONFORMANCE_PRIOR_YEAR,
        },
    )


def _export_google_sheets(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject,
        {
            "profile_id": ctx.profile_id,
            "modelo": "130",
            "filing_year": CONFORMANCE_PRIOR_YEAR,
            "period": "1T",
            "dry_run": False,
        },
    )


LIVE_BUILDERS: dict[str, PayloadBuilder] = {
    "live.sede.view": _live_sede_view,
    "live.expedientes.capture.single": _live_expedientes_capture_single,
    "live.expedientes.capture.bulk": _live_expedientes_capture_bulk,
    "live.filed-capture.single": _live_filed_capture_single,
    "live.filed-capture.bulk": _live_filed_capture_bulk,
    "live.filed-capture.source": _live_filed_capture_source,
    "live.filed-list": _live_filed_list,
    "live.filed-discover": _live_profile_only,
    "live.justificante.list": _live_justificante_list,
    "live.justificante.capture": _live_justificante_capture,
    "live.justificante.show": _live_justificante_show,
    "live.expedientes.list": _live_expedientes_seeded_profile_only,
    "live.expedientes.show": _live_expedientes_show,
    "live.expedientes.latest": _live_expedientes_seeded_profile_only,
    "live.notifications.list": _live_notifications_seeded_profile_only,
    "live.notifications.latest": _live_notifications_seeded_profile_only,
    "live.notifications.show": _live_notifications_show,
    "live.notifications.document.view": _live_notifications_document_view,
    "live.notifications.document.history": _live_notifications_document_history,
    "live.notifications.capture": _live_profile_only,
    "live.notifications.document.capture": _live_notifications_document_capture,
    "live.verify.nif-iva": _live_verify_remote,
    "live.verify.tgvi": _live_verify_remote,
    "live.sync.status": _live_profile_only,
    "live.verify.list": _live_verify_recorded,
    "live.verify.view": _live_verify_recorded,
    "live.verify.latest": _live_verify_recorded,
    "live.filed-history.pull": _live_filed_history_pull,
    "live.iva-wallet.history": _live_iva_wallet_history,
    "live.iva-wallet.capture": _live_iva_wallet_capture,
    "live.iva-wallet.evidence-capture": _live_iva_wallet_evidence_capture,
    "live.iva-wallet.history-capture": _live_iva_wallet_history_capture,
    "export.google-sheets": _export_google_sheets,
}
