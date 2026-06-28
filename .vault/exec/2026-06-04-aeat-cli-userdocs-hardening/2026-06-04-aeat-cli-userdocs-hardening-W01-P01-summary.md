---
tags:
  - '#exec'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---

# `aeat-cli-userdocs-hardening` `W01.P01` summary

Completed the scope and corpus inventory phase for the AEAT CLI user documentation hardening plan.

- Created: `.vault/plan/2026-06-04-aeat-cli-userdocs-hardening-plan.md`
- Created: `.vault/exec/2026-06-04-aeat-cli-userdocs-hardening/2026-06-04-aeat-cli-userdocs-hardening-W01-P01-S01.md`
- Created: `.vault/exec/2026-06-04-aeat-cli-userdocs-hardening/2026-06-04-aeat-cli-userdocs-hardening-W01-P01-S02.md`
- Created: `.vault/exec/2026-06-04-aeat-cli-userdocs-hardening/2026-06-04-aeat-cli-userdocs-hardening-W01-P01-S03.md`
- Created: `.vault/exec/2026-06-04-aeat-cli-userdocs-hardening/2026-06-04-aeat-cli-userdocs-hardening-W01-P01-S04.md`

## Description

The phase established the audit surface before any rewrite: narrative handbook pages, generated CLI reference state, live CLI leaf paths, and help-language behavior.

The narrative inventory identified 20 markdown pages in the operator/handbook corpus, excluding generated API reference, generated inventories, and ignored generated CLI reference output. The current corpus mixes Diataxis roles in several places: first-run tutorial material, broad how-to indexes, model-specific recipes, explanation pages, glossary/reference material, and maintainer/developer docs.

The live CLI audit confirmed 193 leaf commands and captured the known drift between live help and the previously observed generated reference. The help-language audit captured that runtime `--language en` is not consistently enough documented or behaving clearly enough for examples to be trusted without a separate locale mitigation.

## Outcome

Completed. W01.P01 now provides the documentation scope, narrative corpus map, CLI reference drift evidence, and localization drift evidence needed by later rewrite waves.
