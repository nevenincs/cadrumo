"""Desktop shell chrome strings, generated from the canonical locale catalogues.

The desktop shell is a TypeScript frontend, so it cannot call ``tr()``. It
reads one generated JSON file instead, shaped ``{"<locale>": {"<key>":
"<text>"}}`` for every supported locale. The strings themselves live only in
the canonical catalogues: the shell's own chrome under ``desktop.*``, and the
Modelo and declarations wording every frontend shares under ``workspace.*``.
This module declares which keys the shell requires and projects their values.
Nothing here holds a translation.

:data:`DESKTOP_CHROME_KEYS` is the one declaration of the shell's keys. The
locale key scan reads it as a key source, because no Python call site names
these keys and a text scan would otherwise report every one of them as stale.
A key the shell builds at runtime from a template is declared in full, member
by member, in :data:`DESKTOP_CHROME_FAMILIES`. A declared key whose view is not
written yet is also listed in :data:`DESKTOP_CHROME_AWAITING_CONSUMER`.

Generation refuses rather than degrades: a key missing, blank, echoing its own
name, or carrying placeholders the shell cannot substitute in any locale stops
the build, so a release can never show a raw key. Given the shell's source,
generation also refuses a key or template the shell names that the declaration
does not carry, because the generated file would lack it.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Final

from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.i18n.render import extract_placeholders
from cadrumo_client.contracts.navigation import load_navigation_register

from ._paths import LOCALES_DIR, RUNTIME_SRC_DIR, SRC_DIR
from ._status import CatalogueLeafState, classify_catalogue_leaf
from .desktop_assets_keys import ASSET_FAMILIES, ASSET_KEYS, ASSET_PERCENT_PLACEHOLDER_PREFIXES
from .desktop_interface_keys import DESKTOP_INTERFACE_KEYS
from .desktop_ledger_catalogue_keys import DESKTOP_LEDGER_CATALOGUE_KEYS
from .desktop_ledger_document_keys import DESKTOP_LEDGER_DOCUMENT_KEYS
from .desktop_ledger_workflow_keys import DESKTOP_LEDGER_WORKFLOW_KEYS
from .desktop_workspace_keys import WORKSPACE_FAMILIES, WORKSPACE_KEYS
from .errors import LocaleError
from .locale_tree import _flatten_raw_locale_leaves
from .locale_yaml import locale_catalogue_source
from .manager import LocaleManager
from .service_catalogues import SERVICE_LOCALES_DIR

#: The shell's locales, source locale first.
DESKTOP_LOCALES: Final[tuple[str, ...]] = ("en", "es", "ca", "hu")
RUNTIME_LOCALES_DIR: Final[Path] = RUNTIME_SRC_DIR / "_data" / "locales"


_SPENDING_CATEGORIES: Final[tuple[str, ...]] = (
    "cuotas_colegiales",
    "cuotas_autonomos_ss",
    "mutualidad_alternativa",
    "arrendamiento_local",
    "arrendamiento_vivienda_afecto",
    "ibi_local_afecto",
    "suministros_local_afecto",
    "suministros_home_office_luz",
    "suministros_home_office_agua",
    "suministros_home_office_gas",
    "suministros_home_office_internet",
    "amortizacion_vivienda_afecto",
    "ibi_vivienda_afecto",
    "comunidad_vivienda_afecto",
    "telefonia_movil",
    "telefonia_fija",
    "material_oficina",
    "software_suscripcion",
    "hardware_amortizable",
    "mobiliario_amortizable",
    "reparaciones_conservacion",
    "vehiculo_combustible",
    "vehiculo_mantenimiento",
    "vehiculo_seguro",
    "vehiculo_peaje",
    "vehiculo_parking",
    "manutencion_dietas_nacional",
    "manutencion_dietas_extranjero",
    "asesoria_fiscal",
    "asesoria_juridica",
    "asesoria_contable",
    "publicidad_marketing",
    "formacion_profesional",
    "viajes_transporte",
    "viajes_alojamiento",
    "seguros_responsabilidad_civil",
    "seguros_salud_autonomo",
    "gastos_bancarios",
    "gastos_financieros",
    "suministros_cliente_directos",
    "subcontratacion",
    "tributos_fiscalmente_deducibles",
)


#: Keys the shell composes at runtime, as ``prefix -> members``: a template
#: such as ```desktop.example.kind_${kind}``` names ``desktop.example.kind_``
#: here with every member it can produce, and each resulting key is also
#: spelled out in :data:`DESKTOP_CHROME_KEYS`.
DESKTOP_CHROME_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType[str, tuple[str, ...]](
    {
        "desktop.aeat_sync.area.": (
            "census.about",
            "census.name",
            "filed.about",
            "filed.name",
            "notifications.about",
            "notifications.name",
            "vat.about",
            "vat.name",
            "borrador.about",
            "borrador.name",
            "identity.about",
            "identity.name",
        ),
        "desktop.aeat_sync.attempt.": ("failed", "nothing_found", "unknown"),
        "desktop.aeat_sync.progress.": (
            "title",
            "running",
            "stopping",
            "stopped",
            "paused_status",
            "done_all",
            "done_problems",
            "stop",
            "stop_hint",
            "paused",
            "resume",
            "waiting",
            "not_started",
            "outcome.brought",
            "outcome.nothing_found",
            "outcome.failed",
            "outcome.unknown",
            "reason.session_ended",
            "reason.no_access",
            "reason.unavailable",
            "reason.refused",
            "reason.other",
            "try_again",
            "try_again_for",
            "check_again",
            "check_again_for",
            "warn_unknown",
            "warn_confirm",
            "warn_cancel",
            "action_failed",
            "action_unknown",
            "unavailable",
        ),
        "desktop.aeat_sync.results.borrador.": ("imported", "nothing_found", "failed", "unknown"),
        "desktop.aeat_sync.results.changed.": (
            "census.one",
            "census.other",
            "filed.one",
            "filed.other",
            "other.one",
            "other.other",
        ),
        "desktop.aeat_sync.results.filed.differs.": ("status",),
        "desktop.aeat_sync.results.filed.group.": ("aeat_only", "differing", "local_only", "matched"),
        "desktop.aeat_sync.results.filed.record.": ("draft", "marked_filed"),
        "desktop.aeat_sync.results.new.": (
            "filed.one",
            "filed.other",
            "notifications.one",
            "notifications.other",
            "other.one",
            "other.other",
        ),
        "desktop.aeat_sync.results.notifications.group.": ("unread", "read"),
        "desktop.aeat_sync.results.reason.": ("session_ended", "no_access", "unavailable", "refused", "other"),
        "desktop.setup.item.": ("browser", "local_ai"),
        "desktop.setup.state.": (
            "absent",
            "blocked",
            "failed",
            "provisioning",
            "ready",
            "stale",
            "unknown",
            "verifying",
        ),
        "desktop.setup.stale.": ("older_revision", "program_too_old"),
        "desktop.setup.blocked.": ("hardware", "needs_person", "not_in_this_build", "offline"),
        "desktop.setup.failure.": (
            "blocked_by_network",
            "cancelled",
            "damaged_download",
            "disk_full",
            "host_unreachable",
            "interrupted",
            "memory_busy",
            "needs_sign_in",
            "no_permission",
            "not_enough_memory",
            "not_in_this_build",
            "offline",
            "program_missing",
            "program_not_running",
            "program_proxy_differs",
            "secure_connection_failed",
            "unexpected",
        ),
        "desktop.setup.action.": ("check_again", "resume", "set_up", "try_again", "update"),
        "desktop.startup.": (
            "starting",
            "progress",
            "environment_step",
            "runtime_step",
            "workspace_step",
            "environment",
            "runtime",
            "workspace",
            "failed",
            "failure",
            "interrupted",
        ),
        "desktop.profile.view.status_": ("required", "unset", "filled"),
        "desktop.attendance.": ("network", "changes", "delegation", "period_independent"),
        "desktop.calendar.aeat.": ("accepted", "justificante_verified", "not_observed", "submitted_observed"),
        "desktop.calendar.event.": ("filing", "message"),
        "desktop.calendar.local.": ("external_baseline_imported", "not_ready_to_file", "ready_to_file"),
        "desktop.calendar.state.": ("due", "filed", "late", "unknown"),
        "desktop.ledger.section.": ("movements", "invoices", "documents", "rules", "registers", "health"),
        "desktop.ledger.category.": _SPENDING_CATEGORIES,
        "desktop.ledger.category_keywords.": _SPENDING_CATEGORIES,
        "desktop.ledger.category_family.": (
            "social_security",
            "premises",
            "home_office_suministros",
            "home_office_ownership",
            "telecoms",
            "office",
            "vehicle",
            "meals",
            "professional_services",
            "travel",
            "insurance",
            "financial",
            "direct_costs",
            "taxes",
        ),
        "desktop.ledger.iva_category.": (
            "domestic_general",
            "domestic_reduced",
            "domestic_super_reduced",
            "domestic_zero",
            "domestic_exempt",
            "domestic_not_subject",
            "domestic_reverse_charge",
            "intra_community_supply",
            "intra_community_acquisition_reverse_charge",
            "intra_community_triangulation",
            "export_third_country_zero_rated",
            "export_assimilated_zero_rated",
            "import_third_country",
            "recargo_equivalencia",
            "regimen_simplificado",
            "reagp_compensation",
            "operacion_no_sujeta",
            "erroneous_invoice",
            "unknown",
            "intra_community_service_supply",
            "intra_community_service_acquisition_reverse_charge",
        ),
        "desktop.ledger.irpf_category.": (
            "actividad_economica",
            "arrendamiento_local",
            "arrendamiento_vivienda_afecto",
            "trabajo",
        ),
        "desktop.ledger.classification.": (
            "business",
            "personal",
            "mixed",
            "not_yet_processed",
            "processed_unclassified",
            "skipped_by_rule",
            "failed_validation",
            "reviewed_excluded",
        ),
        "desktop.ledger.classify.as_": ("business", "personal", "mixed"),
        "desktop.ledger.classify.title_": ("business", "mixed", "personal", "category"),
        "desktop.ledger.column.": (
            "select",
            "status",
            "date",
            "description",
            "counterparty",
            "direction",
            "amount",
            "eur",
            "classification",
            "category",
            "iva_category",
            "taxable_base",
            "iva_rate",
            "iva_amount",
            "irpf_category",
            "invoice",
            "documents",
            "group_label",
            "notes",
            "lifecycle",
            "classified_by",
            "modified",
            "account",
        ),
        "desktop.ledger.columns.preset.": ("review", "iva", "irpf", "everything"),
        "desktop.ledger.direction.": ("incoming", "outgoing", "internal_transfer"),
        "desktop.ledger.group.": (
            "category",
            "category_family",
            "classification",
            "status",
            "direction",
            "month",
            "group_label",
            "iva_category",
            "counterparty",
            "description",
            "account",
        ),
        "desktop.ledger.group.empty.": (
            "category",
            "category_family",
            "classification",
            "status",
            "direction",
            "month",
            "group_label",
            "iva_category",
            "counterparty",
            "description",
            "account",
        ),
        "desktop.ledger.import_issue.": ("original_file", "gap", "duplicate", "parser"),
        "desktop.ledger.lifecycle.": ("active", "archived", "stashed", "split"),
        "desktop.ledger.readiness_filter.": ("issues", "to_classify", "no_rate"),
        "desktop.ledger.reason.": (
            "missing_business_classification",
            "missing_category",
            "missing_taxable_base",
            "missing_iva_amount",
            "missing_iva_rate",
            "missing_eur_tax_substrate",
            "missing_counterparty_identification_state",
            "domestic_identification_on_intra_community_transaction",
            "eu_member_state_on_export_transaction",
            "missing_counterparty_establishment_on_export",
            "inadmissible_deduction_classification",
            "missing_proportionality_reference",
            "unsupported_currency",
            "unsupported_period",
            "censo_ratio_mismatch",
            "missing_home_office_afectacion",
            "anomaly_non_declarable_iva_category",
            "anomaly_non_declarable_recargo_equivalencia",
        ),
        "desktop.ledger.reason_detail.": (
            "missing_business_classification",
            "missing_category",
            "missing_taxable_base",
            "missing_iva_amount",
            "missing_iva_rate",
            "missing_eur_tax_substrate",
            "missing_counterparty_identification_state",
            "domestic_identification_on_intra_community_transaction",
            "eu_member_state_on_export_transaction",
            "missing_counterparty_establishment_on_export",
            "inadmissible_deduction_classification",
            "missing_proportionality_reference",
            "unsupported_currency",
            "unsupported_period",
            "censo_ratio_mismatch",
            "missing_home_office_afectacion",
            "anomaly_non_declarable_iva_category",
            "anomaly_non_declarable_recargo_equivalencia",
        ),
        "desktop.ledger.review.": ("pending", "reviewed", "skipped", "excluded"),
        "desktop.ledger.sort.": ("asc", "desc"),
        "desktop.ledger.sort.key.": (
            "date",
            "value_date",
            "created_at",
            "classified_at",
            "amount",
            "description",
            "counterparty",
            "classification",
            "category",
            "iva_category",
            "eur",
            "status",
            "direction",
            "group_label",
            "lifecycle",
            "modified",
            "taxable_base",
            "iva_rate",
            "iva_amount",
            "irpf_category",
            "notes",
            "classified_by",
            "select",
            "invoice",
            "documents",
            "account",
        ),
        "desktop.ledger.status.": ("pending", "needs_fixing", "done", "skipped", "excluded"),
        "desktop.ledger.view.": ("all", "to_classify", "to_fix", "to_match", "foreign", "business_expenses"),
        "desktop.ledger.import.refusal.": (
            "transaction_validation",
            "own_account_mismatch",
            "result_limit",
            "source_changed",
            "empty_directory",
            "file_limit",
            "reader_unavailable",
        ),
        "desktop.ledger.import.diagnostic.": (
            "no_rows",
            "already_in_ledger",
            "same_identity",
            "repeated",
            "gap",
            "verified",
            "unreadable",
        ),
        "desktop.ledger.import.provider.": ("auto", "csv", "ofx", "qfx", "xlsx", "xls", "pdf"),
        "desktop.ledger.import.direction.": ("incoming", "outgoing", "internal_transfer"),
        "desktop.ledger.import.filter.": ("bank", "book", "documents"),
        "desktop.ledger.import.kind.": ("bank", "book", "documents"),
        "desktop.ledger.import.drop.": ("bank", "book", "documents"),
        "desktop.ledger.import.accepts.": ("bank", "book", "documents"),
        "desktop.ledger.import.step.": ("what", "preview", "result"),
        "desktop.ledger.import.heading.": ("what", "preview", "result"),
        "desktop.ledger.import.kind_": ("received", "issued"),
        "desktop.ledger.import.account_": ("detected", "unregistered", "no_accounts"),
        "desktop.ledger.export.filter.": ("csv", "jsonl", "xlsx"),
        "desktop.ledger.export.format_": ("csv", "jsonl", "xlsx"),
        "desktop.ledger.export.tsv.": (
            "kind",
            "series",
            "number",
            "date",
            "counterparty",
            "tax_id",
            "country",
            "base",
            "iva",
            "total",
            "currency",
            "payment",
            "description",
            "direction",
            "amount",
            "classification",
            "category",
            "group",
            "id",
        ),
        "desktop.ledger.invoices.class.": ("ordinaria", "simplificada", "rectificativa"),
        "desktop.ledger.invoices.column.": (
            "number",
            "kind",
            "date",
            "operation_date",
            "counterparty",
            "tax_id",
            "country",
            "class",
            "base",
            "iva",
            "recargo",
            "retention",
            "total",
            "currency",
            "linked",
            "payment",
            "notes",
        ),
        "desktop.ledger.invoices.field.": (
            "counterparty_name",
            "counterparty_country",
            "notes",
            "payment_status",
            "iva_category",
            "operation_type",
            "operation_date",
            "retention_rate",
            "retention_amount",
            "series",
            "invoice_class",
            "rectifies_invoice_number",
            "payment_id",
        ),
        "desktop.ledger.invoices.invariant.": ("counterparty", "country", "line", "totals"),
        "desktop.ledger.invoices.kind.": ("issued", "received"),
        "desktop.ledger.invoices.kind_choice.": ("issued", "received"),
        "desktop.ledger.invoices.kinds.": ("all", "issued", "received"),
        "desktop.ledger.invoices.line.": ("description", "quantity", "unit_price", "rate", "category"),
        "desktop.ledger.invoices.payment.": ("paid", "pending", "partially_paid", "overdue", "cancelled"),
        "desktop.ledger.invoices.problem.": (
            "choose_kind",
            "country_letters",
            "currency_letters",
            "tax_id_required",
            "series_required",
            "rectifies_required",
            "choose_rate",
            "no_line",
            "recargo_above_iva",
            "printed_differs",
            "retention_above_base",
            "retention_needs_amount",
            "retention_differs",
            "lease_reference_not_allowed",
            "payment_id_shape",
            "operation_date_fixed",
        ),
        "desktop.ledger.invoices.rate.": ("exempt", "not_subject"),
        "desktop.ledger.invoices.refusal.": (
            "too_long",
            "signed",
            "exponent",
            "currency_symbol",
            "comma_decimal",
            "grouping",
            "ambiguous_grouping",
            "too_many_decimals",
            "zero",
            "not_a_number",
            "percent_as_fraction",
            "percent_above_100",
            "date_not_iso",
            "date_not_in_calendar",
            "not_a_date",
            "line_break",
        ),
        "desktop.ledger.invoices.situacion.s": ("1", "2", "3", "4"),
        "desktop.ledger.documents.viewer.refused.": (
            "not_found",
            "digest_mismatch",
            "unsupported_media",
            "too_large",
            "out_of_range",
            "unreadable",
        ),
        "desktop.ledger.documents.field.": (
            "supplier_name",
            "supplier_tax_id",
            "customer_name",
            "customer_tax_id",
            "counterparty_name",
            "counterparty_tax_id",
            "invoice_number",
            "series",
            "invoice_series",
            "invoice_date",
            "taxable_base",
            "iva_rate",
            "iva_amount",
            "recargo_amount",
            "retention_rate",
            "retencion_rate",
            "retention_amount",
            "retencion_amount",
            "grand_total",
            "currency",
        ),
        "desktop.ledger.documents.grounding.": (
            "reconciled",
            "anchored",
            "unanchored",
            "ambiguous",
            "contradicted",
        ),
        "desktop.ledger.documents.origin.": (
            "exact_structured",
            "text_layer",
            "text_rules",
            "vision",
            "tabular_mapped",
            "operator",
            "derived",
        ),
        "desktop.ledger.documents.reason.": (
            "closure_discrepancy",
            "ambiguous_identity",
            "unresolved_direction",
            "contradicted_regime",
            "undetermined_establishment",
            "unmodelled_invoice_class",
            "contradicted_invoice_class",
        ),
        "desktop.ledger.documents.hold.": (
            "choose_kind",
            "country",
            "currency",
            "findings",
            "corrections",
            "duplicate",
        ),
        "desktop.ledger.documents.media.": (
            "pdf",
            "image",
        ),
        "desktop.ledger.documents.record.": (
            "supplier",
            "invoice_number",
            "invoice_date",
            "taxable_base",
            "iva_rate",
            "iva_amount",
            "notes",
        ),
        "desktop.ledger.documents.source.": (
            "local_file",
            "gmail",
            "google_drive",
            "url",
            "inline",
        ),
        "desktop.ledger.documents.tab.": (
            "review",
            "records",
            "attachments",
            "folder",
            "sent",
            "readers",
        ),
        "desktop.ledger.documents.batch_status.": (
            "ingested",
            "no_op",
            "refused",
            "pending_review",
            "paused",
        ),
        "desktop.ledger.edit.refusal.": (
            "too_long",
            "signed",
            "exponent",
            "currency_symbol",
            "comma_decimal",
            "grouping",
            "ambiguous_grouping",
            "too_many_decimals",
            "zero",
            "not_a_number",
            "percent_as_fraction",
            "percent_above_100",
            "date_not_iso",
            "date_not_in_calendar",
            "not_a_date",
            "year_not_a_number",
            "year_out_of_range",
            "period_unknown",
            "line_break",
            "required",
            "cannot_clear",
            "unknown_choice",
            "needs_share",
            "locked",
        ),
        "desktop.ledger.edit.step.": (
            "set",
            "clear",
            "paste",
            "fill",
            "bulk_set",
            "revert_cell",
            "revert_movement",
            "discard",
            "add_draft",
            "edit_draft",
            "remove_draft",
            "stage_action",
            "drop_action",
        ),
        "desktop.ledger.edit.hint.": ("amount", "figure", "date", "percent"),
        "desktop.ledger.edit.lock.": ("sealed", "transfer", "after_add", "derived"),
        "desktop.ledger.edit.held.": ("cannot_clear", "needs_classification"),
        "desktop.ledger.field.": (
            "booked_date",
            "value_date",
            "currency",
            "business_pct",
            "usage_ratio_id",
            "counterparty_country",
            "counterparty_identification_state",
            "deduction_fact_kind",
            "investment_asset_id",
            "own_account_id",
            "recargo_amount",
            "m210_income_classification",
        ),
        "desktop.ledger.paste.refused_": ("unclosed_quote", "empty"),
        "desktop.ledger.paused.found_": ("saved", "not_saved", "undetermined"),
        "desktop.ledger.paused.counted_": ("saved", "not_saved", "undetermined"),
        "desktop.ledger.apply.": ("mine", "theirs"),
        "desktop.ledger.apply.gone_": ("mine", "theirs"),
        "desktop.ledger.apply.blocker.": (
            "gone",
            "not_active",
            "sealed",
            "cannot_clear",
            "needs_classification",
            "mixed_needs_share",
            "share_needs_mixed",
            "transfer_with_tax",
            "action_and_edits",
            "exclude_and_classification",
            "suggestion_and_edits",
            "suggestion_and_rules",
            "suggestion_needs_share",
            "actions_conflict",
            "too_large",
            "draft_incomplete",
            "sealed_unread",
        ),
        "desktop.ledger.apply.action.": (
            "link",
            "attach",
            "detach",
            "archive",
            "stash",
            "restore",
            "exclude",
            "split",
            "merge",
            "remove",
            "suggestion",
            "m210",
        ),
        "desktop.ledger.apply.outcome.not_sent_": ("paused", "stopped", "after_refusal", "after_part", "parts_unnamed"),
        "desktop.ledger.apply.tally.": (
            "applied",
            "unchanged",
            "settled",
            "refused",
            "unknown",
            "saved_unread",
            "not_sent",
        ),
        "desktop.ledger.accounts.holding.": ("titular", "cotitular"),
        "desktop.ledger.accounts.iban_problem.": ("shape", "check"),
        "desktop.ledger.accounts.named.": ("update", "close", "designate"),
        "desktop.ledger.accounts.role.": ("charge", "refund"),
        "desktop.ledger.accounts.submit.": ("add", "update", "close", "designate"),
        "desktop.ledger.assets.refusal.": (
            "refused_actividad_asset_validation",
            "refused_actividad_asset_unsupported",
            "refused_actividad_asset_incomplete",
            "refused_actividad_asset_claim_conflict",
            "refused_actividad_asset_accelerated_da18_depreciation_not_computed",
        ),
        "desktop.ledger.assets.revision.": ("create", "correct"),
        "desktop.ledger.assets.submit.": ("create", "correct", "forecast", "filing"),
        "desktop.ledger.assets.target.": ("material_m100", "intangible_m100", "material_m130", "intangible_m130"),
        "desktop.ledger.assets.task.": ("create", "correct", "forecast", "filing"),
        "desktop.ledger.capital.disposal.": ("sujeta_no_exenta", "exenta_o_no_sujeta"),
        "desktop.ledger.capital.kind.": ("mueble", "inmueble"),
        "desktop.ledger.capital.refusal.": ("validation", "disposal_incomplete", "duplicate_identifier"),
        "desktop.ledger.counterparty.scope.": (
            "es_mainland",
            "es_canarias",
            "es_ceuta_melilla",
            "eu_member",
            "third_country",
        ),
        "desktop.ledger.counterparty.source.": ("document_evidence", "profile_authority", "operator_assertion"),
        "desktop.ledger.health.count.": ("active", "archived", "stashed", "split", "pending", "reviewed", "skipped"),
        "desktop.ledger.inventory.form.": ("create", "movement", "closing"),
        "desktop.ledger.inventory.kind.": ("opening", "purchase", "cogs", "count"),
        "desktop.ledger.inventory.method.": ("fifo", "pmp", "coste_medio"),
        "desktop.ledger.inventory.refusal.": (
            "activity_conflict",
            "activity_not_found",
            "invalid_valuation_method",
            "duplicate_movement_id",
            "inventory_validation",
            "closing_authority_conflict",
            "closing_authority_invalid",
        ),
        "desktop.ledger.inventory.task.": ("create", "movement", "closing"),
        "desktop.ledger.prorrata.action.": (
            "seed",
            "declare_sector",
            "elect_general",
            "elect_especial",
            "revoke_especial",
            "seed_sector",
            "settle_sector",
        ),
        "desktop.ledger.prorrata.form.": (
            "seed",
            "declare_sector",
            "elect_general",
            "elect_especial",
            "revoke_especial",
            "seed_sector",
            "settle_sector",
        ),
        "desktop.ledger.prorrata.letra.": ("a", "b", "c", "d"),
        "desktop.ledger.prorrata.provenance.": (
            "aeat_autorizada",
            "inicio_actividad",
            "carried_prior_definitiva",
            "interrumpida_tres_ultimos",
        ),
        "desktop.ledger.prorrata.refusal.": (
            "validation",
            "provenance_required",
            "provenance_not_electable",
            "reference_required",
            "reference_not_permitted",
            "seed_source_absent",
            "seed_source_blocked",
            "seed_existing_blocked",
            "regulated_override_standing",
            "sector_prior_definitive_absent",
            "sector_settlement_entry_absent",
        ),
        "desktop.ledger.prorrata.regime.": ("general", "especial"),
        "desktop.ledger.ratios.kind.": (
            "full_deductible",
            "statutory_cap",
            "usage_ratio_home_area",
            "usage_ratio_personal",
        ),
        "desktop.ledger.registers.area.": ("accounts", "prorrata", "capital", "inventory", "assets"),
        "desktop.ledger.rules.area.": ("rules", "ratios", "counterparties", "diagnostics"),
        "desktop.ledger.rules.refusal.": ("empty_pattern", "invalid_pattern", "category", "invalid_command"),
        **WORKSPACE_FAMILIES,
        **ASSET_FAMILIES,
    }
)

DESKTOP_CHROME_KEYS: Final[frozenset[str]] = (
    DESKTOP_LEDGER_DOCUMENT_KEYS
    | DESKTOP_LEDGER_WORKFLOW_KEYS
    | DESKTOP_LEDGER_CATALOGUE_KEYS
    | DESKTOP_INTERFACE_KEYS
    | WORKSPACE_KEYS
    | ASSET_KEYS
)

#: Declared keys no shell source names yet, because their view is still being
#: written. They are authored and generated like every other key; the drift
#: check holds the rest of the declaration to an exact match with the shell
#: source and refuses any key here once the shell names it, so a key leaves
#: this set when its view lands and the set only shrinks.
DESKTOP_CHROME_AWAITING_CONSUMER: Final[frozenset[str]] = frozenset({"desktop.signin.unsupported"})

#: A whole key in quotes, or the fixed head of a template literal up to ``${``.
_SHELL_LITERAL_KEY: Final[re.Pattern[str]] = re.compile(
    r"""["'`]((?:desktop|workspace|ledger\.actividad_asset|auth\.sync\.requirement)\.[A-Za-z0-9_.]+)["'`]"""
)
_SHELL_TEMPLATE_HEAD: Final[re.Pattern[str]] = re.compile(
    r"`((?:desktop|workspace|ledger\.actividad_asset)\.[A-Za-z0-9_.]*)\$\{"
)


