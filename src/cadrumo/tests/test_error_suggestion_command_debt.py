"""Gate: no NEW hardcoded CLI command may enter an error's recovery suggestion.

An error's ``default_suggestion`` is operator-facing recovery guidance, and today
much of it is a literal ``aeat ...`` string baked into the error registry. That
string is untestable: nothing resolves it against the live command surface, so
renaming a verb sweeps the registrations and leaves the suggestion naming a
command that no longer exists. The operator -- frequently an autonomous agent
that will run exactly what it is told -- receives an instruction it cannot
recover from, and no gate notices.

The repaired shape already exists for the notice channel: an ``action_id``
declared in the operator action catalogue, resolved through
:func:`application.operator_actions.next_action`, which fails closed on an
unknown id. Errors have no such channel yet, so the conversion is real work
rather than a rewording, and this gate does not pretend otherwise.

What it does is stop the surface GROWING while that work is done. Every existing
literal is enrolled below as :attr:`SuggestionDebt.UNCONVERTED`; a new one fails
here and its author has to either add the action channel or justify the literal.

**What a green run means, precisely.** Not that these suggestions are correct,
and not that they resolve -- nothing here checks either. Only this: **no error
code has gained or lost a hardcoded-command suggestion since the debt was
measured.** Rows are keyed by ``(module, error code)`` rather than line number,
so ordinary edits do not invalidate them and a stale row fails instead of
lingering.
"""

from __future__ import annotations

import ast
import re
from enum import StrEnum
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ERRORS_ROOT = Path(__file__).resolve().parents[1] / "core" / "errors"

#: Case-SENSITIVE, mirroring ``core.json_contract._RAW_AEAT_COMMAND_PATTERN``:
#: lowercase ``aeat`` is the CLI executable, ``AEAT`` is the tax authority, and
#: only the former is an executable command identity.
_RAW_COMMAND = re.compile(r"(?:^|[\s`'\";|&()])aeat(?=$|[\s`'\";|&()])")


class SuggestionDebt(StrEnum):
    """Why an error suggestion still carries a literal command."""

    #: Enrolled when this gate was written. The suggestion names a command as
    #: prose, resolved by nothing. Not reviewed, not endorsed -- carried debt.
    UNCONVERTED = "unconverted-literal-command"


def _suggestion_command_rows() -> set[tuple[str, str]]:
    """Return ``(module, error code)`` for every literal-command suggestion."""
    rows: set[tuple[str, str]] = set()
    for path in sorted(_ERRORS_ROOT.rglob("*.py")):
        if "/tests/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a broken module fails its own gate
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            suggestion = keywords.get("default_suggestion")
            if not isinstance(suggestion, ast.Constant) or not isinstance(suggestion.value, str):
                continue
            if not _RAW_COMMAND.search(suggestion.value):
                continue
            code = keywords.get("code")
            code_value = code.value if isinstance(code, ast.Constant) and isinstance(code.value, str) else "<unknown>"
            rows.add((path.name, code_value))
    return rows


