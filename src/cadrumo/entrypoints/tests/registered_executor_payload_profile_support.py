"""Build the exact requests of the authentication, usage-ratio and user-profile operations."""

from __future__ import annotations

import json
from decimal import Decimal

from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.usage_ratios import save_usage_ratios_with_secure_object_writes
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend

from ...application.auth.certificate_source_operations import (
    register_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from ...application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose
from ...application.user_profile.censal_file_import_operation import CensalFileImportProvenance
from ...application.user_profile.censal_operation import (
    CensalFieldIntent,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
)
from ...application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.record_group_contracts import ProfileRecordGroupKind
from ...application.user_profile.recovery_custody import enroll_profile_recovery
from ...application.user_profile.view_operation import ProfileViewPageKind
from ...core.auth_provider import AuthProviderKind
from ...core.external_constants import OutputLanguage
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.usage_ratios.model import UsageRatioProfile
from ...domain.user_profile.plantilla_media import PlantillaMediaState
from ...domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from .registered_executor_payload_context import PayloadBuilder, PayloadContext, PayloadResult
from .registered_executor_scenario_constants import (
    CREDENTIAL_INPUT,
    OPERATOR_SCOPE_PORTS,
    ROTATED_CREDENTIAL_INPUT,
)
from .registered_executor_seeding_support import profile_baseline, seeded_repeatable_row


def _baselined(ctx: PayloadContext) -> dict[str, object]:
    """Start a manager write from the stored record's compare-and-swap coordinates."""
    return {
        "profile_id": ctx.profile_id,
        **profile_baseline(ctx.profile_id, decode_context=ctx.decode_context),
    }


def _auth_local_read(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "kind": "diagnostics_list"})


def _auth_profile_login(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {"profile_id": ctx.profile_id}, CREDENTIAL_INPUT.encode())


def _auth_profile_passphrase_rotate(ctx: PayloadContext) -> PayloadResult:
    secret = (
        '{"current_passphrase":"'
        + CREDENTIAL_INPUT
        + '","new_passphrase":"'
        + ROTATED_CREDENTIAL_INPUT
        + '","new_passphrase_confirmation":"'
        + ROTATED_CREDENTIAL_INPUT
        + '"}'
    ).encode()
    return ctx.request(ctx.raw_profile_subject, {"profile_id": ctx.profile_id}, secret)


def _auth_credential_save(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {"provider": "clave_permanente"},
        json.dumps({"password": CREDENTIAL_INPUT}).encode(),
    )


def _auth_provider_configure(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {"provider": AuthProviderKind.CERTIFICATE})


def _auth_session_acquire(ctx: PayloadContext) -> PayloadResult:
    # Named rather than defaulted: an omitted provider resolves from
    # the host's deployment settings, which can select Cl@ve and turn
    # this into an identity refusal against whatever DNI the host holds.
    return ctx.request(ctx.raw_profile_subject, {"provider": AuthProviderKind.CERTIFICATE})


def _auth_certificate(ctx: PayloadContext) -> PayloadResult:
    secret: bytes | None = None
    source_name = "supervisor-certificate"
    source_path = ctx.tmp_path / "absent-certificate.p12"
    if ctx.definition_id != "auth.certificate.source.register":
        register_operator_certificate_source(
            name=source_name,
            certificate_path=source_path,
            operation=ctx.operation,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
        )
    values: dict[str, object] = {"profile_id": ctx.profile_id}
    if ctx.definition_id not in {"auth.certificate.source.list", "auth.certificate.source.check"}:
        values["name"] = source_name
    if ctx.definition_id == "auth.certificate.source.register":
        values["certificate_path"] = source_path
    if ctx.definition_id == "auth.certificate.secret.set":
        secret = CREDENTIAL_INPUT.encode()
    elif ctx.definition_id == "auth.certificate.secret.remove":
        set_operator_certificate_source_secret(
            name=source_name,
            secret=SecretStr(CREDENTIAL_INPUT),
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operation=ctx.operation,
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
        )
    return ctx.request(ctx.raw_profile_subject, values, secret)