def shell_key_references(source: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Return the literal keys and the template prefixes the shell source names.

    Generated files are skipped: they hold the strings, not the uses of them.

    Raises:
        LocaleError: when ``source`` holds no TypeScript, so nothing would be checked.
    """
    literals: set[str] = set()
    templates: set[str] = set()
    sources = [
        path
        for pattern in ("*.ts", "*.tsx")
        for path in source.rglob(pattern)
        if "generated" not in path.relative_to(source).parts
    ]
    if not sources:
        raise LocaleError(f"No desktop shell source under {source}, so no key it names could be checked")
    for path in sources:
        text = path.read_text(encoding=UTF_8_ENCODING)
        literals.update(_SHELL_LITERAL_KEY.findall(text))
        templates.update(_SHELL_TEMPLATE_HEAD.findall(text))
    # A constant such as ``"desktop.example.progress."`` that later code joins
    # with a member names a family, not a catalogue leaf.
    templates.update(key for key in literals if key.endswith("."))
    literals = {key for key in literals if not key.endswith(".")}
    return frozenset(literals), frozenset(templates)


def shell_named_keys(
    literals: frozenset[str], templates: frozenset[str], families: Mapping[str, tuple[str, ...]]
) -> frozenset[str]:
    """Return every key named, expanding the templates that have a declared family."""
    return literals | {f"{prefix}{member}" for prefix in templates & families.keys() for member in families[prefix]}


def shell_drift(
    source: Path,
    keys: frozenset[str] = DESKTOP_CHROME_KEYS - DESKTOP_CHROME_AWAITING_CONSUMER,
    families: Mapping[str, tuple[str, ...]] = DESKTOP_CHROME_FAMILIES,
) -> dict[str, list[str]]:
    """Compare what the shell source names with a key declaration."""
    literals, templates = shell_key_references(source)
    used = shell_named_keys(literals, templates, families)
    return {
        "undeclared_templates": sorted(templates - families.keys()),
        "undeclared": sorted(used - keys),
        "unused": sorted(keys - used),
    }


def refuse_unbuilt_shell_keys(source: Path) -> None:
    """Refuse a key or template the shell names that generation would not carry.

    Such a key is absent from the generated file, so the shell would show the key
    itself; the build stops instead. A declared key nothing names yet is the drift
    test's concern and does not stop a build.
    """
    drift = shell_drift(source, DESKTOP_CHROME_KEYS, DESKTOP_CHROME_FAMILIES)
    missing = drift["undeclared_templates"] + drift["undeclared"]
    if missing:
        raise LocaleError("The desktop shell names keys the chrome declaration does not carry: " + ", ".join(missing))


# The only placeholder form the shell substitutes: ``{name}``.
_SHELL_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{(\w+)\}")


def _catalogue_leaves(locales_dir: Path, locale: str) -> dict[str, object]:
    """Read one locale's catalogue leaves through the catalogue authority."""
    source = locale_catalogue_source(locales_dir, locale)
    if source is None:
        raise LocaleError(f"No catalogue for desktop locale {locale!r} under {locales_dir}")
    return _flatten_raw_locale_leaves(LocaleManager(SRC_DIR, locales_dir).load_locale(source))


#: The navigation register's label keys, read through its validating loader.
#: The shell reads them by key from its generated navigation projection, never
#: by name in its source, so they are generated beside the declared keys rather
#: than declared with them; a missing translation refuses generation the same way.
DESKTOP_NAVIGATION_LABEL_KEYS: Final[frozenset[str]] = frozenset(
    element.label for element in load_navigation_register().elements
)

#: The navigation register's search-keyword keys, read the same way. The
#: palette finds an element by its keywords in the person's language, so each
#: is generated in every locale beside its label.
DESKTOP_NAVIGATION_KEYWORD_KEYS: Final[frozenset[str]] = frozenset(
    element.keywords for element in load_navigation_register().elements
)


def _shell_placeholders(key: str, locale: str, value: str) -> frozenset[str]:
    """Return the ``{name}`` placeholders of ``value``, refusing any other form."""
    shell = frozenset(str(match.group(1)) for match in _SHELL_PLACEHOLDER.finditer(value))
    if shell != extract_placeholders(value) or "%{" in value:
        raise LocaleError(
            f"{locale}:{key} carries a placeholder the desktop shell cannot substitute; use plain {{name}}"
        )
    return shell


_PERCENT_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"%\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _in_shell_form(key: str, value: str) -> str:
    """Write the ``%{name}`` placeholders of a backend-rendered key as the ``{name}`` the shell substitutes.

    Only the families the backend renders itself are converted: it renders a
    ``%{name}`` placeholder and a ``{name}`` one the same way, so the sentence is
    unchanged. Every other key still refuses the form.
    """
    if not key.startswith(ASSET_PERCENT_PLACEHOLDER_PREFIXES):
        return value
    return _PERCENT_PLACEHOLDER.sub(r"{\1}", value)


def _project_locale(locales_dir: Path, locale: str, keys: frozenset[str], refusals: list[str]) -> dict[str, str]:
    leaves = _catalogue_leaves(locales_dir, locale)
    if locales_dir == LOCALES_DIR:
        for owner, owned_locales in (("runtime", RUNTIME_LOCALES_DIR), ("service", SERVICE_LOCALES_DIR)):
            if not owned_locales.is_dir():
                continue
            owned_leaves = _catalogue_leaves(owned_locales, locale)
            collisions = leaves.keys() & owned_leaves.keys()
            if collisions:
                raise LocaleError(f"Desktop and {owner} catalogue keys overlap: {sorted(collisions)}")
            leaves.update(owned_leaves)
    values: dict[str, str] = {}
    for key in sorted(keys):
        leaf = leaves.get(key)
        value = leaf if isinstance(leaf, str) else None
        state = classify_catalogue_leaf(key, value)
        if state is not CatalogueLeafState.AUTHORED or value is None:
            refusals.append(f"{locale}:{key} is {state.value}")
            continue
        values[key] = _in_shell_form(key, value)
    return values


def desktop_chrome_strings(
    locales_dir: Path = LOCALES_DIR,
    *,
    keys: frozenset[str] = DESKTOP_CHROME_KEYS | DESKTOP_NAVIGATION_LABEL_KEYS | DESKTOP_NAVIGATION_KEYWORD_KEYS,
    locales: Sequence[str] = DESKTOP_LOCALES,
) -> dict[str, dict[str, str]]:
    """Project the declared keys out of every locale catalogue.

    Raises:
        LocaleError: when any declared key is not an authored string in every
            locale, or its placeholders differ between locales or use a form
            the shell does not substitute.
    """
    refusals: list[str] = []
    strings = {locale: _project_locale(locales_dir, locale, keys, refusals) for locale in locales}
    if refusals:
        raise LocaleError("Desktop chrome strings are incomplete: " + "; ".join(refusals))
    for key in sorted(keys):
        placeholders = {locale: _shell_placeholders(key, locale, strings[locale][key]) for locale in locales}
        if len(set(placeholders.values())) != 1:
            detail = ", ".join(f"{locale} {sorted(names)}" for locale, names in placeholders.items())
            raise LocaleError(f"{key} has different placeholders across locales: {detail}")
    return strings


def render_desktop_chrome(strings: Mapping[str, Mapping[str, str]]) -> str:
    """Serialize the projection deterministically, keys sorted, as plain UTF-8 JSON."""
    return json.dumps(strings, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Write the desktop shell's chrome strings."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # The build names where its generated inputs go; nothing is written into the source tree by default.
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--shell-source",
        type=Path,
        help="the shell's TypeScript source; refuse a key it names that generation would not carry",
    )
    arguments = parser.parse_args(argv)
    shell_source: object = arguments.shell_source
    try:
        if isinstance(shell_source, Path):
            refuse_unbuilt_shell_keys(shell_source)
        strings = desktop_chrome_strings()
    except LocaleError as exc:
        parser.exit(1, f"refused: {exc}\n")
    output: object = arguments.output
    if not isinstance(output, Path):
        parser.error("--output must resolve to a filesystem path")
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, render_desktop_chrome(strings), encoding=UTF_8_ENCODING)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
