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
        path=_path(r"^src/aeat/tests/fixtures/"),
        reason="external HTML/PDF corpus and fixture generation material preserves official/source labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/_data/registry/aeat/modelos/"),
        reason="registry parser declarations may mention external fixture filenames in comments",
        pattern_names=frozenset({"year-qualified quarterly token", "calendar quarter token"}),
        text=_text(r"(?:fixtures|justificantes|\.pdf)"),
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/adapters/inbound/declaracion/tests/(?:"
            r"_parser_boundary_support|_verification_chain_support|"
            r"_parser_boundary_m\d+_support|_parser_boundary_m\d+_current_expected|"
            r"test_m303_primitive_anti_tautology|test_parser_boundary_part1|"
            r"test_parser_boundary_part2|test_parser_boundary_part3|test_parser_boundary_m\d+|"
            r"test_parser_boundary_synthetic_models|test_parser_privacy_redaction|"
            r"test_parser_synthetic_fixtures|test_verification_chain_part1|"
            r"test_verification_chain_part2|test_verification_chain_part3|"
            r"test_verification_chain_m\d+(?:_historical)?"
            r")\.py$"
        ),
        reason="declaracion parser corpus tests pin external justificante fixture filenames and source labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/adapters/inbound/justificante/tests/test_parser\.py$"),
        reason="justificante parser tests preserve external PDF fixture filenames",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/adapters/inbound/pdf/tests/test_scrub\.py$"),
        reason="inbound parser and scrub tests preserve external justificante/PDF fixture filenames",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/adapters/outbound/aeat/sede/tests/_declarations_support\.py$"),
        reason="sede connector tests preserve redacted submitted-file fixture names",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/adapters/outbound/google/tests/test_(?:pull_result_roundtrip|worksheet_export_pull_roundtrip)\.py$"
        ),
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
        path=_path(
            r"^src/aeat/entrypoints/cli/_common\.py$|^src/aeat/entrypoints/cli/tests/test_ledger_period_grammar\.py$"
        ),
        reason="CLI period grammar refusal docs and tests prove calendar/hybrid spellings are rejected",
    ),
    AllowlistRule(
        path=_path(r"^docs/how-to/(filing-periods|troubleshooting)\.md$"),
        reason="operator docs explicitly say the killed calendar forms are not accepted",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/entrypoints/cli/tests/(test_modelo_registry_surface|test_modelo|test_cold_start_no_profile)\.py$"
        ),
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
        path=_path(r"^src/aeat/domain/calculations/registry/tests/test_(?:registry_schema_part2|queries)\.py$"),
        reason="registry schema/query tests use old combined strings as invalid input",
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
        path=_path(
            r"^src/aeat/(?:domain/modelos|application/filing)/tests/test_(?:secure_storage_roundtrip|history_repository|repository)\.py$"
        ),
        reason="secure-storage tests assert old combined strings are not persisted in encrypted stores",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/filing/tests/test_import\.py$"),
        reason="filing import refusal tests prove old raw period spellings are rejected",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/modelo/tests/test_work_period_normalization\.py$"),
        reason="modelo work-period normalisation tests prove old inbound strings are refused or canonicalised",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/application/modelo/tests/test_(?:export|history|iva_wallet_engine_integration|iva_wallet_engine_overrides|justificante_reconcile_from_persisted|participation_co_emission|reconcile|reconciliation_history|revision_id_d1_contract|simplificado_ledger_bypass)\.py$"
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
        path=_path(
            r"^src/aeat/application/calculations/tests/test_(?:iva_wallet_reconciliation|observations_repository_roundtrip)\.py$"
        ),
        reason="calculation tests preserve operator evidence/source locator labels and redaction assertions",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/calculations/tests/test_cross_period_clean_state(?:_provenance)?\.py$"),
        reason="calculation clean-state tests preserve AEAT expediente source labels, not period inputs",
        pattern_names=frozenset({"year-qualified quarterly token"}),
        text=_text("2025" + "-1T"),
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/application/(?:verification/tests/test_verify_helpers|calculations/tests/test_modelo_720_fichero_boe_roundtrip)\.py$"
        ),
        reason="annual legacy-label tests cover non-core external periodo values",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/(?:adapters/outbound/(?:storage|llm)|application/filing)/tests/test_(?:local|cache_roundtrip|export|testing_registry)\.py$"
        ),
        reason="artifact/cache/export tests preserve external filename and object-key labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/application/live/tests/test_(?:"
            r"filed_capture_calculation_history|iva_remote_state_acquisition|"
            r"iva_wallet_capture_backend|justificante_reconcile_from_persisted"
            r")\.py$"
        ),
        reason="live capture tests preserve AEAT expediente, observation, and secure-object labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/application/(?:ledger/tests/_action_test_support|workflow/tests/test_state_persistence_roundtrip)\.py$"
        ),
        reason="workflow and ledger support tests preserve external work-unit/export path labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/calculations/tests/test_carry_gate_parity\.py$"),
        reason="calculation carry-gate tests preserve opaque AEAT expediente source labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/filing/tests/_export_support\.py$"),
        reason="filing export support tests preserve external export path labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/application/live/tests/_(?:filed_capture_history|justificante_reconcile)_support\.py$"
        ),
        reason="live capture support tests preserve external justificante fixture and work-unit labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/modelo/tests/_export_modelo_303_support\.py$"),
        reason="modelo export support tests preserve external justificante and expediente labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/overview/(?:_calendar|tests/test_calendar[a-z_]*)\.py$"),
        reason="overview calendar code/tests preserve pre-existing display-doc and justificante CSV labels",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/application/overview/tests/calendar_test_support\.py$"),
        reason="overview calendar support tests preserve external justificante CSV labels",
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
        path=_path(
            r"^src/aeat/domain/calculations/registry/tests/test_(?:corpus_round_trip_gate|provisional_specimen_gate)\.py$"
        ),
        reason="registry corpus gates generate external justificante fixture filenames",
    ),
    AllowlistRule(
        path=_path(r"^src/aeat/domain/(?:justificante|modelos|submission)/tests/test_.*\.py$"),
        reason="domain roundtrip tests preserve external justificante, work-unit, and storage labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/entrypoints/cli/tests/test_(?:cli_surface|ledger_corpus_journeys|ledger_persona_yearend_m100|modelo_export_verb|modelo_reconcile_verb|overview_calendar_verb)\.py$"
        ),
        reason="CLI journey tests preserve existing filter-output and external work/evidence labels",
    ),
    AllowlistRule(
        path=_path(
            r"^src/aeat/entrypoints/cli/tests/test_(?:modelo_projection|overview_calendar_local_evidence)\.py$"
        ),
        reason="CLI tests preserve external projection, justificante, and evidence labels",
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
