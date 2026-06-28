---
tags:
  - '#exec'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S08'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---

# `aeat-cli-userdocs-hardening` `W02.P03.S08` execution

Scope: Rewrite the userdocs landing route so non-technical readers can choose setup, ledger, modelo filing, troubleshooting, or reference without understanding the architecture first.

## Description

Rewrote `docs/index.md` around task-first routing:

- start from nothing;
- create or check a taxpayer profile;
- sync censo facts;
- make the ledger ready;
- choose what to file;
- produce a modelo file;
- find model-specific recipes;
- record censo lifecycle changes as a known missing guide;
- reconcile after filing;
- troubleshoot;
- browse all task guides;
- look up details in CLI reference, glossary, and explanation pages.

The long legal disclaimer was moved below the task route while keeping an up-front safety note that `aeat` never submits to the AEAT.

## Outcome

Completed. A non-technical editorial reviewer initially found the page too safety-first and noted weak M036/ledger manual-surface visibility. The patch was revised, and the reviewer then reported no blockers for closing this step.
