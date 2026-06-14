---
tags:
  - '#plan'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
tier: L3
related:
  - '[[2026-06-14-storage-backend-security-review-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `storage-backend-security-review` plan

## Wave `W01` - security edges self-contained

Close the two exploitable security edges plus the KDF floor and dead-surface deletions; self-contained and highest operator-safety value, lands first per the architecture ADR backlog ordering.

Close the residual secure-storage security, integrity, correctness, and standardisation gap in six blast-radius waves.

### Phase `W01.P01` - export-archive KDF

Replace HKDF export-archive sealing with Argon2id and prove roundtrip.

- [x] `W01.P01.S01` - Replace export-archive HKDF sealing-key derivation with Argon2id and persist the kdf params in the recovery-wrap member; `src/aeat/application/bucket_maintenance/_service.py`.
- [x] `W01.P01.S02` - Add a strict export then import roundtrip test over the Argon2id-sealed archive with a non-default passphrase; `src/aeat/application/bucket_maintenance/tests/`.

### Phase `W01.P02` - decrypted-PDF-to-disk elimination

Parse the bbox declaration in memory and delete the tmp scratch path.

- [x] `W01.P02.S03` - Accept an in-memory binary stream in the bbox declaration parse path so no decrypted bytes touch disk; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `W01.P02.S04` - Delete the temporary sensitive PDF helper and fold the bbox branch into the in-memory bytes path; `src/aeat/adapters/outbound/aeat/sede/_declarations_observations.py`.

### Phase `W01.P03` - KDF floor and dead-surface deletion

Add the read-time Argon2 cost floor and delete write-only and dead crypto surfaces.

- [x] `W01.P03.S05` - Apply the manifest KDF validation window to the file-fallback parameters on read and reject below-floor Argon2 cost; `src/aeat/adapters/persistence/storage/master_key/_master_key_records.py`.
- [x] `W01.P03.S06` - Delete the dead non-atomic _write_bytes_secure method and its sensitive-persistence-policy allowlist entries; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `W01.P03.S32` - OWNER-GATED DEFERRED: remove the write-only standalone salt artefact and shrink the torn-install detection tuple after owner review per the no-legacy-compatibility key-management caution; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.

## Wave `W02` - at-rest integrity row binding

Bind row identity into the secure-object payload AEAD and verify integrity columns on read; highest-confidence finding corroborated by two axes and structurally central to every secure-object read. Depends on W01 landing clean.

### Phase `W02.P04` - AEAD row-identity binding and read verification

Bind row identity into the payload AEAD and verify integrity columns on read, failing closed.

