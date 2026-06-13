---
tags:
  - '#audit'
  - '#security-swarm-2026-05-30'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-30-security-swarm-2026-05-30-audit]]"
---

# `security-swarm-2026-05-30` audit: path traversal and filesystem security

## Scope

Read-only audit of axis 5 of 6 in the AEAT security swarm: path traversal,
symlink handling, atomic writes, lockfile race conditions, archive
extraction, file permissions on sensitive payloads, and Windows-specific
filesystem hazards. Surfaces inspected: `src/aeat/core/paths.py`,
`src/aeat/core/env_io.py`, `src/aeat/core/locks.py`,
`src/aeat/core/corpus_manifest/__init__.py`,
`src/aeat/adapters/persistence/storage/**`,
`src/aeat/adapters/outbound/storage/_local.py`,
`src/aeat/adapters/outbound/llm/_cache.py`,
`src/aeat/application/evidence/_service.py`,
`src/aeat/application/ledger/_evidence.py`,
`src/aeat/application/ledger/_actions.py`, `src/aeat/locales/manager.py`.

The codebase has unusually strong defensive primitives: `core/paths.py`
exposes `resolve_relative_subpath` and `resolve_record_json_path` with
strict containment, master-key writes use
`os.open(O_WRONLY|O_CREAT|O_EXCL, 0o600)`, bucket locks use `O_EXCL` for
atomic creation, and every boundary write goes through
`tempfile + os.replace`. The findings below are residual gaps after that
baseline.

## Findings

### LOW: `env/.env` written without explicit `0o600` mode

- file:line: `src/aeat/core/env_io.py:62-74`
- attack: `_atomic_write_text` uses `tempfile.NamedTemporaryFile` with no
  `mode=` argument, so the tempfile lands at the process umask default
  (commonly `0o644` on Linux). The file holds
  `AEAT_LIVE_TESTS_ENABLED`, storage roots, certificate paths, and
  Google API resource identifiers. A local unprivileged user on a
  multi-tenant host can read the operator's live-tests posture and
  infer cert locations. The module docstring claims the payload is
  "operator-controlled configuration, not a secret", but certificate
  path disclosure is a fingerprinting aid for follow-on attacks.
- remediation: Open the tempfile with
  `os.open(..., O_WRONLY|O_CREAT|O_EXCL, 0o600)` mirroring the
  master-key pattern at
  `src/aeat/adapters/persistence/storage/master_key/_master_key.py:260-270`,
  or chmod the tempfile to `0o600` before `os.replace`. On Windows
  `os.chmod` is documented no-op and the existing comment at
  `master_key/_master_key.py:822-823` already accepts that limitation.

### LOW: `LocalFileSystemProvider` payloads written without restrictive mode

