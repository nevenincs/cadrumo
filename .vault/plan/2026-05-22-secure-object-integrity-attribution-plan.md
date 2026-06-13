---
tags:
  - '#plan'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
tier: L2
related:
  - '[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-04-secure-object-integrity-adr]]'
  - '[[2026-06-04-secure-object-integrity-research]]'
---



# `secure-object-integrity` plan: unreadable-row attribution and fail-closed repair diagnostics

This plan extends the completed live IVA wallet and config-repair work
after the remaining critical finding: active-profile secure-object
integrity is still degraded across broader application namespaces even
though the current IVA wallet namespaces are readable.

The objective is read-only attribution first, mutation last. The
operator must be able to inspect which unreadable rows exist, what
namespace owns them, whether the namespace is singleton or multirow,
which active bucket context is safely inferable, and whether the likely
origin matches test-contamination or another storage-routing fault.
No plan step may decrypt or print private payloads, taxpayer ids,
filing identifiers, wallet amounts, or other sensitive row contents.

## Proposed Changes

Add a non-destructive integrity attribution layer under the existing
config repair backend. Expand namespace classification, test hygiene,
root-fallback write guards, readable-envelope validation, and
relational SQL diagnostics so the repair surface can explain corrupted
state without blindly quarantining tax evidence.

### Phase `P01` - unreadable-row attribution report

Add a read-only report that groups unreadable secure-object rows by
safe metadata and likely owner context.

- [x] `P01.S01` - add strict attribution report models for unreadable secure-object rows; `src/aeat/application/repair_integrity.py`.
- [x] `P01.S02` - group unreadable rows by namespace, timestamp range, classification, and singleton-vs-multirow semantics; `src/aeat/application/repair_integrity.py`.
- [x] `P01.S03` - expose attribution output through the existing config repair integrity surface; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P01.S04` - add real-behavior tests for attribution output without payload disclosure; `src/aeat/application/test_repair_integrity.py`.

### Phase `P02` - ephemeral-key test hygiene guard

Prevent new tests from writing throwaway-key encrypted rows into the
active profile database.

- [x] `P02.S05` - add a static hygiene guard for `EphemeralMasterKeyProvider` plus default SQL-backed repositories; `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`.
- [x] `P02.S06` - repair or explicitly classify every hygiene violation found by the guard; `src/aeat`.
- [x] `P02.S07` - document accepted isolation patterns in test helper code, not prose-only docs; `src/aeat/tests`.

### Phase `P03` - root-fallback write refusal

Make profile-bound writes refuse the root fallback database unless a
test or diagnostic explicitly opts into it.

- [x] `P03.S08` - add a storage-route classifier that distinguishes explicit database URLs, active-bucket databases, and root fallback databases; `src/aeat/core/config.py`.
- [x] `P03.S09` - route profile-bound write commands through a root-fallback refusal guard; `src/aeat/entrypoints/cli`.
- [x] `P03.S10` - add CLI regression tests proving guarded writes refuse root fallback and keep bootstrap-safe read-only probes working; `src/aeat/entrypoints/cli`.

### Phase `P04` - namespace and envelope integrity coverage

Broaden integrity diagnostics beyond AES-GCM decryptability.

- [x] `P04.S11` - extend namespace classification to every active namespace discovered by `list_namespaces`; `src/aeat/application/repair_integrity.py`.
- [x] `P04.S12` - add readable-row envelope validation against owning repository classification and schema contracts; `src/aeat/application/repair_integrity.py`.
- [x] `P04.S13` - add relational SQL table and foreign-key integrity diagnostics outside `secure_objects`; `src/aeat/application/diagnostics.py`.

### Phase `P05` - verification and localization

Close the extension wave with locale-safe command text and review.

- [x] `P05.S14` - update new CLI strings through the `aeat.locales` module CLI; `src/aeat/locales`.
- [x] `P05.S15` - run focused repair, config, storage, and diagnostics tests plus registry and locale gates; `src/aeat`.
- [x] `P05.S16` - run mandatory code review and persist the audit record; `.vault/audit`.

## Parallelization

`P01` must land first because later phases consume the attribution
models and safe metadata vocabulary. `P02` can run after `P01.S01`
because the hygiene guard is independent of the CLI attribution output.
`P03` and `P04` should run after `P01` so they share route and namespace
classification terms. `P05` is the final gate and must run last.

## Verification

The plan is complete when all step rows are checked through the
`vault plan` CLI, no unreadable-row report prints private payload
content, focused repair/config/storage tests pass, locale changes are
made through `python -m aeat.locales`, registry verification still
passes, and a code-review audit reports no critical or high findings.