_UNCONVERTED: frozenset[tuple[str, str]] = frozenset(
    {
        ("_adapters_part1.py", "AUTH_AUTH_CERTIFICATE_LOAD"),
        ("_adapters_part1.py", "AUTH_STORAGE_KEYRING_UNAVAILABLE"),
        ("_adapters_part1.py", "AUTH_STORAGE_MASTER_KEY_KDF_VERSION"),
        ("_adapters_part1.py", "AUTH_STORAGE_MASTER_KEY_UNAVAILABLE"),
        ("_adapters_part1.py", "FAIL_BROWSER_EVASION"),
        ("_adapters_part1.py", "INTEGRITY_STORAGE_SECURE_OBJECT_ROW_IDENTITY"),
        ("_adapters_part1.py", "INTEGRITY_STORAGE_SECURE_OBJECT_UNREADABLE"),
        ("_adapters_part1.py", "REFUSED_STORAGE_SESSION_EXPIRED"),
        ("_adapters_part2.py", "AUTH_GOOGLE_CLIENT_NOT_REGISTERED"),
        ("_adapters_part2.py", "AUTH_GOOGLE_CLIENT_REVOKED"),
        ("_adapters_part2.py", "AUTH_GOOGLE_EXPIRED"),
        ("_adapters_part2.py", "AUTH_GOOGLE_REVOKED"),
        ("_adapters_part2.py", "AUTH_GOOGLE_SCOPE_INSUFFICIENT"),
        ("_adapters_part2.py", "AUTH_OUTBOUND_STORAGE_PERMISSION"),
        ("_adapters_part2.py", "AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION"),
        ("_adapters_part2.py", "ERROR_OUTBOUND_STORAGE_PATH_TOO_LONG"),
        ("_adapters_part2.py", "ERROR_STORAGE_BUCKET_PATH_TOO_LONG"),
        ("_adapters_part2.py", "LOCKED_STORAGE_BUCKET_SESSION"),
        ("_adapters_part2.py", "REFUSED_GOOGLE_PROFILE_UNBOUND"),
        ("_adapters_part2.py", "REFUSED_LLM_BUSY"),
        ("_adapters_part2.py", "REFUSED_LLM_CONTENTION"),
        ("_adapters_part2.py", "REFUSED_OUTBOUND_STORAGE_CONFLICT"),
        ("_adapters_part2.py", "REFUSED_STORAGE_BUCKET_NO_ACTIVE"),
        ("_adapters_part2.py", "REFUSED_STORAGE_MASTER_KEY_NO_ACTIVE_SESSION"),
        ("_application_part1.py", "AUTH_SESSION_CORRUPT"),
        ("_application_part1.py", "AUTH_SESSION_DESERIALIZATION"),
        ("_application_part1.py", "AUTH_SESSION_UNAVAILABLE"),
        ("_application_part1.py", "ERROR_APPLICATION_LIVE"),
        ("_application_part1.py", "ERROR_APPLICATION_LIVE_IVA_SURFACE_TIMEOUT"),
        ("_application_part1.py", "ERROR_CONFIG_RESET_JOURNAL_ALREADY_EXISTS"),
        ("_application_part1.py", "ERROR_CONFIG_RESET_JOURNAL_INCOMPLETE"),
        ("_application_part1.py", "ERROR_CONFIG_RESET_JOURNAL_NOT_FOUND"),
        ("_application_part1.py", "ERROR_CONFIG_RESET_OPERATION_NOT_FOUND"),
        ("_application_part1.py", "ERROR_MODELO_COMPARE_NO_REVISIONS"),
        ("_application_part1.py", "ERROR_MODELO_COMPARE_NO_USABLE_REVISIONS"),
        ("_application_part1.py", "ERROR_MODELO_COMPARE_NO_WORK_UNITS"),
        ("_application_part1.py", "ERROR_MODELO_PROJECTION"),
        ("_application_part1.py", "ERROR_MODELO_PROJECT_NO_M130_REVISIONS"),
        ("_application_part1.py", "ERROR_MODELO_PROJECT_NO_M130_UNITS"),
        ("_application_part1.py", "ERROR_MODELO_WORK_SELECTOR"),
        ("_application_part1.py", "FAIL_REPAIR_DECISION_NOT_FOUND"),
        ("_application_part1.py", "INTEGRITY_REPAIR_INTEGRITY"),
        ("_application_part1.py", "LOCKED_AUTH_ACQUISITION"),
        ("_application_part1.py", "LOCKED_AUTH_CLEANUP_IN_PROGRESS"),
        ("_application_part1.py", "LOCKED_CERTIFICATE_SECRET_MUTATION_IN_PROGRESS"),
        ("_application_part1.py", "LOCKED_CONFIG_RESET_ALREADY_RUNNING"),
        ("_application_part1.py", "REFUSED_APPLICATION_LIVE_INPUT"),
        ("_application_part1.py", "REFUSED_APPLICATION_REGISTRY_INPUT"),
        ("_application_part1.py", "REFUSED_AUTH_CERTIFICATE_SOURCE_NOT_FOUND"),
        ("_application_part1.py", "REFUSED_AUTH_CONFIGURE_DANGLING_ACTIVE_PROFILE"),
        ("_application_part1.py", "REFUSED_AUTH_CONFIGURE_NO_ACTIVE_BUCKET"),
        ("_application_part1.py", "REFUSED_AUTH_DIAGNOSTIC_PAYLOAD"),
        ("_application_part1.py", "REFUSED_AUTH_DIAGNOSTIC_PHONE_STATE"),
        ("_application_part1.py", "REFUSED_AUTH_LOGIN_LIVE_TESTS_DISABLED"),
        ("_application_part1.py", "REFUSED_AUTH_LOGIN_PRECONDITION"),
        ("_application_part1.py", "REFUSED_AUTH_OPERATION_SCOPE_CONFLICT"),
        ("_application_part1.py", "REFUSED_AUTH_PROFILE_IDENTITY_MISMATCH"),
        ("_application_part1.py", "REFUSED_AUTH_PROVIDER_NOT_CONFIGURED"),
        ("_application_part1.py", "REFUSED_AUTH_PROVIDER_RESERVED"),
        ("_application_part1.py", "REFUSED_CLAVE_CREDENTIALS_INCOMPLETE"),
        ("_application_part1.py", "REFUSED_CORPUS_SEARCH_INPUT"),
        ("_application_part1.py", "REFUSED_FINANCIAL_AGGREGATION_CATEGORY_COVERAGE"),
        ("_application_part1.py", "REFUSED_FINANCIAL_AGGREGATION_MISSING_CLASSIFICATION"),
        ("_application_part1.py", "REFUSED_MODELO_100_BORRADOR_BINDING"),
        ("_application_part1.py", "REFUSED_MODELO_COMPARE_NEED_TWO_YEARS"),
        ("_application_part1.py", "REFUSED_MODELO_PROJECT_INVALID_DECIMAL_OVERRIDE"),
        ("_application_part1.py", "REFUSED_OPERATOR_SURFACE_CONTRACT"),
        ("_application_part1.py", "REFUSED_PROFILE_BINDING_RESOLUTION"),
        ("_application_part1.py", "REFUSED_PROFILE_LABEL_AMBIGUOUS"),
        ("_application_part1.py", "REFUSED_RECONCILIATION_CROSS_BUCKET"),
        ("_application_part1.py", "REFUSED_REVIEW_EDIT_PARSE"),
        ("_application_part1.py", "REFUSED_REVIEW_FILTER_PARSE"),
        ("_application_part1.py", "REFUSED_TOPIC_NOT_FOUND"),
        ("_application_part1.py", "REFUSED_WIZARD_EDIT_UNSUPPORTED_CONSOLE"),
        ("_application_part1.py", "REFUSED_WIZARD_MISSING_FLAG"),
        ("_application_part1.py", "REFUSED_WIZARD_STATUS"),
        ("_application_part1.py", "REFUSED_WORKFLOW_RESUME_RUN_AMBIGUOUS"),
        ("_application_part2.py", "ERROR_CALC_SHEETS_ENGINE"),
        ("_application_part2.py", "ERROR_CALC_SHEETS_TRANSLATION"),
        ("_application_part2.py", "ERROR_MODELO_CALCULATION_REVISION_SELECTOR"),
        ("_application_part2.py", "ERROR_MODELO_CALCULATION_REVISION_SELECTOR_NOT_FOUND"),
        ("_application_part2.py", "ERROR_MODELO_REVIEW_PACKAGE"),
        ("_application_part2.py", "ERROR_MODELO_REVIEW_PACKAGE_COUNTER_SIGNING"),
        ("_application_part2.py", "ERROR_MODELO_REVIEW_PACKAGE_FEEDBACK"),
        ("_application_part2.py", "ERROR_MODELO_REVIEW_PACKAGE_SIGNING"),
        ("_application_part2.py", "ERROR_MODELO_WORK_ADDRESS_NOT_FOUND"),
        ("_application_part2.py", "ERROR_MODELO_WORK_SELECTOR_UNIT_NOT_FOUND"),
        ("_application_part2.py", "ERROR_PROFILE_CROSS_STORE_DRIFT"),
        ("_application_part2.py", "ERROR_STORAGE_MANAGEMENT"),
        ("_application_part2.py", "INTEGRITY_STORED_CALCULATION_DRIFT"),
        ("_application_part2.py", "REFUSED_EXPORT_FIELD"),
        ("_application_part2.py", "REFUSED_EXPORT_FORMAT"),
        ("_application_part2.py", "REFUSED_IVA_COMPENSATION_CARRY_FORWARD_POLICY"),
        ("_application_part2.py", "REFUSED_IVA_COMPENSATION_CASILLA_REFERENCE"),
        ("_application_part2.py", "REFUSED_IVA_COMPENSATION_DECIMAL_PARSE"),
        ("_application_part2.py", "REFUSED_IVA_COMPENSATION_MODELO"),
        ("_application_part2.py", "REFUSED_IVA_COMPENSATION_RECONCILIATION_INPUT"),
        ("_application_part2.py", "REFUSED_IVA_COMPENSATION_SEED_CONFLICT"),
        ("_application_part2.py", "REFUSED_IVA_COMPENSATION_YEAR_RANGE"),
        ("_application_part2.py", "REFUSED_IVA_WALLET_RECONCILIATION_INVARIANT"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATE_BINDING_INPUT"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATE_CASILLA_INPUT"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATE_DECIMAL_INPUT"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATE_DETAIL_ROWS"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATE_INPUT"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATE_RELATION_INPUT"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATE_SEMANTIC_ROLE"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATE_SHORTCUT_INPUT"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATE_TEXT_INPUT"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATION_REVISION_SELECTOR_AMBIGUOUS"),
        ("_application_part2.py", "REFUSED_MODELO_CALCULATION_REVISION_SELECTOR_STATE"),
        ("_application_part2.py", "REFUSED_MODELO_EXPORT_CROSS_BUCKET"),
        ("_application_part2.py", "REFUSED_MODELO_EXPORT_EVIDENCE_MISSING"),
        ("_application_part2.py", "REFUSED_MODELO_EXPORT_NO_ACTIVE_BUCKET"),
        ("_application_part2.py", "REFUSED_MODELO_EXPORT_OUTPUT_PATH"),
        ("_application_part2.py", "REFUSED_MODELO_FILING_EVIDENCE_MISSING"),
        ("_application_part2.py", "REFUSED_MODELO_PROFILE_READINESS"),
        ("_application_part2.py", "REFUSED_MODELO_RECIPIENT_ENCRYPTION_KEY_NOT_FOUND"),
        ("_application_part2.py", "REFUSED_MODELO_REQUIRED_BINDINGS_MISSING"),
        ("_application_part2.py", "REFUSED_MODELO_REVIEW_ONLY_WORKSPACE_AUTHORITY"),
        ("_application_part2.py", "REFUSED_MODELO_REVIEW_PACKAGE_FEEDBACK_COUNTERSIGN_INVALID"),
        ("_application_part2.py", "REFUSED_MODELO_REVIEW_PACKAGE_INTEGRITY"),
        ("_application_part2.py", "REFUSED_MODELO_REVIEW_PACKAGE_REVISION_STATE"),
        ("_application_part2.py", "REFUSED_MODELO_REVIEW_PACKAGE_SIGNING_KEY_NOT_FOUND"),
        ("_application_part2.py", "REFUSED_MODELO_REVISION_PICK"),
        ("_application_part2.py", "REFUSED_MODELO_WORK_PERIOD_TOKEN"),
        ("_application_part2.py", "REFUSED_MODELO_WORK_REGISTRY_YEAR_MISMATCH"),
        ("_application_part2.py", "REFUSED_MODELO_WORK_SELECTOR_AMBIGUOUS"),
        ("_application_part2.py", "REFUSED_MODELO_WORK_SELECTOR_CONTRADICTION"),
        ("_application_part2.py", "REFUSED_MODELO_WORK_SELECTOR_NO_ACTIVE_BUCKET"),
        ("_application_part2.py", "REFUSED_MODELO_WORK_SELECTOR_REVISION_CONFLICT"),
        ("_application_part2.py", "REFUSED_PROFILE_ALREADY_REGISTERED"),
        ("_application_part2.py", "REFUSED_PROFILE_LOGIN_THROTTLED"),
        ("_application_part2.py", "REFUSED_PROFILE_REGISTRATION"),
        ("_application_part2.py", "REFUSED_STORAGE_RECLAIM"),
        ("_application_part2.py", "REFUSED_STORAGE_RECLAIM_UNCONFIRMED"),
        ("_application_part2.py", "REFUSED_USER_PROFILE_BUNDLE_SCHEMA_VERSION"),
        ("_application_part2.py", "REFUSED_WORKFLOW_INPUT_MISMATCH"),
        ("_core.py", "INTEGRITY_ACTIVE_PROFILE_POINTER"),
        ("_core.py", "INTEGRITY_STORAGE_CORPUS_MANIFEST"),
        ("_core.py", "INTEGRITY_STORAGE_CORPUS_MANIFEST_DRIFT"),
        ("_core.py", "LOCKED_ACCESS_GATE_LIVE_SUBMIT_FORBIDDEN"),
        ("_core.py", "REFUSED_OUTPUT_FORMAT"),
        ("_domain_part1.py", "ERROR_DEADLINES_MISSING_WINDOWS"),
        ("_domain_part1.py", "ERROR_DEADLINES_SCHEDULE_COMPUTATION"),
        ("_domain_part1.py", "ERROR_DOMAIN_BUCKET_MAINTENANCE"),
        ("_domain_part1.py", "ERROR_FINANCIAL_ATTACHMENTS_ATTACHMENT_NOT_FOUND"),
        ("_domain_part1.py", "ERROR_FINANCIAL_INVOICES_INVOICE_NOT_FOUND"),
        ("_domain_part1.py", "ERROR_FINANCIAL_IVA_CATEGORY_NOT_FOUND"),
        ("_domain_part1.py", "ERROR_FINANCIAL_IVA_RATE_NOT_FOUND"),
        ("_domain_part1.py", "FAIL_ADAPTER_SEALED_ARCHIVE_WRITE"),
        ("_domain_part1.py", "FAIL_CERTIFICADO_CENSAL_PARSE"),
        ("_domain_part1.py", "FAIL_DOMAIN_BUCKET_BROWSE"),
        ("_domain_part1.py", "FAIL_DOMAIN_BUCKET_EVENT_HISTORY_PERSISTENCE"),
        ("_domain_part1.py", "FAIL_DOMAIN_BUCKET_EXPORT"),
        ("_domain_part1.py", "FAIL_FINANCIAL_LEDGER_STORAGE"),
        ("_domain_part1.py", "REFUSED_ADAPTER_SEALED_ARCHIVE_HEADER"),
        ("_domain_part1.py", "REFUSED_ADAPTER_SEALED_ARCHIVE_LAYOUT"),
        ("_domain_part1.py", "REFUSED_ADAPTER_SEALED_ARCHIVE_PAYLOAD"),
        ("_domain_part1.py", "REFUSED_AEAT_RECORD_MULTI_RECIPIENT"),
        ("_domain_part1.py", "REFUSED_APODERADO_INVALID_REPRESENTED_NIF"),
        ("_domain_part1.py", "REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE"),
        ("_domain_part1.py", "REFUSED_APODERADO_NOT_CONFIGURED"),
        ("_domain_part1.py", "REFUSED_APODERADO_UNKNOWN_SCOPE"),
        ("_domain_part1.py", "REFUSED_DOMAIN_BUCKET_ARCHIVE"),
        ("_domain_part1.py", "REFUSED_DOMAIN_BUCKET_DELETE"),
        ("_domain_part1.py", "REFUSED_DOMAIN_BUCKET_IMPORT"),
        ("_domain_part1.py", "REFUSED_DOMAIN_BUCKET_RENAME"),
        ("_domain_part1.py", "REFUSED_DOMAIN_BUCKET_RESTORE"),
        ("_domain_part1.py", "REFUSED_DOMAIN_RETENTION_FLOOR"),
        ("_domain_part1.py", "REFUSED_EVIDENCE_BUNDLE_NOT_FOUND"),
        ("_domain_part1.py", "REFUSED_EVIDENCE_BUNDLE_VERIFICATION"),
        ("_domain_part1.py", "REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET"),
        ("_domain_part1.py", "REFUSED_FINANCIAL_LEDGER_TRANSACTION_ID_PREFIX"),
        ("_domain_part1.py", "REFUSED_FINANCIAL_USAGE_RATIOS_CENSO_MISMATCH"),
        ("_domain_part1.py", "REFUSED_INVENTORY_ACTIVIDAD_CONFLICT"),
        ("_domain_part1.py", "REFUSED_INVENTORY_ACTIVIDAD_NOT_FOUND"),
        ("_domain_part1.py", "REFUSED_INVENTORY_SERVICE_INPUT"),
        ("_domain_part1.py", "REFUSED_LEDGER_CONFIRMATION_BLOCKED"),
        ("_domain_part1.py", "REFUSED_LEDGER_COUNTERPARTY_ESTABLISHMENT_CONFLICT"),
        ("_domain_part1.py", "REFUSED_LEDGER_COUNTERPARTY_ESTABLISHMENT_INPUT"),
        ("_domain_part1.py", "REFUSED_LEDGER_EVIDENCE_INPUT"),
        ("_domain_part1.py", "REFUSED_LEDGER_EVIDENCE_NOT_FOUND"),
        ("_domain_part1.py", "REFUSED_LIVE_BORRADOR_SNAPSHOT_NOT_FOUND"),
        ("_domain_part1.py", "REFUSED_LIVE_DEUDAS_SNAPSHOT_NOT_FOUND"),
        ("_domain_part1.py", "REFUSED_LIVE_EXPEDIENTES_SNAPSHOT_NOT_FOUND"),
        ("_domain_part1.py", "REFUSED_LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NOT_FOUND"),
        ("_domain_part1.py", "REFUSED_LIVE_NOTIFICATIONS_SNAPSHOT_NOT_FOUND"),
        ("_domain_part1.py", "REFUSED_LIVE_PORTAL_NOT_FOUND"),
        ("_domain_part1.py", "REFUSED_LIVE_VERIFY_OBSERVATION_NOT_FOUND"),
        ("_domain_part2.py", "ERROR_MODELO_AGGREGATION_BINDING"),
        ("_domain_part2.py", "ERROR_MODELO_AMENDMENT_EVIDENCE_MISSING"),
        ("_domain_part2.py", "ERROR_MODELO_AMENDMENT_TARGET_STATE"),
        ("_domain_part2.py", "ERROR_MODELO_CALCULATION_REGISTRY_UNAVAILABLE"),
        ("_domain_part2.py", "ERROR_MODELO_CALCULATION_REVISION_NOT_FOUND"),
        ("_domain_part2.py", "ERROR_MODELO_CALCULATION_REVISION_STATE"),
        ("_domain_part2.py", "ERROR_MODELO_CASILLA_PROVENANCE_MISSING"),
        ("_domain_part2.py", "ERROR_MODELO_EXTERNAL_FILING_IMPORT"),
        ("_domain_part2.py", "ERROR_MODELO_FILING_RECORD_NOT_FOUND"),
        ("_domain_part2.py", "ERROR_MODELO_IVA_WALLET_RECONCILIATION_BLOCKED"),
        ("_domain_part2.py", "ERROR_MODELO_IVA_WALLET_SEED"),
        ("_domain_part2.py", "ERROR_MODELO_VERIFICATION_REPORT_NOT_FOUND"),
        ("_domain_part2.py", "ERROR_MODELO_WORK_UNIT_ALREADY_DISCARDED"),
        ("_domain_part2.py", "ERROR_MODELO_WORK_UNIT_MUTATION_REFUSED"),
        ("_domain_part2.py", "ERROR_MODELO_WORK_UNIT_NOT_FOUND"),
        ("_domain_part2.py", "ERROR_PORTALS_UNKNOWN_PORTAL"),
        ("_domain_part2.py", "ERROR_RENTAL_CONTRACT_NOT_FOUND"),
        ("_domain_part2.py", "ERROR_RENTAL_FINCA_NOT_FOUND"),
        ("_domain_part2.py", "REFUSED_MODELO_AMENDMENT_COMPLEMENTARIA_LIABILITY_DECREASE"),
        ("_domain_part2.py", "REFUSED_MODELO_AMENDMENT_KIND_NOT_PERMITTED"),
        ("_domain_part2.py", "REFUSED_MODELO_AMENDMENT_OVERRIDE_CASILLA"),
        ("_domain_part2.py", "REFUSED_MODELO_AMENDMENT_VERIFICATION"),
        ("_domain_part2.py", "REFUSED_MODELO_CHARGE_ACCOUNT_MISSING"),
        ("_domain_part2.py", "REFUSED_MODELO_CROSS_PERIOD_CLEAN_STATE"),
        ("_domain_part2.py", "REFUSED_MODELO_IVA_WALLET_CORRECTION_NO_RECORD"),
        ("_domain_part2.py", "REFUSED_MODELO_IVA_WALLET_CORRECTION_SEALED"),
        ("_domain_part2.py", "REFUSED_MODELO_IVA_WALLET_OVERRIDE_FRESH_WALLET"),
        ("_domain_part2.py", "REFUSED_MODELO_IVA_WALLET_OVERRIDE_SEALED"),
        ("_domain_part2.py", "REFUSED_MODELO_IVA_WALLET_SEED_NEGATIVE_AMOUNT"),
        ("_domain_part2.py", "REFUSED_MODELO_IVA_WALLET_SEED_NO_TAXPAYER"),
        ("_domain_part2.py", "REFUSED_MODELO_LOCAL_OBSERVATION"),
        ("_domain_part2.py", "REFUSED_MODELO_REFUND_ELECTION_NOT_ELIGIBLE"),
        ("_domain_part2.py", "REFUSED_MODELO_WORKFLOW_GATE"),
        ("_domain_part2.py", "REFUSED_MODELO_WORK_UNIT_REVISION_DIVERGENCE"),
        ("_domain_part2.py", "REFUSED_PROFILE_NOT_CONFIGURED"),
        ("_domain_part3.py", "INTEGRITY_STORED_PROFILE_DRIFT"),
        ("_domain_part3.py", "INTEGRITY_STORED_TRANSACTION_DRIFT"),
        ("_domain_part3.py", "REFUSED_MODELO_036_PRIOR_ALTA_REQUIRED"),
        ("_entrypoints.py", "ERROR_CONFIG_BOUNDARY"),
    },
)

