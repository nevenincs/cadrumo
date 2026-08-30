"""Repo-wide regression gate for killed combined period strings."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from re import Pattern

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCAN_ROOTS = ("src/cadrumo", "docs")
SKIPPED_PARTS = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "_build",
        "pagefind",
    }
)
TEXT_SUFFIXES = frozenset(
    {
        ".cfg",
        ".csv",
        ".html",
        ".ini",
        ".json",
        ".md",
        ".py",
        ".rst",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
)

COMBINED_PERIOD_PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    ("calendar quarter token", re.compile(r"(?<![A-Za-z0-9])(?:19|20|21|22)\d{2}Q[1-4](?![A-Za-z0-9])")),
    ("year-qualified quarterly token", re.compile(r"(?<![A-Za-z0-9])(?:19|20|21|22)\d{2}-[1-4]T(?![A-Za-z0-9])")),
    (
        "period assignment with combined year prefix",
        re.compile(r"\bperiod\s*=\s*[\"']?(?:19|20|21|22)\d{2}(?:Q[1-4]|-[A-Z0-9-]+|A)?(?=[\"',)\]}]|\s*(?:#|$)|$)"),
    ),
)


@dataclass(frozen=True)
class AllowlistRule:
    """Document one intentional combined-period string bucket."""

    path: Pattern[str]
    reason: str
    pattern_names: frozenset[str] | None = None
    text: Pattern[str] | None = None

    def matches(self, path: str, pattern_name: str, text: str) -> bool:
        if not self.path.search(path):
            return False
        if self.pattern_names is not None and pattern_name not in self.pattern_names:
            return False
        return self.text is None or self.text.search(text) is not None


def _path(pattern: str) -> Pattern[str]:
    return re.compile(pattern)


def _text(pattern: str) -> Pattern[str]:
    return re.compile(pattern)


ALLOWLIST: tuple[AllowlistRule, ...] = (
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/workflow/_state_models\.py$"),
        reason=(
            "the docstring documents the prohibition itself -- it states that declaration "
            "state never keys by a combined token, and names the combined form as the "
            "counter-example. Rewriting it would delete the explanation of why the "
            "identity segment is stored as filing_year:registry_token"
        ),
        pattern_names=frozenset({"calendar quarter token"}),
        text=_text(r"never keys by a combined token"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/_data/registry/aeat/modelos/"),
        reason=(
            "registry PROSE naming AEAT design editions and candidate revision identifiers. "
            "A revision id legitimately carries a year and a period span -- 2011-y-siguientes "
            "is a real one on this very modelo -- so a comment reasoning about how a modelo "
            "SHOULD be partitioned must be able to name the partitions. These are comments, "
            "never a value the loader parses as a period selector"
        ),
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"^\s*#"),
    ),
    AllowlistRule(
        path=_path(r"^docs/_sequences/"),
        reason=(
            "captured CLI transcripts record a work_unit LISTING, whose own columns "
            "carry modelo, filing year and period separately; the token appears only in "
            "the operator-supplied NAME column, which is a label the app never parses "
            "back into a period"
        ),
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"work_unit"),
    ),
    AllowlistRule(
        path=_path(r"^docs/_sequences/"),
        reason=(
            "captured CLI transcripts record the argv an author typed; the token is a "
            "recorded evidence FILENAME, and the sequence is a replay artefact rather "
            "than a call site that could parse it"
        ),
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"fixtures/"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/_data/registry/aeat/legal/"),
        reason=(
            "legal entries quote an Orden's own published title verbatim, and several "
            "name the span they govern ('hasta periodo 1T'); altering official wording "
            "to satisfy a grammar rule would break the corpus cross-check"
        ),
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"Orden|Ejercicio|periodo|quarter|trimestre"),
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/application/modelo/tests/test_(?:"
            r"m303_filing_evidence_validation|m303_regimen_simplificado_scope|"
            r"modelo_work_review|prior_domiciliation_election"
            r")\.py$"
        ),
        reason=(
            "operator-facing work-unit LABELS and AEAT CSV evidence references; the "
            "period reaches these tests as a typed filing_year/period pair and the "
            "string is only what the operator or the authority prints"
        ),
        pattern_names=frozenset({"year-qualified quarterly token"}),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/storage/sync_runs/tests/test_sync_run_record_store\.py$"),
        reason="resolved_scope is a rendered display string persisted for the operator, not a period selector",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"resolved_scope"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/entrypoints/cli/tests/test_(?:ledger_list_filter|modelo_work_review_envelope)\.py$"),
        reason=(
            "the combined form is the REFUSED input under test -- ledger_list_filter "
            "proves the calendar-quarter grammar is rejected -- and a work-unit label "
            "in the envelope test; both would lose their subject if rewritten"
        ),
        pattern_names=frozenset({"year-qualified quarterly token", "calendar quarter token"}),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part2\.py$"),
        reason="a bundled submitted-file fixture constant carries the captured artefact's own filename",
        pattern_names=frozenset({"year-qualified quarterly token"}),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/modelo/tests/test_export_output_paths\.py$"),
        reason="AEAT CSV evidence reference, an authority-issued identifier the test echoes verbatim",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"CSV-"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/tests/fixtures/"),
        reason="external HTML/PDF corpus and fixture generation material preserves official/source labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/_data/registry/aeat/modelos/"),
        reason="registry parser declarations may mention external fixture filenames in comments",
        pattern_names=frozenset({"year-qualified quarterly token", "calendar quarter token"}),
        text=_text(r"(?:fixtures|justificantes|\.pdf)"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/persistence/profile/tests/test_secure_bound_namespace_binding\.py$"),
        reason="namespace-binding roundtrip fixture uses a representative justificante PDF filename",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"justificantes/.*\.pdf"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/persistence/profile/tests/test_secure_bound_key_identity_binding\.py$"),
        reason="key-identity binding fixture uses a representative justificante PDF filename",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"justificantes/.*\.pdf"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/modelo/tests/test_reconciliation_record_store\.py$"),
        reason="reconciliation-record roundtrip fixture uses a representative justificante PDF filename",
        pattern_names=frozenset({"calendar quarter token"}),
        text=_text(r"justificantes.*\.pdf"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/inbound/declaracion/tests/test_parser_source_digest_identity\.py$"),
        reason="source-digest identity test reads a real justificante PDF by its official filename",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"justificantes.*\.pdf"),
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/adapters/inbound/declaracion/tests/(?:"
            r"_parser_boundary_support|_verification_chain_support|"
            r"_parser_boundary_m\d+_support|_parser_boundary_m\d+_current_expected|"
            r"test_m303_primitive_anti_tautology|test_parser_boundary_part1|"
            r"test_parser_boundary_part2|test_parser_boundary_part3|test_parser_boundary_m\d+|"
            r"test_parser_boundary_synthetic_models|test_parser_privacy_redaction|"
            r"test_parser_synthetic_fixtures|test_verification_chain_part1|"
            r"test_verification_chain_part2|test_verification_chain_part3|"
            r"test_verification_chain_m\d+(?:_historical)?|test_real_render_extraction_coverage|"
            r"test_extraction_word_order_independence"
            r")\.py$"
        ),
        reason="declaracion parser corpus tests pin external justificante fixture filenames and source labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/inbound/justificante/tests/test_parser\.py$"),
        reason="justificante parser tests preserve external PDF fixture filenames",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m131_current_year\.py$"),
        reason="parser boundary test preserves the committed synthetic justificante filename",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/(?:"
            r"application/calculations/tests/test_prorrata_regularizacion|"
            r"application/modelo/tests/test_prorrata_regularizacion_source_timing|"
            r"application/modelo/tests/test_review_package(?:_collab_audit|_counter_sign|_feedback|_recipient_encryption|_review_only_workspace|_signing)?|"
            r"application/overview/tests/test_data_prep|"
            r"application/modelo/tests/test_filed_observation_storage_context|"
            r"application/modelo/tests/test_import_flow_mutation_guards|"
            r"application/modelo/tests/test_work_lifecycle_bucket_scope|"
            r"entrypoints/cli/tests/test_modelo_review_package_verb"
            r")\.py$"
        ),
        reason="test-only WorkUnit display labels are paired with typed Period values; no period parsing depends on the label",
        pattern_names=frozenset({"year-qualified quarterly token"}),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/filing/tests/test_export_receipt_artifact_binding\.py$"),
        reason="export-receipt binding fixture names a tmp_path output artefact by a representative filename; no period parsing depends on it",
        pattern_names=frozenset({"calendar quarter token"}),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/domain/iva_compensation/tests/test_carry_forward_taxpayer_identity\.py$"),
        reason="test-only expediente_id label is paired with a typed Period value; no period parsing depends on the label",
        pattern_names=frozenset({"year-qualified quarterly token"}),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/entrypoints/cli/tests/test_app_live_filed_rendering\.py$"),
        reason=(
            "IVA history capture result fixture carries opaque observation-path, "
            "artefact-ref, and failed-declaration log-message strings; none is "
            "parsed as a period boundary"
        ),
        pattern_names=frozenset({"year-qualified quarterly token"}),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/inbound/pdf/tests/test_scrub\.py$"),
        reason="inbound parser and scrub tests preserve external justificante/PDF fixture filenames",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/outbound/aeat/sede/tests/_declarations_support\.py$"),
        reason="sede connector tests preserve redacted submitted-file fixture names",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/adapters/outbound/google/tests/test_(?:pull_result_roundtrip|worksheet_export_pull_roundtrip)\.py$"
        ),
        reason="Google export tests preserve external pull labels and worksheet note locators",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/persistence/storage/sql/tests/test_archive_bundle_roundtrip\.py$"),
        reason="archive bundle tests preserve external draft id labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/adapters/persistence/profile/tests/test_justificante_(?:repository|secure_storage_roundtrip)\.py$"
        ),
        reason="justificante persistence tests preserve external justificante PDF fixture filenames and period tokens",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/entrypoints/cli/tests/test_modelo_result_summary_labels\.py$"),
        reason="result-summary label tests pin external work-unit name labels that embed a period token",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/(core|domain)/(?:_period|period)\.py$|^src/cadrumo/(core|domain)/tests/test_period\.py$"
        ),
        reason="Period source and tests explicitly document/refuse the killed combined input forms",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/entrypoints/cli/_common\.py$|^src/cadrumo/entrypoints/cli/tests/test_ledger_period_grammar\.py$"
        ),
        reason="CLI period grammar refusal docs and tests prove calendar/hybrid spellings are rejected",
    ),
    AllowlistRule(
        path=_path(r"^docs/how-to/(filing-calendar|filing-periods|troubleshooting)\.md$"),
        reason="operator docs explicitly say the killed calendar forms are not accepted",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/entrypoints/cli/tests/(test_modelo_registry_surface|test_modelo|test_cold_start_no_profile)\.py$"
        ),
        reason="CLI refusal/regression tests use old combined strings as invalid operator input",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/entrypoints/cli/tests/test_audit_remediation\.py$"),
        reason="CLI audit regression asserts the old combined form is absent from operator text",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/entrypoints/cli/tests/test_repair_privacy_contract\.py$"),
        reason="privacy-redaction tests preserve sensitive old-shape strings to prove they are redacted",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/domain/calculations/registry/tests/test_(?:registry_schema_part2|queries)\.py$"),
        reason="registry schema/query tests use old combined strings as invalid input",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/domain/calculations/registry/_queries\.py$"),
        reason="registry query docs preserve the retired dashed registry-introspection dialect",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/workflow/(?:_models\.py|tests/test_(?:models|declaration_key)\.py)$"),
        reason="workflow key docs/tests prove declaration keys no longer store combined tokens",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/(?:domain/modelos|application/filing)/tests/test_(?:secure_storage_roundtrip|history_repository|repository)\.py$"
        ),
        reason="secure-storage tests assert old combined strings are not persisted in encrypted stores",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/filing/tests/test_import\.py$"),
        reason="filing import refusal tests prove old raw period spellings are rejected",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/modelo/tests/test_work_period_normalization\.py$"),
        reason="modelo work-period normalisation tests prove old inbound strings are refused or canonicalised",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/application/modelo/tests/test_(?:export|history|iva_wallet_engine_integration|iva_wallet_engine_overrides|justificante_reconcile_from_persisted|participation_co_emission|reconcile|reconcile_value_comparison|reconciliation_history|revision_id_d1_contract|simplificado_ledger_bypass)\.py$"
        ),
        reason="modelo workflow tests preserve external work-unit, justificante, and review labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/transactions/tests/test_diagnostics\.py$"),
        reason="diagnostic source-locator tests preserve old user-provided period strings as opaque input",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/application/aggregation/tests/test_(?:aggregation|counterpart|foreign_assets|retenciones|per_modelo_service|service|iva_ledger)\.py$"
        ),
        reason="aggregation tests still carry targeted invalid-input and historical-label examples",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/application/calculations/tests/test_(?:iva_wallet_reconciliation|observations_repository_roundtrip)\.py$"
        ),
        reason="calculation tests preserve operator evidence/source locator labels and redaction assertions",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/calculations/tests/test_cross_period_clean_state(?:_provenance)?\.py$"),
        reason="calculation clean-state tests preserve AEAT expediente source labels, not period inputs",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text("2025" + "-1T"),
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/application/(?:verification/tests/test_verify_helpers|calculations/tests/test_modelo_720_fichero_boe_roundtrip)\.py$"
        ),
        reason="annual legacy-label tests cover non-core external periodo values",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/(?:adapters/outbound/(?:storage|llm)|application/filing)/tests/test_(?:local|cache_roundtrip|export|testing_registry)\.py$"
        ),
        reason="artifact/cache/export tests preserve external filename and object-key labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/application/live/tests/test_(?:"
            r"filed_capture_calculation_history|iva_remote_state_acquisition|"
            r"iva_wallet_capture_backend|justificante_reconcile_from_persisted"
            r")\.py$"
        ),
        reason="live capture tests preserve AEAT expediente, observation, and secure-object labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/application/(?:ledger/tests/_action_test_support|workflow/tests/test_state_persistence_roundtrip)\.py$"
        ),
        reason="workflow and ledger support tests preserve external work-unit/export path labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/calculations/tests/test_carry_gate_parity\.py$"),
        reason="calculation carry-gate tests preserve opaque AEAT expediente source labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/filing/tests/_export_support\.py$"),
        reason="filing export support tests preserve external export path labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/application/live/tests/_(?:filed_capture_history|justificante_reconcile)_support\.py$"
        ),
        reason="live capture support tests preserve external justificante fixture and work-unit labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/modelo/tests/_export_modelo_303_support\.py$"),
        reason="modelo export support tests preserve external justificante and expediente labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/overview/(?:_calendar|tests/test_calendar[a-z_]*)\.py$"),
        reason="overview calendar code/tests preserve pre-existing display-doc and justificante CSV labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/overview/tests/calendar_test_support\.py$"),
        reason="overview calendar support tests preserve external justificante CSV labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/core/(?:observability/tests/test_replay|tests/test_paths)\.py$"),
        reason="core tests preserve historical replay argv and path-token examples",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/domain/calculations/registry/tests/test_(?:corpus_round_trip_gate|provisional_specimen_gate)\.py$"
        ),
        reason="registry corpus gates generate external justificante fixture filenames",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/domain/(?:justificante|modelos|submission)/tests/test_.*\.py$"),
        reason="domain roundtrip tests preserve external justificante, work-unit, and storage labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/entrypoints/cli/tests/test_(?:cli_surface|ledger_corpus_journeys|ledger_persona_yearend_m100|modelo_export_verb|modelo_reconcile_verb|overview_calendar_verb)\.py$"
        ),
        reason="CLI journey tests preserve existing filter-output and external work/evidence labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/entrypoints/cli/tests/test_(?:modelo_projection|overview_calendar_local_evidence)\.py$"
        ),
        reason="CLI tests preserve external projection, justificante, and evidence labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/tests/test_(?:ledger_corpus_fidelity|ledger_modelo_staleness)\.py$"),
        reason="top-level ledger corpus tests preserve external corpus period labels",
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/locales/(?:ca|en|es|hu)\.yml$"),
        reason="pre-existing locale help examples are ratcheted until the locale sweep owns them",
        pattern_names=frozenset({"calendar quarter token"}),
        text=_text("2024" + "Q1"),
    ),
    AllowlistRule(
        path=_path(r"^docs/how-to/(?:quickstart|modelo-390|irpf-lifecycle|iva-lifecycle)\.md$"),
        reason="docs preserve justificante/export filename examples, not period input grammar",
        pattern_names=frozenset({"year-qualified quarterly token"}),
    ),
    AllowlistRule(
        path=_path(r"^docs/_sequences/"),
        reason=(
            "recorded CLI transcripts: the token appears in the opaque work-unit display name, "
            "its text-mode render, and operator-chosen --output filenames. Every command in these "
            "captures passes the canonical split grammar (--year YYYY --period CODE) and every "
            "envelope carries the typed {filing_year, code} period, so no period input depends "
            "on the combined form. Scoped by text to exactly those three generated shapes, NOT "
            "to the whole tree: an unscoped bucket here silently allowed a genuine period INPUT "
            "anywhere under _sequences/, and in doing so defeated every narrower sibling rule "
            "below whose reason claims a token appearing elsewhere in the same capture still "
            "fails. Those claims are only true while this rule carries a text scope."
        ),
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r'"name": "\d+-\d{4}-[1-4]T"' r"|" r"name\\t\d+-\d{4}-[1-4]T" r"|" r"\.boe"),
    ),
    AllowlistRule(
        path=_path(
            r"^docs/_sequences/how-to/(?:"
            r"first-quarterly-filing/modelo-130-first-quarter|"
            r"modelo-130/modelo-130-(?:manual-casilla|quarterly|inspect-boxes|review-chain)|"
            r"modelo-303/modelo-303-(?:first-quarter|inspect-boxes|revision)|"
            r"modelo-349/modelo-349-(?:first-quarter|export|inspect)|"
            r"modelo-390/modelo-390-annual-2025|"
            r"quickstart/quickstart-modelo-130|"
            r"verification-reports/verification-reports-(?:modelo-303|work-history)|"
            r"verification-reports/verification-reports-export-check|"
            r"file-at-aeat/file-at-aeat-chain|"
            r"filing-calendar/filing-calendar-work-status|"
            r"filing-spine/filing-spine-(?:chain|visible-target|work-list)|"
            r"irpf-lifecycle/irpf-lifecycle-q1|"
            r"iva-lifecycle/iva-lifecycle-q1|"
            r"troubleshooting/troubleshooting-period-grammar"
            r")\.json$"
        ),
        reason="captured CLI sequence preserves the WorkUnit.name display-name field "
        "(<modelo>-<year>-<period>, no modelo- stem) as a JSON string or inside a captured "
        "tab-separated CLI text-output blob, not export filename or period input grammar",
        pattern_names=frozenset({"year-qualified quarterly token"}),
    ),
    AllowlistRule(
        path=_path(
            r"^docs/_sequences/how-to/(?:"
            r"quickstart/quickstart-(?:revision|export|file)|"
            r"review-calculation-values/review-values-(?:bindings|manual-casilla|review-saved)"
            r")\.json$"
        ),
        reason="captured CLI sequence's tab-separated modelo.work.create text output embeds "
        "the WorkUnit.name display-name field, not export filename or period input grammar",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"name\\t\d+-\d{4}-[1-4]T"),
    ),
    AllowlistRule(
        path=_path(
            r"^docs/_sequences/how-to/(?:"
            r"filing-spine/filing-spine-(?:discard|file|history|rename|runs|select)|"
            r"first-quarterly-filing/first-quarter-export-file|"
            r"modelo-130/modelo-130-export-file"
            r")\.json$"
        ),
        reason="captured CLI sequence preserves the WorkUnit.name display-name field as a JSON "
        "string; `work create` derives it from _default_name (application/modelo/work_lifecycle.py) "
        "as <modelo>-<year>-<period>, so it is generated output, not period input grammar. Scoped "
        "by text to the name field alone rather than added to the looser sibling bucket above, so a "
        "genuine combined-period token appearing elsewhere in these same captures still fails.",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r'"name": "\d+-\d{4}-[1-4]T"'),
    ),
    AllowlistRule(
        path=_path(
            r"^docs/_sequences/how-to/(?:"
            r"iva-lifecycle/iva-lifecycle-q1|"
            r"quickstart/quickstart-export"
            r")\.json$"
        ),
        reason="captured CLI sequence's modelo.export --output/output_path names the canonical "
        "modelo-<id>-<year>-<period> fichero-BOE export filename schema, not a period input",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"\.boe"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/entrypoints/cli/tests/test_app_quickfile\.py$"),
        reason="quickfile invoice tests use an opaque operator-facing invoice_number display label, not a period input",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"invoice_number="),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/entrypoints/cli/tests/test_app_quickfile\.py$"),
        reason="quickfile export test names its --output path with the canonical "
        "modelo-<id>-<year>-<period> export filename schema, not a period input",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"tmp_path / "),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/entrypoints/cli/tests/test_modelo_(?:kv_format_localization|state_text_labels)\.py$"),
        reason="work-unit fixtures use an opaque display-name label, not a period input",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"name="),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/adapters/inbound/declaracion/tests/test_result_disposition_channel_evidence\.py$"),
        reason="bundled M303 manual-annex facsimile filenames name the AEAT worked example's four quarters",
        pattern_names=frozenset({"year-qualified quarterly token"}),
    ),
    AllowlistRule(
        path=_path(
            r"^src/cadrumo/(?:"
            r"adapters/inbound/financial/providers/tests/test_(?:mapped_tabular_fallback|tabular_projection)|"
            r"core/tests/test_tabular_dialect"
            r")\.py$"
        ),
        reason="bundled bank/ledger/erp tabular-dialect export fixtures carry the captured export's own filename",
        pattern_names=frozenset({"calendar quarter token"}),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/application/live/tests/test_filed_history_discovery\.py$"),
        reason="synthetic response body names a representative filed-declaration artefact filename, not a period input",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"submitted-file"),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/core/tests/test_redaction_recorded_sequence_output\.py$"),
        reason="the redaction arm's admission rule is proven against representative filename specimens, not period input",
        pattern_names=frozenset({"year-qualified quarterly token"}),
    ),
    AllowlistRule(
        path=_path(r"^src/cadrumo/domain/calculations/registry/tests/test_rate_box_unscreened_groups\.py$"),
        reason="descriptive per-revision label paired with a typed filing_year/period kwarg pair; no string parsing",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text(r"authority\.snapshot"),
    ),
)


@dataclass(frozen=True)
class Finding:
    path: str
    line_number: int
    pattern_name: str
    snippet: str

    def format(self) -> str:
        return f"{self.path}:{self.line_number}: {self.pattern_name}: {self.snippet}"


_PER_LINE_KEYWORD = "period"
"""Literal every line-anchored pattern must require, and the per-file screen uses."""


def _is_whole_text_safe(pattern: Pattern[str]) -> bool:
    """Whether scanning *pattern* over a whole file equals scanning line by line.

    True only when the expression can neither anchor to a line boundary nor span
    one: no ``^``/``$`` (which mean string edges without ``re.MULTILINE``, not
    line edges) and nothing that can consume a newline. Anything else keeps the
    per-line path, so a pattern added later is treated as unsafe until its author
    proves otherwise rather than silently taking the faster route.
    """
    source = pattern.pattern
    return not any(token in source for token in ("^", "$", r"\s", r"\S", ".", r"\n"))


def test_repo_has_no_unallowlisted_combined_period_strings() -> None:
    whole_text = tuple((name, pat) for name, pat in COMBINED_PERIOD_PATTERNS if _is_whole_text_safe(pat))
    per_line = tuple((name, pat) for name, pat in COMBINED_PERIOD_PATTERNS if not _is_whole_text_safe(pat))
    assert whole_text, "no pattern qualified for the whole-file scan; the classifier is inert"
    # The per-file screen below only skips a file when it lacks this literal, so
    # every line-anchored pattern must actually require it. A pattern added
    # without it would be silently skipped in most files; this refuses instead.
    assert all(_PER_LINE_KEYWORD in pattern.pattern for _name, pattern in per_line), (
        f"a line-anchored pattern does not require {_PER_LINE_KEYWORD!r}, so the per-file "
        "screen would skip files it must inspect; widen the screen or make the pattern whole-text safe"
    )

    findings: list[Finding] = []
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # A peer can delete a tracked file between the listing and the read.
            continue
        relative_path = path.relative_to(REPOSITORY_ROOT).as_posix()
        lines: list[str] | None = None

        for pattern_name, pattern in whole_text:
            for match in pattern.finditer(text):
                if lines is None:
                    lines = text.splitlines()
                line_number = text.count("\n", 0, match.start()) + 1
                line = lines[line_number - 1]
                if _is_allowlisted(relative_path, pattern_name, line):
                    continue
                findings.append(
                    Finding(
                        path=relative_path,
                        line_number=line_number,
                        pattern_name=pattern_name,
                        snippet=line.strip(),
                    )
                )

        # The line-anchored patterns still need a line at a time, but only for
        # files that mention the keyword at all, and then only for lines that do.
        # The per-line loop over every line of every tracked file was 38s of pure
        # interpreter overhead across 13 million regex calls.
        if per_line and _PER_LINE_KEYWORD in text:
            if lines is None:
                lines = text.splitlines()
            for line_number, line in enumerate(lines, start=1):
                if _PER_LINE_KEYWORD not in line:
                    continue
                for pattern_name, pattern in per_line:
                    for _match in pattern.finditer(line):
                        if _is_allowlisted(relative_path, pattern_name, line):
                            continue
                        findings.append(
                            Finding(
                                path=relative_path,
                                line_number=line_number,
                                pattern_name=pattern_name,
                                snippet=line.strip(),
                            )
                        )

    assert not findings, "Unallowlisted combined period strings:\n" + "\n".join(
        finding.format() for finding in findings
    )


def test_allowlist_still_refuses_a_period_input_in_every_bucket_it_covers() -> None:
    """Prove the allowlist discriminates rather than merely being satisfied.

    A green scan proves nothing on its own: an allowlist rule broad enough to
    cover its bucket wholesale produces exactly the same green while permitting
    the input the gate exists to forbid. That regression is not hypothetical --
    an unscoped ``docs/_sequences/`` bucket did precisely this, and because it
    matched by path alone it also silently defeated every narrower sibling rule
    whose reason claims a token elsewhere in the same capture still fails.

    So the corpus floor and the hostile-input probe below are the load-bearing
    assertions. Sample tokens are built by concatenation because a literal one
    in this module would be flagged by the gate itself.
    """
    corpus = _tracked_text_files()
    assert len(corpus) > 500, (
        f"combined-period gate scanned only {len(corpus)} files; the scan corpus collapsed, "
        "so a green result above would mean 'nothing was checked' rather than 'nothing is wrong'"
    )

    year = "2026"
    quarter = "-1T"
    benign_display_name = f'        "name": "303-{year}{quarter}",'
    benign_export_path = f'        "output_path": "modelo-130-{year}{quarter}.boe",'
    hostile_period_input = f'        "period": "{year}{quarter}",'

    covered_capture = "docs/_sequences/how-to/filing-spine/filing-spine-file.json"
    pattern_name = "year-qualified quarterly token"

    assert _is_allowlisted(covered_capture, pattern_name, benign_display_name), (
        "the generated work-unit display name is the shape these captures legitimately carry; "
        "refusing it would make the gate unusable"
    )
    assert _is_allowlisted(covered_capture, pattern_name, benign_export_path), (
        "the canonical fichero-BOE export filename is operator-chosen output, not period input"
    )
    assert not _is_allowlisted(covered_capture, pattern_name, hostile_period_input), (
        "a combined period INPUT inside a recorded capture must still fail: this is the exact "
        "form the gate kills, and allowing it here is what an unscoped path bucket does"
    )


def _tracked_text_files() -> list[Path]:
    paths: list[Path] = []
    for relative_path in _tracked_repository_paths():
        if not any(relative_path == root or relative_path.startswith(f"{root}/") for root in SCAN_ROOTS):
            continue
        path = REPOSITORY_ROOT / relative_path
        if _should_scan(path):
            paths.append(path)
    return sorted(paths)


def _tracked_repository_paths() -> tuple[str, ...]:
    """Return paths tracked by Git without spawning a shell command."""
    git_dir = _git_dir()
    index_path = git_dir / "index"
    data = index_path.read_bytes()
    if data[:4] != b"DIRC":
        raise AssertionError(f"unexpected git index header in {index_path}")
    version, entry_count = struct.unpack(">II", data[4:12])
    if version not in (2, 3):
        raise AssertionError(f"unsupported git index version {version}; update the period gate reader")

    offset = 12
    paths: list[str] = []
    for _ in range(entry_count):
        entry_start = offset
        flags = struct.unpack(">H", data[offset + 60 : offset + 62])[0]
        offset += 62
        if flags & 0x4000:
            offset += 2
        path_end = data.index(b"\x00", offset)
        tracked_path = data[offset:path_end].decode("utf-8")
        offset = path_end + 1
        while (offset - entry_start) % 8:
            offset += 1
        paths.append(tracked_path)
    return tuple(paths)


def _git_dir() -> Path:
    git_marker = REPOSITORY_ROOT / ".git"
    if git_marker.is_dir():
        return git_marker
    marker_text = git_marker.read_text(encoding="utf-8").strip()
    prefix = "gitdir: "
    if not marker_text.startswith(prefix):
        raise AssertionError(f"unsupported .git marker: {marker_text!r}")
    git_dir = Path(marker_text[len(prefix) :])
    if not git_dir.is_absolute():
        git_dir = (git_marker.parent / git_dir).resolve()
    return git_dir


def _should_scan(path: Path) -> bool:
    if not path.is_file():
        return False
    relative_parts = path.relative_to(REPOSITORY_ROOT).parts
    if any(part in SKIPPED_PARTS for part in relative_parts):
        return False
    return path.suffix.lower() in TEXT_SUFFIXES


def _is_allowlisted(path: str, pattern_name: str, text: str) -> bool:
    return any(rule.matches(path, pattern_name, text) for rule in ALLOWLIST)
