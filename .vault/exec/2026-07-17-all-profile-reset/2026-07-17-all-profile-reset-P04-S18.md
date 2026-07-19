---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S18'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace all-profile-reset with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-07-17-all-profile-reset-plan placeholders are machine-filled by
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
     The Restrict config switch to UUIDs and exact labels including canonical sandbox labels and reject bare sandbox names and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Restrict config switch to UUIDs and exact labels including canonical sandbox labels and reject bare sandbox names

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py`

## Description

- Add `_resolve_switch_target` to `_custody.py`: resolve a `switch` target from an unambiguous UUID (`read_profile_bucket_by_id`, excluding tombstoned) or fall back to the injected exact-label resolver.
- Route `config_switch` through the new resolver so `switch` accepts a bucket UUID, an exact operator label, and a sandbox's canonical `sandbox:<name>` label, while a bare sandbox short name refuses as an unknown profile (the sandbox namespace check the removed `sandbox use` door performed).

## Outcome

`config switch NAME` is the single accepted profile selector per ADR `cli-authority-verb-conformance` Decision 3: it resolves a live UUID directly, refuses a tombstoned UUID and a bare sandbox short name through the label resolver, and preserves the typed ambiguity refusal. Proven by the sandbox CLI suite (44 passed) including the new UUID-switch and bare-name-rejection tests co-committed with S22.

## Notes

Bare-name rejection was already implied by label-only resolution; the load-bearing new capability is UUID resolution. The shared `_resolve_profile_by_label` (delete/duplicate/rename) is deliberately left label-only — the ADR narrows only `switch`.
