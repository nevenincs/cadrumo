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
    # Successors of the vanished `application/setup`, caught by the non-vacuity
    # assertion below. The setup surface did not shrink, it split: the operator
    # flow that collects profile facts is now `application/wizard`, and the
    # records it produces are persisted by `application/user_profile`. Both are
    # enrolled rather than one, because either alone would cover less than the
    # package it replaces -- and covering less while reading as fixed is the
    # exact failure this entry already suffered once.
    SRC_CADRUMO / "application" / "wizard",
    SRC_CADRUMO / "application" / "user_profile",
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
_SENSITIVE_DIRECT_WRITE_EXCEPTIONS: dict[tuple[str, str, str], str] = {
    (
        "src/cadrumo/application/user_profile/lifecycle.py",
        "_stage_and_validate_restore_database",
        "database.write_bytes",
    ): (
        "restore staging writes the bucket's own already-encrypted database file into the "
        "capsule staging directory, which publication then renames into place; the bytes are "
        "ciphertext the secure store produced, not plaintext escaping it, and the staged file "
        "is authenticated before it is published"
    ),
}
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
        "src/cadrumo/application/registry/_source_connectivity_authority.py",
        "digest",
        "os.open",
    ): "READ-ONLY evidence-descriptor verification, captured because this inventory catalogues "
    "every os.open regardless of flags -- the flags are a runtime value a static scan cannot "
    "judge, so a read is listed rather than guessed at. It opens O_RDONLY|O_NOFOLLOW, reads "
    "through os.fdopen(..., 'rb') to a SHA-256, and writes nothing. Its subject is repository "
    "SOURCE files under an explicitly injected root, not operator financial data, and the open "
    "is confined to that root by a final-path comparison, an is_relative_to check and a "
    "regular-file test",
    (
        "src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py",
        "_dump_wallet_diagnostic",
        "write_text",
    ): "operator-enabled IVA wallet diagnostic writes redacted structural metadata only",
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
    # --- profile custody filesystem substrate -------------------------------
    #
    # The capsule machinery is built from raw descriptors on purpose. It must
    # create exactly once (O_EXCL), pin a directory's IDENTITY rather than its
    # name while it works, and fsync both file and parent before a publication
    # rename is allowed to count. `pathlib` offers none of that, so every entry
    # below is the secure store's own hardened writer -- the thing this policy
    # exists to route data INTO -- rather than a path around it. What they
    # write is ciphertext, custody metadata, or nothing at all in the cases
    # that open a descriptor purely to hold an identity.
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem.py",
        "_fsync_directory",
        "os.open",
    ): "opens a directory descriptor to fsync it; writes no bytes",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem.py",
        "_fsync_windows_published_commit",
        "os.open",
    ): "opens the published commit file to fsync it; writes no bytes",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem.py",
        "_posix_open_exclusive_file",
        "os.open",
    ): "O_EXCL create of one capsule file, the publish-once primitive the capsule contract rests on",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem.py",
        "_profile_custody_posix_lock",
        "os.open",
    ): "custody transaction lock file; carries no data, only exclusion",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem.py",
        "_read_regular_file_open",
        "os.open",
    ): "read path; opened O_RDONLY with a regular-file identity check, writes nothing",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem.py",
        "_write_descriptor_fsynced",
        "os.write",
    ): "writes custody record bytes to a descriptor the caller already created O_EXCL, then fsyncs",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem.py",
        "_write_windows_local_stage",
        "os.open",
    ): "Windows staging create for the local custody record, published by rename",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem.py",
        "clear_profile_custody_local_record",
        "os.open",
    ): "opens the local custody record to truncate it under a held lock; clears custody state, stores none",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem.py",
        "write_profile_custody_local_record",
        "os.open",
    ): "creates the local custody record, which holds capsule pointers and no financial data",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem_primitives.py",
        "_write_exclusive_descriptor_fsynced",
        "os.write",
    ): "shared exclusive-create writer; writes caller-supplied custody bytes to its own O_EXCL descriptor",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem_primitives.py",
        "posix_directory_fd",
        "os.open",
    ): "O_DIRECTORY identity anchor; writes no bytes",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem_primitives.py",
        "posix_open_child_directory",
        "os.open",
    ): "O_DIRECTORY anchor for one child, opened relative to a pinned parent; writes no bytes",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem_primitives.py",
        "write_exclusive_fsynced",
        "os.open",
    ): "shared O_EXCL create used by every custody file writer",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_filesystem_primitives.py",
        "write_exclusive_fsynced_fd",
        "os.open",
    ): "the parent-relative form of the same O_EXCL create, so the target cannot be swapped under it",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_inventory.py",
        "_inventory_posix_file",
        "os.open",
    ): "read path; opens each capsule file no-follow to fingerprint it, writes nothing",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_kdf_codec.py",
        "_write_all",
        "os.write",
    ): "writes to the supervised KDF child's PIPE descriptor, never to a file",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_kdf_supervision.py",
        "profile_kdf_lease",
        "os.open",
    ): "the OS-released KDF permit lock file; an abnormal death releases it at the kernel boundary",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_kdf_supervision.py",
        "profile_kdf_lease",
        "os.write",
    ): "writes the permit holder marker into that lock file; carries no secret and no financial data",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_recovery_artifact.py",
        "_posix_external_directory_fd",
        "os.open",
    ): "anchors the operator-chosen export parent so the write cannot be redirected after the checks; writes no bytes",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_recovery_artifact.py",
        "_read_posix_regular_file",
        "os.open",
    ): "read path for importing a recovery artifact back; writes nothing",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_recovery_artifact.py",
        "_write_export_descriptor",
        "os.write",
    ): "the one sanctioned external export; writes the wrapped recovery artifact the operator explicitly requested, "
    "gated by the store-separately refusal that keeps it out of the storage root",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_recovery_artifact.py",
        "_write_external_exclusive",
        "os.open",
    ): "O_EXCL create for that same export, so it can never silently overwrite an existing artifact",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_sentinel.py",
        "_write_exclusive_fsynced",
        "os.open",
    ): "O_EXCL create of the DEK sentinel, which proves a key without storing one",
    (
        "src/cadrumo/adapters/persistence/storage/custody/_sentinel.py",
        "_write_exclusive_fsynced",
        "os.write",
    ): "writes those sentinel proof bytes; the sentinel is a verifier, never key material",
    # --- operator-facing secret display -------------------------------------
    (
        "src/cadrumo/entrypoints/cli/_config/_secure_input.py",
        "write_to_controlling_terminal",
        "open",
    ): "opens the controlling terminal DEVICE (CONOUT$ / /dev/tty) to show a recovery mnemonic, "
    "deliberately bypassing stdout so a bearer credential cannot land in a redirected stream, a JSON "
    "envelope or a log; a device is not a durable artefact and the function refuses outright when no "
    "terminal is attached rather than degrading to a capturable stream",
    # --- shared atomic-write primitives -------------------------------------
    (
        "src/cadrumo/core/atomic_write.py",
        "atomic_write_publish_once_bytes",
        "os.open",
    ): "shared publish-once primitive; O_EXCL create of caller-supplied bytes, holds no data of its own",
    (
        "src/cadrumo/core/atomic_write.py",
        "hardened_staged_publication",
        "os.open",
    ): "shared hardened staging primitive; same pattern, holds no data of its own",
    # --- profile restore staging --------------------------------------------
    (
        "src/cadrumo/application/user_profile/lifecycle.py",
        "_stage_and_validate_restore_database",
        "database.write_bytes",
    ): "stages the bucket's own already-encrypted database file for publication; the bytes are ciphertext the secure "
    "store produced, and the staged file is authenticated before the publishing rename",
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
