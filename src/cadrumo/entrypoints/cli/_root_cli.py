"""Owned lazy handlers for the executable and ``app`` namespace roots.

The CLI package facade assembles the command graph.  Keeping executable root
callbacks on that facade made their deferred targets indistinguishable from
package bootstrap and forced the graph-import gate to exempt them.  This module
is the public behavior boundary resolved by the two owning ``CommandSpec``
nodes; importing command authority never imports it.
"""

from __future__ import annotations

from typing import cast

import typer

from ...core.output_rendering import OutputFormat
from ._common import preserve_requested_cli_leaf
from ._log_levels import resolve_log_level
from ._root_support import (
    _activate_profile_override,
    _emit_bare_invocation_and_exit,
    _emit_root_help_and_exit,
    _emit_version_report_and_exit,
    _is_introspection_only_invocation,
    _normalize_root_active_profile,
)


def root_command(
    ctx: typer.Context,
    language: str | None = None,
    profile: str | None = None,
    profile_secrets_stdin: bool = False,
    profile_secrets_fd: int | None = None,
    version: bool = False,
    detail: bool = False,
    help_: bool = False,
    format_: OutputFormat = OutputFormat.TEXT,
    tui: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Capture root-level CLI flags into the Typer context."""
    if language is not None:
        from ...core.config import override_settings

        ctx.with_resource(override_settings(cadrumo_output_language=language))
    state = cast("dict[str, object]", ctx.ensure_object(dict))
    state["format"] = format_
    state["tui_requested"] = tui
    state["log_level"] = resolve_log_level(quiet=quiet, verbose=verbose, debug=debug)
    if version:
        _emit_version_report_and_exit(detail=detail)
    if help_:
        _emit_root_help_and_exit(ctx)
    if ctx.invoked_subcommand is not None and _is_introspection_only_invocation(ctx):
        return
    from ...adapters.outbound.aeat.auth.provider_selection import select_provider as select_outbound_auth_provider
    from ...adapters.outbound.aeat.auth.session_store import build_session_store
    from ...adapters.persistence.profile.extracted_document_cache import ExtractedDocumentCacheRepository
    from ...adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
    from ...adapters.persistence.profile.justificante import JustificanteRepository
    from ...adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
    from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...adapters.persistence.profile.usage_ratios import load_usage_ratios_with_censo_guard
    from ...adapters.persistence.storage import build_profile_custody_port, build_profile_login_session_port
    from ...adapters.persistence.workflow import build_workflow_persistence_port
    from ...application.auth.protocols import bind_session_store
    from ...application.auth.providers import bind_auth_provider_selector
    from ...application.ledger.extracted_document_cache import bind_extracted_document_cache_repository_factory
    from ...application.ledger.extraction_draft_store import bind_extraction_draft_repository_factory
    from ...application.ledger.participation_read import bind_transaction_participation_index_repository_factory
    from ...application.ledger.rule_repository import bind_ledger_classification_rule_repository_factory
    from ...application.ledger.transaction_repository import bind_transaction_catalogue_repository_factory
    from ...application.ledger.usage_ratio_repository import bind_usage_ratio_censo_guard_loader
    from ...application.modelo.calculation_repository import bind_calculation_revision_catalogue_repository_factory
    from ...application.modelo.filing_repository import bind_modelo_record_catalogue_repository_factory
    from ...application.modelo.justificante_repository import bind_justificante_repository_factory
    from ...application.modelo.work_unit_repository import bind_work_unit_catalogue_repository_factory
    from ...application.user_profile.custody_ports import bind_profile_custody_port
    from ...application.user_profile.language_resolver import register_language_resolver
    from ...application.user_profile.login_session_port import bind_profile_login_session_port
    from ...application.workflow.persistence import bind_workflow_persistence_port

    ctx.with_resource(bind_profile_custody_port(build_profile_custody_port()))
    ctx.with_resource(bind_profile_login_session_port(build_profile_login_session_port()))
    ctx.with_resource(bind_workflow_persistence_port(build_workflow_persistence_port()))
    ctx.with_resource(bind_extraction_draft_repository_factory(ExtractionDraftRepository))
    ctx.with_resource(bind_extracted_document_cache_repository_factory(ExtractedDocumentCacheRepository))
    ctx.with_resource(bind_transaction_participation_index_repository_factory(TransactionParticipationIndexRepository))
    ctx.with_resource(bind_ledger_classification_rule_repository_factory(LedgerClassificationRuleRepository))
    ctx.with_resource(bind_transaction_catalogue_repository_factory(TransactionCatalogueRepository))
    ctx.with_resource(bind_usage_ratio_censo_guard_loader(load_usage_ratios_with_censo_guard))
    ctx.with_resource(bind_calculation_revision_catalogue_repository_factory(CalculationRevisionCatalogueRepository))
    ctx.with_resource(bind_modelo_record_catalogue_repository_factory(ModeloRecordCatalogueRepository))
    ctx.with_resource(bind_justificante_repository_factory(JustificanteRepository))
    ctx.with_resource(bind_work_unit_catalogue_repository_factory(WorkUnitCatalogueRepository))
    ctx.with_resource(bind_auth_provider_selector(select_outbound_auth_provider))
    ctx.with_resource(bind_session_store(build_session_store()))
    register_language_resolver()
    preserve_requested_cli_leaf(ctx)
    state["profile_override"] = profile
    if ctx.invoked_subcommand is None:
        from ._command_specs import COMMAND_GRAPH
        from ._tui_policy import enforce_tui_request

        enforce_tui_request(ctx, spec=COMMAND_GRAPH.by_key()["root"])
        if profile is not None:
            _activate_profile_override(ctx, profile)
        else:
            _normalize_root_active_profile(ctx)
        _emit_bare_invocation_and_exit(ctx)
    from ._profile_authentication_contract import ProfileSecretSourceOptions

    state["profile_secret_source"] = ProfileSecretSourceOptions(
        stdin=profile_secrets_stdin,
        descriptor=profile_secrets_fd,
    )


def app_root(ctx: typer.Context, help_: bool = False) -> None:
    """Render app-level workflow help when requested."""
    if help_ or ctx.invoked_subcommand is None:
        from ._command_specs import COMMAND_GRAPH
        from ._tui_policy import enforce_tui_request

        enforce_tui_request(ctx, spec=COMMAND_GRAPH.by_key()["app"])
        from ...application.operator_surface import build_help_document, render_help_text
        from ...core.json_contract import strict_round_trip
        from ._common import emit_envelope
        from ._root_payloads import AppRootResult

        document = build_help_document("app")
        typed_app = strict_round_trip(AppRootResult, document)
        emit_envelope(ctx, command="root.app", result=typed_app, lines=render_help_text(document).splitlines())
        raise typer.Exit()


__all__ = ["app_root", "root_command"]
