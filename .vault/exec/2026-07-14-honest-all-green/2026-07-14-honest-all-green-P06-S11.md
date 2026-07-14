---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S11'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace honest-all-green with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-07-14-honest-all-green-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Run the full suite to genuinely green in parallel and sequential modes and record the closing evidence and ## Scope

- `full-tree gates` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the full suite to genuinely green in parallel and sequential modes and record the closing evidence

## Scope

- `full-tree gates`

## Description

- Ran collect-only over the full tree: clean, 12909 collected, no collection
  errors.
- Ran the full `src/cadrumo -n auto` suite captured to an untruncated on-disk
  log (background-capture rule, no truncating pipe): 10 failed, 12893 passed in
  11m23s.
- Sequentially re-ran every failure (`-n 0`) to separate parallel/concurrency
  artifacts from real failures, and gathered git evidence (uncommitted-WIP
  count + recent-commit recency) for each residual to classify owner.

## Outcome

Full parallel run: 10 failed / 12893 passed. Collect-only clean. Sequential
re-run + git-evidence triage:

| Failure | -n 0 result | Owner / disposition |
| --- | --- | --- |
| `tests/test_codebase_size_budgets.py::...line_budgets` | PASSES | Concurrency-read artifact: a peer editing a budgeted file mid-parallel-run tripped the read; my `_loader.py` re-pins (1445) hold at HEAD. Campaign-owned == 0. |
| `tests/test_import_hygiene_gate.py::...underscore_reaches...` | PASSES | Parallel-sensitive baseline scan (documented; passes `-n 0`). |
| `tests/test_cross_module_imports_resolve.py::...against_baseline` | PASSES | Parallel-sensitive baseline scan (passes `-n 0`). |
| `tests/test_cast_rationale_inventory.py::...rationale_marker` | PASSES | Concurrency-read artifact (static source scan raced a peer edit; passes `-n 0`). |
| `core/tests/test_period_combined_string_gate.py::...combined_period_strings` | FAILS | LIVE peer WIP: docs-cli-sequences. Offenders are `docs/_sequences/how-to/**/*.json:111` work-unit `name` frames (`303-2026-1T` / `130-2026-1T`). 9 uncommitted `docs/_sequences` files; the campaign is landing continuously at HEAD (`c28d1da31e`, `ef7bf43101`, `2036801707`, `01ee8d2b93`). |
| `tests/test_parity.py::test_codebase_to_locale_parity` | FAILS | LIVE peer campaign: the known 26-orphan-key locale drift (all four catalogues carry 26 keys no codebase `tr()` references, from the committed CLI underscore rename whose locale cleanup is pending). Active locale campaign (commits 88 min / 2 h ago). On the coordinator's watch-list. |
| `locales/tests/test_audit.py::...pass_production_audit` | FAILS | LIVE peer campaign: the active locale-identity campaign (`7725c3c7cb`, `829e0f571d`, `d0a88fc329` correcting Catalan/Hungarian identity contexts). |
| `locales/tests/test_audit.py::...contextual_product_identity_contract` | FAILS | LIVE peer campaign: same locale-identity surface. |
| `adapters/inbound/justificante/tests/test_parser.py::...test_corpus_pdf_parses[202/2025-1P]` | FIXED | Campaign fallout (S08), now green -- commit `1bef3269c8` (see below). |
| `adapters/inbound/justificante/tests/test_corpus_sidecar_roundtrip.py::...[-34]` | FIXED | Same root cause; fixed together in `1bef3269c8`. |

Campaign-owned (P01 + P05) failures: ZERO. Every P01/P05 surface is green
sequentially; the four `-n auto`-only artifacts pass `-n 0`; the four
locale/docs failures are live in-flight peer campaigns on the coordinator's
watch-list.

The two Modelo 202 justificante corpus tests were OUR OWN campaign's fallout,
not pre-existing: the S08 fixture pass (commit `710217daf6`) correctly
re-sanitised the M202 fixture's tax_id from a personal NIE to a CIF-shaped
`B00000001` (Modelo 202 is Impuesto sobre Sociedades; a sociedad files with a
CIF -- the correction was right) and regenerated the fixture + sidecar, but
missed the two corpus tests' blanket `Y0000001S` assertion
(`test_parser.py:213` and `test_corpus_sidecar_roundtrip.py`'s
`_SYNTHETIC_TAX_ID`). Fixed per the coordinator's direction (a), commit
`1bef3269c8`: both tests now derive the expected tax_id per-fixture from the
fixture-provenance sidecar (the authoritative declaration) -- the sole DISTINCT
tax-id-shaped synthetic token, deduped across the repeated substitution surfaces
-- and assert exact equality against it (not merely "some string"). Docstrings
updated. Full justificante suite green (159 passed).

## Notes

- CAMPAIGN-OWNED FAILURES: ZERO (including the M202 corpus tests, now fixed in
  `1bef3269c8`). The three remaining reds each have an active owner + evidence
  (docs-cli-sequences period gate; locale parity/identity). The four
  `-n auto`-only artifacts pass `-n 0`.
- Honest reading of the goal per the coordinator: everything within reach is
  green; the residual reds are live in-flight peer campaigns with documented
  evidence, not campaign misses. A confirmation re-run after those campaigns
  land is welcome but does not block this close.
- No destructive git; explicit-pathspec commits throughout; the full-suite log
  is retained at the session scratchpad (`s11_full.log`) for signature
  verification.
