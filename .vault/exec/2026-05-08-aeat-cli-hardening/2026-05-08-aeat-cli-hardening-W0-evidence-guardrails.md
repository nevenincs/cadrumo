---
tags:
  - '#exec'
  - '#aeat-cli-hardening'
date: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
  - '[[2026-05-08-aeat-cli-gap-discovery-audit]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `aeat-cli-hardening` `W0 Evidence And Guardrails`

W0 established the rollout control plane before application code changes.

- Created: `2026-05-08-aeat-cli-gap-discovery-audit.md`
- Created: `2026-05-08-aeat-cli-hardening-W0-evidence-guardrails.md`

## Description

The 2026-05-08 CLI audit was not present as a vault audit artifact. A compact
audit record was created to anchor the root cause, surface classes, issue ids,
and action ids that drive the implementation plan.

The working tree is already dirty with unrelated team changes. The unrelated
state includes deleted root vault index files, added replacement vault index
files, AEAT browser and sede adapter edits, registry calculation test edits,
financial CLI test edits, a modified `uv.lock`, and new corpus and registry
scenario files. This rollout must not revert or stage those paths.

Owned W0 files are limited to the CLI hardening audit and execution artifacts.
Future implementation slices must stage explicit path lists only.

## Tests

Validation is documentation/control-plane validation for W0:

- confirmed the plan exists and includes `UX-001` through `UX-017`;
- confirmed the action ledger includes `A1` through `A36`;
- confirmed discovered surfaces are represented in the plan;
- confirmed no destructive git command is required for the rollout.

No application tests were run for W0 because no application code changed.
