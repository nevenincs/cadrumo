"""The wording of the installation area, in the language now on screen.

An act or a request member that has no wording yet is named by its own stable
token, so a newly added act is offered at once and reads as what the runtime
calls it until it is worded.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext

from ....application.runtime.installation_requests import InstallationAct
from ....core.config import override_settings
from ....core.i18n.render import tr
from .acts import InstallationFamily


def worded_in(locale: str | None) -> AbstractContextManager[object]:
    """Word whatever is rendered inside the scope in ``locale``.

    ``None`` keeps the language already on screen. The page that creates the
    first profile chooses its own language before any profile holds one, and
    an area opened from it has to answer in that language. The scope is
    entered only around synchronous rendering, never across a wait.
    """
    return nullcontext() if locale is None else override_settings(cadrumo_output_language=locale)


def family_label(family: InstallationFamily) -> str:
    """Name one family of acts."""
    match family:
        case InstallationFamily.STORAGE:
            return tr("tui.installation.family.storage")
        case InstallationFamily.PROFILES:
            return tr("tui.installation.family.profiles")
        case InstallationFamily.RESET:
            return tr("tui.installation.family.reset")
        case InstallationFamily.REPAIR:
            return tr("tui.installation.family.repair")
        case InstallationFamily.VERIFICATION:
            return tr("tui.installation.family.verification")
        case InstallationFamily.OTHER:
            return tr("tui.installation.family.other")


def act_label(act: InstallationAct) -> str:
    """Name one act."""
    labels = {
        InstallationAct.STORAGE_INVENTORY: tr("tui.installation.act.storage_inventory.label"),
        InstallationAct.STORAGE_CHECK: tr("tui.installation.act.storage_check.label"),
        InstallationAct.STORAGE_INIT: tr("tui.installation.act.storage_init.label"),
        InstallationAct.STORAGE_RECLAIM: tr("tui.installation.act.storage_reclaim.label"),
        InstallationAct.PROFILE_LIST: tr("tui.installation.act.profile_list.label"),
        InstallationAct.RESET_START: tr("tui.installation.act.reset_start.label"),
        InstallationAct.RESET_STATUS: tr("tui.installation.act.reset_status.label"),
        InstallationAct.RESET_RESUME: tr("tui.installation.act.reset_resume.label"),
        InstallationAct.ARCHIVE_INSPECT: tr("tui.installation.act.archive_inspect.label"),
        InstallationAct.ARCHIVE_IMPORT_PREPARE: tr("tui.installation.act.archive_import_prepare.label"),
        InstallationAct.ARCHIVE_IMPORT: tr("tui.installation.act.archive_import.label"),
        InstallationAct.RECOVERY_ENROLL: tr("tui.installation.act.recovery_enroll.label"),
        InstallationAct.REPAIR_REPORT: tr("tui.installation.act.repair_report.label"),
        InstallationAct.REPAIR_LOGS: tr("tui.installation.act.repair_logs.label"),
        InstallationAct.REPAIR_PROFILE: tr("tui.installation.act.repair_profile.label"),
        InstallationAct.REVIEW_PACKAGE_VERIFY: tr("tui.installation.act.review_package_verify.label"),
        InstallationAct.REVIEW_PACKAGE_VERIFY_SIGNATURE: tr(
            "tui.installation.act.review_package_verify_signature.label"
        ),
        InstallationAct.REVIEW_PACKAGE_VERIFY_RECEIPT: tr("tui.installation.act.review_package_verify_receipt.label"),
        InstallationAct.REPORT_VERIFY_DOCUMENT: tr("tui.installation.act.report_verify_document.label"),
    }
    return labels.get(act, act.value)


def act_summary(act: InstallationAct) -> str:
    """Say in one sentence what one act does."""
    summaries = {
        InstallationAct.STORAGE_INVENTORY: tr("tui.installation.act.storage_inventory.summary"),
        InstallationAct.STORAGE_CHECK: tr("tui.installation.act.storage_check.summary"),
        InstallationAct.STORAGE_INIT: tr("tui.installation.act.storage_init.summary"),
        InstallationAct.STORAGE_RECLAIM: tr("tui.installation.act.storage_reclaim.summary"),
        InstallationAct.PROFILE_LIST: tr("tui.installation.act.profile_list.summary"),
        InstallationAct.RESET_START: tr("tui.installation.act.reset_start.summary"),
        InstallationAct.RESET_STATUS: tr("tui.installation.act.reset_status.summary"),
        InstallationAct.RESET_RESUME: tr("tui.installation.act.reset_resume.summary"),
        InstallationAct.ARCHIVE_INSPECT: tr("tui.installation.act.archive_inspect.summary"),
        InstallationAct.ARCHIVE_IMPORT_PREPARE: tr("tui.installation.act.archive_import_prepare.summary"),
        InstallationAct.ARCHIVE_IMPORT: tr("tui.installation.act.archive_import.summary"),
        InstallationAct.RECOVERY_ENROLL: tr("tui.installation.act.recovery_enroll.summary"),
        InstallationAct.REPAIR_REPORT: tr("tui.installation.act.repair_report.summary"),
        InstallationAct.REPAIR_LOGS: tr("tui.installation.act.repair_logs.summary"),
        InstallationAct.REPAIR_PROFILE: tr("tui.installation.act.repair_profile.summary"),
        InstallationAct.REVIEW_PACKAGE_VERIFY: tr("tui.installation.act.review_package_verify.summary"),
        InstallationAct.REVIEW_PACKAGE_VERIFY_SIGNATURE: tr(
            "tui.installation.act.review_package_verify_signature.summary"
        ),
        InstallationAct.REVIEW_PACKAGE_VERIFY_RECEIPT: tr("tui.installation.act.review_package_verify_receipt.summary"),
        InstallationAct.REPORT_VERIFY_DOCUMENT: tr("tui.installation.act.report_verify_document.summary"),
    }
    return summaries.get(act, "")


def field_label(name: str) -> str:
    """Name one request member."""
    labels = {
        "area": tr("tui.installation.field.area"),
        "acknowledge_retention_override": tr("tui.installation.field.acknowledge_retention_override"),
        "retention_override_reason": tr("tui.installation.field.retention_override_reason"),
        "operation_id": tr("tui.installation.field.operation_id"),
        "path": tr("tui.installation.field.path"),
        "label": tr("tui.installation.field.label"),
        "source_digest": tr("tui.installation.field.source_digest"),
        "profile_id": tr("tui.installation.field.profile_id"),
        "lines": tr("tui.installation.field.lines"),
        "profile": tr("tui.installation.field.profile"),
        "clear_active": tr("tui.installation.field.clear_active"),
        "package": tr("tui.installation.field.package"),
        "signature": tr("tui.installation.field.signature"),
        "public_key": tr("tui.installation.field.public_key"),
        "receipt": tr("tui.installation.field.receipt"),
        "operator_public_key": tr("tui.installation.field.operator_public_key"),
        "counter_signer_public_key": tr("tui.installation.field.counter_signer_public_key"),
        "trusted_key": tr("tui.installation.field.trusted_key"),
    }
    return labels.get(name, name)


def yes_no(value: bool) -> str:
    """Render a boolean as the word the person reads."""
    return tr("flows.confirm.yes") if value else tr("flows.confirm.no")


__all__ = ["act_label", "act_summary", "family_label", "field_label", "worded_in", "yes_no"]
