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
| `adapters/inbound/justificante/tests/test_parser.py::...test_corpus_pdf_parses[202/2025-1P]` | FAILS | NOT live peer WIP -> REPORTED. Pre-existing test defect (see below). |
| `adapters/inbound/justificante/tests/test_corpus_sidecar_roundtrip.py::...[-34]` | FAILS | NOT live peer WIP -> REPORTED. Same root cause (the 202/2025-1P M202 fixture). |

Campaign-owned (P01 + P05) failures: ZERO. Every P01/P05 surface is green
sequentially; the four `-n auto`-only artifacts pass `-n 0`; the four
locale/docs failures are live in-flight peer campaigns on the coordinator's
watch-list.

ONE residual is NOT explainable as live peer WIP and is surfaced for
adjudication (not triaged away): the two Modelo 202 justificante corpus tests.
`test_parser.py:213` blanket-asserts `record.tax_id == "Y0000001S"` (a redacted
NIE) for EVERY corpus fixture, but the `202/2025-1P` fixture parses to
`B00000001` -- and its sidecar declares `"synthetic": "B00000001"`, i.e. the
sanitiser DELIBERATELY wrote that value: Modelo 202 is Impuesto sobre Sociedades,
whose filer is a sociedad with a CIF (`B00000001`), not an individual's NIE. The
test's blanket individual-NIE assertion does not accommodate corporate modelos,
and its docstring already says "Redacted NIE/NIF survives the round-trip"
(acknowledging both) -- an oversight, not a convention. The fixture and the
assertion are both only rename-touched (2 days ago); no active M202 or
justificante-corpus campaign. Candidate fixes: (a) derive the expected tax_id
per-fixture from the sidecar's declared `synthetic` value rather than hardcoding
one, or (b) regenerate the 202 fixture to the uniform redacted NIE if the corpus
convention is a single placeholder. Direction (a) matches the docstring intent;
reported to the coordinator rather than guessing the corpus convention.

## Notes

- No campaign-owned regressions. The genuine (non-WIP) residual is the M202
  justificante corpus tests -- a pre-existing test-vs-fixture mismatch on a
  surface with no active owner, surfaced above for adjudication per the
  "fix it or report it" bar. Everything else is either a live in-flight peer
  campaign (docs-cli-sequences, locale identity/parity -- on the watch-list) or
  an `-n auto`-only concurrency/parallel artifact that passes `-n 0`.
- No destructive git; the full-suite log is retained at the session scratchpad
  (`s11_full.log`) for signature verification.
