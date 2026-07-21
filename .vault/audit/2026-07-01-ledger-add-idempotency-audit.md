---
tags:
  - '#audit'
  - '#ledger-add-idempotency'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# `ledger-add-idempotency` audit: `ledger-add-idempotency close honesty review`

## Scope

Fresh-context independent code review (dispatched to a dedicated reviewer persona) over the 16 feature commits of `ledger-add-idempotency`, run as the campaign-close honesty-review gate before declaring the pipeline complete. Reviewed: the manual `ledger add` guarded-idempotent keyed no-op + conflict refusal, the `modelo verify` content-pinned report id, and the `modelo file` content-pinned filing-record id + idempotent re-file. Verdict: PASS / GO, no CRITICAL, no HIGH; core safety and correctness hold.

## Findings

### idempotency-guard-field-omission | medium | same-key add differing only in recargo_amount/source_jurisdiction silently no-ops (fixed)

`_command_matches_current` (`src/aeat/application/ledger/_actions_common.py`), reused by the manual-add idempotency conflict gate, omitted `recargo_amount` and `source_jurisdiction`. A same-key add differing only in those fields silently no-oped and dropped the new value — a silent under-declaration of the recargo de equivalencia surcharge. FIXED in `bdd141a59`: both fields added to the match, with two regression tests proving each difference now raises the conflict refusal.

### filing-anti-tautology-not-load-bearing | medium | filing-record id-mismatch proof passed for the wrong reason (fixed)

The filing-record anti-tautology test seeded `revision_id` with an invalid-hex value, so the `CalculationRevisionId` field pattern raised during field validation before the outcome-pinned id model_validator ran — the mandated proof was not load-bearing. FIXED in `ce1f79e38`: a valid, distinct hex seed makes the model_validator's id-mismatch check the raising path.

### f5bd349a5-scope-bleed | medium | provider-id fix commit bundled unrelated M390 registry work (deferred, not reverted)

Commit `f5bd349a5` (the P01.S01 provider-id lookup fix) also bundled unrelated Modelo 390 registry TOML plus a 253-line M390 fold-in test — a scope-bleed / peer-WIP capture into an atomic ledger commit. The M390 work is preserved in history; reverting would destroy it and is entangled with the ledger fix. VERIFIED intact and coherent: the captured set is a complete régimen-simplificado cuota-devengada fold-in — the relation `modelo-390-rel-303-cuota-devengada-simplificado` (M390 box 79 ← M303 4T casilla 54, `op = copy`, grounded in LIVA arts. 122/123 + RD 1624/1992 art. 71) plus its `target_binding`, casillas, construct, completeness-manifest entry, dependency classification, and live test — not a half-swept fragment. Left in history under the ledger commit; the only residue is that it rode in without its own review, which this note records. Not unwound.

### s22-inline-notice-message | low | modelo-file no-op Notice uses an inline string, not a tr() key (FIXED)

The S22 modelo-file no-op Notice used an inline message string rather than a `tr()` locale key. FIXED in `cd3531ed7`: promoted to the `cli.app.modelo.work.file_idempotent_noop` locale key, translated in all four catalogues, for parity with the localized ledger-add no-op. Because the four locale catalogues were under continuous concurrent multi-campaign rewrite (peer keys uncommitted in the working tree and ~10 peer files staged in the shared index), the commit was built via a temporary index (`GIT_INDEX_FILE` + `commit-tree`) so it carries only this one new key per catalogue and swept zero peer locale WIP — verified: each `.yml` in the commit shows exactly one added line and no peer line.

### s16-roundtrip-strength | low | Transaction roundtrip is survives-reload, not strict-equality + on-disk-mutation (FIXED)

P05.S16's fingerprint roundtrip was a survives-reload presence check. FIXED in `3f4206d3d`: added strict full-model equality across a fresh repository over the same store (the non-default `import_fingerprint` roundtrips exactly, not re-defaults) plus a content-bound anti-tautology leg (a different movement yields a different fingerprint).

### m714-peer-registry-regression | out-of-scope | 5 file-flow tests red from a peer M714 invalid verification expectation

Five `test_file_flow_filing.py` tests fail at registry load with `modelo 714 revision 2021-y-siguientes: verification expectation references unknown casilla '29'/'39'`. The cause is an UNTRACKED peer directory `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/verification_expectations/` — the M714 campaign's in-flight invalid registry state — not this feature. Owner-attributed to the M714 campaign per `full-tree-gate-must-distinguish-owner`; surfaced for that campaign to fix.

## Recommendations

- All in-scope findings are now FIXED and re-verified (my feature surface: 35 passed — idempotency 13, filing roundtrip 15, locale 7): MEDIUM-2 `bdd141a59`, MEDIUM-1 `ce1f79e38`, LOW-S16 `3f4206d3d`, LOW-S22-tr `cd3531ed7`. No further action on the feature.
- MEDIUM-3 (`f5bd349a5` scope bleed): VERIFIED — the bundled M390 work is a complete, coherent fold-in feature (relation + binding + casillas + construct + manifest + dependency + test), intact in history; not reverted. Residual: it rode in without its own review (recorded).
- The `single-subject-mutation-is-idempotent-guarded` codification candidate remains flagged for post-cycle promotion only; do not promote this cycle.
- Two peer-attributed failures observed during the sweep are now BOTH RESOLVED: (1) the five `test_file_flow_filing.py` failures — the M714 campaign self-resolved its untracked invalid verification expectation (replaced with a valid `0003-reconcile-when-present.toml`); the filing tests pass. (2) `test_no_parallel_work_unit_storage_namespace` — the custody campaign's `_bundle.py` / `_custody_carry.py` name the work_units namespace only in a coverage manifest (not shadow storage; the carry writes via `repository.save(namespace=carried.namespace, ...)`); FIXED under operator direction in `7d6887245` by allowlisting the two coverage-manifest files in the gate, alongside the existing `_namespace_registry.py` allowlist. Verified: the previously-red filing tests + custody gate now pass (12 passed).
- Shared-worktree note: the locale surface was under continuous multi-campaign churn throughout close; the `tr` promotion was landed via a temporary-index `commit-tree` specifically to avoid sweeping peer locale WIP. No destructive git ran and no peer work was swept at any point.
