---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S10'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace agent-harness-refoundation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-07-02-agent-harness-refoundation-plan placeholders are machine-filled by
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
     The Add aeat skill, rule, and persona resource templates with a read handler and ## Scope

- `src/aeat/entrypoints/mcp/_resources.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add aeat skill, rule, and persona resource templates with a read handler

## Scope

- `src/aeat/entrypoints/mcp/_resources.py`

## Description

- Add `src/aeat/entrypoints/mcp/_resources.py`, an SDK-independent module over typed pydantic models.
- Define `HarnessResourceKind` StrEnum (`skill`/`rule`/`persona`) matching the URI authority segment.
- Define `HarnessResourceRef` (list rows, no body), `HarnessResourceTemplate` (RFC 6570 template rows), and `HarnessResourceContent` (read payload).
- Add `list_harness_resources()` enumerating one concrete resource per shipped skill, operator rule, and persona, derived through the `aeat.agent` facade (`iter_skill_documents`, `iter_operator_rules`, `iter_personas`), kind-then-name ordered.
- Add `list_harness_resource_templates()` returning the three `aeat://<kind>/{name}` templates.
- Add `read_harness_resource(uri)` parsing `aeat://<kind>/<name>`, resolving to the shipped document text, and raising `HarnessResourceNotFoundError` on a wrong scheme, unknown kind, missing name, or unknown document.

## Outcome

Resource pull channel complete and standalone-importable. Smoke check: 34 skills + 7 rules + 7 personas = 48 concrete resources; three templates; reads resolve a skill, a rule, and a persona verbatim; malformed and unknown URIs (`aeat://skill/nope`, `aeat://bogus/x`, `http://x/y`, `aeat://skill/`) all refuse cleanly. Ruff, ruff-format, pyright clean. Server wiring in S11, tests in S12.

## Notes

The prompt module's embedded `aeat://rule/operating-rules` bundle URI is a distinct notion (the concatenation of all rule files) and is out of this resource surface's scope: this surface enumerates the individual rule files by stem. The prompt embeds its rules text inline, so that URI needs no resource resolution.
