---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:024b552f04b2206f3e225f4946ab7d93da12fe8931d05d984b8455b5d150f804'
step_id: 'S32'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Land the bounded-fstring coverage gate, every dynamic tr or copy-reference site over an enum must carry its registry registration in the same commit, with the three campaign incidents as its seed cases

## Scope

- `src/cadrumo/locales/tests/`

## Description

- Land the dynamic-prefix registry coverage gate in `test_dynamic_prefix_registry_coverage.py`: every dynamic `tr()` or copy-reference namespace must be either registered as a bounded f-string pattern or explicitly enrolled in the open-ended-namespace allowlist with a stated reason.
- Extend the AST scanner to collect `ValidationVerdict.failed` positional key literals so verdict keys built at call sites survive scaffold.
- Add the placeholder self-echo gate repo-wide: a scaffolded locale entry whose value merely echoes its key fails until translated or registered.
- Add the language-override site inventory: the sanctioned override sites are pinned by exact equality, with the context-scoped sites verified to route through the resource-scoped override helper; nested-function attribution fixed to the innermost function.
- Register the status-page profile lifecycle labels as a bounded f-string pattern over the profile status enum.

## Outcome

Landed across the gate commits ending at `a8bdfd054f` (pushed together with the peer's dedup deletion). The three campaign key-strip incidents are the gate's seed cases: a constructed key invisible to the scanner now fails the gate in the same commit that introduces it, instead of being silently stripped by the next scaffold.

## Notes

- The first remediation attempt (a dynamic scanner root) was inert and its validation vacuous because it ran against the already-stripped catalogue; the landed gate family validates against declared registrations, never against damaged state.