def _auth_session_end(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {"all_providers": True})


def _ledger_ratios_list(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {"profile_id": ctx.profile_id, "year": 2025})


def _ledger_ratios_eligible(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject,
        {"profile_id": ctx.profile_id, "year": 2025, "output_language": OutputLanguage.EN},
    )


def _ledger_ratios_validate(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {"profile_id": ctx.profile_id})


def _ledger_ratios_set(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject,
        {
            "profile_id": ctx.profile_id,
            "year": 2025,
            "category": "arrendamiento_vivienda_afecto",
            "ratio": "0.5",
        },
    )


def _ledger_ratios_unset(ctx: PayloadContext) -> PayloadResult:
    category = require_spending_category("arrendamiento_vivienda_afecto", authority=ctx.operation)
    save_usage_ratios_with_secure_object_writes(
        UsageRatioProfile(ratios={category: Decimal("0.50")}),
        (),
        bucket_id=str(ctx.profile_id),
    )
    return ctx.request(
        ctx.raw_profile_subject,
        {"profile_id": ctx.profile_id, "category": "arrendamiento_vivienda_afecto"},
    )


def _user_profile_field_mutation(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject,
        {**_baselined(ctx), "path": PROFILE_OUTPUT_LANGUAGE_PATH, "value": "es"},
    )


def _user_profile_patch(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {**_baselined(ctx), "colegio_concertado": True})


def _user_profile_plantilla_media(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject,
        {
            **_baselined(ctx),
            "year": 2025,
            "change": {"kind": "set", "average_workforce": "2.50", "state": PlantillaMediaState.OBSERVED},
        },
    )


def _user_profile_descendants(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {**_baselined(ctx), "descendants": ()})


def _user_profile_ascendants(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {**_baselined(ctx), "ascendants": ()})


def _user_profile_complete_setup(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, _baselined(ctx))


def _user_profile_view(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject,
        {"profile_id": ctx.profile_id, "page_kind": ProfileViewPageKind.FACTS},
    )


def _user_profile_imputation_election_read(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {"profile_id": ctx.profile_id, "tax_year": 2025})


def _user_profile_record_groups(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject, {"profile_id": ctx.profile_id, "group_kind": ProfileRecordGroupKind.RENTAL_PROPERTY}
    )


def _user_profile_imputation_election_set(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {**_baselined(ctx), "tax_year": 2025, "criterion": "devengo"})


def _workbench_generation(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject,
        {"profile_id": ctx.profile_id, "output_language": OutputLanguage.ES},
    )


def _user_profile_repeatable_row_mutation(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject,
        {
            **_baselined(ctx),
            "section_key": "activities",
            "values": ({"field_key": "description", "value": "Consultoria"},),
        },
    )


def _user_profile_repeatable_row_existing(ctx: PayloadContext) -> PayloadResult:
    row_key, baseline = seeded_repeatable_row(
        ctx.profile_id, operation=ctx.operation, decode_context=ctx.decode_context
    )
    values: dict[str, object] = {
        "profile_id": ctx.profile_id,
        **baseline,
        "section_key": "activities",
        "row_key": row_key,
    }
    if ctx.definition_id == "user-profile.repeatable-row-update":
        values["values"] = ({"field_key": "description", "value": "Assessoria"},)
    return ctx.request(ctx.raw_profile_subject, values)


def _user_profile_bundle_export(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.raw_profile_subject,
        {
            "profile_id": ctx.profile_id,
            "destination": ctx.tmp_path / "profile.bundle",
            "purpose": ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        },
        CREDENTIAL_INPUT.encode(),
    )


def _user_profile_logout(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.raw_profile_subject, {"profile_id": ctx.profile_id})


