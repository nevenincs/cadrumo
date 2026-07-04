---
tags:
  - '#adr'
  - '#review-workflow-cycle-break'
date: '2026-07-03'
modified: '2026-07-03'
related:
  - "[[2026-07-01-import-centralization-adr]]"
  - "[[2026-07-02-import-centralization-audit]]"
  - "[[2026-07-01-import-centralization-research]]"
---

# `review-workflow-cycle-break` adr: `review-workflow cycle break structural fix` | (**status:** `accepted`)

## Problem Statement

The `import-centralization` campaign closed with 5 documented, pinned production
Family-1 cross-package private-import sites: `application.review` and
`application.workflow` imported each other's private `_models` / `_utils`
submodules at runtime because `WorkflowEvent`, `utc_now`, `InvoiceReviewRecord`,
and `LedgerReviewRecord` are mutually needed by both packages as eagerly-resolved
pydantic field types and instantiated values. Importing either package's public
facade from the other re-enters a partially-initialised package during Python's
import machinery, so both sides imported private submodules directly instead.
The closing audit (`2026-07-02-import-centralization-audit`, finding
`plan-letter-hard-zero-not-reached`) investigated a `TYPE_CHECKING`-only fix and
confirmed all 5 sites are genuinely runtime-bound, not deferrable without a
structural change to the module boundary, and recommended either accepting the
ratchet-mode gate as steady state or opening a small ADR-driven follow-up to
break the cycle for real. This ADR is that follow-up.

## Considerations

- `WorkflowEvent` is instantiated at runtime in `review._actions` and used as a
  pydantic field type (`history: tuple[WorkflowEvent, ...]`) on `review._models`'s
  `LedgerReviewRecord` / `InvoiceReviewRecord`; pydantic v2 resolves field-type
  annotations eagerly at class-definition time, so `from __future__ import
  annotations` cannot defer this.
- `InvoiceReviewRecord` / `LedgerReviewRecord` are in turn used as pydantic field
  types on `workflow._models`'s `WorkflowState` (`invoice_reviews`,
  `ledger_reviews`), the same eager-resolution constraint in the opposite
  direction.
- `utc_now` (a re-export of `core.time.now`) is used as a live
  `Field(default_factory=utc_now)` callable on both review records — a bound
  function object needed at class-definition time, not an annotation.
- Neither `WorkflowEvent` nor `LedgerReviewRecord`/`InvoiceReviewRecord` depend on
  anything else in `application.workflow` or `application.review` respectively:
  `WorkflowEvent`'s own fields resolve against `core`/`core.identity` only, and
  the two review records resolve against `WorkflowEvent`, `utc_now`, `core`, and
  `domain.contribuyente` only. This is what makes a shared-leaf extraction clean
  rather than merely relocating the cycle.
- `WorkflowState` itself has 44 consumers across the codebase and stays exactly
  where it is; only the 4 minimal shared names move.

## Considered options

- **Option A — extract the 4 mutually-needed names into a new shared leaf module
  under `application/`.** Chosen. Precedented by the existing
  `application/_errors.py` top-level leaf module pattern (a private module with
  no sub-package parent, consumed by multiple sibling application sub-packages).
- **Option B — accept the ratchet-mode gate as permanent steady state
  (the audit's alternative recommendation).** Rejected: the extraction proved
  low-risk and behaviour-preserving on inspection (no consumer outside the two
  packages reaches the private submodules; every outside consumer already goes
  through the public `application.review` / `application.workflow` facades), so
  there was no reason to accept permanent debt when a clean fix was available.
- **Option C — move `WorkflowState` itself (and its full dependency surface) to
  break the cycle from the workflow side.** Rejected: `WorkflowState` has 44
  cross-codebase consumers; moving it is a large, high-blast-radius change for
  no additional benefit over moving the 4 minimal shared names that actually
  cause the mutual dependency.

## Constraints

- The fix must be behaviour-preserving: identical pydantic model identity,
  field types, validators, and `Field(default_factory=...)` semantics; every
  existing consumer (via the `application.review` / `application.workflow`
  facades) must be unaffected.
- The new shared module must not become a THIRD private cross-package import
  site: both `application.review` and `application.workflow` are descendants of
  the shared module's owning package (`application`), so importing from it is
  not a `Family-1` cross-package private import under the existing scanner rule
  (`owning_package` returns the common parent; sibling/descendant imports are
  exempt), matching the precedent set by `application/_errors.py`.

## Implementation

A new private leaf module, `aeat.application._workflow_review_models`, defines
`WorkflowEvent`, `LedgerReviewRecord`, and `InvoiceReviewRecord` (and re-exports
`utc_now` from `core.time.now`), with zero dependency on either
`application.review` or `application.workflow`. `workflow._models` imports the
three model classes from the shared module at the top of the file (removing its
own `WorkflowEvent` class definition and the deferred bottom-of-file
`from ..review._models import (InvoiceReviewRecord, LedgerReviewRecord)` plus the
now-unnecessary `WorkflowState.model_rebuild()` call). `review._models` imports
`InvoiceReviewRecord` / `LedgerReviewRecord` from the shared module and
re-exports them (dropping its own class definitions of the same two names).
`review._actions` imports `WorkflowEvent` and `utc_now` from the shared module
at runtime, and defers its only remaining `WorkflowState` reference (used solely
as a parameter/return annotation) under `TYPE_CHECKING`, importing it from the
public `application.workflow` facade rather than the private submodule. Every
consumer outside these two packages (`application.user_profile._orchestration`,
`application.auth._operator`, `application.invoices._projection`, and their
tests) is unaffected because they already import through the public facades,
which continue to re-export the same names — now sourced from the shared leaf
module instead of from each other's private submodule.

## Rationale

The 5 documented cycle-break sites collapse to a single, well-understood shape:
4 names with a genuine mutual runtime dependency and no other coupling to either
package's internals. Extracting them to a shared leaf module both packages
depend on (rather than depending on each other) is the standard fix for this
shape and requires no restructuring of either package's public surface, no
consumer-facing behaviour change, and no relaxation of either package's own
architecture. The precedent (`application/_errors.py`) already establishes that
a private, dependency-free leaf module living directly under `application/` and
consumed by multiple sibling sub-packages is an accepted pattern in this
codebase, so this is not a new architectural shape — it is the existing shape
applied to a case the original campaign's `TYPE_CHECKING`-only investigation
could not reach.

## Consequences

- Production Family-1 cross-package private imports for the
  `application.review` <-> `application.workflow` pair drop from 5 to 0; the
  `dev/import_hygiene_baseline.json` `sites` list for this exception is now
  permanently `[]`, and `src/aeat/tests/test_import_hygiene_gate.py` pins that.
- The two packages no longer import each other's private submodules at all;
  `import aeat.application.review` and `import aeat.application.workflow` each
  succeed cleanly and independently, in either order, with no partial-init
  re-entry hazard.
- A separate, pre-existing and unrelated production Family-1 regression (10
  sites, `adapters.persistence.profile.modelos_*` importing `domain.modelos`
  private submodules) was discovered as a side effect of re-running the scanner
  during this work. It predates this change (one committed on this branch via
  `05ab9eb2b2`, one still in-flight as uncommitted peer work under the
  `arch-remediation-ports-inversion` campaign) and is explicitly out of this
  ADR's scope per `full-tree-gate-must-distinguish-owner`; it is left for that
  campaign's own closeout to register or fix.
- Future symbols that develop a genuine mutual runtime dependency between these
  two packages (or any two sibling application sub-packages) should follow the
  same shared-leaf-module pattern rather than reintroducing a private
  cross-package import.