- file:line: `src/aeat/adapters/outbound/storage/_local.py:188-189`
- attack: `tmp_path.write_bytes(payload)` writes through `pathlib`,
  which uses `os.open(..., O_WRONLY|O_CREAT|O_TRUNC, 0o666)` on POSIX
  (subject to umask). Payloads in this provider are already encrypted
  upstream (module docstring states "encryption + classification stay
  above this layer"), so ciphertext disclosure is bounded. However the
  sidecar at line 213 (`sidecar_path.write_text`) carries
  `content_hash`, `object_key_hmac`, and `byte_length` which together
  enable size-channel inference against the encrypted blob set.
- remediation: Wrap the tmp write in `os.open(..., 0o600)` +
  `os.fdopen`, or chmod after write. Tighten the namespace directory
  mkdir to `0o700` for consistency with the substrate's
  `master_key/_master_key.py:822` pattern.

### LOW: `core.paths.resolve_record_json_path` does not use `strict=True`

- file:line: `src/aeat/core/paths.py:137-143`
- attack: `Path.resolve()` (without `strict=True`) silently succeeds
  when the path does not yet exist; symlink resolution still happens
  for existing prefix components. If an attacker with write access to
  the parent directory plants a symlink named `<record_id>.json`
  pointing outside `root`, the subsequent
  `relative_to(resolved_root)` check catches the escape — that part
  is correct. But if the attacker plants a symlink at an intermediate
  component of `root` itself, the subsequent open could land outside
  the intended tree. The `_SAFE_FILE_TOKEN_RE` guard limits
  `record_id` to a single safe segment, so the residual risk is the
  root-directory provisioning question.
- remediation: Document that callers must supply a fully-resolved
  `root` (most already do — see `application/filing/runtime.py:235`).
  Optionally reject `path.is_symlink()` on the resolved path before
  return. This is defence-in-depth tightening, not a live exploit.

### LOW: `PurchaseInvoiceEvidence.add` accepts symlink sources without rejection

- file:line: `src/aeat/application/ledger/_evidence.py:228-241`
- attack: `Path(source_path).expanduser().resolve()` follows symlinks
  silently. The resolved absolute path is stored in the bucket record
  as `source_path` and the SHA-256 is hashed over the followed target.
  An operator who imported a symlink at evidence-attach time will
  silently lose evidence integrity if the symlink target is later
  changed: the on-disk `source_path` string still points at the
  symlink, but the hash was taken over the snapshot-time target. No
  tamper signal is raised on re-hash because the recorded
  `source_path` re-follows the link.
- remediation: Inspect the pre-resolve path with
  `Path(source_path).is_symlink()` and reject, or persist both the
  symlink path and the followed-target hash. Mirrors the
  `corpus_manifest/__init__.py:178` defence which skips symlinks
  deliberately.

### LOW: `evidence._service.export` writes the zip without atomic rename

- file:line: `src/aeat/application/evidence/_service.py:289-301`
- attack: `output_path.parent.mkdir(...)` then
  `zipfile.ZipFile(output_path, mode="w", ...)` writes the archive
  directly to the destination path. A crash, SIGKILL, or disk-full
  event mid-write leaves a partial zip at `output_path`. A subsequent
  `aeat audit replay` could attempt to verify the truncated archive
  and fail with a misleading verification error; worse, an operator
  could distribute the partial file thinking it is complete. The
  manifest-last ordering documented at line 292 addresses the
  "manifest claims records that aren't there" case but not the
  "archive truncated mid-write" case.
- remediation: Write to
  `output_path.with_suffix(output_path.suffix + ".tmp")`, then
  `os.replace(tmp, output_path)` after `ZipFile.close()`. Mirrors
  every other write in the substrate (`_namespace_registry`,
  `_envelope`, `_blob_store`, `_local.py:189`).

### LOW: locale `_locale_path` allow-list has a narrow TOCTOU window

- file:line: `src/aeat/locales/manager.py:159-171`
- attack: The check
  `allowed_locales = {path.stem for path in self.locales_dir.glob("*.yml")}`
  enumerates the directory on every call. The
  `locale != Path(locale).name or Path(locale).suffix` guard at line
  157 already rejects path separators and traversal segments, so this
  is well-defended. The residual concern is a TOCTOU window between
  the `glob`-derived allow-list build and the `is_file()` check at
  line 169 — an attacker with write access to `locales_dir` could
  swap a regular file for a symlink between those two calls. Severity
  is low because (a) `locales_dir` is package data, not user-writable
  on a deployed install, and (b) the `relative_to` check at line 166
  still catches escapes.
- remediation: Open the file with `os.open(..., O_RDONLY|O_NOFOLLOW)`
  on POSIX to reject mid-call symlink swaps. Out of scope on Windows.

### INFORMATIONAL: archive extraction is not present in production paths

- file:line: n/a (scanned `tarfile.open`, `extractall`,
  `ZipFile.extract`, `ZipFile.extractall` across `src/aeat`)
- finding: No production code path extracts a caller-supplied archive.
  The only `zipfile.ZipFile` usages are write paths
  (`application/evidence/_service.py:294`) and test-side read paths
  (`tests/test_wheel_bundles_corpus_and_registry.py:114`,
  `entrypoints/cli/test_audit_verbs.py:119`). No `tarfile` usage at
  all. The zip-slip / tar-slip attack class does not apply to the
  current attack surface.

### INFORMATIONAL: bucket lockfile uses correct atomic primitives

- file:line: `src/aeat/adapters/persistence/storage/bucket/_lockfile.py:120-122`
- finding: `os.open(target, O_CREAT|O_EXCL|O_WRONLY, 0o644)` is the
  textbook portable atomic-lock primitive; `O_EXCL` is mandated atomic
  on every POSIX kernel and on Windows NTFS. The companion module
  `core/locks.py:218-221` adds `fcntl.flock` / `msvcrt.locking`
  mandatory locking on top of the lockfile dirent. No TOCTOU between
  check-existence and lock-acquire because there is no check-then-act
  sequence — acquisition is the single `O_EXCL` syscall.

### INFORMATIONAL: `llm._cache._sanitise_model_for_path` correctly rejects traversal

- file:line: `src/aeat/adapters/outbound/llm/_cache.py:239-249`
- finding: The model-identifier sanitiser at
  `_sanitise_model_for_path` rejects `..`, leading dots, backslashes,
  drive letters, and NUL bytes before path composition. Coverage
  matches the test surface at `test_cache.py:81-113` (eight traversal
  payloads exercised).

### INFORMATIONAL: `_local._validate_namespace` / `_validate_hmac` bound the namespace tree

- file:line: `src/aeat/adapters/outbound/storage/_local.py:45-66`
- finding: Both validators reject `/`, `\\`, leading dots, and any
  non-alnum/non-`-_` character. Combined with `_HMAC_PREFIX_LEN = 8`
  and `_validate_label` clamping to 64 chars with safe-char
  replacement, the resolved path cannot escape `self._root`
  regardless of caller input.

## Summary

- HIGH: 0
- MEDIUM: 0
- LOW: 6
- INFORMATIONAL: 4

Total: 10 findings. No exploitable root-escape or arbitrary-file-overwrite
vulnerability was located. The codebase consistently anchors caller-
supplied sub-paths through `resolve_relative_subpath` /
`resolve_record_json_path`, uses `tempfile + os.replace` for every
persistence boundary, and uses `O_EXCL` for atomic lock creation. The
residual LOW findings cluster around two themes: (1) permission hygiene
on tempfile creation (`env/.env`, `LocalFileSystemProvider` payloads)
where umask, not explicit mode, governs the final permission bits, and
(2) symlink handling on operator-supplied input paths
(`ledger evidence add`, intermediate components of
`resolve_record_json_path`). The single most concerning finding is the
non-atomic write of evidence-bundle ZIP archives at
`application/evidence/_service.py:289-301`, where a crash leaves a
partially-written archive at the operator-facing output path with no
distinguishing tempfile marker.

## Recommendations

Adopt the master-key `os.open(..., 0o600)` pattern uniformly across
every tempfile write that does not already use it (`env_io`,
`_local.py`). Wrap the evidence `ZipFile` write in a tempfile +
`os.replace` so a crash mid-export does not leave a partial archive at
the destination path. Add a `Path.is_symlink()` rejection in
`application/ledger/_evidence.py` to keep the source-hash contract
stable across post-attach symlink target swaps. Treat the six LOW
findings as defence-in-depth tightening; none are exploitable in the
current deployment shape (single-operator install, no multi-tenant
filesystem).
