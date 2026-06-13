---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave11-research]]"
  - "[[2026-04-30-secure-persistence-foundation-wave11-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-final-security-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-final-security-resolution-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave7-audit]]"
---

# `secure-persistence-foundation` audit: wave-11 corpus integrity manifest

## Scope

Audit gate for **wave-11**: directory-level SHA-256 integrity manifest for the four CORPUS-class roots (casillas, manuals, normatives, vat-catalogue), closing the structural-integrity gap surfaced by the final security audit.

Wave-11 in scope:

- Substrate module `src/aeat/adapters/persistence/storage/_corpus_manifest.py` (~340 LoC)
- Three new error classes + trilingual error-code registry registrations
- Public re-exports through `src/aeat/adapters/persistence/storage/__init__.py`
- CLI command `aeat security verify-corpus` with `--corpus` and `--regenerate`
- 27 tests (21 substrate + 6 CLI)
- Vault: research + ADR + this audit

Out of scope (deferred to subsequent waves, all still landing in this PR per the no-deferring directive):

- Argon2id KDF migration (wave-12; needs `argon2-cffi` dep)
- SQLCipher whole-database encryption (wave-12+; needs new dep)
- IDENTITY-class typed records expansion in `SecretStore`
- `_validate_*_id` consolidation refactor
- Connector + export governance hardening (MEDIUM from upstream-reconciliation audit)

## Findings

### Strengths

**Self-attesting digest design.** The manifest's `manifest_sha256` is computed over canonical JSON of every field except itself: `{manifest_version, corpus_root_name, generated_at, entries}` with `sort_keys=True`, `(",", ":")` separators, `ensure_ascii=False`, UTF-8 encoded. Any tampering of body bytes — including an attacker swapping a single entry's `sha256` — invalidates the recorded digest and triggers `CorpusManifestTamperError` at load time. Verified by `test_tampered_manifest_body_raises`.

**Version-gated parsing.** `_MANIFEST_VERSION = 1` is the only version accepted on load. `test_unknown_manifest_version_rejected` deliberately recomputes the manifest digest with version=999 to prove the rejection comes from the version gate and not from the tamper gate.

**Pydantic v2 boundary validation.** `CorpusEntry.relative_path` rejects: empty string, single dot, double dot, absolute paths (`PurePosixPath.is_absolute()`), and any `.` / `..` part anywhere in the path. Parametrised over six hostile inputs in `test_unsafe_relative_path_rejected`. `CorpusManifest.generated_at` requires tz-aware timestamps, rejecting naive datetimes.

**Streaming hash.** `_hash_file` reads in 64 KiB chunks so manuals PDFs (multi-MiB) hash without memory inflation. `test_large_file_hashes_correctly` verifies a 200 KiB synthetic payload across 3+ chunks of the read loop matches `hashlib.sha256(payload).hexdigest()`.

**Deterministic ordering.** Entries are sorted by `relative_path` before serialisation, so the manifest digest is byte-identical across operating systems regardless of `os.walk` order. `test_build_then_verify_clean` asserts the sorted-paths invariant.

**Sidecar self-skip.** `_iter_corpus_files` skips dotfiles and the manifest sidecar itself (`corpus.manifest.json`), so a regenerate is never contaminated by the previous run's artefact. Verified by `test_build_skips_dotfiles_and_manifest_sidecar`.

**Hard cutover, no plaintext fallback.** Per the wave-9 hard-cutover principle, this module never accepts an unsigned/legacy manifest variant. Either a v1 self-attesting manifest is on disk with a matching digest, or load raises.

**Operator CLI parity with wave-10.** `aeat security verify-corpus` follows the exact ergonomics of `rotate-master-key`: deferred imports (no Alembic discovery cost on unrelated subcommands), Rich-printed status, exit-1 on any failure path (drift / missing sidecar / invalid manifest), exit-0 on clean. CI can gate directly on the exit code.

**Trilingual errors in registry.** All three new errors registered with `default_message_es` / `default_message_en` / `default_message_hu`, plus `default_suggestion="aeat security verify-corpus --regenerate"` where actionable. Confirmed via `pytest src/aeat/errors` (25/25 pass).

