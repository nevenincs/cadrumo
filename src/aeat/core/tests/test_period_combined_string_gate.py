"""Repo-wide regression gate for killed combined period strings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from re import Pattern

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCAN_ROOTS = ("src/aeat", "docs")
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
        path=_path(r"^src/aeat/_data/registry/aeat/modelos/"),
        reason="registry modelo TOML remains a free-form authoring input hydrated at the loader boundary",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/tests/fixtures/"),
        reason="external HTML/PDF corpus and fixture generation material preserves official/source labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/adapters/inbound/declaracion/tests/"),
        reason="declaracion parser corpus tests pin external justificante fixture filenames and source labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/adapters/inbound/(?:justificante|pdf)/tests/"),
        reason="inbound parser and scrub tests preserve external justificante/PDF fixture filenames",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/adapters/outbound/aeat/sede/tests/_declarations_support\.py$"),
        reason="sede connector tests preserve redacted submitted-file fixture names",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/adapters/outbound/google/tests/test_(?:pull_result_roundtrip|worksheet_export_pull_roundtrip)\.py$"),
        reason="Google export tests preserve external pull labels and worksheet note locators",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/adapters/persistence/storage/sql/tests/test_archive_bundle_roundtrip\.py$"),
        reason="archive bundle tests preserve external draft id labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/(core|domain)/(?:_period|period)\.py$|^src/aeat/(core|domain)/tests/test_period\.py$"),
        reason="Period source and tests explicitly document/refuse the killed combined input forms",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/entrypoints/cli/_common\.py$|^src/aeat/entrypoints/cli/tests/test_ledger_period_grammar\.py$"),
        reason="CLI period grammar refusal docs and tests prove calendar/hybrid spellings are rejected",
    ),
    AllowlistRule(
        path=_path(r"^docs/how-to/(filing-periods|troubleshooting)\.md$"),
        reason="operator docs explicitly say the killed calendar forms are not accepted",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/entrypoints/cli/tests/(test_modelo_registry_surface|test_modelo|test_cold_start_no_profile)\.py$"),
        reason="CLI refusal/regression tests use old combined strings as invalid operator input",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/entrypoints/cli/tests/test_audit_remediation\.py$"),
        reason="CLI audit regression asserts the old combined form is absent from operator text",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/entrypoints/cli/tests/test_repair_privacy_contract\.py$"),
        reason="privacy-redaction tests preserve sensitive old-shape strings to prove they are redacted",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/domain/calculations/registry/(?:_schema\.py|tests/test_(?:registry_schema_part2|queries)\.py)$"),
        reason="registry loader boundary docs/tests cover legacy free-form authored period inputs",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/domain/calculations/registry/_queries\.py$"),
        reason="registry query docs preserve the retired dashed registry-introspection dialect",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/workflow/(?:_models\.py|tests/test_(?:models|declaration_key)\.py)$"),
        reason="workflow key docs/tests prove declaration keys no longer store combined tokens",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/(?:domain/modelos|application/filing)/tests/test_(?:secure_storage_roundtrip|history_repository|repository)\.py$"),
        reason="secure-storage tests assert old combined strings are not persisted in encrypted stores",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/filing/tests/test_import\.py$"),
        reason="filing import refusal tests prove old raw period spellings are rejected",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/filing/reconciliation/tests/test_reconcile\.py$"),
        reason="filing reconciliation tests preserve justificante labels supplied by external evidence",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/modelo/tests/test_work_period_normalization\.py$"),
        reason="modelo work-period normalisation tests prove old inbound strings are refused or canonicalised",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/application/modelo/tests/test_(?:export|history|iva_wallet_engine_integration|justificante_reconcile_from_persisted|participation_co_emission|reconcile|reconciliation_history|revision_id_d1_contract|simplificado_ledger_bypass)\.py$"
        ),
        reason="modelo workflow tests preserve external work-unit, justificante, and review labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/transactions/tests/test_diagnostics\.py$"),
        reason="diagnostic source-locator tests preserve old user-provided period strings as opaque input",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/application/aggregation/tests/test_(?:aggregation|counterpart|foreign_assets|retenciones|per_modelo_service|service|iva_ledger)\.py$"
        ),
        reason="aggregation tests still carry targeted invalid-input and historical-label examples",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/calculations/tests/test_(?:iva_wallet_reconciliation|observations_repository_roundtrip)\.py$"),
        reason="calculation tests preserve operator evidence/source locator labels and redaction assertions",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/(?:verification/tests/test_verify_helpers|calculations/tests/test_modelo_720_fichero_boe_roundtrip)\.py$"),
        reason="annual legacy-label tests cover non-core external periodo values",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/(?:adapters/outbound/(?:storage|llm)|application/filing)/tests/test_(?:local|cache_roundtrip|export|testing_registry)\.py$"),
        reason="artifact/cache/export tests preserve external filename and object-key labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/live/tests/"),
        reason="live capture tests preserve AEAT expediente, observation, and secure-object labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/(?:ledger/tests/_action_test_support|workflow/tests/test_state_persistence_roundtrip)\.py$"),
        reason="workflow and ledger support tests preserve external work-unit/export path labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/overview/(?:_calendar|tests/test_calendar)\.py$"),
        reason="overview calendar code/tests preserve pre-existing display-doc and justificante CSV labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/verification/_verify\.py$"),
        reason="verification helper docs explicitly refuse combined calendar input",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/core/(?:observability/tests/test_replay|tests/test_paths)\.py$"),
        reason="core tests preserve historical replay argv and path-token examples",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/domain/calculations/registry/tests/test_(?:corpus_round_trip_gate|provisional_specimen_gate)\.py$"),
        reason="registry corpus gates generate external justificante fixture filenames",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/domain/(?:justificante|modelos|submission)/tests/test_.*\.py$"),
        reason="domain roundtrip tests preserve external justificante, work-unit, and storage labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/entrypoints/cli/tests/test_(?:cli_surface|ledger_corpus_journeys|ledger_persona_yearend_m100|modelo_reconcile_verb|overview_calendar_verb)\.py$"),
        reason="CLI journey tests preserve existing filter-output and external work/evidence labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/tests/test_(?:ledger_corpus_fidelity|ledger_modelo_staleness)\.py$"),
        reason="top-level ledger corpus tests preserve external corpus period labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/locales/(?:ca|en|es|hu)\.yml$"),
        reason="pre-existing locale help examples are ratcheted until the locale sweep owns them",
        pattern_names=frozenset({"calendar quarter token"}),
        text=_text("2024" + "Q1"),
    ),
    AllowlistRule(
        path=_path(r"^docs/how-to/(?:quickstart|modelo-390)\.md$"),
        reason="docs preserve justificante/export filename examples, not period input grammar",
        pattern_names=frozenset({"year-qualified quarterly token"}),
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


def test_repo_has_no_unallowlisted_combined_period_strings() -> None:
    findings: list[Finding] = []
    for path in _tracked_text_files():
        relative_path = path.relative_to(REPOSITORY_ROOT).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for pattern_name, pattern in COMBINED_PERIOD_PATTERNS:
                for match in pattern.finditer(line):
                    text = match.group(0)
                    if _is_allowlisted(relative_path, pattern_name, text):
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


def _tracked_text_files() -> list[Path]:
    paths: list[Path] = []
    for root in SCAN_ROOTS:
        paths.extend(path for path in (REPOSITORY_ROOT / root).rglob("*") if _should_scan(path))
    return sorted(paths)


def _should_scan(path: Path) -> bool:
    if not path.is_file():
        return False
    relative_parts = path.relative_to(REPOSITORY_ROOT).parts
    if any(part in SKIPPED_PARTS for part in relative_parts):
        return False
    return path.suffix.lower() in TEXT_SUFFIXES


def _is_allowlisted(path: str, pattern_name: str, text: str) -> bool:
    return any(rule.matches(path, pattern_name, text) for rule in ALLOWLIST)
