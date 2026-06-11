"""Policy tests for sensitive production persistence surfaces."""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path
from typing import override

import pytest

from .....core.external_constants import UTF_8_ENCODING

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_ROOT = Path(__file__).resolve().parents[6]
_SENSITIVE_SURFACES = (
    _ROOT / "src" / "aeat" / "application" / "review",
    _ROOT / "src" / "aeat" / "application" / "workflow" / "_persistence.py",
    _ROOT / "src" / "aeat" / "application" / "auth",
    _ROOT / "src" / "aeat" / "application" / "setup",
    _ROOT / "src" / "aeat" / "application" / "filing" / "_history_repository.py",
    _ROOT / "src" / "aeat" / "application" / "workflow" / "_persistence.py",
    _ROOT / "src" / "aeat" / "domain" / "filing" / "_repository.py",
    _ROOT / "src" / "aeat" / "domain" / "filing" / "_complementaria_repository.py",
    _ROOT / "src" / "aeat" / "domain" / "attachments" / "_repository.py",
    _ROOT / "src" / "aeat" / "domain" / "invoices",
    _ROOT / "src" / "aeat" / "domain" / "justificante" / "_repository.py",
    _ROOT / "src" / "aeat" / "domain" / "submission" / "_repository.py",
    _ROOT / "src" / "aeat" / "domain" / "transactions",
    _ROOT / "src" / "aeat" / "domain" / "usage_ratios" / "_service.py",
    _ROOT / "src" / "aeat" / "adapters" / "persistence" / "profile",
    _ROOT / "src" / "aeat" / "adapters" / "outbound" / "aeat" / "auth",
    _ROOT / "src" / "aeat" / "adapters" / "outbound" / "aeat" / "sede" / "_observation_store.py",
    _ROOT / "src" / "aeat" / "adapters" / "outbound" / "google",
    _ROOT / "src" / "aeat" / "adapters" / "outbound" / "llm",
    _ROOT / "src" / "aeat" / "entrypoints" / "cli" / "oauth.py",
    _ROOT / "src" / "aeat" / "entrypoints" / "cli" / "_ledger.py",
)
_PRODUCTION_ROOT = _ROOT / "src" / "aeat"
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
        "src/aeat/adapters/persistence/storage/_rotation.py",
        "_atomic_write",
        "tempfile.NamedTemporaryFile",
    ): "secure storage rotation writes encrypted envelope payloads only",
    (
        "src/aeat/domain/calculations/registry/_validate_evidence.py",
        "_write_disk_cache",
        "tempfile.NamedTemporaryFile",
    ): "registry corpus PDF-text cache; writes public AEAT manual text only, no user data",
    (
        "src/aeat/domain/calculations/registry/_authority.py",
        "_load_authority",
        "validated_cache_path.write_text",
    ): "registry validation cache marker; writes the literal 'validated' string only",
    (
        "src/aeat/domain/calculations/registry/_loader.py",
        "_load_registry_tree_cached",
        "tempfile.NamedTemporaryFile",
    ): "registry-tree compile cache; writes first-party registry definitions only, no user data",
    (
        "src/aeat/adapters/persistence/storage/blob_store/_blob_store.py",
        "_atomic_write_bytes",
        "tempfile.NamedTemporaryFile",
    ): "blob storage backend writes CORPUS plaintext only; all non-CORPUS blobs are ciphertext",
    (
        "src/aeat/adapters/persistence/storage/blob_store/_materialisation.py",
        "_write_bytes_secure_fd",
        "os.write",
    ): "secure temp materialisation writes through a pre-created private fd",
    (
        "src/aeat/adapters/persistence/storage/blob_store/_materialisation.py",
        "_create_materialised_temp_path",
        "tempfile.mkstemp",
    ): "explicit secret/export materialisation uses private temp files",
    (
        "src/aeat/adapters/persistence/storage/bucket/_sealed_archive_writer.py",
        "write_sealed_archive",
        "tarfile.open",
    ): "sealed bucket archive writer emits encrypted archive payloads",
    (
        "src/aeat/adapters/persistence/storage/envelope/_envelope.py",
        "save_envelope",
        "tempfile.NamedTemporaryFile",
    ): "legacy envelope backend is not allowed from governed sensitive surfaces",
    (
        "src/aeat/adapters/persistence/storage/envelope/_envelope.py",
        "save_encrypted_envelope",
        "tempfile.NamedTemporaryFile",
    ): "legacy encrypted envelope backend is not allowed from governed sensitive surfaces",
    (
        "src/aeat/adapters/persistence/storage/master_key/_master_key_io.py",
        "atomic_write_secure_bytes",
        "os.open",
    ): "master-key backend writes key material with restrictive file modes",
    (
        "src/aeat/adapters/persistence/storage/master_key/_master_key_io.py",
        "atomic_write_secure_bytes",
        "os.write",
    ): "master-key backend writes key material through a private fd",
    (
        "src/aeat/adapters/persistence/storage/master_key/_master_key.py",
        "_write_bytes_secure",
        "os.open",
    ): "master-key backend writes key material with restrictive file modes",
    (
        "src/aeat/adapters/persistence/storage/master_key/_master_key.py",
        "_write_bytes_secure",
        "os.write",
    ): "master-key backend writes key material through a private fd",
    (
        "src/aeat/adapters/persistence/storage/secret_store/_secret_store.py",
        "_write_index",
        "tempfile.NamedTemporaryFile",
    ): "secret-store backend writes encrypted index metadata only",
    (
        "src/aeat/application/auth/_acquisition_lock.py",
        "acquire_auth_acquisition_lock",
        "os.open",
    ): "auth acquisition lock file; non-sensitive lock metadata only",
    (
        "src/aeat/application/filing/_export.py",
        "export_draft",
        "output_path.write_bytes",
    ): "explicit user-directed declaration export",
    (
        "src/aeat/core/corpus_manifest/__init__.py",
        "save_corpus_manifest",
        "tempfile.NamedTemporaryFile",
    ): "non-user corpus manifest generation",
    (
        "src/aeat/core/env_io.py",
        "_atomic_write_text",
        "tempfile.NamedTemporaryFile",
    ): "setup configuration writer; sensitive secret payloads are forbidden by separate tests",
    (
        "src/aeat/core/locks.py",
        "fsync_parent_dir",
        "os.open",
    ): "lock maintenance opens directories, not sensitive data files",
    (
        "src/aeat/core/locks.py",
        "exclusive_file_lock",
        "os.open",
    ): "lock maintenance creates lock files, not sensitive data records",
    (
        "src/aeat/core/observability/_sink.py",
        "_open",
        "self._target.open",
    ): "redacted diagnostic event sink",
    (
        "src/aeat/core/observability/_store.py",
        "save_trace",
        "target.write_text",
    ): "redacted diagnostic trace store",
    (
        "src/aeat/core/observability/_store.py",
        "save_events_append",
        "target.open",
    ): "redacted diagnostic event store",
    (
        "src/aeat/domain/calculations/registry/_parity_tapes.py",
        "save_parity_scenario",
        "path.write_text",
    ): "registry parity tape generation",
    (
        "src/aeat/domain/calculations/registry/_parity_tapes.py",
        "save_parity_tape",
        "path.write_text",
    ): "registry parity tape generation",
    (
        "src/aeat/domain/manuals/_fetch.py",
        "_stream_to_file",
        "destination.open",
    ): "official manual corpus download",
    (
        "src/aeat/domain/manuals/_fetch.py",
        "write_manifest",
        "manifest_path.write_text",
    ): "official manual corpus manifest",
    (
        "src/aeat/application/registry/__init__.py",
        "verify_registry_workbooks",
        "output.write_text",
    ): "registry verification report export through the registry service",
    (
        "src/aeat/locales/manager.py",
        "scaffold",
        "open",
    ): "translation scaffold generation",
    (
        "src/aeat/locales/manager.py",
        "_replace_existing_yaml_leaf",
        "path.write_text",
    ): "locale CLI translation-catalogue update; non-financial YAML message text",
    (
        "src/aeat/locales/manager.py",
        "_append_yaml_leaf",
        "path.write_text",
    ): "locale CLI translation-catalogue append; non-financial YAML message text",
    (
        "src/aeat/locales/manager.py",
        "_remove_existing_yaml_leaf",
        "path.write_text",
    ): "locale CLI translation-catalogue removal; non-financial YAML message text",
    (
        "src/aeat/adapters/persistence/storage/bucket/_lockfile.py",
        "_try_create_lock",
        "os.open",
    ): "per-bucket concurrency lockfile; non-sensitive O_EXCL lock metadata only",
    (
        "src/aeat/adapters/persistence/storage/bucket/_lockfile.py",
        "_write_lockfile_pid",
        "os.write",
    ): "per-bucket concurrency lockfile writes the holding PID, not sensitive data",
    (
        "src/aeat/adapters/persistence/storage/bucket/_manifest_io.py",
        "write_manifest",
        "tmp.write_text",
    ): "bucket directory manifest is plaintext TOML by design; carries no NIF/financial data",
    (
        "src/aeat/core/_bucket_pointer_io.py",
        "write_pointer",
        "tmp.write_text",
    ): "active-profile pointer file is plaintext TOML by design; carries only the bucket id",
    (
        "src/aeat/application/user_profile/_profile_repository.py",
        "_restore_pointer_text",
        "target.write_text",
    ): "restores the active-profile pointer (plaintext TOML, bucket UUID only) during a failed-create rollback",
    (
        "src/aeat/application/user_profile/_orchestration.py",
        "restore_active_profile_pointer",
        "target.write_text",
    ): "restores the active-profile pointer (plaintext TOML, bucket UUID only) when a cold-start create span fails",
    (
        "src/aeat/adapters/outbound/storage/_local.py",
        "put",
        "tmp_path.write_bytes",
    ): "local-filesystem storage adapter writes caller-supplied bytes through atomic temp-then-rename",
    (
        "src/aeat/adapters/outbound/storage/_local.py",
        "put",
        "sidecar_path.write_text",
    ): "local-filesystem storage adapter writes the non-sensitive object-metadata sidecar",
    (
        "src/aeat/adapters/outbound/aeat/sede/_declarations_observations.py",
        "_write_all_fd",
        "os.write",
    ): "declaration-PDF parser bridge writes through a pre-created private fd",
    (
        "src/aeat/adapters/outbound/aeat/sede/_declarations_observations.py",
        "_temporary_sensitive_pdf_path",
        "tempfile.mkstemp",
    ): (
        "short-lived declaration-PDF parser bridge for bbox extraction; private tempfile is unlinked immediately "
        "after parsing"
    ),
    (
        "src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py",
        "_dump_wallet_diagnostic",
        "write_text",
    ): "operator-enabled IVA wallet diagnostic writes redacted structural metadata only",
    (
        "src/aeat/adapters/outbound/fx/_ecb_refresh.py",
        "refresh_bundled_ecb_rates",
        "tmp.write_text",
    ): "ECB refresh utility writes a temporary official reference-rate snapshot before validation",
    (
        "src/aeat/adapters/outbound/fx/_ecb_refresh.py",
        "refresh_bundled_ecb_rates",
        "target.write_text",
    ): "ECB refresh utility writes bundled non-user reference-rate data after parser validation",
    (
        "src/aeat/domain/calculations/registry/_workbook_parity.py",
        "_converted_binary_xls_path",
        "cached_path.write_bytes",
    ): "registry workbook-parity conversion cache; non-user AEAT reference workbook bytes",
    (
        "src/aeat/entrypoints/cli/_config/_profile_bundle.py",
        "config_profile_export",
        "out.write_text",
    ): "explicit operator-directed profile export to a caller-chosen path",
    (
        "src/aeat/application/ledger/_actions_export.py",
        "export_ledger_transactions",
        "command.output_path.write_bytes",
    ): "explicit operator-directed ledger transaction export to a caller-chosen path",
}


