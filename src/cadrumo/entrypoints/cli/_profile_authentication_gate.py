"""Parsed-dispatch safety gate for root profile authentication."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Never, cast

import typer

from ...application.operator_surface.command_ports import ProfileAuthenticationPosture
from ...core.errors.hierarchy import InternalInvariantError
from ._command_secret_contracts import MachineSecretVariantSpec
from ._profile_authentication_contract import (
    ProfileAuthenticationMethod,
    ProfileAuthenticationSecrets,
    command_needs_state_tree,
    profile_authentication_posture,
    root_profile_secret_model,
)
from .command_graph import CommandSpecGraph
from .command_spec import CommandSpec
from .config.secure_input import (
    MachineSecretChannel,
    MachineSecretPayload,
    MachineSecretSelection,
    ProfileSecretChannel,
    ProfileSecretSelection,
    read_machine_secret_payload,
    read_profile_secret_payload,
    select_machine_secret_channel,
    select_profile_secret_channel,
    stage_machine_secret_payload,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from uuid import UUID

    from ...application.user_profile.login_session import ProfileLoginOutcome
    from ...application.workflow.profile_bucket_models import ProfileBucketPointer
    from ._profile_session_gate import RootAuthenticator


_RESOLVED_PROFILE_TARGET_KEY = "cadrumo.resolved_profile_target"
_RUNTIME_PROFILE_KEYS = frozenset(
    {
        "config_check",
        "config_google_register",
        "config_google_login",
        "config_google_status",
        "config_google_logout",
        "config_google_credential_source_set",
        "config_google_credential_source_view",
        "config_google_folder_set",
        "config_google_folder_view",
        "config_google_probe",
        "app_quickfile",
        "app_ledger_evidence_batch",
        "app_ledger_evidence_pull",
        "app_ledger_evidence_pull_all",
        "config_auth_configure",
        "config_auth_apoderado_status",
        "config_auth_apoderado_configure",
        "config_auth_apoderado_clear",
        "config_auth_apoderado_check",
        "config_auth_diagnostics_report",
        "app_diagnostics_run_health",
        "app_diagnostics_runs",
        "app_diagnostics_latency",
        "app_diagnostics_errors",
        "app_diagnostics_llm_usage",
        "app_diagnostics_telemetry_flush",
        "app_ledger_llm_diagnostics",
        "app_live_borrador_100_import",
        "app_live_borrador_100_latest",
        "app_live_borrador_100_list",
        "app_live_borrador_100_view",
        "app_modelo_m036_alta",
        "app_modelo_m036_baja",
        "app_modelo_m036_modificacion",
        "app_modelo_m036_list",
        "app_modelo_m036_view",
        "app_modelo_audit_check",
        "app_modelo_audit_export",
        "app_modelo_audit_view",
        "config_profile_archive_export",
        "config_profile_archive_push",
        "config_profile_archive_reconcile",
        "config_collab_recipient_add",
        "config_collab_recipient_list",
        "config_collab_recipient_remove",
        "app_review_queue",
        "app_review_view",
        "app_modelo_bindings_list",
        "app_modelo_bindings_resolve",
        "app_modelo_requires",
        "app_modelo_readiness",
        "app_ledger_evidence_attachment_queue",
        "app_ledger_evidence_attachment_view",
        "app_ledger_evidence_consent_list",
        "app_ledger_evidence_review_list",
        "app_ledger_evidence_review_view",
        "app_ledger_attach",
        "app_ledger_detach",
        "config_auth_login",
        "config_profile_recovery_status",
        "config_profile_history",
        "config_auth_certificate_register",
        "config_auth_certificate_list",
        "config_auth_certificate_select",
        "config_auth_certificate_remove",
        "config_auth_certificate_check",
        "config_auth_certificate_secret_set",
        "config_auth_certificate_secret_remove",
        "config_profile_censo_pull",
        "config_profile_censo_show",
        "config_profile_censo_import",
        "app_live_filed_list",
        "app_live_filed_discover",
        "app_live_filed_pull",
        "app_live_filed_pull_all",
        "app_live_filed_pull_sources",
        "app_live_iva_wallet_pull",
        "app_live_iva_wallet_history",
        "app_live_iva_wallet_pull_history",
        "app_live_iva_wallet_pull_evidence",
        "app_live_notifications_pull",
        "app_live_notifications_list",
        "app_live_notifications_view",
        "app_live_notifications_latest",
        "app_live_notifications_document_pull",
        "app_live_notifications_document_view",
        "app_live_notifications_document_history",
        "app_live_expedientes_pull",
        "app_live_expedientes_list",
        "app_live_expedientes_view",
        "app_live_expedientes_latest",
        "app_live_justificante_list",
        "app_live_justificante_view",
        "app_live_justificante_pull",
        "app_live_verify_list",
        "app_live_verify_view",
        "app_live_verify_latest",
        "app_live_verify_nif_iva",
        "app_live_verify_tgvi",
        "app_overview_pipeline",
        "app_overview_status",
        "app_overview_calendar",
        "app_overview_agenda",
        "app_overview_backlog",
        "app_overview_explain",
        "app_overview_prepare",
        "app_ledger_invoice_add",
        "app_ledger_invoice_import",
        "app_ledger_invoice_wizard",
        "app_ledger_bienes_inversion_list",
        "app_ledger_bienes_inversion_declare",
        "app_ledger_prorrata_list",
        "app_ledger_prorrata_declare_sector",
        "app_ledger_prorrata_elect_especial",
        "app_ledger_prorrata_elect_general",
        "app_ledger_prorrata_revoke_especial",
        "app_ledger_prorrata_seed",
        "app_ledger_prorrata_seed_sector",
        "app_ledger_prorrata_settle_sector",
        "app_ledger_inventory_list",
        "app_ledger_inventory_create",
        "app_ledger_inventory_movement_add",
        "app_ledger_inventory_valuation_preview",
        "app_ledger_inventory_closing_authority_record",
        "app_ledger_actividad_asset_create",
        "app_ledger_actividad_asset_inspect",
        "app_ledger_actividad_asset_correct",
        "app_ledger_actividad_asset_forecast",
        "app_ledger_actividad_asset_claim",
        "app_ledger_actividad_asset_filing_handoff",
        "app_ledger_ratios_list",
        "app_ledger_ratios_set",
        "app_ledger_ratios_unset",
        "app_ledger_ratios_eligible",
        "app_ledger_ratios_validate",
        "app_ledger_invoice_list",
        "app_ledger_invoice_view",
        "app_ledger_invoice_remove",
        "app_ledger_invoice_update",
        "app_ledger_import",
        "app_ledger_export",
        "app_ledger_link",
        "app_ledger_add",
        "app_ledger_allocate",
        "app_ledger_classify",
        "app_ledger_rule_add",
        "app_ledger_rule_list",
        "app_ledger_rule_apply",
        "app_ledger_evidence_add",
        "app_ledger_evidence_list",
        "app_ledger_evidence_view",
        "app_ledger_evidence_update",
        "app_ledger_evidence_remove",
        "app_ledger_evidence_extract",
        "app_ledger_evidence_confirm",
        "app_ledger_split",
        "app_ledger_merge",
        "app_ledger_update",
        "app_ledger_remove",
        "app_ledger_reset",
        "app_ledger_counterparty_confirm",
        "app_ledger_counterparty_view",
        "app_ledger_counterparty_withdraw",
        "app_ledger_status",
        "app_ledger_check",
        "app_ledger_preflight",
        "app_ledger_history",
        "app_ledger_view",
        "app_ledger_track",
        "app_ledger_list",
        "app_ledger_review",
        "app_ledger_archive",
        "app_ledger_stash",
        "app_ledger_restore",
        "app_ledger_exclude",
        "app_ledger_participation",
        "app_ledger_participation_rebuild",
        "app_modelo_work_rename",
        "app_modelo_work_report",
        "app_modelo_work_discard",
        "app_modelo_work_status",
        "app_modelo_work_history",
        "app_modelo_history",
        "app_modelo_project",
        "app_modelo_compare",
        "app_modelo_m145_create",
        "app_modelo_m145_validate",
        "app_modelo_m145_export",
        "app_modelo_m145_mark_delivered_to_payer",
        "app_modelo_m145_mark_locally_completed",
        "app_modelo_work_list",
        "app_modelo_work_create",
        "app_modelo_work_review",
        "app_modelo_work_run",
        "app_modelo_work_run_details",
        "app_modelo_work_runs",
        "app_modelo_work_resume",
        "app_modelo_work_dependencies",
        "app_modelo_work_select",
        "app_modelo_work_revision",
        "app_modelo_work_compare_taxation",
        "app_modelo_iva_wallet_correct",
        "app_modelo_iva_wallet_balance",
        "app_modelo_iva_wallet_seed",
        "app_modelo_iva_wallet_override",
        "app_modelo_spreadsheet_push",
        "app_modelo_spreadsheet_export",
        "app_modelo_spreadsheet_pull",
        "app_modelo_spreadsheet_calculate",
        "app_modelo_spreadsheet_verify",
        "app_modelo_work_preview_maritime_exemption",
        "app_modelo_review_package_sign",
        "app_modelo_review_package_counter_sign",
        "app_modelo_review_package_encrypt_for_recipient",
        "app_modelo_review_package_decrypt",
        "app_modelo_review_package_encrypt_feedback",
        "app_modelo_review_package_import_feedback",
        "app_modelo_work_revisions",
        "app_modelo_work_observations",
        "app_modelo_work_calculate",
        "app_modelo_work_wizard",
        "app_modelo_work_amend",
        "app_modelo_work_amend_wizard",
        "app_modelo_reconcile_list",
        "app_modelo_reconcile_import",
        "app_modelo_reconcile_pull",
        "app_modelo_filing_record_view",
        "app_modelo_filing_record_list",
        "app_modelo_filing_record_import",
        "app_modelo_filing_record_observe_local",
        "app_modelo_aggregate",
        "app_modelo_verification_report_list",
        "app_modelo_verification_report_view",
        "app_modelo_work_attest_m303_exonerado_390",
        "app_modelo_export",
        "app_modelo_review_package_build",
        "app_modelo_work_verify",
        "app_modelo_work_file",
        "config_profile_descendiente",
        "config_auth_status",
        "config_auth_test",
        "config_auth_logout",
        "config_auth_reset",
        "config_auth_diagnostics_list",
        "config_auth_diagnostics_view",
        "config_profile_descendiente_add",
        "config_profile_descendiente_list",
        "config_profile_descendiente_remove",
        "config_profile_sessions",
        "config_profile_automation_deny",
        "config_profile_automation_list",
        "config_profile_automation_inspect",
        "config_profile_automation_approve",
        "config_profile_automation_decline",
        "config_profile_automation_change",
        "config_profile_lock",
        "config_profile_view",
        "config_profile_validate",
        "config_profile_status",
        "config_profile_plantilla_media_set",
        "config_profile_plantilla_media_list",
        "config_profile_plantilla_media_remove",
        "config_profile_edit",
        "config_profile_add_row",
        "config_profile_edit_row",
        "config_profile_remove_row",
        "config_profile_complete_setup",
        "config_profile_capabilities_view",
        "config_profile_capabilities_set",
    }
)


def _require_discard_confirmation(spec: CommandSpec, arguments: Mapping[str, object]) -> None:
    """Require discard confirmation."""
    if spec.key == "app_modelo_work_discard" and arguments.get("confirmed") is not True:
        from ...core.i18n.render import tr

        target_label = arguments.get("work_unit_id") or " ".join(
            str(arguments.get(key) or "?") for key in ("modelo", "year", "period")
        )
        raise typer.BadParameter(tr("cli.app.modelo.work.discard_requires_yes", work_unit_id=str(target_label)))


def _require_automation_change_sources(
    spec: CommandSpec,
    method: ProfileAuthenticationMethod,
    credential_reference: UUID | None,
    leaf: MachineSecretSelection | None,
) -> None:
    """Require automation change sources."""
    if spec.key == "config_profile_automation_change":
        if method is not ProfileAuthenticationMethod.API_KEY or credential_reference is None:
            _refuse("automation_change_credential_ref_required")
        if leaf is None:
            _refuse("automation_change_proposal_required")


def _require_profile_credential_posture(
    credential_reference: UUID | None,
    method: ProfileAuthenticationMethod,
    posture: ProfileAuthenticationPosture,
    runtime_profile_client: bool,
    root: ProfileSecretSelection | None,
) -> None:
    """Require profile credential posture."""
    if credential_reference is not None:
        if method is not ProfileAuthenticationMethod.API_KEY:
            _refuse("profile_credential_ref_requires_api_key")
        if posture is not ProfileAuthenticationPosture.RESUME_FALLBACK or not runtime_profile_client:
            _refuse("profile_credential_ref_inapplicable")
    elif method is ProfileAuthenticationMethod.API_KEY:
        if root is None:
            _refuse("profile_secrets_api_key_requires_channel")
        if posture is not ProfileAuthenticationPosture.RESUME_FALLBACK or not runtime_profile_client:
            _refuse("profile_secrets_api_key_inapplicable")


def _refuse(key: str) -> Never:
    error = import_module(".errors", __package__).CliRefusedBoundaryError
    raise error(translated_message=f"cli.config.custody.errors.{key}")


def _leaf_selection(spec: CommandSpec, arguments: Mapping[str, object]) -> MachineSecretSelection | None:
    if spec.machine_secret is None:
        return None
    return select_machine_secret_channel(
        secrets_stdin=bool(arguments.get("secrets_stdin", False)),
        secrets_fd=cast("int | None", arguments.get("secrets_fd")),
    )


def _preflight_sources(*, root: ProfileSecretSelection | None, leaf: MachineSecretSelection | None) -> None:
    if root is None or leaf is None:
        return
    root_descriptor = 0 if root.channel is ProfileSecretChannel.STDIN else root.descriptor
    leaf_descriptor = 0 if leaf.channel is MachineSecretChannel.STDIN else leaf.descriptor
    if root_descriptor != leaf_descriptor:
        return
    if root_descriptor == 0:
        _refuse("profile_secrets_stdin_collision")
    _refuse("profile_secrets_fd_collision")


def _selected_variant(spec: CommandSpec, arguments: Mapping[str, object]) -> MachineSecretVariantSpec:
    machine = spec.machine_secret
    if machine is None:
        raise InternalInvariantError("leaf machine-secret model requested for a non-adopter")
    matches: list[MachineSecretVariantSpec] = []
    for variant in machine.variants:
        condition = variant.condition
        if condition is None:
            matches.append(variant)
            continue
        present = arguments.get(condition.option_name) is not None
        if present is (condition.presence == "present"):
            matches.append(variant)
    if len(matches) != 1:
        raise InternalInvariantError("parsed command does not select exactly one machine-secret variant")
    return matches[0]


def _read_and_stage_leaf(
    *, spec: CommandSpec, arguments: Mapping[str, object], selection: MachineSecretSelection | None
) -> None:
    if selection is None:
        return
    from ._command_target import resolve_deferred_target

    model = resolve_deferred_target(_selected_variant(spec, arguments).model)
    if not isinstance(model, type) or not issubclass(model, MachineSecretPayload):
        raise TypeError("leaf machine-secret model must inherit MachineSecretPayload")
    stage_machine_secret_payload(read_machine_secret_payload(model, selection=selection))


def _resolve_login_target_or_refuse(raw: str) -> ProfileBucketPointer:
    """Resolve a profile target, converting label ambiguity to the CLI refusal.

    `resolve_login_target` surfaces `ProfileLabelAmbiguousError`, a WorkflowError
    from the application layer. Left uncaught here it reaches the terminal
    boundary and renders the WORKFLOW-layer message ("... active buckets carry
    it") instead of the dedicated CLI refusal that tells the operator what to do
    ("Use the profile UUID to disambiguate").

    That exact escape was fixed once before, at the three other CLI sites that
    resolve a label -- `_config/_profile_support.resolve_profile_by_label`,
    `_profile_session_gate.normalize_ambient_profile`, and the root
    `--profile` override. This preflight is a FOURTH resolution site, introduced
    after that fix, and it did not carry the conversion, so the escape returned
    on `config profile view <label>` and `config profile validate <label>`.
    """
    from ...application.profile_preconditions import (
        ProfileSelectionFailure,
        profile_selection_failure_verdict,
    )
    from ...application.user_profile.login_session import resolve_login_target
    from ...application.workflow.errors import ProfileLabelAmbiguousError
    from ...domain.user_profile.errors import ProfileNotFoundError
    from .common import attach_cli_policy_verdict
    from .errors import CliRefusedBoundaryError

    try:
        return resolve_login_target(raw)
    except ProfileLabelAmbiguousError as error:
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message="errors.refused.refused_profile_label_ambiguous",
            ),
            verdict=profile_selection_failure_verdict(
                ProfileSelectionFailure.AMBIGUOUS,
                requested_profile=raw,
            ),
        ) from error
    except ProfileNotFoundError as error:
        # The message already names the next step in prose ("run `aeat config
        # profile list`"), but the TYPED action was null, so the machine-readable
        # half of that guidance was missing -- and this CLI's operator is an
        # non-interactive caller, for which the prose is not actionable. The verdict is
        # attached to the existing error rather than replacing it with a
        # `CliRefusedBoundaryError`, so `REFUSED_PROFILE_NOT_FOUND` and its
        # message stay exactly as they are on the wire; only the absent
        # projection is filled. The root `--profile` override already projects
        # this same UNKNOWN verdict.
        attach_cli_policy_verdict(
            error,
            verdict=profile_selection_failure_verdict(
                ProfileSelectionFailure.UNKNOWN,
                requested_profile=raw,
            ),
        )
        raise


def _select_preflight_channels(
    ctx: typer.Context,
    *,
    spec: CommandSpec,
    arguments: Mapping[str, object],
) -> tuple[ProfileSecretSelection | None, MachineSecretSelection | None]:
    """Select both secret scopes and reject any cross-scope channel collision."""
    from .runtime_profile_admission import parsed_root_profile_source

    source = parsed_root_profile_source(ctx)
    if source.credential_reference is not None and (source.stdin or source.descriptor is not None):
        _refuse("profile_credential_ref_conflict")
    root = select_profile_secret_channel(
        profile_secrets_stdin=source.stdin,
        profile_secrets_fd=source.descriptor,
    )
    leaf = _leaf_selection(spec, arguments)
    _preflight_sources(root=root, leaf=leaf)
    return root, leaf


def _configure_root_logging(root_state: dict[str, object]) -> None:
    """Restore the parsed root logging selection before profile resolution."""
    from ...core.logging import resume_logging_configuration
    from ._log_levels import LogLevel, apply_to_root_logger

    log_level = root_state.get("log_level")
    if isinstance(log_level, LogLevel):
        resume_logging_configuration()
        apply_to_root_logger(log_level)


def _resolve_root_profile_override_or_refuse(ctx: typer.Context, raw: str) -> ProfileBucketPointer:
    """Resolve the root ``--profile`` selection with the root override's typed refusal."""
    from ...domain.user_profile.errors import ProfileNotFoundError
    from ._root_support import unresolved_profile_override_refusal

    if not raw.strip():
        raise unresolved_profile_override_refusal(ctx, profile=raw, blank=True)
    try:
        return _resolve_login_target_or_refuse(raw)
    except ProfileNotFoundError as error:
        raise unresolved_profile_override_refusal(ctx, profile=raw.strip(), blank=False) from error


def _resolve_profile_targets(
    ctx: typer.Context,
    *,
    spec: CommandSpec,
    arguments: Mapping[str, object],
    posture: ProfileAuthenticationPosture,
    root_state: dict[str, object],
) -> tuple[str | None, str | None]:
    """Resolve command and root profile targets in their established order."""
    from ._profile_session_gate import bind_profile_target, normalize_ambient_profile

    explicit_target = None
    explicit_label = None
    if spec.profile_target_parameter is not None:
        raw_target = arguments.get(spec.profile_target_parameter)
        if raw_target is not None:
            if not isinstance(raw_target, str):
                raise TypeError("profile target parameter has an invalid type")
            pointer = _resolve_login_target_or_refuse(raw_target)
            explicit_target = pointer.bucket_id
            explicit_label = pointer.label
            root_state[_RESOLVED_PROFILE_TARGET_KEY] = pointer
    if explicit_target is None and posture is not ProfileAuthenticationPosture.NOT_APPLICABLE:
        profile_override = root_state.get("profile_override")
        if isinstance(profile_override, str):
            pointer = _resolve_root_profile_override_or_refuse(ctx, profile_override)
            explicit_target = pointer.bucket_id
            explicit_label = pointer.label
            root_state[_RESOLVED_PROFILE_TARGET_KEY] = pointer
            if posture is not ProfileAuthenticationPosture.RESUME_FALLBACK:
                bind_profile_target(ctx, bucket_id=explicit_target)
        else:
            normalize_ambient_profile(ctx)
    return explicit_target, explicit_label


def _diagnose_unregistered_profile(
    *, spec: CommandSpec, root: ProfileSecretSelection | None, credential_reference: bool = False
) -> bool:
    """Handle the one diagnostic that may finish dispatch before session activation."""
    if not spec.allow_unregistered_profile_diagnostic:
        return False
    from ...application.workflow.profile_bucket_scan import read_profile_bucket_by_id
    from ...core.bucket_pointer import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    if active is None or read_profile_bucket_by_id(active) is not None:
        return False
    if root is not None or credential_reference:
        _refuse("profile_secrets_inapplicable")
    from ...core.storage_materialization import ensure_storage_tree

    ensure_storage_tree()
    return True


def _require_resume_target(
    root: ProfileSecretSelection | None, explicit_target: str | None, *, credential_reference: bool = False
) -> None:
    """Refuse root credentials that have no exact profile target to authenticate."""
    if (root is None and not credential_reference) or explicit_target is not None:
        return
    from ...core.bucket_pointer import resolve_active_bucket_id

    if resolve_active_bucket_id() is None:
        _refuse("profile_secrets_missing_target")


def _activate_parsed_profile_session(
    ctx: typer.Context,
    *,
    posture: ProfileAuthenticationPosture,
    root: ProfileSecretSelection | None,
    leaf: MachineSecretSelection | None,
    spec: CommandSpec,
    arguments: Mapping[str, object],
    explicit_target: str | None,
    explicit_label: str | None,
    command_path: tuple[str, ...],
    authenticate_root: RootAuthenticator,
) -> None:
    """Delegate session policy and authentication to the neutral session gate."""
    from ._profile_session_gate import activate_profile_session

    if posture is not ProfileAuthenticationPosture.RESUME_FALLBACK:
        activate_profile_session(
            ctx,
            posture=posture,
            root_selection=None,
            leaf_selection=leaf,
            spec=spec,
            arguments=arguments,
            target_bucket_id=explicit_target,
            target_profile_label=explicit_label,
            command_path=command_path,
            authenticate_root=authenticate_root,
        )
        return
    _require_resume_target(root, explicit_target)
    activate_profile_session(
        ctx,
        posture=posture,
        root_selection=root,
        leaf_selection=leaf,
        spec=spec,
        arguments=arguments,
        target_bucket_id=explicit_target,
        target_profile_label=explicit_label,
        command_path=command_path,
        authenticate_root=authenticate_root,
    )


def _uses_runtime_profile_client(spec: CommandSpec, arguments: Mapping[str, object]) -> bool:
    """Select the runtime route, including commands with a local preview mode."""
    if spec.key == "config_profile_censo_import":
        return arguments.get("apply") is True
    if spec.key == "app_modelo_work_report_verify":
        return arguments.get("document_only") is not True
    return spec.key in _RUNTIME_PROFILE_KEYS


def preflight_parsed_leaf(
    ctx: typer.Context,
    *,
    graph: CommandSpecGraph,
    spec: CommandSpec,
    arguments: Mapping[str, object],
) -> None:
    """Preflight parsed root/leaf sources, then run the ordinary root gate."""
    node = graph.node(spec.key)
    posture = profile_authentication_posture(node)
    _require_discard_confirmation(spec, arguments)
    root, leaf = _select_preflight_channels(ctx, spec=spec, arguments=arguments)
    if spec.key == "config_profile_automation_create" and leaf is None:
        _refuse("automation_create_proposal_required")
    from .runtime_profile_admission import parsed_root_profile_source

    source = parsed_root_profile_source(ctx)
    method = source.method
    credential_reference = source.credential_reference
    runtime_profile_client = _uses_runtime_profile_client(spec, arguments)
    _require_automation_change_sources(spec, method, credential_reference, leaf)
    _require_profile_credential_posture(credential_reference, method, posture, runtime_profile_client, root)
    if posture is not ProfileAuthenticationPosture.RESUME_FALLBACK and root is not None:
        _refuse("profile_secrets_inapplicable")
    # The secret-source refusals above are still parse-time refusals and write
    # nothing; from here on the command runs, so its storage is provisioned.
    from ...application.provisioning import provision_cli_storage

    provision_cli_storage(writes_state=command_needs_state_tree(node))
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    _configure_root_logging(root_state)
    explicit_target, explicit_label = _resolve_profile_targets(
        ctx,
        spec=spec,
        arguments=arguments,
        posture=posture,
        root_state=root_state,
    )

    def authenticate(
        bucket_id: str,
        root_selection: ProfileSecretSelection,
        leaf_selection: MachineSecretSelection | None,
        spec: CommandSpec,
        arguments: Mapping[str, object],
    ) -> ProfileLoginOutcome:
        return consume_root_fallback(
            ctx,
            bucket_id=bucket_id,
            root=root_selection,
            leaf=leaf_selection,
            spec=spec,
            arguments=arguments,
        )

    if _activate_runtime_leaf(
        ctx,
        spec,
        arguments,
        root,
        leaf,
        explicit_target,
        explicit_label,
        method,
        credential_reference,
        runtime_profile_client,
        node.path[1:],
    ):
        return
    _activate_parsed_profile_session(
        ctx,
        posture=posture,
        root=root,
        leaf=leaf,
        spec=spec,
        arguments=arguments,
        explicit_target=explicit_target,
        explicit_label=explicit_label,
        command_path=node.path[1:],
        authenticate_root=authenticate,
    )
    _materialize_storage_for(spec)


def _materialize_storage_for(spec: CommandSpec) -> None:
    """Materialize the storage tree only for a leaf that declares it writes.

    The tree is twenty-odd directories.  Creating it unconditionally meant a
    read-only command -- ``config profile list`` most visibly -- built the whole
    topology just to report what already existed, which both contradicts its
    declared ``side_effects`` of ``none`` and makes a first run appear to have
    state it does not have.  The declaration is the same authority the census,
    write routing and help surfaces read, so the gate cannot drift from it.
    """
    # The spec invariant already ties the two together: a non-"none" write
    # route requires a "local-state" side effect, so a leaf declaring no side
    # effect provably declares no write route either.
    if spec.policy.side_effects == frozenset({"none"}):
        return
    from ...core.storage_materialization import ensure_storage_tree

    ensure_storage_tree()


def resolved_command_profile_target(ctx: typer.Context) -> ProfileBucketPointer | None:
    """Return the one graph-declared explicit target resolved by dispatch."""
    value = cast("dict[str, object]", ctx.find_root().ensure_object(dict)).get(_RESOLVED_PROFILE_TARGET_KEY)
    if value is None:
        return None
    from ...application.workflow.profile_bucket_models import ProfileBucketPointer

    if not isinstance(value, ProfileBucketPointer):
        raise TypeError("resolved command profile target has an invalid type")
    return value


def consume_root_fallback(
    ctx: typer.Context,
    *,
    bucket_id: str,
    root: ProfileSecretSelection,
    leaf: MachineSecretSelection | None,
    spec: CommandSpec,
    arguments: Mapping[str, object],
) -> ProfileLoginOutcome:
    """Read all required payloads and authenticate exactly the requested profile.

    Proving that a live session now serves the profile belongs to the shared
    admission door, which applies it to every admitting branch rather than to
    this one. What stays here is the check only this caller can make: that the
    profile authenticated is the profile the invocation named.
    """
    _read_and_stage_leaf(spec=spec, arguments=arguments, selection=leaf)
    payload = read_profile_secret_payload(root_profile_secret_model(), selection=root)
    passphrase = ""
    try:
        if not isinstance(payload, ProfileAuthenticationSecrets):
            raise TypeError("root profile-secret model resolved an unexpected payload type")
        if payload.profile_passphrase is None:
            _refuse("profile_secrets_method_mismatch")
        passphrase = payload.profile_passphrase.get_secret_value()
        return _authenticate_for_invocation(ctx, bucket_id=bucket_id, passphrase_callback=lambda: passphrase)
    finally:
        passphrase = ""
        del payload


def prompt_root_authentication(ctx: typer.Context, *, bucket_id: str) -> ProfileLoginOutcome:
    """Authenticate exactly ``bucket_id`` for this invocation with a passphrase typed on the terminal.

    Reached only where no session can be resumed on this host at all, so the
    prompt is the one way an interactive operator gets past the gate. The
    caller has already established that a hardened no-echo prompt is possible.
    """
    from ...core.i18n.render import tr
    from .config.secure_input import prompt_secret_no_echo

    return _authenticate_for_invocation(
        ctx,
        bucket_id=bucket_id,
        passphrase_callback=lambda: prompt_secret_no_echo(tr("cli.config.login.passphrase_prompt")),
    )


def _authenticate_for_invocation(
    ctx: typer.Context,
    *,
    bucket_id: str,
    passphrase_callback: Callable[[], str],
) -> ProfileLoginOutcome:
    from ...application.user_profile.login_session import authenticate_profile_for_invocation
    from ...domain.calculations.registry.authority import bundled_indexed_authority

    # The target named here is scoped to THIS invocation, so it must not
    # become the operator's selection. Only `config login NAME` selects.
    with bundled_indexed_authority().operation() as operation:
        outcome = authenticate_profile_for_invocation(
            name=bucket_id,
            passphrase_callback=passphrase_callback,
            profile_decode_context=operation.profile_decode_context(),
        )
    if outcome.bucket_id != bucket_id:
        raise InternalInvariantError("profile authentication did not establish the exact requested session")
    from ._profile_session_gate import bind_profile_target

    bind_profile_target(ctx, bucket_id=bucket_id)
    if not outcome.session_persisted:
        from ._profile_authentication_notice import stage_profile_session_not_persisted_notice

        stage_profile_session_not_persisted_notice()
    return outcome


__all__ = [
    "consume_root_fallback",
    "preflight_parsed_leaf",
    "prompt_root_authentication",
    "resolved_command_profile_target",
]


def _profile_status_has_no_target(
    spec: CommandSpec,
    explicit_target: str | None,
    root: ProfileSecretSelection | None,
    credential_reference: UUID | None,
) -> bool:
    """Allow empty profile status only when no explicit or active target exists."""
    if (
        spec.key == "config_profile_status"
        and explicit_target is None
        and root is None
        and credential_reference is None
    ):
        from ...core.bucket_pointer import resolve_active_bucket_id

        if resolve_active_bucket_id() is None:
            return True
    return False


def _activate_runtime_leaf(
    ctx: typer.Context,
    spec: CommandSpec,
    arguments: Mapping[str, object],
    root: ProfileSecretSelection | None,
    leaf: MachineSecretSelection | None,
    explicit_target: str | None,
    explicit_label: str | None,
    method: ProfileAuthenticationMethod,
    credential_reference: UUID | None,
    runtime_profile_client: bool,
    command_path: tuple[str, ...],
) -> bool:
    """Apply special runtime routes before the ordinary session gate."""
    if _diagnose_unregistered_profile(spec=spec, root=root, credential_reference=credential_reference is not None):
        return True
    if _profile_status_has_no_target(spec, explicit_target, root, credential_reference):
        return True
    if spec.key == "config_profile_resume":
        _activate_profile_recovery(ctx, spec, arguments, root, leaf, explicit_target)
        return True
    if spec.key == "config_profile_automation_create":
        from ...core.bucket_pointer import resolve_active_bucket_id
        from ._profile_session_gate import bind_profile_target
        from .common import no_active_profile_refusal

        bucket_id = explicit_target or resolve_active_bucket_id()
        if bucket_id is None:
            raise no_active_profile_refusal()
        _read_and_stage_leaf(spec=spec, arguments=arguments, selection=leaf)
        bind_profile_target(ctx, bucket_id=bucket_id)
        return True
    if spec.key == "config_profile_automation_change":
        from .config.runtime_automation_request import stage_automation_change_input
        from .runtime_profile_admission import activate_runtime_profile

        if leaf is None:
            _refuse("automation_change_proposal_required")
        stage_automation_change_input(selection=leaf, kind=arguments.get("kind"))
        _require_resume_target(root, explicit_target, credential_reference=True)
        activate_runtime_profile(
            ctx,
            target_bucket_id=explicit_target,
            target_profile_label=explicit_label,
            root_selection=root,
            method=method,
            credential_reference=credential_reference,
        )
        return True
    if runtime_profile_client:
        from ._profile_session_gate import enforce_explicit_database_route
        from .runtime_profile_admission import activate_runtime_profile

        enforce_explicit_database_route(
            spec=spec,
            command_path=command_path,
            target_bucket_id=explicit_target,
        )
        _require_resume_target(root, explicit_target, credential_reference=credential_reference is not None)
        activate_runtime_profile(
            ctx,
            target_bucket_id=explicit_target,
            target_profile_label=explicit_label,
            root_selection=root,
            method=method,
            credential_reference=credential_reference,
        )
        return True
    return False


def _activate_profile_recovery(
    ctx: typer.Context,
    spec: CommandSpec,
    arguments: Mapping[str, object],
    root: ProfileSecretSelection | None,
    leaf: MachineSecretSelection | None,
    explicit_target: str | None,
) -> None:
    """Stage required leaf input before exact-target profile recovery."""
    from ...core.bucket_pointer import resolve_active_bucket_id
    from .common import no_active_profile_refusal
    from .runtime_profile_admission import activate_runtime_recovery

    if explicit_target is None and resolve_active_bucket_id() is None:
        raise no_active_profile_refusal()
    _read_and_stage_leaf(spec=spec, arguments=arguments, selection=leaf)
    activate_runtime_recovery(ctx, target_bucket_id=explicit_target, root_selection=root)