def _user_profile_censo_review(ctx: PayloadContext) -> PayloadResult:
    record = ProfileRecordRepository.for_current_session(
        ctx.profile_id, profile_decode_context=ctx.decode_context
    ).load(ctx.profile_id)
    return ctx.request(
        str(ctx.profile_id),
        {
            "baseline": CensalProfileBaseline.from_record(record),
            "field_intents": tuple(
                CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT) for path in CENSAL_ADOPTABLE_PATHS
            ),
        },
    )


def _user_profile_censo_prepare(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _user_profile_censo_file_import(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "facts": (
                {
                    "path": "contact.fiscal_address",
                    "value": "Calle Mayor 1",
                    "source": CensalFileImportProvenance.ARTEFACT,
                },
            ),
        },
    )


def _user_profile_censo_preview(ctx: PayloadContext) -> PayloadResult:
    record = ProfileRecordRepository.for_current_session(
        ctx.profile_id, profile_decode_context=ctx.decode_context
    ).load(ctx.profile_id)
    return ctx.request(ctx.profile_subject, {"baseline": CensalProfileBaseline.from_record(record)})


def _user_profile_recovery_status(ctx: PayloadContext) -> PayloadResult:
    enroll_profile_recovery(
        profile_id=ctx.profile_id,
        current_passphrase=CREDENTIAL_INPUT,
        recovery_handover=lambda enrollment: enrollment.recovery_key.code,
    )
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


PROFILE_BUILDERS: dict[str, PayloadBuilder] = {
    "auth.local-read": _auth_local_read,
    "auth.profile.login": _auth_profile_login,
    "auth.profile.passphrase-rotate": _auth_profile_passphrase_rotate,
    "auth.credential.save": _auth_credential_save,
    "auth.provider.configure": _auth_provider_configure,
    "auth.session.acquire": _auth_session_acquire,
    "auth.certificate.source.register": _auth_certificate,
    "auth.certificate.source.list": _auth_certificate,
    "auth.certificate.source.select": _auth_certificate,
    "auth.certificate.source.remove": _auth_certificate,
    "auth.certificate.source.check": _auth_certificate,
    "auth.certificate.secret.set": _auth_certificate,
    "auth.certificate.secret.remove": _auth_certificate,
    "ledger.ratios.list": _ledger_ratios_list,
    "ledger.ratios.eligible": _ledger_ratios_eligible,
    "ledger.ratios.validate": _ledger_ratios_validate,
    "ledger.ratios.set": _ledger_ratios_set,
    "ledger.ratios.unset": _ledger_ratios_unset,
    "auth.session.logout": _auth_session_end,
    "auth.session.reset": _auth_session_end,
    "user-profile.field-mutation": _user_profile_field_mutation,
    "user-profile.patch": _user_profile_patch,
    "user-profile.plantilla-media": _user_profile_plantilla_media,
    "user-profile.descendants": _user_profile_descendants,
    "user-profile.ascendants": _user_profile_ascendants,
    "user-profile.complete-setup": _user_profile_complete_setup,
    "user-profile.view": _user_profile_view,
    "user-profile.imputation-election.read": _user_profile_imputation_election_read,
    "user-profile.imputation-election.set": _user_profile_imputation_election_set,
    "user-profile.record-groups": _user_profile_record_groups,
    "workbench.generation": _workbench_generation,
    "user-profile.repeatable-row-mutation": _user_profile_repeatable_row_mutation,
    "user-profile.repeatable-row-update": _user_profile_repeatable_row_existing,
    "user-profile.repeatable-row-remove": _user_profile_repeatable_row_existing,
    "user-profile.bundle-export": _user_profile_bundle_export,
    "user-profile.logout": _user_profile_logout,
    "user-profile.censo-review": _user_profile_censo_review,
    "user-profile.censo-prepare": _user_profile_censo_prepare,
    "user-profile.censo-file-import": _user_profile_censo_file_import,
    "user-profile.censo-preview": _user_profile_censo_preview,
    "user-profile.recovery.status": _user_profile_recovery_status,
}
