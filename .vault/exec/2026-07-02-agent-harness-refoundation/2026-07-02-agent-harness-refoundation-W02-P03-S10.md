---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

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
