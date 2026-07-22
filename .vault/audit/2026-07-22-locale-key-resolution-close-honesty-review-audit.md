---
tags:
  - '#audit'
  - '#locale-key-resolution'
date: '2026-07-22'
modified: '2026-07-22'
related:
  - "[[2026-07-21-locale-key-resolution-adr]]"
  - "[[2026-07-21-locale-key-resolution-research]]"
---

# `locale-key-resolution` audit: `campaign close honesty review`

## Scope

Campaign close honesty review for the locale-key-resolution campaign, mandated by the
`aeat-campaign-close-honesty-review` rule before any structural-completeness
declaration. The review was performed by an independent read-only reviewer
(locale-architect) with adversarial re-verification of the campaign's closure claims;
this document persists that output. Reviewed surfaces: the four locale catalogues, the
strict missing-key mode, the resolution gate, the allowlist, the LLM classifier hint
path, and the campaign's own reported numbers.

**Verdict: the campaign is NOT structurally complete and must not be declared
closed.** One critical finding (S1) shows the campaign reduced the defect's
visibility on the production classifier path; two high findings remain open (S4, S5).

## Findings

### classifier-fallback-masking | critical | the campaign reduced the defect's visibility on the LLM hint path

S1. `_category_hint` (`src/cadrumo/domain/transactions/_llm.py`) is pinned to
`locale='es'` per the ADR, and Spanish is 0/86 authored. The classifier therefore
receives `'Cuotas colegiales — [full_deductible] — Notes'`, where `Notes` is the
humanize fallback of `categories.registry.cuotas_colegiales.notes`. Before the
campaign the same call site read the raw dotted key — self-evidently broken on sight.
Now it looks like content and passes review, and production does not run strict mode,
so nothing catches it. The campaign reproduced its own thesis against itself: a
plausible fallback masking absent work. Verified directly by the reviewer.

### authoring-sequenced-backwards | high | Spanish, the only locale a consumer reads, was authored last

S2. Spanish stood at 0/86 while Hungarian led at 44/86, even though the pinned
classifier hint is the one production consumer of these strings and it reads only
`es`. Re-sequenced since the review; recorded for the pattern.

### unrepresentable-label-keys | high | 30 of 86 keys were structurally impossible to materialise (fixed)

S3. Only 56 of 86 keys had materialised, leaving `test_codebase_to_locale_parity` RED
with `missing=30`. Root cause (found by accent-hu, verified by the reviewer): 30 of
the 41 `display_label` keys used the same dotted path as their own `.notes` child, so
a catalogue would have needed one YAML node to be simultaneously a scalar leaf and a
parent mapping. Unrepresentable — the keys were not untranslated, they were
impossible. The 11 that worked avoided the collision only by accident (label and
notes happening to use different category stems). Fixed in commit `f74064443e` by
suffixing the 30 with `.label`; all 86 now materialise, `missing=0`, parity gate
green.

### catalogue-honesty-net-negative | high | key-echo placeholder count rose from 64 to 154 (open)

S4. Catalogue honesty went NET NEGATIVE over the campaign: key-echo values (leaf value
identical to its own dotted key) rose from 64 to 154 across the four catalogues,
because scaffold inserted placeholders while the key-echo assertion that would detect
them was never built. `src/cadrumo/tests/test_locale_translation_honesty.py` still
loops `("ca","hu")` only and still asks only "identical to English?", never
"identical to its own key?". Open.

### es-allowlist-enforces-nothing | medium | 45 es allowlist entries carry no gate (open)

S5. 45 `es` entries exist in `_intentional_identical.json` while the honesty gate does
not scan `es`, so the entries enforce nothing. Either extend the gate to `es` or stop
accruing entries that imply a guarantee that does not exist. Open.

### gate-count-was-moving-snapshot | medium | the "exactly 344 failed, 6 passed" claim was inferred, not asserted

S6. The closure claim "exactly 344 failed, 6 passed" was a moving snapshot whose
composition was inferred from a count rather than asserted: runs minutes apart gave
344/6 then 311/39. Inferring gate composition from arithmetic is precisely how the
earlier membership false-green survived.

### accent-residual-unverified | low | the ~177 accent-residual figure could not be independently confirmed

S7. The reviewer could not independently reproduce the ~177 accent-residual figure.
Recorded as unverified, not as confirmed.

### claims-surviving-adversarial-verification | low | the campaign's real output, re-verified

The following closure claims SURVIVED adversarial verification and stand as the
campaign's real output: the resolution-based gate is sound (commit `ddf73d5836`);
strict missing-key mode genuinely fires — proven directly on both the unknown-key and
key-echo paths, with the explicit-`default` opt-out working and the production
fallback intact; the 81-quote carve-out holds, with zero `.quote` keys leaked into any
catalogue; `allow-identical` is not a mute button (reasons sampled and found
legitimate); Hungarian accent drift independently probed at 0; and
`_intentional_identical.json` sustained no concurrency damage despite three concurrent
writers.

## Recommendations

Required before the campaign may be declared structurally complete, each tied to its
finding:

- (S1, S2) Author the `es` catalogue first — it is the only locale the production
  classifier hint reads, and until it is authored the campaign's own masking finding
  applies to itself.
- (S3) The 30-key materialisation fix has landed (`f74064443e`); verify it stays green
  at closure.
- (S4) Build the key-echo assertion (leaf value == its own dotted key is a failure)
  across ALL FOUR catalogues, so scaffold placeholders can no longer pass as content.
- (S5) Decide whether the honesty gate scans `es`; a follow-on decision must either
  extend the gate or halt `es` allowlist accrual. If architecturally significant,
  route through an ADR amendment.
- (S6) Assert the resolution gate's composition directly (which keys are red and why),
  never by count arithmetic.

Still open beyond this review's scope, tracked so closure cannot silently absorb
them: 51 casillas blocked by the fragmented-locale CLI gap (M200 22, M100 29, 306
leaf entries); the 81 AEAT citation quotes awaiting evidence sourcing with a legal
reviewer (per the ADR's binding carve-out); the non-atomic `_write_translation_path`
(`src/cadrumo/locales/_modelo_manager.py:529`); and M100 revisions 2020-2023 deferred
by operator decision (6,005 casillas).
