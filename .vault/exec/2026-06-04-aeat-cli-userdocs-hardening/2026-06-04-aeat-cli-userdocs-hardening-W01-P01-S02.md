---
tags:
  - '#exec'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S02'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---

# `aeat-cli-userdocs-hardening` `W01.P01.S02` execution

Scope: Inventory narrative docs by Diataxis type and map each page to the operator journey it currently supports.

## Description

Generated API pages under `docs/api/`, inventory files under `docs/_inventories/`, and ignored generated CLI reference pages under `docs/cli/` were excluded from the narrative handbook inventory. The user-facing narrative corpus currently consists of 20 markdown pages.

## Inventory

| Page | Current Diataxis role | Journey supported | Hardening note |
| --- | --- | --- | --- |
| `docs/index.md` | Landing route / reference hub | Choose a path, understand safety boundary, get help | Already has path choices, but must become more task-first for setup, ledger, modelo filing, troubleshooting, and generated reference. |
| `docs/getting-started.md` | Tutorial mixed with how-to/reference | First profile through first exported modelo file | Skips ledger readiness depth and treats manual `--casilla`/`--binding` as a note instead of an operational path. |
| `docs/tutorials/index.md` | Tutorial | Example Modelo 130 journey | Useful sequence, but uses example values and manual inputs without enough guardrails for real operators. |
| `docs/how-to/quickstart.md` | How-to | Produce a modelo file quickly | Needs stronger prerequisites and clearer link-out to profile, ledger, verification, and filing handoff pages. |
| `docs/how-to/profile-setup.md` | How-to | Create, switch, and manage profiles | Needs plain-language profile facts and impact on modelo applicability. |
| `docs/how-to/censo-update.md` | How-to | Sync AEAT census facts into a profile | Needs stronger enrolment framing and live-read gate explanation. |
| `docs/how-to/import-bank-statements.md` | How-to | Import, classify, and preflight ledger rows | Covers core loop partly; needs list/view/fix/status/evidence/manual-entry coverage. |
| `docs/how-to/classify-with-llm.md` | How-to | Classify a transaction with LLM assistance | Narrow and useful, but belongs under ledger readiness and should not distract first-time filing readers. |
| `docs/how-to/filing-spine.md` | How-to mixed with reference | Standard create/calculate/verify/file/export/history loop | Needs clearer distinction between work-unit id and calculation-revision id and stricter internal-filed language. |
| `docs/how-to/modelo-303.md` | Model-specific how-to | Quarterly IVA Modelo 303 | Needs link-out to general lifecycle and manual-value pages rather than repeating fragile snippets. |
| `docs/how-to/modelo-390.md` | Model-specific how-to | Annual IVA summary Modelo 390 | Needs link-out to lifecycle, ledger, and verification pages. |
| `docs/how-to/filing-calendar.md` | How-to mixed with explanation | Decide what applies and when | Good candidate for "which modelo should I file?" but must stay task-first. |
| `docs/how-to/reconcile.md` | How-to | Compare local filing record with justificante | Needs expanded advice for divergent casillas and evidence retention. |
| `docs/how-to/troubleshooting.md` | Troubleshooting how-to/reference | Diagnose local setup and workflow errors | Currently starts from system diagnostics; needs symptom-first operator language. |
| `docs/how-to/index.md` | Mixed index, explanation, and reference | Browse recipes | Needs split into an index plus focused recipes. |
| `docs/explanation/index.md` | Explanation | Understand pipeline, safety boundary, provenance | Strong conceptual anchor; should link to concrete recipes and avoid carrying operational steps. |
| `docs/glossary.md` | Reference | Define tax/application vocabulary | Important for first-use terms; should be reachable from first-use-heavy pages. |
| `docs/disclaimer.md` | Safety/legal reference | Understand responsibility and non-filing boundary | Must remain visible but not substitute for operational warnings in workflow pages. |
| `docs/architecture.md` | Developer explanation | Understand layers and registry authority | Not primary operator material; useful as project/reference background. |
| `docs/authoring-guide.md` | Maintainer how-to/reference | Keep docs aligned with code | Not operator material; useful for future documentation contributors. |

## Outcome

Completed. The narrative corpus is mapped by page, current Diataxis role, and operator journey. The inventory confirms the same mitigation direction as the reader review: split mixed pages, move fragile command restatement into generated reference links, and create missing operational pages for profile/censo, ledger readiness, manual values, verification, filing handoff, and troubleshooting.