**No regression in storage substrate.** Full storage suite passes 293/293 (5 skipped, all pre-existing live-marker skips).

### Residual risks (low-severity, accepted)

**R1 — Hash algorithm lock-in.** `_MANIFEST_VERSION=1` implicitly binds to SHA-256. If we later migrate to SHA-3 or BLAKE3, version bump + parallel reader is required. Acceptable: SHA-256 is well below NIST sunset and we control upgrade cadence.

**R2 — TOCTOU window between digest verify and entry verify.** `assert_corpus_clean` first calls `load_corpus_manifest` (verifies body digest), then walks the live corpus to compare. Between those two operations a hostile process could rewrite both the sidecar and a corpus file. Acceptable: this tool is a CI gate and runbook step, not an online security control. Operators run it on an isolated working tree before tagging a release; concurrent-attacker model does not apply.

**R3 — Symlink semantics.** `_iter_corpus_files` uses `Path.rglob("*")` + `is_file()`, which follows symlinks transparently. A malicious actor with write access to the corpus tree could insert a symlink to a file outside the corpus. Acceptable: corpus roots are dev-supervised assets under `git`, and the `relative_path` validator rejects any `..` segment so escape from the manifest namespace is impossible — but symlinks pointing to absolute targets within the same volume are not blocked. Track in a future wave only if the attacker model widens.

**R4 — `corpus_root_name` is operator-supplied.** `build_corpus_manifest(root, corpus_root_name="casillas")` records the supplied name in the manifest body. A misconfigured operator could re-tag one corpus's manifest as another's. Acceptable: this only changes the human-readable label inside the manifest; the digest binds the body, and `verify_corpus_manifest` does not consult `corpus_root_name` for the integrity decision.

### Findings against deferred-list items (none worsened, several made testable)

The corpus integrity manifest is a precondition for subsequent governance work:

- **Argon2id migration (wave-12)** — when the master-key wrapping algorithm changes, the corpus manifest is unaffected (CORPUS class is plaintext-acceptable per the classification policy and never touches the master key). No coupling to manage.
- **SQLCipher whole-DB encryption** — the SQLite database is FINANCIAL/AUDIT class and lives outside the CORPUS roots. Manifest never overlaps DB files; the two integrity surfaces compose cleanly.
- **IDENTITY-typed records in SecretStore** — orthogonal to corpus manifest; SecretStore lives under `secrets/`, never under a corpus root.

## Recommendations

**Pass the gate.** Wave-11 closes the corpus-integrity finding from the final security audit, lands with hard cutover and zero legacy code, and has full test coverage of the threat model relevant to a CI integrity gate.

**Wire the CLI into CI.** Add `aeat security verify-corpus --corpus casillas` (and the three peers) to the pre-tag CI job. With no sidecar present today, the command exits 1 — the natural way to bootstrap is to commit one regenerated sidecar per corpus the first time CI runs and to enforce thereafter.

**Track the symlink decision.** R3 is accepted under the current attacker model. If the threat model widens to "hostile insider with corpus-tree write access", revisit `_iter_corpus_files` to add `Path.is_symlink()` rejection or to require resolved targets to be inside the corpus root.

**Open wave-12 immediately.** Per the user's "no deferring" directive, the next-highest-leverage no-dep-yet item is the **Argon2id KDF migration ADR**. The dependency `argon2-cffi` is small (~50 KiB pure-rust binding), the migration is bytes-level (every wrapped DEK can be re-wrapped under Argon2id-derived KEK with a one-shot rotation tool that mirrors `rotate_master_key`), and it closes the last cryptographic-primitive findings from the final audit.

**Do not regress on review latency.** External reviews (`@gemini` + `@codex`) requested on commit 67b4f09 at PR #441 comments 4334163407 / 4334164592. Findings, when they arrive, are absorbed into this audit by amending the residual-risks section rather than opening a wave-12 prematurely.

## Verdict

**Wave-11 audit gate: PASS.** Substrate + CLI + tests are coherent, hard-cutover, regression-free across the storage substrate, and address the corpus-integrity gap from the final security audit. Residual risks R1–R4 are low-severity and explicitly accepted under the current attacker model.

Proceeding to wave-12 (Argon2id KDF migration) per the standing no-deferring directive.