def _iter_python_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        candidate
        for candidate in path.rglob("*.py")
        if not (candidate.name.startswith("test_") or candidate.name.startswith("_test_") or "tests" in candidate.parts)
    )


def _iter_production_python_files() -> list[Path]:
    return sorted(
        candidate
        for candidate in _PRODUCTION_ROOT.rglob("*.py")
        if not (candidate.name.startswith("test_") or candidate.name.startswith("_test_") or "tests" in candidate.parts)
    )


def _call_name(node: ast.Call) -> str | None:
    target = node.func
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return None


def _dotted_call_name(node: ast.Call) -> str | None:
    target = node.func
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    if not parts:
        return _call_name(node)
    return ".".join(reversed(parts))


def _is_write_mode_arg(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return any(marker in node.value for marker in ("w", "a", "x", "+"))
    return False


def _calls_file_open_for_write(node: ast.Call) -> bool:
    name = _call_name(node)
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
        name = _call_name(node)
        if (
            name in {"write_text", "write_bytes", "NamedTemporaryFile", "mkstemp"}
            or _calls_file_open_for_write(node)
            or dotted in {"os.open", "os.write"}
        ):
            self.calls.append(
                (
                    self.path.relative_to(_ROOT).as_posix(),
                    self.function_stack[-1] if self.function_stack else "<module>",
                    dotted or name or "<unknown>",
                ),
            )
        self.generic_visit(node)


@cache
def _function_spans(path: Path) -> tuple[tuple[int, int, str], ...]:
    tree = ast.parse(path.read_text(encoding=UTF_8_ENCODING), filename=str(path))
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
    text = path.read_text(encoding=UTF_8_ENCODING)
    relative = path.relative_to(_ROOT).as_posix()
    violations = [f"{relative}: contains {token!r}" for token in _FORBIDDEN_TEXT if token in text]
    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            violations.extend(_sensitive_call_violations(node, path=path, relative=relative))
    return violations


def _sensitive_call_violations(node: ast.Call, *, path: Path, relative: str) -> list[str]:
    """Return forbidden-call offences for one AST Call node, honouring the allowlist."""
    name = _call_name(node)
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
        tree = ast.parse(path.read_text(encoding=UTF_8_ENCODING), filename=str(path))
        visitor = _FileWriteVisitor(path)
        visitor.visit(tree)
        observed.update(visitor.calls)

    expected = set(_REVIEWED_PRODUCTION_FILE_WRITES)
    assert observed == expected
