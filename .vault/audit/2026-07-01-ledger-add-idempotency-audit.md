---
tags:
  - '#audit'
  - '#ledger-add-idempotency'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ledger-add-idempotency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ledger-add-idempotency` audit: `ledger-add-idempotency close honesty review`

## Scope

Fresh-context independent code review (dispatched to a dedicated reviewer persona) over the 16 feature commits of `ledger-add-idempotency`, run as the campaign-close honesty-review gate before declaring the pipeline complete. Reviewed: the manual `ledger add` guarded-idempotent keyed no-op + conflict refusal, the `modelo verify` content-pinned report id, and the `modelo file` content-pinned filing-record id + idempotent re-file. Verdict: PASS / GO, no CRITICAL, no HIGH; core safety and correctness hold.

## Findings

### idempotency-guard-field-omission | medium | same-key add differing only in recargo_amount/source_jurisdiction silently no-ops (fixed)

`_command_matches_current` (`src/aeat/application/ledger/_actions_common.py`), reused by the manual-add idempotency conflict gate, omitted `recargo_amount` and `source_jurisdiction`. A same-key add differing only in those fields silently no-oped and dropped the new value — a silent under-declaration of the recargo de equivalencia surcharge. FIXED in `bdd141a59`: both fields added to the match, with two regression tests proving each difference now raises the conflict refusal.

### filing-anti-tautology-not-load-bearing | medium | filing-record id-mismatch proof passed for the wrong reason (fixed)

The filing-record anti-tautology test seeded `revision_id` with an invalid-hex value, so the `CalculationRevisionId` field pattern raised during field validation before the outcome-pinned id model_validator ran — the mandated proof was not load-bearing. FIXED in `ce1f79e38`: a valid, distinct hex seed makes the model_validator's id-mismatch check the raising path.

### f5bd349a5-scope-bleed | medium | provider-id fix commit bundled unrelated M390 registry work (deferred, not reverted)

Commit `f5bd349a5` (the P01.S01 provider-id lookup fix) also bundled unrelated Modelo 390 registry TOML plus a 253-line M390 fold-in test — a scope-bleed / peer-WIP capture into an atomic ledger commit. The M390 work is preserved in history; reverting would destroy it and is entangled with the ledger fix. Documented and surfaced for the M390 campaign to confirm rather than unwound.

### s22-inline-notice-message | low | modelo-file no-op Notice uses an inline string, not a tr() key (acceptable; follow-up)

The S22 modelo-file no-op Notice uses an inline message string rather than a `tr()` locale key — a deliberate choice to avoid concurrent locale-catalogue contention. It is still a properly typed `Notice` (info severity, code, context), does not violate `cli-notices-are-the-only-diagnostic-channel`, and mirrors the adjacent hardcoded `filing_disambiguation` line. Acceptable as committed; promote to a `tr` key once the locale surface settles, for parity with the localized ledger-add no-op.

### s16-roundtrip-strength | low | Transaction roundtrip is survives-reload, not strict-equality + on-disk-mutation (follow-up)

P05.S16's "strict Transaction roundtrip + anti-tautology" is only partially satisfied: it is a survives-reload check rather than a strict `model_a == model_b` equality plus an on-disk-mutation anti-tautology proof. Strengthen in a follow-up.

## Recommendations

- The two MEDIUM in-scope findings are FIXED and re-verified (idempotency suite 13 passed, filing roundtrip suite 15 passed). No further action.
- MEDIUM-3 (`f5bd349a5` scope bleed): confirm with the M390 campaign that the bundled registry work is intact and got its own review; do not revert.
- Track the two LOW items as follow-ups: promote the S22 inline Notice to a `tr` key; strengthen the S16 Transaction roundtrip to strict equality + anti-tautology.
- The `single-subject-mutation-is-idempotent-guarded` codification candidate remains flagged for post-cycle promotion only; do not promote this cycle.
- Owner-attributed S19 non-feature failure: `test_no_parallel_work_unit_storage_namespace` trips on the custody campaign's `application/user_profile/_bundle.py` and `_custody_carry.py` referencing the work_units namespace — surface to that campaign; out of scope for this feature.
