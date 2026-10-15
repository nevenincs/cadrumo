"""Expected primary outcomes for every composed operation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ...application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from ...application.invoices.catalogue_read_operation import (
    INVOICE_LIST_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_OPERATION_DEFINITION_ID,
)
from ...application.invoices.catalogue_remove_operation import INVOICE_REMOVE_OPERATION_DEFINITION_ID
from ...application.invoices.catalogue_update_operation import INVOICE_UPDATE_OPERATION_DEFINITION_ID
from ...application.ledger.bulk_classify_operation import LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID
from ...application.live.iva_wallet_history_operation import IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID
from ...application.modelo.calculation_report_verification_operation import (
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
)
from ...application.modelo.dependency_operation import MODELO_DEPENDENCY_OPERATION_DEFINITION_ID
from ...application.modelo.invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
)
from ...application.modelo.iva_wallet_correction_operation import MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID
from ...application.modelo.taxation_comparison_operation import MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID
from ...application.modelo.work_create_operation import MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
from ...application.overview.read_request import OVERVIEW_READ_DEFINITION_IDS
from ...application.user_profile.automation_operations import build_automation_operation_definitions
from ...application.workflow.resume_operation import WORKFLOW_RESUME_OPERATION_DEFINITION_ID
from ...application.workflow.run_read_operation import (
    WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
    WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
)
from ...core.operations import OperationEffect, OperationTerminalCondition
from ..operation_composition import build_production_operation_registry
from .conformance_families import CONFORMANCE_FAMILIES
from .conformance_family_contract import RegisteredExecutorConformanceCase


def _registered_definition_ids() -> tuple[str, ...]:
    """Every definition the production registry actually composes.

    The matrix is parametrised from this rather than from a hand-listed
    tuple. A hardcoded item list encodes the registry as it stood on the
    day it was written and then detects nothing: this test's own name
    claims it covers EVERY production registered executor, and while the
    list was hand-maintained it silently covered none of the modelo
    family. Deriving the subjects means a newly composed operation joins
    the matrix by existing, and reports a missing scenario rather than
    reconciling quietly.
    """
    return tuple(sorted(definition.definition_id for definition in build_production_operation_registry().definitions))


def _expectations_owned_once(
    cases: Iterable[RegisteredExecutorConformanceCase],
) -> Mapping[str, RegisteredExecutorConformanceCase]:
    """Key scenarios by definition id, refusing a second scenario for the same operation."""
    expectations: dict[str, RegisteredExecutorConformanceCase] = {}
    for case in cases:
        if case.definition_id in expectations:
            raise AssertionError(f"{case.definition_id} declares more than one conformance scenario")
        expectations[case.definition_id] = case
    return expectations


_EXPECTATIONS: Mapping[str, RegisteredExecutorConformanceCase] = _expectations_owned_once(
    (
        *(case for family in CONFORMANCE_FAMILIES for case in family.cases),
        *(
            RegisteredExecutorConformanceCase(
                f"ledger.rule.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if action == "list" else OperationEffect.UPDATED,
                (f"ledger.rule.{action}",),
            )
            for action in ("add", "list", "apply")
        ),
        *(
            RegisteredExecutorConformanceCase(
                definition_id, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, phase_codes
            )
            for definition_id, phase_codes in (
                ("modelo.history", ("modelo.history",)),
                ("modelo.history.timeline", ("modelo.history.timeline",)),
                ("modelo.project", ("modelo.project.prepare", "modelo.project.result")),
                ("modelo.compare", ("modelo.compare.prepare", "modelo.compare.result")),
            )
        ),
        *(
            RegisteredExecutorConformanceCase(
                f"ledger.{action}", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, (f"ledger.{action}",)
            )
            for action in ("archive", "stash", "restore", "exclude")
        ),
        *(
            RegisteredExecutorConformanceCase(
                definition_id,
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE,
                (definition_id,),
            )
            for definition_id in (
                "app.review.queue",
                "app.review.view",
                "modelo.bindings.list",
                "modelo.bindings.resolve",
                "modelo.bindings.resolve.typed",
                "modelo.requires",
                "modelo.readiness",
                "modelo.readiness.summary",
                "ledger.evidence.attachment_queue",
                "ledger.evidence.attachment_view",
                "ledger.evidence.consent.list",
                "ledger.evidence.review.list",
                "ledger.evidence.review.view",
            )
        ),
        *(
            RegisteredExecutorConformanceCase(
                f"config.collab.recipient.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if action == "list" else OperationEffect.UPDATED,
                (f"config.collab.recipient.{action}",),
            )
            for action in ("add", "list", "remove")
        ),
        *(
            RegisteredExecutorConformanceCase(
                definition.definition_id,
                OperationTerminalCondition.REFUSED,
                OperationEffect.NONE,
                expected_phase_codes=(definition.definition_id + ".execute",),
                expected_refusal_ref="REFUSED_AUTOMATION_ADMINISTRATION",
            )
            for definition in build_automation_operation_definitions()
        ),
        RegisteredExecutorConformanceCase(
            "auth.profile.passphrase-rotate", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "auth.credential.save",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("auth.credential.secret-consume", "auth.credential.execute", "auth.credential.settlement"),
        ),
        RegisteredExecutorConformanceCase(
            "auth.provider.configure", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "auth.session.acquire",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            # No certificate is configured in the isolated root, so the
            # provider's local readiness refuses before any session attempt.
            expected_refusal_ref="REFUSED_AUTH_LOGIN_PRECONDITION",
        ),
        *(
            RegisteredExecutorConformanceCase(definition_id, OperationTerminalCondition.SUCCEEDED, effect)
            for definition_id, effect in (
                ("auth.certificate.source.register", OperationEffect.UPDATED),
                ("auth.certificate.source.list", OperationEffect.NONE),
                ("auth.certificate.source.select", OperationEffect.UPDATED),
                ("auth.certificate.source.remove", OperationEffect.UPDATED),
                ("auth.certificate.source.check", OperationEffect.NONE),
                ("auth.certificate.secret.set", OperationEffect.UPDATED),
                ("auth.certificate.secret.remove", OperationEffect.UPDATED),
                ("ledger.ratios.list", OperationEffect.NONE),
                ("ledger.ratios.eligible", OperationEffect.NONE),
                ("ledger.ratios.validate", OperationEffect.NONE),
                ("ledger.ratios.set", OperationEffect.UPDATED),
                ("ledger.ratios.unset", OperationEffect.UPDATED),
            )
        ),
        RegisteredExecutorConformanceCase(
            "auth.session.logout", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "auth.session.reset", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            AUTH_READ_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("auth.local-read.execute",),
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.field-mutation", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.repeatable-row-mutation", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.repeatable-row-update", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.repeatable-row-remove", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.patch", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.plantilla-media", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.descendants", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.complete-setup",
            OperationTerminalCondition.REFUSED,
            OperationEffect.UNKNOWN,
            expected_refusal_ref="REFUSED_PROFILE_SCHEMA_VALIDATION",
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "workbench.generation",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        # Each workbench read is a single-phase owner read that publishes its own
        # definition id and settles NONE. Its live-human CLI/TUI requirement is an
        # access-policy axis the runtime operation authority enforces; this driver
        # composes the supervisor without that authority, so it never applies here.
        *(
            RegisteredExecutorConformanceCase(
                definition_id,
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE,
                (definition_id,),
            )
            for definition_id in (
                "modelo.work.form",
                "modelo.work.casilla_help",
                "modelo.edit.renew",
                "modelo.edit.preflight",
                "modelo.edit.apply_prerequisite",
            )
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.bundle-export", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            # The composed provider preflight refuses before discovery: the
            # isolated root holds no usable provider, so no remote read starts.
            "live.filed-history.pull",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-history.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.expedientes.capture.bulk",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("expedientes-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.expedientes.capture.single",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("expedientes-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.filed-capture.bulk",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-bulk.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.filed-capture.single",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.filed-capture.source",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-source.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.filed-discover",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-discover.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.filed-list",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("filed-list.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.iva-wallet.capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("iva-wallet.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.iva-wallet.evidence-capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("iva-evidence.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.iva-wallet.history-capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("iva-history.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.justificante.capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("justificante-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.notifications.capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("notifications-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.notifications.document.capture",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("notification-document-capture.preflight",),
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "live.verify.nif-iva",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (),
            expected_refusal_ref="REFUSED_APPLICATION_LIVE_NIF_IVA_CERTIFICATE_REQUIRED",
        ),
        RegisteredExecutorConformanceCase(
            "live.verify.tgvi", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "live.verify.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "live.verify.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "live.verify.latest", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "live.justificante.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("justificante-list.read", "justificante-list.result"),
        ),
        RegisteredExecutorConformanceCase(
            "live.justificante.show",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("justificante-show.read", "justificante-show.result"),
        ),
        RegisteredExecutorConformanceCase(
            "live.expedientes.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("expedientes-list.read", "expedientes-list.result"),
        ),
        RegisteredExecutorConformanceCase(
            "live.expedientes.show",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("expedientes-show.read", "expedientes-show.result"),
        ),
        RegisteredExecutorConformanceCase(
            "live.expedientes.latest",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("expedientes-latest.read", "expedientes-latest.result"),
        ),
        RegisteredExecutorConformanceCase(
            "live.notifications.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notifications-list.read", "notifications-list.result"),
        ),
        RegisteredExecutorConformanceCase(
            "live.notifications.show",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notifications-show.read", "notifications-show.result"),
        ),
        RegisteredExecutorConformanceCase(
            "live.notifications.latest",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notifications-latest.read", "notifications-latest.result"),
        ),
        RegisteredExecutorConformanceCase(
            "live.notifications.document.view",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notification-document-view.read", "notification-document-view.result"),
        ),
        RegisteredExecutorConformanceCase(
            "live.notifications.document.history",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("notification-document-history.read", "notification-document-history.result"),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.reconcile.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.reconcile.list",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.filing_record.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "modelo.filing_record.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "modelo.verification_report.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "modelo.verification_report.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "modelo.observation.local", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "modelo.filing_record.import", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            # The isolated settings name no Drive root folder, so the production
            # transport refuses while planning, before any remote call.
            "export.google-sheets",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (
                "export.google-sheets.preflight",
                "export.google-sheets.plan",
            ),
            expected_refusal_ref="REFUSED_GOOGLE_SHEETS_EXPORT_ROOT_FOLDER_REQUIRED",
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.censo-review", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.censo-prepare", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.censo-file-import", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.censo-preview",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            expected_refusal_ref="REFUSED_PROFILE_ACCESS",
        ),
        RegisteredExecutorConformanceCase(
            "modelo.reconcile.import",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            expected_refusal_ref="REFUSED_RECONCILIATION_EVIDENCE_INVALID",
        ),
        RegisteredExecutorConformanceCase(
            "modelo.reconcile.pull",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("modelo-reconcile-pull.prepare",),
            expected_refusal_ref="REFUSED_LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NOT_FOUND",
        ),
        # Verify against a closed runtime endpoint: the executor settles its
        # typed not-ready outcome and changes nothing on the host.
        RegisteredExecutorConformanceCase(
            "local-reader.provision", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.rename", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.metadata", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.create",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("modelo.work.create",),
            expected_refusal_ref=MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE,
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("modelo.work.list",)
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.history",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.work.history",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.filing_record", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.review",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.work.review",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.amendment_context", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (WORKFLOW_RUN_LIST_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            WORKFLOW_RESUME_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (WORKFLOW_RESUME_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            "overview.pipeline", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("overview.pipeline",)
        ),
        *(
            RegisteredExecutorConformanceCase(
                definition_id,
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE,
                (definition_id,),
            )
            for definition_id in OVERVIEW_READ_DEFINITION_IDS.values()
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.wizard_context",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.work.wizard_context",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.revision", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.revision_snapshot", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.revisions", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        RegisteredExecutorConformanceCase(
            MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,),
            expected_refusal_ref="REFUSED_TAXATION_COMPARISON",
        ),
        RegisteredExecutorConformanceCase(
            "modelo.review_package.build",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.review_package.build.preconditions",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.m303_attestation",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.work.m303_attestation.preconditions",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.counterparty",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.counterparty",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.own_account",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.own_account",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.m360_solicitud",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.m360_solicitud",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.remove", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.remove",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.import", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.import",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.add", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.add",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.allocate", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.allocate",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.classify.single",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.classify.single",),
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.add",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.evidence.add",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.list",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.evidence.list",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.view",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.evidence.view",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.update",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.evidence.update",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.remove",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.evidence.remove",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.reader-readiness",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.evidence.reader-readiness",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.extract",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.evidence.extract",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.confirm",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.evidence.confirm",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.split.manual",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.split.manual",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.merge",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.merge",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.update", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.update",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.attach", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.attach",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.detach", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.detach",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.reset", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.reset",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.status", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.status",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.check", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.check",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.preflight", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.preflight",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.history", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.history",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.view", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.view",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.track", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.track",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.list", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.list",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.invoice.add", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.invoice.add",)
        ),
        RegisteredExecutorConformanceCase(
            MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
        ),
        RegisteredExecutorConformanceCase(
            "modelo.aggregate", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
        ),
        *(
            RegisteredExecutorConformanceCase(
                f"ledger.bienes_inversion.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if action == "list" else OperationEffect.UPDATED,
                (f"ledger.bienes_inversion.{action}",),
            )
            for action in ("list", "declare")
        ),
        *(
            RegisteredExecutorConformanceCase(
                f"ledger.prorrata.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if action == "list" else OperationEffect.UPDATED,
            )
            for action in (
                "list",
                "declare_sector",
                "elect_especial",
                "elect_general",
                "revoke_especial",
                "seed",
                "seed_sector",
                "settle_sector",
            )
        ),
        *(
            RegisteredExecutorConformanceCase(
                definition_id,
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.NONE if definition_id == "ledger.inventory.list" else OperationEffect.UPDATED,
                (definition_id,),
            )
            for definition_id in (
                "ledger.inventory.list",
                "ledger.inventory.create",
                "ledger.inventory.movement.add",
                "ledger.inventory.valuation.preview",
                "ledger.inventory.closing-authority.record",
            )
        ),
        *(
            RegisteredExecutorConformanceCase(
                f"ledger.actividad-asset.{action}",
                OperationTerminalCondition.SUCCEEDED,
                OperationEffect.UPDATED if action in {"create", "correct", "claim"} else OperationEffect.NONE,
                (f"ledger.actividad-asset.{action}",),
            )
            for action in ("create", "inspect", "correct", "forecast", "claim", "filing-handoff")
        ),
        RegisteredExecutorConformanceCase(
            "user-profile.recovery.status",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("user-profile.recovery.status",),
        ),
        RegisteredExecutorConformanceCase(
            INVOICE_LIST_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (INVOICE_LIST_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            INVOICE_VIEW_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (INVOICE_VIEW_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            INVOICE_REMOVE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (INVOICE_REMOVE_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            INVOICE_UPDATE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (INVOICE_UPDATE_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (
                "modelo.iva-wallet.correct.commit",
                "modelo.iva-wallet.correct.result",
            ),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.iva-wallet.balance",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("modelo.iva-wallet.balance.read",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.iva-wallet.seed",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.iva-wallet.seed.commit", "modelo.iva-wallet.seed.result"),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.iva-wallet.override",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.iva-wallet.override.commit", "modelo.iva-wallet.override.result"),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.participation",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.participation",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.participation.rebuild",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.participation.rebuild",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.review", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE, ("ledger.review",)
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.discard", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            # Calculated from the unit's (empty) ledger aggregation: the M130
            # revision marks no casilla required, so one revision is persisted.
            "modelo.work.calculate",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.work.calculate.ledger",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.wizard_attempt",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("modelo.work.wizard_attempt",),
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.verify", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.file", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "modelo.edit.apply", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            "modelo.export", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
        RegisteredExecutorConformanceCase(
            MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
        ),
        RegisteredExecutorConformanceCase(
            "modelo.work.amend", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED
        ),
    )
)

"""The settlement each registered executor is expected to reach.

Keyed by definition id, never ordered or counted. Coverage is asserted
against the live registry below, so an operation that gains a definition
without gaining a scenario fails by name instead of by tally."""
