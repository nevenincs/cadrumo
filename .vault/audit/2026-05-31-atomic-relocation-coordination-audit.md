---
tags:
  - '#audit'
  - '#atomic-relocation-coordination'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-atomic-relocation-coordination-adr]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-transient-metastate-sweep-audit]]"
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# `atomic-relocation-coordination` audit: `import-error-window-observed-on-eliminate-shims-branch`

## Scope

During a single suite-collection observation on the `chore/eliminate-shims`
worktree, `uv run --no-sync pytest --collect-only -q` returned 16 collection
errors driven by transient mid-flight symbol relocations. A second
collection 90 seconds later returned clean. The window is the observable
symptom of a coordination gap: relocations landed across multiple commits
rather than one atomic commit per symbol. This audit records the in-flight
relocations observed, classifies each, and references the ADR that closes
the gate going forward.

## Findings

### finding-1 — InvoiceKind canonical-home drift

Pathway: `aeat.domain.invoices` (consumer expectation) vs
`aeat.domain.iva._classification` (canonical site declared today).

Symptom: `ImportError: cannot import name 'InvoiceKind' from 'aeat.domain.invoices'` raised during collection of
`domain/test_runtime_repository_enrollment.py`,
`adapters/persistence/storage/test_runtime_migrated_repositories.py`,
and additional consumers. The `domain/invoices/__init__.py` re-exports
`IvaRate`, `IvaInvoiceClassification`, and `iva_rate_percentage` but not
`InvoiceKind`.

Severity: MEDIUM. Window self-closed; suite collects clean at HEAD. The
underlying coordination defect remains: consumer sweep landed in a
separate commit from the canonical-site move.

Remediation: Track as one Step under the existing
`codebase-solidification` plan via `vault plan step add`, naming the
Step `relocation:InvoiceKind`. The Step's commit subject carries the
same tag.

### finding-2 — ModeloDraftStatus canonical-home drift

Pathway: `aeat.adapters.outbound.aeat.export` (consumer expectation) vs
`aeat.domain.submission._protocols` (canonical site).

Symptom: `ImportError: cannot import name 'ModeloDraftStatus' from 'aeat.adapters.outbound.aeat.export'` raised during collection of
`application/workflow/test_engine.py`,
`application/filing/__init__.py` consumers, and
`adapters/outbound/aeat/export/test_preflight.py`. Roughly a dozen
consumers; `export/__init__.py` does not re-export the symbol.

Severity: MEDIUM. Same shape as finding-1.

Remediation: Track as one Step under the existing plan, named
`relocation:ModeloDraftStatus`. Atomic commit per the ADR.

### finding-3 — PROMOTE001_PROTECT_LIST deletion race

Pathway: `aeat.diagnostics._identity_placement`.

Symptom: `ImportError: cannot import name 'PROMOTE001_PROTECT_LIST'` from
`diagnostics/test_identity_primitive_placement.py`. The symbol was
removed under the `transient-metastate-sweep-audit` recommendation; the
test consumer was updated in a separate commit window.

Severity: LOW. Already resolved at HEAD. Listed as a witness for the
same coordination-defect class; no further remediation needed.

### finding-4 — no audit-grep surface for relocation history

The campaign's commit history does not consistently tag relocation
commits with `relocation:<symbol>` in the subject line. The next
codebase-solidification audit cannot enumerate completed relocations by
`git log --grep`.

Severity: LOW. Going-forward fix; the ADR mandates the tag.

## Recommendations

Apply the atomic-coordination rule encoded in the linked ADR to every
remaining and future symbol relocation. Add Steps for findings 1 and 2
under the existing `codebase-solidification` plan via the `vault plan
step add` CLI. Adopt the `relocation:<symbol>` commit-subject tag from
this point forward.

No retroactive sweep of prior commits; the ADR closes the gate going
forward only. The audit's three findings are factual observations, not
defects to roll back.
