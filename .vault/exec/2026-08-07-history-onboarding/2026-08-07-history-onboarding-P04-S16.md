---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:1564efdf9e3b3d97ed69da83d3babe1cd252c014693e04675a813d297c617aa8'
step_id: 'S16'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace history-onboarding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
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
     The update the agent-harness docs under src/cadrumo/_data/agent that name the filed verb group to cite the new discover and pull-all verbs, verified by the harness-citation conformance check confirming every named verb resolves against the live operator-surface manifest and ## Scope

- `src/cadrumo/_data/agent` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# update the agent-harness docs under src/cadrumo/_data/agent that name the filed verb group to cite the new discover and pull-all verbs, verified by the harness-citation conformance check confirming every named verb resolves against the live operator-surface manifest

## Scope

- `src/cadrumo/_data/agent`

## Description

- Cite `discover` and `pull-all` in the agent-harness routing rule that names the filed verb group.

## Outcome

The rule states the two things an agent reading the report would otherwise get
wrong, rather than only naming the verbs: there is no completeness percentage,
because part of the walked grid comes from an option list whose NIF-scoping is
unconfirmed; and a pair marked REFUSED is not a pair with no filings, so the
answer is to re-run rather than to conclude nothing was filed.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/ src/cadrumo/application/overview/tests/ \
      src/cadrumo/entrypoints/cli/tests/test_app_live_filed_discover.py \
      src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py \
      src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py \
      src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py \
      src/cadrumo/agent/tests/test_rule_surface_conformance.py -q -n0 -m "unit or integration"
    1147 passed, 2 deselected in 155.20s (0:02:35)

## Notes

The row named "the agent-harness docs" plural. Exactly one harness document names
the filed verb group — the operator orientation routing rule; the safety handoff
rule names only the `aeat app live` tree as read-only, which stays true and needed
no edit. Verified by searching the whole harness tree for citations rather than
assuming the plural.
