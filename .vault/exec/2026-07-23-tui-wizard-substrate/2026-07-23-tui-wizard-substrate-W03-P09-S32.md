---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S32'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S32 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Land the bounded-fstring coverage gate, every dynamic tr or copy-reference site over an enum must carry its registry registration in the same commit, with the three campaign incidents as its seed cases and ## Scope

- `src/cadrumo/locales/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Land the bounded-fstring coverage gate, every dynamic tr or copy-reference site over an enum must carry its registry registration in the same commit, with the three campaign incidents as its seed cases

## Scope

- `src/cadrumo/locales/tests/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Land the dynamic-prefix registry coverage gate in `test_dynamic_prefix_registry_coverage.py`: every dynamic `tr()` or copy-reference namespace must be either registered as a bounded f-string pattern or explicitly enrolled in the open-ended-namespace allowlist with a stated reason.
- Extend the AST scanner to collect `ValidationVerdict.failed` positional key literals so verdict keys built at call sites survive scaffold.
- Add the placeholder self-echo gate repo-wide: a scaffolded locale entry whose value merely echoes its key fails until translated or registered.
- Add the language-override site inventory: the sanctioned override sites are pinned by exact equality, with the context-scoped sites verified to route through the resource-scoped override helper; nested-function attribution fixed to the innermost function.
- Register the status-page profile lifecycle labels as a bounded f-string pattern over the profile status enum.

## Outcome

Landed across the gate commits ending at `a8bdfd054f` (pushed together with the peer's dedup deletion). The three campaign key-strip incidents are the gate's seed cases: a constructed key invisible to the scanner now fails the gate in the same commit that introduces it, instead of being silently stripped by the next scaffold.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The first remediation attempt (a dynamic scanner root) was inert and its validation vacuous because it ran against the already-stripped catalogue; the landed gate family validates against declared registrations, never against damaged state.