_DECLARED: dict[tuple[str, str], SuggestionDebt] = {row: SuggestionDebt.UNCONVERTED for row in _UNCONVERTED}


def test_the_scanner_sees_a_real_corpus() -> None:
    """Anti-vacuity: an empty scan would make every assertion below hold trivially."""
    modules = [p for p in _ERRORS_ROOT.rglob("*.py") if "/tests/" not in p.as_posix()]
    assert len(modules) > 5, f"only {len(modules)} error modules found; the scanner is broken"
    assert _suggestion_command_rows(), (
        "no literal-command suggestions found at all. Either the whole debt was genuinely "
        "converted -- in which case empty the declarations below -- or the detector stopped detecting."
    )


def test_no_new_hardcoded_command_suggestion() -> None:
    """A NEW literal command in an error suggestion must not be added silently.

    This is the assertion that bites. Without it the untestable surface grows
    every time an error is added, and the rot is invisible until an operator
    follows a suggestion naming a verb that was renamed away.
    """
    undeclared = sorted(row for row in _suggestion_command_rows() if row not in _DECLARED)
    assert not undeclared, (
        "error codes whose default_suggestion carries a literal 'aeat ...' command with no "
        "declaration here. Prefer a catalogue action_id resolved through next_action(); if the "
        f"literal is genuinely unavoidable, enrol it and say why: {undeclared}"
    )


def test_no_stale_debt_row() -> None:
    """A converted suggestion must drop its row rather than linger.

    Without this the debt list only grows, and a later reader cannot tell which
    rows are live from which were paid off.
    """
    live = _suggestion_command_rows()
    stale = sorted(row for row in _DECLARED if row not in live)
    assert not stale, (
        f"declared suggestion debt that no longer exists -- delete these rows, the conversion landed: {stale}"
    )


def test_the_pattern_distinguishes_the_executable_from_the_authority() -> None:
    """The detector must not fire on the tax authority's name.

    ``AEAT`` names the Spanish tax authority and is retained wherever that is the
    referent; only the lowercase token is the CLI executable. A case-insensitive
    detector would enrol legitimate prose as command debt and make the whole
    baseline meaningless.
    """
    assert _RAW_COMMAND.search("run 'aeat config profile create' first")
    assert not _RAW_COMMAND.search("No persisted AEAT session found on disk.")
    assert not _RAW_COMMAND.search("AEAT's register holds three filings.")