- [ ] `W02.P04.S07` - Bind namespace and object-key digest and schema version into the secure-object payload AEAD associated data; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`.
- [ ] `W02.P04.S08` - Verify the stored payload hash and recomputed revision id on every secure-object read and fail closed on mismatch; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `W02.P04.S09` - Add a row-substitution and corrupted-hash anti-tautology test proving read-time refusal; `src/aeat/adapters/persistence/storage/sql/tests/`.

## Wave `W03` - concurrency and durability

Add WAL and busy_timeout to the bucket engine, fsync the manifest atomic write, and re-validate lockfile reclaim so concurrent invocations and power loss are safe.

### Phase `W03.P05` - SQLite engine pragmas

Set WAL, busy_timeout, and synchronous on the bucket engine connect listener.

- [x] `W03.P05.S10` - Set SQLite busy_timeout in the bucket engine connect listener so a concurrent invocation waits rather than failing immediately with database-locked; `src/aeat/adapters/persistence/storage/sql/engine.py`.
- [x] `W03.P05.S11` - Add a concurrent-writer regression proving two sessions on one bucket do not raise an immediate database-locked error; `src/aeat/adapters/persistence/storage/sql/tests/`.
- [ ] `W03.P05.S33` - LARGER FOLLOW-UP: enable journal_mode=WAL and synchronous=NORMAL after migrating the ~21 at-rest raw-db test readers to a shared WAL-aware helper that also scans the -wal sidecar; `src/aeat/adapters/persistence/storage/sql/engine.py`.

### Phase `W03.P06` - durability and locking

fsync the manifest atomic write, re-validate lockfile reclaim, dispose engine on hard-delete.

- [x] `W03.P06.S12` - fsync the staged tmp file and the parent directory before and after os.replace on the manifest write; `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`.
- [x] `W03.P06.S13` - Re-read and re-validate the holder PID immediately before the stale-lock reclaim unlink; `src/aeat/adapters/persistence/storage/bucket/_lockfile.py`.
- [ ] `W03.P06.S14` - Dispose the cached engine when a bucket DB is hard-deleted so a recreated file does not reuse stale connections; `src/aeat/adapters/persistence/storage/sql/engine.py`.

## Wave `W04` - cross-machine correctness

Make persisted and exported records portable and roundtrip-equal across machines: relative provenance, deterministic bundles, rename integrity detection, and the manifest-digest contract.

### Phase `W04.P07` - portable provenance

Replace absolute source_path with relative or sha-only provenance and prove cross-OS roundtrip.

- [x] `W04.P07.S15` - Replace the resolved absolute source_path provenance with a relative filename or sha-only reference in the raw transaction model; `src/aeat/domain/transactions/_raw_transaction.py`.
- [x] `W04.P07.S16` - Add a cross-OS transaction provenance roundtrip test proving rehydration does not mutate the persisted shape; `src/aeat/domain/transactions/tests/`.

### Phase `W04.P08` - determinism and audit hygiene

Remove non-deterministic bundle timestamps and host-absolute paths from the audit log.

- [x] `W04.P08.S17` - Move exported_at out of the equality-bearing portable bundle payload; `src/aeat/domain/user_profile/_portable_export.py`.
- [x] `W04.P08.S18` - Persist basename-only paths in the bucket exported and imported event payloads; `src/aeat/application/bucket_maintenance/_service.py`.

### Phase `W04.P09` - rename integrity and digest contract

Detect cross-store rename drift and resolve the manifest-digest doc-vs-code gap.

- [x] `W04.P09.S19` - Compare the manifest label against the record display_name in verify_profile_integrity and raise on divergence; `src/aeat/application/user_profile/_profile_repository.py`.
- [x] `W04.P09.S20` - Implement the manifest-digest cross-check over a timestamp-independent projection or correct the contract docstring; `src/aeat/application/bucket_maintenance/_manifest_digest.py`.

## Wave `W05` - standardisation structure enrollment

Route every namespace literal through the registry and extend the adoption gate, resolve the hexagonal inversion and private imports, consume the canonical wrapper, and delete the v1 bundle branch.

### Phase `W05.P10` - namespace registry adoption

Route domain and outbound namespace literals through the registry and extend the adoption gate.

- [ ] `W05.P10.S21` - Route every domain and outbound secure-object namespace literal through its STORAGE_NAMESPACE_REGISTRY definition constant; `src/aeat/domain/`.
- [ ] `W05.P10.S22` - Extend the namespace adoption gate to scan domain and adapters outbound in addition to application; `src/aeat/application/tests/test_namespace_registry_adoption.py`.

### Phase `W05.P11` - hexagonal and import hygiene

Resolve the fincas inversion, rebind private-submodule imports, and promote missing re-exports.

- [ ] `W05.P11.S23` - Resolve the fincas domain hexagonal inversion by relocating the ORM-coupled repository or exposing a typed boundary facade and fix the stale docstring path; `src/aeat/domain/fincas/_repository.py`.
- [x] `W05.P11.S24` - Rebind the private bucket-submodule imports in profile health and overview to the bucket package surface; `src/aeat/application/workflow/_profile_health.py`.
- [ ] `W05.P11.S25` - Promote the sealed-archive read and write helpers to the bucket package all and rebind the maintenance service call sites; `src/aeat/adapters/persistence/storage/bucket/__init__.py`.

### Phase `W05.P12` - enrollment and legacy deletion

Consume the canonical wrapper, delete the v1 bundle branch, and confirm the SQL rotation contract.

- [x] `W05.P12.S26` - Replace the three private secure-objects-for-bucket route helpers with the canonical secure_object_repository_for_bucket wrapper; `src/aeat/domain/invoices/_repository.py`.
- [ ] `W05.P12.S27` - Delete the v1 portable-bundle compat branch and drop version 1 from the supported set per no-legacy-compatibility; `src/aeat/application/user_profile/_bundle.py`.
- [ ] `W05.P12.S28` - Confirm the SQL secure_objects store is covered by the bucket-DEK rewrap rotation path and document or extend the rotation contract; `src/aeat/adapters/persistence/storage/_rotation.py`.

## Wave `W06` - performance

Remove decrypt amplification on the ledger write path and the namespace enumeration scans; sequenced last because the per-transaction-row redesign is the largest item and must not block the security work.

### Phase `W06.P13` - decrypt amplification

Remove the attach_evidence double-decrypt and thread one catalogue per command.

- [x] `W06.P13.S29` - Remove the attach_evidence double full-catalogue decrypt by threading one decrypted catalogue through the command; `src/aeat/application/ledger/_actions_manual.py`.

### Phase `W06.P14` - enumeration and row redesign

Stream namespace enumeration and move transactions to one secure-object row per id.

- [ ] `W06.P14.S30` - Make secure-object namespace enumeration stream decrypted rows instead of materialising and sorting the full set; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `W06.P14.S31` - Move the transaction catalogue to one secure-object row per transaction keyed by transaction id so single-row mutations stop rewriting the whole catalogue; `src/aeat/domain/transactions/_repository.py`.

## Description

Remediate the eleven HIGH, ten MEDIUM, and seven LOW findings of the five-axis
secure-storage audit recorded in the research, against the boundary mandated by
the production-hardening architecture ADR. Work proceeds in six blast-radius
waves: security edges, at-rest integrity, concurrency and durability,
cross-machine correctness, standardisation and enrollment, and performance. Every
persistence-shape change carries a strict non-default roundtrip test and an
anti-tautology proof; every change is one atomic explicit-pathspec commit on the
shared branch, authored only over files with no peer WIP.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

Waves are sequenced by default; W02 in particular depends on W01 landing clean
because it changes the AEAD scheme. Within a wave the phases are largely
independent and may be parallelized: W01 P01/P02/P03 touch disjoint files, as do
W04 P07/P08/P09 and W05 P10/P11/P12. The exception is W06 P14, whose
per-transaction-row redesign must follow the W02 AEAD binding and the W04
provenance change since both alter the transaction persistence shape.

## Verification

The plan is complete when every Step is closed with a matching exec record. Each
Step's gate is the relevant focused pytest suite green plus
`uv run --no-sync pytest --collect-only -q` clean on the touched tree before its
commit. Campaign-level success criteria: the export archive seals under a password
KDF; no decrypted financial bytes touch disk on any path; a row-substitution test
fails closed; concurrent writers on one bucket do not raise database-locked; a
cross-OS transaction roundtrip is byte-equal; the namespace adoption gate scans
domain and outbound and is green; and a fresh-context honesty review runs before
the campaign is declared structurally complete.
