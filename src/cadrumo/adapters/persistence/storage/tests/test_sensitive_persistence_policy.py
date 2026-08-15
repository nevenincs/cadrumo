"""Policy tests for sensitive production persistence surfaces.

**What each secure-storage gate actually scans, and therefore what it can
promise about a directory added tomorrow.** The gates are not interchangeable
and the differences are invisible from their names, so a claim like "the new
package is covered" is only checkable against this table.

The distinction that matters is between a gate that DISCOVERS its subject and
one that is TOLD its subject. A whole-tree scanner covers a new directory the
moment the directory exists. An enumerating gate covers it only when somebody
adds the entry -- and until then reports green, which reads identically to
covered.

============================  ==================  =========================
Gate                          Scans by            Covers a new directory
============================  ==================  =========================
``test_production_file_       whole-tree rglob    automatically
write_inventory_is_reviewed``
``test_sensitive_financial_   fixed surface       only once enumerated
surfaces_do_not_bypass_...``  list
``test_every_sensitive_       fixed surface       n/a: it guards the list
surface_resolves_...``        list                itself
``test_llm_subpackage_        one named           no: single-package gate
persists_nothing``            package
per-repository roundtrips     test-side only      no: proves a repository
                                                  works, not that a module
                                                  uses it
============================  ==================  =========================

Two consequences follow, and both have already bitten.

The strictest tier -- :data:`_SENSITIVE_SURFACES` -- is the enumerating kind,
and enumeration fails OPEN in two directions. A surface that never gets added
is simply never scanned; a surface that is added and later MOVES leaves a path
resolving to nothing, and rglob over a nonexistent path yields an empty
sequence rather than raising. Four entries had gone stale exactly that way and
the tier reported green over all four.
:func:`test_every_sensitive_surface_resolves_to_real_production_code` exists
solely to close that second direction; nothing closes the first except adding
the entry in the same change that creates the directory.

A per-repository roundtrip is not a coverage gate at all. It proves that
repository encrypts what it is handed, which says nothing about whether some
other module writes the same data somewhere else. Only the scanning gates
answer that question, and only over the tree they actually walk.
"""

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
    repo_path,
    repo_relative,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SENSITIVE_SURFACES = (
    SRC_CADRUMO / "application" / "review",
    SRC_CADRUMO / "application" / "workflow" / "_persistence.py",
    SRC_CADRUMO / "application" / "auth",
    SRC_CADRUMO / "application" / "setup",
    SRC_CADRUMO / "application" / "filing" / "_history_repository.py",
    # Four entries below were repointed after the non-vacuity assertion above
    # caught them resolving to nothing: `domain/{attachments,justificante,
    # submission}/_repository.py` and `entrypoints/cli/oauth.py` no longer
    # exist, so the strictest tier had silently stopped scanning four surfaces.
    # Each is widened to its owning package rather than guessed at a successor
    # file, because a package cannot cover less than the single module it
    # replaces.
    SRC_CADRUMO / "domain" / "attachments",
    SRC_CADRUMO / "domain" / "invoices",
    SRC_CADRUMO / "domain" / "justificante",
    SRC_CADRUMO / "domain" / "submission",
    SRC_CADRUMO / "domain" / "transactions",
    SRC_CADRUMO / "domain" / "usage_ratios" / "_service.py",
    SRC_CADRUMO / "adapters" / "persistence" / "profile",
    SRC_CADRUMO / "adapters" / "outbound" / "aeat" / "auth",
    SRC_CADRUMO / "adapters" / "outbound" / "aeat" / "sede" / "_observation_store.py",
    SRC_CADRUMO / "adapters" / "outbound" / "google",
    SRC_CADRUMO / "adapters" / "outbound" / "llm",
    # The gated local-inference subpackage. Enumerated in the SAME change
    # that creates it, never later: between creation and enumeration the
    # code handling decrypted invoice bytes is unguarded, and the
    # non-vacuity assertion above would refuse an entry added any earlier.
    SRC_CADRUMO / "llm",
    # Successor of the vanished `entrypoints/cli/oauth.py`: the OAuth credential
    # flow now lives across the `_config/_google*` modules.
    SRC_CADRUMO / "entrypoints" / "cli" / "_config" / "_google.py",
    SRC_CADRUMO / "entrypoints" / "cli" / "_config" / "_google_credential_source_cli.py",
    SRC_CADRUMO / "entrypoints" / "cli" / "_config" / "_google_credential_source_payloads.py",
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
        "src/cadrumo/core/atomic_write.py",
        "atomic_write_best_effort_bytes",
        "tempfile.NamedTemporaryFile",
    ): "shared best-effort-tier atomic-write primitive (no fsync); writes caller-supplied bytes only, no data of its own",
    (
        "src/cadrumo/core/atomic_write.py",
        "atomic_write_stream",
        "tempfile.NamedTemporaryFile",
    ): "shared streaming atomic-write primitive; writes caller-supplied chunks only, no data of its own",
    (
        "src/cadrumo-harness/src/cadrumo_harness/mcp/_telemetry.py",
        "record",
        "self.path.open",
    ): "payload-free local session telemetry; appends per-call trajectory metadata JSON lines, no sensitive/user data",
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
        "src/cadrumo/core/_fsync.py",
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
        "save_events_append",
        "target.open",
    ): "redacted diagnostic event store",
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
        "src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py",
        "_dump_wallet_diagnostic",
        "write_text",
    ): "operator-enabled IVA wallet diagnostic writes redacted structural metadata only",
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
    ): "explicit operator-directed review-package export stages the rendered filing artefact only long "
    "enough to create its checksum archive, in a directory pinned beside output_path "
    "(dir=output_path.parent), never the OS-shared temp directory",
    (
        "src/cadrumo/application/modelo/_review_package.py",
        "build_review_package",
        "write_text",
    ): "explicit operator-directed review-package export stages revision evidence and manifest JSON only "
    "long enough to create its checksum archive, in a directory pinned beside output_path "
    "(dir=output_path.parent), never the OS-shared temp directory",
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


