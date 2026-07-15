"""Policy tests for sensitive production persistence surfaces."""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path
from typing import override

import pytest

from .....tests import (
    SRC_CADRUMO,
    ast_for_path,
    leaf_name,
    non_test_package_python_files,
    non_test_python_files_under,
    repo_relative,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SENSITIVE_SURFACES = (
    SRC_CADRUMO / "application" / "review",
    SRC_CADRUMO / "application" / "workflow" / "_persistence.py",
    SRC_CADRUMO / "application" / "auth",
    SRC_CADRUMO / "application" / "setup",
    SRC_CADRUMO / "application" / "filing" / "_history_repository.py",
    SRC_CADRUMO / "domain" / "attachments" / "_repository.py",
    SRC_CADRUMO / "domain" / "invoices",
    SRC_CADRUMO / "domain" / "justificante" / "_repository.py",
    SRC_CADRUMO / "domain" / "submission" / "_repository.py",
    SRC_CADRUMO / "domain" / "transactions",
    SRC_CADRUMO / "domain" / "usage_ratios" / "_service.py",
    SRC_CADRUMO / "adapters" / "persistence" / "profile",
    SRC_CADRUMO / "adapters" / "outbound" / "aeat" / "auth",
    SRC_CADRUMO / "adapters" / "outbound" / "aeat" / "sede" / "_observation_store.py",
    SRC_CADRUMO / "adapters" / "outbound" / "google",
    SRC_CADRUMO / "adapters" / "outbound" / "llm",
    SRC_CADRUMO / "entrypoints" / "cli" / "oauth.py",
    SRC_CADRUMO / "entrypoints" / "cli" / "_ledger.py",
)
_FORBIDDEN_CALLS = {
    "write_text",
    "write_bytes",
    "save_envelope",
    "save_encrypted_envelope",
    "load_encrypted_envelope",
    "NamedTemporaryFile",
    "mkstemp",
}
_FORBIDDEN_TEXT = (
    ".envelope.json",
    ".meta.json",
    "NamedTemporaryFile",
)
_SENSITIVE_DIRECT_WRITE_EXCEPTIONS: dict[tuple[str, str, str], str] = {}
_REVIEWED_PRODUCTION_FILE_WRITES = {
    (
        "src/cadrumo/core/atomic_write.py",
        "atomic_write_bytes",
        "tempfile.NamedTemporaryFile",
    ): "shared standard-tier atomic-write primitive; writes caller-supplied bytes only, no data of its own",
    (
        "src/cadrumo/core/atomic_write.py",
        "atomic_write_hardened_bytes",
        "os.open",
    ): "shared hardened-tier atomic-write primitive; mirrors the master-key O_EXCL/0o600 pattern",
    (
        "src/cadrumo/core/atomic_write.py",
        "_write_all",
        "os.write",
    ): "shared complete-write primitive for the hardened atomic writer's private fd",
    (
        "src/cadrumo/adapters/persistence/storage/bucket/_output_language_hint.py",
        "_atomic_write_text",
        "open",
    ): "output-language UI preference hint; writes a normalized language-code string, no user financial data",
    (
        "src/cadrumo/entrypoints/mcp/_telemetry.py",
        "record",
        "self.path.open",
    ): "payload-free local session telemetry; appends per-call trajectory metadata JSON lines, no sensitive/user data",
    (
        "src/cadrumo/application/corpus_search/_embed_build.py",
        "embed_corpus",
        "chunk_ids_path.write_text",
    ): "corpus-search embedding index build; writes public corpus chunk-id metadata, no user data",
    (
        "src/cadrumo/agent/eval/_flywheel.py",
        "write_promoted_scenario",
        "path.write_text",
    ): "agent-harness eval flywheel; writes promoted eval scenario definitions, no sensitive/user data",
    (
        "src/cadrumo/domain/calculations/registry/_validate_evidence.py",
        "_write_disk_cache",
        "tempfile.NamedTemporaryFile",
    ): "registry corpus PDF-text cache; writes public AEAT manual text only, no user data",
    (
        "src/cadrumo/domain/calculations/registry/_loader.py",
        "_load_registry_tree_cached",
        "tempfile.NamedTemporaryFile",
    ): "registry-tree compile cache; writes first-party registry definitions only, no user data",
    (
        "src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py",
        "_write_bytes_secure_fd",
        "os.write",
    ): "secure temp materialisation writes through a pre-created private fd",
    (
        "src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py",
        "_create_materialised_temp_path",
        "tempfile.mkstemp",
    ): "explicit secret/export materialisation uses private temp files",
    (
        "src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_writer.py",
        "write_sealed_archive",
        "tarfile.open",
    ): "sealed bucket archive writer emits encrypted archive payloads",
    (
        "src/cadrumo/application/auth/_acquisition_lock.py",
        "acquire_auth_acquisition_lock",
        "os.open",
    ): "auth acquisition lock file; non-sensitive lock metadata only",
    (
        "src/cadrumo/application/filing/_export.py",
        "export_draft",
        "output_path.write_bytes",
    ): "explicit user-directed declaration export",
    (
        "src/cadrumo/core/locks.py",
        "fsync_parent_dir",
        "os.open",
    ): "lock maintenance opens directories, not sensitive data files",
    (
        "src/cadrumo/core/locks.py",
        "exclusive_file_lock",
        "os.open",
    ): "lock maintenance creates lock files, not sensitive data records",
    (
        "src/cadrumo/core/observability/_sink.py",
        "_open",
        "self._target.open",
    ): "redacted diagnostic event sink",
    (
        "src/cadrumo/core/observability/_store.py",
        "save_trace",
        "target.write_text",
    ): "redacted diagnostic trace store",
    (
        "src/cadrumo/core/observability/_store.py",
        "save_events_append",
        "target.open",
    ): "redacted diagnostic event store",
    (
        "src/cadrumo/domain/calculations/registry/_parity_tapes.py",
        "save_parity_scenario",
        "path.write_text",
    ): "registry parity tape generation",
    (
        "src/cadrumo/domain/calculations/registry/_parity_tapes.py",
        "save_parity_tape",
        "path.write_text",
    ): "registry parity tape generation",
    (
        "src/cadrumo/domain/manuals/_fetch.py",
        "_stream_to_file",
        "destination.open",
    ): "official manual corpus download",
    (
        "src/cadrumo/domain/manuals/_fetch.py",
        "write_manifest",
        "manifest_path.write_text",
    ): "official manual corpus manifest",
    (
        "src/cadrumo/application/registry/__init__.py",
        "verify_registry_workbooks",
        "output.write_text",
    ): "registry verification report export through the registry service",
    (
        "src/cadrumo/locales/_modelo_manager.py",
        "_write_translation_path",
        "path.write_text",
    ): "modelo locale translation writer updates non-financial registry-localised text",
    (
        "src/cadrumo/locales/manager.py",
        "scaffold",
        "open",
    ): "translation scaffold generation",
    (
        "src/cadrumo/locales/manager.py",
        "_replace_existing_yaml_leaf",
        "path.write_text",
    ): "locale CLI translation-catalogue update; non-financial YAML message text",
    (
        "src/cadrumo/locales/manager.py",
        "_append_yaml_leaf",
        "path.write_text",
    ): "locale CLI translation-catalogue append; non-financial YAML message text",
    (
        "src/cadrumo/locales/manager.py",
        "_remove_existing_yaml_leaf",
        "path.write_text",
    ): "locale CLI translation-catalogue removal; non-financial YAML message text",
    (
        "src/cadrumo/adapters/persistence/storage/bucket/_lockfile.py",
        "_try_create_lock",
        "os.open",
    ): "per-bucket concurrency lockfile; non-sensitive O_EXCL lock metadata only",
    (
        "src/cadrumo/adapters/persistence/storage/bucket/_lockfile.py",
        "_write_lockfile_pid",
        "os.write",
    ): "per-bucket concurrency lockfile writes the holding PID, not sensitive data",
    (
        "src/cadrumo/application/user_profile/_profile_repository.py",
        "_restore_pointer_text",
        "target.write_text",
    ): "restores the active-profile pointer (plaintext TOML, bucket UUID only) during a failed-create rollback",
    (
        "src/cadrumo/application/user_profile/_orchestration.py",
        "restore_active_profile_pointer",
        "target.write_text",
    ): "restores the active-profile pointer (plaintext TOML, bucket UUID only) when a cold-start create span fails",
    (
        "src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py",
        "_dump_wallet_diagnostic",
        "write_text",
    ): "operator-enabled IVA wallet diagnostic writes redacted structural metadata only",
    (
        "src/cadrumo/adapters/outbound/fx/_ecb_refresh.py",
        "refresh_bundled_ecb_rates",
        "tmp.write_text",
    ): "ECB refresh utility writes a temporary official reference-rate snapshot before validation",
    (
        "src/cadrumo/adapters/outbound/fx/_ecb_refresh.py",
        "refresh_bundled_ecb_rates",
        "target.write_text",
    ): "ECB refresh utility writes bundled non-user reference-rate data after parser validation",
    (
        "src/cadrumo/domain/calculations/registry/_workbook_parity.py",
        "_converted_binary_xls_path",
        "cached_path.write_bytes",
    ): "registry workbook-parity conversion cache; non-user AEAT reference workbook bytes",
    (
        "src/cadrumo/entrypoints/cli/_config/_profile_bundle.py",
        "config_profile_export",
        "out.write_text",
    ): "explicit operator-directed profile export to a caller-chosen path",
    (
        "src/cadrumo/entrypoints/cli/_config/_profile_bundle.py",
        "config_profile_subject_access_request",
        "out.write_text",
    ): "explicit operator-directed GDPR right-of-access export to a caller-chosen path",
    (
        "src/cadrumo/application/ledger/_actions_export.py",
        "export_ledger_transactions",
        "command.output_path.write_bytes",
    ): "explicit operator-directed ledger transaction export to a caller-chosen path",
    (
        "src/cadrumo/core/observability/_store.py",
        "save_envelope",
        "target.write_text",
    ): "determinism-replay golden-capture surface persists already-CLI-redacted envelope documents only",
    (
        "src/cadrumo/agent/_workspace.py",
        "_write",
        "write_text",
    ): "agent-harness workspace materialiser writes shipped static rules/personas/skills markdown only, no user data",
    (
        "src/cadrumo/agent/_workspace.py",
        "_write_json",
        "write_text",
    ): "agent-harness workspace materialiser writes shipped static JSON manifests only, no user data",
    (
        "src/cadrumo/application/modelo/_review_package.py",
        "build_review_package",
        "write_bytes",
    ): "explicit operator-directed review-package export stages the rendered filing artefact only long enough to create its checksum archive",
    (
        "src/cadrumo/application/modelo/_review_package.py",
        "build_review_package",
        "write_text",
    ): "explicit operator-directed review-package export stages revision evidence and manifest JSON only long enough to create its checksum archive",
    (
        "src/cadrumo/core/corpus_manifest/_bundle_signing.py",
        "generate_corpus_signing_keypair",
        "resolved.write_text",
    ): "maintainer-directed corpus signing-key export writes a private keypair before applying restrictive file permissions",
    (
        "src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py",
        "review_package_sign",
        "output.write_text",
    ): "explicit operator-directed signature-envelope export to a caller-chosen path; "
    "public key only, no secret material",
    (
        "src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py",
        "review_package_counter_sign",
        "output.write_text",
    ): "explicit operator-directed counter-sign receipt export to a caller-chosen path; "
    "public key only, no secret material",
    (
        "src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py",
        "review_package_encrypt_for_recipient",
        "output.write_text",
    ): "explicit operator-directed recipient-encrypted envelope export to a caller-chosen path; AEAD ciphertext only, "
        "never the plaintext review package",
    (
        "src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py",
        "review_package_encrypt_feedback",
        "output.write_text",
    ): "explicit operator-directed feedback export writes an originator-encrypted envelope only, never the plaintext feedback",
    (
        "src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py",
        "review_package_decrypt",
        "output.write_bytes",
    ): "explicit operator-directed recovered review-package export to a caller-chosen path, mirroring the existing "
    "review-package build/export write pattern",
}


def _iter_python_files(path: Path) -> list[Path]:
    return list(non_test_python_files_under(path, include_data=True))


def _iter_production_python_files() -> list[Path]:
    return list(non_test_package_python_files(include_data=True))


def _dotted_call_name(node: ast.Call) -> str | None:
    target = node.func
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    if not parts:
        return leaf_name(node.func) or None
    return ".".join(reversed(parts))


def _is_write_mode_arg(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return any(marker in node.value for marker in ("w", "a", "x", "+"))
    return False


def _calls_file_open_for_write(node: ast.Call) -> bool:
    name = leaf_name(node.func)
    if name not in {"open"}:
        return False
    mode_arg: ast.AST | None = None
    if len(node.args) >= 2:
        mode_arg = node.args[1]
    elif len(node.args) == 1 and isinstance(node.func, ast.Attribute):
        mode_arg = node.args[0]
    for keyword in node.keywords:
        if keyword.arg == "mode":
            mode_arg = keyword.value
            break
    return _is_write_mode_arg(mode_arg)


class _FileWriteVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.function_stack: list[str] = []
        self.calls: list[tuple[str, str, str]] = []

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    @override
    def visit_Call(self, node: ast.Call) -> None:
        dotted = _dotted_call_name(node)
        name = leaf_name(node.func)
        if (
            name in {"write_text", "write_bytes", "NamedTemporaryFile", "mkstemp"}
            or _calls_file_open_for_write(node)
            or dotted in {"os.open", "os.write"}
        ):
            self.calls.append(
                (
                    repo_relative(self.path),
                    self.function_stack[-1] if self.function_stack else "<module>",
                    dotted or name or "<unknown>",
                ),
            )
        self.generic_visit(node)


@cache
def _function_spans(path: Path) -> tuple[tuple[int, int, str], ...]:
    tree = ast_for_path(path)
    assert tree is not None, f"{repo_relative(path)} must be parseable"
    spans: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        end_lineno = getattr(node, "end_lineno", node.lineno)
        spans.append((node.lineno, end_lineno, node.name))
    return tuple(spans)


def _function_for_line(path: Path, line_number: int) -> str:
    best_name = "<module>"
    best_line = -1
    for start, end, name in _function_spans(path):
        if start <= line_number <= end and start > best_line:
            best_name = name
            best_line = start
    return best_name


def test_sensitive_financial_surfaces_do_not_bypass_secure_object_backend() -> None:
    """Financial/tax state must not write plaintext or file-envelope payloads directly."""

    violations: list[str] = []
    for surface in _SENSITIVE_SURFACES:
        for path in _iter_python_files(surface):
            violations.extend(_sensitive_surface_violations(path))
    assert violations == []


def _sensitive_surface_violations(path: Path) -> list[str]:
    """Return every forbidden-text + forbidden-call offence in one source file."""
    text = path.read_text(encoding="utf-8")
    relative = repo_relative(path)
    violations = [f"{relative}: contains {token!r}" for token in _FORBIDDEN_TEXT if token in text]
    tree = ast_for_path(path)
    assert tree is not None, f"{relative} must be parseable"
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            violations.extend(_sensitive_call_violations(node, path=path, relative=relative))
    return violations


def _sensitive_call_violations(node: ast.Call, *, path: Path, relative: str) -> list[str]:
    """Return forbidden-call offences for one AST Call node, honouring the allowlist."""
    name = leaf_name(node.func)
    key = (relative, _function_for_line(path, node.lineno), _dotted_call_name(node) or name or "<unknown>")
    if key in _SENSITIVE_DIRECT_WRITE_EXCEPTIONS:
        return []
    offences: list[str] = []
    if name in _FORBIDDEN_CALLS:
        offences.append(f"{relative}:{node.lineno}: calls {name}()")
    if _calls_file_open_for_write(node):
        offences.append(f"{relative}:{node.lineno}: opens a file in write/append mode")
    return offences


def test_production_file_write_inventory_is_reviewed() -> None:
    """Any new production file writer must be classified before merge."""

    observed: set[tuple[str, str, str]] = set()
    for path in _iter_production_python_files():
        tree = ast_for_path(path)
        assert tree is not None, f"{repo_relative(path)} must be parseable"
        visitor = _FileWriteVisitor(path)
        visitor.visit(tree)
        observed.update(visitor.calls)

    expected = set(_REVIEWED_PRODUCTION_FILE_WRITES)
    assert observed == expected
