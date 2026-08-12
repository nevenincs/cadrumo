---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:94bfdccb4d9456600ff3820079595ea0ae2184afdb5b0ce9036341f2bfcd6400'
step_id: 'S58'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# W04.P07.S58 Step Record

## Scope

- Domain filing-evidence and calculation-revision types, including revision content integrity and amendment lineage.
- Application model lifecycle and canonical typed producer/consumer bindings.
- Formula runtime and annual Orden resolution, including refusal when governing authority is unavailable.
- Persistence, import, export, and quickfile evidence propagation.
- Prorrata calculation scope and semantic absence handling.
- CLI annotations, localized operator messages, and direct real-behavior tests.
- S58 lifecycle audit, this execution record, and the governing plan step state.

## Description

Establish immutable M303 filing-instance evidence at revision creation and make calculation revision-aware, deleting the legacy compatibility surfaces the change replaces rather than bridging them.

## Outcome

Completed. The approved candidate establishes immutable filing evidence and revision-aware calculation authority while deleting legacy compatibility surfaces.

## Validation

- Engine, Orden, formula, and amendment lane: **73 passed**.
- Evidence, import, export, prorrata, and legacy-removal lane: **156 passed**, plus **one unchanged translated-message assertion** verified separately.
- Exact quickfile help and integration lane: **2 passed**.
- Focused core `basedpyright`: **0 errors, 0 warnings**.
- Ruff, `compileall`, and `git diff --check`: clean.
- AST call census and retired-surface scans: clean.

## Incidents and resolutions

- Revision content integrity initially omitted filing evidence; the canonical revision content now carries and validates it.
- A derive-helper default and its `123` call sites diverged; callers were migrated to the explicit typed contract and the obsolete default removed.
- Annual Orden selection could continue without resolved authority; it now refuses the pending/unresolved state.
- A Typer-decorated `RevisionId` annotation crossed the CLI boundary incorrectly; the CLI binding now uses the supported boundary type and converts into the domain identifier.
- Quickfile did not thread filing evidence consistently, and a bienes migration return was misused; both consumers now follow the canonical lifecycle result.
- Prorrata staged scope and Orden selection had drifted, including blanket `None` semantics; the implementation now distinguishes canonical absence from required values.
- Bounded RAG found the governing documents but its code endpoint was stale against approved v9; source grounding therefore used the approved candidate tree and reviewer evidence.
- Four prorrata-especial advisory-emission failures and one parent-only M390 carry-disposition failure were excluded as pre-existing baseline failures and remain unverified by the reviewer.

## Closure

Reviewer verdict: **APPROVE**. No superseded PASS counts or legacy-support claims are carried forward.

## Notes

This step was executed on one machine only; the parallel campaign on the diverged history did not re-execute it, so its record needed no reconciliation. Its consumers did: `S55` and `S56` both consume this step's evidence-reference contract, and both were executed twice and reconciled. The `filing_instance_evidence` contract this step established was subsequently tightened during that reconciliation - the field and the revision-id derivation both dropped their defaults after measurement showed 90 of 95 constructors already supplied it explicitly, and a tree-wide AST gate now enforces it.

The excluded baseline failures recorded above remain open and are not closed by this record.