def test_every_sensitive_surface_resolves_to_real_production_code() -> None:
    """Every enumerated surface must cover at least one non-test module.

    The strictest persistence tier is an ENUMERATED tuple, not a tree walk, and
    without this assertion it fails OPEN. ``_iter_python_files`` filters an
    rglob with no existence check and no ``is_dir()``, so a surface path that
    does not exist -- or that exists but has been emptied -- yields the empty
    list, contributes zero violations, and is indistinguishable from a surface
    pointing at clean code. **The instrument cannot otherwise tell you it lost
    a surface.**

    Three real events produce that state, and a relocation campaign produces
    two of them at once: a directory renamed or deleted without updating this
    list; a directory emptied because its modules moved elsewhere, leaving a
    named entry over nothing; and a directory enumerated in advance of being
    created, which iterates nothing while reporting success.

    The assertion is deliberately scoped to all enumerated surfaces rather than
    to any one campaign's: every entry here is load-bearing, and any future
    deletion, rename or relocation touching any of them is silently unguarded
    until this test exists. It names the offending entry so the failure is
    actionable rather than merely red.
    """
    empty = [repo_relative(surface) for surface in _SENSITIVE_SURFACES if not _iter_python_files(surface)]
    assert empty == [], (
        "every entry in _SENSITIVE_SURFACES must resolve to at least one non-test module; "
        f"these resolve to nothing and are therefore unguarded: {empty}. "
        "Either the path was renamed/deleted/emptied and the entry is stale, or the entry "
        "was added before its directory existed. Fix the entry -- do not delete this check."
    )


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


_REVIEW_PACKAGE_STAGING_SITES: tuple[tuple[str, str], ...] = (
    ("src/cadrumo/application/modelo/_review_package.py", "build_review_package"),
    ("src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py", "review_package_build"),
)
"""Every known site that stages review-package plaintext filing evidence in a
``tempfile.TemporaryDirectory`` before zipping/reading it. Each entry is
``(repo-relative file, owning function)``.
"""


def test_review_package_staging_pins_dir_beside_destination() -> None:
    """Review-package plaintext staging must never fall back to the OS-shared temp dir.

    Both known staging call sites build a ``tempfile.TemporaryDirectory`` that
    transiently holds the fichero-BOE draft, the full ``CalculationRevision``
    JSON, and the bundled ``LedgerFilingEvidence`` JSON in plaintext for the
    duration of the archive build. ``sensitive-financial-data-secure-storage-
    only`` forbids that plaintext ever touching a scratch location outside the
    operator's control, so each call MUST pass an explicit ``dir=`` keyword
    pinning the staging directory beside the operator-chosen destination
    (``output_path.parent`` / ``output.parent``). Dropping ``dir=`` reverts to
    ``tempfile.gettempdir()`` -- the exact defect this test pins shut -- and
    this test then fails.
    """
    found: set[tuple[str, str]] = set()
    for relative, owning_function in _REVIEW_PACKAGE_STAGING_SITES:
        path = repo_path(relative)
        tree = ast_for_path(path)
        assert tree is not None, f"{relative} must be parseable"
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _dotted_call_name(node)
            if dotted not in {"tempfile.TemporaryDirectory", "TemporaryDirectory"}:
                continue
            function_name = _function_for_line(path, node.lineno)
            if function_name != owning_function:
                continue
            found.add((relative, owning_function))
            keyword_names = {keyword.arg for keyword in node.keywords}
            assert "dir" in keyword_names, (
                f"{relative}:{node.lineno} ({owning_function}): TemporaryDirectory call must pass "
                "an explicit dir= pinning staging beside the destination, never the OS-shared temp dir"
            )
    assert found == set(_REVIEW_PACKAGE_STAGING_SITES), (
        "expected exactly one TemporaryDirectory call in each known review-package staging "
        f"function; found {sorted(found)} -- a moved/renamed/removed call site means this test "
        "is no longer covering what it claims to cover"
    )
